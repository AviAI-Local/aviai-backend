from typing import Dict, List
import uuid
from fastapi import HTTPException
from rich.console import Console

from database.model import Account, PromptTemplate, Session as DBSession

console = Console()

class PromptService: 
    def __init__(self, db: DBSession):
        self.db = db

    def get_prompt(self, prompt_id: str) -> PromptTemplate:
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.template_id == prompt_id
        ).first()

        return prompt if prompt else None

    def get_prompt_by_name(self, template_name: str) -> PromptTemplate:
        """Get prompt template by name"""
        prompt = self.db.query(PromptTemplate).filter(
            PromptTemplate.template_name == template_name
        ).first()

        return prompt if prompt else None

    def create_template(self, prompt_data: Dict) -> PromptTemplate:
        prompt = PromptTemplate(
            template_id=str(uuid.uuid4()),
            template_name=prompt_data.get("template_name"),
            category=prompt_data.get("category", "general"),
            content=prompt_data.get("content"),
            created_by=prompt_data.get("created_by")
        )

        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def update_template(self, template_id: str, update_data: Dict) -> PromptTemplate:
        """Update an existing prompt template"""
        prompt = self.get_prompt(template_id)
        if not prompt:
            return None

        # Update allowed fields
        allowed_fields = ["template_name", "content"]

        for field in allowed_fields:
            if field in update_data:
                setattr(prompt, field, update_data[field])

        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def delete_template(self, template_id: str) -> bool:
        """Delete a prompt template"""
        prompt = self.get_prompt(template_id)
        if not prompt:
            return False

        self.db.delete(prompt)
        self.db.commit()
        return True

    def get_all_prompts(self) -> List[PromptTemplate]:
        return self.db.query(PromptTemplate).all()

    def get_prompts_by_category(self, category: str) -> List[PromptTemplate]:
        """Get all prompts in a specific category"""
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.category == category
        ).all()
    
    def get_prompt_by_account(self, account_id: str) -> List[PromptTemplate]:
        account = self.db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail=f"Account with ID {account_id} does not exist")
        
        return self.db.query(PromptTemplate).filter(PromptTemplate.created_by == account_id)



    
    

    