"""月度考核与费用结算接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.settlement import (
    SettlementAdjust,
    SettlementConfirm,
    SettlementCreate,
    SettlementDetail,
    SettlementOut,
)
from app.services import settlement_service

router = APIRouter(tags=["费用结算"])


@router.get(
    "/settlements",
    response_model=Page[SettlementOut],
    summary="月度结算台账列表",
)
def list_settlements(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    contract_id: Annotated[int | None, Query(description="按合同过滤")] = None,
    vendor_id: Annotated[int | None, Query(description="按承包单位过滤")] = None,
    period_year: Annotated[int | None, Query(description="考核年份")] = None,
    period_month: Annotated[int | None, Query(description="考核月份")] = None,
    status: Annotated[str | None, Query(description="已考核/已结算")] = None,
    keyword: Annotated[str | None, Query(description="结算单号/合同名称/编号")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[SettlementOut]:
    rows, total = settlement_service.list_settlements(
        db,
        contract_id=contract_id,
        vendor_id=vendor_id,
        period_year=period_year,
        period_month=period_month,
        status=status,
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


@router.post(
    "/contracts/{contract_id}/settlements",
    response_model=SettlementOut,
    status_code=201,
    summary="生成月度考核结算单",
)
def create_settlement(
    contract_id: int, payload: SettlementCreate, db: Annotated[Session, Depends(get_db)]
) -> SettlementOut:
    return settlement_service.to_out(
        settlement_service.assess_settlement(db, contract_id, payload)
    )


@router.get("/settlements/{settlement_id}", response_model=SettlementDetail, summary="结算单详情")
def get_settlement(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> SettlementDetail:
    return settlement_service.to_detail(
        db, settlement_service.get_settlement(db, settlement_id)
    )


@router.post(
    "/settlements/{settlement_id}/reassess",
    response_model=SettlementOut,
    summary="按最新巡查/问题数据重新考核",
)
def reassess_settlement(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> SettlementOut:
    return settlement_service.to_out(settlement_service.reassess_settlement(db, settlement_id))


@router.patch(
    "/settlements/{settlement_id}",
    response_model=SettlementOut,
    summary="手工调整其他扣款/奖励",
)
def adjust_settlement(
    settlement_id: int, payload: SettlementAdjust, db: Annotated[Session, Depends(get_db)]
) -> SettlementOut:
    return settlement_service.to_out(
        settlement_service.adjust_settlement(db, settlement_id, payload)
    )


@router.post(
    "/settlements/{settlement_id}/confirm",
    response_model=SettlementOut,
    summary="确认结算（已考核 → 已结算）",
)
def confirm_settlement(
    settlement_id: int, payload: SettlementConfirm, db: Annotated[Session, Depends(get_db)]
) -> SettlementOut:
    return settlement_service.to_out(
        settlement_service.confirm_settlement(db, settlement_id, payload)
    )


@router.delete("/settlements/{settlement_id}", response_model=MessageOut, summary="删除结算单")
def delete_settlement(
    settlement_id: int, db: Annotated[Session, Depends(get_db)]
) -> MessageOut:
    settlement_service.delete_settlement(db, settlement_id)
    return MessageOut(message="删除成功")
