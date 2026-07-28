from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class Vendor(BaseModel, TimestampMixin):
    __tablename__ = "vendors"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    tax_number = Column(String(100), nullable=True)
    country_code = Column(String(2), nullable=True)
    default_expense_account = Column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    default_currency = Column(String(3), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company", back_populates="vendors")
    aliases = relationship("VendorAlias", back_populates="vendor")


class VendorAlias(BaseModel, TimestampMixin):
    __tablename__ = "vendor_aliases"

    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    alias = Column(String(255), nullable=False)
    normalized_alias = Column(String(255), nullable=False)

    vendor = relationship("Vendor", back_populates="aliases")

    __table_args__ = (UniqueConstraint("vendor_id", "normalized_alias"),)
