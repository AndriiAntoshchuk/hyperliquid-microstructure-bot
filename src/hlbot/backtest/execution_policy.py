from dataclasses import dataclass
from enum import Enum
from math import isfinite

class ExecutionMode(str, Enum):
    TAKER = "taker"
    MAKER = "maker"

@dataclass(frozen=True)
class ExecutionPolicy:
    entry_mode: ExecutionMode = ExecutionMode.TAKER
    scale_in_mode: ExecutionMode = ExecutionMode.TAKER
    exit_mode: ExecutionMode = ExecutionMode.TAKER
    maker_max_age_seconds: float = 10.0
    maker_queue_ahead_fraction: float = 1.0
    maker_max_replacements: int = 0

    def __post_init__(self):
        if not isfinite(self.maker_max_age_seconds) or self.maker_max_age_seconds <= 0:
            raise ValueError("maker_max_age_seconds must be positive and finite")
        if not isfinite(self.maker_queue_ahead_fraction) or self.maker_queue_ahead_fraction < 0:
            raise ValueError("maker_queue_ahead_fraction must be finite and non-negative")
        if not isinstance(self.maker_max_replacements, int) or self.maker_max_replacements < 0:
            raise ValueError("maker_max_replacements must be a non-negative integer")

    @classmethod
    def taker_only(cls):
        return cls()

    @classmethod
    def maker_entries(cls, max_age_seconds: float = 10.0, queue_ahead_fraction: float = 1.0, max_replacements: int = 0):
        return cls(
            ExecutionMode.MAKER,
            ExecutionMode.MAKER,
            ExecutionMode.TAKER,
            max_age_seconds,
            queue_ahead_fraction,
            max_replacements
        )

    @classmethod
    def maker_only(cls, max_age_seconds: float = 10.0, queue_ahead_fraction: float = 1.0, max_replacements: int = 0):
        return cls(
            ExecutionMode.MAKER,
            ExecutionMode.MAKER,
            ExecutionMode.MAKER,
            max_age_seconds,
            queue_ahead_fraction,
            max_replacements
        )