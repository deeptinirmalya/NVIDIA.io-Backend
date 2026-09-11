# Startup API

A professional FastAPI backend structure with modular routing, database session management, and high-grade security configuration.

## 🚀 Features
- **Modular Routing**: Organized by version (`/v1`) and module (`admin`, `auth`, `users`, `organigation`).
- **Database Support**: Built-in support for both Sync and Async SQLAlchemy sessions.
- **Security**: Pre-configured CORS, Security Headers, and Global Exception Handling.
- **Configuration**: Environment variable management using `.env` and Pydantic Settings.

## 🛠️ Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd app
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn sqlalchemy aiomysql asyncmy pymysql pydantic-settings python-dotenv
   ```

4. **Configure Environment**:
   Update the `.env` file with your database credentials and secret key.

5. **Run the application**:
   ```bash
   uvicorn main:app --reload
   ```

## 📂 Project Structure
- `api/`: API versioning and module routes.
- `core/`: Global configuration and security settings.
- `db/`: Database session management and base models.
- `main.py`: Application entry point.

## Participation and Response Flow

The event participation endpoint is:

```text
POST /participate/{event_id}/event
```

The endpoint delegates registration work through these layers:

```text
participate_on_event
   -> RegistrationService
         -> PaymentServices.check_idempotency_key
         -> PaymentCrudServices.initialize_single_starter_payment_entry
```

### Paid events

Paid events require the `Idempotency-Key` request header.

- If the key already exists, `check_idempotency_key()` returns a `JSONResponse` immediately. The registration service returns that same object, and the endpoint returns it directly to the client. The existing response status and body are preserved.
- If the key does not exist, the service creates the registration and payment record. Razorpay's synchronous SDK call is run with `asyncio.to_thread()` so it does not block the async event loop. The payment CRUD method returns the order ID, and the endpoint wraps it in a `201` response.

Every async layer must use `await`, and every intermediary function must use `return` when it needs to pass a result or response to its caller.

### Free events

The endpoint also returns the result of `check_or_create_single_free_registration()` directly. That service must explicitly return a response after creating the registration; otherwise the endpoint receives `None` and the client may receive a `null` response body.
