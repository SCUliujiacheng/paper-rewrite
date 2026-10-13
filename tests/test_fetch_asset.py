import hashlib
import importlib.util
import threading
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location(
    "fetch_asset", Path(__file__).resolve().parents[1] / "scripts" / "fetch_asset.py"
)
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


@pytest.fixture
def asset_server():
    data = b"published binary asset\x00\x01\x02" * 20
    state = {
        "ranges": [],
        "mode": "valid",
        "active": 0,
        "peak": 0,
        "request_times": [],
        "retry_after": "2",
    }
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            raw_range = self.headers.get("Range", "")
            start, end = (int(value) for value in raw_range.removeprefix("bytes=").split("-"))
            with lock:
                state["ranges"].append((start, end))
                state["request_times"].append((time.monotonic(), time.time()))
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
                occurrence = state["ranges"].count((start, end))
            try:
                time.sleep(0.005)
                if state["mode"] == "fail_later" and start >= 64:
                    self.send_error(503)
                    return
                if (
                    state["mode"].startswith("retry_after_")
                    or state["mode"] == "global_retry_after"
                    and start == 0
                ) and occurrence == 1:
                    self.send_response(503 if state["mode"].endswith("503") else 429)
                    self.send_header("Retry-After", state["retry_after"])
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if state["mode"] == "global_retry_after" and start == 64:
                    time.sleep(0.1)
                self.send_response(200 if state["mode"] == "ignore_range" else 206)
                offset = 1 if state["mode"] == "wrong_range" else 0
                total = len(data) + (1 if state["mode"] == "wrong_total" else 0)
                self.send_header("Content-Range", f"bytes {start + offset}-{end}/{total}")
                self.send_header("Content-Length", str(end - start + 1))
                self.end_headers()
                body = data[start : end + 1]
                if state["mode"] == "truncate_once" and occurrence == 1:
                    body = body[:-1]
                self.wfile.write(body)
            finally:
                with lock:
                    state["active"] -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/asset", data, state
    server.shutdown()
    server.server_close()
    thread.join()


def run_download(asset_server, target, **kwargs):
    url, data, _ = asset_server
    return fetch.download_asset(
        url,
        target,
        len(data),
        hashlib.sha256(data).hexdigest(),
        part_size=64,
        workers=3,
        timeout=2,
        **kwargs,
    )


def test_downloads_all_ranges_and_atomically_produces_verified_asset(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    assert run_download(asset_server, target) == target
    _, data, state = asset_server
    assert target.read_bytes() == data
    assert sorted(state["ranges"]) == [
        (0, 63),
        (64, 127),
        (128, 191),
        (192, 255),
        (256, 319),
        (320, 383),
        (384, 447),
        (448, 499),
    ]
    assert state["peak"] <= 3
    assert not list(tmp_path.glob("*.assembling*"))


@pytest.mark.parametrize("mode", ["ignore_range", "wrong_range", "wrong_total"])
def test_rejects_range_or_size_contract_violations(asset_server, tmp_path, mode):
    asset_server[2]["mode"] = mode
    target = tmp_path / "asset.bin"
    with pytest.raises(ValueError):
        run_download(asset_server, target, retries=0)
    assert not target.exists()


def test_retries_truncated_parts_instead_of_accepting_them(asset_server, tmp_path):
    asset_server[2]["mode"] = "truncate_once"
    target = tmp_path / "asset.bin"
    run_download(asset_server, target, retries=1)
    assert target.read_bytes() == asset_server[1]
    assert set(Counter(asset_server[2]["ranges"]).values()) == {2}


def test_resumes_only_verified_completed_parts_after_failure(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    state = asset_server[2]
    state["mode"] = "fail_later"
    with pytest.raises(HTTPError):
        run_download(asset_server, target, retries=0)
    assert not target.exists()
    state["mode"] = "valid"
    run_download(asset_server, target)
    assert target.read_bytes() == asset_server[1]
    assert state["ranges"].count((0, 63)) == 1


def test_global_hash_mismatch_never_publishes_a_final_file(asset_server, tmp_path):
    url, data, _ = asset_server
    target = tmp_path / "asset.bin"
    with pytest.raises(ValueError, match="SHA256"):
        fetch.download_asset(url, target, len(data), "0" * 64, part_size=64, workers=2)
    assert not target.exists()


def test_existing_valid_asset_is_verified_without_any_http_request(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    target.write_bytes(asset_server[1])
    run_download(asset_server, target)
    assert asset_server[2]["ranges"] == []


def test_existing_invalid_asset_is_preserved_without_explicit_replacement(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    target.write_bytes(b"existing file")
    with pytest.raises(FileExistsError):
        run_download(asset_server, target)
    assert target.read_bytes() == b"existing file"
    assert asset_server[2]["ranges"] == []


def test_explicit_replacement_is_atomic_after_verification(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    target.write_bytes(b"")
    run_download(asset_server, target, replace_invalid=True)
    assert target.read_bytes() == asset_server[1]


def test_explicit_prefix_reuse_saves_complete_ranges_but_still_checks_final_hash(
    asset_server, tmp_path
):
    target = tmp_path / "asset.bin"
    target.write_bytes(asset_server[1][:150])
    run_download(asset_server, target, replace_invalid=True, reuse_prefix=True)
    assert target.read_bytes() == asset_server[1]
    assert (0, 63) not in asset_server[2]["ranges"]
    assert (64, 127) not in asset_server[2]["ranges"]


def test_bad_prefix_is_preserved_on_failure_but_not_reused_again(asset_server, tmp_path):
    target = tmp_path / "asset.bin"
    target.write_bytes(b"wrong prefix" * 10)
    with pytest.raises(ValueError, match="SHA256"):
        run_download(asset_server, target, replace_invalid=True, reuse_prefix=True)
    assert target.read_bytes() == b"wrong prefix" * 10
    run_download(asset_server, target, replace_invalid=True, reuse_prefix=True)
    assert target.read_bytes() == asset_server[1]
    assert (0, 63) in asset_server[2]["ranges"]


@pytest.mark.parametrize("sha256", ["", "xyz", "a" * 63])
def test_requires_complete_sha256_before_network_activity(asset_server, tmp_path, sha256):
    with pytest.raises(ValueError):
        fetch.download_asset(asset_server[0], tmp_path / "asset", 480, sha256)
    assert asset_server[2]["ranges"] == []


def test_rejects_more_than_thirty_two_workers_before_network_activity(asset_server, tmp_path):
    with pytest.raises(ValueError):
        fetch.download_asset(asset_server[0], tmp_path / "asset", 480, "a" * 64, workers=33)
    assert asset_server[2]["ranges"] == []


def test_allows_thirty_two_workers_with_verified_streamed_parts(asset_server, tmp_path):
    url, data, state = asset_server
    target = tmp_path / "asset.bin"
    fetch.download_asset(
        url, target, len(data), hashlib.sha256(data).hexdigest(), part_size=64, workers=32
    )
    assert target.read_bytes() == data
    assert state["peak"] <= 32


@pytest.mark.parametrize("status", [429, 503])
def test_honors_retry_after_seconds_before_retrying_http_errors(asset_server, tmp_path, status):
    url, data, state = asset_server
    state["mode"] = f"retry_after_{status}"
    target = tmp_path / "asset.bin"
    fetch.download_asset(
        url,
        target,
        len(data),
        hashlib.sha256(data).hexdigest(),
        part_size=len(data),
        workers=1,
        retries=1,
    )
    assert target.read_bytes() == data
    assert len(state["request_times"]) == 2
    assert state["request_times"][1][0] - state["request_times"][0][0] >= 2


def test_honors_retry_after_http_date(asset_server, tmp_path):
    url, data, state = asset_server
    state["mode"] = "retry_after_429"
    state["retry_after"] = format_datetime(datetime.now(UTC) + timedelta(seconds=3), usegmt=True)
    target = tmp_path / "asset.bin"
    fetch.download_asset(
        url,
        target,
        len(data),
        hashlib.sha256(data).hexdigest(),
        part_size=len(data),
        workers=1,
        retries=1,
    )
    assert target.read_bytes() == data
    assert state["request_times"][1][1] >= parsedate_to_datetime(state["retry_after"]).timestamp()


def test_huge_retry_after_fails_without_an_early_retry(asset_server, tmp_path):
    url, data, state = asset_server
    state["mode"] = "retry_after_429"
    state["retry_after"] = "3600"
    target = tmp_path / "asset.bin"
    with pytest.raises(ValueError, match="Retry-After"):
        fetch.download_asset(
            url,
            target,
            len(data),
            hashlib.sha256(data).hexdigest(),
            part_size=len(data),
            workers=1,
            retries=1,
        )
    assert len(state["request_times"]) == 1
    assert not target.exists()


def test_rate_limit_pauses_new_ranges_across_workers(asset_server, tmp_path):
    url, data, state = asset_server
    state["mode"] = "global_retry_after"
    target = tmp_path / "asset.bin"
    fetch.download_asset(
        url,
        target,
        len(data),
        hashlib.sha256(data).hexdigest(),
        part_size=64,
        workers=2,
        retries=1,
    )
    assert target.read_bytes() == data
    first_time = state["request_times"][state["ranges"].index((0, 63))][0]
    later = [
        moment[0]
        for span, moment in zip(state["ranges"], state["request_times"], strict=True)
        if span[0] >= 128
    ]
    assert min(later) - first_time >= 2


def test_exhausted_rate_limit_stops_new_ranges_across_workers(asset_server, tmp_path):
    url, data, state = asset_server
    state["mode"] = "global_retry_after"
    target = tmp_path / "asset.bin"
    with pytest.raises(HTTPError):
        fetch.download_asset(
            url,
            target,
            len(data),
            hashlib.sha256(data).hexdigest(),
            part_size=64,
            workers=2,
            retries=0,
        )
    assert not target.exists()
    assert all(start < 128 for start, _ in state["ranges"])
    assert state["ranges"].count((0, 63)) == 1
