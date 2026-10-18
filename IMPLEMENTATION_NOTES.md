# Engineering improvements implemented (October 2026)

This repository snapshot is based on the ZIP archive provided in the conversation, not a live GitHub clone.

## 1. Reproducible offline workflow

- CLI: `python -m hlbot backtest --config configs/demo_backtest.json --data data/sample --output reports/demo_backtest.json`
- Pipeline: WebSocket JSONL -> domain models -> market-state features -> illustrative past-return signal -> strategy engine -> replay execution/accounting -> JSON report.
- `data/sample/` contains deterministic **synthetic** 120-book/120-trade messages. Generate with `python scripts/generate_demo_data.py`.
- The example intentionally illustrates mechanics, not a calibrated, live-safe or proven-profitable trading strategy.

## 2. Bounded asynchronous persistence

- `src/hlbot/data/buffered_writer.py`: bounded `asyncio.Queue`, background batched file writes using `asyncio.to_thread`, date/channel/coin rotation, flush-on-close, queue backpressure, writer error propagation, throughput/wait/bytes metrics.
- `src/hlbot/data/hyperliquid_ws_collector.py`: now uses buffered writer, preserves synchronous `write_record` for reference and compatibility; CLI flags include `--queue-size`, `--batch-size`, `--flush-interval`.
- `scripts/benchmark_writer.py`: contrasts original per-record synchronous writes with the buffered writer, verifies exact output equivalence, emits machine-readable metrics.
- Limitations: in-memory buffers are not crash-durable; no `fsync`, at-least-once replay, or exchange delivery guarantee. Slow disk can propagate pressure upstream and lead to feed disconnects.

## 3. Testing/CI/quality

- End-to-end offline CLI/backtesting integration tests.
- Writer tests for file rotation, batch boundaries, queue saturation, disk failures and draining.
- Collector/WebSocket fake-connection integration test.
- Position-context tests for long/short, moving entry cost basis, MFE/MAE, lookbacks, gaps, chronological ordering and state resets.
- Removed a duplicate `evaluate_exit()` call from `strategy/engine.py`.
- CI matrix 3.11/3.13; extended lint on new code; gradually scoped mypy; compile check; 80% minimum branch-aware coverage; offline CLI/benchmark smoke tests.

## Local verification

- Python 3.13.5, Linux.
- `pytest -q --cov=hlbot --cov-branch --cov-fail-under=80`: **508 passed**, **86.03% total branch-aware coverage**.
- `python -m compileall -q src scripts tests`: passed.
- `pip install -e . --no-deps --no-build-isolation`: passed (already installed dependencies were used).
- Offline CLI sample: 120 snapshots, 120 trades, 90 evaluated states, 2 simulated fills, 1 completed simulated trade.
- Buffered writer benchmark with 2,000 records: about 59.8k records/second versus 42.1k for per-record baseline (1.42x), output exactly equal. Performance is machine/workload-dependent.
- Ruff and mypy **could not be installed/run locally** because external package access was unavailable. CI configuration is provided but must be run on GitHub to confirm those gates.
- No live Hyperliquid connection, real-trading integration or profitability validation was performed.
