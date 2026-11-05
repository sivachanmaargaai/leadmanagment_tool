from datetime import date as Date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, Division, UpdateModel

Billing = Literal["One-time", "Monthly", "Yearly"]
QuoteStatus = Literal["Draft", "Sent", "Accepted", "Rejected", "Expired"]
Money = Annotated[Decimal, Field(ge=0, le=999999999, max_digits=12, decimal_places=2, allow_inf_nan=False)]


class QuotationItem(ApiModel):
    description: str = Field(min_length=1, max_length=1000)
    quantity: Decimal = Field(gt=0, le=999999, max_digits=12, decimal_places=4, allow_inf_nan=False)
    rate: Money
    billing: Billing = "One-time"


class QuotationDocument(ApiModel):
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    number: str = Field(default="", max_length=50, pattern=r"^(?:[A-Za-z0-9][A-Za-z0-9 ._/-]*)?$")
    customer: str = Field(min_length=1, max_length=120)
    division: Division
    contact: str = Field(default="", max_length=150)
    address: str = Field(default="", max_length=2000)
    date: Date
    valid_until: Date | None = Field(default=None, alias="validUntil")
    status: QuoteStatus = "Draft"
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    items: list[QuotationItem] = Field(default_factory=list, max_length=100)
    tax: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)
    terms: str = Field(default="", max_length=10000)
    amount: Money = Decimal("0")
    billing: Billing = "One-time"

    @model_validator(mode="after")
    def date_order(self):
        if self.valid_until and self.valid_until < self.date:
            raise ValueError("Valid-until must be on or after the quotation date")
        subtotals = {}
        for item in self.items:
            subtotals[item.billing] = subtotals.get(item.billing, Decimal("0")) + (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for subtotal in subtotals.values():
            total = subtotal + (subtotal * self.tax / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if total > Decimal("9999999999.99"):
                raise ValueError("Total for each billing period must not exceed 9,999,999,999.99")
        return self


class QuotationUpdate(UpdateModel):
    expected_version: int = Field(alias="expectedVersion", ge=1)
    status: QuoteStatus | None = None
    document: QuotationDocument | None = None

    @model_validator(mode="after")
    def one_operation(self):
        if (self.status is None) == (self.document is None):
            raise ValueError("Send either status or document")
        return self


def totals(document, uploaded=False):
    if uploaded:
        return {document.billing: {"subtotal": float(document.amount), "tax": 0, "total": float(document.amount)}}
    result = {}
    for item in document.items:
        bucket = result.setdefault(item.billing, {"subtotal": Decimal("0")})
        bucket["subtotal"] += (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    for bucket in result.values():
        subtotal = bucket["subtotal"]
        tax = (subtotal * document.tax / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        bucket.update(subtotal=float(subtotal), tax=float(tax), total=float(subtotal + tax))
    return result
