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


class InboxSource(str, enum.Enum):
    web_text = "web_text"
    web_receipt = "web_receipt"
    telegram = "telegram"
    api = "api"
    email = "email"


class ContentType(str, enum.Enum):
    text = "text"
    image = "image"
    document = "document"


class DetectedLanguage(str, enum.Enum):
    en = "en"
    ar = "ar"
    mixed = "mixed"
    unknown = "unknown"


class InboxStatus(str, enum.Enum):
    received = "received"
    processing = "processing"
    extracted = "extracted"
    failed = "failed"
    archived = "archived"


class DocumentType(str, enum.Enum):
    receipt = "receipt"
    invoice = "invoice"
    bank_statement = "bank_statement"
    other = "other"


class UploadStatus(str, enum.Enum):
    pending = "pending"
    stored = "stored"
    failed = "failed"
    quarantined = "quarantined"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    invalid = "invalid"


class TransactionType(str, enum.Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"


class DraftStatus(str, enum.Enum):
    draft = "draft"
    needs_clarification = "needs_clarification"
    ready_for_review = "ready_for_review"
    approved = "approved"
    rejected = "rejected"
    posted = "posted"


class ApprovalEntityType(str, enum.Enum):
    transaction = "transaction"
    journal_entry = "journal_entry"
    budget = "budget"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class JournalSource(str, enum.Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    manual = "manual"
    reversal = "reversal"


class JournalStatus(str, enum.Enum):
    draft = "draft"
    posted = "posted"
    reversed = "reversed"


class TelegramStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class UpdateProcessingStatus(str, enum.Enum):
    received = "received"
    processed = "processed"
    ignored = "ignored"
    failed = "failed"


class BudgetPeriod(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class BudgetStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class NotificationChannel(str, enum.Enum):
    in_app = "in_app"
    telegram = "telegram"
    email = "email"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    read = "read"
    failed = "failed"


class ActorType(str, enum.Enum):
    user = "user"
    telegram = "telegram"
    system = "system"
    ai = "ai"
