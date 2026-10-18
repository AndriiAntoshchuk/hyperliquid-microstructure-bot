import bisect
from dataclasses import dataclass

from hlbot.backtest.accounting import (
    BacktestPosition,
    close_position,
    open_position,
    position_notional,
    scale_position,
    unrealized_pnl,
)
from hlbot.backtest.execution import (
    SimulatedFill,
    entry_side,
    execution_slippage_bps,
    exit_side,
    simulate_exit_order,
    simulate_market_order,
)
from hlbot.backtest.execution_policy import ExecutionMode, ExecutionPolicy
from hlbot.backtest.fees import FeeSchedule
from hlbot.backtest.latency import ExecutionLatency
from hlbot.backtest.maker import default_maker_price, place_maker_order
from hlbot.backtest.maker_lifecycle import PendingMakerOrder, advance_pending_maker
from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade
from hlbot.strategy.engine import StrategyAction, StrategyEngine, StrategyPosition
from hlbot.strategy.market_state import MarketStateBuilder
from hlbot.strategy.order_intent import OrderIntent
from hlbot.strategy.signal import SignalDirection


@dataclass(frozen=True)
class ReplayFill:
    action: StrategyAction
    fill: SimulatedFill
    fee_paid: float = 0.0
    execution_mode: ExecutionMode = ExecutionMode.TAKER

@dataclass(frozen=True)
class ReplayTrade:
    direction: SignalDirection
    entry_ts: float
    exit_ts: float
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float
    scale_ins: int
    exit_reason: str = "unknown"

    @property
    def holding_seconds(self) -> float:
        return self.exit_ts - self.entry_ts

@dataclass(frozen=True)
class ReplayEquityPoint:
    timestamp: float
    realized_pnl_gross: float
    unrealized_pnl: float
    fees_paid: float
    net_pnl: float

@dataclass(frozen=True)
class ReplayResult:
    fills: tuple[ReplayFill, ...]
    closed_positions: tuple[BacktestPosition, ...]
    final_position: BacktestPosition | None
    equity_curve: tuple[ReplayEquityPoint, ...]
    states_evaluated: int
    states_skipped: int
    trades: tuple[ReplayTrade, ...] = ()

    @property
    def total_realized_pnl_gross(self) -> float:
        total = sum(position.realized_pnl_gross for position in self.closed_positions)
        if self.final_position is not None: total += self.final_position.realized_pnl_gross
        return total

    @property
    def total_fees(self) -> float:
        total = sum(position.fees_paid for position in self.closed_positions)
        if self.final_position is not None: total += self.final_position.fees_paid
        return total

    @property
    def total_realized_pnl_net(self) -> float:
        return self.total_realized_pnl_gross - self.total_fees

@dataclass
class PendingReplayMaker:
    action: StrategyAction
    direction: SignalDirection
    state: PendingMakerOrder
    scale_counted: bool = False
    replacements_used: int = 0

@dataclass(frozen=True)
class PendingExecution:
    action: StrategyAction
    arrival_ts: float
    mode: ExecutionMode
    direction: SignalDirection
    order_intent: OrderIntent | None = None
    exit_quantity: float | None = None

def build_equity_point(timestamp: float, mid_price: float, closed_positions: list[BacktestPosition], position: BacktestPosition | None) -> ReplayEquityPoint:
    realized = sum(item.realized_pnl_gross for item in closed_positions)
    fees = sum(item.fees_paid for item in closed_positions)
    unrealized = 0.0

    if position is not None:
        realized += position.realized_pnl_gross
        fees += position.fees_paid
        unrealized = unrealized_pnl(position, mid_price)

    return ReplayEquityPoint(
        timestamp=timestamp,
        realized_pnl_gross=realized,
        unrealized_pnl=unrealized,
        fees_paid=fees,
        net_pnl=realized + unrealized - fees
    )

def maker_delta_fill(pending: PendingMakerOrder, delta_quantity: float, snapshot: OrderBookSnapshot) -> SimulatedFill:
    price = pending.order.limit_price

    return SimulatedFill(
        side=pending.order.side,
        timestamp=pending.last_fill_ts,
        requested_notional=0.0,
        filled_notional=delta_quantity * price,
        requested_quantity=delta_quantity,
        filled_quantity=delta_quantity,
        average_price=price,
        reference_mid_price=snapshot.mid_price,
        slippage_bps=execution_slippage_bps(pending.order.side, price, snapshot.mid_price),
        levels_consumed=0,
        fully_filled=True
    )

class ReplayBacktester:
    def __init__(
        self,
        strategy_engine: StrategyEngine,
        fee_bps: float | None = None,
        max_snapshot_age: float = 15.0,
        execution_policy: ExecutionPolicy | None = None,
        fee_schedule: FeeSchedule | None = None,
        latency: ExecutionLatency | None = None
    ):
        if max_snapshot_age <= 0: raise ValueError("max_snapshot_age must be positive")
        if fee_bps is not None and fee_schedule is not None: raise ValueError("use fee_bps or fee_schedule, not both")

        if fee_bps is not None:
            if fee_bps < 0: raise ValueError("legacy fee_bps cannot be negative")
            fee_schedule = FeeSchedule(taker_bps=fee_bps, maker_bps=fee_bps)

        self.strategy_engine = strategy_engine
        self.max_snapshot_age = max_snapshot_age
        self.execution_policy = execution_policy or ExecutionPolicy.taker_only()
        self.fee_schedule = fee_schedule or FeeSchedule()
        self.latency = latency or ExecutionLatency()

    def run(self, snapshots: list[OrderBookSnapshot], trades: list[Trade]) -> ReplayResult:
        snapshots = sorted(snapshots, key=lambda snapshot: (snapshot.exchange_ts, snapshot.local_ts))
        trades = sorted(trades, key=lambda trade: (trade.exchange_ts, trade.local_ts))
        trade_times = [trade.exchange_ts for trade in trades]
        state_builder = MarketStateBuilder(snapshots, trades, self.max_snapshot_age)

        fills = []
        completed_trades = []
        closed_positions = []
        equity_curve = []
        position = None
        pending_maker = None
        pending_execution = None
        entry_ts = None
        entry_quantity = 0.0
        entry_notional = 0.0
        exit_quantity = 0.0
        exit_notional = 0.0
        scale_ins_used = 0
        states_evaluated = 0
        states_skipped = 0
        previous_snapshot_ts = None

        for snapshot in snapshots:
            had_pending = pending_maker is not None or pending_execution is not None
            interval_trades = []

            if previous_snapshot_ts is not None:
                start = bisect.bisect_right(trade_times, previous_snapshot_ts)
                end = bisect.bisect_right(trade_times, snapshot.exchange_ts)
                interval_trades = trades[start:end]

            if pending_maker is not None:
                expiry_ts = pending_maker.state.order.placed_ts + self.execution_policy.maker_max_age_seconds
                eligible_trades = [trade for trade in interval_trades if trade.exchange_ts <= expiry_ts]
                previous_filled = pending_maker.state.filled_quantity
                pending_maker.state = advance_pending_maker(pending_maker.state, eligible_trades)
                delta_quantity = pending_maker.state.filled_quantity - previous_filled

                if delta_quantity > 0:
                    mode = ExecutionMode.MAKER
                    fee_bps = self.fee_schedule.bps_for(mode)
                    fill = maker_delta_fill(pending_maker.state, delta_quantity, snapshot)
                    fee = self.fee_schedule.fee_for(fill.filled_notional, mode)
                    fills.append(ReplayFill(pending_maker.action, fill, fee, mode))

                    if pending_maker.action == StrategyAction.ENTER:
                        if position is None:
                            position = open_position(pending_maker.direction, fill, fee_bps)
                            entry_ts = fill.timestamp
                        else:
                            position = scale_position(position, fill, fee_bps)

                        entry_quantity += fill.filled_quantity
                        entry_notional += fill.filled_notional

                    elif pending_maker.action == StrategyAction.SCALE_IN:
                        if position is None: raise RuntimeError("cannot scale without open position")

                        position = scale_position(position, fill, fee_bps)
                        entry_quantity += fill.filled_quantity
                        entry_notional += fill.filled_notional

                        if not pending_maker.scale_counted:
                            scale_ins_used += 1
                            pending_maker.scale_counted = True

                    elif pending_maker.action == StrategyAction.EXIT:
                        if position is None: raise RuntimeError("cannot exit without open position")

                        direction = position.direction
                        exit_quantity += fill.filled_quantity
                        exit_notional += fill.filled_notional
                        position = close_position(position, fill, fee_bps)

                        if position.is_flat:
                            entry_price = entry_notional / entry_quantity
                            exit_price = exit_notional / exit_quantity
                            gross_pnl = (exit_price - entry_price) * exit_quantity if direction == SignalDirection.LONG else (entry_price - exit_price) * exit_quantity

                            closed_positions.append(position)
                            completed_trades.append(
                                ReplayTrade(
                                    direction=direction,
                                    entry_ts=entry_ts,
                                    exit_ts=fill.timestamp,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    quantity=exit_quantity,
                                    gross_pnl=gross_pnl,
                                    fees=position.fees_paid,
                                    net_pnl=gross_pnl - position.fees_paid,
                                    scale_ins=scale_ins_used
                                )
                            )

                            position = None
                            entry_ts = None
                            entry_quantity = 0.0
                            entry_notional = 0.0
                            exit_quantity = 0.0
                            exit_notional = 0.0
                            scale_ins_used = 0

                    else:
                        raise RuntimeError(f"unsupported pending action: {pending_maker.action}")

                if pending_maker.state.fully_filled:
                    pending_maker = None

                elif snapshot.exchange_ts >= expiry_ts:
                    if pending_maker.replacements_used < self.execution_policy.maker_max_replacements:
                        side = pending_maker.state.order.side
                        price = default_maker_price(snapshot, side)

                        order = place_maker_order(
                            snapshot,
                            side,
                            pending_maker.state.remaining_quantity,
                            limit_price=price,
                            queue_ahead_fraction=self.execution_policy.maker_queue_ahead_fraction
                        )

                        pending_maker = PendingReplayMaker(
                            action=pending_maker.action,
                            direction=pending_maker.direction,
                            state=PendingMakerOrder.from_order(order),
                            scale_counted=pending_maker.scale_counted,
                            replacements_used=pending_maker.replacements_used + 1
                        )
                    else:
                        pending_maker = None

            if pending_execution is not None and snapshot.exchange_ts >= pending_execution.arrival_ts:
                action = pending_execution.action
                mode = pending_execution.mode
                direction = pending_execution.direction

                if mode == ExecutionMode.MAKER:
                    side = entry_side(direction) if action in (StrategyAction.ENTER, StrategyAction.SCALE_IN) else exit_side(direction)
                    price = default_maker_price(snapshot, side)

                    if action in (StrategyAction.ENTER, StrategyAction.SCALE_IN):
                        if pending_execution.order_intent is None: raise RuntimeError("maker entry requires order intent")
                        quantity = pending_execution.order_intent.notional / price
                    else:
                        if pending_execution.exit_quantity is None: raise RuntimeError("maker exit requires quantity")
                        quantity = pending_execution.exit_quantity

                    order = place_maker_order(
                        snapshot,
                        side,
                        quantity,
                        limit_price=price,
                        queue_ahead_fraction=self.execution_policy.maker_queue_ahead_fraction
                    )

                    pending_maker = PendingReplayMaker(
                        action=action,
                        direction=direction,
                        state=PendingMakerOrder.from_order(order)
                    )

                elif action in (StrategyAction.ENTER, StrategyAction.SCALE_IN):
                    if pending_execution.order_intent is None: raise RuntimeError("taker entry requires order intent")

                    fee_bps = self.fee_schedule.bps_for(mode)
                    fill = simulate_market_order(snapshot, pending_execution.order_intent)

                    if fill.filled_quantity > 0:
                        fee = self.fee_schedule.fee_for(fill.filled_notional, mode)
                        fills.append(ReplayFill(action, fill, fee, mode))

                        if action == StrategyAction.ENTER:
                            if position is not None: raise RuntimeError("cannot enter while position is open")

                            position = open_position(direction, fill, fee_bps)
                            entry_ts = fill.timestamp
                            scale_ins_used = 0
                        else:
                            if position is None: raise RuntimeError("cannot scale without open position")

                            position = scale_position(position, fill, fee_bps)
                            scale_ins_used += 1

                        entry_quantity += fill.filled_quantity
                        entry_notional += fill.filled_notional

                elif action == StrategyAction.EXIT:
                    if position is None: raise RuntimeError("cannot exit without open position")
                    if pending_execution.exit_quantity is None: raise RuntimeError("taker exit requires quantity")

                    fee_bps = self.fee_schedule.bps_for(mode)
                    fill = simulate_exit_order(snapshot, direction, pending_execution.exit_quantity)

                    if fill.filled_quantity > 0:
                        fee = self.fee_schedule.fee_for(fill.filled_notional, mode)
                        fills.append(ReplayFill(action, fill, fee, mode))
                        exit_quantity += fill.filled_quantity
                        exit_notional += fill.filled_notional
                        position = close_position(position, fill, fee_bps)

                        if position.is_flat:
                            entry_price = entry_notional / entry_quantity
                            exit_price = exit_notional / exit_quantity
                            gross_pnl = (exit_price - entry_price) * exit_quantity if direction == SignalDirection.LONG else (entry_price - exit_price) * exit_quantity

                            closed_positions.append(position)
                            completed_trades.append(
                                ReplayTrade(
                                    direction=direction,
                                    entry_ts=entry_ts,
                                    exit_ts=fill.timestamp,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    quantity=exit_quantity,
                                    gross_pnl=gross_pnl,
                                    fees=position.fees_paid,
                                    net_pnl=gross_pnl - position.fees_paid,
                                    scale_ins=scale_ins_used
                                )
                            )

                            position = None
                            entry_ts = None
                            entry_quantity = 0.0
                            entry_notional = 0.0
                            exit_quantity = 0.0
                            exit_notional = 0.0
                            scale_ins_used = 0

                else:
                    raise RuntimeError(f"unsupported pending execution action: {action}")

                pending_execution = None

            state = state_builder.build(snapshot.exchange_ts)
            previous_snapshot_ts = snapshot.exchange_ts

            if state is None:
                states_skipped += 1
                continue

            states_evaluated += 1

            if had_pending:
                equity_curve.append(build_equity_point(snapshot.exchange_ts, state.mid_price, closed_positions, position))
                continue

            strategy_position = None

            if position is not None:
                strategy_position = StrategyPosition(
                    direction=position.direction,
                    entry_price=position.average_entry_price,
                    entry_ts=entry_ts,
                    current_notional=position_notional(position, state.mid_price),
                    scale_ins_used=scale_ins_used
                )

            decision = self.strategy_engine.evaluate(state, strategy_position)

            if decision.action in (StrategyAction.ENTER, StrategyAction.SCALE_IN):
                if decision.order_intent is None: raise RuntimeError(f"{decision.action.value} requires order_intent")

                mode = self.execution_policy.entry_mode if decision.action == StrategyAction.ENTER else self.execution_policy.scale_in_mode
                latency_seconds = self.latency.seconds_for(decision.action)

                if latency_seconds > 0:
                    pending_execution = PendingExecution(
                        action=decision.action,
                        arrival_ts=snapshot.exchange_ts + latency_seconds,
                        mode=mode,
                        direction=decision.order_intent.direction,
                        order_intent=decision.order_intent
                    )
                elif mode == ExecutionMode.MAKER:
                    side = entry_side(decision.order_intent.direction)
                    price = default_maker_price(snapshot, side)
                    quantity = decision.order_intent.notional / price

                    order = place_maker_order(
                        snapshot,
                        side,
                        quantity,
                        limit_price=price,
                        queue_ahead_fraction=self.execution_policy.maker_queue_ahead_fraction
                    )

                    pending_maker = PendingReplayMaker(
                        action=decision.action,
                        direction=decision.order_intent.direction,
                        state=PendingMakerOrder.from_order(order)
                    )
                else:
                    fee_bps = self.fee_schedule.bps_for(mode)
                    fill = simulate_market_order(snapshot, decision.order_intent)

                    if fill.filled_quantity > 0:
                        fee = self.fee_schedule.fee_for(fill.filled_notional, mode)
                        fills.append(ReplayFill(decision.action, fill, fee, mode))

                        if decision.action == StrategyAction.ENTER:
                            if position is not None: raise RuntimeError("cannot enter while position is open")

                            position = open_position(decision.order_intent.direction, fill, fee_bps)
                            entry_ts = fill.timestamp
                            scale_ins_used = 0
                        else:
                            if position is None: raise RuntimeError("cannot scale without open position")

                            position = scale_position(position, fill, fee_bps)
                            scale_ins_used += 1

                        entry_quantity += fill.filled_quantity
                        entry_notional += fill.filled_notional

            elif decision.action == StrategyAction.EXIT:
                if position is None: raise RuntimeError("cannot exit without open position")

                mode = self.execution_policy.exit_mode
                latency_seconds = self.latency.seconds_for(StrategyAction.EXIT)

                if latency_seconds > 0:
                    pending_execution = PendingExecution(
                        action=StrategyAction.EXIT,
                        arrival_ts=snapshot.exchange_ts + latency_seconds,
                        mode=mode,
                        direction=position.direction,
                        exit_quantity=position.quantity
                    )
                elif mode == ExecutionMode.MAKER:
                    side = exit_side(position.direction)
                    price = default_maker_price(snapshot, side)

                    order = place_maker_order(
                        snapshot,
                        side,
                        position.quantity,
                        limit_price=price,
                        queue_ahead_fraction=self.execution_policy.maker_queue_ahead_fraction
                    )

                    pending_maker = PendingReplayMaker(
                        action=StrategyAction.EXIT,
                        direction=position.direction,
                        state=PendingMakerOrder.from_order(order)
                    )
                else:
                    fee_bps = self.fee_schedule.bps_for(mode)
                    direction = position.direction
                    fill = simulate_exit_order(snapshot, direction, position.quantity)

                    if fill.filled_quantity > 0:
                        fee = self.fee_schedule.fee_for(fill.filled_notional, mode)
                        fills.append(ReplayFill(StrategyAction.EXIT, fill, fee, mode))
                        exit_quantity += fill.filled_quantity
                        exit_notional += fill.filled_notional
                        position = close_position(position, fill, fee_bps)

                        if position.is_flat:
                            entry_price = entry_notional / entry_quantity
                            exit_price = exit_notional / exit_quantity
                            gross_pnl = (exit_price - entry_price) * exit_quantity if direction == SignalDirection.LONG else (entry_price - exit_price) * exit_quantity

                            closed_positions.append(position)
                            completed_trades.append(
                                ReplayTrade(
                                    direction=direction,
                                    entry_ts=entry_ts,
                                    exit_ts=fill.timestamp,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    quantity=exit_quantity,
                                    gross_pnl=gross_pnl,
                                    fees=position.fees_paid,
                                    net_pnl=gross_pnl - position.fees_paid,
                                    scale_ins=scale_ins_used,
                                    exit_reason=decision.exit_decision.reason.value
                                )
                            )

                            position = None
                            entry_ts = None
                            entry_quantity = 0.0
                            entry_notional = 0.0
                            exit_quantity = 0.0
                            exit_notional = 0.0
                            scale_ins_used = 0

            elif decision.action != StrategyAction.HOLD:
                raise RuntimeError(f"unsupported strategy action: {decision.action}")

            equity_curve.append(build_equity_point(snapshot.exchange_ts, state.mid_price, closed_positions, position))

        return ReplayResult(
            fills=tuple(fills),
            closed_positions=tuple(closed_positions),
            final_position=position,
            equity_curve=tuple(equity_curve),
            states_evaluated=states_evaluated,
            states_skipped=states_skipped,
            trades=tuple(completed_trades)
        )