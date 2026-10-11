import pytest

from hlbot.backtest.execution_policy import ExecutionMode, ExecutionPolicy

def test_default_policy_is_taker_only():
    policy = ExecutionPolicy()

    assert policy.entry_mode == ExecutionMode.TAKER
    assert policy.scale_in_mode == ExecutionMode.TAKER
    assert policy.exit_mode == ExecutionMode.TAKER

def test_taker_only_factory():
    policy = ExecutionPolicy.taker_only()

    assert policy.entry_mode == ExecutionMode.TAKER
    assert policy.scale_in_mode == ExecutionMode.TAKER
    assert policy.exit_mode == ExecutionMode.TAKER

def test_maker_entries_factory():
    policy = ExecutionPolicy.maker_entries(max_age_seconds=5, queue_ahead_fraction=0.5)

    assert policy.entry_mode == ExecutionMode.MAKER
    assert policy.scale_in_mode == ExecutionMode.MAKER
    assert policy.exit_mode == ExecutionMode.TAKER
    assert policy.maker_max_age_seconds == pytest.approx(5)
    assert policy.maker_queue_ahead_fraction == pytest.approx(0.5)

def test_maker_only_factory():
    policy = ExecutionPolicy.maker_only()

    assert policy.entry_mode == ExecutionMode.MAKER
    assert policy.scale_in_mode == ExecutionMode.MAKER
    assert policy.exit_mode == ExecutionMode.MAKER

def test_invalid_maker_age_is_rejected():
    with pytest.raises(ValueError):
        ExecutionPolicy(maker_max_age_seconds=0)

def test_invalid_queue_fraction_is_rejected():
    with pytest.raises(ValueError):
        ExecutionPolicy(maker_queue_ahead_fraction=-1)

def test_maker_policy_supports_replacements():
    policy = ExecutionPolicy.maker_entries(max_age_seconds=5, queue_ahead_fraction=1, max_replacements=3)

    assert policy.maker_max_replacements == 3

def test_invalid_replacement_count_is_rejected():
    with pytest.raises(ValueError):
        ExecutionPolicy(maker_max_replacements=-1)