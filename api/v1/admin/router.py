from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from beanie import PydanticObjectId
from security.auth import token_required
from security.rate_limiter import rate_limiter
from .schemas import EventCreate
from fastapi.responses import JSONResponse
from db.models.event import Event, EventStatus
from db.models.auth import User
from db.models.registration import Registration
from db.models.team import Team
from monitoring.logger import logging

logger = logging.getLogger("admin")

admin_router = APIRouter()


@admin_router.post("/add-event")
async def add_event(
    request: Request,
    data: EventCreate,
    user_data: dict = Depends(token_required(["ADMIN",])),
    _: None = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    try:
        print(f"DATA: {data}")
        # stp 1: extract user information
        user_id = str(user_data.get("user_id"))

        # stp 2: create event document
        event = Event(
            **data.model_dump(),
            created_by=user_id
        )

        # stp 3: insert event into database
        await event.insert()
        logger.info("Successfully created new event", extra={"event_id": str(event.id), "event_name": event.name, "created_by": user_id})

        # stp 4: success response
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Event created successfully",
                "data": {
                    "id": str(event.id)
                },
                "error": None
            }
        )

    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception("Failed to create event", exc_info=exc)
        raise HTTPException(status_code=500, detail="Could not create event")


@admin_router.get("/all-events")
async def get_all_events(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(50, ge=1, le=500, description="Events per page"),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        collection = Event.get_motor_collection()
        pipeline = [
            {
                "$facet": {
                    "metadata": [{"$count": "total_items"}],
                    "events": [
                        {"$sort": {"created_at": -1, "_id": -1}},
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
                        {
                            "$project": {
                                "_id": 1,
                                "name": 1,
                                "status": 1,
                                "created_at": 1,
                                "updated_at": 1,
                            }
                        },
                    ],
                }
            }
        ]
        result = await collection.aggregate(pipeline).to_list(length=1)
        aggregation_result = result[0] if result else {"metadata": [], "events": []}
        metadata = aggregation_result.get("metadata", [])
        total_count = metadata[0]["total_items"] if metadata else 0
        events = aggregation_result.get("events", [])

        event_list = [
            {
                "id": str(event.get("_id")),
                "name": event.get("name"),
                "status": event.get("status"),
                "created_at": event.get("created_at").isoformat() if event.get("created_at") else None,
                "updated_at": event.get("updated_at").isoformat() if event.get("updated_at") else None,
            }
            for event in events
        ]
        total_pages = (total_count + limit - 1) // limit if total_count else 0

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Events retrieved successfully",
                "data": event_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception(f"Error fetching admin event list: {str(exc)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.patch("/events/{event_id}/status")
async def update_event_status(
    event_id: str,
    status: str = Query(..., description="New event status: DRAFT, PUBLISHED, ONGOING, COMPLETED, CANCELLED"),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        try:
            object_id = PydanticObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event id format")

        try:
            event_status = EventStatus(status.upper())
        except ValueError:
            allowed = ", ".join([item.value for item in EventStatus])
            raise HTTPException(status_code=400, detail=f"Invalid status. Allowed values: {allowed}")

        event = await Event.get(object_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        event.status = event_status
        event.updated_at = datetime.utcnow()
        await event.save()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event status updated successfully",
                "data": {
                    "event_id": str(event.id),
                    "status": event.status.value,
                    "updated_at": event.updated_at.isoformat(),
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception(f"Error updating event status: {str(exc)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.get("/dashboard-summary")
async def get_dashboard_summary(
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        user_collection = User.get_motor_collection()
        registration_collection = Registration.get_motor_collection()
        event_collection = Event.get_motor_collection()

        total_users = await user_collection.count_documents({})
        total_registrations = await registration_collection.count_documents({})
        total_paid_events = await event_collection.count_documents({"payment_type": "PAID"})
        total_paid_registrations = await registration_collection.count_documents({"payment_status": "PAID"})

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Dashboard summary retrieved successfully",
                "data": {
                    "total_end_users": total_users,
                    "total_registrations": total_registrations,
                    "total_paid_events": total_paid_events,
                    "total_paid_registrations": total_paid_registrations,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception(f"Error fetching dashboard summary: {str(exc)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.get("/event-registrations/{event_id}")
async def get_event_registrations(
    event_id: str,
    email: str | None = Query(None, description="Filter by user email substring"),
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(50, ge=1, le=500, description="Registrations per page"),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        try:
            event_object_id = PydanticObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event id format")

        registration_collection = Registration.get_motor_collection()
        match_stage = {"$match": {"event_id": event_object_id}}
        
        pipeline = [
            match_stage,
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user_info",
                }
            },
            {
                "$addFields": {
                    "user_email": {"$arrayElemAt": ["$user_info.email", 0]},
                }
            },
        ]
        
        if email:
            pipeline.append({
                "$match": {
                    "user_email": {"$regex": email, "$options": "i"}
                }
            })

        pipeline.append({
            "$facet": {
                "metadata": [{"$count": "total_items"}],
                "registrations": [
                    {"$sort": {"created_at": -1, "_id": -1}},
                    {"$skip": (page - 1) * limit},
                    {"$limit": limit},
                    {
                        "$project": {
                            "_id": 0,
                            "user_email": 1,
                            "registration_type": 1,
                            "status": 1,
                            "payment_status": 1,
                            "created_at": 1,
                        }
                    },
                ],
            }
        })

        result = await registration_collection.aggregate(pipeline).to_list(length=1)
        aggregation_result = result[0] if result else {"metadata": [], "registrations": []}
        metadata = aggregation_result.get("metadata", [])
        total_count = metadata[0]["total_items"] if metadata else 0
        registrations = aggregation_result.get("registrations", [])

        registration_list = [
            {
                "email": reg.get("user_email"),
                "registration_type": reg.get("registration_type"),
                "status": reg.get("status"),
                "payment_status": reg.get("payment_status"),
                "created_at": reg.get("created_at").isoformat() if reg.get("created_at") else None,
            }
            for reg in registrations
        ]
        total_pages = (total_count + limit - 1) // limit if total_count else 0

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event registrations retrieved successfully",
                "data": registration_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
                "filters": {
                    "event_id": event_id,
                    "email": email,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception(f"Error fetching event registrations: {str(exc)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.get("/get-event-id")
async def get_event_ids(
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=7, refill_rate=0.5, mode="both"))
):
    try:
        events = await Event.find_all().to_list()

        event_list = [
            {
                "id": str(event.id),
                "name": event.name,
            }
            for event in events
        ]
        return JSONResponse(
            status_code=200,
            content= {
            "success": True,
            "message": "Event ids retrieved successfully",
            "data": event_list,
            "error": None,
        }
    )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.patch("/events/{event_id}/status")
async def update_event_status(
    event_id: str,
    status: str = Query(..., description="New event status: DRAFT, PUBLISHED, ONGOING, COMPLETED, CANCELLED"),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
):
    try:
        try:
            object_id = PydanticObjectId(event_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid event id format")

        try:
            event_status = EventStatus(status.upper())
        except ValueError:
            allowed = ", ".join(item.value for item in EventStatus)
            raise HTTPException(status_code=400, detail=f"Invalid status. Allowed values: {allowed}")

        event = await Event.get(object_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        event.status = event_status
        event.updated_at = datetime.utcnow()
        await event.save()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Event status updated successfully",
                "data": {
                    "event_id": str(event.id),
                    "status": event.status.value,
                    "updated_at": event.updated_at.isoformat(),
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as exc:
        logger.exception(f"Error updating event status: {str(exc)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@admin_router.get("/all-users")
async def get_user_email_status(
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    limit: int = Query(100, ge=1, le=500, description="Users per page"),
    status: str | None = Query(None, description="Filter by status: ACTIVE, INACTIVE, PENDING, SUSPENDED"),
    email: str | None = Query(None, description="Filter by email substring or exact match"),
    user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
    _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
):
    try:
        filters = {}

        if status:
            filters["status"] = status.upper()

        if email:
            filters["email"] = {"$regex": email, "$options": "i"}

        collection = User.get_motor_collection()

        total_count = await collection.count_documents(filters)

        users = await (
            collection
            .find(filters, {"_id": 0, "email": 1, "status": 1})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
            .to_list()
        )

        total_pages = (total_count + limit - 1) // limit if total_count else 0

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User email and status retrieved successfully",
                "data": users,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
                "filters": {
                    "status": status,
                    "email": email,
                },
                "error": None,
            },
        )
    except HTTPException as httpe:
        raise httpe
    except Exception as e:
        logger.error(f"Error fetching user list: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")





