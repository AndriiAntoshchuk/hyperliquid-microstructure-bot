Hummingbot Integration

This directory contains the Hummingbot-specific integration used by the Hyperliquid Microstructure Bot project.

The main research and strategy code lives separately under:

src/hlbot/

This directory only contains code and patches required to connect the project to Hummingbot.

Collector

download_order_book_and_trades.py collects:

Hyperliquid public trades
L2 order-book snapshots
Exchange timestamps
Local receive timestamps
Order-book update IDs
Collector version metadata

Current default market:

PONS-USD

The collector also avoids repeatedly writing stale order books by tracking:

order_book.snapshot_uid
Hyperliquid Trade ID Patch

Hummingbot originally used the Hyperliquid transaction hash as the public trade ID.

A single Hyperliquid transaction can contain multiple fills, so the transaction hash is not guaranteed to uniquely identify each fill.

The patch changes the trade ID to:

time:coin:tid

Patch file:

patches/hyperliquid_trade_id.patch
HIP-3 Workaround

During development, Hyperliquid testnet HIP-3 market loading caused repeated HTTP 429 rate-limit errors.

The temporary workaround disables HIP-3 market loading.

Patch file:

patches/hyperliquid_disable_hip3.patch

This workaround should be reviewed when upgrading Hummingbot.

Check Patches

From the project root:

./hummingbot_ext/check_patches.sh

This verifies that the patches are compatible with the local Hummingbot source.

Apply Patches
./hummingbot_ext/apply_patches.sh

By default, the scripts expect Hummingbot at:

~/Documents/Hummingbot

A different Hummingbot path can be supplied as the first argument.

Install Collector
./hummingbot_ext/install_collector.sh

This copies the version-controlled collector into:

Hummingbot/scripts/download_order_book_and_trades.py
Attribution

Hummingbot is an open-source project maintained by the Hummingbot Foundation.

Files and patches in this directory integrate with or modify Hummingbot code.

The rest of this repository is developed separately as part of the Hyperliquid Microstructure Bot research project.

See the upstream Hummingbot repository and license for the applicable licensing terms.