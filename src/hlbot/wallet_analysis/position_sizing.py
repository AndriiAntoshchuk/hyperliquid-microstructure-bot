from dataclasses import dataclass
from statistics import mean, median

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill

POSITION_EPSILON = 1e-9

@dataclass(frozen=True)
class OrderExecution:
    order_id: int
    side: str
    first_ts: float
    last_ts: float
    fill_count: int
    quantity: float
    notional: float
    average_price: float
    start_position: float | None
    end_position: float | None
    change_type: str

@dataclass(frozen=True)
class SizingObservation:
    wallet: str
    coin: str
    direction: str
    start_ts: float
    initial_entry_notional: float
    max_position_notional: float
    total_entry_notional: float
    number_of_orders: int
    initial_entry_fill_count: int
    scale_in_count: int
    scale_out_count: int
    flip_count: int

    @property
    def scale_ratio(self) -> float:
        if self.initial_entry_notional == 0: return 0.0
        return self.max_position_notional / self.initial_entry_notional

    @property
    def scaled_in(self) -> bool:
        return self.scale_in_count > 0

@dataclass(frozen=True)
class SizingSummary:
    episodes: int
    average_initial_entry_notional: float
    median_initial_entry_notional: float
    average_max_position_notional: float
    median_max_position_notional: float
    average_scale_ratio: float
    scaled_in_fraction: float
    average_orders_per_episode: float
    average_scale_in_count: float
    average_scale_out_count: float

def signed_quantity(fill: WalletFill) -> float:
    return fill.quantity if fill.side == "buy" else -fill.quantity

def end_position(fill: WalletFill) -> float | None:
    if fill.start_position is None: return None
    return fill.start_position + signed_quantity(fill)

def classify_position_change(start: float | None, end: float | None) -> str:
    if start is None or end is None: return "unknown"
    if start * end < -POSITION_EPSILON: return "flip"

    before = abs(start)
    after = abs(end)

    if before <= POSITION_EPSILON and after > POSITION_EPSILON: return "entry"
    if after > before + POSITION_EPSILON: return "scale_in"
    if after < before - POSITION_EPSILON: return "scale_out"
    return "unchanged"

def position_change_type(fill: WalletFill) -> str:
    return classify_position_change(fill.start_position, end_position(fill))

def build_order_executions(episode: TradingEpisode) -> list[OrderExecution]:
    grouped = {}

    for fill in episode.fills:
        grouped.setdefault(fill.order_id, []).append(fill)

    orders = []

    for order_id, fills in grouped.items():
        sides = {fill.side for fill in fills}
        if len(sides) != 1: raise ValueError(f"Order {order_id} contains multiple sides")

        first = fills[0]
        last = fills[-1]
        quantity = sum(fill.quantity for fill in fills)
        notional = sum(fill.price * fill.quantity for fill in fills)
        start = first.start_position
        end = end_position(last)

        orders.append(
            OrderExecution(
                order_id=order_id,
                side=first.side,
                first_ts=first.timestamp,
                last_ts=last.timestamp,
                fill_count=len(fills),
                quantity=quantity,
                notional=notional,
                average_price=notional / quantity,
                start_position=start,
                end_position=end,
                change_type=classify_position_change(start, end)
            )
        )

    return sorted(orders, key=lambda order: order.first_ts)

def max_position_notional(episode: TradingEpisode) -> float:
    values = []

    for fill in episode.fills:
        if fill.start_position is None: continue

        end = end_position(fill)
        values.append(abs(fill.start_position) * fill.price)

        if end is not None: values.append(abs(end) * fill.price)

    return max(values, default=0.0)

def analyze_episode_sizing(episode: TradingEpisode) -> SizingObservation:
    orders = build_order_executions(episode)

    if not orders: raise ValueError("episode contains no orders")

    entry_order = next((order for order in orders if order.change_type == "entry"), orders[0])
    scale_ins = [order for order in orders if order.change_type == "scale_in"]
    scale_outs = [order for order in orders if order.change_type == "scale_out"]
    flips = [order for order in orders if order.change_type == "flip"]

    total_entry_notional = sum(
        order.notional
        for order in orders
        if order.change_type in {"entry", "scale_in"}
    )

    return SizingObservation(
        wallet=episode.wallet,
        coin=episode.coin,
        direction=episode.direction,
        start_ts=episode.start_ts,
        initial_entry_notional=entry_order.notional,
        max_position_notional=max_position_notional(episode),
        total_entry_notional=total_entry_notional,
        number_of_orders=len(orders),
        initial_entry_fill_count=entry_order.fill_count,
        scale_in_count=len(scale_ins),
        scale_out_count=len(scale_outs),
        flip_count=len(flips)
    )

def analyze_position_sizing(episodes: list[TradingEpisode]) -> list[SizingObservation]:
    return [analyze_episode_sizing(episode) for episode in episodes]

def summarize_position_sizing(observations: list[SizingObservation]) -> SizingSummary:
    if not observations:
        return SizingSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    return SizingSummary(
        episodes=len(observations),
        average_initial_entry_notional=mean(item.initial_entry_notional for item in observations),
        median_initial_entry_notional=median(item.initial_entry_notional for item in observations),
        average_max_position_notional=mean(item.max_position_notional for item in observations),
        median_max_position_notional=median(item.max_position_notional for item in observations),
        average_scale_ratio=mean(item.scale_ratio for item in observations),
        scaled_in_fraction=sum(item.scaled_in for item in observations) / len(observations),
        average_orders_per_episode=mean(item.number_of_orders for item in observations),
        average_scale_in_count=mean(item.scale_in_count for item in observations),
        average_scale_out_count=mean(item.scale_out_count for item in observations)
    )