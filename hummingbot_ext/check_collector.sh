#!/bin/bash

set -u

DATA_DIR="${DATA_DIR:-/home/hlbot/hummingbot/data}"
MAX_AGE="${MAX_AGE:-120}"
MARKETS=("PONS" "CASHCAT" "PURR" "LIT")
FAILED=0

if [ "$(docker inspect -f '{{.State.Running}}' hummingbot 2>/dev/null)" = "true" ]; then
    echo "Container: OK"
else
    echo "Container: FAILED"
    FAILED=1
fi

echo

for market in "${MARKETS[@]}"; do
    latest=$(ls -1t "$DATA_DIR"/hyperliquid_perpetual_"$market"-USD_order_book_snapshots_*.txt 2>/dev/null | head -1)

    if [ -z "$latest" ]; then
        echo "$market: FAILED - no order book file"
        FAILED=1
        continue
    fi

    now=$(date +%s)
    modified=$(stat -c %Y "$latest")
    age=$((now - modified))
    size=$(stat -c %s "$latest")

    echo "$market:"
    echo "  File: $(basename "$latest")"
    echo "  Age: ${age}s"
    echo "  Size: ${size} bytes"

    if [ "$age" -le "$MAX_AGE" ] && [ "$size" -gt 0 ]; then
        echo "  Order book: OK"
    else
        echo "  Order book: FAILED"
        FAILED=1
    fi
done

echo
df -h /

exit "$FAILED"
