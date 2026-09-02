"""
Payment CRUD operations for database access.
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from beanie import PydanticObjectId
from db.models.payment import Payment, PaymentStatus
from utils import util, auth_util


class PaymentCRUD:


    @staticmethod
    async def create_payment(
        event_id: PydanticObjectId,
        user_id: PydanticObjectId,
        amount: Decimal,
        idempotency_key: str,
        currency: str = "INR",
        registration_id: Optional[PydanticObjectId] = None,
        team_id: Optional[PydanticObjectId] = None,
        status: PaymentStatus = PaymentStatus.CREATED,
        session=None,
    ) -> Payment:
        """
        Create a new payment.
        
        Args:
            event_id: Event ID
            user_id: User ID (payer - typically captain for team payments)
            amount: Payment amount in base units (e.g., 500 for ₹500)
            idempotency_key: Unique key to prevent duplicate payments
            currency: Currency code (default: INR)
            registration_id: Registration ID (optional, set after payment succeeds)
            team_id: Team ID (for team payments)
            status: Payment status (default: CREATED)
        
        Returns:
            Created Payment document
        """
        payment = Payment(
            event_id=event_id,
            user_id=user_id,
            amount=amount,
            currency=currency,
            status=status,
            registration_id=registration_id,
            team_id=team_id,
            idempotency_key=idempotency_key,
            created_at=auth_util.get_now_utc(),
            updated_at=auth_util.get_now_utc(),
        )
        await payment.insert(session=session)
        return payment

    @staticmethod
    async def get_payment_by_id(payment_id: PydanticObjectId) -> Optional[Payment]:
        return await Payment.get(payment_id)

    @staticmethod
    async def get_payment_by_idempotency_key(
        idempotency_key: str,
    ) -> Optional[Payment]:
        payment = await Payment.find_one({"idempotency_key": idempotency_key})
        return payment

    @staticmethod
    async def get_payment_by_razorpay_order_id(
        razorpay_order_id: str,
    ) -> Optional[Payment]:
        payment = await Payment.find_one({"razorpay_order_id": razorpay_order_id})
        return payment

    @staticmethod
    async def get_payment_by_razorpay_payment_id(
        razorpay_payment_id: str,
    ) -> Optional[Payment]:
        payment = await Payment.find_one({"razorpay_payment_id": razorpay_payment_id})
        return payment

    @staticmethod
    async def get_user_payments(
        user_id: PydanticObjectId,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Payment]:
        payments = (
            await Payment.find({"user_id": user_id})
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return payments

    @staticmethod
    async def get_event_payments(
        event_id: PydanticObjectId,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Payment]:
        payments = (
            await Payment.find({"event_id": event_id})
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return payments

    @staticmethod
    async def count_payments_by_status(
        event_id: PydanticObjectId,
        status: PaymentStatus,
    ) -> int:
        count = await Payment.find({"event_id": event_id, "status": status}).count()
        return count

    @staticmethod
    async def update_payment_status(
        payment_id: PydanticObjectId,
        status: PaymentStatus,
    ) -> Optional[Payment]:
        payment = await Payment.get(payment_id)
        if payment:
            payment.status = status
            payment.updated_at = auth_util.get_now_utc()
            await payment.save()
        return payment

    @staticmethod
    async def update_payment_with_razorpay_order(
        payment_id: PydanticObjectId,
        razorpay_order_id: str,
        session=None,
    ) -> Optional[Payment]:

        payment = await Payment.get(payment_id)
        if payment:
            payment.razorpay_order_id = razorpay_order_id
            payment.status = PaymentStatus.PROCESSING
            payment.updated_at = auth_util.get_now_utc()
            await payment.save(session=session)
        return payment

    @staticmethod
    async def update_payment_with_razorpay_response(
        payment_id: PydanticObjectId,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Optional[Payment]:
        payment = await Payment.get(payment_id)
        if payment:
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = PaymentStatus.SUCCESS
            payment.signature_verified = True
            payment.completed_at = auth_util.get_now_utc()
            payment.updated_at = auth_util.get_now_utc()
            await payment.save()
        return payment

    @staticmethod
    async def mark_payment_failed(
        payment_id: PydanticObjectId,
        failure_reason: str,
    ) -> Optional[Payment]:
        payment = await Payment.get(payment_id)
        if payment:
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = failure_reason
            payment.updated_at = auth_util.get_now_utc()
            await payment.save()
        return payment

    @staticmethod
    async def set_payment_registration_id(
        payment_id: PydanticObjectId,
        registration_id: PydanticObjectId,
    ) -> Optional[Payment]:
        payment = await Payment.get(payment_id)
        if payment:
            payment.registration_id = registration_id
            payment.updated_at = auth_util.get_now_utc()
            await payment.save()
        return payment

    @staticmethod
    async def mark_webhook_received(
        payment_id: PydanticObjectId,
    ) -> Optional[Payment]:

        payment = await Payment.get(payment_id)
        if payment:
            payment.webhook_received = True
            payment.webhook_received_at = auth_util.get_now_utc()
            await payment.save()
        return payment

    @staticmethod
    async def get_payments_by_status(
        event_id: PydanticObjectId,
        status: PaymentStatus,
        limit: int = 100,
    ) -> list[Payment]:
        payments = (
            await Payment.find({"event_id": event_id, "status": status})
            .limit(limit)
            .to_list()
        )
        return payments

    @staticmethod
    async def refund_payment(
        payment_id: PydanticObjectId,
    ) -> Optional[Payment]:
        return await PaymentCRUD.update_payment_status(
            payment_id,
            PaymentStatus.REFUNDED,
        )
