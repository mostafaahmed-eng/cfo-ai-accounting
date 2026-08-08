from sqlalchemy import Column, SmallInteger, String
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
    # Bumped on password change to invalidate every previously issued
    # access and refresh token (ver claim is compared against this).
    token_version = Column(SmallInteger, nullable=False, default=0, server_default="0")

    memberships = relationship("CompanyMember", back_populates="user", lazy="noload")
