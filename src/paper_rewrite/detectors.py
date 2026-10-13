"""Opt-in detector comparison. Scores describe a provider prediction, not authorship."""

import hashlib
import math
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _probabilities(value: Any) -> dict[str, float]:
    allowed = {"human", "ai", "mixed", "ai_paraphrased", "human_paraphrased"}
    if not isinstance(value, dict) or not {"human", "ai", "mixed"} <= value.keys():
        raise ValueError("Missing class probabilities")
    if not value.keys() <= allowed:
        raise ValueError("Unsupported probability classes")
    if any(
        type(score) not in (int, float) or not 0 <= score <= 1 or not math.isfinite(score)
        for score in value.values()
    ):
        raise ValueError("Invalid probability")
    if not math.isclose(sum(value.values()), 1.0, abs_tol=0.001):
        raise ValueError("Class probabilities must sum to one")
    return value


class _RawDocument(BaseModel):
    """Retain validated score fields only; do not retain text, keys or unknown metadata."""

    model_config = ConfigDict(extra="ignore")
    document_classification: Literal["HUMAN_ONLY", "MIXED", "AI_ONLY"]
    class_probabilities: dict[str, float]
    predicted_class: (
        Literal["human", "ai", "mixed", "ai_paraphrased", "human_paraphrased"] | None
    ) = None
    confidence_category: Literal["high", "medium", "low"] | None = None
    average_generated_prob: float | None = Field(default=None, ge=0, le=1, strict=True)
    completely_generated_prob: float | None = Field(default=None, ge=0, le=1, strict=True)

    @field_validator("class_probabilities", mode="before")
    @classmethod
    def validate_probabilities(cls, value: Any) -> dict[str, float]:
        return _probabilities(value)


class DetectorMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    probabilities: dict[str, float]
    classification: Literal["HUMAN_ONLY", "MIXED", "AI_ONLY"]
    raw: dict[str, Any]
    model_version: str = "unknown"

    @field_validator("probabilities", mode="before")
    @classmethod
    def validate_probabilities(cls, value: Any) -> dict[str, float]:
        return _probabilities(value)

    @model_validator(mode="after")
    def bind_raw_values(self) -> "DetectorMeasurement":
        raw = _RawDocument.model_validate(self.raw)
        if raw.class_probabilities != self.probabilities:
            raise ValueError("Raw probability mismatch")
        if raw.document_classification != self.classification:
            raise ValueError("Raw classification mismatch")
        self.raw = raw.model_dump(exclude_none=True)
        return self


class DetectorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detector: Literal["GPTZero"] = "GPTZero"
    status: Literal["completed", "not_configured", "not_run", "error"]
    model_version: str = "unknown"
    measured_at: datetime | None = None
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    before: DetectorMeasurement | None = None
    after: DetectorMeasurement | None = None
    error: (
        Literal["timeout", "rate_limited", "http_error", "network_error", "invalid_response"] | None
    ) = None
    provenance: Literal["api", "user_supplied"] = "api"
    user_supplied: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def enforce_status(self) -> "DetectorReport":
        if self.measured_at is not None and self.measured_at.tzinfo is None:
            raise ValueError("Measurement time must include timezone")
        if self.status == "completed":
            if self.before is None or self.after is None or self.measured_at is None or self.error:
                raise ValueError("Completed report requires both measurements and time")
        elif self.before is not None or self.after is not None:
            raise ValueError("Uncompleted report cannot contain scores")
        if self.status in ("not_run", "not_configured") and self.measured_at is not None:
            raise ValueError("Unrun report cannot claim a measurement time")
        if (self.status == "error") != (self.error is not None):
            raise ValueError("Error code must match status")
        return self


class GPTZeroDetector:
    def __init__(
        self,
        api_key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        timeout_seconds: float = 30,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    async def compare(self, source: str, candidate: str, consent: bool) -> DetectorReport:
        common = {"source_sha256": _sha256(source), "output_sha256": _sha256(candidate)}
        # Identity comparison intentionally rejects truthy strings and integers.
        if consent is not True:
            return DetectorReport(status="not_run", **common)
        if not self._api_key:
            return DetectorReport(status="not_configured", **common)
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self._timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                before = await self._measure(client, source)
                after = await self._measure(client, candidate)
            version = (
                before.model_version if before.model_version == after.model_version else "unknown"
            )
            return DetectorReport(
                status="completed",
                measured_at=datetime.now(UTC),
                model_version=version,
                before=before,
                after=after,
                **common,
            )
        except httpx.TimeoutException:
            code = "timeout"
        except httpx.HTTPStatusError as exc:
            code = "rate_limited" if exc.response.status_code == 429 else "http_error"
        except httpx.RequestError:
            code = "network_error"
        except (ValueError, TypeError, KeyError, ValidationError):
            code = "invalid_response"
        # Do not stringify provider errors: they may include request headers or text.
        return DetectorReport(status="error", error=code, measured_at=datetime.now(UTC), **common)

    async def _measure(self, client: httpx.AsyncClient, text: str) -> DetectorMeasurement:
        response = await client.post(
            "https://api.gptzero.me/v2/predict/text",
            headers={"x-api-key": self._api_key, "Accept": "application/json"},
            json={"document": text},
        )
        response.raise_for_status()
        payload = response.json()
        documents = payload["documents"]
        if not isinstance(documents, list) or len(documents) != 1:
            raise ValueError("Expected one document")
        raw = _RawDocument.model_validate(documents[0])
        version = payload.get("model_version", payload.get("version", "unknown"))
        if not isinstance(version, str) or not version.strip():
            version = "unknown"
        return DetectorMeasurement(
            probabilities=raw.class_probabilities,
            classification=raw.document_classification,
            raw=raw.model_dump(exclude_none=True),
            model_version=version,
        )


def validate_manual_report(payload: Any, source: str, candidate: str) -> DetectorReport:
    """Validate reported values and hashes, never authenticate a claimed detector run."""
    try:
        report = DetectorReport.model_validate(payload)
        if report.source_sha256 != _sha256(source) or report.output_sha256 != _sha256(candidate):
            raise ValueError("Text hashes do not match")
    except (ValidationError, ValueError, TypeError):
        # Avoid leaking raw imported content through Pydantic's input_value diagnostics.
        raise ValueError("Invalid detector report or text hash mismatch") from None
    return report.model_copy(update={"provenance": "user_supplied", "user_supplied": True})
