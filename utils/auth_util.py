import re
import hashlib
from datetime import datetime, UTC
from core.config import settings
from zoneinfo import ZoneInfo




def get_now_utc():
    return datetime.now(UTC)

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

        time_diff = (get_now_utc() - last['login_at']).total_seconds() / 3600
        if time_diff < 2:
            score += 100
            
    return score



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
            time_diff = (get_now_utc() - last_login).total_seconds() / 3600
            if time_diff < 2:
                score += 100 
            
    return score