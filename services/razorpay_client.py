import httpx
import razorpay

from core.config import settings


RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


razorpay_order_client = httpx.AsyncClient(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET
    ),
    timeout=10.0
)


async def create_razorpay_order(
    amount: int,
    participation_id: int,
    participation_type: str,
    event_id: int,
    user_id: int,
):
    if participation_type not in ("SINGLE", "TEAM"):
        raise ValueError("Unsupported participation type")

    payload = {
        "amount": amount * 100,
        "currency": "INR",
        "receipt": (
            f"single_participate_{participation_id}"
            if participation_type == "SINGLE"
            else f"team_participate_{participation_id}"
        ),
        "notes": {
            "participation_type": participation_type,
            "participation_id": str(participation_id),
            "event_id": str(event_id),
            "user_id": str(user_id),
        }
    }

    response = await razorpay_order_client.post(
        f"{RAZORPAY_BASE_URL}/orders",
        json=payload
    )

    response.raise_for_status()

    return response.json()