# Hyperliquid Microstructure Bot

[![CI](https://github.com/AndriiAntoshchuk/hyperliquid-microstructure-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/AndriiAntoshchuk/hyperliquid-microstructure-bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)

**An event-driven Python framework for collecting Hyperliquid perpetual-futures market data, studying market microstructure, and testing execution-aware trading strategies.**

The project brings together high-frequency order-book and trade data, feature engineering, configurable position-management rules, historical replay, risk controls, and a Hummingbot execution integration. It is primarily a **quantitative research and systems-engineering project**, not a turnkey profitable trading bot.

## Highlights

- **Market-data ingestion:** asynchronous Hyperliquid WebSocket collector for `l2Book`, best bid/offer (`bbo`), and public trades; optional Hummingbot-based L2/trade collector.
- **Microstructure features:** spread, microprice, order-book imbalance, trade flow, short-horizon returns and volatility, depth, liquidity, and execution-cost estimates.
- **Market selection:** collect universe metadata, rank markets, form a stable collection universe, validate L2 coverage, and screen potential trading markets by execution capacity and expected movement relative to costs.
- **Strategy primitives:** pluggable signal interface, entry filters, long/short positions, scale-ins, liquidity-aware sizing, stop-loss/take-profit rules, and maximum holding periods.
- **Event-driven backtesting:** chronological order-book/trade replay with taker depth consumption, maker-order simulation, partial fills, configurable fees and latency, position accounting, and P&L reporting.
- **Risk and execution components:** order/position limits, stale-data checks, kill switch, drawdown/loss limits, order lifecycle tracking, account reconciliation, and Hummingbot perpetual adapter.
- **Research tooling:** wallet-fill analysis, trading-episode reconstruction, event studies, and momentum-versus-mean-reversion classification.
- **Reproducible offline demo:** tracked synthetic market-data fixture, deterministic mean-reversion example, command-line replay, and JSON report.
- **Buffered persistence:** bounded asynchronous queue, batched JSONL writes, backpressure, shutdown draining and writer metrics.
- **Automated testing:** unit and integration tests with GitHub Actions CI.

> **Project status:** Research infrastructure and testable execution components are implemented. The illustrative signal is **not calibrated or suitable for live use**, and the repository does **not** provide a complete production live-trading runner. The default `NoSignalModel` used in smoke tests deliberately creates no entry signals.

## Architecture

```text
Hyperliquid WebSocket / Hummingbot / Hyperliquid Info API
                          |
                Collectors and loaders
                          |
          Normalized order books and trades
                          |
        Market-state and microstructure features
                          |
         Signal model --> Strategy engine
                          |          |
                   Position rules  |  Order intent
                                   |
                    +--------------+--------------+
                    |                             |
            Historical replay           Risk-checked execution
            + fill simulation           + order tracking
            + position accounting       + Hummingbot adapter
                    |                             |
           Performance analysis         Reconciliation / events
```

The historical replay and live-execution integration are **separate components**; the diagram is a conceptual view, not a claim that the repository provides an end-to-end live trading daemon.

## Repository structure

```text
src/hlbot/
├── backtest/         # Historical replay, maker/taker simulation, fees, latency, P&L
├── data/             # WebSocket/universe collection, loaders, validation, coverage
├── execution/        # Client interfaces, Hummingbot adapter, order state, reconciliation
├── features/         # Microstructure, liquidity, movement, execution-quality features
├── models/           # Domain models for books, trades, wallets, and episodes
├── research/         # Event studies and momentum/mean-reversion analysis
├── risk/             # Risk limits, checks, and execution context
├── selection/        # Market ranking, stable universe, and trading eligibility
├── strategy/         # Signals, strategy decisions, sizing, entries, scale-ins, exits
└── wallet_analysis/  # Wallet episode, sizing, and P&L studies

scripts/               # Data collection, selection, replay, benchmarking, research CLIs
configs/               # Deterministic illustrative backtest configuration
data/sample/           # Tracked synthetic WebSocket fixture (no real trades)
tests/integration/     # Offline end-to-end and buffered-writer tests
hummingbot_ext/        # Optional Hummingbot collector, connector patches, health scripts
tests/unit/            # Unit test suite
.github/workflows/     # CI configuration
pyproject.toml         # Python package configuration
```

## Requirements and installation

- **Python 3.11+** (CI tests Python 3.11 and 3.13).
- Internet connection to collect new data from Hyperliquid.
- A small **synthetic** L2/trade dataset is included for the offline demo. Real-data research requires your own recording.
- Hummingbot is **optional** and only required for its dedicated collector and connector integrations.

```bash
git clone https://github.com/AndriiAntoshchuk/hyperliquid-microstructure-bot.git
cd hyperliquid-microstructure-bot

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

The core package declares `requests`, `websockets`, and `matplotlib` as dependencies. The `dev` extra installs pytest, pytest-asyncio, coverage, Ruff and mypy:

```bash
python -m pip install -e ".[dev]"
```

Run commands below from the **repository root**, with the virtual environment activated.

## Quick start: complete offline demo (no API keys required)

From the repository root after installing the package:

```bash
python -m hlbot backtest \
  --config configs/demo_backtest.json \
  --data data/sample \
  --output reports/demo_backtest.json
```

This reads **120 synthetic book snapshots and 120 synthetic trade messages** through the production WebSocket loader, computes time-aligned market state, evaluates a simple **five-second return mean-reversion signal**, runs the `StrategyEngine` and `ReplayBacktester`, and writes an auditable JSON report including simulated fills and completed trades. Sample outcomes are deliberately **not** investment returns or evidence of alpha.

To regenerate the deterministic fixture:

```bash
python scripts/generate_demo_data.py --output data/sample
```

The signal is illustrative, not trained, tested out-of-sample, or live-trading safe. The replay supports more sophisticated execution models, but this demo uses the taker-only/default-latency configuration and a simple holding-period exit. Real market recordings can replace the synthetic fixture by passing a different `--data` directory and selecting a matching `coin` in a copied config.

## Quick start: collect market data

The standalone collector subscribes to Hyperliquid's **mainnet public WebSocket** and saves local JSONL records. No trading credentials are needed for public data collection.

Collect a single market for 60 seconds:

```bash
python scripts/collect_hyperliquid_ws.py --coin PONS --duration 60
```

Collect multiple markets until interrupted:

```bash
python scripts/collect_hyperliquid_ws.py --coins PONS PURR LIT
```

The default collector uses the fast `l2Book` subscription. To request deep L2 data instead:

```bash
python scripts/collect_hyperliquid_ws.py --coin PONS --deep-l2 --duration 300
```

The default output directory is `data/raw/hyperliquid_ws_fast/`, including when `--deep-l2` is selected; set `--data-dir` to keep the datasets separate.

Example output filenames:

```text
data/raw/hyperliquid_ws_fast/
├── hyperliquid_ws_PONS_l2Book_YYYY-MM-DD.jsonl
├── hyperliquid_ws_PONS_bbo_YYYY-MM-DD.jsonl
└── hyperliquid_ws_PONS_trades_YYYY-MM-DD.jsonl
```

Each line contains a JSON record with source/channel metadata, coin, receive timestamp, connection ID, message index, and the original channel payload. The WebSocket collector writes through a **bounded** `asyncio.Queue` and a background batched writer. On saturation, the producer waits rather than silently discarding accepted messages; this backpressure may eventually cause upstream disconnects when ingestion cannot keep up. The writer drains on normal disconnect/cancellation, but an abrupt process crash can lose buffered events (no `fsync` guarantee). Set `--queue-size`, `--batch-size`, and `--flush-interval` to tune the trade-off. Status prints queue size, high-water mark, writer throughput and cumulative producer wait time. The loader converts book/trade events into normalized model objects for replay. Reconnects use exponential backoff; the collector supports dynamically changing subscriptions from a saved universe file.

### Buffered persistence benchmark

Compare the old per-event write approach against the new asynchronous batched writer on **identical synthetic records**, and verify byte-for-byte output equivalence:

```bash
python scripts/benchmark_writer.py --records 3000 --output reports/writer_benchmark.json
```

Reported throughput, elapsed time, queue high-water mark, cumulative enqueue wait time, and batch statistics are environment-specific. Measure on your deployment hardware before choosing queue and batch sizes; this benchmark does not test packet loss on a real exchange feed.

## Replay and benchmarking

The package implements an event-driven `ReplayBacktester` (`src/hlbot/backtest/replay.py`) with strategy state evaluation, book-based taker fills, optional maker-order queue/lifecycle modeling, configurable fees/latency, equity curves, and trade-level performance summaries.

**Controlled replay test on standalone WebSocket data** (requires a sufficiently long, continuous recording):

```bash
python scripts/run_real_l2_replay_check.py PONS \
  --source fast \
  --data-dir data/raw/hyperliquid_ws_fast \
  --notional 100 \
  --holding-seconds 30 \
  --fee-bps 5
```

This command uses a **synthetic single-entry signal** to exercise the replay and execution accounting. It does not measure predictive signal quality or real trading performance. The default `--fee-bps` is zero unless overridden.

**Replay smoke test on Hummingbot-collected data:**

```bash
python scripts/run_replay_smoke_test.py PONS \
  --data-dir data/raw/hummingbot_vps
```

**Replay throughput benchmark:**

```bash
python scripts/benchmark_replay.py PONS \
  --data-dir data/raw/hummingbot_vps \
  --runs 10
```

Both Hummingbot-data commands use `NoSignalModel` by design. They exercise data loading and replay infrastructure, **not** the profitability of a strategy. `benchmark_replay.py` reports event counts, median runtime, events/second, p95/p99 run times, memory usage, and environment metadata. Results depend on hardware and the local dataset; no independently reproduced benchmark result is claimed here.

### Strategy and execution behavior

`StrategyEngine` consumes a `SignalModel` and `StrategySpec` to decide whether to **hold, enter, scale in, or exit**. Configurable rules include maximum spread, maximum position notional, maximum scale-ins, stop loss, take profit, maximum holding time, and a cap based on visible book liquidity.

`RiskEngine` and `RiskCheckedExecutor` provide independent pre-submission controls such as order and position limits, stale market data, connectivity/reconciliation checks, drawdown and daily-loss limits, latency, open-order count, and a kill switch. Hummingbot adapter classes provide execution interfaces, but deployment and orchestration require additional integration and validation.

## Market discovery and liquidity screening

An optional pipeline ranks markets and builds a dynamically maintained collection/trading universe.

**1. Collect universe snapshots** (run over time; a single snapshot is not enough for stable selection):

```bash
python scripts/collect_universe.py --interval 60
```

**2. Build the stable selection and collection universe** after enough observations have accumulated:

```bash
python scripts/build_stable_market_universe.py
```

**3. Collect the selected markets dynamically:**

```bash
python scripts/collect_hyperliquid_ws.py --dynamic \
  --universe-file data/derived/market_selection/collection_universe.json
```

**4. Check L2 coverage, then estimate execution capacity and trading eligibility:**

```bash
python scripts/check_l2_readiness.py
python scripts/build_execution_profile.py
python scripts/build_trading_universe.py
```

These commands exchange timestamped artifacts under `data/derived/market_selection/`. `build_execution_profile.py` validates that L2 readiness belongs to the same selection epoch; `build_trading_universe.py` checks profile freshness and tests execution cost against measured market movement. Some stages need roughly an hour or more of recent observations, depending on their configuration.

A separate rolling market scanner is available:

```bash
python scripts/run_market_scanner.py --once
```

## Hummingbot integration (optional)

`hummingbot_ext/` contains an alternative Hummingbot Strategy V2 collector and two Hyperliquid connector patches:

- **Trade ID patch:** builds a per-fill identifier instead of relying on a transaction hash that may cover multiple fills.
- **HIP-3 workaround:** disables HIP-3 market loading to avoid rate-limit issues encountered in the development/testnet setup. Review this workaround against the Hummingbot version you use.

The helper scripts default to a Hummingbot checkout at `~/Documents/Hummingbot`; provide another path as the first argument if needed:

```bash
./hummingbot_ext/check_patches.sh /path/to/Hummingbot
./hummingbot_ext/apply_patches.sh /path/to/Hummingbot
./hummingbot_ext/install_collector.sh /path/to/Hummingbot
```

Use `hummingbot_ext/conf_multi_data.example.yml` as a reference for running the installed collector in Hummingbot. The patch applicability and Hummingbot version have **not** been verified by this repository's Python unit tests. Back up or commit changes in your Hummingbot checkout before applying patches.

The collector writes one JSON record per line despite the `.txt` extension, with filenames such as:

```text
hyperliquid_perpetual_PONS-USD_order_book_snapshots_YYYY-MM-DD.txt
hyperliquid_perpetual_PONS-USD_trades_YYYY-MM-DD.txt
```

`hummingbot_ext/check_collector.sh` and `watchdog_collector.sh` are deployment-specific health scripts. They currently assume a Linux/Docker setup (including a `hummingbot` container and fixed paths/markets); they are **not** portable, generic monitoring tools out of the box.

## Wallet and event-study research

The repository also includes research commands for historical Hyperliquid wallet fills and entry-timing analysis:

```bash
# Download fills for an address and UTC start date
python scripts/download_wallet.py 0xYOUR_WALLET_ADDRESS --start 2026-01-01

# Analyze saved fills and reconstructed trading episodes
python scripts/analyze_wallet.py 0xYOUR_WALLET_ADDRESS

# Run the event-study CLI with its available options
python scripts/run_event_study.py --help
```

Wallet download and event-study results depend on upstream data availability and your local historical recordings. Wallet profitability or classification results are **not** evidence that the repository's own strategy is profitable.

## Tests and quality checks

```bash
# Unit and integration tests
python -m pytest -q

# Branch-aware coverage (requires pytest-cov)
python -m pytest -q --cov=hlbot --cov-branch --cov-report=term-missing

# CI lint configuration (requires ruff)
ruff check . --select F
```

GitHub Actions (`.github/workflows/ci.yml`) tests Python 3.11 and 3.13, runs the existing Ruff `F` checks plus stricter `E4,E7,E9,F,B` rules on the new modules, performs scoped mypy checks, compiles Python modules, and runs unit/integration tests with an 80% branch-aware coverage minimum. It also executes the offline sample replay and verifies benchmark output equivalence. Normal CI requires no exchange connection.

## Important limitations

- **No packaged production strategy:** the pluggable signal/strategy infrastructure is available, but a calibrated signal model and complete deployed live-trading service are not shipped.
- **Backtest != live execution:** maker queue position, slippage, feed gaps, fees, latency, and fill likelihood must be calibrated for the actual venue, market, and account.
- **Market data is local:** real raw datasets and generated reports are ignored by Git; only the small synthetic demo fixture is tracked. Examples requiring real historical data still need your own collection.
- **Hummingbot compatibility is version-specific:** collector patches and adapter behavior require manual integration checks.
- **Trading risk remains:** leverage, liquidity discontinuities, operational outages, and liquidation can cause losses. Nothing here guarantees returns.

## Attribution and licensing

This repository contains project-specific integration with [Hummingbot](https://github.com/hummingbot/hummingbot), a separate open-source project. Refer to upstream licensing terms for Hummingbot-derived components.

**No root `LICENSE` file is included in the inspected repository snapshot.** If you intend to allow reuse or contributions, add an explicit license covering the code you own and ensure compatibility with applicable upstream licenses.
