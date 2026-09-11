import requests
from mailtrap import Mail, Address, MailtrapClient
from datetime import timezone
from zoneinfo import ZoneInfo
from worker.tasks import send_wl_mail
import secrets
import string
import io
import pyotp
import qrcode
import cloudinary
import cloudinary.uploader

from core.config import settings


def mailtrap_service(subject, body, to_email):
    mail = Mail(
    sender=Address(email="hello@deepti.com", name="Mailtrap Test"),
    to=[Address(email=to_email)],
    subject=subject,
    text=body,
    category="Integration Test")

    client = MailtrapClient(
        token="e66c7fa96d3f6a8728a919234e4fa62c",
        sandbox=True,
        inbox_id=4538769
    )

    response = client.send(mail)
    print(f"✅ message send to mail trap with response {response} \n")



def ensure_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt



IST = ZoneInfo("Asia/Kolkata")
def ensure_aware_ist(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt



def generate_random_event_code(length: int = 6) -> str:
    letters = string.ascii_uppercase
    digits = string.digits
    pool = letters + digits

    while True:
        code = "".join(secrets.choice(pool) for _ in range(length))

        if any(c.isalpha() for c in code) and any(c.isdigit() for c in code):
            
            return code



cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)
# ======================================================================

def mail_service(subject, body, receiver_email, priority, is_real = True):
    if not is_real:
        mailtrap_service(subject, body, receiver_email)
    else:
        send_wl_mail(subject, body, receiver_email, priority)



