"""保洁外包合同接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.contract import (
    ContractCreate,
    ContractDetail,
    ContractOut,
    ContractTerminate,
    ContractUpdate,
)
from app.schemas.settlement import AssessmentPreview
from app.services import contract_service, settlement_service

router = APIRouter(prefix="/contracts", tags=["外包合同"])


@router.get("", response_model=Page[ContractOut], summary="合同列表")
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    keyword: Annotated[str | None, Query(description="合同名称/编号/范围说明模糊搜索")] = None,
    vendor_id: Annotated[int | None, Query(description="按承包单位过滤")] = None,
    status: Annotated[str | None, Query(description="履约中/已终止/已到期")] = None,
    district: Annotated[str | None, Query(description="按服务区域过滤")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "start_date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[ContractOut]:
    rows, total = contract_service.list_contracts(
        db,
        keyword=keyword,
        vendor_id=vendor_id,
        status=status,
        district=district,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[ContractOut](
        items=[contract_service.to_out(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=ContractOut, status_code=201, summary="新增合同")
def create_contract(payload: ContractCreate, db: Annotated[Session, Depends(get_db)]) -> ContractOut:
    return contract_service.to_out(contract_service.create_contract(db, payload))


@router.get("/{contract_id}", response_model=ContractDetail, summary="合同详情")
def get_contract(contract_id: int, db: Annotated[Session, Depends(get_db)]) -> ContractDetail:
    return contract_service.get_contract_detail(db, contract_id)


@router.patch("/{contract_id}", response_model=ContractOut, summary="更新合同")
def update_contract(
    contract_id: int, payload: ContractUpdate, db: Annotated[Session, Depends(get_db)]
) -> ContractOut:
    return contract_service.to_out(contract_service.update_contract(db, contract_id, payload))


@router.post("/{contract_id}/terminate", response_model=ContractOut, summary="终止合同")
def terminate_contract(
    contract_id: int, payload: ContractTerminate, db: Annotated[Session, Depends(get_db)]
) -> ContractOut:
    return contract_service.to_out(
        contract_service.terminate_contract(db, contract_id, payload.reason)
    )


@router.delete("/{contract_id}", response_model=MessageOut, summary="删除合同")
def delete_contract(contract_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    contract_service.delete_contract(db, contract_id)
    return MessageOut(message="删除成功")


@router.get(
    "/{contract_id}/assessment-preview",
    response_model=AssessmentPreview,
    summary="月度考核测算（生成结算单前预览扣款）",
)
def assessment_preview(
    contract_id: int,
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    monthly_fee: Annotated[float | None, Query(ge=0)] = None,
) -> AssessmentPreview:
    contract = contract_service.get_contract(db, contract_id)
    summary = settlement_service.collect_assessment(
        db, contract, year, month, fee_override=monthly_fee
    )
    total, payable = settlement_service.recompute_preview(summary, monthly_fee_override=monthly_fee)
    return AssessmentPreview(
        contract_id=contract_id,
        period_year=year,
        period_month=month,
        monthly_fee=summary["monthly_fee"],
        inspection_count=summary["inspection_count"],
        avg_score=summary["avg_score"],
        issue_new_count=summary["issue_new_count"],
        issue_overdue_count=summary["issue_overdue_count"],
        issue_reject_count=summary["issue_reject_count"],
        score_deduction=summary["score_deduction"],
        issue_deduction=summary["issue_deduction"],
        overdue_deduction=summary["overdue_deduction"],
        reject_deduction=summary["reject_deduction"],
        auto_deduction=summary["auto_deduction"],
        total_deduction=total,
        payable_amount=payable,
        assess_grade=summary["assess_grade"],
        evidences=summary["details"],
    )
