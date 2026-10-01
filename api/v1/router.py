from fastapi import APIRouter
from api.v1.admin.router import admin_router
from api.v1.auth.router import auth_router
from api.v1.events.router import event_router
from api.v1.teams.router import teams_router
from api.v1.payments.router import payment_router
from api.v1.webhooks.router import webhook_router
from api.v1.user.router import user_router



v1_router = APIRouter()
# Included routers
v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
v1_router.include_router(event_router,prefix="/event", tags=["Event"])
v1_router.include_router(teams_router,prefix="/teams", tags=["Teams"])
v1_router.include_router(payment_router, prefix="/payment", tags=["Payments"])
v1_router.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
v1_router.include_router(user_router, prefix="/user", tags=["User"])


# super Admin router initialization
from api.v1.superAdmin.routers.super_admin_admin_management import superadmin_admin_management_router
v1_router.include_router(superadmin_admin_management_router, prefix="/superadmin/admin-management", tags=["SuperAdmin Admin Router"])

from api.v1.superAdmin.routers.super_admin_event_management import superadmin_event_router
v1_router.include_router(superadmin_event_router, prefix="/superadmin/event-management", tags=["SuperAdmin Event Router"])

from api.v1.superAdmin.routers.super_admin_singleRegistration_management import superadmin_singleRegistration_management_router
v1_router.include_router(superadmin_singleRegistration_management_router, prefix="/superadmin/singleregistration-management", tags=["SuperAdmin Singleregistration management Router"])

from api.v1.superAdmin.routers.super_admin_teamRegistration_management import superadmin_teamRegistration_management_router
v1_router.include_router(superadmin_teamRegistration_management_router, prefix="/superadmin/teamregistration-management", tags=["SuperAdmin Teamregistration management Router"])

from api.v1.superAdmin.routers.super_admin_payment_management import superadmin_payment_management_router
v1_router.include_router(superadmin_payment_management_router, prefix="/superadmin/payment-management", tags=["SuperAdmin Payment management Router"])

from api.v1.superAdmin.routers.super_admin_student_management import superadmin_student_management_router
v1_router.include_router(superadmin_student_management_router, prefix="/superadmin/student-management", tags=["SuperAdmin Student management Router"])


from api.v1.superAdmin.routers.super_admin_superadmin_management import superadmin_superadmin_management_router
v1_router.include_router(superadmin_superadmin_management_router, prefix="/superadmin/superadmin-management", tags=["SuperAdmin Superadmin management Router"])

from api.v1.superAdmin.routers.super_admin_system_management import superadmin_system_management_router
v1_router.include_router(superadmin_system_management_router, prefix="/superadmin/system-management", tags=["SuperAdmin System management Router"])


from api.v1.superAdmin.routers.super_admin_notification_management import superadmin_notification_management_router
v1_router.include_router(superadmin_notification_management_router, prefix="/superadmin/notification-management", tags=["SuperAdmin Notification management Router"])


