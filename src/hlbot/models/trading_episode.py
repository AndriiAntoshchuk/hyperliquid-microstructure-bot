from dataclasses import dataclass

from hlbot.models.wallet_fill import WalletFill

@dataclass(frozen=True)
class TradingEpisode:
    wallet: str
    coin: str
    start_ts: float
    end_ts: float
    fills: tuple[WalletFill, ...]
    realized_pnl: float

    def __post_init__(self):
        if not self.wallet: raise ValueError("wallet cannot be empty")
        if not self.coin: raise ValueError("coin cannot be empty")
        if self.start_ts <= 0 or self.end_ts <= 0: raise ValueError("timestamps must be positive")
        if self.end_ts < self.start_ts: raise ValueError("end_ts cannot be before start_ts")
        if not self.fills: raise ValueError("episode must contain fills")

    @property
    def duration(self) -> float:
        return self.end_ts - self.start_ts

    @property
    def number_of_fills(self) -> int:
        return len(self.fills)

    @property
    def direction(self) -> str:
        return "long" if self.fills[0].side == "buy" else "short"

    @property
    def max_position_size(self) -> float:
        max_position = 0.0

        for fill in self.fills:
            if fill.start_position is None: continue
            signed_quantity = fill.quantity if fill.side == "buy" else -fill.quantity
            end_position = fill.start_position + signed_quantity
            max_position = max(max_position, abs(fill.start_position), abs(end_position))

        return max_position

    @property
    def vwap_entry(self) -> float:
        entry_side = "buy" if self.direction == "long" else "sell"
        entries = [fill for fill in self.fills if fill.side == entry_side]
        quantity = sum(fill.quantity for fill in entries)

        if quantity == 0: return 0.0
        return sum(fill.price * fill.quantity for fill in entries) / quantity

    @property
    def vwap_exit(self) -> float:
        exit_side = "sell" if self.direction == "long" else "buy"
        exits = [fill for fill in self.fills if fill.side == exit_side]
        quantity = sum(fill.quantity for fill in exits)

        if quantity == 0: return 0.0
        return sum(fill.price * fill.quantity for fill in exits) / quantity

    @property
    def return_pct(self) -> float:
        if self.vwap_entry == 0 or self.vwap_exit == 0: return 0.0
        if self.direction == "long": return (self.vwap_exit / self.vwap_entry - 1) * 100
        return (self.vwap_entry / self.vwap_exit - 1) * 100