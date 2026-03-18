from typing import Dict
from fastapi import APIRouter, Body, Depends, HTTPException
from rich.console import Console

from agent.prompt.service import PromptService
from database.config import get_db
from database.model import Session
from agent.prompt.templates import create_prompt_example

router = APIRouter()
console = Console()

@router.post("/create")
async def create_prompt(
    prompt_data: Dict = Body(..., examples=[create_prompt_example]),
    db: Session = Depends(get_db)
):
    service = PromptService(db)
    prompt = service.create_template(prompt_data)
    return {"prompt": prompt}

@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    service = PromptService(db)
    item = service.get_prompt(prompt_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return item.to_dict()

@router.get("/")
async def get_all_prompts(db: Session = Depends(get_db)):
    service = PromptService(db)
    items = service.get_all_prompts()
    return [item.to_dict() for item in items]

@router.get("/name/{template_name}")
async def get_prompt_by_name(template_name: str, db: Session = Depends(get_db)):
    service = PromptService(db)
    item = service.get_prompt_by_name(template_name)
    if not item:
        raise HTTPException(status_code=404, detail=f"Prompt template '{template_name}' not found")
    return item.to_dict()

@router.get("/category/{category}")
async def get_prompts_by_category(category: str, db: Session = Depends(get_db)):
    service = PromptService(db)
    items = service.get_prompts_by_category(category)
    return [item.to_dict() for item in items]

@router.put("/{prompt_id}")
async def update_prompt(
    prompt_id: str,
    update_data: Dict = Body(..., examples=[{
        "template_name": "updated_template_name",
        "content": "Updated prompt content here..."
    }]),
    db: Session = Depends(get_db)
):
    """Update an existing prompt template"""
    service = PromptService(db)
    prompt = service.update_template(prompt_id, update_data)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return {"message": "Prompt updated successfully", "prompt": prompt.to_dict()}


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Delete a prompt template"""
    service = PromptService(db)
    success = service.delete_template(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    return {"message": "Prompt deleted successfully"}