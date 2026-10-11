"""Password encryption and account verification."""

from cryptography.fernet import Fernet

from sender_email.models import SenderAccount
from sender_email.smtp.client import SMTPConfig, verify_smtp


class PasswordEncryptor:
    """Encrypts/decrypts mailbox passwords."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


class AccountManager:
    def __init__(self, encryptor: PasswordEncryptor) -> None:
        self._enc = encryptor

    async def verify_connection(self, account: SenderAccount) -> tuple[bool, str | None]:
        config = SMTPConfig(
            host=account.smtp_host,
            port=account.smtp_port,
            use_ssl=account.smtp_use_ssl,
            username=account.smtp_username,
            password=self._enc.decrypt(account.smtp_password_encrypted),
        )
        if account.smtp_username == "dry-run":
            return True, None
        return await verify_smtp(config)
