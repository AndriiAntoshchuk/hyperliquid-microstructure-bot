# Deployment examples

This directory contains **sanitized, reproducible examples**, not an export of the author's actual VPS. They document two distinct collection paths. The Python WebSocket collector is runnable with Docker Compose. The Hummingbot path describes how to attach health checks and automated recovery to an **existing** Hummingbot installation/container; it does not bundle or configure the third-party Hummingbot runtime itself.

No exchange credentials are required for the public-data WebSocket collector. Never commit private keys, wallet seeds, API tokens, real `.env` files, private VPS addresses or production data.

## A. Containerized Python WebSocket collector (runnable)

Requirements: Docker Engine with the Compose plugin (Linux VPS or local Docker Desktop), access to Hyperliquid WebSocket APIs, and adequate disk space.

From the repository root:

```sh
cp deployment/ws-collector/.env.example deployment/ws-collector/.env
# Edit COINS and other settings as appropriate.
docker compose --env-file deployment/ws-collector/.env -f deployment/ws-collector/compose.yaml up -d --build
docker compose -f deployment/ws-collector/compose.yaml ps
docker compose -f deployment/ws-collector/compose.yaml logs -f --tail=100
```

The container runs `scripts/collect_hyperliquid_ws.py` with the package installed in Python 3.13. The environment variable `COINS` is space-separated (e.g. `BTC ETH`). Data is written in JSONL format to the persistent Docker named volume `collector_data`, mounted at `/data`. The container uses a non-root user, capped Docker logs, a 45-second shutdown grace period, a restart policy and a freshness-based health check. No application or exchange ports are exposed.

For a manual check of output files:

```sh
docker compose -f deployment/ws-collector/compose.yaml exec collector ls -lh /data/raw
```

Stop the collector with:

```sh
docker compose -f deployment/ws-collector/compose.yaml down
```

This **keeps** the named volume. Do not use `down --volumes` unless you intend to delete the recorded dataset. For backups, use Docker volume backups or copy the data from a running container.

**Health-check semantics:** `healthcheck.py` reports healthy when at least one `l2Book` JSONL file is nonempty and recently modified. A health check does not prove that every market is receiving valid events, and Docker's `restart: unless-stopped` restarts **exited processes**, not merely unhealthy containers. The collector's own reconnect loop handles transient WebSocket errors. The initial startup grace and staleness threshold must be tuned to real market activity.

## B. Existing Hummingbot collector on Ubuntu (template)

This repository contains the Hummingbot strategy script, connector patches, and legacy checks in `hummingbot_ext/`. The live VPS's Docker image/version, Hummingbot runtime configuration, volume mounts, service user, API credentials and server-specific paths are **not available in this repository**; therefore this section deliberately does **not** claim one-command reconstruction of that VPS.

1. Install/configure your own compatible Hummingbot Docker deployment, mounting its data directory to the host. Make sure your collector output uses names like `hyperliquid_perpetual_PONS-USD_order_book_snapshots_*.txt`. See `hummingbot_ext/` for collector code and patches; ensure connector patch compatibility with the installed Hummingbot version before applying changes.
2. Copy `deployment/hummingbot/watchdog.env.example` to `/etc/hlbot/hummingbot-watchdog.env` and edit **all** paths, market names and container name. Store the file outside Git. Default `HB_DRY_RUN=1` means the watchdog *reports* failures without restarting anything.
3. Run the watchdog manually as the same Unix user that has permission to read the Hummingbot files and access the Docker daemon:

   ```sh
   set -a; . /etc/hlbot/hummingbot-watchdog.env; set +a
   python3 deployment/hummingbot/watchdog.py
   ```

4. After confirming paths and detection with representative data, set `HB_DRY_RUN=0` if you want automatic `docker restart` on stale output. A cooldown prevents repeated restart attempts within `HB_RESTART_COOLDOWN_SECONDS`. **A restart is not confirmation of recovery**: review files and logs afterward.
5. Schedule with **either** the example systemd service/timer **or** `cron.example`, not both. The `.service` file assumes user `hlbot` and repository at `/opt/hlbot/repo`; adapt paths and permissions for your VPS. The cron example assumes the same environment-file and repo locations.

Example systemd installation (after editing the paths and `User=`):

```sh
sudo install -Dm644 deployment/hummingbot/hummingbot-watchdog.service /etc/systemd/system/hummingbot-watchdog.service
sudo install -Dm644 deployment/hummingbot/hummingbot-watchdog.timer /etc/systemd/system/hummingbot-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl enable --now hummingbot-watchdog.timer
systemctl list-timers --all | grep hummingbot-watchdog
journalctl -u hummingbot-watchdog.service -n 50 --no-pager
```

**Operational caveats:** Hummingbot markets may stop publishing on quiet periods; tune `HB_MAX_AGE_SECONDS` to avoid false alarms. The watchdog expects standard Hummingbot order-book filenames (not the separate Python collector's JSONL filenames). It uses a state-file cooldown, not a distributed lock; use a single scheduler and avoid overlapping invocations. Grant Docker access only to an appropriate trusted service user, because Docker socket permissions are highly privileged.

## C. Validation before deployment

```sh
python -m pytest -q tests/integration/test_deployment_health.py tests/unit/test_execution_import_integrity.py
python -m pytest -q
# Optional, if Docker is installed:
docker compose -f deployment/ws-collector/compose.yaml config
```

The example uses public data collection only, and is **not** a live order-execution deployment. Real VPS recovery and image/patch compatibility must be checked on your own host.
