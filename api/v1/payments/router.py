"""
Payments API router - Payment verification and status.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from beanie import PydanticObjectId

from security.auth import token_required
from security.rate_limiter import rate_limiter
from services.payment_service import PaymentService
from crud.payment_crud import PaymentCRUD
from crud.registration_crud import RegistrationCRUD
from crud.team_crud import TeamCRUD
from db.models.payment import PaymentStatus
from db.models.registration import RegistrationStatus, RegistrationPaymentStatus
from api.v1.payments.schemas import (
    PaymentStatusResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


@payments_router.post("/{payment_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_unpaid_payment(
    payment_id: str,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
):
    """Cancel an abandoned or failed checkout attempt."""
    try:
        payment = await PaymentService.cancel_unpaid_payment(
            payment_id=PydanticObjectId(payment_id),
            user_id=PydanticObjectId(user_data["user_id"]),
        )
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return {
            "success": True,
            "message": "Unpaid payment cancelled",
            "data": {"paymentId": str(payment.id), "status": payment.status},
            "error": None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@payments_router.get(
    "/{payment_id}/status",
    response_model=PaymentStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_payment_status(
    payment_id: str,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=30, refill_rate=1.0, mode="both")),
):
    """
    Get payment status.
    Returns:
    - status: CREATED, PROCESSING, SUCCESS, FAILED, REFUNDED
    - razorpayOrderId: Razorpay order ID (if created)
    - razorpayPaymentId: Razorpay payment ID (if paid)
    - signatureVerified: True if webhook signature verified
    """
    try:
        payment = await PaymentCRUD.get_payment_by_id(PydanticObjectId(payment_id))
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        
        return PaymentStatusResponse(
            id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            razorpay_order_id=payment.razorpay_order_id,
            razorpay_payment_id=payment.razorpay_payment_id,
            signature_verified=payment.signature_verified,
            created_at=payment.created_at.isoformat(),
        )
    
    except Exception as e:
        logger.error(f"Get payment status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment status",
        )


@payments_router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_payment(
    request: PaymentVerifyRequest,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    """
    Verify payment after Razorpay checkout.
    
    This endpoint is called from the frontend after user completes payment on Razorpay.
    
    Args:
    - razorpayOrderId: Order ID from checkout
    - razorpayPaymentId: Payment ID from checkout
    - razorpaySignature: Signature from checkout (HMAC-SHA256)
    
    This verifies the signature and marks payment as success.
    The webhook from Razorpay backend will also update registration status.
    """
    try:
        payment = await PaymentCRUD.get_payment_by_razorpay_order_id(
            request.razorpay_order_id
        )
        if not payment:
            raise ValueError("Payment not found")

        if payment.user_id != PydanticObjectId(user_data["user_id"]):
            raise ValueError("You cannot verify this payment")

        if payment.status == PaymentStatus.SUCCESS:
            return PaymentVerifyResponse(
                success=True,
                message="Payment was already verified by Razorpay webhook",
                data={
                    "paymentId": str(payment.id),
                    "status": payment.status,
                    "registrationId": str(payment.registration_id) if payment.registration_id else None,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                },
            )

        if payment.status == PaymentStatus.FAILED:
            raise ValueError(f"Payment cannot be verified from status {payment.status}")

        if not PaymentService.verify_checkout_signature(
            request.razorpay_order_id,
            request.razorpay_payment_id,
            request.razorpay_signature,
        ):
            raise ValueError("Payment signature verification failed")

        from datetime import datetime

        payment.razorpay_payment_id = request.razorpay_payment_id
        payment.razorpay_signature = request.razorpay_signature
        payment.signature_verified = True
        payment.status = PaymentStatus.PROCESSING
        payment.updated_at = datetime.utcnow()
        await payment.save()

        # Important: do not auto-confirm registration here.
        # Real success is authoritative only after Razorpay's webhook confirms the payment.
        logger.info(
            f"Payment {payment.id} signature verified on frontend; awaiting Razorpay webhook confirmation"
        )

        return PaymentVerifyResponse(
            success=True,
            message="Payment signature verified; awaiting Razorpay webhook confirmation",
            data={
                "paymentId": str(payment.id),
                "status": payment.status,
                "registrationId": str(payment.registration_id) if payment.registration_id else None,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment verification failed",
        )
