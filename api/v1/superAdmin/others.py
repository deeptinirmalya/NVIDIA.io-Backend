from sqlalchemy.ext.asyncio import AsyncSession
import random
from sqlalchemy import select



from utils import util, auth_util
from engine.cache import set_value, get_value


from db.models.auth import User

# request for a key

async def request_code_to_superadmin(reason: str, user_id: int, db: AsyncSession):
	
	# email = (await db.execute(select(User.email).where(User.id == user_id))).scalar_one_or_none()
	
	# if email is None:
	# 			return {
	# 		"success": False,
	# 		"message": "No super admin found with this user ID",
	# 	}
	email = "test@gmail.com"
	cache_key = f"super_admin_code_by{email}_for_{reason}"
	existing_code = await get_value(cache_key)

	if existing_code is not None:
		return {
			"success": False,
			"message": "Code already exists",
		}

	code = random.randint(100000, 999999)
	await set_value(cache_key, code, expire=300)
	body = f"Reason:- {reason}\nBy:- {email}\nCode:- {code}"
	
	util.mail_service("Code Request from SRJN5.o", body, "deeptilapy@gmail.com", 2)

	return {
		"success": True,
		"message": "Code created successfully",
	}


async def verify_superadmin_code(reason: str, user_id: int, db: AsyncSession, code: int):

	# email = (await db.execute(select(User.email).where(User.id == user_id))).scalar_one_or_none()
	
	# if email is None:
	# 			return {
	# 		"success": False,
	# 		"message": "No super admin found with this user ID",
	# 	}

	email = "test@gmail.com"
	cache_key = f"super_admin_code_by{email}_for_{reason}"

	existing_code = await get_value(cache_key)
	if existing_code is None:
		return {
			"success": False,
			"message": "Invalid code or code not present",
		}

	if code != existing_code:
		return {
			"success": False,
			"message": "Invalid code or code not present",
		}

	return {
		"success": True,
		"message": "valid code"
	}