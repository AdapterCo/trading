from app.alerts.service import AlertService


def test_send_without_webhook_never_raises():
    service = AlertService(webhook_url=None)
    service.send("BOT_PAUSED", "test message")  # must not raise


def test_send_unknown_event_type_still_does_not_raise():
    service = AlertService(webhook_url=None)
    service.send("SOMETHING_NOT_IN_THE_SPEC", "test message")


def test_webhook_failure_never_propagates(monkeypatch):
    service = AlertService(webhook_url="http://example.invalid/webhook")

    def boom(*args, **kwargs):
        raise ConnectionError("network is down")

    monkeypatch.setattr("httpx.post", boom)
    service.send("EMERGENCY", "should not raise even though the webhook is broken")  # must not raise


def test_webhook_called_with_event_payload(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))

    monkeypatch.setattr("httpx.post", fake_post)
    service = AlertService(webhook_url="http://example.invalid/webhook")
    service.send("DRAWDOWN_LIMIT", "drawdown hit", context={"symbol": "BTCUSDT"})

    assert len(calls) == 1
    url, payload, _ = calls[0]
    assert url == "http://example.invalid/webhook"
    assert payload["event_type"] == "DRAWDOWN_LIMIT"
    assert payload["context"]["symbol"] == "BTCUSDT"
