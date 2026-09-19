"""保洁外包合同相关数据结构。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.restroom import RestroomBrief
from app.schemas.vendor import VendorBrief


class ContractBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="合同名称")
    service_scope: str = Field(default="", max_length=300, description="服务范围说明")
    scope_districts: list[str] = Field(default_factory=list, description="服务区域")
    start_date: date = Field(description="合同开始日期")
    end_date: date = Field(description="合同到期日期")
    signed_date: date | None = Field(default=None, description="签订日期")
    monthly_fee: float = Field(default=0.0, ge=0, description="月度服务费（元）")
    payment_terms: str = Field(default="按月考核结算，次月 15 日前支付", max_length=300)
    restroom_ids: list[int] = Field(default_factory=list, description="纳入服务范围的公厕")
    remark: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("合同到期日期必须晚于开始日期")
        return self


class ContractCreate(ContractBase):
    code: str | None = Field(default=None, max_length=32, description="合同编号，留空自动生成")
    vendor_id: int = Field(description="承包单位")


class ContractUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    service_scope: str | None = Field(default=None, max_length=300)
    scope_districts: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    signed_date: date | None = None
    monthly_fee: float | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=300)
    restroom_ids: list[int] | None = None
    remark: str | None = Field(default=None, max_length=500)


class ContractTerminate(BaseModel):
    reason: str = Field(min_length=1, max_length=500, description="终止原因")


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    vendor_id: int
    vendor: VendorBrief | None = None
    service_scope: str
    scope_districts: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date
    signed_date: date | None = None
    monthly_fee: float
    payment_terms: str
    status: str
    terminate_reason: str | None = None
    remark: str | None = None
    restrooms: list[RestroomBrief] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ContractBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    status: str
    monthly_fee: float
    start_date: date
    end_date: date
    vendor_id: int


class ContractDetail(ContractOut):
    """合同详情：附带服务公厕数量与费用结算汇总。"""

    restroom_count: int = 0
    settlement_count: int = 0
    settled_count: int = 0
    settled_total: float = 0.0
    latest_period: str | None = None
    latest_payable: float | None = None
    latest_status: str | None = None
