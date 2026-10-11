"""Deterministic rule-based classifier.

Handles obvious cases without spending LLM tokens: auto-reply,
out-of-office, unsubscribe, explicit rejection.
"""

import re
from typing import ClassVar

from reply_classifier.classifier.base import (
    ClassificationResult,
    NextAction,
    ReplyCategory,
    Sentiment,
)


class RuleBasedClassifier:
    """Deterministic classifier for obvious cases."""

    OOO_PATTERNS: ClassVar[list[str]] = [
        r"out\s+of\s+office",
        r"автоответ",
        r"автоматический ответ",
        r"в\s+отпуске",
        r"не\s+в\s+офисе",
        r"вернусь\s+\d{1,2}",
        r"буду\s+в\s+отпуске",
        r"в\s+командировке",
    ]

    AUTO_REPLY_PATTERNS: ClassVar[list[str]] = [
        r"это\s+автоматическое\s+сообщение",
        r"this\s+is\s+an\s+automated\s+message",
        r"не\s+отвечайте\s+на\s+это\s+письмо",
        r"do\s+not\s+reply",
        r"письмо\s+получено",
    ]

    UNSUB_PATTERNS: ClassVar[list[str]] = [
        r"отпишите?\s+меня",
        r"удалите\s+меня\s+из\s+рассылки",
        r"unsubscribe",
        r"снимите\s+с\s+рассылки",
        r"не\s+пишите\s+мне\s+больше",
        r"stop\s+emailing",
        r"remove\s+me",
    ]

    WRONG_PERSON_PATTERNS: ClassVar[list[str]] = [
        r"я\s+не\s+отвечаю\s+за",
        r"это\s+не\s+моя\s+зона",
        r"обратитесь\s+к",
        r"not\s+my\s+area",
        r"wrong\s+person",
        r"я\s+не\s+в\s+курсе",
        r"этим\s+занимается",
    ]

    NEGATIVE_PATTERNS: ClassVar[list[str]] = [
        r"не\s+интересно",
        r"не\s+нужно",
        r"спасибо,?\s+не\s+надо",
        r"not\s+interested",
        r"no\s+thanks",
        r"откажитесь\s+от\s+идеи",
        r"мы\s+не\s+заинтересованы",
    ]

    POSITIVE_PATTERNS: ClassVar[list[str]] = [
        r"интересно",
        r"расскажите\s+подробнее",
        r"давайте\s+обсудим",
        r"готовы\s+обсудить",
        r"пришлите\s+предложение",
        r"хочу\s+узнать",
        r"let'?s\s+talk",
        r"tell\s+me\s+more",
        r"interested",
        r"send\s+more\s+info",
    ]

    def classify(
        self,
        *,
        subject: str | None,
        body: str,
        from_email: str,
    ) -> ClassificationResult | None:
        """Return a result when confident, otherwise ``None`` (defer to LLM)."""
        text = f"{subject or ''}\n{body}".lower()

        if self._matches_any(text, self.AUTO_REPLY_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.AUTO_REPLY,
                confidence=0.95,
                sentiment=Sentiment.NEUTRAL,
                intent="automated response",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Автоматический ответ — не требует реакции",
            )

        if self._matches_any(text, self.OOO_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.OUT_OF_OFFICE,
                confidence=0.9,
                sentiment=Sentiment.NEUTRAL,
                intent="out of office",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Человек в отпуске/командировке — не требует реакции",
            )

        if self._matches_any(text, self.UNSUB_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.UNSUBSCRIBE,
                confidence=0.95,
                sentiment=Sentiment.NEGATIVE,
                intent="unsubscribe request",
                suggested_action=NextAction.UNSUBSCRIBE,
                suggested_action_reason="Запрос на отписку — обязательно добавить в stop-list",
            )

        if self._matches_any(text, self.WRONG_PERSON_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.WRONG_PERSON,
                confidence=0.85,
                sentiment=Sentiment.NEUTRAL,
                intent="wrong person",
                suggested_action=NextAction.FORWARD_TO_HUMAN,
                suggested_action_reason="Не тот адресат — возможно, стоит найти правильный контакт",
            )

        if self._matches_any(text, self.NEGATIVE_PATTERNS):
            return ClassificationResult(
                category=ReplyCategory.NOT_INTERESTED,
                confidence=0.85,
                sentiment=Sentiment.NEGATIVE,
                intent="not interested",
                suggested_action=NextAction.CLOSE,
                suggested_action_reason="Явный отказ — закрыть контакт, не тратить время",
            )

        if self._matches_any(text, self.POSITIVE_PATTERNS):
            questions = self._extract_questions(body)
            return ClassificationResult(
                category=ReplyCategory.QUESTION if questions else ReplyCategory.POSITIVE,
                confidence=0.7,
                sentiment=Sentiment.POSITIVE,
                intent="interest expressed",
                extracted_questions=questions,
                suggested_action=NextAction.REPLY,
                suggested_action_reason="Проявлен интерес — нужно ответить",
            )

        return None

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _extract_questions(body: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", body)
        return [s.strip() for s in sentences if s.strip().endswith("?")][:5]
