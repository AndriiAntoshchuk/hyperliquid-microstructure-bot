import json
import os
import subprocess
import sys
from pathlib import Path

from hlbot.backtest.demo_workflow import run_backtest

ROOT = Path(__file__).resolve().parents[2]


def test_reproducible_demo_and_accounting(tmp_path):
    report = run_backtest(ROOT / "configs/demo_backtest.json", ROOT / "data/sample", tmp_path / "report.json")
    saved = json.loads((tmp_path / "report.json").read_text())
    assert report == saved
    assert report["input"] == {"snapshots": 120, "trades": 120}
    assert report["replay"]["states_evaluated"] > 0
    assert report["replay"]["has_open_position"] is False
    assert report["performance"]["closed_trades"] >= 1
    assert report["performance"]["fills"] >= 2
    assert report["performance"]["fees"] > 0
    assert len(report["trades"]) == report["performance"]["closed_trades"]
    assert abs(report["performance"]["net_pnl"] - (
        report["performance"]["gross_pnl"] - report["performance"]["fees"]
    )) < 1e-8


def test_public_module_cli(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    report_path = tmp_path / "backtest.json"
    result = subprocess.run(
        [sys.executable, "-m", "hlbot", "backtest", "--config", "configs/demo_backtest.json",
         "--data", "data/sample", "--output", str(report_path)],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    assert "states_evaluated" in result.stdout
    assert json.loads(report_path.read_text())["performance"]["fills"] >= 2


def test_reject_missing_data(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="no DEMO l2Book snapshots"):
        run_backtest(ROOT / "configs/demo_backtest.json", tmp_path, tmp_path / "result.json")
