import base64
import hashlib
from cryptography.fernet import Fernet
from config import Config

def _get_fernet_key(secret_key: str) -> bytes:
    """Derives a valid Fernet 32-byte urlsafe base64-encoded key from secret_key."""
    digest = hashlib.sha256(secret_key.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)

def get_fernet() -> Fernet:
    key = _get_fernet_key(Config.SECRET_KEY)
    return Fernet(key)

def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key using symmetric Fernet encryption."""
    if not plain_key:
        return ''
    f = get_fernet()
    encrypted = f.encrypt(plain_key.encode('utf-8'))
    return encrypted.decode('utf-8')

def decrypt_api_key(cipher_text: str) -> str:
    """Decrypt an encrypted API key."""
    if not cipher_text:
        return ''
    try:
        f = get_fernet()
        decrypted = f.decrypt(cipher_text.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception:
        return cipher_text
