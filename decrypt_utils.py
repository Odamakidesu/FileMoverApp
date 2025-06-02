import json
import base64
import boto3
from cryptography.fernet import Fernet
from auth_secrets import S3_BUCKET_NAME, CREDENTIALS_OBJECT_KEY, KEY_OBJECT_KEY

def fetch_from_s3(object_key: str) -> bytes:
    """S3からファイルを読み込んでバイナリで返す"""
    s3 = boto3.client("s3", region_name="ap-northeast-1")
    response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=object_key)
    return response["Body"].read()

def decrypt_credentials() -> dict:
    """S3から暗号ファイルと鍵を取得して復号した認証情報を返す"""

    # S3から暗号データと鍵を取得
    encrypted_data = fetch_from_s3(CREDENTIALS_OBJECT_KEY)
    print("データ取れた")

    # base64復号 → Fernet形式に変換
    b64_key_raw = fetch_from_s3(KEY_OBJECT_KEY)  # ← bytes型
    b64_key_str = b64_key_raw.decode("utf-8").strip()  # ← 文字列に変換して改行除去
    fernet = Fernet(b64_key_str)

    # 復号とJSON変換
    decrypted_data = fernet.decrypt(encrypted_data)
    return json.loads(decrypted_data.decode("utf-8"))