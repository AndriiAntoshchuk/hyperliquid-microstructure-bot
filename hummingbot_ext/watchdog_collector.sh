#!/bin/bash

set -u

PATH="/usr/local/bin:/usr/bin:/bin"
DATA_DIR="/home/hlbot/hummingbot/data"
MAX_AGE=120
MARKETS=("PONS" "CASHCAT" "PURR" "LIT")
FAILED=0

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Checking collector"

if [ "$(docker inspect -f '{{.State.Running}}' hummingbot 2>/dev/null)" != "true" ]; then
    echo "Container is not running"
    FAILED=1
fi

for market in "${MARKETS[@]}"; do
    latest=$(ls -1t "$DATA_DIR"/hyperliquid_perpetual_"$market"-USD_order_book_snapshots_*.txt 2>/dev/null | head -1)

    if [ -z "$latest" ]; then
        echo "$market: no order-book file"
        FAILED=1
        continue
    fi

    now=$(date +%s)
    modified=$(stat -c %Y "$latest")
    age=$((now - modified))
    size=$(stat -c %s "$latest")

    if [ "$age" -gt "$MAX_AGE" ] || [ "$size" -eq 0 ]; then
        echo "$market: STALE age=${age}s size=${size}"
        FAILED=1
    else
        echo "$market: OK age=${age}s"
    fi
done

if [ "$FAILED" -eq 0 ]; then
    echo "Collector healthy"
    exit 0
fi

echo "Collector unhealthy - restarting Hummingbot"
docker restart hummingbot

sleep 30

echo "Post-restart check:"
/home/hlbot/hummingbot/check_collector.sh
