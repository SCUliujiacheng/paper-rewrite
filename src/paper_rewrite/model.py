"""The upstream model is a completion model, not a chat model.

Prompt format from sgaofen/humanizer-local-model (Apache-2.0); see NOTICE.
No HTTP proxies, redirects, or remote model hosts: drafts stay on loopback.
"""

import ipaddress
from urllib.parse import urlsplit

import httpx

INSTRUCTION = (
    "Rewrite the text below so it reads like a person wrote it, not a language model.\n\n"
    "Reorganize it as you see fit. Vary sentence length on purpose. Cut hedging,\n"
    "throat-clearing, and any sentence that only announces what comes next.\n"
    "Prefer the concrete word over the abstract one. It is fine to sound uneven.\n\n"
    "Every fact, number, unit, date, name and quotation must survive unchanged."
)
SEPARATOR = "\n\n### Rewritten:\n\n"


class ModelError(RuntimeError):
    """A safe user-visible error, without upstream response bodies or input text."""


class LocalModel:
    def __init__(
        self,
        url: str = "http://127.0.0.1:8091",
        *,
        name: str = "humanizer-12b",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 180,
    ):
        parsed = urlsplit(url)
        try:
            local = (
                parsed.hostname == "localhost"
                or ipaddress.ip_address(parsed.hostname or "").is_loopback
            )
            port = parsed.port
        except ValueError:
            local, port = False, None
        if (
            not local
            or parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or port == 0
        ):
            raise ValueError("model endpoint must be a loopback HTTP origin")
        self.url = url.rstrip("/")
        self.name = name
        self.transport = transport
        self.timeout = timeout

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.url,
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
            timeout=timeout or self.timeout,
        )

    async def complete(self, text: str, seed: int = 0) -> str:
        body = {
            "prompt": INSTRUCTION + "\n\n" + text.strip() + SEPARATOR,
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 0,
            "min_p": 0,
            "repeat_penalty": 1.0,
            "n_predict": 2048,
            "seed": seed,
            "stream": False,
            "cache_prompt": False,
        }
        try:
            async with self._client() as client:
                response = await client.post("/completion", json=body)
                response.raise_for_status()
                if len(response.content) > 100_000:
                    raise ModelError("model_response_too_large")
                result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ModelError("model_unavailable_or_invalid_response") from error
        if not isinstance(result, dict):
            raise ModelError("model_invalid_response")
        content = result.get("content")
        if (
            result.get("truncated")
            or result.get("stop_type") == "limit"
            or result.get("stopped_limit")
        ):
            raise ModelError("model_output_truncated")
        if not isinstance(content, str) or not content.strip() or len(content) > 5000:
            raise ModelError("model_empty_or_invalid_output")
        return content.strip()

    async def ready(self) -> bool:
        try:
            async with self._client(timeout=2) as client:
                response = await client.get("/health")
                return response.status_code == 200 and response.json().get("status") == "ok"
        except (httpx.HTTPError, ValueError, AttributeError):
            return False
