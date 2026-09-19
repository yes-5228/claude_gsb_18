"""业务枚举与规则常量。"""

from enum import StrEnum


class RestroomStatus(StrEnum):
    NORMAL = "正常开放"
    MAINTENANCE = "维修中"
    CLOSED = "暂停使用"


class RestroomGrade(StrEnum):
    FIRST = "一类"
    SECOND = "二类"
    THIRD = "三类"


class Shift(StrEnum):
    MORNING = "早班"
    MIDDLE = "中班"
    NIGHT = "晚班"


class InspectionResult(StrEnum):
    NORMAL = "正常"
    ABNORMAL = "发现问题"


class IssueCategory(StrEnum):
    CLEANING = "保洁不到位"
    FACILITY = "设施损坏"
    ODOR = "异味扰民"
    CONSUMABLE = "耗材缺失"
    SAFETY = "安全隐患"
    OTHER = "其他"


class IssueSeverity(StrEnum):
    NORMAL = "一般"
    SERIOUS = "严重"
    URGENT = "紧急"


class IssueStatus(StrEnum):
    PENDING = "待整改"
    PROCESSING = "整改中"
    REVIEWING = "待验收"
    DONE = "已完成"
    CLOSED = "已关闭"


# 整改流转规则：当前状态 -> 允许流转到的状态
ISSUE_TRANSITIONS: dict[str, list[str]] = {
    IssueStatus.PENDING: [IssueStatus.PROCESSING, IssueStatus.CLOSED],
    IssueStatus.PROCESSING: [IssueStatus.REVIEWING, IssueStatus.CLOSED],
    IssueStatus.REVIEWING: [IssueStatus.DONE, IssueStatus.PROCESSING],
    IssueStatus.DONE: [IssueStatus.CLOSED],
    IssueStatus.CLOSED: [],
}

# 状态流转对应的动作名称，用于生成整改流水
TRANSITION_ACTIONS: dict[tuple[str, str], str] = {
    (IssueStatus.PENDING, IssueStatus.PROCESSING): "开始整改",
    (IssueStatus.PENDING, IssueStatus.CLOSED): "作废关闭",
    (IssueStatus.PROCESSING, IssueStatus.REVIEWING): "提交验收",
    (IssueStatus.PROCESSING, IssueStatus.CLOSED): "终止关闭",
    (IssueStatus.REVIEWING, IssueStatus.DONE): "验收通过",
    (IssueStatus.REVIEWING, IssueStatus.PROCESSING): "验收驳回",
    (IssueStatus.DONE, IssueStatus.CLOSED): "归档关闭",
}

# 巡查检查项，每项 0-10 分
INSPECTION_CHECK_ITEMS: list[str] = [
    "地面与台阶清洁",
    "便池蹲位清洁",
    "洗手台与镜面",
    "通风除臭",
    "耗材补充",
    "垃圾清运",
    "工具与标识摆放",
    "墙面门窗卫生",
]

INSPECTION_ITEM_MAX_SCORE = 10

GRADE_EXCELLENT = "优秀"
GRADE_GOOD = "良好"
GRADE_PASS = "合格"
GRADE_FAIL = "不合格"

# 仍处于整改闭环中的状态，用于统计未整改问题
OPEN_ISSUE_STATUSES: list[str] = [
    IssueStatus.PENDING,
    IssueStatus.PROCESSING,
    IssueStatus.REVIEWING,
]

# 单检查项低于该分数视为不合格项
INSPECTION_ITEM_PROBLEM_THRESHOLD = 6


class VendorStatus(StrEnum):
    """外包单位合作状态。"""

    ACTIVE = "合作中"
    SUSPENDED = "暂停合作"
    TERMINATED = "终止合作"


class ContractStatus(StrEnum):
    """外包合同履行状态。"""

    ACTIVE = "履行中"
    EXPIRED = "已到期"
    TERMINATED = "已终止"


class ContractScopeType(StrEnum):
    """服务范围划定方式。"""

    DISTRICT = "按区域"
    RESTROOM = "指定公厕"


class SettlementStatus(StrEnum):
    """月度结算考核状态。"""

    PENDING = "待考核"
    ASSESSED = "已考核"
    SETTLED = "已结算"


# 结算状态流转：当前状态 -> 允许流转到的状态
SETTLEMENT_TRANSITIONS: dict[str, list[str]] = {
    SettlementStatus.PENDING: [SettlementStatus.ASSESSED],
    SettlementStatus.ASSESSED: [SettlementStatus.SETTLED, SettlementStatus.PENDING],
    SettlementStatus.SETTLED: [SettlementStatus.ASSESSED],
}

SETTLEMENT_TRANSITION_ACTIONS: dict[tuple[str, str], str] = {
    (SettlementStatus.PENDING, SettlementStatus.ASSESSED): "完成考核",
    (SettlementStatus.ASSESSED, SettlementStatus.SETTLED): "确认结算",
    (SettlementStatus.ASSESSED, SettlementStatus.PENDING): "退回重做",
    (SettlementStatus.SETTLED, SettlementStatus.ASSESSED): "撤销结算",
}

# 月度质量考核扣款规则：当月巡查平均分低于下限按下一档比例扣月度费用
# （下限分, 扣款比例），自高到低匹配
QUALITY_DEDUCTION_TIERS: list[tuple[float, float]] = [
    (90.0, 0.0),
    (80.0, 0.01),
    (70.0, 0.03),
    (0.0, 0.08),
]

# 当月新增问题按严重程度的单条扣款金额（元）
ISSUE_DEDUCTION_AMOUNTS: dict[str, float] = {
    IssueSeverity.NORMAL.value: 50.0,
    IssueSeverity.SERIOUS.value: 150.0,
    IssueSeverity.URGENT.value: 300.0,
}

# 截至考核时仍超期未闭环问题的追加扣款（元/条）
OVERDUE_DEDUCTION_AMOUNT = 200.0
