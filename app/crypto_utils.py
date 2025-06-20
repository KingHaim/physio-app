import os
from cryptography.fernet import Fernet
import base64
from flask import current_app
import re

def get_fernet_cipher():
    """
    Get a Fernet cipher instance using the environment key.
    
    Returns:
        Fernet: The cipher instance, or None if key is not available
    """
    try:
        fernet_key = os.environ.get('FERNET_SECRET_KEY')
        if not fernet_key:
            current_app.logger.error("FERNET_SECRET_KEY not found in environment variables")
            return None
            
        return Fernet(fernet_key.encode())
    except Exception as e:
        current_app.logger.error(f"Error creating Fernet cipher: {str(e)}")
        return None

def encrypt_text(text: str) -> str:
    """
    Encrypt sensitive text data using Fernet encryption.
    
    Args:
        text (str): The plain text to encrypt
        
    Returns:
        str: The encrypted text as a base64 string, or None if encryption fails
    """
    try:
        if not text:
            return None
            
        cipher = get_fernet_cipher()
        if not cipher:
            return None
            
        # Encrypt the text
        encrypted_data = cipher.encrypt(text.encode())
        
        # Return as base64 string
        return base64.b64encode(encrypted_data).decode()
        
    except Exception as e:
        current_app.logger.error(f"Error encrypting text: {str(e)}")
        return None

def decrypt_text(encrypted_text: str) -> str:
    """
    Decrypt sensitive text data using Fernet decryption.
    
    Args:
        encrypted_text (str): The encrypted text as a base64 string
        
    Returns:
        str: The decrypted text, or None if decryption fails
    """
    try:
        if not encrypted_text:
            return None
            
        cipher = get_fernet_cipher()
        if not cipher:
            return None
            
        # Check if the text looks like it might be encrypted
        # Fernet tokens are always base64-encoded and have a specific format
        if not isinstance(encrypted_text, str):
            return None
            
        # Quick check: if it's too short, it's definitely not encrypted
        if len(encrypted_text) < 20:  # Fernet tokens are much longer
            return encrypted_text  # Return as-is if it's likely plain text
            
        # Quick check: if it doesn't look like base64, it's probably plain text
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(encrypted_text):
            return encrypted_text  # Return as-is if it doesn't look like base64
            
        # Try to decode from base64
        try:
            encrypted_bytes = base64.b64decode(encrypted_text.encode())
        except (base64.binascii.Error, ValueError):
            # If base64 decoding fails, it's probably plain text
            return encrypted_text  # Return as-is if it's likely plain text
            
        # Try to decrypt
        try:
            decrypted_data = cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception:
            # If decryption fails, it might be plain text that was stored
            return encrypted_text  # Return as-is if it's likely plain text
        
    except Exception as e:
        current_app.logger.error(f"Error in decrypt_text: {str(e)}")
        # Return the original text if decryption fails completely
        return encrypted_text if encrypted_text else None

def encrypt_token(token):
    """
    Encrypt a Calendly API token using Fernet encryption.
    
    Args:
        token (str): The plain text token to encrypt
        
    Returns:
        str: The encrypted token as a base64 string, or None if encryption fails
    """
    try:
        if not token:
            return None
            
        # Get the Fernet key from environment
        fernet_key = os.environ.get('FERNET_SECRET_KEY')
        if not fernet_key:
            current_app.logger.error("FERNET_SECRET_KEY not found in environment variables")
            return None
            
        # Create Fernet cipher
        cipher = Fernet(fernet_key.encode())
        
        # Encrypt the token
        encrypted_token = cipher.encrypt(token.encode())
        
        # Return as base64 string
        return base64.b64encode(encrypted_token).decode()
        
    except Exception as e:
        current_app.logger.error(f"Error encrypting token: {str(e)}")
        return None

def decrypt_token(encrypted_token):
    """
    Decrypt a Calendly API token using Fernet decryption.
    
    Args:
        encrypted_token (str): The encrypted token as a base64 string
        
    Returns:
        str: The decrypted token, or None if decryption fails
    """
    try:
        if not encrypted_token:
            return None
            
        # Get the Fernet key from environment
        fernet_key = os.environ.get('FERNET_SECRET_KEY')
        if not fernet_key:
            current_app.logger.error("FERNET_SECRET_KEY not found in environment variables")
            return None
            
        # Create Fernet cipher
        cipher = Fernet(fernet_key.encode())
        
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_token.encode())
        
        # Decrypt the token
        decrypted_token = cipher.decrypt(encrypted_bytes)
        
        # Return as string
        return decrypted_token.decode()
        
    except Exception as e:
        current_app.logger.error(f"Error decrypting token: {str(e)}")
        return None 