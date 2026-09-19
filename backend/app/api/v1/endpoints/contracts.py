"""保洁服务外包合同接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.vendor import ContractCreate, ContractDetail, ContractOut, ContractUpdate
from app.services import vendor_service

router = APIRouter(prefix="/contracts", tags=["保洁外包-合同"])


@router.get("", response_model=Page[ContractOut], summary="外包合同列表")
def list_contracts(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    vendor_id: Annotated[int | None, Query(description="按承包单位过滤")] = None,
    status: Annotated[str | None, Query(description="履行状态")] = None,
    scope_type: Annotated[str | None, Query(description="服务范围类型")] = None,
    keyword: Annotated[str | None, Query(description="合同名称/编号/单位名称")] = None,
) -> Page[ContractOut]:
    rows, total = vendor_service.list_contracts(
        db,
        vendor_id=vendor_id,
        status=status,
        scope_type=scope_type,
        keyword=keyword,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page[ContractOut](
        items=[vendor_service.contract_to_out(db, row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=ContractOut, status_code=201, summary="登记外包合同")
def create_contract(payload: ContractCreate, db: Annotated[Session, Depends(get_db)]) -> ContractOut:
    contract = vendor_service.create_contract(db, payload)
    return vendor_service.contract_to_out(db, contract)


@router.get("/covering/{restroom_id}", response_model=list[ContractOut], summary="覆盖指定公厕的外包合同")
def contracts_covering_restroom(
    restroom_id: int, db: Annotated[Session, Depends(get_db)]
) -> list[ContractOut]:
    rows = vendor_service.contracts_covering_restroom(db, restroom_id)
    return [vendor_service.contract_to_out(db, row) for row in rows]


@router.get("/{contract_id}", response_model=ContractDetail, summary="合同详情（含费用台账）")
def get_contract(contract_id: int, db: Annotated[Session, Depends(get_db)]) -> ContractDetail:
    return vendor_service.contract_detail(db, contract_id)


@router.patch("/{contract_id}", response_model=ContractOut, summary="更新合同")
def update_contract(
    contract_id: int, payload: ContractUpdate, db: Annotated[Session, Depends(get_db)]
) -> ContractOut:
    contract = vendor_service.update_contract(db, contract_id, payload)
    return vendor_service.contract_to_out(db, contract)


@router.delete("/{contract_id}", response_model=MessageOut, summary="删除合同")
def delete_contract(contract_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    vendor_service.delete_contract(db, contract_id)
    return MessageOut(message="删除成功")
