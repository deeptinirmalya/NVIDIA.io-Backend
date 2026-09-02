# 1. Middleware for VPS (Extracts Real User IP & Agent)
# On your VPS, Cloudflare passes the true client IP in the CF-Connecting-IP header. This middleware extracts it and stores it inside request.state so your endpoint handlers can use it easily.

# Python
# from fastapi import FastAPI, Request
# from starlette.middleware.base import BaseHTTPMiddleware
# from typing import Optional

# app = FastAPI()

# class VPSCloudflareMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         # 1. Extract Real Client IP attached by Cloudflare
#         # Fallback to direct client IP if header is missing
#         client_ip: Optional[str] = request.headers.get("cf-connecting-ip")
#         if not client_ip:
#             client_ip = request.client.host if request.client else "Unknown"

#         # 2. Extract User-Agent header
#         user_agent: str = request.headers.get("user-agent", "Unknown")

#         # 3. Store extracted variables in Request State for endpoint access
#         request.state.client_ip = client_ip
#         request.state.user_agent = user_agent

#         # Process the request
#         response = await call_next(request)
#         return response

# # Register the middleware in FastAPI
# app.add_middleware(VPSCloudflareMiddleware)


# # Example Route: Accessing the extracted values
# @app.get("/customer/profile")
# async def get_customer_profile(request: Request):
#     return {
#         "message": "Welcome Customer",
#         "client_ip": request.state.client_ip,
#         "user_agent": request.state.user_agent,
#     }


# ============== how to use it in blueprint end point means routes ===================================
###  dependencis file
# from fastapi import Request

# def get_client_ip(request: Request) -> str:
#     return getattr(request.state, "client_ip", "Unknown")

# def get_user_agent(request: Request) -> str:
#     return getattr(request.state, "user_agent", "Unknown")

# #### route files
# from fastapi import APIRouter, Depends
# from dependencies import get_client_ip, get_user_agent

# router = APIRouter(prefix="/customer")

# @router.get("/profile")
# async def get_customer_profile(
#     client_ip: str = Depends(get_client_ip),
#     user_agent: str = Depends(get_user_agent)
# ):
#     return {
#         "real_ip": client_ip,
#         "user_agent": user_agent
#     }


# ======================================================================================================================================================================================================

# 2. Middleware for Render (Verifies Secret Header + Extracts IP & Agent)
# On Render, the middleware enforces security first. If a request comes without the correct X-Via-Cloudflare token, it immediately returns an HTTP 403 Forbidden error, stopping unauthorized visitors from accessing your Render backend directly.

# Python
# from fastapi import FastAPI, Request, status
# from fastapi.responses import JSONResponse
# from starlette.middleware.base import BaseHTTPMiddleware
# import hmac

# app = FastAPI()

# # Configuration: Store your actual secret token here (or load from environment variables)
# SECRET_HEADER_NAME = "x-via-cloudflare"
# SECRET_HEADER_VALUE = "your_super_secret_token_12345"

# class RenderSecurityMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         # 1. Extract the secret header added by Cloudflare Transform Rules
#         incoming_secret = request.headers.get(SECRET_HEADER_NAME)

#         # 2. Validate secret header using secure constant-time comparison
#         if not incoming_secret or not hmac.compare_digest(incoming_secret, SECRET_HEADER_VALUE):
#             return JSONResponse(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 content={"detail": "Forbidden: Direct access to origin server is blocked."}
#             )

#         # 3. Extract Real Client IP & User-Agent
#         client_ip = request.headers.get("cf-connecting-ip")
#         if not client_ip:
#             client_ip = request.client.host if request.client else "Unknown"

#         user_agent = request.headers.get("user-agent", "Unknown")

#         # 4. Attach extracted variables to Request State
#         request.state.client_ip = client_ip
#         request.state.user_agent = user_agent

#         response = await call_next(request)
#         return response

# # Register the middleware in FastAPI
# app.add_middleware(RenderSecurityMiddleware)


# # Example Routes
# @app.get("/employee/dashboard")
# async def employee_dashboard(request: Request):
#     return {
#         "status": "Authenticated via Cloudflare",
#         "client_ip": request.state.client_ip,
#         "user_agent": request.state.user_agent,
#     }


# ====================================================================================================================================

# Loophole 1: The "Other Cloudflare Account" Attack (VPS)
# The Threat
# Your UFW firewall allows any connection coming from Cloudflare's IP range.
# An attacker can create a free Cloudflare account, set up a domain (e.g., hacker.com), and point hacker.com directly to your VPS IP address.

# Because hacker.com routes through Cloudflare's servers, your UFW firewall sees a valid Cloudflare IP and allows the TCP connection straight to Nginx!

# The Seal (Nginx Host Verification)
# You must configure Nginx to reject any request that does not specifically match your legitimate domain name (vibelist.in).

# In your Nginx config, add a default fallback block that silently drops unmatched traffic:

# Nginx
# # 1. Default fallback: Drop any request targeting raw IP or unknown domain
# server {
#     listen 80 default_server;
#     listen 443 ssl default_server;
#     server_name _;
#     return 444; # Special Nginx code: Closes connection without sending a response
# }

# # 2. Your legitimate app block
# server {
#     listen 80;
#     server_name api.vibelist.in customer.vibelist.in;
#     # ... your normal proxy pass to FastAPI
# }

# Loophole 2: IPv6 Bypass (VPS)
# The Threat
# If your VPS provider (DigitalOcean, AWS, Linode) assigns both an IPv4 and an IPv6 address to your server, but you only added Cloudflare’s IPv4 ranges to ufw, a hacker can bypass your firewall completely by targeting your server's direct IPv6 address!

# The Seal (Add Cloudflare IPv6 Ranges)
# Ensure IPv6 rules are added to ufw alongside IPv4:

# Bash
# # Add Cloudflare IPv6 ranges to UFW
# sudo ufw allow from 2606:4700::/32 to any port 80,443 proto tcp
# sudo ufw allow from 2803:f800::/32 to any port 80,443 proto tcp
# sudo ufw allow from 2405:b500::/32 to any port 80,443 proto tcp
# sudo ufw allow from 2405:8100::/32 to any port 80,443 proto tcp
# sudo ufw allow from 2a06:98c0::/29 to any port 80,443 proto tcp
# sudo ufw allow from 2c0f:f240::/32 to any port 80,443 proto tcp
# (Or disable IPv6 on your VPS entirely if you do not use it).

# Loophole 3: Transform Rule Setting on Cloudflare (Render)
# The Threat
# An attacker discovers your Render backend URL (employee.onrender.com) and tries sending a fake header X-Via-Cloudflare: guessed_token.

# If your Cloudflare Transform Rule is set to "Add static" instead of "Set static", Cloudflare will append a second header rather than overwriting the client's input.

# The Seal (Use "Set Static")
# When setting up the Request Header Modification rule in Cloudflare Transform Rules:

# Select Set static (NOT "Add static").

# "Set static" forces Cloudflare to overwrite any existing X-Via-Cloudflare header sent by the client, neutralizing any client header-spoofing attempt before the request reaches Render.

# The GoalYou want to secure your Render app (employee.onrender.com) so that ONLY requests coming through Cloudflare are allowed. You do this by making Cloudflare attach a secret key header:X-Via-Cloudflare: my_secret_123The Attack ScenarioA hacker finds out your direct Render backend address: [https://employee.onrender.com](https://employee.onrender.com).
# If the hacker opens Postman or cURL on their laptop and manually sends a request directly to Render with the header:X-Via-Cloudflare: my_secret_123If they guess or steal your secret key, Render's Python code would accept it!Even worse: What if the hacker sends their fake request through Cloudflare, hoping Cloudflare passes their fake header to Render?The Vulnerability (If Misconfigured in Cloudflare)When setting up Cloudflare Transform Rules, Cloudflare gives you options on how to handle headers:  ❌ Scenario A: What happens if Cloudflare "Appends" / "Adds" headers?If a hacker sends a request through Cloudflare with a fake header: X-Via-Cloudflare: WRONG_KEYThe hacker's request reaches Cloudflare carrying X-Via-Cloudflare: WRONG_KEY.Cloudflare's rule appends your secret key to the request.  The request arrives at Render with TWO values or a merged list:X-Via-Cloudflare: WRONG_KEY, my_secret_123When your Python middleware reads request.headers.get("x-via-cloudflare"), it might get confused, read WRONG_KEY, fail the check, or behave unpredictably.The Fix: "Set Static"✅ Scenario B: Using "Set Static" (The Secure Way)In Cloudflare Transform Rules, you choose Set static instead of adding/appending:  The hacker sends a request carrying X-Via-Cloudflare: WRONG_KEY.Cloudflare sees Set static. It wipes out/overwrites any client-supplied X-Via-Cloudflare header.  Cloudflare replaces it with your official key: X-Via-Cloudflare: my_secret_123.The request arrives at Render with ONLY ONE clean, untampered header:X-Via-Cloudflare: my_secret_123


# ===========================================================================================================================================================================================================================

# ******************************** CROS ************************************************************************
# Can I set a rule in the API.example.in that I only accept request from only selected frontend url

# YES, absolutely. You can enforce this using two layers of security:

# Browser Layer (CORS) – Tells browsers to block unauthorized websites from calling your API.

# Server/Cloudflare Layer (Hard Origin Verification) – Drops non-browser tools (like curl, Postman, or malicious bots) trying to spoof requests to your API.

# Layer 1: Enforce Allowed Frontends via FastAPI (CORS Middleware)
# When a web browser makes a cross-origin request from [https://myfrontend.com](https://myfrontend.com) to [https://api.example.in](https://api.example.in), the browser automatically attaches an Origin header (Origin: [https://myfrontend.com](https://myfrontend.com)).

# FastAPI includes a built-in CORSMiddleware to restrict allowed origins.  
# davidmuraya.com

# Add this to your FastAPI Apps (VPS & Render):
# Python
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI()

# # Define ONLY the exact frontend URLs allowed to talk to this API
# ALLOWED_ORIGINS = [
#     "https://vibelist.in",
#     "https://www.vibelist.in",
#     "https://admin.vibelist.in", # Example secondary frontend
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=ALLOWED_ORIGINS,  # Blocks any origin NOT in this list
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE"],
#     allow_headers=["*"],
# )
# How Browser Security Works Here:
# If someone loads an attacker site ([https://evil-hacker.com](https://evil-hacker.com)) and tries to run fetch('[https://api.example.in](https://api.example.in)'), the browser sends a preflight request. FastAPI checks evil-hacker.com, sees it is not in ALLOWED_ORIGINS, and refuses to send the Access-Control-Allow-Origin header. The browser blocks the request completely.

# Layer 2: Hard Block at Cloudflare / Middleware (For Non-Browser Clients)
# CORS is enforced by web browsers. A hacker using curl or Postman can manually pass Origin: [https://vibelist.in](https://vibelist.in) to bypass browser-based CORS checks.

# To prevent non-browser scripts from faking the Origin header, add strict checking in your FastAPI Middleware or via Cloudflare WAF Rules.

# In Your FastAPI Custom Middleware:
# Python
# from fastapi import Request, status
# from fastapi.responses import JSONResponse

# # Add inside your existing custom middleware dispatch logic:

# ALLOWED_ORIGINS = {"https://vibelist.in", "https://www.vibelist.in"}

# origin = request.headers.get("origin")
# referer = request.headers.get("referer")

# # For state-changing operations (POST/PUT/DELETE), require a valid Origin/Referer
# if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
#     valid_origin = origin in ALLOWED_ORIGINS
#     valid_referer = referer and any(referer.startswith(o) for o in ALLOWED_ORIGINS)
    
#     if not (valid_origin or valid_referer):
#         return JSONResponse(
#             status_code=status.HTTP_403_FORBIDDEN,
#             content={"detail": "Access forbidden: Invalid or missing Origin domain."}
#         )
# Layer 3: Cloudflare WAF Rule (Block at the Edge)
# To block unauthorized traffic before it even touches your VPS or Render server, you can set a rule directly in Cloudflare:

# Go to Cloudflare Dashboard → Security → WAF → Custom Rules.

# Click Create Rule.

# Expression:

# Plaintext
# (http.request.method in {"POST" "PUT" "DELETE"} and not http.referer contains "vibelist.in" and not http.request.headers["origin"][0] in {"https://vibelist.in" "https://www.vibelist.in"})




# Domains & Routing:

# assets.example.in: R2 storage CDN (Inbound/Outbound attachments with UUIDs).

# api.example.in: FastAPI backend (Pointed to ngrok during local development).

# app.example.in: React frontend dashboard for agents.

# updates.example.in: AWS SES isolated domain for news@updates.example.in marketing emails.

# Email Senders:

# support@example.in: Inbound ticket creation + Outbound agent replies.

# notify@example.in: Transactional alerts, password resets, OTPs.

# news@updates.example.in: Marketing releases and announcements.