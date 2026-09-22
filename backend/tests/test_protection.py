from decimal import Decimal

from app.db.models import PositionRecord
from app.positions.protection import evaluate

COMMON = dict(
    break_even_trigger_r=Decimal("1.0"),
    trailing_start_r=Decimal("1.5"),
    trailing_atr_multiplier=Decimal("1.0"),
)


def _position(**overrides) -> PositionRecord:
    base = dict(
        symbol="BTCUSDT", status="OPEN",
        quantity="1", average_entry="100", cost_basis="100", fees_total="0",
        initial_stop_price="98", stop_price="98", take_profit="106",
        break_even_active=False, highest_price_since_entry="100",
    )
    base.update(overrides)
    return PositionRecord(**base)


def test_stop_hit_has_highest_priority():
    position = _position()
    result = evaluate(position, current_price=Decimal("97"), atr_5m=Decimal("1"), strategic_exit_signal=True, **COMMON)
    assert result.exit_action == "STOP"


def test_take_profit_hit():
    position = _position()
    result = evaluate(position, current_price=Decimal("107"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    assert result.exit_action == "TAKE_PROFIT"


def test_no_action_when_price_between_stop_and_breakeven_trigger():
    position = _position()
    # R=2 (100-98); breakeven triggers at entry+1*R=102
    result = evaluate(position, current_price=Decimal("101"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    assert result.exit_action is None
    assert result.new_stop_price is None


def test_break_even_moves_stop_up_accounting_for_fees():
    position = _position(fees_total="0.5")  # fees_per_unit = 0.5 (qty=1)
    # R=2; trigger at entry+1*R=102
    result = evaluate(position, current_price=Decimal("102"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    assert result.exit_action is None
    assert result.break_even_active is True
    assert result.new_stop_price == Decimal("100.5")  # entry + fees_per_unit, never below current stop


def test_break_even_never_moves_stop_down():
    # current stop already above the computed break-even candidate
    position = _position(stop_price="101", fees_total="0.1")
    result = evaluate(position, current_price=Decimal("102"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    assert result.new_stop_price is None or Decimal(str(result.new_stop_price)) >= Decimal("101")


def test_trailing_stop_only_rises_with_price():
    position = _position(highest_price_since_entry="100")
    # R=2; trailing starts at entry+1.5*R=103
    result = evaluate(position, current_price=Decimal("105"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    assert result.exit_action is None
    assert result.new_stop_price == Decimal("104")  # highest(105) - atr(1)
    assert result.highest_price_since_entry == Decimal("105")


def test_trailing_stop_never_exceeds_current_price_drop():
    # simulate a position already trailing at 104; a small pullback must not lower the stop
    position = _position(stop_price="104", highest_price_since_entry="105")
    result = evaluate(position, current_price=Decimal("104.5"), atr_5m=Decimal("1"), strategic_exit_signal=False, **COMMON)
    # trailing candidate = highest(105) - atr(1) = 104, equal to current stop -> no change, no exit
    assert result.exit_action is None


def test_strategic_exit_only_fires_when_no_stop_take_or_trailing_update_pending():
    position = _position()
    # price between stop/take and below breakeven/trailing triggers
    result = evaluate(position, current_price=Decimal("101"), atr_5m=Decimal("1"), strategic_exit_signal=True, **COMMON)
    assert result.exit_action == "STRATEGY_EXIT"


def test_strategic_exit_does_not_override_pending_trailing_update():
    position = _position(highest_price_since_entry="100")
    result = evaluate(position, current_price=Decimal("105"), atr_5m=Decimal("1"), strategic_exit_signal=True, **COMMON)
    # trailing stop update takes priority over strategy exit (#34)
    assert result.exit_action is None
    assert result.new_stop_price == Decimal("104")
