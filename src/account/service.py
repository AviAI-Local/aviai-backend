import re
from typing import Dict, Optional, List
import uuid
import bcrypt
from fastapi import HTTPException
from sqlalchemy import func
from database.model import Account, ConversationHistory, Session as DBSession, Scenario


class AccountService:
    def __init__(self, db: DBSession):
        self.db = db

    def validate_email_format(self, email: str) -> bool:
        """Validate if the string follows RMIT email pattern."""
        # Check if it ends with @rmit.edu.vn
        return email.endswith('@rmit.edu.vn')
    
    def validate_student_email_format(self, email: str) -> bool:
        """Validate if the string follows student email pattern: s + 7 digits + @rmit.edu.vn."""
        if not email.endswith('@rmit.edu.vn'):
            return False
        
        # Extract the local part (before @rmit.edu.vn)
        local_part = email[:-12]  # Remove '@rmit.edu.vn' (12 characters including @)
        
        # Check if it starts with 's' followed by exactly 7 digits
        student_pattern = r'^s\d{7}$'
        return re.match(student_pattern, local_part) is not None
    
    def validate_account_data(self, account_data: Dict) -> None:
        """Validate account data and raise appropriate exceptions."""
        # Validate required fields
        required_fields = ["account_name", "password", "role", "user_name", "avatar", "major"]
        for field in required_fields:
            if field not in account_data or account_data[field] in (None, ""):
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate role
        if account_data["role"].lower() not in ["admin", "student"]:
            raise HTTPException(status_code=400, detail="Role must be either 'admin' or 'student'")
        
        # Validate password length
        if len(account_data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Validate account_name follows email pattern
        if not self.validate_email_format(account_data["account_name"]):
            raise HTTPException(status_code=400, detail="Account name must be a valid RMIT email address (@rmit.edu.vn)")
        
        # Validate student email format if role is student
        if account_data["role"].lower() == "student":
            if not self.validate_student_email_format(account_data["account_name"]):
                raise HTTPException(
                    status_code=400, 
                    detail="Student account name must follow pattern: s + 7 digits + @rmit.edu.vn (e.g., s1234567@rmit.edu.vn)"
                )
            
    def check_duplicate_account(self, account_name: str) -> None:
        """Check for duplicate account and raise exception if found."""
        if self.get_account_by_name(account_name):
            raise HTTPException(status_code=400, detail="Account with this account_name already exists")
    
    def create_account_with_validation(self, account_data: Dict) -> Dict:
        """Create account with full validation and return response data."""
        # Validate input data
        self.validate_account_data(account_data)
        
        # Check for duplicates
        self.check_duplicate_account(account_data["account_name"])
        
        # Create account
        account = self.create_account(account_data)
        
        # Return response data
        return {
            "message": "Create account success",
            "account": {
                "account_id": account.account_id,
                "account_name": account.account_name,
                "role": account.role.value
            }
        }
    
    def create_account(self, account_data: Dict) -> Account:
        account = Account(
            account_id=str(uuid.uuid4()),
            account_name=account_data["account_name"],
            password=self._hash_password(account_data["password"]),
            role=account_data["role"].upper(),
            user_name=account_data.get("user_name"),
            avatar=account_data.get("avatar"),
            major=account_data.get("major")
        )
        
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account
            
    def get_account(self, account_id: str) -> Optional[Account]:
        return self.db.query(Account).filter(Account.account_id == account_id).first()
    
    def get_account_by_id(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.db.query(Account).filter(Account.account_id == account_id).first()
    
    def get_all_accounts(self) -> List[Account]:
        return self.db.query(Account).all()
    
    def delete_account(self, account_id: str) -> bool:
        account = self.get_account(account_id)
        if not account:
            return False

        # RESTRICT: block delete if there are dependent records
        if account.sessions or account.notes or account.created_usecases:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete account. It has sessions, notes, or usecases. Delete or reassign them first."
            )

        try:
            self.db.delete(account)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="An error occurred while deleting the account"
            )

    def get_account_by_name(self, account_name: str) -> Optional[Account]:
        """Get account by name (case-insensitive)."""
        return self.db.query(Account).filter(func.lower(Account.account_name) == account_name.lower()).first()

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8')) 
    
    def authenticate_user(self, account_name: str, plain_password: str) -> Optional[Account]:
        """Authenticate user with account name and password."""
        user = self.get_account_by_name(account_name)
        if not user:
            return None
        if not self.verify_password(plain_password, user.password):
            return None
        return user

    def update_account_fields(self, account_id: str, updates: dict) -> Account:
        allowed_fields = {"account_name", "password", "role", "user_name", "avatar", "major"}
        account = self.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        for field, value in updates.items():
            if field not in allowed_fields:
                raise HTTPException(status_code=400, detail=f"Field '{field}' cannot be updated.")
            if field == "password":
                value = self._hash_password(value)
            setattr(account, field, value)
        self.db.commit()
        self.db.refresh(account)
        return account
    
    