from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from repository import users as user_repo
from domain.user import hash_password
import uuid


router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "client"

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(req: RegisterRequest):
    existing = await user_repo.get_user(req.username)
    if existing:
        raise HTTPException(400, "Username already exists")
    if req.role not in ("client", "waiter", "chef", "admin"):
        raise HTTPException(400, "Invalid role")
    await user_repo.create_user(req.username, req.password, req.role)
    return {"message": "User created", "username": req.username, "role": req.role}

@router.post("/login")
async def login(req: LoginRequest):
    user = await user_repo.get_user(req.username)
    if not user or user.password_hash != hash_password(req.password):  # нужно импортировать hash_password
        raise HTTPException(401, "Invalid credentials")
    token = str(uuid.uuid4())
    await user_repo.store_token(token, user.username)
    return {"token": token, "role": user.role, "username": user.username}