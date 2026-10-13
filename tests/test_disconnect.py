"""Real socket regressions: a browser abort must stop ongoing upstream work."""

import asyncio
import json
import socket

import pytest
import uvicorn

from paper_rewrite.app import create_app


@pytest.mark.parametrize("endpoint", ["rewrite", "detect"])
async def test_socket_disconnect_cancels_upstream(endpoint):
    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()
    after_cancel_stage = []

    class WaitingModel:
        name = "cancellation-fixture"

        async def complete(self, text, seed=0):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            after_cancel_stage.append("model_finished")
            return "本实验重复5次。"

    class WaitingDetector:
        async def compare(self, source, candidate, consent):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            after_cancel_stage.append("second_upload")
            return {"status": "fixture_only"}

    app = create_app(model=WaitingModel(), detector=WaitingDetector())
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="critical"))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    writer = None
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(0.01)
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        payload = (
            {"text": "实验重复5次。", "candidates": 1}
            if endpoint == "rewrite"
            else {"source": "original", "candidate": "rewrite", "consent": True}
        )
        body = json.dumps(payload).encode()
        header = (
            f"POST /api/{endpoint} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode()
        writer.write(header + body)
        await writer.drain()
        await asyncio.wait_for(started.wait(), 3)
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(cancelled.wait(), 2)
        release.set()
        assert not after_cancel_stage
    finally:
        release.set()
        if writer:
            writer.close()
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        sock.close()
