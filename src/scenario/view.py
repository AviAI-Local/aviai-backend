from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from database.model import Account
from scenario.schema import ScenarioResponse, create_request_example
from .service import ScenarioService
from database.config import get_db
from typing import Optional
from typing import Literal

router = APIRouter(tags=["scenario"])  # ← prefix removed → handled in main.py

@router.post(
    "/",
    response_model=ScenarioResponse,
    summary="Create new scenario"
)
async def create_scenario(
    data: dict = Body(..., examples=[create_request_example]),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user)
):
    service = ScenarioService(db)
    data["created_by"] = current_user.account_id
    result = service.create_scenario_with_validation(data)
    return result["scenario"]


@router.get("/", response_model=List[ScenarioResponse])
async def get_all_scenarios(db: Session = Depends(get_db)):
    service = ScenarioService(db)
    items = service.get_all_scenarios()
    return items

@router.get(
    "/limit/{limit}",
    response_model=List[ScenarioResponse],
    summary="Get scenarios with limit, sorting, pagination, exclusion"
)
async def get_scenarios_with_limit(
    limit: int,
    sort_by: Literal["name", "date", "popularity"] = "date",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    exclude_ids: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")

    exclude_list = None
    if exclude_ids:
        exclude_list = [x.strip() for x in exclude_ids.split(",") if x.strip()]

    service = ScenarioService(db)
    return service.get_scenarios_with_limit(
        limit=limit,
        sort_by=sort_by,
        order=order,
        page=page,
        exclude_ids=exclude_list
    )


@router.get("/search", response_model=List[ScenarioResponse])
async def search_by_name(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    return service.search_by_name(q)

@router.get(
    "/sorted",
    response_model=List[ScenarioResponse],
    summary="Sort scenarios dynamically"
)
async def sort_scenarios(
    sort_by: str = Query("date", pattern=r"^(name|date|popularity)$"),
    order: str = Query("desc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)

    if sort_by == "name":
        return service.get_scenarios_sorted_by_name(order)
    if sort_by == "popularity":
        return service.get_scenarios_sorted_by_popularity(order)

    return service.get_scenarios_sorted_by_date(order)


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

