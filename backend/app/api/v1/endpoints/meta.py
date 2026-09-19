"""字典接口：供前端下拉选项使用。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTION_CHECK_ITEMS,
    INSPECTION_ITEM_MAX_SCORE,
    ISSUE_NEW_DEDUCTION,
    ISSUE_OVERDUE_DEDUCTION,
    ISSUE_REJECT_DEDUCTION,
    ISSUE_TRANSITIONS,
    MAX_AUTO_DEDUCTION_RATE,
    SCORE_DEDUCTION_RULES,
    ContractStatus,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomGrade,
    RestroomStatus,
    SettlementStatus,
    Shift,
    VendorStatus,
)
from app.core.database import get_db
from app.services import inspection_service

router = APIRouter(prefix="/meta", tags=["字典"])


class RestroomOption(BaseModel):
    id: int
    code: str
    name: str
    district: str


class Dictionaries(BaseModel):
    restroom_status: list[str]
    restroom_grade: list[str]
    shift: list[str]
    issue_category: list[str]
    issue_severity: list[str]
    issue_status: list[str]
    inspection_check_items: list[str]
    inspection_item_max_score: int
    issue_transitions: dict[str, list[str]]
    vendor_status: list[str]
    contract_status: list[str]
    settlement_status: list[str]
    assess_rules: dict


@router.get("/dictionaries", response_model=Dictionaries, summary="枚举字典")
def get_dictionaries() -> Dictionaries:
    return Dictionaries(
        restroom_status=[item.value for item in RestroomStatus],
        restroom_grade=[item.value for item in RestroomGrade],
        shift=[item.value for item in Shift],
        issue_category=[item.value for item in IssueCategory],
        issue_severity=[item.value for item in IssueSeverity],
        issue_status=[item.value for item in IssueStatus],
        inspection_check_items=list(INSPECTION_CHECK_ITEMS),
        inspection_item_max_score=INSPECTION_ITEM_MAX_SCORE,
        issue_transitions={key: list(value) for key, value in ISSUE_TRANSITIONS.items()},
        vendor_status=[item.value for item in VendorStatus],
        contract_status=[item.value for item in ContractStatus],
        settlement_status=[item.value for item in SettlementStatus],
        assess_rules={
            "score_rules": [
                {"min_score": threshold, "rate": rate, "note": note}
                for threshold, rate, note in SCORE_DEDUCTION_RULES
            ],
            "issue_new_deduction": dict(ISSUE_NEW_DEDUCTION),
            "issue_overdue_deduction": ISSUE_OVERDUE_DEDUCTION,
            "issue_reject_deduction": ISSUE_REJECT_DEDUCTION,
            "max_auto_deduction_rate": MAX_AUTO_DEDUCTION_RATE,
        },
    )


@router.get("/restroom-options", response_model=list[RestroomOption], summary="公厕下拉选项")
def get_restroom_options(
    db: Annotated[Session, Depends(get_db)], keyword: str | None = None
) -> list[RestroomOption]:
    rows = inspection_service.restroom_options(db, keyword=keyword)
    return [
        RestroomOption(id=row.id, code=row.code, name=row.name, district=row.district)
        for row in rows
    ]
