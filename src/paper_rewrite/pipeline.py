"""Bounded rewriting; rejected candidates are visible and never silently accepted."""

import hashlib
import time
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from .documents import split_document
from .guards import AuditResult, audit
from .model import ModelError


class Model(Protocol):
    name: str

    async def complete(self, text: str, seed: int = 0) -> str: ...


class Attempt(BaseModel):
    text: str
    audit: AuditResult | None = None
    error: str | None = None


class SegmentReport(BaseModel):
    id: int
    original: str
    output: str
    status: Literal["rewritten", "retained", "skipped", "failed"]
    audit: AuditResult
    attempts: list[Attempt] = Field(default_factory=list)


class RewriteReport(BaseModel):
    source: str
    output: str
    segments: list[SegmentReport]
    warnings: list[str]
    model: str
    language: Literal["zh", "en"]
    elapsed_seconds: float
    requires_review: Literal[True] = True
    detector_status: Literal["not_run"] = "not_run"
    source_sha256: str
    output_sha256: str
    status: Literal["completed", "partial", "failed", "unchanged"]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Rewriter:
    def __init__(self, model: Model):
        self.model = model

    async def rewrite(
        self,
        text: str,
        language: str = "zh",
        protected_terms: list[str] | None = None,
        candidates: int = 2,
    ) -> RewriteReport:
        if language not in {"zh", "en"} or type(candidates) is not int or not 1 <= candidates <= 3:
            raise ValueError("invalid language or candidate count")
        terms = list(dict.fromkeys(t.strip() for t in (protected_terms or []) if t.strip()))
        if len(terms) > 30 or any(len(term) > 100 for term in terms):
            raise ValueError("at most 30 protected terms of 100 characters each")
        segments = split_document(text)
        started = time.monotonic()
        reports: list[SegmentReport] = []
        assembled: list[str] = []
        model_failed = False
        for segment in segments:
            original = segment.text
            relevant = [term for term in terms if term in original]
            check = audit(original, original, relevant)
            output = original
            attempts: list[Attempt] = []
            status = "skipped"
            if segment.rewriteable:
                status = "retained"
                if model_failed:
                    status = "failed"
                else:
                    for attempt_index in range(candidates):
                        try:
                            proposal = (
                                await self.model.complete(
                                    original, seed=42 + segment.id * 3 + attempt_index
                                )
                            ).strip()
                        except ModelError as error:
                            # A bad candidate is local; a broken service would repeat timeouts.
                            attempts.append(Attempt(text="", error=str(error)))
                            status = "failed"
                            model_failed = str(error) not in {
                                "model_output_truncated",
                                "model_empty_or_invalid_output",
                            }
                            break
                        candidate_audit = audit(original, proposal, relevant)
                        attempts.append(Attempt(text=proposal, audit=candidate_audit))
                        if not candidate_audit.blocked and proposal != original:
                            output, check, status = proposal, candidate_audit, "rewritten"
                            break
                    if status == "retained" and attempts and attempts[-1].audit:
                        check = attempts[-1].audit
            reports.append(
                SegmentReport(
                    id=segment.id,
                    original=original,
                    output=output,
                    status=status,
                    audit=check,
                    attempts=attempts,
                )
            )
            assembled.append(output + segment.separator)
        output = "".join(assembled)
        rewritten = any(r.status == "rewritten" for r in reports)
        incomplete = any(r.status in {"failed", "retained"} for r in reports)
        status = (
            "partial"
            if rewritten and incomplete
            else "completed"
            if rewritten
            else "failed"
            if any(r.status == "failed" for r in reports)
            else "unchanged"
        )
        return RewriteReport(
            source=text,
            output=output,
            segments=reports,
            model=self.model.name,
            language=language,
            elapsed_seconds=round(time.monotonic() - started, 3),
            source_sha256=text_hash(text),
            output_sha256=text_hash(output),
            status=status,
            warnings=["human_review_required"]
            + (["original_retained_in_some_segments"] if incomplete else []),
        )
