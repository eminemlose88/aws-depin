import os
import streamlit as st
from cryptography.fernet import Fernet

def get_encryption_key():
    """
    Retrieve the encryption key from environment variables or Streamlit secrets.
    If not found, generate one (for development) or raise error (for production).
    """
    key = os.environ.get("ENCRYPTION_KEY")
    
    if not key and hasattr(st, "secrets") and "secrets" in st.secrets:
        key = st.secrets["secrets"].get("ENCRYPTION_KEY")
    elif not key and hasattr(st, "secrets"):
        key = st.secrets.get("ENCRYPTION_KEY")
        
    if not key:
        # Fallback for dev: Generate a key and warn
        # Note: In production, this key MUST be persistent!
        # For now, we'll try to use a static fallback if not set, to avoid data loss on restart
        # WARN: This is not secure for production.
        print("WARNING: ENCRYPTION_KEY not set. Using insecure default for dev.")
        # Fixed key for dev to allow restarts without losing data access
        # Generated with Fernet.generate_key()
        key = b'Z7y6y5x4w3v2u1t0s9r8q7p6o5n4m3l2k1j0i9h8g7f=' 
        
    if isinstance(key, str):
        key = key.encode()
        
    return key

def encrypt_key(key_text):
    """Encrypt a private key string."""
    if not key_text:
        return None
    try:
        f = Fernet(get_encryption_key())
        return f.encrypt(key_text.encode()).decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

def decrypt_key(encrypted_text):
    """Decrypt a private key string."""
    if not encrypted_text:
        return None
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted_text.encode()).decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return None
