class HummingbotExecutionEventListener:
    def __init__(self, connector, bridge, event_tags=None):
        self.connector = connector
        self.bridge = bridge
        self.event_tags = event_tags
        self._registrations = None

    @classmethod
    def from_connector(cls, connector, bridge):
        from importlib import import_module

        events = import_module("hummingbot.core.event.events")
        return cls(connector, bridge, events.MarketEvent)

    @property
    def started(self) -> bool:
        return self._registrations is not None

    def start(self) -> None:
        if self.started: return
        if self.event_tags is None:
            raise ValueError("event tags are not configured")

        registrations = (
            (self._tag("BuyOrderCreated"), self.bridge.on_order_created),
            (self._tag("SellOrderCreated"), self.bridge.on_order_created),
            (self._tag("OrderFailure"), self.bridge.on_order_failure),
            (self._tag("OrderCancelled"), self.bridge.on_order_cancelled),
            (self._tag("OrderFilled"), self.bridge.on_order_filled),
            (self._tag("BuyOrderCompleted"), self.bridge.on_order_completed),
            (self._tag("SellOrderCompleted"), self.bridge.on_order_completed)
        )

        added = []

        try:
            for tag, listener in registrations:
                self.connector.add_listener(tag, listener)
                added.append((tag, listener))
        except Exception:
            for tag, listener in reversed(added):
                self.connector.remove_listener(tag, listener)
            raise

        self._registrations = registrations

    def stop(self) -> None:
        if not self.started: return

        for tag, listener in reversed(self._registrations):
            self.connector.remove_listener(tag, listener)

        self._registrations = None

    def _tag(self, name: str):
        tag = getattr(self.event_tags, name)
        return getattr(tag, "value", tag)