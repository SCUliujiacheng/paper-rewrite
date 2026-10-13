"""Contract tests use an HTTP transport fixture; no paid requests are made."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

SOURCE = "Original toy experiment."
OUTPUT = "Revised toy experiment."


def response_payload(version="2026-test"):
    document = {
        "document_classification": "MIXED",
        "predicted_class": "mixed",
        "class_probabilities": {"human": 0.2, "ai": 0.3, "mixed": 0.5},
        "confidence_category": "medium",
        "average_generated_prob": 0.4,
        "completely_generated_prob": 0.3,
        "overall_burstiness": 0.7,
        "paragraphs": [],
        "sentences": [],
    }
    result = {"documents": [document]}
    if version is not None:
        result["model_version"] = version
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("consent", [False, None, "true", 1])
async def test_only_literal_consent_allows_network(consent):
    from paper_rewrite.detectors import GPTZeroDetector

    def forbid_network(request):
        pytest.fail("Non-boolean consent must never send text")

    report = await GPTZeroDetector("test-secret", httpx.MockTransport(forbid_network)).compare(
        SOURCE, OUTPUT, consent=consent
    )
    assert report.status == "not_run"
    assert report.before is None and report.after is None
    assert report.measured_at is None


@pytest.mark.asyncio
async def test_missing_key_returns_not_configured_without_network():
    from paper_rewrite.detectors import GPTZeroDetector

    def forbid_network(request):
        pytest.fail("Missing API key must never send text")

    report = await GPTZeroDetector(None, httpx.MockTransport(forbid_network)).compare(
        SOURCE, OUTPUT, consent=True
    )
    assert report.status == "not_configured"


@pytest.mark.asyncio
async def test_completed_comparison_preserves_scores_timestamp_and_exact_hashes():
    from paper_rewrite.detectors import GPTZeroDetector

    requests = []

    def provider(request):
        requests.append(json.loads(request.content))
        assert request.url == "https://api.gptzero.me/v2/predict/text"
        assert request.headers["x-api-key"] == "test-secret"
        return httpx.Response(200, json=response_payload())

    report = await GPTZeroDetector("test-secret", httpx.MockTransport(provider)).compare(
        SOURCE, OUTPUT, consent=True
    )
    assert report.status == "completed"
    assert requests == [{"document": SOURCE}, {"document": OUTPUT}]
    assert report.before.probabilities == {"human": 0.2, "ai": 0.3, "mixed": 0.5}
    assert report.after.classification == "MIXED"
    assert report.before.raw["average_generated_prob"] == 0.4
    assert report.model_version == "2026-test"
    assert report.measured_at.utcoffset().total_seconds() == 0
    assert report.source_sha256 == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert report.output_sha256 == hashlib.sha256(OUTPUT.encode()).hexdigest()
    assert report.user_supplied is False
    assert "test-secret" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_missing_version_is_unknown_instead_of_inferred_latest():
    from paper_rewrite.detectors import GPTZeroDetector

    report = await GPTZeroDetector(
        "test-secret",
        httpx.MockTransport(lambda _: httpx.Response(200, json=response_payload(None))),
    ).compare(SOURCE, OUTPUT, consent=True)
    assert report.status == "completed"
    assert report.model_version == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_score", [-0.1, 1.1, float("nan"), "0.3", True])
async def test_invalid_probabilities_fail_closed(bad_score):
    from paper_rewrite.detectors import GPTZeroDetector

    payload = response_payload()
    payload["documents"][0]["class_probabilities"]["ai"] = bad_score
    report = await GPTZeroDetector(
        "test-secret",
        httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps(payload))),
    ).compare(SOURCE, OUTPUT, consent=True)
    assert report.status == "error"
    assert report.error == "invalid_response"
    assert report.before is None and report.after is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"documents": []},
        {"documents": [{"document_classification": "MIXED"}]},
        {
            "documents": [
                {
                    "document_classification": "MIXED",
                    "class_probabilities": {"human": 0.1, "ai": 0.1, "mixed": 0.1},
                }
            ]
        },
    ],
)
async def test_invalid_provider_schema_never_reports_completed(payload):
    from paper_rewrite.detectors import GPTZeroDetector

    report = await GPTZeroDetector(
        "test-secret", httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ).compare(SOURCE, OUTPUT, consent=True)
    assert report.status == "error"
    assert report.error == "invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(429, "rate_limited"), (401, "http_error")])
async def test_http_errors_do_not_expose_keys_or_provider_body(status, code):
    from paper_rewrite.detectors import GPTZeroDetector

    report = await GPTZeroDetector(
        "test-secret",
        httpx.MockTransport(
            lambda _: httpx.Response(status, text="test-secret private provider details")
        ),
    ).compare(SOURCE, OUTPUT, consent=True)
    assert report.status == "error"
    assert report.error == code
    assert "test-secret" not in report.model_dump_json()
    assert "private provider details" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_timeout_returns_safe_error():
    from paper_rewrite.detectors import GPTZeroDetector

    def timeout(request):
        raise httpx.ReadTimeout("test-secret", request=request)

    report = await GPTZeroDetector("test-secret", httpx.MockTransport(timeout)).compare(
        SOURCE, OUTPUT, consent=True
    )
    assert report.status == "error"
    assert report.error == "timeout"
    assert "test-secret" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_unbounded_integer_score_is_rejected_without_an_exception():
    from paper_rewrite.detectors import GPTZeroDetector

    payload = response_payload()
    payload["documents"][0]["class_probabilities"]["ai"] = 10**1000
    report = await GPTZeroDetector(
        "test-secret", httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ).compare(SOURCE, OUTPUT, consent=True)
    assert report.status == "error"
    assert report.error == "invalid_response"


@pytest.mark.asyncio
async def test_redirect_does_not_forward_private_text_or_key():
    from paper_rewrite.detectors import GPTZeroDetector

    def redirect(request):
        assert request.url.host == "api.gptzero.me"
        return httpx.Response(307, headers={"Location": "https://other.example/collect"})

    report = await GPTZeroDetector("test-secret", httpx.MockTransport(redirect)).compare(
        SOURCE, OUTPUT, consent=True
    )
    assert report.status == "error"
    assert report.error == "http_error"


@pytest.mark.asyncio
async def test_second_text_failure_cannot_report_success_for_a_partial_comparison():
    from paper_rewrite.detectors import GPTZeroDetector

    def provider(request):
        if json.loads(request.content)["document"] == SOURCE:
            return httpx.Response(200, json=response_payload())
        return httpx.Response(429, text="test-secret")

    report = await GPTZeroDetector("test-secret", httpx.MockTransport(provider)).compare(
        SOURCE, OUTPUT, consent=True
    )
    assert report.status == "error"
    assert report.error == "rate_limited"
    assert report.before is None and report.after is None


def manual_payload():
    document = response_payload()["documents"][0]
    measurement = {
        "probabilities": document["class_probabilities"],
        "classification": "MIXED",
        "raw": document,
    }
    return {
        "detector": "GPTZero",
        "status": "completed",
        "model_version": "2026-test",
        "measured_at": "2026-10-14T01:00:00Z",
        "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(OUTPUT.encode()).hexdigest(),
        "before": measurement,
        "after": measurement,
        "provenance": "api",
        "user_supplied": False,
    }


def test_manual_report_is_bound_to_text_and_always_labeled_user_supplied():
    from paper_rewrite.detectors import validate_manual_report

    report = validate_manual_report(manual_payload(), SOURCE, OUTPUT)
    assert report.status == "completed"
    assert report.provenance == "user_supplied"
    assert report.user_supplied is True


@pytest.mark.parametrize("change", ["hash", "status", "missing_measurement", "bad_raw", "time"])
def test_manual_report_rejects_unbound_or_inconsistent_claims(change):
    from paper_rewrite.detectors import validate_manual_report

    payload = manual_payload()
    if change == "hash":
        payload["output_sha256"] = "0" * 64
    elif change == "status":
        payload["status"] = "not_run"
    elif change == "missing_measurement":
        payload["before"] = None
    elif change == "bad_raw":
        payload["before"]["probabilities"] = {"human": 0.5, "ai": 0.1, "mixed": 0.4}
    else:
        payload["measured_at"] = "2026-10-14T01:00:00"
    with pytest.raises(ValueError):
        validate_manual_report(payload, SOURCE, OUTPUT)


def test_smoke_samples_are_original_bilingual_and_preserve_fixture_terms():
    path = Path(__file__).parents[1] / "data" / "smoke.jsonl"
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(samples) >= 14
    assert len({sample["id"] for sample in samples}) == len(samples)
    assert sum(sample["language"] == "zh" for sample in samples) >= 8
    assert sum(sample["language"] == "en" for sample in samples) >= 6
    for sample in samples:
        assert sample["synthetic"] is True
        assert sample["license"] == "CC0"
        assert sample["source"] == "project-authored synthetic smoke sample"
        assert all(term in sample["text"] for term in sample["protected_terms"])
        if sample["language"] == "zh":
            assert 100 <= len(sample["text"]) <= 250
