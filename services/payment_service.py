"""
Payment service layer - Razorpay integration and payment logic.
"""
import logging
import hmac
import hashlib
from decimal import Decimal
from datetime import datetime
from typing import Optional

import razorpay
from beanie import PydanticObjectId

from core.config import settings
from db.models.payment import Payment, PaymentStatus
from db.models.event import Event
from db.models.registration import Registration, RegistrationStatus, RegistrationPaymentStatus
from crud.payment_crud import PaymentCRUD
from crud.registration_crud import RegistrationCRUD
from crud.team_crud import TeamCRUD

logger = logging.getLogger(__name__)


class PaymentService:
    """Service layer for payment operations and Razorpay integration."""

    @staticmethod
    def create_idempotency_key(
        event_id: PydanticObjectId,
        user_id: PydanticObjectId,
        team_id: Optional[PydanticObjectId] = None,
    ) -> str:
        """
        Create idempotency key to prevent duplicate payments.
        
        Format: event_{eventId}_user_{userId}_team_{teamId}_{timestamp}
        or      event_{eventId}_user_{userId}_{timestamp}
        """
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        if team_id:
            return f"event_{event_id}_user_{user_id}_team_{team_id}_{timestamp}"
        return f"event_{event_id}_user_{user_id}_{timestamp}"

    @staticmethod
    async def create_payment_for_single_registration(
        event_id: PydanticObjectId,
        user_id: PydanticObjectId,
        registration_id: PydanticObjectId,
        amount: Decimal,
        currency: str = "INR",
        session=None,
    ) -> Payment:
        """
        Create payment for SINGLE type registration.
        
        Args:
            event_id: Event ID
            user_id: User ID (payer)
            registration_id: Registration ID
            amount: Payment amount
            currency: Currency code
        
        Returns:
            Created Payment document
        """
        idempotency_key = PaymentService.create_idempotency_key(
            event_id=event_id,
            user_id=user_id,
        )
        
        # Check for existing payment with same idempotency key (prevents duplicates)
        existing_payment = await PaymentCRUD.get_payment_by_idempotency_key(idempotency_key)
        if existing_payment:
            logger.info(f"Payment already exists with idempotency key: {idempotency_key}")
            return existing_payment
        
        payment = await PaymentCRUD.create_payment(
            event_id=event_id,
            user_id=user_id,
            registration_id=registration_id,
            amount=amount,
            idempotency_key=idempotency_key,
            currency=currency,
            status=PaymentStatus.CREATED,
            session=session,
        )
        
        logger.info(f"Payment created: {payment.id} for user: {user_id}")
        return payment

    @staticmethod
    async def create_payment_for_team_registration(
        event_id: PydanticObjectId,
        captain_id: PydanticObjectId,
        team_id: PydanticObjectId,
        registration_id: PydanticObjectId,
        amount: Decimal,
        currency: str = "INR",
        session=None,
    ) -> Payment:
        """
        Create payment for TEAM type registration.
        
        IMPORTANT: Amount is event.fee (NOT multiplied by team size).
        Only the team captain pays once for the entire team.
        
        Args:
            event_id: Event ID
            captain_id: Team captain user ID (payer)
            team_id: Team ID
            registration_id: Registration ID
            amount: Payment amount (should be event.fee, not per member)
            currency: Currency code
        
        Returns:
            Created Payment document
        """
        idempotency_key = PaymentService.create_idempotency_key(
            event_id=event_id,
            user_id=captain_id,
            team_id=team_id,
        )
        
        # Check for existing payment (prevents duplicates)
        existing_payment = await PaymentCRUD.get_payment_by_idempotency_key(idempotency_key)
        if existing_payment:
            logger.info(f"Team payment already exists: {idempotency_key}")
            return existing_payment
        
        payment = await PaymentCRUD.create_payment(
            event_id=event_id,
            user_id=captain_id,
            team_id=team_id,
            registration_id=registration_id,
            amount=amount,
            idempotency_key=idempotency_key,
            currency=currency,
            status=PaymentStatus.CREATED,
            session=session,
        )
        
        logger.info(f"Team payment created: {payment.id} for team: {team_id}")
        return payment

    @staticmethod
    def create_razorpay_order_payload(
        payment: Payment,
        event: Event,
        receipt: str = None,
        notes: dict = None,
    ) -> dict:
        """
        Create payload for Razorpay Create Order API.
        
        Args:
            payment: Payment document
            event: Event document
            receipt: Receipt/reference ID
            notes: Additional metadata
        
        Returns:
            Dictionary ready for Razorpay API
        """
        amount_paise = int(payment.amount * 100)  # Convert to paise
        
        return {
            "amount": amount_paise,
            "currency": payment.currency,
            "receipt": receipt or str(payment.id),
            "notes": notes or {
                "event_id": str(event.id),
                "event_name": event.name,
                "payment_id": str(payment.id),
            },
        }

    @staticmethod
    def verify_checkout_signature(
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verify the frontend client-side Razorpay payment signature."""
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, razorpay_signature)

        if not is_valid:
            logger.warning(
                "Checkout signature verification failed for order: %s",
                razorpay_order_id,
            )

        return is_valid

    @staticmethod
    def verify_webhook_signature(
        payload: bytes | str,
        razorpay_signature: str,
    ) -> bool:
        """Verify Razorpay webhook authenticity using the webhook secret."""
        if not razorpay_signature:
            return False

        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            raw,
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, razorpay_signature)

        if not is_valid:
            logger.warning("Webhook signature verification failed")

        return is_valid

    @staticmethod
    def create_razorpay_client() -> razorpay.Client:
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError("Missing Razorpay credentials.")
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    @staticmethod
    async def create_razorpay_order_for_payment(
        payment: Payment,
        event: Event,
        session=None,
    ) -> dict:
        """Create and persist a Razorpay order for a payment record."""
        if payment.razorpay_order_id:
            return {
                "id": payment.razorpay_order_id,
                "amount": int(payment.amount * 100),
                "currency": payment.currency,
                "key": settings.RAZORPAY_KEY_ID,
            }

        client = PaymentService.create_razorpay_client()
        payload = PaymentService.create_razorpay_order_payload(
            payment,
            event,
            receipt=str(payment.id),
            notes={
                "event_id": str(event.id),
                "event_name": event.name,
                "payment_id": str(payment.id),
                "user_id": str(payment.user_id),
                "registration_id": str(payment.registration_id) if payment.registration_id else "",
            },
        )
        order = client.order.create(data=payload)

        if not order or not order.get("id"):
            raise RuntimeError("Unable to create Razorpay order")

        await PaymentCRUD.update_payment_with_razorpay_order(
            payment.id,
            order["id"],
            session=session,
        )

        return {
            "id": order["id"],
            "amount": int(payment.amount * 100),
            "currency": payment.currency,
            "key": settings.RAZORPAY_KEY_ID,
        }

    @staticmethod
    async def process_webhook_payment_success(
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        razorpay_amount: int,  # Amount in paise
        raw_body: bytes | str | None = None,
    ) -> tuple[bool, Optional[str], Optional[Payment]]:
        """
        Process successful payment webhook from Razorpay.
        
        Args:
            razorpay_order_id: Order ID
            razorpay_payment_id: Payment ID
            razorpay_signature: Webhook signature
            razorpay_amount: Amount paid (in paise)
        
        Returns:
            Tuple: (success: bool, error_message: Optional[str], payment: Optional[Payment])
        """
        # Verify signature using the raw webhook payload and webhook secret.
        if raw_body is not None and not PaymentService.verify_webhook_signature(
            raw_body,
            razorpay_signature,
        ):
            return False, "Invalid webhook signature", None
        
        # Find payment by Razorpay order ID
        payment = await PaymentCRUD.get_payment_by_razorpay_order_id(razorpay_order_id)
        if not payment:
            logger.error(f"Payment not found for order: {razorpay_order_id}")
            return False, "Payment not found", None
        
        # Mark webhook as received (for idempotency)
        await PaymentCRUD.mark_webhook_received(payment.id)
        
        # If payment already success, return early (idempotent)
        if payment.status == PaymentStatus.SUCCESS:
            logger.info(f"Payment {payment.id} already marked as SUCCESS, skipping")
            return True, None, payment
        
        # Verify amount matches
        expected_amount_paise = int(payment.amount * 100)
        if razorpay_amount != expected_amount_paise:
            logger.error(
                f"Amount mismatch for payment {payment.id}: "
                f"expected {expected_amount_paise}, got {razorpay_amount}"
            )
            await PaymentCRUD.mark_payment_failed(
                payment.id,
                f"Amount mismatch: expected {expected_amount_paise}, got {razorpay_amount}",
            )
            return False, "Amount verification failed", payment
        
        # Update payment with Razorpay details
        payment = await PaymentCRUD.update_payment_with_razorpay_response(
            payment.id,
            razorpay_payment_id,
            razorpay_signature,
        )
        
        # Update registration status to CONFIRMED
        if payment.registration_id:
            registration = await RegistrationCRUD.get_registration_by_id(
                payment.registration_id
            )
            if registration:
                registration.status = RegistrationStatus.CONFIRMED
                registration.payment_status = RegistrationPaymentStatus.PAID
                registration.updated_at = datetime.utcnow()
                await registration.save()
                
                logger.info(
                    f"Registration {registration.id} confirmed via payment {payment.id}"
                )
        
        # Update team status if team payment
        if payment.team_id:
            await TeamCRUD.confirm_team(payment.team_id)
            logger.info(f"Team {payment.team_id} confirmed via payment {payment.id}")
        
        logger.info(f"Payment {payment.id} processed successfully")
        return True, None, payment

    @staticmethod
    async def process_webhook_payment_failed(
        razorpay_order_id: str,
        razorpay_payment_id: str,
        failure_reason: str,
    ) -> tuple[bool, Optional[str], Optional[Payment]]:
        """
        Process failed payment webhook.
        
        Args:
            razorpay_order_id: Order ID
            razorpay_payment_id: Payment ID
            failure_reason: Reason for failure
        
        Returns:
            Tuple: (success: bool, error_message: Optional[str], payment: Optional[Payment])
        """
        # Find payment
        payment = await PaymentCRUD.get_payment_by_razorpay_order_id(razorpay_order_id)
        if not payment:
            logger.error(f"Payment not found for order: {razorpay_order_id}")
            return False, "Payment not found", None
        
        # Mark as failed
        payment = await PaymentCRUD.mark_payment_failed(payment.id, failure_reason)
        
        # Update registration payment status
        if payment.registration_id:
            registration = await RegistrationCRUD.get_registration_by_id(
                payment.registration_id
            )
            if registration:
                registration.status = RegistrationStatus.CANCELLED
                registration.payment_status = RegistrationPaymentStatus.FAILED
                registration.updated_at = datetime.utcnow()
                await registration.save()
        
        logger.warning(f"Payment {payment.id} marked as failed: {failure_reason}")
        return True, None, payment

    @staticmethod
    async def cancel_unpaid_payment(
        payment_id: PydanticObjectId,
        user_id: PydanticObjectId,
    ) -> Optional[Payment]:
        """Cancel an unpaid checkout attempt and its pending registration."""
        payment = await PaymentCRUD.get_payment_by_id(payment_id)
        if not payment:
            return None

        if payment.user_id != user_id:
            raise ValueError("You cannot cancel this payment")

        if payment.status == PaymentStatus.SUCCESS:
            raise ValueError("A successful payment cannot be cancelled")

        payment = await PaymentCRUD.mark_payment_failed(
            payment_id,
            "Checkout was cancelled or abandoned",
        )

        if payment and payment.registration_id:
            registration = await RegistrationCRUD.get_registration_by_id(
                payment.registration_id
            )
            if registration and registration.status != RegistrationStatus.CONFIRMED:
                registration.status = RegistrationStatus.CANCELLED
                registration.payment_status = RegistrationPaymentStatus.FAILED
                registration.updated_at = datetime.utcnow()
                await registration.save()

        return payment

    @staticmethod
    async def get_payment_status(payment_id: PydanticObjectId) -> Optional[Payment]:
        """Get current payment status."""
        return await PaymentCRUD.get_payment_by_id(payment_id)
