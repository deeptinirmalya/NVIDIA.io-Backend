from sqlalchemy.ext.asyncio import AsyncSession
import random
from sqlalchemy import select
from fastapi import HTTPException



from utils import util, auth_util
from engine.cache import set_value, get_value, delete_value


from db.models.auth import User, UserRole

# request for a key

async def request_code_to_superadmin(reason: str, user_id: int, db: AsyncSession):
	normalized_reason = reason.upper()
	if  normalized_reason not in ["ADD_NEW_SUPER_ADMIN", "ADD_NEW_ADMIN"]:
		raise HTTPException(status_code=404, detail="Invalid reasom for requesting a code")
	
	email = (await db.execute(select(User.email).where(User.id == user_id, User.role == UserRole.SUPERADMIN))).scalar_one_or_none()
	
	if email is None:
				return {
			"success": False,
			"message": "No super admin found with this user ID",
		}
	
	# email = "test@gmail.com"
	cache_key = f"super_admin_code_by{email}_for_{reason}"
	existing_code = await get_value(cache_key)

	if existing_code is not None:
		return {
			"success": False,
			"message": "Code already exists",
		}

	code = random.randint(100000, 999999)
	await set_value(cache_key, code, expire=300)
	body = f"""
	<html>
		<body>
			<p style="font-size: 18px; font-family: sans-serif;">
				<strong>Reason:</strong> {reason}<br><br>
				<strong>By:</strong> {email}<br><br>
				<strong>Code:</strong> <b style="font-size: 24px; color: #333;">{code}</b>
			</p>
		</body>
	</html>
	"""
	
	await util.mail_service(subject="Code Request from SRJN5.o", body=body, receiver_email=["deeptilapy@gmail.com"], priority=9, is_real=True)

	return {
		"success": True,
		"message": "Code created successfully",
	}


async def verify_superadmin_code(reason: str, user_id: int, db: AsyncSession, code: int):

	email = (await db.execute(select(User.email).where(User.id == user_id,  User.role == UserRole.SUPERADMIN))).scalar_one_or_none()
	
	if email is None:
				return {
			"success": False,
			"message": "No super admin found with this user ID",
		}

	# email = "test@gmail.com"
	cache_key = f"super_admin_code_by{email}_for_{reason}"

	existing_code = await get_value(cache_key)
	
	if existing_code is None:
		return {
			"success": False,
			"message": "Invalid code or code not present",
		}

	if str(code).strip() != str(existing_code).strip():
		return {
			"success": False,
			"message": "Invalid code",
		}

	# Delete the key after successful verification to prevent reuse
	await delete_value(cache_key)

	return {
		"success": True,
		"message": "valid code"
	}