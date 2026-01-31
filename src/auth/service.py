from datetime import datetime, timedelta, timezone
import os
import re
from typing import Dict
from fastapi import Depends, HTTPException, status
import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from account.service import AccountService
from auth.utils import create_access_token
from database.model import Account, Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = os.environ.get("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.account_service = AccountService(db)

    def validate_email_format(self, email: str) -> bool:
        """Validate if the string follows email pattern."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None
    
    def authenticate_user_with_token(self, form_data: OAuth2PasswordRequestForm) -> Dict:
        """Authenticate user and return access token."""
        # Validate email format
        if not self.validate_email_format(form_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be a valid email address",
            )
        
        user = self.account_service.authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.account_id}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    
    def get_user_profile(self, current_user: Account) -> Dict:
        """Get user profile data."""
        if hasattr(current_user, 'to_dict'):
            return current_user.to_dict()
        return current_user
    
