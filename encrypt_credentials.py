from cryptography.fernet import Fernet
import os

# 一度だけ鍵を生成（後で get_decryption_key に埋め込む）
key = Fernet.generate_key()
print("🔑 Key:", key.decode())  # ← コピーして decrypt_utils に貼る！

fernet = Fernet(key)
with open("credentials.json", "rb") as f:
    original = f.read()

encrypted = fernet.encrypt(original)

# 保存
os.makedirs("encrypted_credentials", exist_ok=True)
with open("dist/runtime/credentials.enc", "wb") as f:
    f.write(encrypted)