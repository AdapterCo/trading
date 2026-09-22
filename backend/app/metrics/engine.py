"""MetricsEngine (instrucao.md #78). Computes performance stats from real trades/ledger only.

Never hides costs: fees and slippage are always included in realized_pnl already
(PositionRepository.close deducts them), so these aggregates are net, not gross-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import TradeRecord


@dataclass(frozen=True)
class MetricsSnapshot:
    trade_count: int
    gross_profit: Decimal
    gross_loss: Decimal
    net_profit: Decimal
    fees_total: Decimal
    win_rate: Decimal | None
    loss_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    payoff: Decimal | None
    max_drawdown: Decimal | None
    consecutive_wins: int
    consecutive_losses: int


class MetricsEngine:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compute(self, symbol: str) -> MetricsSnapshot:
        trades = (
            self._session.query(TradeRecord)
            .filter_by(symbol=symbol)
            .order_by(TradeRecord.closed_at)
            .all()
        )

        if not trades:
            return MetricsSnapshot(
                trade_count=0, gross_profit=Decimal("0"), gross_loss=Decimal("0"), net_profit=Decimal("0"),
                fees_total=Decimal("0"), win_rate=None, loss_rate=None, average_win=None, average_loss=None,
                expectancy=None, profit_factor=None, payoff=None, max_drawdown=None,
                consecutive_wins=0, consecutive_losses=0,
            )

        pnls = [Decimal(t.realized_pnl) for t in trades]
        fees = sum((Decimal(t.fees_total) for t in trades), Decimal("0"))

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        gross_profit = sum(wins, Decimal("0"))
        gross_loss = sum(losses, Decimal("0"))  # negative
        net_profit = gross_profit + gross_loss

        n = len(pnls)
        win_rate = Decimal(len(wins)) / n if n else None
        loss_rate = Decimal(len(losses)) / n if n else None
        average_win = gross_profit / len(wins) if wins else None
        average_loss = gross_loss / len(losses) if losses else None

        expectancy = net_profit / n if n else None
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None
        payoff = (average_win / abs(average_loss)) if average_win is not None and average_loss not in (None, Decimal("0")) else None

        max_dd = _max_drawdown_from_equity_curve(pnls)
        cur_wins, cur_losses = _current_streaks(pnls)

        return MetricsSnapshot(
            trade_count=n, gross_profit=gross_profit, gross_loss=gross_loss, net_profit=net_profit,
            fees_total=fees, win_rate=win_rate, loss_rate=loss_rate, average_win=average_win,
            average_loss=average_loss, expectancy=expectancy, profit_factor=profit_factor, payoff=payoff,
            max_drawdown=max_dd, consecutive_wins=cur_wins, consecutive_losses=cur_losses,
        )


def _max_drawdown_from_equity_curve(pnls: list[Decimal]) -> Decimal:
    """Drawdown of the cumulative-PnL curve built purely from closed trades —
    not the same as the live account drawdown (#39), which also reflects unrealized moves."""
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        max_dd = max(max_dd, drawdown)
    return max_dd


def _current_streaks(pnls: list[Decimal]) -> tuple[int, int]:
    """Returns (consecutive_wins, consecutive_losses) as of the most recent trade —
    only one of the two can be non-zero."""
    if not pnls:
        return 0, 0
    last_sign = pnls[-1] > 0
    streak = 0
    for pnl in reversed(pnls):
        if (pnl > 0) != last_sign:
            break
        streak += 1
    return (streak, 0) if last_sign else (0, streak)
