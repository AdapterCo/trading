"""Bearer-token auth for critical control endpoints (instrucao.md #64, #93).

Fails closed: if CONTROL_API_TOKEN isn't configured, control endpoints refuse to
run at all rather than silently accepting unauthenticated requests.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def require_control_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.control_api_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="CONTROL_API_TOKEN not configured")
    if credentials is None or credentials.credentials != settings.control_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing control token")
