import dataclasses
from decimal import Decimal

from app.core.config import Settings
from app.exchange.types import AccountBalance, AccountInfo, BestBidAsk, SymbolRules
from app.risk.engine import RiskEngine
from app.risk.types import RiskState

SETTINGS = Settings(_env_file=None)
ENGINE = RiskEngine(SETTINGS)


def _symbol_rules(**overrides) -> SymbolRules:
    base = dict(
        symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
        tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
        min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
        min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
    )
    base.update(overrides)
    return SymbolRules(**base)


def _account(**overrides) -> AccountInfo:
    base = dict(
        can_trade=True, can_withdraw=False, can_deposit=True, update_time=1,
        balances=[AccountBalance(asset="USDT", free=Decimal("1000"), locked=Decimal("0"))],
    )
    base.update(overrides)
    return AccountInfo(**base)


def _quote(**overrides) -> BestBidAsk:
    base = dict(
        symbol="BTCUSDT", bid_price=Decimal("100.00"), bid_qty=Decimal("1"),
        ask_price=Decimal("100.02"), ask_qty=Decimal("1"),
    )
    base.update(overrides)
    return BestBidAsk(**base)


def _state(**overrides) -> RiskState:
    base = dict(
        equity=Decimal("1000"),
        high_water_mark=Decimal("1000"),
        daily_reference_equity=Decimal("1000"),
        open_positions_count=0,
        consecutive_losses=0,
        orders_sent_last_hour=0,
        entries_sent_today=0,
        candles_since_last_close=None,
        market_data_healthy=True,
        exchange_healthy=True,
        reconciled=True,
        has_conflicting_order=False,
    )
    base.update(overrides)
    return RiskState(**base)


def _evaluate(**state_overrides):
    return ENGINE.evaluate_buy(
        entry_price=Decimal("100"),
        atr_5m=Decimal("1"),  # 1.5% stop distance with default STOP_ATR_MULTIPLIER=1.5
        symbol_rules=_symbol_rules(),
        account=_account(),
        quote=_quote(),
        state=_state(**state_overrides),
    )


def test_healthy_state_is_approved_with_sizing():
    decision = _evaluate()
    assert decision.approved is True
    assert decision.reasons == []
    assert decision.stop_price == Decimal("98.5")
    assert decision.take_profit == Decimal("103")  # R=1.5, entry+2*1.5
    assert decision.quantity is not None and decision.quantity > 0


def test_rejects_when_max_open_positions_reached():
    decision = _evaluate(open_positions_count=1)
    assert decision.approved is False
    assert "MAX_OPEN_POSITIONS_REACHED" in decision.reasons


def test_rejects_when_cooldown_active():
    decision = _evaluate(candles_since_last_close=0)
    assert decision.approved is False
    assert "COOLDOWN_ACTIVE" in decision.reasons


def test_cooldown_satisfied_after_enough_candles():
    decision = _evaluate(candles_since_last_close=SETTINGS.cooldown_candles)
    assert decision.approved is True


def test_rejects_when_consecutive_losses_reach_limit():
    decision = _evaluate(consecutive_losses=SETTINGS.max_consecutive_losses)
    assert decision.approved is False
    assert "CONSECUTIVE_LOSS_LIMIT_REACHED" in decision.reasons


def test_rejects_when_daily_loss_limit_reached():
    decision = _evaluate(equity=Decimal("960"), daily_reference_equity=Decimal("1000"))  # -4% > 3% limit
    assert decision.approved is False
    assert "DAILY_LOSS_LIMIT_REACHED" in decision.reasons


def test_rejects_when_drawdown_limit_reached():
    decision = _evaluate(equity=Decimal("880"), high_water_mark=Decimal("1000"))  # -12% > 10% limit
    assert decision.approved is False
    assert "DRAWDOWN_LIMIT_REACHED" in decision.reasons


def test_rejects_when_market_data_unhealthy():
    decision = _evaluate(market_data_healthy=False)
    assert decision.approved is False
    assert "MARKET_DATA_NOT_HEALTHY" in decision.reasons


def test_rejects_when_not_reconciled():
    decision = _evaluate(reconciled=False)
    assert decision.approved is False
    assert "ACCOUNT_NOT_RECONCILED" in decision.reasons


def test_rejects_when_orders_per_hour_limit_reached():
    decision = _evaluate(orders_sent_last_hour=SETTINGS.max_orders_per_hour)
    assert decision.approved is False
    assert "MAX_ORDERS_PER_HOUR_REACHED" in decision.reasons


def test_rejects_on_wide_spread():
    decision = ENGINE.evaluate_buy(
        entry_price=Decimal("100"),
        atr_5m=Decimal("1"),
        symbol_rules=_symbol_rules(),
        account=_account(),
        quote=_quote(bid_price=Decimal("100"), ask_price=Decimal("105")),  # ~5% spread >> 0.1% limit
        state=_state(),
    )
    assert decision.approved is False
    assert "SPREAD_TOO_WIDE" in decision.reasons


def test_rejects_when_stop_exceeds_max_stop_percent():
    decision = ENGINE.evaluate_buy(
        entry_price=Decimal("100"),
        atr_5m=Decimal("5"),  # 7.5% stop distance >> 2% MAX_STOP_PERCENT
        symbol_rules=_symbol_rules(),
        account=_account(),
        quote=_quote(),
        state=_state(),
    )
    assert decision.approved is False
    assert "STOP_EXCEEDS_MAX_STOP_PERCENT" in decision.reasons


def test_account_cannot_trade_is_rejected():
    decision = ENGINE.evaluate_buy(
        entry_price=Decimal("100"),
        atr_5m=Decimal("1"),
        symbol_rules=_symbol_rules(),
        account=_account(can_trade=False),
        quote=_quote(),
        state=_state(),
    )
    assert decision.approved is False
    assert "ACCOUNT_CANNOT_TRADE" in decision.reasons
