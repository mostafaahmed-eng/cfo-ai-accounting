from sqlalchemy import Column, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.enums import Language, UserStatus
from app.models.base import BaseModel, TimestampMixin


class User(BaseModel, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    language = Column(
        SAEnum(Language, create_type=False),
        default=Language.en,
        nullable=False,
        server_default="en",
    )
    timezone = Column(String(50), default="UTC", nullable=False, server_default="UTC")
    status = Column(
        SAEnum(UserStatus, create_type=False),
        default=UserStatus.active,
        nullable=False,
        server_default="active",
    )

    memberships = relationship("CompanyMember", back_populates="user", lazy="noload")
