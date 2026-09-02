# db/session.py
from typing import AsyncGenerator
from fastapi import HTTPException
from beanie import Document
from pymongo.errors import PyMongoError

from core.config import settings
from db.models.auth import User

async def get_tx_session() -> AsyncGenerator:
    # if settings.PYTHON_ENV == "development":
    #     yield None
    #     return

    client = User.get_motor_collection().database.client
    
    async with await client.start_session() as session:
        async with session.start_transaction():
            try:
                yield session
            except (HTTPException, PyMongoError, Exception) as exc:
                if session.in_transaction:
                    await session.abort_transaction()
                raise exc