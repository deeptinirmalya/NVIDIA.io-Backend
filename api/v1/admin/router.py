# from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, HTTPException
# from beanie import PydanticObjectId
# from security.auth import token_required
# from security.rate_limiter import rate_limiter
# from .schemas import EventCreate
# from fastapi.responses import JSONResponse
# from db.models.event import Event, EventStatus
# from db.models.auth import User
# from db.models.registration import Registration
# from db.models.team_registration import Team
# from monitoring.logger import logging

# logger = logging.getLogger("admin")

admin_router = APIRouter()


# @admin_router.post("/add-event")
# async def add_event(
#     request: Request,
#     data: EventCreate,
#     user_data: dict = Depends(token_required(["ADMIN"])),
#     _: None = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
# ):
#     try:
#         print(f"DATA: {data}")
#         # stp 1: extract user information
#         user_id = str(user_data.get("user_id"))

#         # stp 2: create event document
#         event = Event(
#             **data.model_dump(),
#             created_by=user_id
#         )

#         # stp 3: insert event into database
#         await event.insert()
#         logger.info("Successfully created new event", extra={"event_id": str(event.id), "event_name": event.name, "created_by": user_id})

#         # stp 4: success response
#         return JSONResponse(
#             status_code=201,
#             content={
#                 "success": True,
#                 "message": "Event created successfully",
#                 "data": {
#                     "id": str(event.id)
#                 },
#                 "error": None
#             }
#         )

#     except HTTPException as httpe:
#         raise httpe
#     except Exception as exc:
#         logger.exception("Failed to create event", exc_info=exc)
#         raise HTTPException(status_code=500, detail="Could not create event")


# @admin_router.get("/all-events")
# async def get_all_events(
#     page: int = Query(1, ge=1, description="Page number starting from 1"),
#     limit: int = Query(50, ge=1, le=500, description="Events per page"),
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
# ):
#     pass


# @admin_router.patch("/events/{event_id}/status")
# async def update_event_status(
#     event_id: str,
#     status: str = Query(..., description="New event status: DRAFT, PUBLISHED, ONGOING, COMPLETED, CANCELLED"),
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
# ):
#     pass


# @admin_router.get("/dashboard-summary")
# async def get_dashboard_summary(
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
# ):
#     pass



# @admin_router.get("/event-registrations/{event_id}")
# async def get_event_registrations(
#     event_id: str,
#     email: str | None = Query(None, description="Filter by user email substring"),
#     page: int = Query(1, ge=1, description="Page number starting from 1"),
#     limit: int = Query(50, ge=1, le=500, description="Registrations per page"),
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
# ):
#     pass



# @admin_router.get("/get-event-id")
# async def get_event_ids(
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=7, refill_rate=0.5, mode="both"))
# ):
#     pass


# @admin_router.patch("/events/{event_id}/status")
# async def update_event_status(
#     event_id: str,
#     status: str = Query(..., description="New event status: DRAFT, PUBLISHED, ONGOING, COMPLETED, CANCELLED"),
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both")),
# ):
#     pass



# @admin_router.get("/all-users")
# async def get_user_email_status(
#     page: int = Query(1, ge=1, description="Page number starting from 1"),
#     limit: int = Query(100, ge=1, le=500, description="Users per page"),
#     status: str | None = Query(None, description="Filter by status: ACTIVE, INACTIVE, PENDING, SUSPENDED"),
#     email: str | None = Query(None, description="Filter by email substring or exact match"),
#     user_data: dict = Depends(token_required(allowed_roles=["ADMIN", "SUPERADMIN"])),
#     _rate_limit = Depends(rate_limiter(max_tokens=10, refill_rate=0.5, mode="both"))
# ): 
#     pass





