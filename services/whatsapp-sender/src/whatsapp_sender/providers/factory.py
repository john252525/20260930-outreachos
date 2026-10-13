"""Provider factory."""

from whatsapp_sender.config import Settings
from whatsapp_sender.encryptor import SecretEncryptor
from whatsapp_sender.models import WhatsAppAccount
from whatsapp_sender.providers.base import WhatsAppProvider
from whatsapp_sender.providers.dry_run import DryRunProvider
from whatsapp_sender.providers.gupshup import GupshupProvider


def build_provider(
    account: WhatsAppAccount, *, encryptor: SecretEncryptor, settings: Settings
) -> WhatsAppProvider:
    if settings.dry_run:
        return DryRunProvider()
    api_key = encryptor.decrypt(account.api_key_encrypted)
    if account.provider == "gupshup":
        return GupshupProvider(api_key, app_name=account.provider_account_id)
    return DryRunProvider()
