#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUMMINGBOT_DIR="${1:-$HOME/Documents/Hummingbot}"

echo "Checking trade ID patch..."
git -C "$HUMMINGBOT_DIR" apply --check \
  "$SCRIPT_DIR/patches/hyperliquid_trade_id.patch"

echo "Trade ID patch: ready"

echo "Checking HIP-3 patch..."
git -C "$HUMMINGBOT_DIR" apply --check \
  "$SCRIPT_DIR/patches/hyperliquid_disable_hip3.patch"

echo "HIP-3 patch: ready"