"""
Security utilities for handling sensitive data.
"""
import os
import base64
import json
import logging
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


def generate_key(password: str, salt: Optional[bytes] = None) -> bytes:
    """
    Generate encryption key from password.

    Args:
        password: Password to derive key from
        salt: Optional salt (generated if not provided)

    Returns:
        Encryption key
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)

    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_data(data: Dict[str, Any], password: str) -> Dict[str, Any]:
    """
    Encrypt sensitive data.

    Args:
        data: Data to encrypt
        password: Encryption password

    Returns:
        Dictionary with encrypted data and salt
    """
    try:
        salt = os.urandom(16)
        key = generate_key(password, salt)

        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(json.dumps(data).encode())

        return {
            "encrypted_data": base64.b64encode(encrypted_data).decode(),
            "salt": base64.b64encode(salt).decode(),
        }
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        # Return unencrypted data with error flag
        return {"data": data, "encryption_error": str(e)}


def decrypt_data(encrypted: Dict[str, Any], password: str) -> Optional[Dict[str, Any]]:
    """
    Decrypt encrypted data.

    Args:
        encrypted: Dictionary with encrypted data and salt
        password: Encryption password

    Returns:
        Decrypted data or None if decryption fails
    """
    try:
        encrypted_data = base64.b64decode(encrypted["encrypted_data"])
        salt = base64.b64decode(encrypted["salt"])

        key = generate_key(password, salt)
        fernet = Fernet(key)

        decrypted_data = fernet.decrypt(encrypted_data).decode()
        return json.loads(decrypted_data)
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        return None


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive information from log data.

    Args:
        data: Data to sanitize

    Returns:
        Sanitized data
    """
    sanitized = data.copy()

    # List of keys that might contain sensitive information
    sensitive_keys = [
        "api_key",
        "key",
        "password",
        "token",
        "secret",
        "credential",
        "OPENAI_API_KEY",
        "DOCUMENTINTELLIGENCE_API_KEY",
    ]

    # Sanitize key-value pairs
    for key in list(sanitized.keys()):
        if any(s_key in key.lower() for s_key in sensitive_keys):
            if isinstance(sanitized[key], str) and sanitized[key]:
                sanitized[key] = "***REDACTED***"

    return sanitized
