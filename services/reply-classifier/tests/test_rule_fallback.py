"""Unit tests for the rule-based fallback classifier."""

import pytest
from reply_classifier.classifier.base import NextAction, ReplyCategory
from reply_classifier.classifier.rule_fallback import RuleBasedClassifier


@pytest.fixture
def clf() -> RuleBasedClassifier:
    return RuleBasedClassifier()


def test_auto_reply(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Auto: Re: Ваше предложение",
        body="Это автоматическое сообщение. Ваше письмо получено.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.AUTO_REPLY
    assert result.suggested_action == NextAction.CLOSE


def test_out_of_office(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Ваше предложение",
        body="Я в отпуске до 15.10.2026. Вернусь — отвечу.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.OUT_OF_OFFICE


def test_unsubscribe(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Ваше предложение",
        body="Пожалуйста, удалите меня из рассылки и не пишите больше.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.UNSUBSCRIBE
    assert result.suggested_action == NextAction.UNSUBSCRIBE


def test_wrong_person(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Предложение",
        body="Это не моя зона, обратитесь к Ивану.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.WRONG_PERSON


def test_not_interested(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Предложение",
        body="Спасибо, не интересно.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.NOT_INTERESTED


def test_positive_with_question(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Предложение",
        body="Интересно. Расскажите подробнее. Какая цена?",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.QUESTION
    assert result.sentiment.value == "positive"
    assert len(result.extracted_questions) >= 1


def test_unknown_returns_none(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Предложение",
        body="Хм, посмотрю позже.",
        from_email="x@y.com",
    )
    assert result is None


def test_english_unsubscribe(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Offer",
        body="Please remove me from your list.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.UNSUBSCRIBE


def test_english_positive(clf: RuleBasedClassifier) -> None:
    result = clf.classify(
        subject="Re: Offer",
        body="Thanks, tell me more about pricing.",
        from_email="x@y.com",
    )
    assert result is not None
    assert result.category == ReplyCategory.POSITIVE
