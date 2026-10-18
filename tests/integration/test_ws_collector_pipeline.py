import json
from pathlib import Path

import pytest

from hlbot.data import hyperliquid_ws_collector as collector


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration from None


@pytest.mark.asyncio
async def test_collector_persists_all_accepted_messages_on_disconnect(tmp_path, monkeypatch):
    messages = []
    for index in range(9):
        messages.append(json.dumps({
            "channel": "l2Book",
            "data": {"coin": "DEMO", "time": 1_780_000_000_000 + index * 1000,
                     "levels": [[{"px": "99", "sz": "1"}], [{"px": "101", "sz": "1"}]]},
        }))
    socket = FakeWebSocket(messages)
    monkeypatch.setattr(collector.websockets, "connect", lambda *args, **kwargs: socket)
    await collector.collect_connection("DEMO", tmp_path, queue_size=2, batch_size=5, flush_interval=60)

    files = list(Path(tmp_path).glob("*_l2Book_*.jsonl"))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert len(rows) == 9
    assert [r["message_index"] for r in rows] == list(range(1, 10))
    assert [r["data"]["time"] for r in rows] == [1_780_000_000_000 + i * 1000 for i in range(9)]
    assert len(socket.sent) == 3  # book, bbo, trades subscriptions
