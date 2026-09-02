import logging
from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime
from fastapi.responses import JSONResponse

from services.payment_service import PaymentService
from api.v1.webhooks.schemas import RazorpayWebhook
from db.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

webhooks_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhooks_router.post(
    "/razorpay",
    status_code=status.HTTP_200_OK,
)
async def razorpay_webhook(request: Request):
    """
    Razorpay webhook handler.
    
    Handles:
    - payment.authorized: Payment successful
    - payment.failed: Payment failed
    
    Webhook signature is verified using HMAC-SHA256.
    Idempotent: Multiple deliveries of same event are handled safely.
    
    Returns: {"status": "ok"} on success (even if already processed)
    """

    try:

        body = await request.json()
        
        event_type = body.get("event")
        payload = body.get("payload", {})
        webhook_id = body.get("id")
        raw_body = await request.body()

        logger.info(f"Razorpay webhook received: {event_type} (ID: {webhook_id})")

        if not event_type or not payload:
            logger.warning("Invalid webhook structure")
            return {"status": "ok"}

        payment_payload = payload.get("payment", {})
        payment_data = payment_payload.get("entity", payment_payload)
        razorpay_order_id = payment_data.get("order_id")
        razorpay_payment_id = payment_data.get("id")
        razorpay_signature = request.headers.get("x-razorpay-signature")
        amount_paise = payment_data.get("amount")

        if not razorpay_signature or not PaymentService.verify_webhook_signature(
            raw_body,
            razorpay_signature,
        ):
            logger.error("Invalid or missing Razorpay webhook signature")
            return {"status": "ok"}
        

        if event_type in {"payment.authorized", "payment.captured"}:
            if not (razorpay_order_id and razorpay_payment_id and amount_paise):
                logger.error("Missing required fields in webhook")
                return {"status": "ok"}

            success, error_msg, payment = await PaymentService.process_webhook_payment_success(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                razorpay_amount=amount_paise,
                raw_body=None,
            )
            
            if success and payment:
                logger.info(f"Payment {payment.id} marked as SUCCESS via webhook")
                

                await AuditLog(
                    actor_user_id=payment.user_id,
                    action="payment_success_webhook",
                    entity_type="payment",
                    entity_id=payment.id,
                    metadata={
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                        "amount": str(payment.amount),
                        "webhook_id": webhook_id,
                    },
                ).insert()
                
                return {"status": "ok"}
            else:
                logger.error(f"Payment processing failed: {error_msg}")
                if error_msg == "Payment not found":
                    return JSONResponse(status_code=500, content={"status": "retry"})
                return {"status": "ok"}
        

        elif event_type == "payment.failed":
            if not (razorpay_order_id and razorpay_payment_id):
                logger.error("Missing order/payment ID in failure event")
                return {"status": "ok"}
            
            failure_reason = payment_data.get("error_description", "Unknown error")
            
            success, error_msg, payment = await PaymentService.process_webhook_payment_failed(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                failure_reason=failure_reason,
            )
            
            if payment:
                logger.warning(f"Payment {payment.id} marked as FAILED: {failure_reason}")
                

                await AuditLog(
                    actor_user_id=payment.user_id,
                    action="payment_failed_webhook",
                    entity_type="payment",
                    entity_id=payment.id,
                    metadata={
                        "razorpay_order_id": razorpay_order_id,
                        "razorpay_payment_id": razorpay_payment_id,
                        "failure_reason": failure_reason,
                        "webhook_id": webhook_id,
                    },
                ).insert()
            
            if error_msg == "Payment not found":
                return JSONResponse(status_code=500, content={"status": "retry"})
            return {"status": "ok"}
        

        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)

        return {"status": "ok"}


@webhooks_router.get("/health", status_code=status.HTTP_200_OK)
async def webhook_health():

    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
