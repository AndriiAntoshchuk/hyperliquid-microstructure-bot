#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUMMINGBOT_DIR="${1:-$HOME/Documents/Hummingbot}"

echo "Applying Hyperliquid trade ID patch"
git -C "$HUMMINGBOT_DIR" apply \
  "$SCRIPT_DIR/patches/hyperliquid_trade_id.patch"

echo "Applying HIP-3 workaround"
git -C "$HUMMINGBOT_DIR" apply \
  "$SCRIPT_DIR/patches/hyperliquid_disable_hip3.patch"

echo "Done."