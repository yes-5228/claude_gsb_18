"""保洁外包单位业务逻辑。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import ContractStatus, SettlementStatus
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Contract, Settlement, Vendor
from app.schemas.vendor import VendorCreate, VendorDetail, VendorOut, VendorUpdate

SORTABLE_FIELDS = {
    "name": Vendor.name,
    "code": Vendor.code,
    "status": Vendor.status,
    "created_at": Vendor.created_at,
}


def _next_code(db: Session) -> str:
    """生成形如 WB-001 的单位编号。"""
    seq = (db.scalar(select(func.count()).select_from(Vendor)) or 0) + 1
    while True:
        code = f"WB-{seq:03d}"
        if not db.scalar(select(Vendor.id).where(Vendor.code == code)):
            return code
        seq += 1


def get_vendor(db: Session, vendor_id: int) -> Vendor:
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise NotFoundError(f"外包单位 {vendor_id} 不存在")
    return vendor


def list_vendors(
    db: Session,
    *,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    order: str = "desc",
) -> tuple[list[Vendor], int]:
    stmt = select(Vendor)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Vendor.name.like(like),
                Vendor.code.like(like),
                Vendor.contact_person.like(like),
            )
        )
    if status:
        stmt = stmt.where(Vendor.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, Vendor.created_at)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), Vendor.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def list_all_vendors(db: Session) -> list[Vendor]:
    return list(db.scalars(select(Vendor).order_by(Vendor.name)))


def create_vendor(db: Session, payload: VendorCreate) -> Vendor:
    data = payload.model_dump()
    code = (data.pop("code") or "").strip() or _next_code(db)
    name = data["name"].strip()
    if db.scalar(select(Vendor.id).where(Vendor.code == code)):
        raise DomainError(f"单位编号 {code} 已存在")
    if db.scalar(select(Vendor.id).where(Vendor.name == name)):
        raise DomainError(f"单位名称「{name}」已存在")
    vendor = Vendor(code=code, name=name, **{k: v for k, v in data.items() if k != "name"})
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def update_vendor(db: Session, vendor_id: int, payload: VendorUpdate) -> Vendor:
    vendor = get_vendor(db, vendor_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        name = data["name"].strip()
        exists = db.scalar(
            select(Vendor.id).where(Vendor.name == name, Vendor.id != vendor_id)
        )
        if exists:
            raise DomainError(f"单位名称「{name}」已存在")
        vendor.name = name
    for key, value in data.items():
        if key == "name":
            continue
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return vendor


def delete_vendor(db: Session, vendor_id: int) -> None:
    """删除单位：仍有合同（含已终止/到期）时拒绝，保留费用追溯链。"""
    vendor = get_vendor(db, vendor_id)
    contract_count = db.scalar(
        select(func.count()).select_from(Contract).where(Contract.vendor_id == vendor_id)
    ) or 0
    if contract_count:
        raise ConflictError(
            f"该单位名下已有 {contract_count} 份合同，不能删除；如停止合作可将单位置为「已停用」"
        )
    db.delete(vendor)
    db.commit()


def _money(value: float) -> float:
    """金额四舍五入到分。"""
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def current_month_payable(db: Session, vendor_id: int) -> float:
    now = datetime.now()
    rows = db.scalars(
        select(Settlement).join(Contract, Contract.id == Settlement.contract_id).where(
            Contract.vendor_id == vendor_id,
            Settlement.period_year == now.year,
            Settlement.period_month == now.month,
            Settlement.status == SettlementStatus.SETTLED.value,
        )
    ).all()
    return _money(sum(row.payable_amount for row in rows))


def get_vendor_detail(db: Session, vendor_id: int) -> VendorDetail:
    vendor = get_vendor(db, vendor_id)
    contract_count = db.scalar(
        select(func.count()).select_from(Contract).where(Contract.vendor_id == vendor_id)
    ) or 0
    active_count = db.scalar(
        select(func.count())
        .select_from(Contract)
        .where(
            Contract.vendor_id == vendor_id,
            Contract.status == ContractStatus.ACTIVE.value,
        )
    ) or 0
    base = VendorOut.model_validate(vendor).model_dump()
    return VendorDetail(
        **base,
        contract_count=contract_count,
        active_contract_count=active_count,
        current_month_payable=current_month_payable(db, vendor_id),
    )
