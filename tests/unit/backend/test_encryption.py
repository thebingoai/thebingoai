"""Tests for database password encryption utilities (Fernet symmetric encryption)."""

import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_FERNET_KEY = Fernet.generate_key().decode()
ALT_FERNET_KEY = Fernet.generate_key().decode()


def _reset_cipher():
    """Reset the module-level cached cipher so each test starts clean."""
    import backend.security.encryption as mod
    mod._cipher = None


# ---------------------------------------------------------------------------
# get_cipher
# ---------------------------------------------------------------------------

class TestGetCipher:
    """Tests for get_cipher singleton behaviour."""

    def setup_method(self):
        _reset_cipher()

    def teardown_method(self):
        _reset_cipher()

    @patch("backend.security.encryption.settings")
    def test_returns_fernet_instance(self, mock_settings):
        """get_cipher returns a Fernet object when given a valid key."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import get_cipher

        cipher = get_cipher()
        assert isinstance(cipher, Fernet)

    @patch("backend.security.encryption.settings")
    def test_caches_cipher_across_calls(self, mock_settings):
        """Repeated calls return the same Fernet instance (singleton cache)."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import get_cipher

        first = get_cipher()
        second = get_cipher()
        assert first is second

    @patch("backend.security.encryption.settings")
    def test_invalid_key_raises_value_error(self, mock_settings):
        """An invalid encryption key produces a clear ValueError."""
        mock_settings.db_encryption_key = "not-a-valid-fernet-key"
        from backend.security.encryption import get_cipher

        with pytest.raises(ValueError, match="Invalid DB_ENCRYPTION_KEY"):
            get_cipher()


# ---------------------------------------------------------------------------
# encrypt_password / decrypt_password
# ---------------------------------------------------------------------------

class TestEncryptDecrypt:
    """Round-trip and edge-case tests for encrypt/decrypt functions."""

    def setup_method(self):
        _reset_cipher()

    def teardown_method(self):
        _reset_cipher()

    @patch("backend.security.encryption.settings")
    def test_round_trip(self, mock_settings):
        """Encrypting then decrypting returns the original plaintext."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import encrypt_password, decrypt_password

        plaintext = "super-secret-db-password"
        encrypted = encrypt_password(plaintext)
        assert decrypt_password(encrypted) == plaintext

    @patch("backend.security.encryption.settings")
    def test_encrypted_differs_from_plaintext(self, mock_settings):
        """The ciphertext must not equal the plaintext."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import encrypt_password

        plaintext = "super-secret-db-password"
        encrypted = encrypt_password(plaintext)
        assert encrypted != plaintext

    @patch("backend.security.encryption.settings")
    def test_empty_string_passthrough(self, mock_settings):
        """Empty string is returned as-is without encryption."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import encrypt_password, decrypt_password

        assert encrypt_password("") == ""
        assert decrypt_password("") == ""

    @patch("backend.security.encryption.settings")
    def test_none_passthrough(self, mock_settings):
        """None is returned as-is (falsy guard)."""
        mock_settings.db_encryption_key = TEST_FERNET_KEY
        from backend.security.encryption import encrypt_password, decrypt_password

        assert encrypt_password(None) is None
        assert decrypt_password(None) is None

    def test_decrypt_with_wrong_key_raises(self):
        """Decrypting with a different key raises ValueError."""
        _reset_cipher()

        # Encrypt with key A
        with patch("backend.security.encryption.settings") as mock_settings:
            mock_settings.db_encryption_key = TEST_FERNET_KEY
            from backend.security.encryption import encrypt_password
            encrypted = encrypt_password("secret")

        _reset_cipher()

        # Decrypt with key B
        with patch("backend.security.encryption.settings") as mock_settings:
            mock_settings.db_encryption_key = ALT_FERNET_KEY
            from backend.security.encryption import decrypt_password
            with pytest.raises(ValueError, match="encryption key mismatch"):
                decrypt_password(encrypted)
