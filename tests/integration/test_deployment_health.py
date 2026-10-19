import importlib.util
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws_health = _load("ws_health", PROJECT_ROOT / "deployment/ws-collector/healthcheck.py")
hb_watchdog = _load("hb_watchdog", PROJECT_ROOT / "deployment/hummingbot/watchdog.py")


def test_ws_health_requires_nonempty_recent_l2(tmp_path):
    path = tmp_path / "hyperliquid_ws_BTC_l2Book_2026-10-19.jsonl"
    assert not ws_health.has_recent_snapshot(tmp_path, 30, now=100)
    path.write_text("{}\n")
    os.utime(path, (95, 95))
    assert ws_health.has_recent_snapshot(tmp_path, 30, now=100)
    assert not ws_health.has_recent_snapshot(tmp_path, 2, now=100)
    path.write_text("")
    assert not ws_health.has_recent_snapshot(tmp_path, 30, now=100)


def test_hummingbot_watchdog_dry_run_cannot_restart(tmp_path, monkeypatch, capsys):
    restarts = []

    def fake_run(args, **kwargs):
        if args[1] == "inspect":
            return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
        restarts.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(hb_watchdog.subprocess, "run", fake_run)
    monkeypatch.setenv("HB_CONTAINER", "my-hummingbot")
    monkeypatch.setenv("HB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HB_MARKETS", "BTC")
    monkeypatch.setenv("HB_DRY_RUN", "1")
    assert hb_watchdog.main() == 1
    assert not restarts
    assert "DRY RUN" in capsys.readouterr().out


def test_hummingbot_watchdog_cooldown(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args[1])
        if args[1] == "inspect":
            return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(hb_watchdog.subprocess, "run", fake_run)
    monkeypatch.setenv("HB_CONTAINER", "my-hummingbot")
    monkeypatch.setenv("HB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HB_MARKETS", "BTC")
    monkeypatch.setenv("HB_DRY_RUN", "0")
    monkeypatch.setenv("HB_RESTART_COOLDOWN_SECONDS", "600")
    monkeypatch.setenv("HB_STATE_DIR", str(tmp_path / "state"))
    assert hb_watchdog.main() == 0
    assert hb_watchdog.main() == 1
    assert calls.count("restart") == 1


def test_hummingbot_healthy_does_not_restart(tmp_path, monkeypatch):
    filename = tmp_path / "hyperliquid_perpetual_PONS-USD_order_book_snapshots_1.txt"
    filename.write_text("{}\n")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args[1])
        return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")

    monkeypatch.setattr(hb_watchdog.subprocess, "run", fake_run)
    monkeypatch.setenv("HB_CONTAINER", "hummingbot")
    monkeypatch.setenv("HB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HB_MARKETS", "PONS")
    monkeypatch.setenv("HB_DRY_RUN", "0")
    assert hb_watchdog.main() == 0
    assert calls == ["inspect"]


def test_watchdog_invalid_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("HB_MARKETS", "")
    assert hb_watchdog.main() == 2
