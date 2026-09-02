import requests
from mailtrap import Mail, Address, MailtrapClient
from datetime import timezone
from worker.tasks import send_wl_mail
import secrets
import string
import io
import pyotp
import qrcode


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



def generate_random_event_code(length: int = 6) -> str:
    letters = string.ascii_uppercase
    digits = string.digits
    pool = letters + digits

    while True:
        code = "".join(secrets.choice(pool) for _ in range(length))

        if any(c.isalpha() for c in code) and any(c.isdigit() for c in code):
            
            return code






# ==============================================================================
# def generate_totp_qr(
#     account_name: str,
#     issuer_name: str = "MyApp",
# ) -> tuple[str, bytes]:

#     secret = pyotp.random_base32()

#     # Create the provisioning URI
#     provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
#         name=account_name,
#         issuer_name=issuer_name,
#     )

#     # Generate QR Code
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_M,
#         box_size=10,
#         border=4,)

#     qr.add_data(provisioning_uri)
#     qr.make(fit=True)

#     image = qr.make_image(fill_color="black", back_color="white")

#     buffer = io.BytesIO()
#     image.save(buffer, format="PNG")

#     return secret, buffer.getvalue()


# secret, qr_bytes = generate_totp_qr(
#     account_name="user@example.com",
#     issuer_name="HireNest"
# )

# Encrypt and store `secret` in your database.

# Return `qr_bytes` from your FastAPI endpoint.


def verify_totp(secret: str, user_otp: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(user_otp, valid_window=1)

# ======================================================================

def mail_service(subject, body, receiver_email, priority, is_real = True):
    if not is_real:
        mailtrap_service(subject, body, receiver_email)
    else:
        send_wl_mail(subject, body, receiver_email, priority)


