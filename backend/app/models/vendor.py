"""保洁服务外包单位模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VendorStatus
from app.core.database import Base


class Vendor(Base):
    """承接保洁服务的外包单位。"""

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, comment="单位名称")
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, comment="单位编号")
    contact_person: Mapped[str] = mapped_column(String(60), default="", comment="联系人")
    contact_phone: Mapped[str] = mapped_column(String(30), default="", comment="联系电话")
    address: Mapped[str] = mapped_column(String(200), default="", comment="单位地址")
    qualification: Mapped[str] = mapped_column(String(200), default="", comment="资质等级/证书")
    status: Mapped[str] = mapped_column(
        String(20), default=VendorStatus.ACTIVE.value, index=True, comment="合作状态"
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    contracts: Mapped[list["Contract"]] = relationship(  # noqa: F821
        back_populates="vendor", cascade="all, delete-orphan"
    )
