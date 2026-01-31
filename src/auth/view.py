from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from account.schema import AccountResponse
from auth.dependencies import get_current_user
from auth.service import AuthService
from database.config import get_db
from database.model import Session

router = APIRouter()

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate user and return access token."""
    service = AuthService(db)
    return service.authenticate_user_with_token(form_data)

@router.get("/me", response_model=AccountResponse)
async def read_users_me(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user profile."""
    service = AuthService(db)
    return service.get_user_profile(current_user)

