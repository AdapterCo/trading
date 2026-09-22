"""MonteCarloEngine (instrucao.md #100). NumPy float64 explicitly permitted here (#6, #8) —
this is statistical research on already-realized trade results, not accounting.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np


@dataclass(frozen=True)
class MonteCarloResult:
    n_simulations: int
    final_equity_percentiles: dict[int, float]  # e.g. {5: ..., 50: ..., 95: ...}
    max_drawdown_percentiles: dict[int, float]
    probability_of_ruin: float  # fraction of paths that ever hit equity <= 0


class MonteCarloEngine:
    def __init__(self, *, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)

    def run(
        self,
        trade_returns: list[Decimal],
        *,
        initial_equity: Decimal,
        n_simulations: int = 1000,
        percentiles: tuple[int, ...] = (5, 25, 50, 75, 95),
    ) -> MonteCarloResult:
        """instrucao.md #100 — bootstrap resampling of REAL trade returns (with
        replacement), reshuffling their order, to see the range of outcomes the
        same edge could have produced under a different sequence of luck.

        Never fabricates a return that didn't actually happen — only resamples
        from the empirical distribution of realized trades.
        """
        if not trade_returns:
            raise ValueError("cannot run Monte Carlo with zero trades")

        returns = np.array([float(r) for r in trade_returns], dtype=np.float64)
        n_trades = len(returns)
        start_equity = float(initial_equity)

        final_equities = np.empty(n_simulations, dtype=np.float64)
        max_drawdowns = np.empty(n_simulations, dtype=np.float64)
        ruined = np.zeros(n_simulations, dtype=bool)

        for i in range(n_simulations):
            sampled = self._rng.choice(returns, size=n_trades, replace=True)
            equity_curve = start_equity + np.cumsum(sampled)
            running_peak = np.maximum.accumulate(np.concatenate(([start_equity], equity_curve)))[1:]
            drawdowns = running_peak - equity_curve

            final_equities[i] = equity_curve[-1]
            max_drawdowns[i] = drawdowns.max() if len(drawdowns) else 0.0
            ruined[i] = bool(np.any(equity_curve <= 0))

        final_pct = {p: float(np.percentile(final_equities, p)) for p in percentiles}
        dd_pct = {p: float(np.percentile(max_drawdowns, p)) for p in percentiles}
        probability_of_ruin = float(ruined.mean())

        return MonteCarloResult(
            n_simulations=n_simulations,
            final_equity_percentiles=final_pct,
            max_drawdown_percentiles=dd_pct,
            probability_of_ruin=probability_of_ruin,
        )
