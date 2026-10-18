import json
import time
from dataclasses import asdict, dataclass
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from hlbot.execution.hyperliquid_testnet import TESTNET_API_URL
from hlbot.execution.hyperliquid_testnet_session import HyperliquidTestnetSession


@dataclass(frozen=True)
class MarketOpenPreview:
    coin:str
    side:str
    requested_notional:float
    mid:float
    quantity:float
    estimated_notional:float
    sz_decimals:int
    slippage_bps:float

@dataclass(frozen=True)
class RiskSizedOpenPreview:
    coin:str
    side:str
    risk_dollars:float
    stop_price:float
    reference_entry_price:float
    risk_per_unit:float
    quantity:float
    estimated_notional:float
    planned_stop_risk:float
    sz_decimals:int
    slippage_bps:float

@dataclass(frozen=True)
class MarketClosePreview:
    coin:str
    side:str
    mid:float
    quantity:float
    estimated_notional:float
    entry_price:float
    slippage_bps:float


class HyperliquidTestnetExecutor:
    def __init__(self, session:HyperliquidTestnetSession, max_notional:float=100.0, log_path:str|Path="data/runtime/testnet_execution/manual_orders.jsonl",):
        if session.base_url!=TESTNET_API_URL:
            raise RuntimeError("testnet executor cannot use a non-testnet URL")
        if max_notional<10:
            raise ValueError("max_notional must be at least $10")
        self.session=session
        self.max_notional=float(max_notional)
        self.log_path=Path(log_path)

    @staticmethod
    def _check_slippage(bps):
        if not 0<bps<=50:
            raise ValueError("slippage_bps must be in (0, 50]")

    def _sz_decimals(self,coin):
        coin=coin.upper()
        market=next(
            (x for x in self.session.info.meta()["universe"] if x["name"]==coin),
            None,
        )
        if market is None:
            raise ValueError(f"unknown perp: {coin}")
        return int(market["szDecimals"])

    def preview_long(self,coin,notional,slippage_bps=15.0):
        coin=coin.upper()
        if notional<10:
            raise ValueError("Hyperliquid minimum order value is $10")
        if notional>self.max_notional:
            raise ValueError(
                f"notional ${notional:g} exceeds hard cap ${self.max_notional:g}"
            )
        self._check_slippage(slippage_bps)
        sz_decimals=self._sz_decimals(coin)
        mids=self.session.info.all_mids()
        if coin not in mids:
            raise ValueError(f"no mid price for {coin}")
        mid=float(mids[coin])
        step=Decimal(1).scaleb(-sz_decimals)
        quantity=(Decimal(str(notional))/Decimal(str(mid))).quantize(
            step,rounding=ROUND_DOWN
        )
        estimated=float(quantity)*mid
        if estimated<10:
            raise ValueError(
                f"rounded order value ${estimated:.4f} is below $10 minimum"
            )
        return MarketOpenPreview(
            coin,"BUY",float(notional),mid,float(quantity),estimated,
            sz_decimals,float(slippage_bps),
        )

    def preview_long_risk(
        self,
        coin,
        risk_dollars,
        stop_price,
        reference_entry_price,
        slippage_bps=15.0,
    ):
        coin=coin.upper()
        risk_dollars=float(risk_dollars)
        stop=float(stop_price)
        entry=float(reference_entry_price)

        if risk_dollars<=0:
            raise ValueError("risk_dollars must be positive")
        if stop<=0 or entry<=0:
            raise ValueError("entry and stop must be positive")
        if entry<=stop:
            raise ValueError("entry must be above stop for long risk sizing")

        self._check_slippage(slippage_bps)
        sz_decimals=self._sz_decimals(coin)
        risk_per_unit=entry-stop
        step=Decimal(1).scaleb(-sz_decimals)

        quantity=(
            Decimal(str(risk_dollars))
            / Decimal(str(risk_per_unit))
        ).quantize(step,rounding=ROUND_DOWN)

        if quantity<=0:
            raise ValueError("risk-sized quantity rounds to zero")

        quantity=float(quantity)
        notional=quantity*entry
        stop_risk=quantity*risk_per_unit

        if notional<10:
            raise ValueError(
                f"risk-sized notional ${notional:.4f} is below $10 minimum"
            )
        if notional>self.max_notional:
            raise ValueError(
                f"risk-sized notional ${notional:.4f} exceeds "
                f"${self.max_notional:g} hard cap"
            )

        return RiskSizedOpenPreview(
            coin=coin,
            side="BUY",
            risk_dollars=risk_dollars,
            stop_price=stop,
            reference_entry_price=entry,
            risk_per_unit=risk_per_unit,
            quantity=quantity,
            estimated_notional=notional,
            planned_stop_risk=stop_risk,
            sz_decimals=sz_decimals,
            slippage_bps=float(slippage_bps),
        )

    def open_long(self,coin,notional,slippage_bps=15.0,*,confirm):
        if confirm!="EXECUTE TESTNET":
            raise RuntimeError(
                'order blocked: confirm must equal "EXECUTE TESTNET"'
            )
        p=self.preview_long(coin,notional,slippage_bps)
        response=self.session._exchange.market_open(
            name=p.coin,is_buy=True,sz=p.quantity,px=p.mid,
            slippage=p.slippage_bps/10_000,
        )
        self._log({
            "event":"TESTNET_MARKET_OPEN_LONG",
            "submit_ts_ms":int(time.time()*1000),
            "account":self.session.account_address,
            "signer":self.session.signer_address,
            **asdict(p),"response":response,
        })
        return response

    def open_long_risk(
        self,
        coin,
        risk_dollars,
        stop_price,
        reference_entry_price,
        slippage_bps=15.0,
        *,
        confirm,
    ):
        if confirm!="EXECUTE TESTNET":
            raise RuntimeError(
                'order blocked: confirm must equal "EXECUTE TESTNET"'
            )

        p=self.preview_long_risk(
            coin,risk_dollars,stop_price,
            reference_entry_price,slippage_bps,
        )

        self.session._exchange.update_leverage(
            leverage=1,
            name=p.coin,
            is_cross=True,
        )

        response=self.session._exchange.market_open(
            name=p.coin,
            is_buy=True,
            sz=p.quantity,
            px=p.reference_entry_price,
            slippage=p.slippage_bps/10_000,
        )

        self._log({
            "event":"TESTNET_RISK_SIZED_OPEN_LONG",
            "submit_ts_ms":int(time.time()*1000),
            "account":self.session.account_address,
            "signer":self.session.signer_address,
            **asdict(p),
            "response":response,
        })

        return p,response

    def preview_close_long(self,coin,slippage_bps=15.0):
        coin=coin.upper()
        self._check_slippage(slippage_bps)
        state=self.session.info.user_state(self.session.account_address)
        position=next(
            (
                x["position"] for x in state.get("assetPositions",())
                if x["position"]["coin"]==coin
            ),
            None,
        )
        if position is None:
            raise ValueError(f"no open {coin} position")
        quantity=float(position["szi"])
        if quantity<=0:
            raise ValueError(f"{coin} position is not long")
        mids=self.session.info.all_mids()
        mid=float(mids[coin])
        return MarketClosePreview(
            coin,"SELL",mid,quantity,quantity*mid,
            float(position["entryPx"]),float(slippage_bps),
        )

    def close_long(self,coin,slippage_bps=15.0,*,confirm):
        if confirm!="CLOSE TESTNET":
            raise RuntimeError(
                'close blocked: confirm must equal "CLOSE TESTNET"'
            )
        p=self.preview_close_long(coin,slippage_bps)
        response=self.session._exchange.market_close(
            coin=p.coin,
            sz=p.quantity,
            px=p.mid,
            slippage=p.slippage_bps/10_000,
        )
        self._log({
            "event":"TESTNET_MARKET_CLOSE_LONG",
            "submit_ts_ms":int(time.time()*1000),
            "account":self.session.account_address,
            "signer":self.session.signer_address,
            **asdict(p),"response":response,
        })
        return response

    def _log(self,row):
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(row,separators=(",",":"),default=str)+"\n")
