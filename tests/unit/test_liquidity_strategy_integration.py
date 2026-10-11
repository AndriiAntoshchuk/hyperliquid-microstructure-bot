from hlbot.strategy.engine import StrategyAction, StrategyEngine
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

class LongSignal:
    def evaluate(self, state):
        return SignalDecision(SignalDirection.LONG, 1.0, "test")

def market_state(bid: float = 400, ask: float = 600) -> MarketState:
    return MarketState(
        timestamp=100,
        mid_price=100,
        spread_bps=1,
        imbalance_1=0,
        imbalance_5=0,
        weighted_imbalance_5=0,
        microprice_deviation_bps=0,
        trade_flow_5s=0,
        volatility_10s=0,
        bid_liquidity_10bps=1000,
        ask_liquidity_10bps=1000,
        return_5s=0,
        return_30s=0,
        bid_visible_notional_5=bid,
        ask_visible_notional_5=ask
    )

def test_entry_is_liquidity_capped():
    spec = StrategySpec(1000, 1000, 0, max_visible_liquidity_fraction=.25)
    decision = StrategyEngine(spec, LongSignal()).evaluate(market_state())

    assert decision.action == StrategyAction.ENTER
    assert decision.order_intent is not None
    assert decision.order_intent.notional == 100

def test_entry_is_unchanged_without_liquidity_cap():
    spec = StrategySpec(1000, 1000, 0)
    decision = StrategyEngine(spec, LongSignal()).evaluate(market_state())

    assert decision.action == StrategyAction.ENTER
    assert decision.order_intent is not None
    assert decision.order_intent.notional == 1000

def test_zero_visible_liquidity_blocks_entry():
    spec = StrategySpec(1000, 1000, 0, max_visible_liquidity_fraction=.25)
    decision = StrategyEngine(spec, LongSignal()).evaluate(market_state(bid=0))

    assert decision.action == StrategyAction.HOLD
    assert decision.order_intent is None