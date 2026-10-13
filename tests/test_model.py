import httpx
import pytest

from paper_rewrite.model import LocalModel, ModelError


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://localhost.evil.test",
        "http://127.0.0.1@evil.test",
        "http://127.0.0.1:8080/?key=secret",
        "file:///tmp/model",
    ],
)
def test_model_rejects_nonlocal_or_ambiguous_endpoints(url):
    with pytest.raises(ValueError):
        LocalModel(url)


async def test_real_client_uses_completion_training_format():
    def respond(request):
        import json

        body = json.loads(request.content)
        assert request.url.path == "/completion"
        assert body["prompt"].startswith("Rewrite the text below")
        assert body["prompt"].endswith("\n\n实验重复5次。\n\n### Rewritten:\n\n")
        assert body["seed"] == 11
        assert body["n_predict"] == 2048
        return httpx.Response(
            200, json={"content": " 本实验共重复5次。 ", "stop_type": "eos", "truncated": False}
        )

    client = LocalModel(transport=httpx.MockTransport(respond))
    result = await client.complete("实验重复5次。", seed=11)
    assert result == "本实验共重复5次。"


@pytest.mark.parametrize(
    "reply",
    [
        {"content": ""},
        {"content": 123},
        {"content": "半句话", "stop_type": "limit"},
        {"content": "内容", "truncated": True},
        {"content": "x" * 5001},
    ],
)
async def test_bad_or_truncated_model_output_is_not_success(reply):
    client = LocalModel(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply)))
    with pytest.raises(ModelError):
        await client.complete("原文")


async def test_upstream_secret_details_never_reach_error():
    client = LocalModel(
        transport=httpx.MockTransport(lambda _: httpx.Response(500, text="secret-in-log"))
    )
    with pytest.raises(ModelError) as caught:
        await client.complete("original")
    assert "secret-in-log" not in str(caught.value)


async def test_unready_health_is_false():
    client = LocalModel(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    assert not await client.ready()
