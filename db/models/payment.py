from datetime import datetime
from decimal import Decimal
from enum import Enum

from beanie import Document, PydanticObjectId
from bson.decimal128 import Decimal128
from pydantic import Field, field_validator
from pymongo import IndexModel, ASCENDING, DESCENDING


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Payment(Document):


    event_id: PydanticObjectId

    registration_id: PydanticObjectId

    user_id: PydanticObjectId

    team_id: PydanticObjectId | None = None



    amount: Decimal

    currency: str = "INR"

    status: PaymentStatus = PaymentStatus.CREATED


    idempotency_key: str


    razorpay_order_id: str | None = None

    razorpay_payment_id: str | None = None

    razorpay_signature: str | None = None

    signature_verified: bool = False


    failure_reason: str | None = None

    refund_id: str | None = None

    refund_reason: str | None = None


    webhook_received: bool = False

    webhook_received_at: datetime | None = None


    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    completed_at: datetime | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value):
        if value is None:
            return value
        if isinstance(value, Decimal128):
            return value.to_decimal()
        if isinstance(value, (int, float, str, Decimal)):
            return Decimal(str(value))
        return value

    class Settings:

        name = "payments"

        indexes = [

            IndexModel(
                [("idempotency_key", ASCENDING)],
                unique=True
            ),

            IndexModel(
                [("razorpay_order_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "razorpay_order_id": {"$type": "string"}
                }
            ),

            # Razorpay payment lookup
            IndexModel(
                [("razorpay_payment_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "razorpay_payment_id": {"$type": "string"}
                }
            ),

            IndexModel(
                [("registration_id", ASCENDING)]
            ),

            IndexModel(
                [("user_id", ASCENDING)]
            ),

            IndexModel(
                [("event_id", ASCENDING)]
            ),

            IndexModel(
                [
                    ("status", ASCENDING),
                    ("created_at", DESCENDING)
                ]
            ),
        ]