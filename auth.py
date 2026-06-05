from fastapi import Header, HTTPException, Depends
from repository import users as user_repo

def require_role(role: str):
    async def verifier(authorization: str = Header(...)):
        token = authorization.replace("Bearer ", "")
        username = await user_repo.get_username_by_token(token)
        if not username:
            raise HTTPException(403, "Invalid token")
        user = await user_repo.get_user(username)
        if not user or user.role != role:
            raise HTTPException(403, "Forbidden")
        return user
    return verifier