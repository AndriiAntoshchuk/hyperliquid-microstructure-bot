#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUMMINGBOT_DIR="${1:-$HOME/Documents/Hummingbot}"

cp \
  "$SCRIPT_DIR/download_order_book_and_trades.py" \
  "$HUMMINGBOT_DIR/scripts/download_order_book_and_trades.py"

echo "Collector installed."