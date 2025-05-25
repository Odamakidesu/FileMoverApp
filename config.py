import json
import os
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()

def get_resource_path(filename: str) -> Path:
    return BASE_DIR / filename

# 各種パス定数
TOKEN_PATH = get_resource_path("token.pickle")
CREDENTIAL_PATH = get_resource_path("credentials.json")
AUTH_COMPLETE_HTML_PATH = get_resource_path("auth_complete.html")
KEYWORDS_FILE = "config_keywords.json"
BASE_CONFIG_FILE = "config_local.json"
BASE_ROOT_DEFAULT = str(Path.home() / "Pictures")

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

DEFAULT_KEYWORDS = [
    "ケモ", "けも", "獣", "ふぁーすと", "kemocon", "OFFF", "もっふ", "モッフ", "モフ", "もふ", "JMoF",
    "着ぐるみ", "きぐるみ", "fur", "666", "kemo", "kemono", "off", "オフ", "おふ", "撮影", "オオカミ",
    "ookami", "いぬ"
]

def save_base_root(path):
    with open(BASE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"BASE_ROOT": path}, f, indent=2, ensure_ascii=False)

def load_base_root():
    if os.path.exists(BASE_CONFIG_FILE):
        try:
            with open(BASE_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("BASE_ROOT", BASE_ROOT_DEFAULT)
        except Exception:
            return BASE_ROOT_DEFAULT
    return BASE_ROOT_DEFAULT

def save_keywords(keywords):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump({"KEYWORDS": keywords}, f, indent=2, ensure_ascii=False)

def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("KEYWORDS", DEFAULT_KEYWORDS)
        except Exception:
            return DEFAULT_KEYWORDS
    return DEFAULT_KEYWORDS

KEYWORDS = load_keywords()
