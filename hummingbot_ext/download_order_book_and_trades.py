import json
import os
import time
from datetime import datetime
from typing import Dict

from pydantic import Field

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


COLLECTOR_VERSION = "0.2.0"


class DownloadTradesAndOrderBookSnapshotsConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)

    exchange: str = Field(default="hyperliquid_perpetual")
    trading_pairs: list = Field(default=["PONS-USD"])

    def update_markets(self, markets: MarketDict) -> MarketDict:
        trading_pairs_set = set(self.trading_pairs)
        markets[self.exchange] = (
            markets.get(self.exchange, set()) | trading_pairs_set
        )
        return markets


class DownloadTradesAndOrderBookSnapshots(StrategyV2Base):
    depth = int(os.getenv("DEPTH", 20))

    last_dump_timestamp = 0
    time_between_csv_dumps = 10

    current_date = None

    ob_file_paths = {}
    trades_file_paths = {}

    subscribed_to_order_book_trade_event: bool = False

    def __init__(
        self,
        connectors: Dict[str, ConnectorBase],
        config: DownloadTradesAndOrderBookSnapshotsConfig,
    ):
        super().__init__(connectors, config)

        self.config = config

        self.ob_temp_storage = {
            trading_pair: []
            for trading_pair in config.trading_pairs
        }

        self.trades_temp_storage = {
            trading_pair: []
            for trading_pair in config.trading_pairs
        }

        self.last_order_book_uid = {
            trading_pair: None
            for trading_pair in config.trading_pairs
        }

        self.create_order_book_and_trade_files()

        self.order_book_trade_event = SourceInfoEventForwarder(
            self._process_public_trade
        )

    def on_tick(self):
        if not self.subscribed_to_order_book_trade_event:
            self.subscribe_to_order_book_trade_event()

        self.check_and_replace_files()

        for trading_pair in self.config.trading_pairs:
            order_book = self.connectors[
                self.config.exchange
            ].get_order_book(trading_pair)

            uid = order_book.snapshot_uid

            # Do not save the same stale snapshot repeatedly.
            if uid != self.last_order_book_uid[trading_pair]:
                order_book_data = self.get_order_book_dict(
                    self.config.exchange,
                    trading_pair,
                    self.depth,
                )

                self.ob_temp_storage[trading_pair].append(
                    order_book_data
                )

                self.last_order_book_uid[trading_pair] = uid

        if self.last_dump_timestamp < self.current_timestamp:
            self.dump_and_clean_temp_storage()

    def get_order_book_dict(
        self,
        exchange: str,
        trading_pair: str,
        depth: int = 20,
    ):
        order_book = self.connectors[
            exchange
        ].get_order_book(trading_pair)

        snapshot = order_book.snapshot

        local_ts = time.time()
        update_id = order_book.snapshot_uid

        # Hyperliquid snapshot_uid is based on exchange timestamp in ms.
        exchange_ts = (
            update_id / 1000.0
            if update_id is not None
            else None
        )

        return {
            "collector_version": COLLECTOR_VERSION,
            "exchange": exchange,
            "trading_pair": trading_pair,

            "local_ts": local_ts,
            "exchange_ts": exchange_ts,

            # Kept for backward compatibility with previous files.
            "ts": local_ts,

            "update_id": update_id,

            "bids": snapshot[0]
            .loc[: (depth - 1), ["price", "amount"]]
            .values
            .tolist(),

            "asks": snapshot[1]
            .loc[: (depth - 1), ["price", "amount"]]
            .values
            .tolist(),
        }

    def _process_public_trade(
        self,
        event_tag: int,
        market: ConnectorBase,
        event: OrderBookTradeEvent,
    ):
        local_ts = time.time()

        self.trades_temp_storage[event.trading_pair].append(
            {
                "collector_version": COLLECTOR_VERSION,
                "exchange": self.config.exchange,
                "trading_pair": event.trading_pair,

                "local_ts": local_ts,

                # Hyperliquid trade timestamp received through Hummingbot.
                "exchange_ts": event.timestamp,

                # Kept for backward compatibility.
                "ts": event.timestamp,

                "price": event.price,
                "q_base": event.amount,
                "side": event.type.name.lower(),

                "trade_id": event.trade_id,
            }
        )

    def dump_and_clean_temp_storage(self):
        for trading_pair, order_book_info in self.ob_temp_storage.items():
            if order_book_info:
                file = self.ob_file_paths[trading_pair]

                for obj in order_book_info:
                    file.write(json.dumps(obj) + "\n")

                file.flush()

                self.ob_temp_storage[trading_pair] = []

        for trading_pair, trades_info in self.trades_temp_storage.items():
            if trades_info:
                file = self.trades_file_paths[trading_pair]

                for obj in trades_info:
                    file.write(json.dumps(obj) + "\n")

                file.flush()

                self.trades_temp_storage[trading_pair] = []

        self.last_dump_timestamp = (
            self.current_timestamp
            + self.time_between_csv_dumps
        )

    def check_and_replace_files(self):
        current_date = datetime.now().strftime("%Y-%m-%d")

        if current_date != self.current_date:
            for file in self.ob_file_paths.values():
                file.close()

            for file in self.trades_file_paths.values():
                file.close()

            self.create_order_book_and_trade_files()

    def create_order_book_and_trade_files(self):
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        self.ob_file_paths = {
            trading_pair: self.get_file(
                self.config.exchange,
                trading_pair,
                "order_book_snapshots",
                self.current_date,
            )
            for trading_pair in self.config.trading_pairs
        }

        self.trades_file_paths = {
            trading_pair: self.get_file(
                self.config.exchange,
                trading_pair,
                "trades",
                self.current_date,
            )
            for trading_pair in self.config.trading_pairs
        }

    @staticmethod
    def get_file(
        exchange: str,
        trading_pair: str,
        source_type: str,
        current_date: str,
    ):
        file_path = (
            data_path()
            + f"/{exchange}_{trading_pair}_{source_type}_{current_date}.txt"
        )

        return open(file_path, "a")

    def subscribe_to_order_book_trade_event(self):
        for market in self.connectors.values():
            for order_book in market.order_books.values():
                order_book.add_listener(
                    OrderBookEvent.TradeEvent,
                    self.order_book_trade_event,
                )

        self.subscribed_to_order_book_trade_event = True