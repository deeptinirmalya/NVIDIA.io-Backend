import re
import hashlib
from datetime import datetime, UTC
from core.config import settings
from zoneinfo import ZoneInfo
import base64
import time
import io
import hashlib
import pyotp
import qrcode
from qrcode.image.pil import Image, PilImage
from cryptography.fernet import Fernet
import os

from core.config import settings




def get_now_utc():
    return datetime.now(UTC)

def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

IST = ZoneInfo("Asia/Kolkata")
def get_now_ist():
    return datetime.now(IST)



# =================== Argon2 = ===========================


from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher(
    memory_cost=settings.ARGON2_RAM_SIZE,   
    time_cost=3,
    parallelism=2
    )

def hash_password(password: str) -> str: 
    return ph.hash(password)

def verify_password(pwd: str, hashed: str) -> bool: 
    try:
        return ph.verify(hashed, pwd)
    except (VerifyMismatchError, Exception):
        return False




def validate_password(password: str):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def generate_fingerprint(ip: str, user_agent: str) -> str:
    data = f"{ip}|{user_agent}"
    return hashlib.sha256(data.encode()).hexdigest()

def calculate_risk(current: dict, history: list):

    if not history: return 0 
    
    score = 0
    last = history[0]
    
    known_ips = {h['ip_address'] for h in history}
    if current['ip'] not in known_ips: score += 30
    

    known_uas = {h['user_agent'] for h in history}
    if current['user_agent'] not in known_uas: score += 40

    if current['country'] != last['country']:
        score += 50

        time_diff = (get_now_utc() - as_utc(last['login_at'])).total_seconds() / 3600
        if time_diff < 2:
            score += 100
            
    return min(score, 100)



def calculate_risk_refresh(current: dict, history: list):

    if not history: 
        return 0 
    
    score = 0
    last = history[-1] 
    
    known_ips = {h.get('ip_address') for h in history if h.get('ip_address')}
    if current.get('ip') not in known_ips: 
        score += 30
    

    known_uas = {h.get('user_agent') for h in history if h.get('user_agent')}
    if current.get('user_agent') not in known_uas: 
        score += 40


    current_country = current.get('country')
    last_country = last.get('country')
    
    if current_country and last_country and current_country != last_country:
        score += 50
        

        last_login = last.get('login_at')
        if last_login:
            time_diff = (get_now_utc() - as_utc(last_login)).total_seconds() / 3600
            if time_diff < 2:
                score += 100 
            
    return min(score, 100)






global_secret_code = settings.ENCRYPTION_KEY

def derive_key_fast(salt: bytes) -> bytes:
    raw_key = hashlib.pbkdf2_hmac(
        'sha256',
        global_secret_code.encode('utf-8'),
        salt,
        iterations=10_000,
        dklen=32
    )
    return base64.urlsafe_b64encode(raw_key)



async def generate_totp_qr(account_holder_name: str, platform_name: str = "NVIDIA.io") -> tuple[str, str]:
    
    secret = pyotp.random_base32()

    #====================== enc ==========================
    salt = os.urandom(16)
    key = derive_key_fast(salt)
    f = Fernet(key)
    ciphertext = f.encrypt(secret.encode('utf-8'))
    payload = salt + ciphertext
    encript_secret =  base64.b64encode(payload).decode('utf-8')
    #====================== enc ==========================

    algorithm = hashlib.sha256
    totp = pyotp.TOTP(secret, digest=algorithm)
    provisioning_uri = totp.provisioning_uri(
        name=account_holder_name,
        issuer_name=platform_name,
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    # Add data URI prefix here:
    raw_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    qr_base64 = f"data:image/png;base64,{raw_b64}"

    return secret, encript_secret, qr_base64





async def verify_totp(enc_secret: str, user_code: str,) -> bool:
    algorithm = hashlib.sha256
    # =================================== dec ==================================
    payload = base64.b64decode(enc_secret.encode('utf-8'))
    salt = payload[:16]
    ciphertext = payload[16:]
    key = derive_key_fast(salt)
    f = Fernet(key)
    plaintext = f.decrypt(ciphertext)
    secret = plaintext.decode('utf-8')
    # =================================== dec ==================================
    totp = pyotp.TOTP(secret, digest=algorithm)
    clean_code = str(user_code).strip().replace(" ", "").replace("-", "")
    return totp.verify(clean_code, valid_window=1)


async def current_totp_code(enc_secret: str):
    algorithm = hashlib.sha256
    # ========================== dec ========================================
    payload = base64.b64decode(enc_secret.encode('utf-8'))
    salt = payload[:16]
    ciphertext = payload[16:]
    key = derive_key_fast(salt)
    f = Fernet(key)
    plaintext = f.decrypt(ciphertext)
    secret = plaintext.decode('utf-8')
    # ========================== dec ========================================

    totp = pyotp.TOTP(secret, digest=algorithm)
    otp = totp.now()
    remaining = totp.interval - (time.time() % totp.interval)

    return otp, remaining















# secret, encript_secret, qr_b64 = generate_totp_qr("deepti2", "NVDIA.io")

# print(f"\nSecret: {secret}")
# print(f"\nENC Secret: {encript_secret}")
# print(f"\nBase 64 URI: {qr_b64}")


# # secret = input("secret: ")
# secret = "y/c/heQd9KiHKH0BDRrYfGdBQUFBQUJxcjNfR2tpLURuZ2pFWlQzb0x4UVhxQU04NS1rb0oxX0ZQZC1XRjQzYjV3NVZPU2dwZDAzQmxyMTBYZGd6MTNRWUJta2RTMzJBaFBrQUVqWTFfMU5QeVhpUXdraFNZQ0dTb3FTTjdrRy1kTEc2bGFKemhYV200QWswcC1pRzl1Z1hUdzBN"
# otp = input("\n\nuser otp:")

# if verify_totp(secret, otp):
#     print("PASS verified")
# else:
#     print("fail")


