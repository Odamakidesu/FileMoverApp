import json
import os
from pathlib import Path

# デフォルトの保存先
BASE_ROOT_DEFAULT = str(Path.home() / "Pictures" )
BASE_CONFIG_FILE = "config_local.json"
KEYWORDS_FILE = "config_keywords.json"

# Google API スコープ
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

# デフォルトのケモノ関連キーワード
DEFAULT_KEYWORDS = [
    "ケモ", "けも", "獣", "ふぁーすと", "kemocon", "OFFF", "もっふ", "モッフ", "モフ", "もふ", "JMoF" , "着ぐるみ", "きぐるみ", "fur", "666", "kemo", "kemono", "off", "オフ", "おふ", "撮影", "オオカミ", "ookami", "いぬ"
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
