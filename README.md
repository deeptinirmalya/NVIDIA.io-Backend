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
