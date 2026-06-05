from dataclasses import dataclass, field
from uuid import uuid4
import hashlib

@dataclass
class User:
    username: str
    password_hash: str
    role: str
    id: str = field(default_factory=lambda: str(uuid4()))

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()