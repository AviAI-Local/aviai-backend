from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from database.model import Scenario, Account
from datetime import datetime
import uuid
from fastapi import HTTPException
import pytz


def get_vietnam_timezone():
    return pytz.timezone("Asia/Ho_Chi_Minh")


def get_vietnam_time():
    return datetime.now(get_vietnam_timezone())


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db

    def validate_scenario_data(self, data: Dict) -> None:
        required = [
            "scenario_name",
            "scenario_text",
            "created_by",
            "personal_characteristics",
            "attitude_in_interview",
            "category",
            "prompt_id"
        ]

        for field in required:
            if (
                field not in data
                or data[field] is None
                or (isinstance(data[field], str) and not data[field].strip())
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing or empty required field: {field}",
                )

        if len(data["scenario_name"]) < 3:
            raise HTTPException(
                status_code=400,
                detail="scenario_name must be at least 3 characters",
            )

        creator = (
            self.db.query(Account)
            .filter(Account.account_id == data["created_by"])
            .first()
        )
        if not creator:
            raise HTTPException(
                status_code=404,
                detail=f"Account not found: {data['created_by']}",
            )

    def create_scenario(self, data: Dict) -> Scenario:
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_name=data["scenario_name"],
            scenario_text=data["scenario_text"],
            created_by=data["created_by"],
            created_at=get_vietnam_time(),
            personal_characteristics=data["personal_characteristics"],
            attitude_in_interview=data["attitude_in_interview"],
            rule_interview=data.get("rule_interview", ""),
            category=data["category"],
            prompt_id=data["prompt_id"]
        )

        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def create_scenario_with_validation(self, data: Dict) -> Dict:
        self.validate_scenario_data(data)
        scenario = self.create_scenario(data)
        return {
            "message": "Scenario created successfully",
            "scenario": scenario,
        }

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return (
            self.db.query(Scenario)
            .filter(Scenario.scenario_id == scenario_id)
            .first()
        )

    def get_all_scenarios(self) -> List[Scenario]:
        return self.db.query(Scenario).all()

    def get_scenarios_sorted_by_name(self, order: str = "asc") -> List[Scenario]:
        if order.lower() == "desc":
            return (
                self.db.query(Scenario)
                .order_by(Scenario.scenario_name.desc())
                .all()
            )
        return (
            self.db.query(Scenario)
            .order_by(Scenario.scenario_name.asc())
            .all()
        )

    def get_scenarios_sorted_by_date(self, order: str = "desc") -> List[Scenario]:
        if order.lower() == "asc":
            return (
                self.db.query(Scenario)
                .order_by(Scenario.created_at.asc())
                .all()
            )
        return (
            self.db.query(Scenario)
            .order_by(Scenario.created_at.desc())
            .all()
        )

    def get_scenarios_sorted_by_popularity(
        self, order: str = "desc"
    ) -> List[Scenario]:
        if order.lower() == "asc":
            return (
                self.db.query(Scenario)
                .order_by(Scenario.times_chosen.asc())
                .all()
            )
        return (
            self.db.query(Scenario)
            .order_by(Scenario.times_chosen.desc())
            .all()
        )

    def search_by_name(self, term: str) -> List[Scenario]:
        return (
            self.db.query(Scenario)
            .filter(Scenario.scenario_name.ilike(f"%{term}%"))
            .all()
        )

    def delete_scenario(self, scenario_id: str) -> bool:
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return False
        try:
            self.db.delete(scenario)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Error while deleting scenario",
            )

    def increment_times_chosen(self, scenario_id: str) -> Optional[Scenario]:
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return None
        scenario.times_chosen = (scenario.times_chosen or 0) + 1
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def update_scenario(self, scenario_id: str, updates: Dict) -> Scenario:
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        allowed = {
            "scenario_name",
            "scenario_text",
            "personal_characteristics",
            "attitude_in_interview",
            "rule_interview",
            "category",
            "times_chosen",
        }

        for field, value in updates.items():
            if field not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot update field: {field}",
                )
            if field == "character_gender" and value:
                value = str(value).upper()
            setattr(scenario, field, value)

        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def get_scenarios_with_limit(
        self,
        limit: int,
        sort_by: str = "date",
        order: str = "desc",
        page: int = 1,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Scenario]:

        query = self.db.query(Scenario)

        if exclude_ids:
            query = query.filter(~Scenario.scenario_id.in_(exclude_ids))

        if sort_by == "name":
            sort_column = Scenario.scenario_name
        elif sort_by == "popularity":
            sort_column = Scenario.times_chosen
        else:
            sort_column = Scenario.created_at

        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        offset = (page - 1) * limit
        return query.offset(offset).limit(limit).all()
