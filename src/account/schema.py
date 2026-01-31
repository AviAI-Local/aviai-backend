from typing import Optional
from pydantic import BaseModel

class AccountResponse(BaseModel):
    account_id: str
    account_name: str
    password: str
    role: Optional[str] = None
    user_name: Optional[str] = None
    avatar: Optional[str] = None
    major: Optional[str] = None

account_example = {
    "account_id": "user_001",
    "account_name": "s1234567@rmit.edu.vn",
    "password": "$2b$12$eIX5Z8Q1Qb6QJZQ1Qb6QJ.ZQ1Qb6QJZQ1Qb6QJZQ1Qb6QJZQ1Qb6QJ",  # example bcrypt hash
    "role": "student",
    "user_name": "John Doe",
    "avatar": "https://example.com/avatar.jpg",
    "major": "Computer Science"
}

account_request_example = {
    "account_name": "s1234567@rmit.edu.vn",
    "password": "plaintextpassword",
    "role": "student",
    "user_name": "John Doe",
    "avatar": "https://example.com/avatar.jpg",
    "major": "Computer Science"
}