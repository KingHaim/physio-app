import os
from cryptography.fernet import Fernet
import base64
from flask import current_app

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