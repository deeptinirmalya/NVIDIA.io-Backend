"""
Registration service layer - unified registration logic for all event types.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from beanie import PydanticObjectId

from db.models.event import Event, ParticipationType, PaymentType
from db.models.registration import Registration, RegistrationStatus, RegistrationPaymentStatus
from db.models.payment import Payment
from db.models.team import Team
from crud.registration_crud import RegistrationCRUD
from crud.team_crud import TeamCRUD
from services.team_service import TeamService
from services.payment_service import PaymentService
from db.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class RegistrationService:
    """Service layer for registration operations."""

    @staticmethod
    async def validate_registration_window(event: Event) -> bool:
        """
        Validate that event registration window is open.
        
        Raises:
            ValueError: If registration window is closed
        """
        now = datetime.utcnow()
        
        if now < event.registration_start:
            raise ValueError("Registration has not started yet")
        
        if now > event.registration_end:
            raise ValueError("Registration has ended")
        
        return True

    @staticmethod
    async def validate_event_published(event: Event) -> bool:
        """
        Validate that event is published/ongoing.
        
        Raises:
            ValueError: If event is not available
        """
        from db.models.event import EventStatus
        
        if event.status not in (EventStatus.PUBLISHED, EventStatus.ONGOING):
            raise ValueError(f"Event is not available (status: {event.status})")
        
        return True

    @staticmethod
    async def register_single_free(
        event_id: PydanticObjectId,
        event: Event,
        user_id: PydanticObjectId,
    ) -> Registration:
        """
        Register user for SINGLE + FREE event.
        
        Flow:
        1. Validate event and registration window
        2. Check no duplicate registration
        3. Check event capacity
        4. Create Registration (CONFIRMED, NOT_REQUIRED)
        5. Create AuditLog
        
        Args:
            event_id: Event ID
            event: Event model
            user_id: User ID
        
        Returns:
            Created Registration
        
        Raises:
            ValueError: If validation fails
        """
        # Validate
        await RegistrationService.validate_event_published(event)
        await RegistrationService.validate_registration_window(event)
        
        if event.participation_type != ParticipationType.SINGLE:
            raise ValueError("Event is not SINGLE type")
        
        if event.payment_type != PaymentType.FREE:
            raise ValueError("Event is not FREE")
        
        # Check duplicate
        existing = await RegistrationCRUD.get_single_registration(event_id, user_id)
        if existing:
            raise ValueError("User is already registered for this event")
        
        # Check capacity
        if event.max_participants:
            current_count = await RegistrationCRUD.count_registrations(event_id)
            if current_count >= event.max_participants:
                raise ValueError("Event is full")
        
        # Create registration (directly confirmed for FREE events)
        registration = await RegistrationCRUD.create_registration(
            event_id=event_id,
            registration_type="SINGLE",
            status=RegistrationStatus.CONFIRMED,
            payment_status=RegistrationPaymentStatus.NOT_REQUIRED,
            user_id=user_id,
            team_id=None,
        )
        
        # Create audit log
        await AuditLog(
            actor_user_id=user_id,
            action="user_registered_single_free",
            entity_type="registration",
            entity_id=registration.id,
            metadata={
                "event_id": str(event_id),
                "event_name": event.name,
            },
        ).insert()
        
        logger.info(f"User {user_id} registered for FREE event {event_id}")
        return registration

    @staticmethod
    async def register_single_paid(
        event_id: PydanticObjectId,
        event: Event,
        user_id: PydanticObjectId,
        session=None,
    ) -> tuple[Registration, Payment]:
        """
        Register user for SINGLE + PAID event and create payment.
        
        Flow:
        1. Validate event and registration window
        2. Check no duplicate registration
        3. Check event capacity
        4. Create Registration (PENDING, PENDING)
        5. Create Payment (CREATED)
        6. Create AuditLog
        
        Args:
            event_id: Event ID
            event: Event model
            user_id: User ID
        
        Returns:
            Tuple: (Registration, Payment)
        
        Raises:
            ValueError: If validation fails
        """
        # Validate
        await RegistrationService.validate_event_published(event)
        await RegistrationService.validate_registration_window(event)
        
        if event.participation_type != ParticipationType.SINGLE:
            raise ValueError("Event is not SINGLE type")
        
        if event.payment_type != PaymentType.PAID:
            raise ValueError("Event is not PAID")
        
        if not event.fee or event.fee <= 0:
            raise ValueError("Event fee not set")
        
        # Check duplicate
        existing = await RegistrationCRUD.get_single_registration(event_id, user_id)
        if existing:
            raise ValueError("User is already registered for this event")
        
        # Check capacity
        if event.max_participants:
            current_count = await RegistrationCRUD.count_registrations(event_id)
            if current_count >= event.max_participants:
                raise ValueError("Event is full")
        
        # Create registration (PENDING - will confirm after payment)
        registration = await RegistrationCRUD.create_registration(
            event_id=event_id,
            registration_type="SINGLE",
            status=RegistrationStatus.PENDING,
            payment_status=RegistrationPaymentStatus.PENDING,
            user_id=user_id,
            team_id=None,
            session=session,
        )
        
        # Create payment
        payment = await PaymentService.create_payment_for_single_registration(
            event_id=event_id,
            user_id=user_id,
            registration_id=registration.id,
            amount=event.fee,
            currency=event.currency or "INR",
            session=session,
        )
        
        # Create audit log
        await AuditLog(
            actor_user_id=user_id,
            action="user_registered_single_paid",
            entity_type="registration",
            entity_id=registration.id,
            metadata={
                "event_id": str(event_id),
                "event_name": event.name,
                "payment_id": str(payment.id),
                "amount": str(event.fee),
            },
        ).insert(session=session)
        
        logger.info(f"User {user_id} registered for PAID event {event_id}, payment: {payment.id}")
        return registration, payment

    @staticmethod
    async def register_team_free(
        event_id: PydanticObjectId,
        event: Event,
        team_id: PydanticObjectId,
    ) -> Registration:
        """
        Register team for TEAM + FREE event.
        
        Called automatically when team reaches minimum size.
        
        Flow:
        1. Validate team and event
        2. Verify team has minimum members
        3. Check no duplicate team registration
        4. Create Registration (CONFIRMED, NOT_REQUIRED)
        5. Update Team status to CONFIRMED
        6. Create AuditLog
        
        Args:
            event_id: Event ID
            event: Event model
            team_id: Team ID
        
        Returns:
            Created Registration
        
        Raises:
            ValueError: If validation fails
        """
        # Validate
        await RegistrationService.validate_event_published(event)
        await RegistrationService.validate_registration_window(event)
        
        if event.participation_type != ParticipationType.TEAM:
            raise ValueError("Event is not TEAM type")
        
        if event.payment_type != PaymentType.FREE:
            raise ValueError("Event is not FREE")
        
        # Validate team
        team = await TeamCRUD.get_team_by_id(team_id)
        if not team:
            raise ValueError("Team not found")
        
        if team.event_id != event_id:
            raise ValueError("Team does not belong to this event")
        
        # Check no duplicate registration
        existing = await RegistrationCRUD.get_team_registration(event_id, team_id)
        if existing:
            raise ValueError("Team is already registered for this event")
        
        # Create registration
        registration = await RegistrationCRUD.create_registration(
            event_id=event_id,
            registration_type="TEAM",
            status=RegistrationStatus.CONFIRMED,
            payment_status=RegistrationPaymentStatus.NOT_REQUIRED,
            user_id=None,
            team_id=team_id,
        )
        
        # Update team status
        await TeamCRUD.confirm_team(team_id)
        
        # Create audit log
        await AuditLog(
            actor_user_id=team.captain_id,
            action="team_registered_free",
            entity_type="registration",
            entity_id=registration.id,
            metadata={
                "event_id": str(event_id),
                "event_name": event.name,
                "team_id": str(team_id),
                "team_name": team.name,
            },
        ).insert()
        
        logger.info(f"Team {team_id} registered for FREE event {event_id}")
        return registration

    @staticmethod
    async def register_team_paid(
        event_id: PydanticObjectId,
        event: Event,
        team_id: PydanticObjectId,
        captain_id: PydanticObjectId,
        session=None,
    ) -> tuple[Registration, Payment]:
        """
        Register team for TEAM + PAID event and create payment.
        
        IMPORTANT: Only the team captain can initiate this.
        Amount is event.fee (NOT multiplied by team size).
        
        Flow:
        1. Validate team and event
        2. Verify captain owns team
        3. Verify team has minimum members
        4. Check no duplicate team registration
        5. Create Registration (PENDING, PENDING)
        6. Create Payment (CREATED) - single payment for team
        7. Update Team status to PAYMENT_PENDING
        8. Create AuditLog
        
        Args:
            event_id: Event ID
            event: Event model
            team_id: Team ID
            captain_id: Captain user ID (must match team.captain_id)
        
        Returns:
            Tuple: (Registration, Payment)
        
        Raises:
            ValueError: If validation fails
        """
        # Validate
        await RegistrationService.validate_event_published(event)
        await RegistrationService.validate_registration_window(event)
        
        if event.participation_type != ParticipationType.TEAM:
            raise ValueError("Event is not TEAM type")
        
        if event.payment_type != PaymentType.PAID:
            raise ValueError("Event is not PAID")
        
        if not event.fee or event.fee <= 0:
            raise ValueError("Event fee not set")
        
        # Validate team and captain
        team = await TeamCRUD.get_team_by_id(team_id)
        if not team:
            raise ValueError("Team not found")
        
        if team.event_id != event_id:
            raise ValueError("Team does not belong to this event")
        
        if team.captain_id != captain_id:
            raise ValueError("Only team captain can register the team for payment")
        
        # Check team has minimum members
        member_count = await TeamService.get_team_member_count(team_id)
        if event.team_size_min and member_count < event.team_size_min:
            raise ValueError(f"Team must have at least {event.team_size_min} members")
        
        # Check no duplicate registration
        existing = await RegistrationCRUD.get_team_registration(event_id, team_id)
        if existing:
            raise ValueError("Team is already registered for this event")
        
        # Create registration (PENDING - will confirm after payment)
        registration = await RegistrationCRUD.create_registration(
            event_id=event_id,
            registration_type="TEAM",
            status=RegistrationStatus.PENDING,
            payment_status=RegistrationPaymentStatus.PENDING,
            user_id=None,
            team_id=team_id,
            session=session,
        )
        
        # Create payment - CAPTAIN PAYS ONCE for entire team (NOT per member)
        payment = await PaymentService.create_payment_for_team_registration(
            event_id=event_id,
            captain_id=captain_id,
            team_id=team_id,
            registration_id=registration.id,
            amount=event.fee,  # Single payment for team
            currency=event.currency or "INR",
            session=session,
        )
        
        # Update team status to PAYMENT_PENDING
        await TeamCRUD.mark_team_payment_pending(team_id, session=session)
        
        # Create audit log
        await AuditLog(
            actor_user_id=captain_id,
            action="team_registered_paid",
            entity_type="registration",
            entity_id=registration.id,
            metadata={
                "event_id": str(event_id),
                "event_name": event.name,
                "team_id": str(team_id),
                "team_name": team.name,
                "payment_id": str(payment.id),
                "amount": str(event.fee),
                "member_count": member_count,
            },
        ).insert(session=session)
        
        logger.info(f"Team {team_id} registered for PAID event {event_id}, payment: {payment.id}")
        return registration, payment
