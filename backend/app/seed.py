"""演示数据生成：首次启动时写入，便于快速体验各模块。"""

import random
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    INSPECTION_CHECK_ITEMS,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    RestroomGrade,
    RestroomStatus,
    Shift,
)
from app.models import Issue, Restroom
from app.schemas.contract import ContractCreate
from app.schemas.inspection import InspectionCreate, InspectionItem
from app.schemas.issue import IssueCreate, IssueStatusUpdate
from app.schemas.restroom import RestroomCreate
from app.schemas.settlement import SettlementConfirm, SettlementCreate
from app.schemas.vendor import VendorCreate
from app.services import (
    contract_service,
    inspection_service,
    issue_service,
    restroom_service,
    settlement_service,
    vendor_service,
)

RANDOM_SEED = 20240913

RESTROOM_SPECS = [
    ("人民广场公共厕所", "城东区", "人民广场东侧 50 米", RestroomGrade.FIRST, RestroomStatus.NORMAL, "王秀兰", 12, 6, True),
    ("滨江公园公共厕所", "城东区", "滨江公园 3 号入口", RestroomGrade.SECOND, RestroomStatus.NORMAL, "李国强", 8, 4, True),
    ("和平路公共厕所", "城东区", "和平路与解放街交叉口", RestroomGrade.THIRD, RestroomStatus.MAINTENANCE, "赵敏", 4, 2, False),
    ("火车站南广场公共厕所", "城西区", "火车站南广场西侧", RestroomGrade.FIRST, RestroomStatus.NORMAL, "陈志远", 16, 8, True),
    ("西城集贸市场公共厕所", "城西区", "西城集贸市场北门", RestroomGrade.SECOND, RestroomStatus.NORMAL, "刘桂芳", 10, 4, False),
    ("文化路步行街公共厕所", "城西区", "文化路步行街中段", RestroomGrade.SECOND, RestroomStatus.NORMAL, "孙鹏", 9, 5, True),
    ("滨江新区体育中心公共厕所", "滨江新区", "体育中心东看台下", RestroomGrade.FIRST, RestroomStatus.NORMAL, "周晓燕", 14, 7, True),
    ("滨江新区政务中心公共厕所", "滨江新区", "政务服务中心一楼", RestroomGrade.SECOND, RestroomStatus.NORMAL, "吴建华", 8, 4, True),
    ("老城隍庙公共厕所", "老城区", "城隍庙街 12 号", RestroomGrade.THIRD, RestroomStatus.NORMAL, "郑淑珍", 5, 2, False),
    ("老城区第三小学旁公共厕所", "老城区", "第三小学东侧巷道", RestroomGrade.THIRD, RestroomStatus.CLOSED, "何伟", 4, 2, False),
]

INSPECTORS = ["张伟", "刘洋", "胡明月", "邓晨曦", "马晓峰", "杨柳"]
MANAGERS = ["王秀兰", "李国强", "陈志远", "刘桂芳", "周晓燕", "吴建华", "郑淑珍", "孙鹏"]

ISSUE_TEMPLATES = {
    IssueCategory.CLEANING: [
        "地面存在明显污渍未及时清理",
        "蹲位清洁不彻底，存在残留",
        "垃圾篓内垃圾未及时清运",
    ],
    IssueCategory.FACILITY: [
        "水龙头漏水，需更换阀芯",
        "感应冲水器失灵，无法自动冲水",
        "隔间门锁损坏无法反锁",
    ],
    IssueCategory.ODOR: [
        "公厕内异味明显，通风效果差",
        "排风扇停转导致异味积聚",
    ],
    IssueCategory.CONSUMABLE: [
        "洗手液未及时补充",
        "纸巾盒空置，未补充厕纸",
    ],
    IssueCategory.SAFETY: [
        "地面湿滑未放置防滑警示牌",
        "照明灯具损坏，夜间存在安全隐患",
    ],
    IssueCategory.OTHER: [
        "无障碍扶手松动需加固",
        "标识牌褪色需更换",
    ],
}

CATEGORY_BY_ITEM = {
    "地面与台阶清洁": IssueCategory.CLEANING,
    "便池蹲位清洁": IssueCategory.CLEANING,
    "洗手台与镜面": IssueCategory.CLEANING,
    "通风除臭": IssueCategory.ODOR,
    "耗材补充": IssueCategory.CONSUMABLE,
    "垃圾清运": IssueCategory.CLEANING,
    "工具与标识摆放": IssueCategory.OTHER,
    "墙面门窗卫生": IssueCategory.CLEANING,
}

# 外包合同规划：(单位名, 联系人, 服务区域, 月费用, 覆盖的公厕序号)
VENDOR_SPECS = [
    ("城东环卫服务有限公司", "马建华", ["城东区"], 42000.0, [0, 1, 2]),
    ("西城美洁物业管理有限公司", "林晓峰", ["城西区"], 48000.0, [3, 4, 5]),
    ("滨江新城环境工程有限公司", "赵雅琴", ["滨江新区"], 36000.0, [6, 7]),
]
OLD_DISTRICT_VENDOR = ("老城保洁服务队", "钱德海", ["老城区"], 18000.0, [8, 9])


def _build_items(rng: random.Random, quality: float) -> list[InspectionItem]:
    items: list[InspectionItem] = []
    for name in INSPECTION_CHECK_ITEMS:
        score = quality + rng.uniform(-1.6, 1.4)
        items.append(InspectionItem(name=name, score=max(0, min(10, round(score)))))
    return items


def _pick_problem(items: list[InspectionItem]) -> str | None:
    """找出最需要整改的检查项：优先取不合格项，否则取得分最低的一项。"""
    if not items:
        return None
    problems = [item for item in items if item.score < 6]
    pool = problems or items
    return min(pool, key=lambda item: item.score).name


def seed_database(db: Session, *, reset: bool = False) -> int:
    """写入演示数据，返回新增的问题条数；已有数据时默认跳过。"""
    existing = db.scalar(select(func.count()).select_from(Restroom)) or 0
    if existing and not reset:
        return 0

    rng = random.Random(RANDOM_SEED)
    now = datetime.now()

    restrooms = [
        restroom_service.create_restroom(
            db,
            RestroomCreate(
                name=name,
                district=district,
                address=address,
                grade=grade,
                status=status,
                manager=manager,
                manager_phone=f"13{rng.randint(100000000, 999999999)}",
                stall_count=stalls,
                basin_count=basins,
                has_accessible=accessible,
                open_hours="06:00-22:30" if grade == RestroomGrade.FIRST else "06:30-21:30",
            ),
        )
        for name, district, address, grade, status, manager, stalls, basins, accessible in RESTROOM_SPECS
    ]

    quality_by_restroom = {room.id: rng.uniform(7.4, 9.8) for room in restrooms}
    inspection_ids: list[tuple[int, int]] = []  # (restroom_id, inspection_id)

    for offset in range(44, -1, -1):
        day = now - timedelta(days=offset)
        for room in restrooms:
            if room.status == RestroomStatus.CLOSED:
                continue
            if rng.random() < 0.3:
                continue
            quality = quality_by_restroom[room.id] + rng.uniform(-1.0, 0.6)
            if rng.random() < 0.18:
                quality -= 2.6
            items = _build_items(rng, quality)
            inspection = inspection_service.create_inspection(
                db,
                InspectionCreate(
                    restroom_id=room.id,
                    inspector=rng.choice(INSPECTORS),
                    shift=rng.choice(list(Shift)),
                    inspect_time=day.replace(
                        hour=rng.choice([8, 10, 14, 16, 19]), minute=rng.choice([5, 20, 35, 50])
                    ),
                    items=items,
                    remark=None,
                ),
            )
            inspection_ids.append((room.id, inspection.id))

    created = 0
    for restroom_id, inspection_id in inspection_ids:
        summary = inspection_service.get_inspection(db, inspection_id)
        if summary.result != "发现问题" or rng.random() > 0.75:
            continue
        problem_item = _pick_problem([InspectionItem(**item) for item in summary.items])
        category = CATEGORY_BY_ITEM.get(problem_item or "", IssueCategory.OTHER)
        title = rng.choice(ISSUE_TEMPLATES[category])
        severity = (
            IssueSeverity.URGENT
            if category in (IssueCategory.SAFETY, IssueCategory.FACILITY) and rng.random() < 0.3
            else rng.choice([IssueSeverity.NORMAL, IssueSeverity.SERIOUS])
        )
        age_days = (now - summary.inspect_time).days
        deadline = summary.inspect_time + timedelta(
            days=1 if severity == IssueSeverity.URGENT else 3
        )
        issue = issue_service.create_issue(
            db,
            IssueCreate(
                restroom_id=restroom_id,
                inspection_id=inspection_id,
                report_time=summary.inspect_time,
                title=title,
                description=f"巡查得分 {summary.score} 分（{summary.grade}），检查项「{problem_item}」不达标，请安排整改。",
                category=category,
                severity=severity,
                reporter=summary.inspector,
                assignee=rng.choice(MANAGERS),
                deadline=deadline,
                initial_remark="由保洁巡查自动生成的问题工单",
            ),
        )
        created += 1
        _advance_issue(db, issue.id, age_days, rng)

    _seed_contracts(db, restrooms, now)

    return created


def _seed_contracts(db: Session, restrooms: list, now: datetime) -> None:
    """登记外包单位与合同，并为历史月份生成考核结算单。"""
    specs = VENDOR_SPECS + [OLD_DISTRICT_VENDOR]
    contracts = []
    for index, (name, contact, districts, fee, room_indexes) in enumerate(specs):
        vendor = vendor_service.create_vendor(
            db,
            VendorCreate(
                name=name,
                contact_person=contact,
                contact_phone=f"139{index:08d}",
                address=f"{districts[0]}环卫大厦 {index + 1} 层",
                qualification="环卫保洁服务一级资质" if index < 2 else "环卫保洁服务二级资质",
            ),
        )
        scope_ids = [restrooms[i].id for i in room_indexes]
        # 老城区合同年初签订、上月到期，其余覆盖整个年度
        start = date(now.year, 1, 1)
        end = (
            date(now.year, now.month, 1) - timedelta(days=1)
            if index == len(specs) - 1
            else date(now.year, 12, 31)
        )
        contract = contract_service.create_contract(
            db,
            ContractCreate(
                vendor_id=vendor.id,
                name=f"{districts[0]}公厕保洁外包服务合同",
                service_scope=f"{ '、'.join(districts) }共 {len(scope_ids)} 座公厕日常保洁、耗材补给与垃圾清运",
                scope_districts=districts,
                start_date=start,
                end_date=end,
                signed_date=date(now.year, 1, 1),
                monthly_fee=fee,
                restroom_ids=scope_ids,
            ),
        )
        contracts.append(contract)

    # 为最近两个月生成结算单：上月已结算、本月已考核待结算
    first_of_month = now.replace(day=1)
    prev_month_end = first_of_month - timedelta(days=1)
    prev_year, prev_month = prev_month_end.year, prev_month_end.month
    for index, contract in enumerate(contracts):
        if contract.start_date > date(prev_year, prev_month, 1):
            continue
        settled = settlement_service.assess_settlement(
            db,
            contract.id,
            SettlementCreate(
                period_year=prev_year,
                period_month=prev_month,
                assessor="考核组",
                assess_remark="按当月巡查与整改数据自动核算，已复核",
            ),
        )
        settlement_service.confirm_settlement(
            db,
            settled.id,
            SettlementConfirm(operator="财务科", remark="上月费用已随月度请款支付"),
        )
        # 本月结算单：前两份正常，第三份留待系统中演示「已考核」
        if index < 3 and contract.start_date <= now.date():
            settlement_service.assess_settlement(
                db,
                contract.id,
                SettlementCreate(
                    period_year=now.year,
                    period_month=now.month,
                    assessor="考核组",
                    assess_remark="本月巡查数据持续更新中，结算前可重新考核",
                ),
            )


def _advance_issue(db: Session, issue_id: int, age_days: int, rng: random.Random) -> None:
    """按问题存在时长模拟整改进度，让看板呈现多种状态。"""
    steps: list[tuple[str, str, str]] = []
    if age_days >= 1:
        steps.append(
            (
                IssueStatus.PROCESSING.value,
                "街办保洁队",
                "已派单至保洁班组，安排当日整改",
            )
        )
    if age_days >= 3:
        # 约三成问题首次验收被驳回，整改后重新提交，形成验收驳回扣款记录
        if rng.random() < 0.3:
            steps.append(
                (
                    IssueStatus.REVIEWING.value,
                    "整改责任人",
                    "整改完成，提交巡查员验收",
                )
            )
            steps.append(
                (
                    IssueStatus.PROCESSING.value,
                    "巡查员",
                    "验收驳回：整改不彻底，需返工",
                )
            )
        steps.append(
            (
                IssueStatus.REVIEWING.value,
                "整改责任人",
                "整改完成，提交巡查员验收",
            )
        )
    if age_days >= 5 and rng.random() < 0.75:
        steps.append((IssueStatus.DONE.value, "巡查员", "现场复核通过，问题已闭环"))
    if age_days >= 8 and rng.random() < 0.6:
        steps.append((IssueStatus.CLOSED.value, "值班长", "归档关闭"))

    for target, operator, remark in steps:
        try:
            issue_service.change_status(
                db,
                issue_id,
                IssueStatusUpdate(to_status=IssueStatus(target), operator=operator, remark=remark),
            )
        except Exception:  # noqa: BLE001  演示数据允许跳过不合法的流转
            break

    # 整改流水时间默认取当前时间，这里按上报时间逐日顺延，
    # 使历史月份的驳回、闭环能被月度考核正确归集
    issue = issue_service.get_issue(db, issue_id)
    base = issue.report_time
    timeline = [base + timedelta(days=index) for index in range(len(issue.records))]
    closed_at = timeline[-1] if issue.status == IssueStatus.CLOSED.value else None
    db.commit()
    db.flush()
    # updated_at 带 onupdate，ORM 赋值会被覆盖，这里用 Core SQL 直改时间
    from sqlalchemy import update as sql_update

    from app.models import RectificationRecord

    for record, when in zip(issue.records, timeline, strict=True):
        db.execute(
            sql_update(RectificationRecord)
            .where(RectificationRecord.id == record.id)
            .values(created_at=when)
        )
    db.execute(
        sql_update(Issue)
        .where(Issue.id == issue_id)
        .values(updated_at=timeline[-1], closed_at=closed_at)
    )
    db.commit()
