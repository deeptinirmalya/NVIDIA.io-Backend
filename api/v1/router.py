from fastapi import APIRouter
from api.v1.admin.router import admin_router
from api.v1.auth.router import auth_router
from api.v1.events.router import events_router
from api.v1.teams.router import teams_router
from api.v1.payments.router import payments_router
from api.v1.webhooks.router import webhooks_router


v1_router = APIRouter()

# Included routers
v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
v1_router.include_router(events_router, tags=["Events"])
v1_router.include_router(teams_router, tags=["Teams"])
v1_router.include_router(payments_router, tags=["Payments"])
v1_router.include_router(webhooks_router, tags=["Webhooks"])


