from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from hlbot.execution.fill import ExecutionFill

@dataclass(frozen=True)
class LivePosition:
    coin: str
    quantity: float = 0.0
    average_entry_price: float | None = None

    def __post_init__(self):
        if not self.coin: raise ValueError("coin cannot be empty")
        if not isfinite(self.quantity): raise ValueError("quantity must be finite")

        if self.average_entry_price is not None:
            if not isfinite(self.average_entry_price) or self.average_entry_price <= 0:
                raise ValueError("average_entry_price must be positive and finite")

        if self.quantity == 0 and self.average_entry_price is not None:
            raise ValueError("flat position cannot have average_entry_price")

        if self.quantity != 0 and self.average_entry_price is None:
            raise ValueError("open position requires average_entry_price")

    @property
    def direction(self) -> str:
        if self.quantity > 0: return "long"
        if self.quantity < 0: return "short"
        return "flat"

@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    peak_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fees: float

    @property
    def drawdown_pct(self) -> float:
        return max(0.0, (self.peak_equity - self.equity) / self.peak_equity * 100)

class AccountTracker:
    def __init__(self, starting_equity: float):
        if not isfinite(starting_equity) or starting_equity <= 0:
            raise ValueError("starting_equity must be positive and finite")

        self.starting_equity = starting_equity
        self._positions: dict[str, LivePosition] = {}
        self._marks: dict[str, float] = {}
        self._fill_ids: set[str] = set()
        self._gross_realized_pnl = 0.0
        self._fees = 0.0
        self._daily_realized_pnl: dict[str, float] = {}
        self._peak_equity = starting_equity

    def position(self, coin: str) -> LivePosition:
        return self._positions.get(coin, LivePosition(coin))
    
    def positions(self) -> tuple[LivePosition, ...]:
        return tuple(sorted(self._positions.values(), key=lambda position: position.coin))
    
    def has_fill(self, fill_id: str) -> bool:
        return fill_id in self._fill_ids

    def apply_fill(self, fill: ExecutionFill) -> None:
        if fill.fill_id in self._fill_ids:
            raise ValueError(f"duplicate fill: {fill.fill_id}")

        position = self.position(fill.coin)
        old_quantity = position.quantity
        fill_quantity = fill.signed_quantity
        new_quantity = old_quantity + fill_quantity
        average = position.average_entry_price
        realized = 0.0

        if old_quantity == 0 or old_quantity * fill_quantity > 0:
            old_notional = abs(old_quantity) * (average or 0.0)
            fill_notional = abs(fill_quantity) * fill.price
            total_quantity = abs(old_quantity) + abs(fill_quantity)
            new_average = (old_notional + fill_notional) / total_quantity
        else:
            close_quantity = min(abs(old_quantity), abs(fill_quantity))

            if old_quantity > 0:
                realized = close_quantity * (fill.price - average)
            else:
                realized = close_quantity * (average - fill.price)

            if new_quantity == 0:
                new_average = None
            elif old_quantity * new_quantity > 0:
                new_average = average
            else:
                new_average = fill.price

        self._positions[fill.coin] = LivePosition(fill.coin, new_quantity, new_average)
        self._fill_ids.add(fill.fill_id)
        self._gross_realized_pnl += realized
        self._fees += fill.fee

        day = datetime.fromtimestamp(fill.timestamp, timezone.utc).date().isoformat()
        self._daily_realized_pnl[day] = self._daily_realized_pnl.get(day, 0.0) + realized - fill.fee

        self._update_peak_equity()

    def update_mark(self, coin: str, price: float) -> None:
        if not isfinite(price) or price <= 0:
            raise ValueError("mark price must be positive and finite")

        self._marks[coin] = price
        self._update_peak_equity()

    def position_notional(self, coin: str) -> float:
        position = self.position(coin)

        if position.quantity == 0:
            return 0.0

        mark = self._marks.get(coin, position.average_entry_price)
        return abs(position.quantity) * mark

    @property
    def gross_realized_pnl(self) -> float:
        return self._gross_realized_pnl

    @property
    def fees(self) -> float:
        return self._fees

    @property
    def realized_pnl(self) -> float:
        return self._gross_realized_pnl - self._fees

    @property
    def unrealized_pnl(self) -> float:
        total = 0.0

        for coin, position in self._positions.items():
            if position.quantity == 0: continue

            mark = self._marks.get(coin, position.average_entry_price)
            total += position.quantity * (mark - position.average_entry_price)

        return total

    @property
    def equity(self) -> float:
        return self.starting_equity + self.realized_pnl + self.unrealized_pnl

    @property
    def peak_equity(self) -> float:
        return self._peak_equity

    def realized_pnl_for_day(self, timestamp: float) -> float:
        day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        return self._daily_realized_pnl.get(day, 0.0)

    def snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            self.equity,
            self.peak_equity,
            self.realized_pnl,
            self.unrealized_pnl,
            self.fees
        )

    def _update_peak_equity(self) -> None:
        self._peak_equity = max(self._peak_equity, self.equity)