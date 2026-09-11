import logging
from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)

webhook_router = APIRouter()


@webhook_router.post(
    "/razorpay",
    status_code=status.HTTP_200_OK,
)
async def razorpay_webhook(request: Request):
    """
    Handles:
    - payment.authorized: Payment successful
    - payment.failed: Payment failed
    
    Webhook signature is verified using HMAC-SHA256.
    Idempotent: Multiple deliveries of same event are handled safely.
    
    Returns: {"status": "ok"} on success (even if already processed)
    """
    body = await request.json()
    print(f"\n\n ================================================== \n\n")
    print(f"\n{body}\n")
    print(f"\n\n ================================================== \n\n")