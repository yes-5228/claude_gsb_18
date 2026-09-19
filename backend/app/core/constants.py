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
    ACTIVE = "合作中"
    SUSPENDED = "已停用"


class ContractStatus(StrEnum):
    ACTIVE = "履约中"
    TERMINATED = "已终止"
    EXPIRED = "已到期"


class SettlementStatus(StrEnum):
    ASSESSED = "已考核"
    SETTLED = "已结算"


# 巡查质量考核：月均分下限（含）到扣款比例，从上到下匹配
# 如 [85, 90) 扣月费用 1%；无巡查记录当月不扣巡查项
SCORE_DEDUCTION_RULES: list[tuple[float, float, str]] = [
    (90, 0.0, "月均分不低于 90 分，不扣款"),
    (85, 0.01, "月均分 85-90 分，按月费用 1% 扣款"),
    (80, 0.02, "月均分 80-85 分，按月费用 2% 扣款"),
    (70, 0.05, "月均分 70-80 分，按月费用 5% 扣款"),
    (0, 0.10, "月均分低于 70 分，按月费用 10% 扣款"),
]

# 当月新上报问题按严重程度扣款（元/条）
ISSUE_NEW_DEDUCTION: dict[str, int] = {
    IssueSeverity.URGENT.value: 200,
    IssueSeverity.SERIOUS.value: 100,
    IssueSeverity.NORMAL.value: 50,
}

# 考核期末仍超期未闭环的问题扣款（元/条）
ISSUE_OVERDUE_DEDUCTION = 300

# 验收驳回扣款（元/次）
ISSUE_REJECT_DEDUCTION = 150

# 自动考核扣款（巡查 + 问题整改）合计不超过月费用的该比例
MAX_AUTO_DEDUCTION_RATE = 0.30

# 考核等级
ASSESS_EXCELLENT = "优秀"
ASSESS_QUALIFIED = "合格"
ASSESS_BASIC = "基本合格"
ASSESS_FAIL = "不合格"
