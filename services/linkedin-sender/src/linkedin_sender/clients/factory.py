"""Selects the LinkedIn client implementation for an account."""

from linkedin_sender.clients.base import LinkedInClient
from linkedin_sender.clients.dry_run import DryRunClient
from linkedin_sender.clients.linkedin_api_client import LinkedInApiClient
from linkedin_sender.config import Settings
from linkedin_sender.encryptor import SecretEncryptor
from linkedin_sender.models import LinkedInAccount


def build_client(
    account: LinkedInAccount, *, encryptor: SecretEncryptor, settings: Settings
) -> LinkedInClient:
    if settings.dry_run:
        return DryRunClient(account_email=account.email)
    password = encryptor.decrypt(account.password_encrypted)
    cookies = encryptor.decrypt(account.cookies_encrypted) if account.cookies_encrypted else None
    return LinkedInApiClient(
        email=account.email,
        password=password,
        cookies=cookies,
        proxy_url=account.proxy_url,
        user_agent=account.user_agent,
    )
