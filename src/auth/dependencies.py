# FastAPI-specific injection functions

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from account.service import AccountService
from database.config import get_db
from database.model import Account, Session

ALGORITHM = os.environ.get("ALGORITHM")
SECRET_KEY = os.environ.get("SECRET_KEY")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
    ) -> Account:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            account_id = payload.get("sub")
            if account_id is None:
                raise credentials_exception
        except InvalidTokenError:
            raise credentials_exception
        user = AccountService(db).get_account_by_id(account_id)
        if user is None:
            raise credentials_exception
        return user 