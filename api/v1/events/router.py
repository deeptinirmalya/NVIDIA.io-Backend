import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from beanie import PydanticObjectId
from fastapi.responses import JSONResponse

from security.auth import token_required
from engine.cache import get_value, set_value
from security.rate_limiter import rate_limiter
from db.models.event import Event, ParticipationType, PaymentType, EventStatus
from db.models.auth import User
from db.models.registration import Registration, RegistrationStatus
from db.models.team_member import TeamMember
from services.registration_service import RegistrationService
from services.payment_service import PaymentService
from api.v1.events.schemas import (
    RegisterSingleFreeRequest,
    RegisterSingleFreeResponse,
    RegisterSinglePaidRequest,
    RegisterSinglePaidResponse,
    RegisterTeamFreeRequest,
    RegisterTeamFreeResponse,
    RegisterTeamPaidRequest,
    RegisterTeamPaidResponse,
)
from services.team_service import TeamService

logger = logging.getLogger(__name__)

events_router = APIRouter(prefix="/events", tags=["Events"])


@events_router.get("/all-events", status_code=status.HTTP_200_OK)
async def view_events(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Event category: TECH, NON_TECH, SPORTS, CULTURAL"),
    gender: str | None = Query(None, description="Gender filter: BOYS, GIRLS, BOTH"),
    search: str | None = Query(None, description="Search by event name, about, or venue"),
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
):
    normalized_category = category.upper() if category else "all"
    normalized_gender = gender.upper() if gender else "all"
    normalized_search = str(search).strip() if search is not None else "all"
    cache_key = f"all_events:page={page}:limit={limit}:category={normalized_category}:gender={normalized_gender}:search={normalized_search}"

    cached = get_value(cache_key)
    if cached is not None:
        try:
            if isinstance(cached, (bytes, bytearray)):
                cached = cached.decode("utf-8")
            cached_response = json.loads(cached)
            return cached_response
        except Exception:
            logger.warning(f"Invalid cache payload for key: {cache_key}")

    try:
        filters = {
            "status": {"$ne": EventStatus.DRAFT.value},
        }

        if category:
            try:
                filters["category"] = category.upper()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid category value")

        if gender:
            try:
                filters["gender"] = gender.upper()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid gender value")

        if search is not None:
            search_term = str(search).strip()
            if search_term:
                filters["$or"] = [
                    {"name": {"$regex": search_term, "$options": "i"}},
                    {"about": {"$regex": search_term, "$options": "i"}},
                    {"venue": {"$regex": search_term, "$options": "i"}},
                ]

        total_count = await Event.find(filters).count()

        # If no events found, return None for data
        if total_count == 0:
            response = {
                "success": True,
                "message": "No events found",
                "data": None,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_items": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False,
                },
                "error": None,
            }
            try:
                set_value(cache_key, json.dumps(response), expire=300)
            except Exception:
                logger.warning(f"Failed to cache empty events response for key: {cache_key}")
            return response

        all_events = await Event.find(filters).to_list()

        ordered_events = sorted(all_events, key=lambda event: event.created_at, reverse=True)
        start = (page - 1) * limit
        end = start + limit
        paginated_events = ordered_events[start:end]

        response_items = []
        for event in paginated_events:
            response_items.append({
                "id": str(event.id),
                "name": event.name,
                "category": event.category,
                "gender": event.gender.value if hasattr(event.gender, 'value') else event.gender,
            })

        total_pages = (total_count + limit - 1) // limit if total_count else 0

        response = {
            "success": True,
            "message": "Events retrieved successfully",
            "data": response_items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
            "error": None,
        }

        try:
            set_value(cache_key, json.dumps(response), expire=300)
        except Exception:
            logger.warning(f"Failed to cache events response for key: {cache_key}")

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error fetching events: {str(exc)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve events")

@events_router.get("/{event_id}/joined-status", status_code=status.HTTP_200_OK)
async def check_user_joined_event(
    event_id: str,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT", "ADMIN", "SUPERADMIN"])),
):

    try:
        try:
            event_object_id = PydanticObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event id format")

        event = await Event.get(event_object_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        user_id = PydanticObjectId(user_data["user_id"])

        single_registration = await Registration.find_one({
            "event_id": event_object_id,
            "user_id": user_id,
            "registration_type": "SINGLE",
            "status": RegistrationStatus.CONFIRMED.value,
        })
        if single_registration:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "User is already registered for this event",
                    "data": {"joined": True},
                    "error": None,
                },
            )

        team_membership = await TeamMember.find_one({
            "event_id": event_object_id,
            "user_id": user_id,
            "status": "ACTIVE",
        })
        if team_membership:
            team_registration = await Registration.find_one({
                "event_id": event_object_id,
                "team_id": team_membership.team_id,
                "registration_type": "TEAM",
                "status": RegistrationStatus.CONFIRMED.value,
            })
            if team_registration:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "User is part of a registered team for this event",
                        "data": {"joined": True},
                        "error": None,
                    },
                )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User has not joined this event",
                "data": {"joined": False},
                "error": None,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error checking event join status: {str(exc)}")
        raise HTTPException(status_code=500, detail="Failed to check event join status")


@events_router.get("/{event_id}/details")
async def get_event_details(
    event_id: str,
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "STUDENT", "SUPERADMIN"])),
    _rate_limi = Depends(rate_limiter(max_tokens=5, refill_rate=0.5, mode="ip"))
):
    try:
        try:
            object_id = PydanticObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event id format")

        event = await Event.get(object_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        if event.status not in {
            EventStatus.PUBLISHED,
            EventStatus.ONGOING,
            EventStatus.COMPLETED,
            EventStatus.CANCELLED,
        }:
            raise HTTPException(status_code=404, detail="Event not found")

        data = {
            "id": str(event.id),
            "name": event.name,
            "about": event.about,
            "rules": event.rules,
            "venue": event.venue,
            "category": event.category.value if hasattr(event.category, "value") else event.category,
            "status": event.status.value if hasattr(event.status, "value") else event.status,
            "participation_type": event.participation_type.value if hasattr(event.participation_type, "value") else event.participation_type,
            "payment_type": event.payment_type.value if hasattr(event.payment_type, "value") else event.payment_type,
            "gender": event.gender.value if hasattr(event.gender, "value") else event.gender,
            "fee": float(event.fee) if event.fee is not None else None,
            "team_size_min": event.team_size_min,
            "team_size_max": event.team_size_max,
            "registration_start": event.registration_start.isoformat() if event.registration_start else None,
            "registration_end": event.registration_end.isoformat() if event.registration_end else None,
            "start_time": event.start_time.isoformat() if event.start_time else None,
            "end_time": event.end_time.isoformat() if event.end_time else None,
        }

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Here is the data",
                "data": data,
                "error": None,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching event details: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@events_router.post(
    "/{event_id}/register",
    response_model=RegisterSingleFreeResponse | RegisterSinglePaidResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_for_event(
    event_id: str,
    request: RegisterSingleFreeRequest | RegisterSinglePaidRequest,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both")),
):
    """
    Register for an event.
    
    Handles all registration types:
    - SINGLE + FREE: Direct confirmation
    - SINGLE + PAID: Creates payment, returns Razorpay order
    
    For TEAM events, use /teams endpoints.
    """
    payment = None
    try:
        # Get event
        event = await Event.get(PydanticObjectId(event_id))
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        
        user_id = PydanticObjectId(user_data["user_id"])
        
        # Route based on event type
        if event.participation_type == ParticipationType.SINGLE:
            if event.payment_type == PaymentType.FREE:
                # SINGLE + FREE
                registration = await RegistrationService.register_single_free(
                    event_id=PydanticObjectId(event_id),
                    event=event,
                    user_id=user_id,
                )
                
                return RegisterSingleFreeResponse(
                    success=True,
                    message="Registered successfully",
                    data={
                        "registrationId": str(registration.id),
                        "status": registration.status,
                        "eventId": str(event_id),
                    },
                )
            
            elif event.payment_type == PaymentType.PAID:
                # SINGLE + PAID
                registration, payment = await RegistrationService.register_single_paid(
                    event_id=PydanticObjectId(event_id),
                    event=event,
                    user_id=user_id,
                )
                
                order = await PaymentService.create_razorpay_order_for_payment(
                    payment,
                    event,
                )

                return RegisterSinglePaidResponse(
                    success=True,
                    message="Registration initiated, please complete payment",
                    data={
                        "razorpayOrderId": order["id"],
                        "amount": int(payment.amount * 100),
                        "currency": payment.currency,
                        "paymentId": str(payment.id),
                        "registrationId": str(registration.id),
                    },
                )
        
        elif event.participation_type == ParticipationType.TEAM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This is a TEAM event. Use /api/v1/teams to create or join a team first, then register.",
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown event participation type",
            )
    
    except ValueError as e:
        if payment:
            await PaymentService.cancel_unpaid_payment(payment.id, user_id)
        logger.warning(f"Validation error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        if payment:
            await PaymentService.cancel_unpaid_payment(payment.id, user_id)
        error_msg = str(e)
        logger.exception(f"Registration error: {error_msg}")
        # Include the actual error in response for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {error_msg}",
        )


@events_router.post(
    "/{event_id}/teams/register",
    response_model=RegisterTeamFreeResponse | RegisterTeamPaidResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_team_for_event(
    event_id: str,
    request: RegisterTeamFreeRequest | RegisterTeamPaidRequest,
    user_data: dict = Depends(token_required(allowed_roles=["STUDENT"])),
    rate_limit_dep=Depends(rate_limiter(max_tokens=5, refill_rate=0.1, mode="both")),
):
    """
    Register a team for an event (Captain only).
    
    Handles:
    - TEAM + FREE: Auto-registers when team meets minimum size (called internally)
    - TEAM + PAID: Creates payment for team, only captain can call
    
    For TEAM + PAID: Amount is event.fee (NOT multiplied by team size).
    Captain pays once for entire team.
    """
    payment = None
    try:
        # Get event
        event = await Event.get(PydanticObjectId(event_id))
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        
        if event.participation_type != ParticipationType.TEAM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This event is not a TEAM event",
            )
        
        user_id = PydanticObjectId(user_data["user_id"])

        if request.team_id:
            team_id = PydanticObjectId(request.team_id)
        elif request.team_name:
            team = await TeamService.create_team(
                event_id=PydanticObjectId(event_id),
                event=event,
                team_name=request.team_name,
                captain_id=user_id,
            )
            team_id = team.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either team_id or team_name is required",
            )

        if event.payment_type == PaymentType.FREE:
            # TEAM + FREE
            registration = await RegistrationService.register_team_free(
                event_id=PydanticObjectId(event_id),
                event=event,
                team_id=team_id,
            )
            
            return RegisterTeamFreeResponse(
                success=True,
                message="Team registered successfully",
                data={
                    "registrationId": str(registration.id),
                    "teamId": str(team_id),
                    "status": registration.status,
                    "memberCount": 0,  # TODO: Get actual count
                },
            )
        
        elif event.payment_type == PaymentType.PAID:
            # TEAM + PAID
            registration, payment = await RegistrationService.register_team_paid(
                event_id=PydanticObjectId(event_id),
                event=event,
                team_id=team_id,
                captain_id=user_id,
            )
            
            order = await PaymentService.create_razorpay_order_for_payment(
                payment,
                event,
            )

            return RegisterTeamPaidResponse(
                success=True,
                message="Team registration initiated, captain must complete payment",
                data={
                    "razorpayOrderId": order["id"],
                    "amount": int(payment.amount * 100),
                    "currency": payment.currency,
                    "paymentId": str(payment.id),
                    "registrationId": str(registration.id),
                    "teamId": str(team_id),
                    "memberCount": 0,
                },
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown payment type",
            )
    
    except ValueError as e:
        if payment:
            await PaymentService.cancel_unpaid_payment(payment.id, user_id)
        logger.warning(f"Validation error during team registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        if payment:
            await PaymentService.cancel_unpaid_payment(payment.id, user_id)
        error_msg = str(e)
        logger.exception(f"Team registration error: {error_msg}")
        # Include the actual error in response for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Team registration failed: {error_msg}",
        )
