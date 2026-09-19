"""外包单位与保洁合同业务逻辑。"""

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    ContractScopeType,
    ContractStatus,
    SettlementStatus,
    VendorStatus,
)
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import (
    CleaningContract,
    MonthlySettlement,
    Restroom,
    Vendor,
)
from app.schemas.vendor import (
    ContractCreate,
    ContractDetail,
    ContractOut,
    VendorCreate,
    VendorDetail,
    VendorOut,
    VendorUpdate,
)


def _next_vendor_code(db: Session) -> str:
    seq = (db.scalar(select(func.count()).select_from(Vendor)) or 0) + 1
    while True:
        code = f"WB-{seq:04d}"
        if not db.scalar(select(Vendor.id).where(Vendor.code == code)):
            return code
        seq += 1


def _next_contract_code(db: Session) -> str:
    seq = (db.scalar(select(func.count()).select_from(CleaningContract)) or 0) + 1
    while True:
        code = f"HT-{seq:04d}"
        if not db.scalar(select(CleaningContract.id).where(CleaningContract.code == code)):
            return code
        seq += 1


# ---------------- 外包单位 ----------------


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
) -> tuple[list[Vendor], int]:
    stmt = select(Vendor)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Vendor.name.like(like),
                Vendor.code.like(like),
                Vendor.contact_person.like(like),
                Vendor.license_no.like(like),
            )
        )
    if status:
        stmt = stmt.where(Vendor.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Vendor.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt)), total


def create_vendor(db: Session, payload: VendorCreate) -> Vendor:
    data = payload.model_dump()
    code = (data.pop("code") or "").strip() or _next_vendor_code(db)
    if db.scalar(select(Vendor.id).where(Vendor.code == code)):
        raise DomainError(f"单位编号 {code} 已存在")
    name = data["name"].strip()
    if db.scalar(select(Vendor.id).where(Vendor.name == name)):
        raise DomainError(f"单位名称「{name}」已存在")
    data["name"] = name
    vendor = Vendor(code=code, **data)
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
        data["name"] = name
    for key, value in data.items():
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return vendor


def delete_vendor(db: Session, vendor_id: int) -> None:
    vendor = get_vendor(db, vendor_id)
    contract_count = db.scalar(
        select(func.count()).select_from(CleaningContract).where(CleaningContract.vendor_id == vendor_id)
    ) or 0
    if contract_count:
        raise ConflictError(f"该单位已签订 {contract_count} 份合同，不能直接删除")
    db.delete(vendor)
    db.commit()


def vendor_detail(db: Session, vendor_id: int) -> VendorDetail:
    vendor = get_vendor(db, vendor_id)
    contracts = list(vendor.contracts)
    year = date.today().year
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    settled = [
        s
        for c in contracts
        for s in c.settlements
        if s.period_start <= year_end
        and s.period_end >= year_start
        and s.status == SettlementStatus.SETTLED.value
    ]
    base = VendorOut.model_validate(vendor).model_dump()
    return VendorDetail(
        **base,
        contract_count=len(contracts),
        active_contract_count=sum(
            1 for c in contracts if effective_status(c) == ContractStatus.ACTIVE.value
        ),
        settled_amount_year=round(sum(s.payable_amount for s in settled), 2),
        deduction_total_year=round(sum(s.total_deduction for s in settled), 2),
    )


# ---------------- 合同 ----------------


def scope_restroom_ids(db: Session, contract: CleaningContract) -> list[int]:
    """按服务范围划定方式解析实际覆盖的公厕 ID。"""
    if contract.scope_type == ContractScopeType.RESTROOM.value:
        ids = contract.scope_restroom_ids or []
        if not ids:
            return []
        rows = db.scalars(select(Restroom.id).where(Restroom.id.in_(ids)))
        return list(rows)
    districts = contract.scope_districts or []
    if not districts:
        return []
    return list(
        db.scalars(select(Restroom.id).where(Restroom.district.in_(districts)).order_by(Restroom.code))
    )


def scope_text(db: Session, contract: CleaningContract) -> str:
    if contract.scope_type == ContractScopeType.RESTROOM.value:
        count = len(scope_restroom_ids(db, contract))
        return f"指定 {count} 座公厕"
    districts = contract.scope_districts or []
    return "全域：" + "、".join(districts) if districts else "未设置区域"


def effective_status(contract: CleaningContract) -> str:
    """履行中状态随合同期限自动到期，终止状态保持不变。"""
    if contract.status == ContractStatus.TERMINATED.value:
        return ContractStatus.TERMINATED.value
    if contract.end_date < date.today():
        return ContractStatus.EXPIRED.value
    return ContractStatus.ACTIVE.value


def _validate_scope(db: Session, data: dict) -> None:
    scope_type = data.get("scope_type", ContractScopeType.DISTRICT.value)
    districts = data.get("scope_districts") or []
    restroom_ids = data.get("scope_restroom_ids") or []
    if scope_type == ContractScopeType.DISTRICT.value:
        if not districts:
            raise DomainError("按区域承包时至少选择一个服务区域")
    elif scope_type == ContractScopeType.RESTROOM.value:
        if not restroom_ids:
            raise DomainError("指定公厕承包时至少选择一座公厕")
        existing = set(
            db.scalars(select(Restroom.id).where(Restroom.id.in_(restroom_ids)))
        )
        missing = [rid for rid in restroom_ids if rid not in existing]
        if missing:
            raise DomainError(f"公厕 {', '.join(map(str, missing))} 不存在")
    else:
        raise DomainError("服务范围类型无效")


def get_contract(db: Session, contract_id: int) -> CleaningContract:
    contract = db.get(CleaningContract, contract_id)
    if contract is None:
        raise NotFoundError(f"合同 {contract_id} 不存在")
    return contract


def list_contracts(
    db: Session,
    *,
    vendor_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    scope_type: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[CleaningContract], int]:
    stmt = select(CleaningContract)
    if vendor_id:
        stmt = stmt.where(CleaningContract.vendor_id == vendor_id)
    if status == ContractStatus.ACTIVE.value:
        # 履行中需要结合期限实时判断
        stmt = stmt.where(
            CleaningContract.status == ContractStatus.ACTIVE.value,
            CleaningContract.end_date >= date.today(),
        )
    elif status:
        stmt = stmt.where(CleaningContract.status == status)
    if scope_type:
        stmt = stmt.where(CleaningContract.scope_type == scope_type)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                CleaningContract.name.like(like),
                CleaningContract.code.like(like),
                CleaningContract.vendor_id.in_(
                    select(Vendor.id).where(Vendor.name.like(like))
                ),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(CleaningContract.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt)), total


def create_contract(db: Session, payload: ContractCreate) -> CleaningContract:
    get_vendor(db, payload.vendor_id)
    data = payload.model_dump()
    code = (data.pop("code") or "").strip() or _next_contract_code(db)
    if db.scalar(select(CleaningContract.id).where(CleaningContract.code == code)):
        raise DomainError(f"合同编号 {code} 已存在")
    if data["end_date"] <= data["start_date"]:
        raise DomainError("合同结束日期必须晚于开始日期")
    _validate_scope(db, data)
    contract = CleaningContract(code=code, status=ContractStatus.ACTIVE.value, **data)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def update_contract(db: Session, contract_id: int, payload) -> CleaningContract:
    contract = get_contract(db, contract_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("vendor_id") is not None:
        get_vendor(db, data["vendor_id"])
    status = data.pop("status", None)

    merged = {
        "scope_type": contract.scope_type,
        "scope_districts": list(contract.scope_districts or []),
        "scope_restroom_ids": list(contract.scope_restroom_ids or []),
        **data,
    }
    needs_scope_check = any(
        key in data for key in ("scope_type", "scope_districts", "scope_restroom_ids")
    )
    if needs_scope_check:
        _validate_scope(db, merged)

    start = data.get("start_date", contract.start_date)
    end = data.get("end_date", contract.end_date)
    if end <= start:
        raise DomainError("合同结束日期必须晚于开始日期")

    for key, value in data.items():
        setattr(contract, key, value)
    if status is not None:
        contract.status = status
    db.commit()
    db.refresh(contract)
    return contract


def delete_contract(db: Session, contract_id: int) -> None:
    contract = get_contract(db, contract_id)
    settlement_count = len(contract.settlements)
    if settlement_count:
        raise ConflictError(
            f"该合同已有 {settlement_count} 条月度结算记录，不能删除；可将合同状态置为「已终止」"
        )
    db.delete(contract)
    db.commit()


def contracts_covering_restroom(db: Session, restroom_id: int) -> list[CleaningContract]:
    """找出服务范围覆盖指定公厕的合同（按区域或指定公厕）。"""
    restroom = db.get(Restroom, restroom_id)
    if restroom is None:
        raise NotFoundError(f"公厕 {restroom_id} 不存在")
    contracts = list(db.scalars(select(CleaningContract)))
    covering = [
        contract
        for contract in contracts
        if contract.status != ContractStatus.TERMINATED.value
        and restroom_id in scope_restroom_ids(db, contract)
    ]
    def _sort_key(contract: CleaningContract) -> tuple[int, date]:
        active = 0 if effective_status(contract) == ContractStatus.ACTIVE.value else 1
        return (active, -contract.end_date.toordinal())

    covering.sort(key=_sort_key)
    return covering


def contract_to_out(db: Session, contract: CleaningContract) -> ContractOut:
    out = ContractOut.model_validate(contract)
    out.scope_text = scope_text(db, contract)
    out.scope_restroom_count = len(scope_restroom_ids(db, contract))
    out.effective_status = effective_status(contract)
    return out


def contract_detail(db: Session, contract_id: int) -> ContractDetail:
    contract = get_contract(db, contract_id)
    out = contract_to_out(db, contract)
    restrooms = db.scalars(
        select(Restroom)
        .where(Restroom.id.in_(scope_restroom_ids(db, contract) or [-1]))
        .order_by(Restroom.code)
    )
    restroom_items = [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "district": r.district,
            "status": r.status,
            "manager": r.manager,
        }
        for r in restrooms
    ]
    settlements = sorted(contract.settlements, key=lambda s: s.period_month, reverse=True)
    assessed = [s for s in settlements if s.status != SettlementStatus.PENDING.value]
    scores = [s.avg_score for s in assessed if s.avg_score is not None]
    detail = ContractDetail(**out.model_dump(), restrooms=restroom_items, settlements=[])
    detail.settlement_count = len(settlements)
    detail.latest_period = settlements[0].period_month if settlements else None
    detail.total_payable = round(
        sum(s.payable_amount for s in assessed if s.status == SettlementStatus.SETTLED.value), 2
    )
    detail.total_deduction = round(sum(s.total_deduction for s in assessed), 2)
    detail.avg_score = round(sum(scores) / len(scores), 1) if scores else None
    detail.settlements = [
        {
            "id": s.id,
            "code": s.code,
            "period_month": s.period_month,
            "monthly_fee": s.monthly_fee,
            "total_deduction": s.total_deduction,
            "payable_amount": s.payable_amount,
            "avg_score": s.avg_score,
            "issue_count": s.issue_count,
            "overdue_count": s.overdue_count,
            "status": s.status,
        }
        for s in settlements
    ]
    return detail
