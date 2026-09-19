"""月度费用结算与考核扣款业务逻辑。"""

import calendar
from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    OPEN_ISSUE_STATUSES,
    OVERDUE_DEDUCTION_AMOUNT,
    QUALITY_DEDUCTION_TIERS,
    ISSUE_DEDUCTION_AMOUNTS,
    SETTLEMENT_TRANSITIONS,
    SettlementStatus,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import (
    CleaningContract,
    Inspection,
    Issue,
    MonthlySettlement,
    Restroom,
    SettlementInspection,
    SettlementIssue,
)
from app.schemas.vendor import (
    DeductionDetail,
    SettlementCreate,
    SettlementDetail,
    SettlementInspectionItem,
    SettlementIssueItem,
    SettlementOut,
    SettlementPreview,
    VendorBrief,
)
from app.services import vendor_service

SORTABLE_FIELDS = {
    "period_month": MonthlySettlement.period_month,
    "payable_amount": MonthlySettlement.payable_amount,
    "total_deduction": MonthlySettlement.total_deduction,
    "created_at": MonthlySettlement.created_at,
}


def parse_period(period_month: str) -> tuple[date, date]:
    """把 YYYY-MM 解析为周期起止日期。"""
    try:
        year, month = (int(part) for part in period_month.split("-"))
        if not 1 <= month <= 12:
            raise ValueError
    except (ValueError, AttributeError):
        raise DomainError("考核月份格式应为 YYYY-MM，例如 2026-08") from None
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _next_code(db: Session, period_month: str) -> str:
    prefix = f"JS-{period_month.replace('-', '')}"
    seq = (
        db.scalar(
            select(func.count()).select_from(MonthlySettlement).where(
                MonthlySettlement.code.like(f"{prefix}-%")
            )
        )
        or 0
    ) + 1
    while True:
        code = f"{prefix}-{seq:02d}"
        if not db.scalar(select(MonthlySettlement.id).where(MonthlySettlement.code == code)):
            return code
        seq += 1


def get_settlement(db: Session, settlement_id: int) -> MonthlySettlement:
    settlement = db.get(MonthlySettlement, settlement_id)
    if settlement is None:
        raise NotFoundError(f"结算单 {settlement_id} 不存在")
    return settlement


def _quality_rate(avg_score: float | None) -> tuple[float, str]:
    if avg_score is None:
        return 0.0, "当期无巡查记录，不扣质量款"
    descriptions = [
        (0.0, lambda: "均分达标，不扣质量款"),
        (0.01, lambda: f"当期巡查均分 {avg_score} 分，未达 90 分优秀线，按月费 1% 扣款"),
        (0.03, lambda: f"当期巡查均分 {avg_score} 分，低于 80 分良好线，按月费 3% 扣款"),
        (0.08, lambda: f"当期巡查均分 {avg_score} 分，低于 70 分合格线，按月费 8% 扣款"),
    ]
    for index, (threshold, rate) in enumerate(QUALITY_DEDUCTION_TIERS):
        if avg_score >= threshold:
            return rate, descriptions[index][1]()
    rate = QUALITY_DEDUCTION_TIERS[-1][1]
    return rate, f"均分 {avg_score} 分，低于 70 分合格线，按月费 {rate * 100:.0f}% 扣款"


def collect_metrics(
    db: Session, contract: CleaningContract, period_start: date, period_end: date
) -> dict:
    """汇总合同服务范围内、考核周期内的巡查与问题数据，并计算各项扣款。"""
    restroom_ids = vendor_service.scope_restroom_ids(db, contract)
    start_dt = datetime.combine(period_start, time.min)
    end_dt = datetime.combine(period_end, time.max)
    now = datetime.now()

    inspections: list[Inspection] = []
    issues: list[Issue] = []
    if restroom_ids:
        inspections = list(
            db.scalars(
                select(Inspection)
                .where(
                    Inspection.restroom_id.in_(restroom_ids),
                    Inspection.inspect_time >= start_dt,
                    Inspection.inspect_time <= end_dt,
                )
                .order_by(Inspection.inspect_time)
            )
        )
        issues = list(
            db.scalars(
                select(Issue)
                .where(
                    Issue.restroom_id.in_(restroom_ids),
                    Issue.report_time >= start_dt,
                    Issue.report_time <= end_dt,
                )
                .order_by(Issue.report_time)
            )
        )

    restroom_map = {
        r.id: r.name
        for r in db.scalars(
            select(Restroom).where(Restroom.id.in_(restroom_ids or [-1]))
        )
    }

    avg_score = (
        round(sum(i.score for i in inspections) / len(inspections), 1) if inspections else None
    )
    quality_rate, quality_basis = _quality_rate(avg_score)
    quality_deduction = round(contract.monthly_fee * quality_rate, 2)

    details: list[DeductionDetail] = []
    if quality_deduction > 0:
        details.append(
            DeductionDetail(
                type="quality",
                name=f"质量考核扣款（{quality_rate * 100:.0f}%）",
                amount=quality_deduction,
                basis=quality_basis,
            )
        )

    issue_total = 0.0
    overdue_total = 0.0
    issue_snapshots: list[dict] = []
    overdue_count = 0
    for issue in issues:
        amount = ISSUE_DEDUCTION_AMOUNTS.get(issue.severity, ISSUE_DEDUCTION_AMOUNTS["一般"])
        issue_total += amount
        details.append(
            DeductionDetail(
                type="issue",
                name=f"{issue.severity}问题 {issue.code}",
                amount=amount,
                basis=f"当期新增「{issue.category}」问题，{issue.severity}档扣款 {amount:.0f} 元",
                ref_id=issue.id,
            )
        )
        is_overdue = (
            issue.deadline is not None
            and issue.status in OPEN_ISSUE_STATUSES
            and issue.deadline < now
        )
        link_deduction = amount
        reason = f"当期新增{issue.severity}问题，扣款 {amount:.0f} 元"
        if is_overdue:
            overdue_count += 1
            overdue_total += OVERDUE_DEDUCTION_AMOUNT
            link_deduction += OVERDUE_DEDUCTION_AMOUNT
            reason += f"；超期未闭环，追加扣款 {OVERDUE_DEDUCTION_AMOUNT:.0f} 元"
            details.append(
                DeductionDetail(
                    type="overdue",
                    name=f"超期未闭环 {issue.code}",
                    amount=OVERDUE_DEDUCTION_AMOUNT,
                    basis=f"问题超期未闭环（期限 {issue.deadline:%Y-%m-%d}），追加扣款",
                    ref_id=issue.id,
                )
            )
        issue_snapshots.append(
            {
                "issue": issue,
                "restroom_name": restroom_map.get(issue.restroom_id, ""),
                "is_overdue": is_overdue,
                "deduction": round(link_deduction, 2),
                "reason": reason,
            }
        )

    inspection_snapshots = [
        {
            "inspection": item,
            "restroom_name": restroom_map.get(item.restroom_id, ""),
            "deduction": 0.0,
            "reason": "计入当月质量均分" + ("；发现问题" if item.result == "发现问题" else ""),
        }
        for item in inspections
    ]

    return {
        "inspections": inspection_snapshots,
        "issues": issue_snapshots,
        "inspection_count": len(inspections),
        "avg_score": avg_score,
        "issue_count": len(issues),
        "overdue_count": overdue_count,
        "quality_deduction": quality_deduction,
        "issue_deduction": round(issue_total, 2),
        "overdue_deduction": round(overdue_total, 2),
        "details": details,
        "quality_rate": quality_rate,
    }


def preview_settlement(
    db: Session, contract_id: int, period_month: str
) -> SettlementPreview:
    contract = vendor_service.get_contract(db, contract_id)
    period_start, period_end = parse_period(period_month)
    metrics = collect_metrics(db, contract, period_start, period_end)
    total = (
        metrics["quality_deduction"]
        + metrics["issue_deduction"]
        + metrics["overdue_deduction"]
    )
    return SettlementPreview(
        contract_id=contract_id,
        period_month=period_month,
        period_start=period_start,
        period_end=period_end,
        monthly_fee=contract.monthly_fee,
        inspection_count=metrics["inspection_count"],
        avg_score=metrics["avg_score"],
        issue_count=metrics["issue_count"],
        overdue_count=metrics["overdue_count"],
        quality_deduction=metrics["quality_deduction"],
        issue_deduction=metrics["issue_deduction"],
        overdue_deduction=metrics["overdue_deduction"],
        total_deduction=round(total, 2),
        payable_amount=round(max(0.0, contract.monthly_fee - total), 2),
        details=metrics["details"],
        inspections=[
            {
                "id": s["inspection"].id,
                "restroom_name": s["restroom_name"],
                "inspector": s["inspection"].inspector,
                "inspect_time": s["inspection"].inspect_time,
                "score": s["inspection"].score,
                "grade": s["inspection"].grade,
                "result": s["inspection"].result,
            }
            for s in metrics["inspections"]
        ],
        issues=[
            {
                "id": s["issue"].id,
                "code": s["issue"].code,
                "restroom_name": s["restroom_name"],
                "title": s["issue"].title,
                "category": s["issue"].category,
                "severity": s["issue"].severity,
                "status": s["issue"].status,
                "report_time": s["issue"].report_time,
                "deadline": s["issue"].deadline,
                "is_overdue": s["is_overdue"],
                "deduction": s["deduction"],
                "deduction_reason": s["reason"],
            }
            for s in metrics["issues"]
        ],
    )


def create_settlement(db: Session, payload: SettlementCreate) -> MonthlySettlement:
    contract = vendor_service.get_contract(db, payload.contract_id)
    period_start, period_end = parse_period(payload.period_month)
    if period_end < contract.start_date or period_start > contract.end_date:
        raise DomainError(
            f"考核月份 {payload.period_month} 不在合同期限"
            f"（{contract.start_date} ~ {contract.end_date}）内"
        )
    exists = db.scalar(
        select(MonthlySettlement.id).where(
            MonthlySettlement.contract_id == payload.contract_id,
            MonthlySettlement.period_month == payload.period_month,
        )
    )
    if exists:
        raise DomainError(f"该合同 {payload.period_month} 的结算单已存在，请勿重复登记")

    settlement = MonthlySettlement(
        code=_next_code(db, payload.period_month),
        contract_id=payload.contract_id,
        period_month=payload.period_month,
        period_start=period_start,
        period_end=period_end,
        monthly_fee=contract.monthly_fee,
        remark=payload.remark,
        status=SettlementStatus.PENDING.value,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def assess_settlement(
    db: Session, settlement_id: int, *, operator: str, remark: str | None = None
) -> MonthlySettlement:
    """按当期巡查质量与问题整改情况执行考核，固化扣款快照。"""
    settlement = get_settlement(db, settlement_id)
    if settlement.status == SettlementStatus.SETTLED.value:
        raise DomainError("结算单已确认结算，请先撤销结算再重新考核")
    contract = vendor_service.get_contract(db, settlement.contract_id)
    metrics = collect_metrics(db, contract, settlement.period_start, settlement.period_end)

    # 重新考核时清空旧的明细快照，保留其他扣款调整
    for link in list(settlement.inspection_links):
        db.delete(link)
    for link in list(settlement.issue_links):
        db.delete(link)
    db.flush()

    for snap in metrics["inspections"]:
        src = snap["inspection"]
        settlement.inspection_links.append(
            SettlementInspection(
                inspection_id=src.id,
                restroom_id=src.restroom_id,
                restroom_name=snap["restroom_name"],
                inspector=src.inspector,
                inspect_time=src.inspect_time,
                score=src.score,
                grade=src.grade,
                result=src.result,
                deduction=snap["deduction"],
                deduction_reason=snap["reason"],
            )
        )
    for snap in metrics["issues"]:
        src = snap["issue"]
        settlement.issue_links.append(
            SettlementIssue(
                issue_id=src.id,
                restroom_id=src.restroom_id,
                code=src.code,
                restroom_name=snap["restroom_name"],
                title=src.title,
                category=src.category,
                severity=src.severity,
                status=src.status,
                report_time=src.report_time,
                deadline=src.deadline,
                is_overdue=snap["is_overdue"],
                deduction=snap["deduction"],
                deduction_reason=snap["reason"],
            )
        )

    details = list(metrics["details"])
    if settlement.manual_deduction:
        details.append(
            DeductionDetail(
                type="manual",
                name="其他调整",
                amount=round(settlement.manual_deduction, 2),
                basis=settlement.manual_reason or "人工调整",
            )
        )

    settlement.monthly_fee = contract.monthly_fee
    settlement.quality_deduction = metrics["quality_deduction"]
    settlement.issue_deduction = metrics["issue_deduction"]
    settlement.overdue_deduction = metrics["overdue_deduction"]
    settlement.inspection_count = metrics["inspection_count"]
    settlement.avg_score = metrics["avg_score"]
    settlement.issue_count = metrics["issue_count"]
    settlement.overdue_count = metrics["overdue_count"]
    settlement.deduction_details = [item.model_dump() for item in details]
    auto_total = (
        metrics["quality_deduction"]
        + metrics["issue_deduction"]
        + metrics["overdue_deduction"]
        + settlement.manual_deduction
    )
    settlement.total_deduction = round(auto_total, 2)
    settlement.payable_amount = round(max(0.0, contract.monthly_fee - auto_total), 2)
    settlement.status = SettlementStatus.ASSESSED.value
    settlement.assessed_at = datetime.now()
    settlement.assessed_by = operator
    if remark is not None:
        settlement.remark = remark
    db.commit()
    db.refresh(settlement)
    return settlement


def update_manual(
    db: Session, settlement_id: int, *, manual_deduction: float, manual_reason: str
) -> MonthlySettlement:
    settlement = get_settlement(db, settlement_id)
    if settlement.status == SettlementStatus.SETTLED.value:
        raise DomainError("结算单已确认结算，不能再调整扣款")
    if settlement.status == SettlementStatus.PENDING.value:
        raise DomainError("请先完成考核，再登记其他扣款调整")
    if abs(manual_deduction) > settlement.monthly_fee:
        raise DomainError("调整金额不能超过当月合同费用")

    details = [
        item
        for item in (settlement.deduction_details or [])
        if item.get("type") != "manual"
    ]
    if manual_deduction:
        details.append(
            {
                "type": "manual",
                "name": "其他调整",
                "amount": round(manual_deduction, 2),
                "basis": manual_reason,
            }
        )
    settlement.manual_deduction = round(manual_deduction, 2)
    settlement.manual_reason = manual_reason if manual_deduction else ""
    settlement.deduction_details = details
    auto = (
        settlement.quality_deduction
        + settlement.issue_deduction
        + settlement.overdue_deduction
        + settlement.manual_deduction
    )
    settlement.total_deduction = round(auto, 2)
    settlement.payable_amount = round(max(0.0, settlement.monthly_fee - auto), 2)
    db.commit()
    db.refresh(settlement)
    return settlement


def change_status(db: Session, settlement_id: int, payload) -> MonthlySettlement:
    settlement = get_settlement(db, settlement_id)
    target = payload.to_status
    if target == settlement.status:
        raise DomainError(f"结算单已处于「{target}」状态")
    allowed = SETTLEMENT_TRANSITIONS.get(settlement.status, [])
    if target not in allowed:
        raise DomainError(
            f"当前状态「{settlement.status}」不允许变更为「{target}」，可选："
            + ("、".join(allowed) if allowed else "无")
        )

    settlement.status = target
    now = datetime.now()
    if target == SettlementStatus.SETTLED.value:
        settlement.settled_at = now
        settlement.settled_by = payload.operator
    elif target == SettlementStatus.ASSESSED.value:
        # 撤销结算：回到已考核状态
        settlement.settled_at = None
        settlement.settled_by = ""
        settlement.assessed_at = now
        settlement.assessed_by = payload.operator
    elif target == SettlementStatus.PENDING.value:
        # 退回重做：清空考核结果与逐笔快照，仅保留月度费用与月份
        settlement.assessed_at = None
        settlement.assessed_by = ""
        for link in list(settlement.inspection_links):
            db.delete(link)
        for link in list(settlement.issue_links):
            db.delete(link)
        settlement.quality_deduction = 0.0
        settlement.issue_deduction = 0.0
        settlement.overdue_deduction = 0.0
        settlement.manual_deduction = 0.0
        settlement.manual_reason = ""
        settlement.total_deduction = 0.0
        settlement.payable_amount = 0.0
        settlement.inspection_count = 0
        settlement.avg_score = None
        settlement.issue_count = 0
        settlement.overdue_count = 0
        settlement.deduction_details = []
    if payload.remark is not None:
        settlement.remark = payload.remark
    db.commit()
    db.refresh(settlement)
    return settlement


def allowed_transitions(settlement: MonthlySettlement) -> list[dict[str, str]]:
    from app.core.constants import SETTLEMENT_TRANSITION_ACTIONS

    return [
        {
            "status": target,
            "action": SETTLEMENT_TRANSITION_ACTIONS.get(
                (settlement.status, target), "状态变更"
            ),
        }
        for target in SETTLEMENT_TRANSITIONS.get(settlement.status, [])
    ]


def list_settlements(
    db: Session,
    *,
    contract_id: int | None = None,
    vendor_id: int | None = None,
    status: str | None = None,
    period_month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "period_month",
    order: str = "desc",
) -> tuple[list[MonthlySettlement], int]:
    stmt = select(MonthlySettlement).join(
        CleaningContract, CleaningContract.id == MonthlySettlement.contract_id
    )
    if contract_id:
        stmt = stmt.where(MonthlySettlement.contract_id == contract_id)
    if vendor_id:
        stmt = stmt.where(CleaningContract.vendor_id == vendor_id)
    if status:
        stmt = stmt.where(MonthlySettlement.status == status)
    if period_month:
        stmt = stmt.where(MonthlySettlement.period_month == period_month)
    if date_from:
        stmt = stmt.where(MonthlySettlement.period_start >= date_from)
    if date_to:
        stmt = stmt.where(MonthlySettlement.period_end <= date_to)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            MonthlySettlement.code.like(like)
            | CleaningContract.code.like(like)
            | CleaningContract.name.like(like)
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, MonthlySettlement.period_month)
    stmt = (
        stmt.order_by(column.desc() if order == "desc" else column.asc(), MonthlySettlement.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt)), total


def _to_out(settlement: MonthlySettlement) -> SettlementOut:
    out = SettlementOut.model_validate(settlement)
    if settlement.contract is not None:
        out.vendor = VendorBrief.model_validate(settlement.contract.vendor)
    return out


def to_out(settlement: MonthlySettlement) -> SettlementOut:
    return _to_out(settlement)


def to_detail(settlement: MonthlySettlement) -> SettlementDetail:
    detail = SettlementDetail.model_validate(settlement)
    if settlement.contract is not None:
        detail.vendor = VendorBrief.model_validate(settlement.contract.vendor)
    detail.inspection_links = [
        SettlementInspectionItem.model_validate(link) for link in settlement.inspection_links
    ]
    detail.issue_links = [
        SettlementIssueItem.model_validate(link) for link in settlement.issue_links
    ]
    return detail


def delete_settlement(db: Session, settlement_id: int) -> None:
    settlement = get_settlement(db, settlement_id)
    if settlement.status == SettlementStatus.SETTLED.value:
        raise DomainError("已确认结算的台账不能删除，请先撤销结算")
    db.delete(settlement)
    db.commit()


def trace_by_inspection(db: Session, inspection_id: int) -> list[dict]:
    """巡查记录 → 考核结算单的反向追溯。"""
    rows = db.scalars(
        select(SettlementInspection).where(SettlementInspection.inspection_id == inspection_id)
    ).all()
    return [_trace_item(db, row.settlement_id, row.deduction, row.deduction_reason) for row in rows]


def trace_by_issue(db: Session, issue_id: int) -> list[dict]:
    """问题记录 → 考核结算单的反向追溯。"""
    rows = db.scalars(
        select(SettlementIssue).where(SettlementIssue.issue_id == issue_id)
    ).all()
    return [_trace_item(db, row.settlement_id, row.deduction, row.deduction_reason) for row in rows]


def _trace_item(
    db: Session, settlement_id: int, deduction: float, reason: str
) -> dict:
    settlement = get_settlement(db, settlement_id)
    contract = settlement.contract
    return {
        "settlement_id": settlement.id,
        "code": settlement.code,
        "contract_id": contract.id,
        "contract_code": contract.code,
        "contract_name": contract.name,
        "vendor_name": contract.vendor.name,
        "period_month": settlement.period_month,
        "status": settlement.status,
        "payable_amount": settlement.payable_amount,
        "total_deduction": settlement.total_deduction,
        "deduction": round(float(deduction or 0), 2),
        "deduction_reason": reason or "",
        "assessed_at": settlement.assessed_at,
    }
