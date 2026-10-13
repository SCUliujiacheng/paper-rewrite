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
        assert body["temperature"] == 1.0
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


async def test_sampling_experiment_temperature_reaches_local_completion():
    def respond(request):
        import json

        body = json.loads(request.content)
        assert body["temperature"] == 0.35
        assert body["prompt"].endswith("\n\n实验重复5次。\n\n### Rewritten:\n\n")
        return httpx.Response(200, json={"content": "本实验重复5次。", "stop_type": "eos"})

    model = LocalModel(temperature=0.35, transport=httpx.MockTransport(respond))
    assert await model.complete("实验重复5次。") == "本实验重复5次。"


@pytest.mark.parametrize("temperature", [-0.1, 2.1, float("nan"), float("inf"), True])
def test_invalid_sampling_setting_rejected_before_network(temperature):
    with pytest.raises(ValueError):
        LocalModel(temperature=temperature)


async def test_chat_backend_uses_delimited_manuscript_terms_and_official_sampling():
    import json

    from paper_rewrite.model import LocalChatModel

    def respond(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert "authorization" not in request.headers
        assert body["model"] == "qwen3.5-4b"
        assert body["messages"][0]["role"] == "system"
        assert "uncertainty" in body["messages"][0]["content"]
        message = body["messages"][1]
        assert message["role"] == "user"
        data = json.loads(message["content"].split("<manuscript_data>\n")[1].split("\n</")[0])
        assert data == {"source": "BM25可能适用于检索。", "protected_terms": ["BM25"]}
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.8 and body["top_k"] == 20 and body["min_p"] == 0
        assert body["presence_penalty"] == 1.5 and body["repeat_penalty"] == 1.0
        assert body["max_tokens"] == 2048 and body["n"] == 1
        assert body["seed"] == 12 and body["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "BM25可能用于检索。"},
                    }
                ]
            },
        )

    model = LocalChatModel(transport=httpx.MockTransport(respond))
    assert await model.complete("BM25可能适用于检索。", 12, ["BM25"]) == "BM25可能用于检索。"


@pytest.mark.parametrize(
    "url", ["https://example.com", "http://localhost.evil.test", "file:///tmp"]
)
def test_chat_backend_rejects_remote_or_ambiguous_endpoints(url):
    from paper_rewrite.model import LocalChatModel

    with pytest.raises(ValueError):
        LocalChatModel(url)


@pytest.mark.parametrize(
    "reply,code",
    [
        ({"choices": []}, "model_invalid_response"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
            "model_output_truncated",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
            "model_empty_or_invalid_output",
        ),
        (
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "<think>private</think>Text"}}
                ]
            },
            "model_reasoning_output",
        ),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "Text", "reasoning_content": "private reasoning"},
                    }
                ]
            },
            "model_reasoning_output",
        ),
        (
            {"choices": [{"finish_reason": "tool_calls", "message": {"content": "Text"}}]},
            "model_invalid_response",
        ),
    ],
)
async def test_chat_malformed_reasoning_or_truncated_reply_is_not_success(reply, code):
    from paper_rewrite.model import LocalChatModel

    model = LocalChatModel(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply)))
    with pytest.raises(ModelError) as error:
        await model.complete("PRIVATE-MANUSCRIPT")
    assert str(error.value) == code
    assert "PRIVATE" not in str(error.value)


async def test_chat_http_error_and_timeout_are_redacted():
    from paper_rewrite.model import LocalChatModel

    def timeout(request):
        raise httpx.ReadTimeout("PRIVATE-MANUSCRIPT", request=request)

    for transport in [
        httpx.MockTransport(timeout),
        httpx.MockTransport(lambda _: httpx.Response(500, text="PRIVATE-MANUSCRIPT")),
    ]:
        with pytest.raises(ModelError) as caught:
            await LocalChatModel(transport=transport).complete("original")
        assert str(caught.value) == "model_unavailable_or_invalid_response"


def test_factory_keeps_humanizer_default_and_qwen_uses_its_own_defaults(monkeypatch):
    from paper_rewrite.model import LocalChatModel, create_model

    for name in ["PAPER_MODEL_BACKEND", "PAPER_MODEL_URL", "PAPER_MODEL_NAME"]:
        monkeypatch.delenv(name, raising=False)
    assert type(create_model()) is LocalModel
    assert create_model().temperature == 1.0
    monkeypatch.setenv("PAPER_MODEL_BACKEND", "qwen")
    monkeypatch.setenv("PAPER_MODEL_NAME", "operator-model-alias")
    monkeypatch.setenv("PAPER_MODEL_URL", "http://127.0.0.1:9999")
    model = create_model()
    assert isinstance(model, LocalChatModel)
    assert model.name == "operator-model-alias"
    assert model.url == "http://127.0.0.1:9999"
    assert model.temperature == 0.7
    assert create_model(backend="humanizer", temperature=0.35).temperature == 0.35
    with pytest.raises(ValueError):
        create_model(backend="remote")


async def test_original_completion_ignores_optional_terms_without_changing_upstream_prompt():
    from paper_rewrite.model import INSTRUCTION, SEPARATOR

    def respond(request):
        import json

        assert json.loads(request.content)["prompt"] == INSTRUCTION + "\n\nText" + SEPARATOR
        return httpx.Response(200, json={"content": "Revised text", "stop_type": "eos"})

    model = LocalModel(transport=httpx.MockTransport(respond))
    assert await model.complete("Text", protected_terms=["Text"]) == "Revised text"
