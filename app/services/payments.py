import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Outbox, Payment
from app.schemas.payment import PaymentCreate


async def get_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.idempotency_key == key))


async def create_payment(session: AsyncSession, data: PaymentCreate, key: str) -> Payment:
    existing = await get_by_idempotency_key(session, key)
    if existing:
        return existing

    payment = Payment(
        amount=data.amount,
        currency=data.currency,
        description=data.description,
        metadata_=data.metadata,
        idempotency_key=key,
        webhook_url=str(data.webhook_url),
    )
    session.add(payment)
    await session.flush()
    session.add(Outbox(event_type="payment.created", payload={"payment_id": str(payment.id)}))

    try:
        # Payment and outbox event are committed atomically.
        await session.commit()
    except IntegrityError:
        # The unique DB constraint is the final protection against concurrent
        # requests carrying the same Idempotency-Key.
        await session.rollback()
        existing = await get_by_idempotency_key(session, key)
        if existing:
            return existing
        raise

    await session.refresh(payment)
    return payment


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    return await session.get(Payment, payment_id)
