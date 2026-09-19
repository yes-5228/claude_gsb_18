"""保洁服务外包相关数据结构：单位、合同、月度结算考核。"""

from datetime import date, datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ---------------- 外包单位 ----------------


class VendorBrief(BaseModel):
    """其他模块引用外包单位时的精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class VendorBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="单位名称")
    license_no: str = Field(default="", max_length=60, description="统一社会信用代码")
    contact_person: str = Field(default="", max_length=60, description="联系人")
    contact_phone: str = Field(default="", max_length=30, description="联系电话")
    address: str = Field(default="", max_length=200, description="单位地址")
    status: str = Field(default="合作中", max_length=20, description="合作状态")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class VendorCreate(VendorBase):
    code: str | None = Field(default=None, max_length=32, description="单位编号，留空自动生成")


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    license_no: str | None = Field(default=None, max_length=60)
    contact_person: str | None = Field(default=None, max_length=60)
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=500)


class VendorOut(VendorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_at: datetime
    updated_at: datetime


class VendorDetail(VendorOut):
    """单位详情，附带合同与结算汇总。"""

    contract_count: int = 0
    active_contract_count: int = 0
    settled_amount_year: float = 0.0
    deduction_total_year: float = 0.0


# ---------------- 合同 ----------------


class ContractBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class ContractBase(BaseModel):
    vendor_id: int = Field(description="承包单位")
    name: str = Field(min_length=1, max_length=120, description="合同名称")
    scope_type: str = Field(default="按区域", description="服务范围：按区域 / 指定公厕")
    scope_districts: list[str] = Field(default_factory=list, description="按区域：区域列表")
    scope_restroom_ids: list[int] = Field(default_factory=list, description="指定公厕：公厕 ID 列表")
    start_date: date = Field(description="合同开始日期")
    end_date: date = Field(description="合同结束日期")
    monthly_fee: float = Field(default=0.0, ge=0, description="月度服务费用（元）")
    payment_terms: str = Field(default="", max_length=200, description="结算与付款约定")
    signed_at: date | None = Field(default=None, description="签订日期")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class ContractCreate(ContractBase):
    code: str | None = Field(default=None, max_length=32, description="合同编号，留空自动生成")


class ContractUpdate(BaseModel):
    vendor_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    scope_type: str | None = None
    scope_districts: list[str] | None = None
    scope_restroom_ids: list[int] | None = None
    start_date: date | None = None
    end_date: date | None = None
    monthly_fee: float | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=20, description="手动变更履行状态")
    signed_at: date | None = None
    remark: str | None = Field(default=None, max_length=500)


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    vendor_id: int
    vendor: VendorBrief | None = None
    name: str
    scope_type: str
    scope_districts: list[str] = Field(default_factory=list)
    scope_restroom_ids: list[int] = Field(default_factory=list)
    scope_text: str = ""
    scope_restroom_count: int = 0
    start_date: date
    end_date: date
    monthly_fee: float
    payment_terms: str
    status: str
    effective_status: str = ""
    signed_at: date | None = None
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class ContractDetail(ContractOut):
    """合同详情，附带服务范围内公厕与月度结算台账。"""

    restrooms: list[dict] = Field(default_factory=list)
    settlement_count: int = 0
    latest_period: str | None = None
    total_payable: float = 0.0
    total_deduction: float = 0.0
    avg_score: float | None = None
    settlements: list[dict] = Field(default_factory=list)


# ---------------- 月度结算 ----------------


class SettlementInspectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inspection_id: int | None = None
    restroom_id: int | None = None
    restroom_name: str
    inspector: str
    inspect_time: datetime
    score: float
    grade: str
    result: str
    deduction: float = 0.0
    deduction_reason: str = ""


class SettlementIssueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int | None = None
    restroom_id: int | None = None
    code: str
    restroom_name: str
    title: str
    category: str
    severity: str
    status: str
    report_time: datetime
    deadline: datetime | None = None
    is_overdue: bool = False
    deduction: float = 0.0
    deduction_reason: str = ""


class DeductionDetail(BaseModel):
    """单项扣款构成，用于结算单逐项追溯。"""

    type: str = Field(description="扣款类型：quality / issue / overdue / manual")
    name: str = Field(description="扣款名称")
    amount: float = Field(description="扣款金额（元）")
    basis: str = Field(default="", description="计算依据说明")
    ref_id: int | None = Field(default=None, description="关联巡查/问题 ID")


class SettlementBase(BaseModel):
    contract_id: int = Field(description="所属合同")
    period_month: str = Field(min_length=7, max_length=7, description="考核月份 YYYY-MM")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class SettlementCreate(SettlementBase):
    pass


class SettlementManualUpdate(BaseModel):
    """其他扣款调整（可负，代表奖励核增）。"""

    manual_deduction: float = Field(description="调整金额，正数扣减、负数核增")
    manual_reason: str = Field(min_length=1, max_length=300, description="调整说明")


class SettlementRemarkUpdate(BaseModel):
    remark: str | None = Field(default=None, max_length=500)


class SettlementStatusUpdate(BaseModel):
    """结算状态流转。"""

    to_status: str = Field(description="目标状态")
    operator: str = Field(min_length=1, max_length=60, description="操作人")
    remark: str | None = Field(default=None, max_length=500, description="处理说明")


class SettlementPreview(BaseModel):
    """考核前的测算结果，不写库。"""

    contract_id: int
    period_month: str
    period_start: date
    period_end: date
    monthly_fee: float
    inspection_count: int = 0
    avg_score: float | None = None
    issue_count: int = 0
    overdue_count: int = 0
    quality_deduction: float = 0.0
    issue_deduction: float = 0.0
    overdue_deduction: float = 0.0
    total_deduction: float = 0.0
    payable_amount: float = 0.0
    details: list[DeductionDetail] = Field(default_factory=list)
    inspections: list[dict] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    contract_id: int
    contract: ContractBrief | None = None
    vendor: VendorBrief | None = None
    period_month: str
    period_start: date
    period_end: date
    monthly_fee: float
    quality_deduction: float
    issue_deduction: float
    overdue_deduction: float
    manual_deduction: float
    manual_reason: str
    total_deduction: float
    payable_amount: float
    inspection_count: int
    avg_score: float | None = None
    issue_count: int
    overdue_count: int
    details: list[DeductionDetail] = Field(
        default_factory=list,
        validation_alias=AliasChoices("deduction_details", "details"),
        serialization_alias="details",
    )
    status: str
    assessed_at: datetime | None = None
    assessed_by: str
    settled_at: datetime | None = None
    settled_by: str
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class SettlementDetail(SettlementOut):
    """结算单详情，附带逐笔巡查与问题快照。"""

    inspection_links: list[SettlementInspectionItem] = Field(default_factory=list)
    issue_links: list[SettlementIssueItem] = Field(default_factory=list)


class SettlementTraceItem(BaseModel):
    """巡查/问题反向追溯到的结算单信息。"""

    settlement_id: int
    code: str
    contract_id: int
    contract_code: str
    contract_name: str
    vendor_name: str
    period_month: str
    status: str
    payable_amount: float
    total_deduction: float
    deduction: float = Field(description="该条巡查/问题在本结算单中的扣款")
    deduction_reason: str = Field(default="", description="扣款原因")
    assessed_at: datetime | None = None
