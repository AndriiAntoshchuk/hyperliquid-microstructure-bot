import pytest

from hlbot.execution.perpetual_config import MarginMode, PerpetualExecutionConfig, PerpetualMarketConfig

def test_market_config():
    config = PerpetualMarketConfig("PONS", 5)
    assert config.coin == "PONS"
    assert config.leverage == 5
    assert config.margin_mode == MarginMode.AUTO

def test_explicit_margin_mode():
    config = PerpetualMarketConfig("PONS", 3, MarginMode.CROSS)
    assert config.margin_mode == MarginMode.CROSS

def test_invalid_leverage():
    with pytest.raises(ValueError):
        PerpetualMarketConfig("PONS", 0)

def test_boolean_leverage_is_invalid():
    with pytest.raises(ValueError):
        PerpetualMarketConfig("PONS", True)

def test_empty_coin():
    with pytest.raises(ValueError):
        PerpetualMarketConfig("", 5)

def test_execution_config_lookup():
    config = PerpetualExecutionConfig((
        PerpetualMarketConfig("PONS", 5),
        PerpetualMarketConfig("LIT", 3)
    ))

    assert config.market("LIT").leverage == 3

def test_duplicate_market_is_rejected():
    with pytest.raises(ValueError):
        PerpetualExecutionConfig((
            PerpetualMarketConfig("PONS", 5),
            PerpetualMarketConfig("PONS", 3)
        ))

def test_unknown_market():
    config = PerpetualExecutionConfig((PerpetualMarketConfig("PONS", 5),))

    with pytest.raises(KeyError):
        config.market("LIT")