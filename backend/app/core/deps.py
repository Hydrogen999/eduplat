from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, Role

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_token(creds.credentials, "access")
    except ValueError:
        raise HTTPException(401, "Invalid token")
    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "User inactive")
    return user

def require_role(*roles: Role):
    async def _checker(user: Annotated[User, Depends(get_current_user)]):
        if user.role not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return _checker

CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN, Role.SUPER_ADMIN))]