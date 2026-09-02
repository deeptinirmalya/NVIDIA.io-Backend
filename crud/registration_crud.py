"""
Registration CRUD operations for database access.
"""
from datetime import datetime
from typing import Optional
from beanie import PydanticObjectId
from db.models.registration import Registration, RegistrationStatus, RegistrationPaymentStatus
from db.models.event import Event


class RegistrationCRUD:
    """Database operations for Registration model."""

    @staticmethod
    async def create_registration(
        event_id: PydanticObjectId,
        registration_type: str,
        status: RegistrationStatus = RegistrationStatus.PENDING,
        payment_status: RegistrationPaymentStatus = RegistrationPaymentStatus.NOT_REQUIRED,
        user_id: Optional[PydanticObjectId] = None,
        team_id: Optional[PydanticObjectId] = None,
        session=None,
    ) -> Registration:
        """
        Create a new registration.
        
        Args:
            event_id: Event ID
            registration_type: "SINGLE" or "TEAM"
            status: Registration status (default: PENDING)
            payment_status: Payment status (default: NOT_REQUIRED for FREE events)
            user_id: User ID (required for SINGLE type)
            team_id: Team ID (required for TEAM type)
        
        Returns:
            Created Registration document
        """
        registration = Registration(
            event_id=event_id,
            registration_type=registration_type,
            user_id=user_id,
            team_id=team_id,
            status=status,
            payment_status=payment_status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await registration.insert(session=session)
        return registration

    @staticmethod
    async def get_registration_by_id(registration_id: PydanticObjectId) -> Optional[Registration]:
        """Get registration by ID."""
        return await Registration.get(registration_id)

    @staticmethod
    async def get_single_registration(
        event_id: PydanticObjectId,
        user_id: PydanticObjectId,
    ) -> Optional[Registration]:
        """
        Get SINGLE type registration for a user in an event.
        
        Raises:
            ValueError: If registration_type is not SINGLE
        """
        registration = await Registration.find_one(
            {
                "event_id": event_id,
                "user_id": user_id,
                "registration_type": "SINGLE",
            }
        )
        return registration

    @staticmethod
    async def get_team_registration(
        event_id: PydanticObjectId,
        team_id: PydanticObjectId,
    ) -> Optional[Registration]:
        """Get TEAM type registration for a team in an event."""
        registration = await Registration.find_one(
            {
                "event_id": event_id,
                "team_id": team_id,
                "registration_type": "TEAM",
            }
        )
        return registration

    @staticmethod
    async def get_user_registrations(
        user_id: PydanticObjectId,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Registration]:
        """Get all registrations for a user."""
        registrations = await Registration.find({"user_id": user_id}).skip(skip).limit(limit).to_list()
        return registrations

    @staticmethod
    async def get_event_registrations(
        event_id: PydanticObjectId,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Registration]:
        """Get all registrations for an event."""
        registrations = (
            await Registration.find({"event_id": event_id})
            .skip(skip)
            .limit(limit)
            .to_list()
        )
        return registrations

    @staticmethod
    async def count_registrations(event_id: PydanticObjectId) -> int:
        """Count total registrations for an event."""
        count = await Registration.find({"event_id": event_id}).count()
        return count

    @staticmethod
    async def update_registration_status(
        registration_id: PydanticObjectId,
        status: RegistrationStatus,
    ) -> Optional[Registration]:
        """Update registration status."""
        registration = await Registration.get(registration_id)
        if registration:
            registration.status = status
            registration.updated_at = datetime.utcnow()
            await registration.save()
        return registration

    @staticmethod
    async def update_payment_status(
        registration_id: PydanticObjectId,
        payment_status: RegistrationPaymentStatus,
    ) -> Optional[Registration]:
        """Update payment status in registration."""
        registration = await Registration.get(registration_id)
        if registration:
            registration.payment_status = payment_status
            registration.updated_at = datetime.utcnow()
            await registration.save()
        return registration

    @staticmethod
    async def confirm_registration(registration_id: PydanticObjectId) -> Optional[Registration]:
        """Confirm a registration (status -> CONFIRMED)."""
        return await RegistrationCRUD.update_registration_status(
            registration_id,
            RegistrationStatus.CONFIRMED,
        )

    @staticmethod
    async def cancel_registration(registration_id: PydanticObjectId) -> Optional[Registration]:
        """Cancel a registration (status -> CANCELLED)."""
        return await RegistrationCRUD.update_registration_status(
            registration_id,
            RegistrationStatus.CANCELLED,
        )

    @staticmethod
    async def get_registrations_by_status(
        event_id: PydanticObjectId,
        status: RegistrationStatus,
        limit: int = 100,
    ) -> list[Registration]:
        """Get registrations by status."""
        registrations = (
            await Registration.find({"event_id": event_id, "status": status})
            .limit(limit)
            .to_list()
        )
        return registrations

    @staticmethod
    async def delete_registration(registration_id: PydanticObjectId) -> bool:
        """Delete a registration (soft delete via status)."""
        registration = await Registration.get(registration_id)
        if registration:
            registration.status = RegistrationStatus.CANCELLED
            registration.updated_at = datetime.utcnow()
            await registration.save()
            return True
        return False
