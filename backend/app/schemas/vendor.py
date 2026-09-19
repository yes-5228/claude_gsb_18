"""保洁外包单位相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VendorBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="单位名称")
    code: str | None = Field(default=None, max_length=32, description="单位编号，留空自动生成")
    contact_person: str = Field(default="", max_length=60, description="联系人")
    contact_phone: str = Field(default="", max_length=30, description="联系电话")
    address: str = Field(default="", max_length=200, description="单位地址")
    qualification: str = Field(default="", max_length=200, description="资质等级/证书")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    contact_person: str | None = Field(default=None, max_length=60)
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)
    qualification: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, description="合作状态")
    remark: str | None = Field(default=None, max_length=500)


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    contact_person: str
    contact_phone: str
    address: str
    qualification: str
    status: str
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class VendorBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    status: str


class VendorDetail(VendorOut):
    """单位详情，附带合同与费用的汇总。"""

    contract_count: int = 0
    active_contract_count: int = 0
    current_month_payable: float = 0.0
