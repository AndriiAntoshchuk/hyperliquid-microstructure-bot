from collections import defaultdict

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill

POSITION_EPSILON = 1e-9
PERP_DIRECTIONS = {"Open Long", "Close Long", "Open Short", "Close Short"}

class EpisodeBuilder:
    def build(self, fills: list[WalletFill]) -> list[TradingEpisode]:
        fills_by_coin = defaultdict(list)

        for fill in fills:
            if not self._is_perpetual(fill): continue
            fills_by_coin[fill.coin].append(fill)

        episodes = []
        for coin_fills in fills_by_coin.values():
            episodes.extend(self._build_coin(sorted(coin_fills, key=lambda fill: fill.timestamp)))

        return sorted(episodes, key=lambda episode: episode.start_ts)

    def _build_coin(self, fills: list[WalletFill]) -> list[TradingEpisode]:
        if not fills: return []

        episodes = []
        current_fills = []
        current_pnl = 0.0
        synchronized = False

        for fill in fills:
            if fill.start_position is None: raise ValueError(f"Fill {fill.trade_id} has no start_position")

            start_position = self._normalize_position(fill.start_position)
            end_position = self._normalize_position(start_position + self._signed_quantity(fill))

            if not synchronized:
                if self._is_flat(start_position):
                    synchronized = True
                elif self._is_flat(end_position):
                    synchronized = True
                    continue
                elif self._position_flipped(start_position, end_position):
                    synchronized = True
                    current_fills = [fill]
                    current_pnl = 0.0
                    continue
                else:
                    continue

            if not current_fills:
                if self._is_flat(start_position) and not self._is_flat(end_position):
                    current_fills = [fill]
                    current_pnl = fill.closed_pnl
                elif not self._is_flat(start_position):
                    synchronized = False

                continue

            current_fills.append(fill)
            current_pnl += fill.closed_pnl

            if self._is_flat(end_position):
                episodes.append(self._make_episode(current_fills, current_pnl))
                current_fills = []
                current_pnl = 0.0
            elif self._position_flipped(start_position, end_position):
                episodes.append(self._make_episode(current_fills, current_pnl))
                current_fills = [fill]
                current_pnl = 0.0

        return episodes

    @staticmethod
    def _make_episode(fills: list[WalletFill], realized_pnl: float) -> TradingEpisode:
        first = fills[0]
        last = fills[-1]

        return TradingEpisode(
            wallet=first.wallet,
            coin=first.coin,
            start_ts=first.timestamp,
            end_ts=last.timestamp,
            fills=tuple(fills),
            realized_pnl=realized_pnl
        )

    @staticmethod
    def _is_perpetual(fill: WalletFill) -> bool:
        return fill.direction in PERP_DIRECTIONS

    @staticmethod
    def _signed_quantity(fill: WalletFill) -> float:
        return fill.quantity if fill.side == "buy" else -fill.quantity

    @staticmethod
    def _normalize_position(position: float) -> float:
        return 0.0 if abs(position) <= POSITION_EPSILON else position

    @staticmethod
    def _is_flat(position: float) -> bool:
        return abs(position) <= POSITION_EPSILON

    @staticmethod
    def _position_flipped(start_position: float, end_position: float) -> bool:
        return start_position * end_position < 0