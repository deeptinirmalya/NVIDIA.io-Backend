from fastapi import APIRouter
from api.v1.admin.router import admin_router
from api.v1.auth.router import auth_router
from api.v1.events.router import event_router
from api.v1.teams.router import teams_router
from api.v1.payments.router import payment_router
from api.v1.webhooks.router import webhook_router


v1_router = APIRouter()

# Included routers
v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
v1_router.include_router(event_router,prefix="/event", tags=["Event"])
v1_router.include_router(teams_router,prefix="/teams", tags=["Teams"])
v1_router.include_router(payment_router, prefix="/payment", tags=["Payments"])
v1_router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])


