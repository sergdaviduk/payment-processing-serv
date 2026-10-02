import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_session
from app.schemas.payment import PaymentCreate, PaymentCreated, PaymentRead
from app.services.payments import create_payment, get_payment

router = APIRouter(prefix="/api/v1/payments", tags=["payments"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=PaymentCreated, status_code=status.HTTP_202_ACCEPTED)
async def post_payment(
    body: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    session: AsyncSession = Depends(get_session),
):
    payment = await create_payment(session, body, idempotency_key)
    return PaymentCreated(payment_id=payment.id, status=payment.status, created_at=payment.created_at)


@router.get("/{payment_id}", response_model=PaymentRead)
async def read_payment(payment_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    payment = await get_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentRead(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata_,
        status=payment.status,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
