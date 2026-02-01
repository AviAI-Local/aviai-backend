from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List
from sqlalchemy.orm import Session
from .service import ScenarioService
from database.config import get_db
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(tags=["scenarios"])  # ← prefix removed → handled in main.py

class ScenarioResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    scenario_summary: str
    personal_characteristics: str
    attitude_in_interview: str
    rule_interview: str
    character_name: str
    character_gender: str
    industry: str
    scenario_text: str
    created_by: str
    created_at: datetime
    times_chosen: int = 0

    class Config:
        from_attributes = True


@router.post(
    "/",
    response_model=ScenarioResponse,
    summary="Create new scenario"
)
async def create_scenario(
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    result = service.create_scenario_with_validation(data)
    return result["scenario"]


@router.get("/", response_model=List[ScenarioResponse])
async def get_all_scenarios(db: Session = Depends(get_db)):
    service = ScenarioService(db)
    items = service.get_all_scenarios()
    return items




@router.get("/sorted/name", response_model=List[ScenarioResponse])
async def sorted_by_name(
    order: str = Query("asc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    return service.get_scenarios_sorted_by_name(order)


@router.get("/sorted/date", response_model=List[ScenarioResponse])
async def sorted_by_date(
    order: str = Query("desc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    return service.get_scenarios_sorted_by_date(order)


@router.get("/sorted/popularity", response_model=List[ScenarioResponse])
async def sorted_by_popularity(
    order: str = Query("desc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    return service.get_scenarios_sorted_by_popularity(order)


@router.get("/search", response_model=List[ScenarioResponse])
async def search_by_name(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    return service.search_by_name(q)
@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    item = service.get_scenario(scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return item


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: str,
    updates: dict = Body(...),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    updated = service.update_scenario(scenario_id, updates)
    return updated


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    deleted = service.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"message": "Scenario deleted successfully"}


@router.post("/{scenario_id}/use", summary="Increment usage counter")
async def mark_as_used(scenario_id: str, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    scenario = service.increment_times_chosen(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "scenario_id": scenario.scenario_id,
        "times_chosen": scenario.times_chosen
    }