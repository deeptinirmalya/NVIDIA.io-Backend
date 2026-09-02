"""
Schemas for payments API.
"""
from pydantic import BaseModel, Field
from beanie import PydanticObjectId
from decimal import Decimal


class PaymentStatusResponse(BaseModel):
    """Response for payment status."""
    payment_id: str = Field(..., alias="id")
    status: str
    amount: Decimal
    currency: str
    razorpay_order_id: str | None
    razorpay_payment_id: str | None
    signature_verified: bool
    created_at: str

    class Config:
        populate_by_name = True


class RazorpayWebhookPayload(BaseModel):
    """Razorpay webhook payload."""
    type: str = Field(..., description="Event type, e.g., 'payment.authorized'")
    created_at: int = Field(..., description="Unix timestamp")
    event_id: str = Field(..., description="Event ID from Razorpay")
    payload: dict = Field(..., description="Event payload with payment details")


class RazorpayPaymentEntity(BaseModel):
    """Razorpay payment entity from webhook."""
    id: str = Field(..., description="Razorpay payment ID")
    entity: str = Field(default="payment")
    amount: int = Field(..., description="Amount in paise")
    currency: str = Field(default="INR")
    status: str = Field(..., description="Payment status")
    order_id: str = Field(..., description="Razorpay order ID")
    notes: dict = Field(default_factory=dict)


class RazorpayPaymentSuccessWebhook(BaseModel):
    """Razorpay payment.authorized webhook."""
    type: str = Field(default="payment.authorized")
    payload: dict = Field(...)

    class Config:
        example = {
            "type": "payment.authorized",
            "payload": {
                "payment": {
                    "id": "pay_IluGWxBm9U8zJ8",
                    "entity": "payment",
                    "amount": 5000,
                    "currency": "INR",
                    "status": "authorized",
                    "order_id": "order_IluGWxBm9U8zJ8",
                    "notes": {}
                }
            }
        }


class PaymentVerifyRequest(BaseModel):
    """Request to verify payment after Razorpay checkout."""
    razorpay_order_id: str = Field(..., description="Razorpay order ID")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID")
    razorpay_signature: str = Field(..., description="Razorpay signature (HMAC-SHA256)")


class PaymentVerifyResponse(BaseModel):
    """Response for payment verification."""
    success: bool
    message: str
    data: dict = Field(
        ...,
        example={
            "paymentId": "507f1f77bcf86cd799439013",
            "status": "SUCCESS",
            "registrationId": "507f1f77bcf86cd799439011",
            "amount": "500",
            "currency": "INR",
        }
    )
