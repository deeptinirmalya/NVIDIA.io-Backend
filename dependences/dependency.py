from fastapi import Request, status, requests, HTTPException
import httpx
from fastapi.responses import JSONResponse

def get_client_ip(request: Request) -> str:
    client_ip = getattr(request.state, "client_ip", None)
    if client_ip:
        return client_ip
    return request.client.host if request.client else "Unknown"

def get_user_agent(request: Request) -> str:
    user_agent = getattr(request.state, "user_agent", None)
    return user_agent or request.headers.get("user-agent", "Unknown")





