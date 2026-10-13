"""Download published assets through verified, resumable HTTP byte ranges.

Only the Python standard library is required. Downloaded files are never executed.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(path: Path) -> tuple[int, int] | None:
    return (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None


def download_asset(
    url: str,
    destination: str | Path,
    expected_size: int,
    sha256: str,
    *,
    workers: int = 8,
    part_size: int = 4 * 1024 * 1024,
    retries: int = 3,
    timeout: float = 60,
    replace_invalid: bool = False,
    reuse_prefix: bool = False,
) -> Path:
    """Publish a file atomically only after its size and required SHA256 agree.

    A sibling cache stores completed ranges and their hashes. Retry reads only
    verified cache parts. Existing incomplete files remain intact until replacement.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise ValueError("A complete SHA256 is required")
    if urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError("Only HTTP(S) asset URLs are supported")
    if not 1 <= workers <= 8 or part_size < 1 or expected_size < 1 or retries < 0 or timeout <= 0:
        raise ValueError("Invalid download limits; workers must be between 1 and 8")
    sha256 = sha256.lower()
    target = Path(destination)
    original_identity = _identity(target)
    if original_identity is not None:
        if original_identity[0] == expected_size and _sha256(target) == sha256:
            print(f"Verified existing asset: {target}", flush=True)
            return target
        if not replace_invalid:
            raise FileExistsError(
                f"Existing asset is invalid; explicit replacement required: {target}"
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Identity-specific cache prevents mixing parts from different publications.
    cache_key = hashlib.sha256(f"{url}|{sha256}|{expected_size}|{part_size}".encode()).hexdigest()[
        :16
    ]
    cache = target.parent / f".{target.name}.{cache_key}.parts"
    cache.mkdir(exist_ok=True)
    manifest = {"url": url, "sha256": sha256, "size": expected_size, "part_size": part_size}
    manifest_path = cache / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Download cache metadata does not match the requested asset")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ranges = [
        (start, min(start + part_size, expected_size) - 1)
        for start in range(0, expected_size, part_size)
    ]

    def part_path(start: int) -> Path:
        return cache / f"{start:012d}.part"

    rejected_prefix = cache / "prefix_rejected"
    if (
        reuse_prefix
        and replace_invalid
        and original_identity is not None
        and original_identity[0] < expected_size
        and not rejected_prefix.exists()
    ):
        # Opt-in only: a prior partial file is a prefix, never an authenticated
        # publication. The mandatory whole-file hash still gates final replacement.
        with target.open("rb") as prefix:
            for start, end in ranges:
                size = end - start + 1
                if end >= original_identity[0]:
                    break
                part = part_path(start)
                if part.exists() and part.with_suffix(".sha256").exists():
                    prefix.seek(size, 1)
                    continue
                digest = hashlib.sha256()
                temporary = part.with_suffix(".pending")
                with temporary.open("wb") as stream:
                    remaining = size
                    while remaining:
                        chunk = prefix.read(min(256 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Existing prefix changed while being read")
                        stream.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                os.replace(temporary, part)
                part.with_suffix(".sha256").write_text(digest.hexdigest(), encoding="ascii")

    def fetch_part(start: int, end: int) -> int:
        path = part_path(start)
        checksum_path = path.with_suffix(".sha256")
        size = end - start + 1
        if path.exists() and checksum_path.exists() and path.stat().st_size == size:
            checksum = checksum_path.read_text(encoding="ascii").strip()
            if re.fullmatch(r"[0-9a-f]{64}", checksum) and _sha256(path) == checksum:
                return size
        temporary = path.with_suffix(".pending")
        for attempt in range(retries + 1):
            try:
                request = Request(
                    url,
                    headers={
                        "Range": f"bytes={start}-{end}",
                        "Accept-Encoding": "identity",
                        "User-Agent": "paper-rewrite-asset-fetch/0.1",
                        "Cache-Control": "no-cache",
                    },
                )
                digest = hashlib.sha256()
                with urlopen(request, timeout=timeout) as response:
                    if response.status != 206:
                        raise ValueError(f"Server did not honor byte range {start}-{end}")
                    wanted = f"bytes {start}-{end}/{expected_size}"
                    if response.headers.get("Content-Range") != wanted:
                        raise ValueError(f"Content-Range mismatch for {start}-{end}")
                    length = response.headers.get("Content-Length")
                    if length is not None and int(length) != size:
                        raise ValueError(f"Content-Length mismatch for {start}-{end}")
                    received = 0
                    with temporary.open("wb") as stream:
                        while received < size:
                            chunk = response.read(min(256 * 1024, size - received))
                            if not chunk:
                                raise ValueError(f"Truncated range {start}-{end}")
                            stream.write(chunk)
                            digest.update(chunk)
                            received += len(chunk)
                        if response.read(1):
                            raise ValueError(f"Oversized range {start}-{end}")
                os.replace(temporary, path)
                checksum_path.write_text(digest.hexdigest(), encoding="ascii")
                return size
            except (OSError, URLError, ValueError) as error:
                temporary.unlink(missing_ok=True)
                if attempt == retries:
                    raise error
                time.sleep(min(2**attempt, 8))
        raise RuntimeError("Unreachable retry state")

    started = time.monotonic()
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_part, start, end) for start, end in ranges]
        try:
            for future in as_completed(futures):
                completed += future.result()
                elapsed = time.monotonic() - started
                print(
                    f"{target.name}: {completed}/{expected_size} bytes "
                    f"({completed / expected_size:.1%}), {elapsed:.1f}s",
                    flush=True,
                )
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    assembled: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.name}.assembling-", delete=False
        ) as stream:
            assembled = Path(stream.name)
            for start, _ in ranges:
                with part_path(start).open("rb") as part:
                    shutil.copyfileobj(part, stream, length=1024 * 1024)
            stream.flush()
            os.fsync(stream.fileno())
        if assembled.stat().st_size != expected_size or _sha256(assembled) != sha256:
            # Discard only this utility's known range files, allowing a clean retry.
            for start, _ in ranges:
                part_path(start).unlink(missing_ok=True)
                part_path(start).with_suffix(".sha256").unlink(missing_ok=True)
            rejected_prefix.write_text("Whole-file verification failed", encoding="ascii")
            raise ValueError("Downloaded asset SHA256 or final size does not match")
        if _identity(target) != original_identity:
            raise FileExistsError("Destination changed during download; original file preserved")
        os.replace(assembled, target)
        assembled = None
        for start, _ in ranges:
            part_path(start).unlink(missing_ok=True)
            part_path(start).with_suffix(".sha256").unlink(missing_ok=True)
            part_path(start).with_suffix(".pending").unlink(missing_ok=True)
        manifest_path.unlink()
        rejected_prefix.unlink(missing_ok=True)
        cache.rmdir()
        print(f"SHA256 verified: {sha256}  {target}", flush=True)
        return target
    finally:
        if assembled is not None:
            assembled.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--part-mib", type=int, choices=[4, 8], default=4)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--replace-invalid", action="store_true")
    parser.add_argument("--reuse-prefix", action="store_true")
    args = parser.parse_args()
    download_asset(
        args.url,
        args.destination,
        args.size,
        args.sha256,
        workers=args.workers,
        part_size=args.part_mib * 1024 * 1024,
        retries=args.retries,
        timeout=args.timeout,
        replace_invalid=args.replace_invalid,
        reuse_prefix=args.reuse_prefix,
    )


if __name__ == "__main__":
    main()
