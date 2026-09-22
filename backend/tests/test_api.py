from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db import models  # noqa: F401 — registers all tables
from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    settings = Settings(_env_file=None, control_api_token="test-token")
    app.dependency_overrides[__import__("app.core.config", fromlist=["get_settings"]).get_settings] = lambda: settings

    monkeypatch.setattr("app.api.routes._worker", lambda s: _FakeWorker())

    yield TestClient(app), session
    app.dependency_overrides.clear()


class _FakeWorker:
    def pause(self):
        return None

    def resume(self):
        return {"state": "READY", "manual_resume_required": False}

    def emergency_exit(self):
        return {"position_closed": False, "reconciled": True, "state": "EMERGENCY"}


def test_status_with_no_state_yet(client):
    test_client, _ = client
    response = test_client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["bot_state"]["state"] == "UNKNOWN"
    assert body["position"] is None


def test_control_endpoint_rejects_missing_token(client):
    test_client, _ = client
    response = test_client.post("/control/pause")
    assert response.status_code == 401


def test_control_endpoint_rejects_wrong_token(client):
    test_client, _ = client
    response = test_client.post("/control/pause", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_control_pause_succeeds_with_correct_token(client):
    test_client, _ = client
    response = test_client.post("/control/pause", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_control_resume_succeeds_with_correct_token(client):
    test_client, _ = client
    response = test_client.post("/control/resume", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["state"] == "READY"


def test_control_emergency_exit_succeeds_with_correct_token(client):
    test_client, _ = client
    response = test_client.post("/control/emergency_exit", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["state"] == "EMERGENCY"


def test_control_endpoint_unconfigured_token_returns_503():
    from app.core.config import get_settings

    settings = Settings(_env_file=None, control_api_token=None)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        test_client = TestClient(app)
        response = test_client.post("/control/pause", headers={"Authorization": "Bearer anything"})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
