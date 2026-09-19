"""保洁服务外包单位接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.vendor import VendorCreate, VendorDetail, VendorOut, VendorUpdate
from app.services import vendor_service

router = APIRouter(prefix="/vendors", tags=["保洁外包-单位"])


class VendorOption(BaseModel):
    id: int
    code: str
    name: str


@router.get("/meta/options", response_model=list[VendorOption], summary="外包单位下拉选项")
def vendor_options(
    db: Annotated[Session, Depends(get_db)],
    keyword: Annotated[str | None, Query(description="名称/编号模糊搜索")] = None,
    active_only: Annotated[bool, Query(description="仅合作中的单位")] = False,
) -> list[VendorOption]:
    rows, _ = vendor_service.list_vendors(
        db, keyword=keyword, status="合作中" if active_only else None, page=1, page_size=100
    )
    return [VendorOption(id=row.id, code=row.code, name=row.name) for row in rows]


@router.get("", response_model=Page[VendorOut], summary="外包单位列表")
def list_vendors(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    keyword: Annotated[str | None, Query(description="名称/编号/联系人/信用代码")] = None,
    status: Annotated[str | None, Query(description="合作状态")] = None,
) -> Page[VendorOut]:
    rows, total = vendor_service.list_vendors(
        db,
        keyword=keyword,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page[VendorOut](
        items=[VendorOut.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=VendorOut, status_code=201, summary="登记外包单位")
def create_vendor(payload: VendorCreate, db: Annotated[Session, Depends(get_db)]) -> VendorOut:
    return VendorOut.model_validate(vendor_service.create_vendor(db, payload))


@router.get("/{vendor_id}", response_model=VendorDetail, summary="外包单位详情")
def get_vendor(vendor_id: int, db: Annotated[Session, Depends(get_db)]) -> VendorDetail:
    return vendor_service.vendor_detail(db, vendor_id)


@router.patch("/{vendor_id}", response_model=VendorOut, summary="更新外包单位")
def update_vendor(
    vendor_id: int, payload: VendorUpdate, db: Annotated[Session, Depends(get_db)]
) -> VendorOut:
    return VendorOut.model_validate(vendor_service.update_vendor(db, vendor_id, payload))


@router.delete("/{vendor_id}", response_model=MessageOut, summary="删除外包单位")
def delete_vendor(vendor_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    vendor_service.delete_vendor(db, vendor_id)
    return MessageOut(message="删除成功")
