"""
Encryption utilities for storing sensitive API keys in the database.
Uses Fernet symmetric encryption derived from the app's SECRET_KEY.
"""
import base64
import hashlib
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_fernet():
    """Get a Fernet instance derived from the app's SECRET_KEY."""
    from flask import current_app
    secret = current_app.config['SECRET_KEY']
    # Derive a 32-byte key from SECRET_KEY using SHA256, then base64 encode for Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(plaintext):
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return None
    try:
        f = _get_fernet()
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f'Encryption failed: {e}')
        return None


def decrypt_value(ciphertext):
    """Decrypt a previously encrypted value. Returns plaintext string."""
    if not ciphertext:
        return None
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning('Decryption failed - invalid token (wrong SECRET_KEY or corrupted data)')
        return None
    except Exception as e:
        logger.error(f'Decryption failed: {e}')
        return None
