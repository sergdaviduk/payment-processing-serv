import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Outbox
from app.workers.broker import PAYMENTS_QUEUE, broker


async def publish_batch() -> int:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Outbox)
                .where(Outbox.status == "pending")
                .order_by(Outbox.created_at)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        ).all()
        published = 0
        for row in rows:
            try:
                await broker.publish(
                    row.payload,
                    queue=PAYMENTS_QUEUE,
                    persist=True,
                    message_id=str(row.id),
                )
                row.status = "published"
                row.published_at = datetime.now(timezone.utc)
                published += 1
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)
        await session.commit()
        return published


async def run_outbox() -> None:
    async with broker:
        while True:
            await publish_batch()
            await asyncio.sleep(settings.outbox_poll_interval)


if __name__ == "__main__":
    asyncio.run(run_outbox())
