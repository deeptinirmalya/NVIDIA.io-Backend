import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from core.config import settings
from db.models.auth import User, EmailVerification, RefreshToken, LoginHistory, TokenBlacklist
from db.models.event import Event
from db.models.registration import Registration
from db.models.team import Team
from db.models.team_member import TeamMember
from db.models.payment import Payment
from db.models.audit_log import AuditLog

async def init_db():

    client = AsyncIOMotorClient(settings.MONGODB_URL, tlsCAFile=certifi.where())
    database = client[settings.MONGODB_DB_NAME]

    # Remove legacy unique indexes that incorrectly indexed null Razorpay IDs.
    payments_collection = database[Payment.Settings.name]
    index_information = await payments_collection.index_information()
    expected_partial_filters = {
        "razorpay_order_id": {"razorpay_order_id": {"$type": "string"}},
        "razorpay_payment_id": {"razorpay_payment_id": {"$type": "string"}},
    }
    for index_name, index in index_information.items():
        keys = index.get("key", [])
        indexed_field = next(
            (field for field, expected_keys in (
                ("razorpay_order_id", [("razorpay_order_id", 1)]),
                ("razorpay_payment_id", [("razorpay_payment_id", 1)]),
            ) if keys == expected_keys),
            None,
        )
        if (
            indexed_field
            and index_name != "_id_"
            and (
                not index.get("unique")
                or index.get("partialFilterExpression")
                != expected_partial_filters[indexed_field]
            )
        ):
            await payments_collection.drop_index(index_name)


    await init_beanie(
        database=database,
        document_models=[
            User,
            EmailVerification,
            RefreshToken,
            LoginHistory,
            TokenBlacklist,
            Event,
            Registration,
            Team,
            TeamMember,
            Payment,
            AuditLog
        ]
    )
