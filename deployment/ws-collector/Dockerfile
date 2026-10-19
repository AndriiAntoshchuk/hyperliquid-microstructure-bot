FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY scripts/collect_hyperliquid_ws.py ./scripts/collect_hyperliquid_ws.py
COPY deployment/ws-collector/healthcheck.py ./deployment/ws-collector/healthcheck.py

RUN pip install --no-cache-dir . \
    && groupadd --system hlbot \
    && useradd --system --gid hlbot --home-dir /app hlbot \
    && mkdir -p /data/raw \
    && chown -R hlbot:hlbot /data

USER hlbot

CMD ["python", "scripts/collect_hyperliquid_ws.py", "--coins", "BTC", "--data-dir", "/data/raw"]
