from datetime import datetime, timezone
from sqlalchemy.orm import Session
from crud.repository import get_user_by_id

def login_user(db: Session, user_id: int):
    """
    Updates the last_login timestamp for a user.
    Includes proper rollback and error handling.
    """
    user = get_user_by_id(db, user_id)

    if not user:
        return {"message": "User not found", "user_id": user_id}

    user.last_login = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Login updated", "user_id": user_id}