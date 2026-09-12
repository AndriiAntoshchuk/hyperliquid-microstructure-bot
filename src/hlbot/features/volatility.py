import math
from statistics import pstdev

def log_returns(prices: list[float]) -> list[float]:
    if any(price <= 0 for price in prices): raise ValueError("prices must be positive")
    return [math.log(current / previous) for previous, current in zip(prices, prices[1:])]

def volatility(prices: list[float]) -> float:
    returns = log_returns(prices)
    return 0.0 if len(returns) < 2 else pstdev(returns)