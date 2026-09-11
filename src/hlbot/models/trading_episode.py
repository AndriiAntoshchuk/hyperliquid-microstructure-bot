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
        if not self.wallet:
            raise ValueError("wallet cannot be empty")

        if not self.coin:
            raise ValueError("coin cannot be empty")

        if self.start_ts <= 0 or self.end_ts <= 0:
            raise ValueError("timestamps must be positive")

        if self.end_ts < self.start_ts:
            raise ValueError("end_ts cannot be before start_ts")

        if not self.fills:
            raise ValueError("episode must contain fills")

    @property
    def duration(self) -> float:
        return self.end_ts - self.start_ts

    @property
    def number_of_fills(self) -> int:
        return len(self.fills)