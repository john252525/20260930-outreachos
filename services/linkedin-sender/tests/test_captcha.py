"""Unit tests for captcha / ban detection."""

from linkedin_sender.session.captcha_detector import BanDetector, CaptchaDetector


def test_captcha_detected() -> None:
    assert CaptchaDetector.detect("Please complete the checkpoint/challenge to continue")
    assert CaptchaDetector.detect("We detected unusual activity")


def test_captcha_not_detected() -> None:
    assert not CaptchaDetector.detect("message sent successfully")


def test_ban_detected() -> None:
    assert BanDetector.detect("Your account has been restricted")
    assert not BanDetector.detect("all good")
