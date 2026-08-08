import enum


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ACCOUNTANT = "ACCOUNTANT"
    APPROVER = "APPROVER"
    VIEWER = "VIEWER"


class MemberStatus(str, enum.Enum):
    active = "active"
    invited = "invited"
    disabled = "disabled"


class UserStatus(str, enum.Enum):
    active = "active"
    invited = "invited"
    disabled = "disabled"


class Language(str, enum.Enum):
    en = "en"
    ar = "ar"


class AccountType(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    revenue = "revenue"
    expense = "expense"
