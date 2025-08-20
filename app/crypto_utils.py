import os
from cryptography.fernet import Fernet
import base64
from flask import current_app
import re

def get_fernet_cipher():
    """
    Get a Fernet cipher instance using the environment key. Returns None if encryption disabled.
    """
    try:
        # Allow global disabling via config/env
        if hasattr(current_app, 'config') and current_app.config.get('DISABLE_ENCRYPTION', False):
            return None
        fernet_key = os.environ.get('FERNET_SECRET_KEY')
        if not fernet_key:
            # If encryption is enabled but key missing, disable gracefully
            current_app.logger.warning("Encryption disabled: FERNET_SECRET_KEY not set")
            return None
        return Fernet(fernet_key.encode())
    except Exception as e:
        current_app.logger.error(f"Error creating Fernet cipher: {str(e)}")
        return None

def encrypt_text(text: str) -> str:
    """
    Encrypt sensitive text data using Fernet encryption. If encryption is disabled or unavailable, return the input.
    """
    try:
        if text is None:
            return None
        cipher = get_fernet_cipher()
        if not cipher:
            return text
        encrypted_data = cipher.encrypt(text.encode())
        return base64.b64encode(encrypted_data).decode()
    except Exception as e:
        current_app.logger.warning(f"Encryption unavailable, returning plaintext: {str(e)}")
        return text

def decrypt_text(encrypted_text: str) -> str:
    """
    Decrypt sensitive text data. If encryption is disabled or token not valid, return the input unchanged.
    """
    try:
        if encrypted_text is None:
            return None
        cipher = get_fernet_cipher()
        if not cipher:
            return encrypted_text
        if not isinstance(encrypted_text, str):
            return encrypted_text
        if len(encrypted_text) < 20:
            return encrypted_text
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(encrypted_text):
            return encrypted_text
        try:
            encrypted_bytes = base64.b64decode(encrypted_text.encode())
        except (base64.binascii.Error, ValueError):
            return encrypted_text
        try:
            decrypted_data = cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception:
            return encrypted_text
    except Exception as e:
        current_app.logger.warning(f"Decrypt unavailable, returning plaintext: {str(e)}")
        return encrypted_text

def encrypt_token(token):
    """
    Encrypt a token. If encryption is disabled or key is missing, return input.
    """
    try:
        if token is None:
            return None
        cipher = get_fernet_cipher()
        if not cipher:
            return token
        encrypted_token = cipher.encrypt(token.encode())
        return base64.b64encode(encrypted_token).decode()
    except Exception as e:
        current_app.logger.warning(f"Token encryption unavailable, returning plaintext: {str(e)}")
        return token

def decrypt_token(encrypted_token):
    """
    Decrypt a token. If encryption is disabled or token invalid, return input unchanged.
    """
    try:
        if encrypted_token is None:
            return None
        cipher = get_fernet_cipher()
        if not cipher:
            return encrypted_token
        if not isinstance(encrypted_token, str):
            return encrypted_token
        try:
            encrypted_bytes = base64.b64decode(encrypted_token.encode())
        except (base64.binascii.Error, ValueError):
            return encrypted_token
        try:
            decrypted_token = cipher.decrypt(encrypted_bytes)
            return decrypted_token.decode()
        except Exception:
            return encrypted_token
    except Exception as e:
        current_app.logger.warning(f"Token decrypt unavailable, returning plaintext: {str(e)}")
        return encrypted_token 