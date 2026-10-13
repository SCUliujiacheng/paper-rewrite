"""Loopback-only workbench; no manuscript storage, logging, or analytics."""

import asyncio
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .detectors import GPTZeroDetector, validate_manual_report
from .guards import audit
from .model import create_model
from .pipeline import Rewriter
from .settings import default_language

Text = Annotated[str, StringConstraints(min_length=1, max_length=12000)]
Term = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RewriteRequest(RequestModel):
    text: Text
    language: Literal["zh", "en"] = "zh"
    protected_terms: list[Term] = Field(default_factory=list, max_length=30)
    candidates: int = Field(default=2, ge=1, le=3)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class CheckRequest(RequestModel):
    source: Text
    candidate: Annotated[str, StringConstraints(max_length=36000)]
    protected_terms: list[Term] = Field(default_factory=list, max_length=30)


class DetectRequest(RequestModel):
    source: Text
    candidate: Text
    consent: bool = False


class ImportRequest(RequestModel):
    source: Text
    candidate: Text
    report: dict


async def while_connected(request: Request, operation):
    """Keep one receive waiter alive; polling cancels middleware receive too early.

    FastAPI has consumed the validated JSON body before this helper runs. An
    upstream upload already received by a provider cannot be recalled, but no
    remaining comparison or candidate request should start after disconnect.
    """

    async def disconnected():
        while (await request.receive())["type"] != "http.disconnect":
            pass

    work = asyncio.create_task(operation)
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({work, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            raise HTTPException(499, "request_cancelled")
        return await work
    finally:
        for task in (work, watcher):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, watcher, return_exceptions=True)


def create_app(*, model=None, detector=None) -> FastAPI:
    model = model or create_model()
    detector = detector or GPTZeroDetector(os.getenv("GPTZERO_API_KEY"))
    rewriter = Rewriter(model)
    lock = asyncio.Lock()
    app = FastAPI(title="Paper Rewrite / 改稿台", version="0.1.0", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if origin and origin != expected:
            return JSONResponse({"detail": "cross_origin_denied"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "json_required"}, status_code=415)
            try:
                if int(request.headers.get("content-length", "0")) > 160000:
                    return JSONResponse({"detail": "request_too_large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "invalid_content_length"}, status_code=400)
            # Also bound chunked bodies, not only the client-supplied Content-Length.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 160000:
                    return JSONResponse({"detail": "request_too_large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self' data:; connect-src 'self'; "
                    "frame-ancestors 'none'; base-uri 'self'"
                ),
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # FastAPI's default includes invalid input text in the response.
        return JSONResponse(
            {"detail": "invalid_request", "fields": [list(item["loc"]) for item in error.errors()]},
            status_code=422,
        )

    @app.get("/api/health")
    async def health():
        return {
            "version": "0.1.0",
            "model": model.name,
            "model_ready": await model.ready(),
            "detector_configured": bool(os.getenv("GPTZERO_API_KEY")),
            "default_language": default_language(),
        }

    @app.post("/api/rewrite")
    async def rewrite(body: RewriteRequest, request: Request):
        if lock.locked():
            raise HTTPException(429, "model_busy")
        async with lock:
            try:
                return await while_connected(
                    request,
                    rewriter.rewrite(
                        body.text, body.language, body.protected_terms, body.candidates
                    ),
                )
            except ValueError as error:
                raise HTTPException(422, str(error)) from error

    @app.post("/api/check")
    async def check(body: CheckRequest):
        return audit(body.source, body.candidate, body.protected_terms)

    @app.post("/api/detect")
    async def detect(body: DetectRequest, request: Request):
        return await while_connected(
            request, detector.compare(body.source, body.candidate, consent=body.consent)
        )

    @app.post("/api/detector-report")
    async def import_report(body: ImportRequest):
        try:
            return validate_manual_report(body.report, body.source, body.candidate)
        except ValueError as error:
            raise HTTPException(422, "invalid_or_mismatched_detector_report") from error

    packaged = Path(__file__).parent / "static"
    development = Path(__file__).resolve().parents[2] / "web" / "dist"
    static = packaged if (packaged / "index.html").exists() else development
    if (static / "index.html").exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="workbench")
    return app
