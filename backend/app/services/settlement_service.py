"""月度考核与费用结算业务逻辑。

考核口径：
- 巡查质量：合同服务范围内公厕当月巡查均分，按 SCORE_DEDUCTION_RULES 扣款；
- 问题整改：当月新上报问题按严重程度计扣，期末仍超期未闭环的问题加倍计扣，
  验收驳回按次计扣；自动扣款合计封顶为月费用的 30%；
- 其他扣款与奖励由考核人手工登记。
每条扣款都写入 details 依据明细，关联到具体的巡查记录/问题工单，
实现「结算金额 ←→ 考核结果 ←→ 巡查与问题」的互相追溯。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    ASSESS_BASIC,
    ASSESS_EXCELLENT,
    ASSESS_FAIL,
    ASSESS_QUALIFIED,
    ISSUE_NEW_DEDUCTION,
    ISSUE_OVERDUE_DEDUCTION,
    ISSUE_REJECT_DEDUCTION,
    MAX_AUTO_DEDUCTION_RATE,
    OPEN_ISSUE_STATUSES,
    SCORE_DEDUCTION_RULES,
    ContractStatus,
    SettlementStatus,
)
from app.core.exceptions import DomainError, NotFoundError
from app.models import Contract, Inspection, Issue, RectificationRecord, Settlement
from app.schemas.settlement import (
    DeductionEvidence,
    SettlementAdjust,
    SettlementConfirm,
    SettlementCreate,
    SettlementDetail,
    SettlementOut,
)
from app.services import contract_service

SORTABLE_FIELDS = {
    "period_year": Settlement.period_year,
    "monthly_fee": Settlement.monthly_fee,
    "payable_amount": Settlement.payable_amount,
    "total_deduction": Settlement.total_deduction,
    "created_at": Settlement.created_at,
}


def money(value: float) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def period_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def period_label(year: int, month: int) -> str:
    return f"{year} 年 {month} 月"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def get_settlement(db: Session, settlement_id: int) -> Settlement:
    row = db.get(Settlement, settlement_id)
    if row is None:
        raise NotFoundError(f"结算单 {settlement_id} 不存在")
    return row


def _next_code(db: Session, year: int, month: int) -> str:
    prefix = f"JS-{year}{month:02d}-"
    seq = (
        db.scalar(
            select(func.count()).select_from(Settlement).where(Settlement.code.like(f"{prefix}%"))
        )
        or 0
    ) + 1
    while True:
        code = f"{prefix}{seq:03d}"
        if not db.scalar(select(Settlement.id).where(Settlement.code == code)):
            return code
        seq += 1


def _score_rule(avg_score: float | None) -> tuple[float, str]:
    """返回（扣款比例，适用说明）；当月无巡查记录时不扣巡查项。"""
    if avg_score is None:
        return 0.0, "当月无巡查记录，巡查质量项不计扣"
    for threshold, rate, note in SCORE_DEDUCTION_RULES:
        if avg_score >= threshold:
            return rate, note
    return SCORE_DEDUCTION_RULES[-1][1], SCORE_DEDUCTION_RULES[-1][2]


def _grade(avg_score: float | None, new_count: int, overdue_count: int, reject_count: int) -> str:
    if avg_score is not None and avg_score < 70:
        return ASSESS_FAIL
    if overdue_count > 0 or (avg_score is not None and avg_score < 80):
        return ASSESS_BASIC
    if avg_score is not None and avg_score >= 90 and new_count == 0 and reject_count == 0:
        return ASSESS_EXCELLENT
    if avg_score is None and (new_count or overdue_count):
        return ASSESS_BASIC
    return ASSESS_QUALIFIED


def collect_assessment(
    db: Session, contract: Contract, year: int, month: int, fee_override: float | None = None
) -> dict:
    """按合同服务范围统计当月考核数据并生成扣款依据，不落库。"""
    start, end = period_range(year, month)
    now = datetime.now()
    cutoff = min(now, end)
    scope_ids = [room.id for room in contract.restrooms]
    fee = contract.monthly_fee if fee_override is None else fee_override

    inspections: list[Inspection] = []
    issues: list[Issue] = []
    rejects: list[RectificationRecord] = []
    if scope_ids:
        inspections = list(
            db.scalars(
                select(Inspection)
                .where(
                    Inspection.restroom_id.in_(scope_ids),
                    Inspection.inspect_time >= start,
                    Inspection.inspect_time < end,
                )
                .order_by(Inspection.inspect_time)
            )
        )
        issues = list(
            db.scalars(
                select(Issue)
                .where(Issue.restroom_id.in_(scope_ids))
                .order_by(Issue.report_time)
            )
        )
        rejects = list(
            db.scalars(
                select(RectificationRecord)
                .join(Issue, Issue.id == RectificationRecord.issue_id)
                .where(
                    Issue.restroom_id.in_(scope_ids),
                    RectificationRecord.action == "验收驳回",
                    RectificationRecord.created_at >= start,
                    RectificationRecord.created_at < end,
                )
            )
        )

    inspection_count = len(inspections)
    avg_score = round(sum(item.score for item in inspections) / inspection_count, 1) if inspections else None

    new_issues = [issue for issue in issues if start <= issue.report_time < end]
    overdue_ids: set[int] = set()
    overdue_issues = []
    for issue in issues:
        # 期末仍超期未闭环：期限在考核期末前已到，且到期末仍未闭环
        # （含期末后才闭环的问题）；期初之前已关闭的历史问题不计入，
        # 避免同一条问题在后续月份重复计扣。
        if (
            issue.deadline is not None
            and issue.deadline < cutoff
            and (
                issue.status in OPEN_ISSUE_STATUSES
                or (issue.closed_at is not None and issue.closed_at > cutoff)
            )
            and (issue.closed_at is None or issue.closed_at >= start)
            and issue.report_time < end
            and issue.id not in overdue_ids
        ):
            overdue_ids.add(issue.id)
            overdue_issues.append(issue)

    evidences: list[dict] = []

    rate, score_note = _score_rule(avg_score)
    score_deduction = money(fee * rate)
    evidences.append(
        DeductionEvidence(
            type="score",
            title=(
                f"巡查质量扣款：{score_note}（当月 {inspection_count} 次巡查，"
                f"均分 {avg_score if avg_score is not None else '无'}）"
            ),
            amount=score_deduction,
            ref_type="inspection",
            ref_time=None,
            meta={"rate": rate, "avg_score": avg_score, "inspection_count": inspection_count},
        ).model_dump()
    )

    issue_deduction = 0.0
    for issue in new_issues:
        standard = ISSUE_NEW_DEDUCTION.get(issue.severity, ISSUE_NEW_DEDUCTION["一般"])
        issue_deduction += standard
        evidences.append(
            DeductionEvidence(
                type="new_issue",
                title=f"当月新上报问题（{issue.severity}）：{issue.title}",
                amount=float(standard),
                ref_type="issue",
                ref_id=issue.id,
                ref_code=issue.code,
                ref_time=_iso(issue.report_time),
                meta={"standard": standard, "severity": issue.severity},
            ).model_dump()
        )
    issue_deduction = money(issue_deduction)

    overdue_deduction = 0.0
    for issue in overdue_issues:
        overdue_deduction += ISSUE_OVERDUE_DEDUCTION
        evidences.append(
            DeductionEvidence(
                type="overdue",
                title=f"期末超期未闭环问题：{issue.title}",
                amount=float(ISSUE_OVERDUE_DEDUCTION),
                ref_type="issue",
                ref_id=issue.id,
                ref_code=issue.code,
                ref_time=_iso(issue.deadline),
                meta={"standard": ISSUE_OVERDUE_DEDUCTION},
            ).model_dump()
        )
    overdue_deduction = money(overdue_deduction)

    reject_deduction = money(len(rejects) * ISSUE_REJECT_DEDUCTION)
    rejected_issue_ids = {record.issue_id for record in rejects}
    for record in rejects:
        issue = next((item for item in issues if item.id == record.issue_id), None)
        evidences.append(
            DeductionEvidence(
                type="reject",
                title=f"验收驳回 1 次：{issue.title if issue else '关联问题'}（{record.remark or ''}）",
                amount=float(ISSUE_REJECT_DEDUCTION),
                ref_type="issue",
                ref_id=record.issue_id,
                ref_code=issue.code if issue else "",
                ref_time=_iso(record.created_at),
                meta={"standard": ISSUE_REJECT_DEDUCTION, "record_id": record.id},
            ).model_dump()
        )

    auto_total = money(
        score_deduction + issue_deduction + overdue_deduction + reject_deduction
    )
    cap = money(fee * MAX_AUTO_DEDUCTION_RATE)
    if auto_total > cap and cap >= 0:
        evidences.append(
            DeductionEvidence(
                type="cap",
                title=f"自动扣款封顶：按月费用 {int(MAX_AUTO_DEDUCTION_RATE * 100)}% 封顶调整",
                amount=money(cap - auto_total),
                ref_type="",
                meta={"cap": cap, "auto_total": auto_total},
            ).model_dump()
        )
        auto_capped = cap
    else:
        auto_capped = auto_total

    grade = _grade(avg_score, len(new_issues), len(overdue_issues), len(rejects))

    return {
        "monthly_fee": money(fee),
        "inspection_count": inspection_count,
        "avg_score": avg_score,
        "issue_new_count": len(new_issues),
        "issue_overdue_count": len(overdue_issues),
        "issue_reject_count": len(rejects),
        "score_deduction": score_deduction,
        "issue_deduction": issue_deduction,
        "overdue_deduction": overdue_deduction,
        "reject_deduction": reject_deduction,
        "auto_deduction": auto_capped,
        "rejected_issue_ids": sorted(rejected_issue_ids),
        "assess_grade": grade,
        "details": evidences,
    }


def _recompute_amounts(row: Settlement) -> None:
    """依据各项扣款与奖励重算合计与应付金额。"""
    auto_total = money(
        row.score_deduction
        + row.issue_deduction
        + row.overdue_deduction
        + row.reject_deduction
    )
    cap = money(row.monthly_fee * MAX_AUTO_DEDUCTION_RATE)
    auto_capped = min(auto_total, cap)
    gross = money(auto_capped + (row.other_deduction or 0.0))
    total = money(gross - (row.bonus or 0.0))
    payable = money(row.monthly_fee - total)
    if payable < 0:
        payable = 0.0
    row.total_deduction = total
    row.payable_amount = payable


def recompute_preview(
    summary: dict, *, monthly_fee_override: float | None = None
) -> tuple[float, float]:
    """测算预览：返回（扣款合计、应付金额），不含手工项。"""
    fee = money(
        summary["monthly_fee"] if monthly_fee_override is None else monthly_fee_override
    )
    total = money(summary["auto_deduction"])
    payable = max(0.0, money(fee - total))
    return total, payable


def assess_settlement(
    db: Session, contract_id: int, payload: SettlementCreate
) -> Settlement:
    contract = contract_service.get_contract(db, contract_id)
    if contract.status == ContractStatus.TERMINATED.value:
        raise DomainError("合同已终止，不能再生成结算单")

    start, end = period_range(payload.period_year, payload.period_month)
    if start.date() > contract.end_date or end.date() <= contract.start_date:
        raise DomainError(
            f"{period_label(payload.period_year, payload.period_month)}不在合同期限"
            f"（{contract.start_date} ~ {contract.end_date}）内，不能生成结算单"
        )
    exists = db.scalar(
        select(Settlement.id).where(
            Settlement.contract_id == contract_id,
            Settlement.period_year == payload.period_year,
            Settlement.period_month == payload.period_month,
        )
    )
    if exists:
        raise DomainError(
            f"{period_label(payload.period_year, payload.period_month)}的结算单已存在，"
            "未结算前可在详情中重新考核"
        )

    summary = collect_assessment(db, contract, payload.period_year, payload.period_month)
    row = Settlement(
        code=_next_code(db, payload.period_year, payload.period_month),
        contract_id=contract_id,
        period_year=payload.period_year,
        period_month=payload.period_month,
        monthly_fee=(
            money(payload.monthly_fee) if payload.monthly_fee is not None else summary["monthly_fee"]
        ),
        inspection_count=summary["inspection_count"],
        avg_score=summary["avg_score"],
        issue_new_count=summary["issue_new_count"],
        issue_overdue_count=summary["issue_overdue_count"],
        issue_reject_count=summary["issue_reject_count"],
        score_deduction=summary["score_deduction"],
        issue_deduction=summary["issue_deduction"],
        overdue_deduction=summary["overdue_deduction"],
        reject_deduction=summary["reject_deduction"],
        assess_grade=summary["assess_grade"],
        assess_remark=payload.assess_remark,
        details=summary["details"],
        assessor=payload.assessor,
        assess_time=datetime.now(),
        status=SettlementStatus.ASSESSED.value,
    )
    _recompute_amounts(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def reassess_settlement(db: Session, settlement_id: int) -> Settlement:
    """按最新巡查/问题数据重新考核，仅「已考核」状态允许。"""
    row = get_settlement(db, settlement_id)
    _require_status(row, SettlementStatus.ASSESSED.value, "重新考核")
    contract = contract_service.get_contract(db, row.contract_id)
    summary = collect_assessment(
        db, contract, row.period_year, row.period_month, fee_override=row.monthly_fee
    )
    row.inspection_count = summary["inspection_count"]
    row.avg_score = summary["avg_score"]
    row.issue_new_count = summary["issue_new_count"]
    row.issue_overdue_count = summary["issue_overdue_count"]
    row.issue_reject_count = summary["issue_reject_count"]
    row.score_deduction = summary["score_deduction"]
    row.issue_deduction = summary["issue_deduction"]
    row.overdue_deduction = summary["overdue_deduction"]
    row.reject_deduction = summary["reject_deduction"]
    row.assess_grade = summary["assess_grade"]
    row.details = summary["details"]
    row.assess_time = datetime.now()
    _sync_manual_details(row)
    _recompute_amounts(row)
    db.commit()
    db.refresh(row)
    return row


def adjust_settlement(db: Session, settlement_id: int, payload: SettlementAdjust) -> Settlement:
    row = get_settlement(db, settlement_id)
    _require_status(row, SettlementStatus.ASSESSED.value, "调整")
    if payload.other_deduction is not None:
        row.other_deduction = money(payload.other_deduction)
    if payload.other_reason is not None:
        row.other_reason = payload.other_reason
    if payload.bonus is not None:
        row.bonus = money(payload.bonus)
    if payload.monthly_fee is not None:
        row.monthly_fee = money(payload.monthly_fee)
    if payload.assess_remark is not None:
        row.assess_remark = payload.assess_remark
    _sync_manual_details(row)
    _recompute_amounts(row)
    db.commit()
    db.refresh(row)
    return row


def _sync_manual_details(row: Settlement) -> None:
    """手工项同步进依据明细，保证详情页金额可逐项解释。"""
    auto = [item for item in (row.details or []) if item.get("type") in ("score", "new_issue", "overdue", "reject", "cap")]
    manual: list[dict] = []
    if row.other_deduction:
        manual.append(
            DeductionEvidence(
                type="manual",
                title=f"其他扣款：{row.other_reason or '考核人手工登记'}",
                amount=money(row.other_deduction),
            ).model_dump()
        )
    if row.bonus:
        manual.append(
            DeductionEvidence(
                type="bonus",
                title="考核奖励：考核人手工登记",
                amount=money(-row.bonus),
            ).model_dump()
        )
    row.details = auto + manual


def confirm_settlement(db: Session, settlement_id: int, payload: SettlementConfirm) -> Settlement:
    row = get_settlement(db, settlement_id)
    _require_status(row, SettlementStatus.ASSESSED.value, "确认结算")
    row.status = SettlementStatus.SETTLED.value
    row.settle_operator = payload.operator
    row.settle_remark = payload.remark
    row.settle_time = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def _require_status(row: Settlement, status: str, action: str) -> None:
    if row.status != status:
        raise DomainError(f"结算单当前为「{row.status}」，不能{action}")


def delete_settlement(db: Session, settlement_id: int) -> None:
    row = get_settlement(db, settlement_id)
    _require_status(row, SettlementStatus.ASSESSED.value, "删除")
    db.delete(row)
    db.commit()


def to_out(row: Settlement) -> SettlementOut:
    data = SettlementOut.model_validate(row)
    data.period = row.period
    return data


def to_detail(db: Session, row: Settlement) -> SettlementDetail:
    contract = contract_service.get_contract(db, row.contract_id)
    base = to_out(row).model_dump()
    return SettlementDetail(
        **base,
        vendor_name=contract.vendor.name,
        contract_name=contract.name,
        contract_code=contract.code,
        evidences=[DeductionEvidence.model_validate(item) for item in (row.details or [])],
    )


def list_settlements(
    db: Session,
    *,
    contract_id: int | None = None,
    vendor_id: int | None = None,
    period_year: int | None = None,
    period_month: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    order: str = "desc",
) -> tuple[list[Settlement], int]:
    stmt = select(Settlement).join(Contract, Contract.id == Settlement.contract_id)
    if contract_id:
        stmt = stmt.where(Settlement.contract_id == contract_id)
    if vendor_id:
        stmt = stmt.where(Contract.vendor_id == vendor_id)
    if period_year:
        stmt = stmt.where(Settlement.period_year == period_year)
    if period_month:
        stmt = stmt.where(Settlement.period_month == period_month)
    if status:
        stmt = stmt.where(Settlement.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Settlement.code.like(like),
                Contract.code.like(like),
                Contract.name.like(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, Settlement.created_at)
    stmt = stmt.order_by(
        Settlement.period_year.desc(),
        Settlement.period_month.desc(),
        column.desc() if order == "desc" else column.asc(),
        Settlement.id.desc(),
    )
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique())
    return rows, total


def list_by_issue(db: Session, issue_id: int) -> list[tuple[Settlement, list[dict]]]:
    """反向追溯：某条问题被哪些月度考核单计扣过。

    遍历结算单的依据明细，返回 (结算单, 命中的依据条目) 列表。
    """
    rows = list(
        db.scalars(
            select(Settlement).order_by(
                Settlement.period_year.desc(), Settlement.period_month.desc()
            )
        )
    )
    hits: list[tuple[Settlement, list[dict]]] = []
    for row in rows:
        matched = [
            item
            for item in (row.details or [])
            if item.get("ref_type") == "issue" and item.get("ref_id") == issue_id
        ]
        if matched:
            hits.append((row, matched))
    return hits
