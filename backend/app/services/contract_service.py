"""保洁外包合同业务逻辑。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import ContractStatus, SettlementStatus
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Contract, Restroom, Settlement, Vendor
from app.models.contract import contract_restroom
from app.schemas.contract import ContractCreate, ContractDetail, ContractOut, ContractUpdate

SORTABLE_FIELDS = {
    "code": Contract.code,
    "name": Contract.name,
    "start_date": Contract.start_date,
    "end_date": Contract.end_date,
    "monthly_fee": Contract.monthly_fee,
    "created_at": Contract.created_at,
}


def _next_code(db: Session) -> str:
    """生成形如 HT-0001 的合同编号。"""
    seq = (db.scalar(select(func.count()).select_from(Contract)) or 0) + 1
    while True:
        code = f"HT-{seq:04d}"
        if not db.scalar(select(Contract.id).where(Contract.code == code)):
            return code
        seq += 1


def money(value: float) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def effective_status(contract: Contract, today: date | None = None) -> str:
    """合同状态：已终止优先，其次按期限判断到期，否则履约中。"""
    if contract.status == ContractStatus.TERMINATED.value:
        return ContractStatus.TERMINATED.value
    today = today or datetime.now().date()
    if today > contract.end_date:
        return ContractStatus.EXPIRED.value
    return ContractStatus.ACTIVE.value


def get_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError(f"合同 {contract_id} 不存在")
    return contract


def to_out(contract: Contract) -> ContractOut:
    data = ContractOut.model_validate(contract)
    data.status = effective_status(contract)
    return data


def get_contract_detail(db: Session, contract_id: int) -> ContractDetail:
    contract = get_contract(db, contract_id)
    base = to_out(contract).model_dump()
    settlement_rows = list(
        db.scalars(
            select(Settlement)
            .where(Settlement.contract_id == contract_id)
            .order_by(Settlement.period_year.desc(), Settlement.period_month.desc())
        )
    )
    settled = [s for s in settlement_rows if s.status == SettlementStatus.SETTLED.value]
    latest = settlement_rows[0] if settlement_rows else None
    return ContractDetail(
        **base,
        restroom_count=len(contract.restrooms),
        settlement_count=len(settlement_rows),
        settled_count=len(settled),
        settled_total=money(sum(s.payable_amount for s in settled)),
        latest_period=latest.period if latest else None,
        latest_payable=latest.payable_amount if latest else None,
        latest_status=latest.status if latest else None,
    )


def _load_restrooms(db: Session, restroom_ids: list[int]) -> list[Restroom]:
    ids = list(dict.fromkeys(restroom_ids))
    if not ids:
        return []
    rows = list(db.scalars(select(Restroom).where(Restroom.id.in_(ids))))
    if len(rows) != len(ids):
        found = {row.id for row in rows}
        missing = [rid for rid in ids if rid not in found]
        raise DomainError(f"公厕 {', '.join(map(str, missing))} 不存在，无法纳入服务范围")
    rows.sort(key=lambda room: ids.index(room.id))
    return rows


def _check_scope_conflict(
    db: Session,
    restroom_ids: list[int],
    start: date,
    end: date,
    *,
    exclude_id: int | None = None,
) -> None:
    """同一公厕在同一时段不能被两份履约中的合同重复覆盖。"""
    if not restroom_ids:
        return
    stmt = (
        select(Contract)
        .join(contract_restroom, contract_restroom.c.contract_id == Contract.id)
        .where(
            contract_restroom.c.restroom_id.in_(restroom_ids),
            Contract.status == ContractStatus.ACTIVE.value,
            Contract.start_date <= end,
            Contract.end_date >= start,
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(Contract.id != exclude_id)
    conflict = db.scalars(stmt.distinct()).first()
    if conflict is not None:
        raise DomainError(
            f"服务范围与合同 {conflict.code}（{conflict.name}）重叠："
            "同一公厕在合同期内已由其他合同覆盖"
        )


def list_contracts(
    db: Session,
    *,
    keyword: str | None = None,
    vendor_id: int | None = None,
    status: str | None = None,
    district: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "start_date",
    order: str = "desc",
) -> tuple[list[Contract], int]:
    stmt = select(Contract)
    if vendor_id:
        stmt = stmt.where(Contract.vendor_id == vendor_id)
    if district:
        stmt = stmt.join(contract_restroom, contract_restroom.c.contract_id == Contract.id).join(
            Restroom, Restroom.id == contract_restroom.c.restroom_id
        ).where(Restroom.district == district).distinct()
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(Contract.name.like(like), Contract.code.like(like), Contract.service_scope.like(like))
        )

    rows = list(db.scalars(stmt.order_by(Contract.id.desc())))
    if status:
        rows = [row for row in rows if effective_status(row) == status]

    total = len(rows)
    column = SORTABLE_FIELDS.get(sort_by, Contract.start_date)
    rows.sort(
        key=lambda row: (getattr(row, column.key), row.id), reverse=order == "desc"
    )
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


def create_contract(db: Session, payload: ContractCreate) -> Contract:
    vendor = db.get(Vendor, payload.vendor_id)
    if vendor is None:
        raise NotFoundError(f"外包单位 {payload.vendor_id} 不存在")
    restrooms = _load_restrooms(db, payload.restroom_ids)
    _check_scope_conflict(db, payload.restroom_ids, payload.start_date, payload.end_date)

    code = (payload.code or "").strip() or _next_code(db)
    if db.scalar(select(Contract.id).where(Contract.code == code)):
        raise DomainError(f"合同编号 {code} 已存在")

    contract = Contract(
        code=code,
        name=payload.name.strip(),
        vendor_id=payload.vendor_id,
        service_scope=payload.service_scope,
        scope_districts=payload.scope_districts,
        start_date=payload.start_date,
        end_date=payload.end_date,
        signed_date=payload.signed_date,
        monthly_fee=money(payload.monthly_fee),
        payment_terms=payload.payment_terms,
        remark=payload.remark,
        restrooms=restrooms,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def update_contract(db: Session, contract_id: int, payload: ContractUpdate) -> Contract:
    contract = get_contract(db, contract_id)
    if contract.status == ContractStatus.TERMINATED.value:
        raise DomainError("合同已终止，不能修改；如需履约请重新签订合同")

    data = payload.model_dump(exclude_unset=True)
    start = data.get("start_date", contract.start_date)
    end = data.get("end_date", contract.end_date)
    if end <= start:
        raise DomainError("合同到期日期必须晚于开始日期")

    if "restroom_ids" in data:
        restrooms = _load_restrooms(db, payload.restroom_ids or [])
        _check_scope_conflict(
            db, payload.restroom_ids or [], start, end, exclude_id=contract.id
        )
        contract.restrooms = restrooms
    elif start != contract.start_date or end != contract.end_date:
        _check_scope_conflict(
            db, [room.id for room in contract.restrooms], start, end, exclude_id=contract.id
        )

    for key, value in data.items():
        if key == "restroom_ids":
            continue
        if key == "monthly_fee" and value is not None:
            contract.monthly_fee = money(value)
        else:
            setattr(contract, key, value)
    db.commit()
    db.refresh(contract)
    return contract


def terminate_contract(db: Session, contract_id: int, reason: str) -> Contract:
    contract = get_contract(db, contract_id)
    if contract.status == ContractStatus.TERMINATED.value:
        raise DomainError("合同已处于终止状态")
    contract.status = ContractStatus.TERMINATED.value
    contract.terminate_reason = reason
    db.commit()
    db.refresh(contract)
    return contract


def delete_contract(db: Session, contract_id: int) -> None:
    """删除合同：已有月度结算记录时拒绝，保证费用台账可追溯。"""
    contract = get_contract(db, contract_id)
    settlement_count = db.scalar(
        select(func.count()).select_from(Settlement).where(Settlement.contract_id == contract_id)
    ) or 0
    if settlement_count:
        raise ConflictError(
            f"该合同已有 {settlement_count} 条月度结算记录，不能删除；"
            "不再履约可终止合同，历史台账将保留"
        )
    db.delete(contract)
    db.commit()


def restroom_contracts(db: Session, restroom_id: int) -> list[Contract]:
    """查询某座公厕当前受哪些合同覆盖（详情页反查用）。"""
    rows = list(
        db.scalars(
            select(Contract)
            .join(contract_restroom, contract_restroom.c.contract_id == Contract.id)
            .where(contract_restroom.c.restroom_id == restroom_id)
            .order_by(Contract.start_date.desc())
        )
    )
    today = datetime.now().date()
    return [row for row in rows if effective_status(row, today) == ContractStatus.ACTIVE.value]
