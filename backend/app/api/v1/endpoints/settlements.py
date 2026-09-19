"""月度费用结算与考核扣款接口。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.vendor import (
    SettlementCreate,
    SettlementDetail,
    SettlementManualUpdate,
    SettlementOut,
    SettlementPreview,
    SettlementRemarkUpdate,
    SettlementStatusUpdate,
    SettlementTraceItem,
)
from app.services import settlement_service

router = APIRouter(prefix="/settlements", tags=["保洁外包-结算考核"])


class TransitionOption(BaseModel):
    status: str
    action: str


@router.get("", response_model=Page[SettlementOut], summary="月度费用结算台账列表")
def list_settlements(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    contract_id: Annotated[int | None, Query(description="按合同过滤")] = None,
    vendor_id: Annotated[int | None, Query(description="按外包单位过滤")] = None,
    status: Annotated[str | None, Query(description="结算状态")] = None,
    period_month: Annotated[str | None, Query(description="考核月份 YYYY-MM")] = None,
    date_from: Annotated[date | None, Query(description="周期开始不早于")] = None,
    date_to: Annotated[date | None, Query(description="周期结束不晚于")] = None,
    keyword: Annotated[str | None, Query(description="结算单号/合同号/合同名称")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "period_month",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[SettlementOut]:
    rows, total = settlement_service.list_settlements(
        db,
        contract_id=contract_id,
        vendor_id=vendor_id,
        status=status,
        period_month=period_month,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[SettlementOut](
        items=[settlement_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.get("/preview", response_model=SettlementPreview, summary="考核扣款测算（不写库）")
def preview_settlement(
    db: Annotated[Session, Depends(get_db)],
    contract_id: Annotated[int, Query(description="合同 ID")],
    period_month: Annotated[str, Query(description="考核月份 YYYY-MM")],
) -> SettlementPreview:
    return settlement_service.preview_settlement(db, contract_id, period_month)


@router.post("", response_model=SettlementOut, status_code=201, summary="登记月度结算单（待考核）")
def create_settlement(
    payload: SettlementCreate, db: Annotated[Session, Depends(get_db)]
) -> SettlementOut:
    return settlement_service.to_out(settlement_service.create_settlement(db, payload))


@router.get("/{settlement_id}", response_model=SettlementDetail, summary="结算单详情（可追溯明细）")
def get_settlement(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> SettlementDetail:
    return settlement_service.to_detail(settlement_service.get_settlement(db, settlement_id))


@router.post("/{settlement_id}/assess", response_model=SettlementDetail, summary="执行月度考核")
def assess_settlement(
    settlement_id: int,
    payload: SettlementStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SettlementDetail:
    settlement = settlement_service.assess_settlement(
        db,
        settlement_id,
        operator=payload.operator,
        remark=payload.remark,
    )
    return settlement_service.to_detail(settlement)


@router.post("/{settlement_id}/manual", response_model=SettlementDetail, summary="登记其他扣款调整")
def update_manual(
    settlement_id: int,
    payload: SettlementManualUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SettlementDetail:
    settlement = settlement_service.update_manual(
        db,
        settlement_id,
        manual_deduction=payload.manual_deduction,
        manual_reason=payload.manual_reason,
    )
    return settlement_service.to_detail(settlement)


@router.get(
    "/{settlement_id}/transitions",
    response_model=list[TransitionOption],
    summary="结算单可执行的状态动作",
)
def list_transitions(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> list[TransitionOption]:
    settlement = settlement_service.get_settlement(db, settlement_id)
    return [
        TransitionOption(**option) for option in settlement_service.allowed_transitions(settlement)
    ]


@router.post("/{settlement_id}/transitions", response_model=SettlementOut, summary="结算状态流转")
def change_status(
    settlement_id: int,
    payload: SettlementStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SettlementOut:
    return settlement_service.to_out(
        settlement_service.change_status(db, settlement_id, payload)
    )


@router.patch("/{settlement_id}", response_model=SettlementOut, summary="更新结算单备注")
def update_remark(
    settlement_id: int,
    payload: SettlementRemarkUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SettlementOut:
    settlement = settlement_service.get_settlement(db, settlement_id)
    settlement.remark = payload.remark
    db.commit()
    db.refresh(settlement)
    return settlement_service.to_out(settlement)


@router.delete("/{settlement_id}", response_model=MessageOut, summary="删除结算单")
def delete_settlement(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> MessageOut:
    settlement_service.delete_settlement(db, settlement_id)
    return MessageOut(message="删除成功")


# ---------------- 反向追溯 ----------------


@router.get(
    "/trace/inspection/{inspection_id}",
    response_model=list[SettlementTraceItem],
    summary="巡查记录反向追溯结算扣款",
)
def trace_inspection(
    inspection_id: int, db: Annotated[Session, Depends(get_db)]
) -> list[SettlementTraceItem]:
    return [SettlementTraceItem(**item) for item in settlement_service.trace_by_inspection(db, inspection_id)]


@router.get(
    "/trace/issue/{issue_id}",
    response_model=list[SettlementTraceItem],
    summary="问题记录反向追溯结算扣款",
)
def trace_issue(
    issue_id: int, db: Annotated[Session, Depends(get_db)]
) -> list[SettlementTraceItem]:
    return [SettlementTraceItem(**item) for item in settlement_service.trace_by_issue(db, issue_id)]
