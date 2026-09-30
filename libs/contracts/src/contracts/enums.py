"""All enumerations used across contracts."""

from enum import StrEnum


class TenantStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DELETED = "deleted"


class BriefStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    ABANDONED = "abandoned"
    ARCHIVED = "archived"


class PrimaryGoal(StrEnum):
    LEAD_GEN = "lead_gen"
    PARTNERSHIP = "partnership"
    HIRING = "hiring"
    PR = "pr"
    RESEARCH = "research"
    OTHER = "other"


class ToneOfVoice(StrEnum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    NEUTRAL = "neutral"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompanySize(StrEnum):
    SMB = "smb"
    MID = "mid"
    ENTERPRISE = "enterprise"
    ANY = "any"
    UNKNOWN = "unknown"


class CompanyType(StrEnum):
    MANUFACTURER = "manufacturer"
    DISTRIBUTOR = "distributor"
    RETAILER = "retailer"
    SERVICE = "service"
    AGENCY = "agency"
    SAAS = "saas"
    OTHER = "other"


class RoleCategory(StrEnum):
    DECISION_MAKER = "decision_maker"
    INFLUENCER = "influencer"
    GATEKEEPER = "gatekeeper"
    CHAMPION = "champion"
    UNKNOWN = "unknown"


class Seniority(StrEnum):
    C_LEVEL = "c_level"
    VP = "vp"
    DIRECTOR = "director"
    MANAGER = "manager"
    SPECIALIST = "specialist"
    UNKNOWN = "unknown"


class ContactStatus(StrEnum):
    CANDIDATE = "candidate"
    APPROVED = "approved"
    CONTACTED = "contacted"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    ARCHIVED = "archived"


class CompanyStatus(StrEnum):
    CANDIDATE = "candidate"
    CONTACTED = "contacted"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    ARCHIVED = "archived"


class EmailType(StrEnum):
    WORK = "work"
    PERSONAL = "personal"
    UNKNOWN = "unknown"


class PhoneType(StrEnum):
    WORK = "work"
    MOBILE = "mobile"
    UNKNOWN = "unknown"


class ConsentStatus(StrEnum):
    UNKNOWN = "unknown"
    GRANTED = "granted"
    DENIED = "denied"
    NOT_REQUIRED = "not_required"


class LawfulBasis(StrEnum):
    CONSENT = "consent"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class Channel(StrEnum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"


class MessageStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"
    REPLIED = "replied"
    CLOSED = "closed"


class BounceType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class IdentityType(StrEnum):
    USER = "user"
    SERVICE = "service"


class ReplyCategory(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NOT_INTERESTED = "not_interested"
    WRONG_PERSON = "wrong_person"
    AUTO_REPLY = "auto_reply"
    QUESTION = "question"
    UNSUBSCRIBE = "unsubscribe"
    OUT_OF_OFFICE = "out_of_office"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class NextAction(StrEnum):
    REPLY = "reply"
    SCHEDULE_MEETING = "schedule_meeting"
    FORWARD_TO_HUMAN = "forward_to_human"
    ADD_TO_NURTURE = "add_to_nurture"
    UNSUBSCRIBE = "unsubscribe"
    CLOSE = "close"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ExperimentVariableType(StrEnum):
    SUBJECT = "subject"
    BODY = "body"
    OFFER = "offer"
    CTA = "cta"
    TONE = "tone"
    SEND_TIME = "send_time"
    CHANNEL = "channel"
    OTHER = "other"


class PrimaryMetric(StrEnum):
    REPLY_RATE = "reply_rate"
    POSITIVE_REPLY_RATE = "positive_reply_rate"
    MEETINGS_BOOKED = "meetings_booked"
    OPEN_RATE = "open_rate"


class SignalType(StrEnum):
    HIRING = "hiring"
    FUNDING = "funding"
    LAUNCH = "launch"
    EXPANSION = "expansion"
    AWARD = "award"
    NEWS = "news"
    OTHER = "other"
