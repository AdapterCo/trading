from decimal import Decimal

import pytest

from app.research.monte_carlo import MonteCarloEngine


def test_run_rejects_empty_trade_returns():
    engine = MonteCarloEngine(seed=1)
    with pytest.raises(ValueError):
        engine.run([], initial_equity=Decimal("1000"))


def test_all_positive_returns_never_shows_ruin():
    engine = MonteCarloEngine(seed=42)
    returns = [Decimal("10")] * 20
    result = engine.run(returns, initial_equity=Decimal("1000"), n_simulations=200)
    assert result.probability_of_ruin == 0.0
    assert result.final_equity_percentiles[50] > 1000


def test_percentiles_are_ordered():
    engine = MonteCarloEngine(seed=7)
    returns = [Decimal("10"), Decimal("-8"), Decimal("15"), Decimal("-5"), Decimal("3")]
    result = engine.run(returns, initial_equity=Decimal("1000"), n_simulations=500)
    p = result.final_equity_percentiles
    assert p[5] <= p[25] <= p[50] <= p[75] <= p[95]


def test_deterministic_with_fixed_seed():
    returns = [Decimal("10"), Decimal("-8"), Decimal("15")]
    a = MonteCarloEngine(seed=123).run(returns, initial_equity=Decimal("1000"), n_simulations=100)
    b = MonteCarloEngine(seed=123).run(returns, initial_equity=Decimal("1000"), n_simulations=100)
    assert a.final_equity_percentiles == b.final_equity_percentiles
