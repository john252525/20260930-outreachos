"""Shared classification primitives."""

from dataclasses import dataclass, field
from enum import StrEnum


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


@dataclass
class ClassificationResult:
    category: ReplyCategory
    confidence: float
    sentiment: Sentiment = Sentiment.NEUTRAL
    intent: str | None = None
    extracted_questions: list[str] = field(default_factory=list)
    extracted_actions: list[str] = field(default_factory=list)
    suggested_action: NextAction = NextAction.FORWARD_TO_HUMAN
    suggested_action_reason: str = ""
    classified_by: str = "rule"
    language: str | None = None
