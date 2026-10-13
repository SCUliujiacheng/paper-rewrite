import asyncio
import importlib.util
import json
from pathlib import Path

import httpx

from paper_rewrite.model import LocalModel


def test_evaluation_counts_retained_cases_not_success(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "evaluate", Path(__file__).parents[1] / "scripts/evaluate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def respond(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"content": "实验重复999次。", "stop_type": "eos"})

    monkeypatch.setattr(
        module, "LocalModel", lambda _: LocalModel(transport=httpx.MockTransport(respond))
    )
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {"id": "test", "text": "实验重复5次。", "language": "zh", "protected_terms": []}
        ),
        encoding="utf-8",
    )
    result = asyncio.run(module.evaluate(corpus, "http://127.0.0.1", 1))
    assert result["totals"]["zh"]["changed_cases"] == 0
    assert result["totals"]["zh"]["rejected_candidates"] == 1
    assert result["detector_evaluation"] == "not_run_no_commercial_credentials"
    assert result["model_artifact"] is None
    assert result["runtime"] is None
    assert result["backend_identity_verification"] == "not_verified"


def test_model_provenance_hashes_supplied_file_not_an_assumed_model(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "evaluate", Path(__file__).parents[1] / "scripts/evaluate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model = tmp_path / "custom.gguf"
    model.write_bytes(b"abc")
    result = module.artifact_metadata(model, "example/model", "revision-1")
    assert result == {
        "file": "custom.gguf",
        "repo": "example/model",
        "revision": "revision-1",
        "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "size_bytes": 3,
        "provenance": "local_file_verified_server_binding_not_verified",
    }
