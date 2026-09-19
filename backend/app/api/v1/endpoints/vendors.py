"""保洁外包单位接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.common import MessageOut, Page
from app.schemas.vendor import VendorCreate, VendorDetail, VendorOut, VendorUpdate
from app.services import vendor_service

router = APIRouter(prefix="/vendors", tags=["外包单位"])


@router.get("", response_model=Page[VendorOut], summary="外包单位列表")
def list_vendors(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    keyword: Annotated[str | None, Query(description="名称/编号/联系人模糊搜索")] = None,
    status: Annotated[str | None, Query(description="合作状态")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[VendorOut]:
    rows, total = vendor_service.list_vendors(
        db,
        keyword=keyword,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[VendorOut](
        items=[VendorOut.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.get("/options", response_model=list[VendorOut], summary="单位下拉选项（全部）")
def vendor_options(db: Annotated[Session, Depends(get_db)]) -> list[VendorOut]:
    return [VendorOut.model_validate(row) for row in vendor_service.list_all_vendors(db)]


@router.post("", response_model=VendorOut, status_code=201, summary="新增外包单位")
def create_vendor(payload: VendorCreate, db: Annotated[Session, Depends(get_db)]) -> VendorOut:
    return VendorOut.model_validate(vendor_service.create_vendor(db, payload))


@router.get("/{vendor_id}", response_model=VendorDetail, summary="外包单位详情")
def get_vendor(vendor_id: int, db: Annotated[Session, Depends(get_db)]) -> VendorDetail:
    return vendor_service.get_vendor_detail(db, vendor_id)


@router.patch("/{vendor_id}", response_model=VendorOut, summary="更新外包单位")
def update_vendor(
    vendor_id: int, payload: VendorUpdate, db: Annotated[Session, Depends(get_db)]
) -> VendorOut:
    return VendorOut.model_validate(vendor_service.update_vendor(db, vendor_id, payload))


@router.delete("/{vendor_id}", response_model=MessageOut, summary="删除外包单位")
def delete_vendor(vendor_id: int, db: Annotated[Session, Depends(get_db)]) -> MessageOut:
    vendor_service.delete_vendor(db, vendor_id)
    return MessageOut(message="删除成功")
