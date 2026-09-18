from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.integration_models import WebhookDelivery
from app.webhook_delivery import _mark_failed_delivery


def _delivery(attempts: int) -> WebhookDelivery:
    return WebhookDelivery(
        webhook_id=uuid4(),
        activity_id=uuid4(),
        event="task.updated",
        status="pending",
        attempts=attempts,
    )


def test_failed_webhook_delivery_uses_exponential_backoff():
    now = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    delivery = _delivery(attempts=1)

    _mark_failed_delivery(delivery, "configuration_error:ValueError", now)

    assert delivery.status == "failed"
    assert delivery.last_error == "configuration_error:ValueError"
    assert delivery.next_attempt_at == now + timedelta(minutes=2)


def test_webhook_delivery_is_marked_exhausted_after_fifth_attempt():
    now = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    delivery = _delivery(attempts=5)

    _mark_failed_delivery(delivery, "network_error:ConnectError", now)

    assert delivery.status == "exhausted"
    assert delivery.last_error == "network_error:ConnectError"
    assert delivery.next_attempt_at is None


def test_webhook_failure_error_is_bounded_for_operational_visibility():
    now = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    delivery = _delivery(attempts=2)

    _mark_failed_delivery(delivery, "x" * 700, now)

    assert delivery.status == "failed"
    assert len(delivery.last_error or "") == 500
    assert delivery.next_attempt_at == now + timedelta(minutes=4)
