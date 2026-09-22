from decimal import getcontext

from app.core.config import Settings, TradingMode


def test_default_trading_mode_is_never_live():
    settings = Settings(_env_file=None)
    assert settings.trading_mode == TradingMode.PAPER
    assert settings.is_live is False


def test_decimal_precision_configured():
    assert getcontext().prec == 28


def test_default_symbol_matches_spec():
    settings = Settings(_env_file=None)
    assert settings.symbol == "BTCUSDT"
    assert settings.base_asset == "BTC"
    assert settings.quote_asset == "USDT"


def test_live_mode_requires_explicit_env_value():
    settings = Settings(_env_file=None, trading_mode="live")
    assert settings.is_live is True
