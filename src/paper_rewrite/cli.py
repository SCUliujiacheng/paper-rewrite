"""Command-line entry points use the same checks and pipeline as the workbench."""

import argparse
import asyncio
import json
import os
import sys
import threading
import webbrowser
from pathlib import Path

from .guards import audit
from .model import create_model
from .pipeline import Rewriter
from .settings import default_language


def read_document(path: Path) -> str:
    if path.stat().st_size > 100_000:
        raise ValueError("input_file_too_large")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="改稿台 / Paper Rewrite — local rewriting and review"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="open local workbench")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true")
    serve.add_argument("--backend", choices=["humanizer", "qwen"])
    check = sub.add_parser("check", help="compare two UTF-8 files without a model")
    check.add_argument("source", type=Path)
    check.add_argument("candidate", type=Path)
    check.add_argument("--keep", action="append", default=[])
    rewrite = sub.add_parser("rewrite", help="rewrite using a local completion or chat model")
    rewrite.add_argument("source", type=Path)
    rewrite.add_argument("-o", "--output", required=True, type=Path)
    rewrite.add_argument("--report", type=Path)
    rewrite.add_argument("--language", choices=["zh", "en"], default=default_language())
    rewrite.add_argument("--candidates", type=int, choices=[1, 2, 3], default=2)
    rewrite.add_argument("--keep", action="append", default=[])
    rewrite.add_argument("--backend", choices=["humanizer", "qwen"])
    rewrite.add_argument(
        "--model-url", default=os.getenv("PAPER_MODEL_URL", "http://127.0.0.1:8091")
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn

            from .app import create_app

            if not 1 <= args.port <= 65535:
                raise ValueError("invalid_port")
            application = create_app(model=create_model(backend=args.backend))
            if args.open:
                timer = threading.Timer(1.0, webbrowser.open, [f"http://127.0.0.1:{args.port}"])
                timer.daemon = True
                timer.start()
            uvicorn.run(
                application,
                host="127.0.0.1",
                port=args.port,
                access_log=False,
            )
            return 0
        source = read_document(args.source)
        if args.command == "check":
            result = audit(source, read_document(args.candidate), args.keep)
            print(result.model_dump_json(indent=2))
            return 2 if result.blocked else 0
        targets = [args.output] + ([args.report] if args.report else [])
        if len({p.resolve() for p in targets}) != len(targets):
            raise ValueError("output_and_report_must_differ")
        if any(path.exists() or path.resolve() == args.source.resolve() for path in targets):
            raise ValueError("output_exists_choose_a_new_path")
        model = create_model(args.model_url, backend=args.backend)
        result = asyncio.run(
            Rewriter(model).rewrite(source, args.language, args.keep, args.candidates)
        )
        if result.status == "failed":
            print("model_failed: no rewritten file created", file=sys.stderr)
            return 3
        with args.output.open("x", encoding="utf-8", newline="") as handle:
            handle.write(result.output)
        if args.report:
            with args.report.open("x", encoding="utf-8") as handle:
                handle.write(result.model_dump_json(indent=2) + "\n")
        print(json.dumps({"status": result.status, "requires_review": True}, ensure_ascii=False))
        return 0 if result.status == "completed" else 2
    except (OSError, ValueError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
