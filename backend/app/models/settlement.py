"""合同月度考核与费用结算模型。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import SettlementStatus
from app.core.database import Base


class Settlement(Base):
    """一份合同某一个自然月的考核结果与费用结算。"""

    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("contract_id", "period_year", "period_month", name="uq_settlement_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="结算单号")
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True, comment="所属合同"
    )
    period_year: Mapped[int] = mapped_column(Integer, index=True, comment="考核年份")
    period_month: Mapped[int] = mapped_column(Integer, index=True, comment="考核月份 1-12")

    # 费用：生成时从合同快照月度费用，可手工调整
    monthly_fee: Mapped[float] = mapped_column(Float, default=0.0, comment="月度服务费（元）")

    # 考核数据（自动统计，留痕）
    inspection_count: Mapped[int] = mapped_column(Integer, default=0, comment="当月巡查次数")
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="当月巡查均分")
    issue_new_count: Mapped[int] = mapped_column(Integer, default=0, comment="当月新上报问题数")
    issue_overdue_count: Mapped[int] = mapped_column(Integer, default=0, comment="期末超期未闭环数")
    issue_reject_count: Mapped[int] = mapped_column(Integer, default=0, comment="验收驳回次数")

    # 扣款明细金额
    score_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="巡查质量扣款")
    issue_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="问题整改扣款")
    overdue_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="超期未闭环扣款")
    reject_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="验收驳回扣款")
    other_deduction: Mapped[float] = mapped_column(
        Float, default=0.0, comment="其他扣款（手工登记）"
    )
    other_reason: Mapped[str] = mapped_column(String(300), default="", comment="其他扣款说明")
    bonus: Mapped[float] = mapped_column(Float, default=0.0, comment="奖励金额（手工登记）")
    total_deduction: Mapped[float] = mapped_column(Float, default=0.0, comment="扣款合计")
    payable_amount: Mapped[float] = mapped_column(Float, default=0.0, comment="应付结算金额")

    assess_grade: Mapped[str] = mapped_column(String(20), default="", comment="考核等级")
    assess_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="考核说明")
    details: Mapped[list[dict]] = mapped_column(
        JSON, default=list, comment="扣款依据明细，可回溯到巡查/问题记录"
    )

    assessor: Mapped[str] = mapped_column(String(60), default="", comment="考核人")
    assess_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="考核时间")
    status: Mapped[str] = mapped_column(
        String(20), default=SettlementStatus.ASSESSED.value, index=True, comment="结算状态"
    )
    settle_operator: Mapped[str] = mapped_column(String(60), default="", comment="结算确认人")
    settle_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结算时间")
    settle_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="结算备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    contract: Mapped["Contract"] = relationship(back_populates="settlements")  # noqa: F821

    @property
    def period(self) -> str:
        return f"{self.period_year}-{self.period_month:02d}"
