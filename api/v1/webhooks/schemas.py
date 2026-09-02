"""
Webhook schemas for Razorpay integration.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class RazorpayPaymentPayload(BaseModel):
    """Razorpay payment payload from webhook."""
    id: str = Field(..., description="Razorpay payment ID")
    entity: str = Field(default="payment")
    amount: int = Field(..., description="Amount in paise")
    currency: str = Field(default="INR")
    status: str = Field(..., description="Payment status")
    order_id: str = Field(..., description="Razorpay order ID")
    invoice_id: Optional[str] = None
    international: bool = False
    method: str = Field(default="emandate")
    amount_refunded: int = 0
    refund_status: Optional[str] = None
    captured: bool = False
    description: Optional[str] = None
    card_id: Optional[str] = None
    bank: Optional[str] = None
    wallet: Optional[str] = None
    vpa: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    fee: Optional[int] = None
    tax: Optional[int] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_reason: Optional[str] = None
    error_step: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None
    acquirer_data: Optional[Dict[str, Any]] = None
    settle_full_balance: bool = False
    settlement_status: Optional[str] = None
    created_at: int = Field(..., description="Unix timestamp")


class RazorpayWebhook(BaseModel):
    """Razorpay webhook event."""
    id: str = Field(..., description="Webhook event ID")
    entity: str = Field(default="event")
    event: str = Field(..., description="Event type, e.g., payment.authorized")
    contains: list[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(...)
    created_at: int = Field(..., description="Unix timestamp")

    class Config:
        extra = "allow"
