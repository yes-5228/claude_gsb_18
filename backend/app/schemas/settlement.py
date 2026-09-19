"""月度考核与费用结算相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contract import ContractBrief


class DeductionEvidence(BaseModel):
    """扣款依据明细：每一条都可回溯到巡查/问题记录。"""

    type: str = Field(description="扣款类型：score/new_issue/overdue/reject/manual/bonus")
    title: str = Field(description="事项说明")
    amount: float = Field(description="扣款（正数）或奖励（负数）金额")
    ref_type: str = Field(default="", description="关联记录类型：inspection/issue/record")
    ref_id: int | None = Field(default=None, description="关联记录 ID")
    ref_code: str = Field(default="", description="关联记录编号")
    ref_time: str | None = Field(default=None, description="关联记录发生时间（ISO 字符串）")
    meta: dict = Field(default_factory=dict, description="补充信息，如问题严重程度/扣罚标准")


class SettlementCreate(BaseModel):
    period_year: int = Field(ge=2000, le=2100, description="考核年份")
    period_month: int = Field(ge=1, le=12, description="考核月份")
    monthly_fee: float | None = Field(default=None, ge=0, description="月费用，默认取合同约定")
    assessor: str = Field(default="", max_length=60, description="考核人")
    assess_remark: str | None = Field(default=None, max_length=500)


class SettlementAdjust(BaseModel):
    """手工调整其他扣款/奖励（自动考核项不可直接改）。"""

    other_deduction: float | None = Field(default=None, ge=0, description="其他扣款金额")
    other_reason: str | None = Field(default=None, max_length=300)
    bonus: float | None = Field(default=None, ge=0, description="奖励金额")
    monthly_fee: float | None = Field(default=None, ge=0, description="调整月费用")
    assess_remark: str | None = Field(default=None, max_length=500)


class SettlementConfirm(BaseModel):
    operator: str = Field(min_length=1, max_length=60, description="结算确认人")
    remark: str | None = Field(default=None, max_length=500, description="结算备注")


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    contract_id: int
    contract: "ContractBrief | None" = None
    period_year: int
    period_month: int
    period: str = ""
    monthly_fee: float
    inspection_count: int
    avg_score: float | None = None
    issue_new_count: int
    issue_overdue_count: int
    issue_reject_count: int
    score_deduction: float
    issue_deduction: float
    overdue_deduction: float
    reject_deduction: float
    other_deduction: float
    other_reason: str
    bonus: float
    total_deduction: float
    payable_amount: float
    assess_grade: str
    assess_remark: str | None = None
    details: list[dict] = Field(default_factory=list)
    assessor: str
    assess_time: datetime | None = None
    status: str
    settle_operator: str = ""
    settle_time: datetime | None = None
    settle_remark: str | None = None
    created_at: datetime
    updated_at: datetime


class SettlementDetail(SettlementOut):
    """结算详情：在列表字段基础上补充关联合同/单位信息。"""

    vendor_name: str = ""
    contract_name: str = ""
    contract_code: str = ""
    # 用于页面直接渲染的追溯依据（解析自 details）
    evidences: list[DeductionEvidence] = Field(default_factory=list)


class AssessmentPreview(BaseModel):
    """生成结算单前的考核测算结果。"""

    contract_id: int
    period_year: int
    period_month: int
    monthly_fee: float
    inspection_count: int = 0
    avg_score: float | None = None
    issue_new_count: int = 0
    issue_overdue_count: int = 0
    issue_reject_count: int = 0
    score_deduction: float = 0.0
    issue_deduction: float = 0.0
    overdue_deduction: float = 0.0
    reject_deduction: float = 0.0
    auto_deduction: float = 0.0
    total_deduction: float = 0.0
    payable_amount: float = 0.0
    assess_grade: str = ""
    evidences: list[DeductionEvidence] = Field(default_factory=list)


class SettlementTraceItem(BaseModel):
    """问题/巡查记录反查到的结算单条目。"""

    settlement_id: int
    settlement_code: str
    contract_id: int
    contract_name: str
    vendor_name: str
    period: str
    status: str
    payable_amount: float
    evidences: list[DeductionEvidence] = Field(default_factory=list)
