from typing import Dict, List
from fastapi import APIRouter, Body, Depends, HTTPException
from account.service import AccountService
from database.config import get_db
from database.model import Session
from account.schema import AccountResponse, account_example, account_request_example

router = APIRouter()

@router.post(
    "/create",
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": account_example}}}}}},
    description="""
    Create a new account. The 'role' field only accepts two values: 'admin' or 'student'.

    **Email Format Requirements:**
    - All accounts must use @rmit.edu.vn domain
    - Student accounts must follow pattern: s + 7 digits + @rmit.edu.vn (e.g., s1234567@rmit.edu.vn)
    - Admin accounts can use any valid RMIT email format

    **Example request body for student:**
    ```json
    {
    "account_name": "s1234567@rmit.edu.vn",
    "password": "plaintextpassword",
    "role": "student"
    }
    ```

    **Example request body for admin:**
    ```json
    {
    "account_name": "admin@rmit.edu.vn",
    "password": "plaintextpassword",
    "role": "admin"
    }
    ```
    """
)
async def create_account(
    account_data: Dict = Body(..., examples=[account_request_example]),
    db: Session = Depends(get_db)
): 
    service = AccountService(db)
    return service.create_account_with_validation(account_data)

@router.get(
    "/",
    response_model=List[AccountResponse],
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": account_example}}}}}}
)
async def get_all_account(db: Session = Depends(get_db)):
    """Get all available accounts."""
    service = AccountService(db)
    return service.get_all_accounts()

router.get(
    "/{account_id}",
    response_model=AccountResponse,
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": account_example}}}}}}
)
async def get_account_by_id(account_id: str, db: Session = Depends(get_db)):
    """Get a specific account by ID"""
    service = AccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account.to_dict()

@router.patch(
    "/update/{account_id}",
    response_model=AccountResponse,
    responses={200: {"content": {"application/json": {"examples": {"default": {"value": account_example}}}}}},
    description="Update multiple fields of an account at once"
)
async def update_account(
    account_id: str, 
    updates: dict = Body(..., examples={            
        "user_name": "Jane Doe",
        "avatar": "https://example.com/avatar2.jpg",
        "major": "Business Analytics"
    }), 
    db: Session = Depends(get_db)
):
    """Update multiple fields of an account at once."""
    service = AccountService(db)
    update_account = service.update_account_fields(account_id, updates)
    if not update_account:
        raise HTTPException(status_code=404, detail="Account not found")
    return update_account.to_dict()

@router.delete("/delete/{account_id}")
async def delete_account(account_id: str, db: Session = Depends(get_db)):
    """Delete an account."""
    service = AccountService(db)
    if not service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Account deleted successfully"}

