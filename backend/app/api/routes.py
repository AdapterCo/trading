"""API endpoints (instrucao.md #16, #88-#89). Query endpoints are open; control
endpoints require CONTROL_API_TOKEN (instrucao.md #93).

Control actions call ExecutionWorker's methods directly and synchronously — this
is administrative/rare, unlike the continuous trading loop, which instrucao.md #52
explicitly forbids running inside a FastAPI request.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_control_token
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import BotStateRecord, PositionRecord, SignalRecord
from app.exchange.binance_adapter import BinanceExchangeAdapter
from app.workers.execution_worker import ExecutionWorker

router = APIRouter()


@router.get("/status")
def get_status(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    bot_state = db.get(BotStateRecord, settings.symbol)
    position = (
        db.query(PositionRecord).filter_by(symbol=settings.symbol, status="OPEN").one_or_none()
    )
    last_signal = (
        db.query(SignalRecord)
        .filter_by(symbol=settings.symbol)
        .order_by(SignalRecord.created_at.desc())
        .first()
    )

    return {
        "trading_mode": settings.trading_mode.value,
        "symbol": settings.symbol,
        "bot_state": {
            "state": bot_state.state if bot_state else "UNKNOWN",
            "high_water_mark": str(bot_state.high_water_mark) if bot_state else None,
            "daily_reference_equity": str(bot_state.daily_reference_equity) if bot_state else None,
            "consecutive_losses": bot_state.consecutive_losses if bot_state else 0,
            "manual_resume_required": bot_state.manual_resume_required if bot_state else False,
            "block_reason": bot_state.block_reason if bot_state else None,
        },
        "position": (
            {
                "quantity": str(position.quantity),
                "average_entry": str(position.average_entry),
                "stop_price": str(position.stop_price),
                "take_profit": str(position.take_profit),
                "trailing_stop": str(position.trailing_stop) if position.trailing_stop else None,
            }
            if position
            else None
        ),
        "last_signal": (
            {
                "decision": last_signal.decision,
                "reasons": last_signal.reasons,
                "created_at": last_signal.created_at.isoformat(),
            }
            if last_signal
            else None
        ),
    }


def _worker(settings: Settings) -> ExecutionWorker:
    return ExecutionWorker(settings, exchange=BinanceExchangeAdapter(settings))


@router.post("/control/pause", dependencies=[Depends(require_control_token)])
def control_pause(settings: Settings = Depends(get_settings)) -> dict:
    _worker(settings).pause()
    return {"ok": True}


@router.post("/control/resume", dependencies=[Depends(require_control_token)])
def control_resume(settings: Settings = Depends(get_settings)) -> dict:
    return _worker(settings).resume()


@router.post("/control/emergency_exit", dependencies=[Depends(require_control_token)])
def control_emergency_exit(settings: Settings = Depends(get_settings)) -> dict:
    return _worker(settings).emergency_exit()
