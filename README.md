# Hummingbot Integration

Hummingbot-specific integration used by the **Hyperliquid Microstructure Bot** project.

The main research and strategy code lives under:

```text
src/hlbot/
```

---

## Market Data Collector

`download_order_book_and_trades.py` collects:

- Hyperliquid public trades
- L2 order-book snapshots
- Exchange timestamps
- Local receive timestamps
- Order-book update IDs
- Collector version metadata

### Default Market

```text
PONS-USD
```

Stale order-book snapshots are filtered using:

```python
order_book.snapshot_uid
```

---

## Hyperliquid Trade ID Fix

Hummingbot originally used the Hyperliquid transaction hash as the public trade ID.

A single transaction can contain multiple fills, so the transaction hash is not necessarily unique for every fill.

The collector instead uses:

```text
time:coin:tid
```

Patch:

```text
patches/hyperliquid_trade_id.patch
```

---

## HIP-3 Workaround

During development, Hyperliquid testnet HIP-3 market loading caused repeated HTTP `429` rate-limit errors.

The current workaround disables HIP-3 market loading.

Patch:

```text
patches/hyperliquid_disable_hip3.patch
```

> This workaround should be reviewed when upgrading Hummingbot.

---

## Usage

### Check Patches

Verify that the patches are compatible with the local Hummingbot source:

```bash
./hummingbot_ext/check_patches.sh
```

### Apply Patches

```bash
./hummingbot_ext/apply_patches.sh
```

### Install Collector

```bash
./hummingbot_ext/install_collector.sh
```

By default, the scripts expect Hummingbot at:

```text
~/Documents/Hummingbot
```

A different Hummingbot path can be supplied as the first argument.

---

## Project Separation

```text
src/hlbot/
└── Quantitative research, models, validation, backtesting and strategy

hummingbot_ext/
└── Hummingbot integration, collector and connector patches
```

---

## Attribution

Hummingbot is an open-source project maintained by the Hummingbot Foundation.

Files in this directory integrate with or modify Hummingbot components. The quantitative research and strategy components of this repository are developed separately under `src/hlbot/`.

See the upstream Hummingbot repository and license for applicable licensing terms.