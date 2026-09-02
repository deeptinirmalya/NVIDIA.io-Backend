from sqlalchemy import select
from sqlalchemy.orm import Session
from db.base import User

def get_user_by_id(db: Session, user_id: int):
    """Fetches a single user by their ID."""
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

def get_users_filtered(db: Session, limit: int, offset: int):
    """
    Fetches users with age > 18 using SQLAlchemy 2.0 syntax.
    Returns a list of dictionaries (mappings).
    """
    return db.execute(
        select(User.name, User.age, User.last_login)
        .where(User.age > 18)
        .limit(limit)
        .offset(offset)
    ).mappings().all()