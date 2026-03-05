from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from database.model import Scenario, Account
from datetime import datetime
import uuid
from fastapi import HTTPException
import pytz
from sqlalchemy import func


def get_vietnam_timezone():
    return pytz.timezone("Asia/Ho_Chi_Minh")


def get_vietnam_time():
    return datetime.now(get_vietnam_timezone())


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────────
    # Helper: base query for active (non-deleted) scenarios
    # ────────────────────────────────────────────────
    def _active_query(self):
        return self.db.query(Scenario).filter(Scenario.is_deleted == False)

    # ────────────────────────────────────────────────
    # Validation & Creation (unchanged except minor cleanup)
    # ────────────────────────────────────────────────
    def validate_scenario_data(self, data: Dict) -> None:
        required = [
            "scenario_name",
            "scenario_summary",
            "scenario_text",
            "created_by",
            "personal_characteristics",
            "attitude_in_interview",
            "character_name",
            "character_gender",
            "industry",
        ]

        for field in required:
            if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
                raise HTTPException(400, f"Missing or empty required field: {field}")

        if len(data["scenario_name"]) < 3:
            raise HTTPException(400, "scenario_name must be at least 3 characters")
        if len(data["scenario_summary"]) < 10:
            raise HTTPException(400, "scenario_summary must be at least 10 characters")
        if len(data["character_name"]) < 2:
            raise HTTPException(400, "character_name must be at least 2 characters")

        gender = str(data["character_gender"]).lower().strip()
        if gender not in ["male", "female", "other"]:
            raise HTTPException(400, "character_gender must be 'male', 'female' or 'other'")

        creator = self.db.query(Account).filter(Account.account_id == data["created_by"]).first()
        if not creator:
            raise HTTPException(404, f"Account not found: {data['created_by']}")

    def create_scenario(self, data: Dict) -> Scenario:
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_name=data["scenario_name"],
            scenario_summary=data["scenario_summary"],
            scenario_text=data["scenario_text"],
            created_by=data["created_by"],
            created_at=get_vietnam_time(),
            personal_characteristics=data["personal_characteristics"],
            attitude_in_interview=data["attitude_in_interview"],
            rule_interview=data.get("rule_interview", ""),
            character_name=data["character_name"],
            character_gender=data["character_gender"].upper(),
            industry=data["industry"],
            is_deleted=False,           # explicit default
            times_chosen=0,             # explicit default if not already set in model
        )

        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def create_scenario_with_validation(self, data: Dict) -> Dict:
        self.validate_scenario_data(data)
        scenario = self.create_scenario(data)
        return {"message": "Scenario created successfully", "scenario": scenario}

    # ────────────────────────────────────────────────
    # Read operations — exclude deleted by default
    # ────────────────────────────────────────────────
    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return self._active_query().filter(Scenario.scenario_id == scenario_id).first()

    def get_all_scenarios(self) -> List[Scenario]:
        return self._active_query().all()

    def get_deleted_scenarios(self) -> List[Scenario]:
        """Get only soft-deleted scenarios, sorted by most recently deleted"""
        return (
            self.db.query(Scenario)
            .filter(Scenario.is_deleted == True)
            .order_by(Scenario.created_at.desc())
            .all()
        )

    def search_by_name(self, term: str) -> List[Scenario]:
        return self._active_query().filter(Scenario.scenario_name.ilike(f"%{term}%")).all()

    def get_scenarios_sorted_by_name(self, order: str = "asc") -> List[Scenario]:
        query = self._active_query()
        if order.lower() == "desc":
            query = query.order_by(Scenario.scenario_name.desc())
        else:
            query = query.order_by(Scenario.scenario_name.asc())
        return query.all()

    def get_scenarios_sorted_by_date(self, order: str = "desc") -> List[Scenario]:
        query = self._active_query()
        if order.lower() == "asc":
            query = query.order_by(Scenario.created_at.asc())
        else:
            query = query.order_by(Scenario.created_at.desc())
        return query.all()

    def get_scenarios_sorted_by_popularity(self, order: str = "desc") -> List[Scenario]:
        query = self._active_query()
        if order.lower() == "asc":
            query = query.order_by(Scenario.times_chosen.asc())
        else:
            query = query.order_by(Scenario.times_chosen.desc())
        return query.all()

    def get_scenarios_with_limit(
        self,
        limit: int,
        sort_by: str = "date",
        order: str = "desc",
        page: int = 1,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Scenario]:
        query = self._active_query()

        if exclude_ids:
            query = query.filter(~Scenario.scenario_id.in_(exclude_ids))

        if sort_by == "name":
            sort_column = Scenario.scenario_name
        elif sort_by == "popularity":
            sort_column = Scenario.times_chosen
        else:
            sort_column = Scenario.created_at

        if order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        offset = (page - 1) * limit
        return query.offset(offset).limit(limit).all()

    # ────────────────────────────────────────────────
    # Soft Delete + Hard Delete + Restore
    # ────────────────────────────────────────────────
    def soft_delete_scenario(self, scenario_id: str) -> bool:
        scenario = self.db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
        if not scenario:
            return False
        if scenario.is_deleted:
            return True  # already deleted → idempotent

        scenario.is_deleted = True
        if not scenario.scenario_name.endswith(" (DELETED)"):
            scenario.scenario_name = f"{scenario.scenario_name} (DELETED)"

        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise HTTPException(500, "Error during soft delete")

    def restore_scenario(self, scenario_id: str) -> Optional[Scenario]:
        scenario = (
            self.db.query(Scenario)
            .filter(Scenario.scenario_id == scenario_id, Scenario.is_deleted == True)
            .first()
        )
        if not scenario:
            return None

        scenario.is_deleted = False
        if scenario.scenario_name.endswith(" (DELETED)"):
            scenario.scenario_name = scenario.scenario_name[:-10].rstrip()

        try:
            self.db.commit()
            self.db.refresh(scenario)
            return scenario
        except Exception:
            self.db.rollback()
            raise HTTPException(500, "Error during restore")

    # ────────────────────────────────────────────────
    # Other mutations
    # ────────────────────────────────────────────────
    def increment_times_chosen(self, scenario_id: str) -> Optional[Scenario]:
        scenario = self.get_scenario(scenario_id)  # uses active query → None if deleted
        if not scenario:
            return None
        scenario.times_chosen = (scenario.times_chosen or 0) + 1
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def update_scenario(self, scenario_id: str, updates: Dict) -> Scenario:
        scenario = self.get_scenario(scenario_id)  # uses active query → None if deleted
        if not scenario:
            raise HTTPException(404, "Scenario not found or is deleted")

        allowed = {
            "scenario_name",
            "scenario_summary",
            "scenario_text",
            "personal_characteristics",
            "attitude_in_interview",
            "rule_interview",
            "character_name",
            "character_gender",
            "industry",
            "times_chosen",
        }

        for field, value in updates.items():
            if field not in allowed:
                raise HTTPException(400, f"Cannot update field: {field}")
            if field == "character_gender" and value:
                value = str(value).upper()
            setattr(scenario, field, value)

        self.db.commit()
        self.db.refresh(scenario)
        return scenario