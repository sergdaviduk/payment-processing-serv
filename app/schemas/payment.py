import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.payment import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str | None = Field(default=None, max_length=500)
    metadata: dict = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentCreated(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str | None
    metadata: dict
    status: PaymentStatus
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
