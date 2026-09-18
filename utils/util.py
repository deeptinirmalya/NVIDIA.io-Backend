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
import json
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
import cloudinary
import cloudinary.uploader

from core.config import settings


class EncryptionError(ValueError):
    """Raised when encrypted data cannot be created or decoded."""


def _get_fernet(secret_key: bytes | str) -> Fernet:
    key = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
    if not isinstance(key, bytes):
        raise TypeError("Encryption key must be bytes or string")

    try:
        return Fernet(key)
    except ValueError:
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
        return Fernet(derived_key)


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



def encode_dict(data: dict, secret_key: bytes | str) -> str:
    if not isinstance(data, dict):
        raise EncryptionError("Encryption data must be a dictionary")

    try:
        json_data = json.dumps(data).encode("utf-8")
        return _get_fernet(secret_key).encrypt(json_data).decode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise EncryptionError("Unable to encrypt data") from exc


def decode_dict(secret_code: str, secret_key: bytes | str) -> dict:
    if not isinstance(secret_code, str):
        raise EncryptionError("Encrypted data must be a string")

    try:
        decrypted_data = _get_fernet(secret_key).decrypt(secret_code.encode("utf-8"))
        data = json.loads(decrypted_data.decode("utf-8"))
    except (InvalidToken, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise EncryptionError("Unable to decrypt data") from exc

    if not isinstance(data, dict):
        raise EncryptionError("Decrypted data must be a dictionary")

    return data
# ======================================================================

def mail_service(subject, body, receiver_email, priority, is_real = True):
    if not is_real:
        mailtrap_service(subject, body, receiver_email)
    else:
        send_wl_mail(subject, body, receiver_email, priority)



