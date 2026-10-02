from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.payment import PaymentCreate


def test_payment_create_valid():
    item = PaymentCreate(amount="100.50", currency="RUB", webhook_url="https://example.com/hook")
    assert item.amount == Decimal("100.50")
    assert item.currency.value == "RUB"


def test_payment_amount_must_be_positive():
    with pytest.raises(ValidationError):
        PaymentCreate(amount="0", currency="USD", webhook_url="https://example.com/hook")
