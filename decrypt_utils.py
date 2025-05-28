import os
import sys
import json
from cryptography.fernet import Fernet
from config import CREDENTIAL_ENC_PATH, CREDENTIAL_JSON_PATH
from pathlib import Path

def get_decryption_key() -> bytes:
    # ⚠ 安全に生成した base64 形式の鍵（32bytes）
    return b'e_PrrwO4eaJA4xkcmN-GZFItLrZSrRxG7Hc3hgrnS9M='

def decrypt_credentials() -> dict:
    if not CREDENTIAL_ENC_PATH.exists():
        raise FileNotFoundError(f"暗号化ファイルが存在しません: {CREDENTIAL_ENC_PATH}")
    
    with open(CREDENTIAL_ENC_PATH, "rb") as f:
        encrypted_data = f.read()

    fernet = Fernet(get_decryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)

    return json.loads(decrypted_data.decode("utf-8"))