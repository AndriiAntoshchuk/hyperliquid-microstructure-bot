from hlbot.models.trade import Trade, TradeSide

def buy_sell_volume(trades: list[Trade]) -> tuple[float, float]:
    buy_volume = sum(trade.quantity for trade in trades if trade.side == TradeSide.BUY)
    sell_volume = sum(trade.quantity for trade in trades if trade.side == TradeSide.SELL)
    return buy_volume, sell_volume

def trade_flow_imbalance(trades: list[Trade]) -> float:
    buy_volume, sell_volume = buy_sell_volume(trades)
    total = buy_volume + sell_volume
    return 0.0 if total == 0 else (buy_volume - sell_volume) / total

def trades_in_window(trades: list[Trade], end_ts: float, window_seconds: float) -> list[Trade]:
    if window_seconds <= 0: raise ValueError("window_seconds must be positive")
    start_ts = end_ts - window_seconds
    return [trade for trade in trades if start_ts < trade.exchange_ts <= end_ts]

def rolling_trade_flow_imbalance(trades: list[Trade], end_ts: float, window_seconds: float) -> float:
    return trade_flow_imbalance(trades_in_window(trades, end_ts, window_seconds))

def rolling_trade_flow_features(trades: list[Trade], end_ts: float, windows=(1, 3, 5, 10, 30)) -> dict[str, float]:
    result = {}
    for window in windows:
        selected = trades_in_window(trades, end_ts, window)
        buy_volume, sell_volume = buy_sell_volume(selected)
        total = buy_volume + sell_volume
        suffix = f"{window:g}s"
        result[f"buy_volume_{suffix}"] = buy_volume
        result[f"sell_volume_{suffix}"] = sell_volume
        result[f"tfi_{suffix}"] = 0.0 if total == 0 else (buy_volume - sell_volume) / total
    return result