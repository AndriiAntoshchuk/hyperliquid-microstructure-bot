import asyncio
import json

from hlbot.data.hyperliquid_ws_collector import load_universe_coins, sync_subscriptions


class WebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))

def test_load_universe_coins(tmp_path):
    path = tmp_path / "collection.json"
    path.write_text(json.dumps({
        "coins": ["ARB", "PONS", "ARB"]
    }))

    assert load_universe_coins(
        path,
        ("PONS", "LIT")
    ) == ("ARB", "PONS")

def test_missing_universe_uses_fallback(tmp_path):
    assert load_universe_coins(
        tmp_path / "missing.json",
        ("PONS", "LIT")
    ) == ("PONS", "LIT")

def test_empty_universe_uses_fallback(tmp_path):
    path = tmp_path / "collection.json"
    path.write_text(json.dumps({"coins": []}))

    assert load_universe_coins(
        path,
        ("PONS", "LIT")
    ) == ("PONS", "LIT")

def test_subscribe_new_coin():
    websocket = WebSocket()
    active = {"PONS"}

    asyncio.run(sync_subscriptions(
        websocket,
        active,
        ("PONS", "ARB")
    ))

    assert active == {"PONS", "ARB"}
    assert len(websocket.messages) == 3
    assert all(
        message["method"] == "subscribe"
        for message in websocket.messages
    )

def test_unsubscribe_removed_coin():
    websocket = WebSocket()
    active = {"PONS", "ARB"}

    asyncio.run(sync_subscriptions(
        websocket,
        active,
        ("ARB",)
    ))

    assert active == {"ARB"}
    assert len(websocket.messages) == 3
    assert all(
        message["method"] == "unsubscribe"
        for message in websocket.messages
    )

def test_add_and_remove_coin():
    websocket = WebSocket()
    active = {"PONS", "LIT"}

    asyncio.run(sync_subscriptions(
        websocket,
        active,
        ("LIT", "ARB")
    ))

    assert active == {"LIT", "ARB"}
    assert len(websocket.messages) == 6

    methods = [
        message["method"]
        for message in websocket.messages
    ]

    assert methods.count("unsubscribe") == 3
    assert methods.count("subscribe") == 3

def test_no_change_sends_nothing():
    websocket = WebSocket()
    active = {"PONS", "LIT"}

    asyncio.run(sync_subscriptions(
        websocket,
        active,
        ("PONS", "LIT")
    ))

    assert active == {"PONS", "LIT"}
    assert websocket.messages == []