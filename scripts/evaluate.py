"""Run the frozen synthetic smoke corpus. This is not a detector effectiveness benchmark."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from paper_rewrite.model import LocalModel
from paper_rewrite.pipeline import Rewriter


def artifact_metadata(path, repo=None, revision=None):
    if path is None:
        return None
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {
        "file": path.name,
        "repo": repo,
        "revision": revision,
        "sha256": digest,
        "size_bytes": path.stat().st_size,
        "provenance": "local_file_verified_server_binding_not_verified",
    }


async def evaluate(corpus, model_url, candidates, *, artifact=None, runtime=None):
    model = LocalModel(model_url)
    if not await model.ready():
        raise RuntimeError("Local model is not ready; no evaluation results were generated")
    results = []
    for line in corpus.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        report = await Rewriter(model).rewrite(
            case["text"], case["language"], case["protected_terms"], candidates
        )
        results.append(
            {"id": case["id"], "synthetic": True, "report": report.model_dump(mode="json")}
        )
        print(f"{case['id']}: {report.status} ({report.elapsed_seconds}s)", flush=True)
    totals = {}
    for lang in ("zh", "en"):
        group = [r["report"] for r in results if r["report"]["language"] == lang]
        totals[lang] = {
            "cases": len(group),
            "changed_cases": sum(r["output"] != r["source"] for r in group),
            "statuses": {
                s: sum(r["status"] == s for r in group)
                for s in ("completed", "partial", "failed", "unchanged")
            },
            "rejected_candidates": sum(
                a["audit"]["blocked"]
                for r in group
                for s in r["segments"]
                for a in s["attempts"]
                if a["audit"]
            ),
            "warning_cases": sum(
                any(i["severity"] == "warning" for s in r["segments"] for i in s["audit"]["issues"])
                for r in group
            ),
            "total_seconds": round(sum(r["elapsed_seconds"] for r in group), 3),
        }
    return {
        "scope": "synthetic_smoke_not_detector_benchmark",
        "measured_at": datetime.now(UTC).isoformat(),
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "model_artifact": artifact,
        "runtime": runtime,
        "backend_identity_verification": "not_verified",
        "detector_evaluation": "not_run_no_commercial_credentials",
        "human_semantic_review": "not_performed",
        "candidates": candidates,
        "totals": totals,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/smoke.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-url", default="http://127.0.0.1:8091")
    parser.add_argument("--candidates", type=int, default=2, choices=[1, 2, 3])
    parser.add_argument(
        "--model-file", type=Path, help="hash this local file; not a server attestation"
    )
    parser.add_argument("--model-repo")
    parser.add_argument("--model-revision")
    parser.add_argument("--runtime", help="operator-supplied runtime and hardware description")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a fresh output path; existing results are not overwritten")
    artifact = artifact_metadata(args.model_file, args.model_repo, args.model_revision)
    report = asyncio.run(
        evaluate(
            args.corpus, args.model_url, args.candidates, artifact=artifact, runtime=args.runtime
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(report["totals"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
