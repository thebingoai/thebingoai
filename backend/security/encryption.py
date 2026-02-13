"""Database password encryption utilities using Fernet symmetric encryption."""

from cryptography.fernet import Fernet, InvalidToken
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

_cipher = None


def get_cipher() -> Fernet:
    """Get or create the Fernet cipher instance."""
    global _cipher
    if _cipher is None:
        try:
            _cipher = Fernet(settings.db_encryption_key.encode())
        except Exception as e:
            raise ValueError(
                f"Invalid DB_ENCRYPTION_KEY. Generate a valid key with: "
                f"python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            ) from e
    return _cipher


def encrypt_password(plaintext: str) -> str:
    """
    Encrypt a database password.

    Args:
        plaintext: Plain text password

    Returns:
        Encrypted password (base64 encoded)
    """
    if not plaintext:
        return plaintext

    cipher = get_cipher()
    encrypted = cipher.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_password(encrypted: str) -> str:
    """
    Decrypt a database password.

    Args:
        encrypted: Encrypted password (base64 encoded)

    Returns:
        Plain text password

    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not encrypted:
        return encrypted

    cipher = get_cipher()
    try:
        decrypted = cipher.decrypt(encrypted.encode())
        return decrypted.decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt password - wrong encryption key or corrupted data")
        raise ValueError("Failed to decrypt password - encryption key mismatch") from e
