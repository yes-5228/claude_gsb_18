"""保洁外包合同模型。"""

from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ContractStatus
from app.core.database import Base

# 合同与公厕的多对多关联：界定合同的服务范围
contract_restroom = Table(
    "contract_restroom",
    Base.metadata,
    Column("contract_id", ForeignKey("contracts.id", ondelete="CASCADE"), primary_key=True),
    Column("restroom_id", ForeignKey("restrooms.id", ondelete="CASCADE"), primary_key=True),
)


class Contract(Base):
    """与外包单位签订的保洁服务合同。"""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="合同编号")
    name: Mapped[str] = mapped_column(String(120), index=True, comment="合同名称")
    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True, comment="承包单位"
    )
    service_scope: Mapped[str] = mapped_column(String(300), default="", comment="服务范围说明")
    scope_districts: Mapped[list[str]] = mapped_column(
        JSON, default=list, comment="服务区域（用于范围兜底与展示）"
    )
    start_date: Mapped[date] = mapped_column(Date, index=True, comment="合同开始日期")
    end_date: Mapped[date] = mapped_column(Date, index=True, comment="合同到期日期")
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="签订日期")
    monthly_fee: Mapped[float] = mapped_column(Float, default=0.0, comment="月度服务费（元）")
    payment_terms: Mapped[str] = mapped_column(
        String(300), default="按月考核结算，次月 15 日前支付", comment="付款约定"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ContractStatus.ACTIVE.value, index=True, comment="合同状态"
    )
    terminate_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="终止原因")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    vendor: Mapped["Vendor"] = relationship(back_populates="contracts")  # noqa: F821
    restrooms: Mapped[list["Restroom"]] = relationship(  # noqa: F821
        secondary=contract_restroom, lazy="selectin"
    )
    settlements: Mapped[list["Settlement"]] = relationship(  # noqa: F821
        back_populates="contract", cascade="all, delete-orphan"
    )
