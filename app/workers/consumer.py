import asyncio
import random
import uuid
from datetime import datetime, timezone

import httpx
from faststream import FastStream
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Payment, PaymentStatus
from app.workers.broker import DLQ, DLX, DLQ_PUBLISHER, PAYMENTS_QUEUE, broker

app = FastStream(broker)
MAX_WEBHOOK_ATTEMPTS = 3

@broker.subscriber(DLQ, exchange=DLX)
async def dlq_sink(message: dict) -> None:
    pass

async def send_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def send_webhook_with_retry(url: str, payload: dict) -> None:
    """Three total attempts with exponential backoff: 1s, 2s."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_WEBHOOK_ATTEMPTS + 1):
        try:
            await send_webhook(url, payload)
            return
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < MAX_WEBHOOK_ATTEMPTS:
                await asyncio.sleep(2 ** (attempt - 1))
    assert last_error is not None
    raise last_error


@broker.subscriber(PAYMENTS_QUEUE)
async def process_payment(message: dict) -> None:
    payment_id = uuid.UUID(message["payment_id"])

    async with SessionLocal() as session:
        payment = await session.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        # Duplicate broker delivery is harmless: only pending payments are processed.
        if payment is None or payment.status != PaymentStatus.PENDING:
            return

        await asyncio.sleep(random.uniform(2, 5))
        payment.status = (
            PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED
        )
        payment.processed_at = datetime.now(timezone.utc)
        webhook_url = payment.webhook_url
        webhook_payload = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "processed_at": payment.processed_at.isoformat(),
        }
        await session.commit()

    try:
        await send_webhook_with_retry(webhook_url, webhook_payload)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        # Business processing is already complete. A failed notification is preserved
        # in RabbitMQ DLQ for inspection/replay after three delivery attempts.
        await DLQ_PUBLISHER.publish(
            {
                **webhook_payload,
                "webhook_url": webhook_url,
                "attempts": MAX_WEBHOOK_ATTEMPTS,
                "error": str(exc),
            },
        )
