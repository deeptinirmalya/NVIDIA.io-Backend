from fastapi import Request, status, requests, HTTPException
import httpx
from fastapi.responses import JSONResponse

def get_client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", "Unknown")

def get_user_agent(request: Request) -> str:
    return getattr(request.state, "user_agent", "Unknown")





