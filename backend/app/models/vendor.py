"""保洁服务外包：外包单位、合同、月度结算考核模型。"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ContractScopeType,
    ContractStatus,
    SettlementStatus,
    VendorStatus,
)
from app.core.database import Base


class Vendor(Base):
    """保洁服务外包单位（承包公司）。"""

    __tablename__ = "cleaning_vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="单位编号")
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, comment="单位名称")
    license_no: Mapped[str] = mapped_column(String(60), default="", comment="统一社会信用代码")
    contact_person: Mapped[str] = mapped_column(String(60), default="", comment="联系人")
    contact_phone: Mapped[str] = mapped_column(String(30), default="", comment="联系电话")
    address: Mapped[str] = mapped_column(String(200), default="", comment="单位地址")
    status: Mapped[str] = mapped_column(
        String(20), default=VendorStatus.ACTIVE.value, index=True, comment="合作状态"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    contracts: Mapped[list["CleaningContract"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan"
    )


class CleaningContract(Base):
    """保洁服务外包合同：约定服务范围、合同期限与月度费用。"""

    __tablename__ = "cleaning_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="合同编号")
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_vendors.id", ondelete="RESTRICT"), index=True, comment="承包单位"
    )
    name: Mapped[str] = mapped_column(String(120), comment="合同名称")
    scope_type: Mapped[str] = mapped_column(
        String(20), default=ContractScopeType.DISTRICT.value, comment="服务范围划定方式"
    )
    scope_districts: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="按区域承包的区域列表"
    )
    scope_restroom_ids: Mapped[list[int]] = mapped_column(
        JSON, default=list, comment="指定公厕承包的公厕 ID 列表"
    )
    start_date: Mapped[date] = mapped_column(Date, index=True, comment="合同开始日期")
    end_date: Mapped[date] = mapped_column(Date, index=True, comment="合同结束日期")
    monthly_fee: Mapped[float] = mapped_column(Float, default=0.0, comment="月度服务费用（元）")
    payment_terms: Mapped[str] = mapped_column(String(200), default="", comment="结算与付款约定")
    status: Mapped[str] = mapped_column(
        String(20), default=ContractStatus.ACTIVE.value, index=True, comment="履行状态"
    )
    signed_at: Mapped[date | None] = mapped_column(Date, nullable=True, comment="签订日期")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    vendor: Mapped["Vendor"] = relationship(back_populates="contracts")
    settlements: Mapped[list["MonthlySettlement"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class MonthlySettlement(Base):
    """月度费用结算与考核扣款台账，一个合同一个月至多一条。"""

    __tablename__ = "cleaning_settlements"
    __table_args__ = (
        UniqueConstraint("contract_id", "period_month", name="uq_contract_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="结算单编号")
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_contracts.id", ondelete="CASCADE"), index=True, comment="所属合同"
    )
    period_month: Mapped[str] = mapped_column(
        String(7), index=True, comment="考核月份，格式 YYYY-MM"
    )
    period_start: Mapped[date] = mapped_column(Date, comment="考核周期开始日")
    period_end: Mapped[date] = mapped_column(Date, comment="考核周期结束日")

    # 费用与扣款（元），考核后由系统按快照计算
    monthly_fee: Mapped[float] = mapped_column(Float, default=0.0, comment="月度费用（合同快照）")
    quality_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="质量考核扣款")
    issue_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="问题整改扣款")
    overdue_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="超期未闭环扣款")
    manual_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="其他调整金额")
    manual_reason: Mapped[str] = mapped_column(String(300), default="", comment="其他调整说明")
    total_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="扣款合计")
    payable_amount: Mapped[float] = mapped_column(Float, default=0.0, comment="本月应结算金额")

    # 考核指标快照：考核后固化，作为扣款可追溯依据
    inspection_count: Mapped[int] = mapped_column(Integer, default=0, comment="当期巡查次数")
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="当期平均得分")
    issue_count: Mapped[int] = mapped_column(Integer, default=0, comment="当期新增问题数")
    overdue_count: Mapped[int] = mapped_column(Integer, default=0, comment="超期未闭环问题数")
    deduction_details: Mapped[list[dict]] = mapped_column(
        JSON, default=list, comment="扣款明细（各档次/各问题逐项快照）"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=SettlementStatus.PENDING.value,
        index=True,
        comment="结算考核状态",
    )
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="考核时间")
    assessed_by: Mapped[str] = mapped_column(String(60), default="", comment="考核人")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结算时间")
    settled_by: Mapped[str] = mapped_column(String(60), default="", comment="结算确认人")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    contract: Mapped["CleaningContract"] = relationship(back_populates="settlements")
    inspection_links: Mapped[list["SettlementInspection"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan"
    )
    issue_links: Mapped[list["SettlementIssue"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan"
    )


class SettlementInspection(Base):
    """结算单与当期巡查记录的关联快照：结算金额可追溯到每一次巡查。"""

    __tablename__ = "cleaning_settlement_inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_settlements.id", ondelete="CASCADE"), index=True
    )
    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    restroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("restrooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    restroom_name: Mapped[str] = mapped_column(String(120), default="", comment="公厕名称快照")
    inspector: Mapped[str] = mapped_column(String(60), default="", comment="巡查人快照")
    inspect_time: Mapped[datetime] = mapped_column(DateTime, comment="巡查时间快照")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="巡查得分快照")
    grade: Mapped[str] = mapped_column(String(20), default="", comment="评分等级快照")
    result: Mapped[str] = mapped_column(String(20), default="", comment="巡查结论快照")
    deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="该记录对应扣款")
    deduction_reason: Mapped[str] = mapped_column(String(200), default="", comment="扣款原因")

    settlement: Mapped["MonthlySettlement"] = relationship(back_populates="inspection_links")


class SettlementIssue(Base):
    """结算单与当期问题记录的关联快照：问题整改情况可追溯到每一笔扣款。"""

    __tablename__ = "cleaning_settlement_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_settlements.id", ondelete="CASCADE"), index=True
    )
    issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    restroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("restrooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(32), default="", comment="问题编号快照")
    restroom_name: Mapped[str] = mapped_column(String(120), default="", comment="公厕名称快照")
    title: Mapped[str] = mapped_column(String(120), default="", comment="问题标题快照")
    category: Mapped[str] = mapped_column(String(30), default="", comment="问题分类快照")
    severity: Mapped[str] = mapped_column(String(20), default="", comment="严重程度快照")
    status: Mapped[str] = mapped_column(String(20), default="", comment="考核时整改状态快照")
    report_time: Mapped[datetime] = mapped_column(DateTime, comment="上报时间快照")
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="整改期限快照")
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False, comment="考核时是否超期未闭环")
    deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="该问题对应扣款")
    deduction_reason: Mapped[str] = mapped_column(String(200), default="", comment="扣款原因")

    settlement: Mapped["MonthlySettlement"] = relationship(back_populates="issue_links")
