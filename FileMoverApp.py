import customtkinter as ctk
import shutil
import os
import zipfile
import pickle
import datetime
import logging
import threading
import tempfile
import re
import subprocess
import string
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from tkinter import filedialog, messagebox, Text
from tkinterdnd2 import DND_FILES, TkinterDnD
from config import (
    load_base_root,
    save_base_root,
    load_keywords,
    save_keywords,
    load_event_format,
    save_event_format,
    TOKEN_PATH,
    SUPPORTED_IMAGE_EXTENSIONS,
    CREDENTIAL_JSON_PATH,
    # AUTH_COMPLETE_HTML_PATH,
    SCOPES,
    DEFAULT_KEYWORDS,
    KEYWORDS_FILE,)
from google.auth.transport.requests import Request
from decrypt_utils import decrypt_credentials

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
logging.basicConfig(filename="error.log", level=logging.ERROR)

# キーワードにヒットしているか判定
def is_hit_keywords_event(title: str, description: str = "") -> bool:
    keywords = load_keywords()
    combined = (title or "") + " " + (description or "")
    combined = combined.lower()
    for keyword in keywords:
        if keyword.lower() in combined:
            return True
    return False

# ヒットするイベントを取得
def get_hit_keywords_events(max_results=250):
    creds = None
    try:
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    config_dict = decrypt_credentials()
                    flow = InstalledAppFlow.from_client_config(config_dict, SCOPES)
                    # html_content = AUTH_COMPLETE_HTML_PATH.read_text(encoding="utf-8")
                    creds = flow.run_local_server(port=0, timeout_seconds=60)
                    
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
                # 生成された復号ファイルを削除
                try:
                    os.remove(CREDENTIAL_JSON_PATH)
                except FileNotFoundError:
                    pass
            except Exception as e:
                logging.error("Google認証エラー", exc_info=True)
                messagebox.showerror("Google認証失敗", f"Google認証中に問題が発生しました。\n操作を中止または権限が不足している可能性があります。\n\n{str(e)}")
                return None

        service = build('calendar', 'v3', credentials=creds)
        now = datetime.datetime.utcnow()
        one_year_ago = now - datetime.timedelta(days=365)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=one_year_ago.isoformat() + 'Z',
            timeMax=now.isoformat() + 'Z',
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        hit_keyword_events = []
        fmt = load_event_format()
        for event in events_result.get('items', []):
            title = event.get('summary', '')
            description = event.get('description', '')
            if is_hit_keywords_event(title, description):
                start = event['start'].get('dateTime', event['start'].get('date'))
                dt = datetime.datetime.fromisoformat(start)

                # --- 日付フォーマット置換ロジック ---
                def format_with_date(fmt: str, dt: datetime.datetime) -> str:
                    match = re.search(r"\{date:([^}]+)\}", fmt)
                    if match:
                        date_fmt = match.group(1)
                        formatted_date = dt.strftime(date_fmt)
                        fmt = fmt.replace(match.group(0), formatted_date)
                    else:
                        # デフォルト形式
                        fmt = fmt.replace("{date}", dt.strftime("%Y%m%d"))
                    return fmt.replace("{event}", title)

                formatted = format_with_date(fmt, dt)
                hit_keyword_events.append(formatted)
        return hit_keyword_events
    except FileNotFoundError as e:
        messagebox.showerror("エラー", "必要なファイル（credentials.json や token.pickle）が見つかりません。")
    except Exception as e:
        logging.error("処理失敗", exc_info=True)
        messagebox.showerror("エラー", f"Google予定取得中にエラーが発生しました: {str(e)}")

# zip解凍用ヘルパー関数
# 画像ファイルの判定
def is_image(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_IMAGE_EXTENSIONS

# zipファイル解凍(Sjis→UTF-8変換)
def extract_and_copy_images(zip_path, target_dir):
    with tempfile.TemporaryDirectory() as temp_dir:
        # 日本語が混ざると文字化けするので一旦7zで展開
        cmd = [
            os.path.join(os.getcwd(), "7za.exe"),
            "x", f"-o{temp_dir}", zip_path, "-y"
        ]
        # 7zでzipファイルを展開
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            messagebox.showerror("展開失敗", f"7zでZIPを展開できませんでした: {str(e)}")
            return

        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                if is_image(full_path):
                    os.makedirs(target_dir, exist_ok=True)
                    dest_path = os.path.join(target_dir, file)

                    counter = 1
                    base, ext = os.path.splitext(dest_path)
                    while os.path.exists(dest_path):
                        dest_path = f"{base}_{counter}{ext}"
                        counter += 1

                    shutil.copy2(full_path, dest_path)

# フォーマットの妥当性を検証
def validate_format(format_str: str) -> bool:
    # 無効なプレースホルダ検出（{未閉じ}, {空}, 変数名に使えない文字など）
    invalid_chars = r'[\/:*?"<>|]'
    if re.findall(invalid_chars, format_str):
        return False

        # プレースホルダ抽出: str.formatの構文に従う
    try:
        formatter = string.Formatter()
        fields = [field_name for _, field_name, _, _ in formatter.parse(format_str) if field_name]
    except ValueError:
        return False  # フォーマット構文エラー（例：未閉じの{}など）

    # 必須の置換子チェック
    if not any(tag in format_str for tag in ("{event}", "{date}")):
        return False

    # 不正なフィールド名（Pythonの識別子 + strftime指定子許可）
    for f in fields:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*(?::[^{}]*)?", f):
            return False

    return True

class FileMoverApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        # 初期表示時
        self.base_root = load_base_root()
        self.title("File Mover App")
        self.geometry("400x650")

        self.file_paths = []
        self.dest_base_dir = None

        self.status_label = ctk.CTkLabel(self, text="Googleアカウントを認証してください", text_color="black")
        self.status_label.pack(pady=10)

        # 保存先選択
        self.select_base_button = ctk.CTkButton(self, text="親フォルダ選択", command=self.select_base_root)
        self.select_base_button.pack(padx=20)

        self.base_dir_display = ctk.CTkLabel(self, text=f"保存先の親フォルダ: {self.base_root}", text_color="gray")
        self.base_dir_display.pack(anchor="w", padx=20, pady=(0, 10))
        
        button_width = 180
        self.edit_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.edit_frame.pack(pady=2)
        # キーワード編集画面
        self.keyword_edit_button = ctk.CTkButton(self.edit_frame, text="キーワード編集", width=button_width, command=self.open_keyword_editor)
        self.keyword_edit_button.pack(side="left", padx=5)

        self.format_edit_button = ctk.CTkButton(self.edit_frame, text="フォーマット編集", width=button_width, command=self.open_format_editor)
        self.format_edit_button.pack(side="left", padx=5)

        # Google Calender認証
        self.event_label = ctk.CTkLabel(self, text="イベント情報")
        self.event_label.pack(anchor="w", padx=20)

        self.google_buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.google_buttons_frame.pack(pady=2)
        self.google_reset = ctk.CTkButton(self.google_buttons_frame, text="Googleアカウント変更", width=button_width, command=self.reset_google_token)
        self.google_reset.pack(side="left", padx=5)
        self.google_fetch = ctk.CTkButton(self.google_buttons_frame, text="予定一覧を取得", width=button_width, command=self.fetch_events_list)
        self.google_fetch.pack(side="left", padx=5)
        self.event_combo = ctk.CTkComboBox(self, values=[], width=400, command=self.set_event_entry)
        self.event_combo.set("")
        self.event_combo.pack(padx=20, pady=5)

        # ========= 手動入力セクション =========
        self.event_name_label = ctk.CTkLabel(self, text="イベント名（手動入力）：")
        self.event_name_label.pack(anchor="w", padx=20)
        self.event_entry = ctk.CTkEntry(self, placeholder_text="例：20250523_sample")
        self.event_entry.pack(padx=20, pady=(0, 10), fill="x")

        # ========= 展開先名 =========
        self.subfolder_label = ctk.CTkLabel(self, text="展開先のフォルダ名")
        self.subfolder_label.pack(anchor="w", padx=20)
        self.subfolder_entry = ctk.CTkEntry(self)
        self.subfolder_entry.pack(padx=20, pady=(0, 10), fill="x")

        # ========= ファイル選択と表示 =========
        self.file_button = ctk.CTkButton(self, text="ファイル選択", command=self.select_files)
        self.file_button.pack(pady=5)

        self.file_display = Text(
            self,
            height=7,
            background="#F1F1F1",
            foreground="#333333",
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#A0A0A0",
            font=("Segoe UI", 11)
        )
        self.file_display.pack(padx=20, pady=5, fill="both")

        self.file_display.drop_target_register(DND_FILES)
        self.file_display.dnd_bind('<<Drop>>', self.on_drop)

        self.file_display.drop_target_register(DND_FILES)
        self.after(200, lambda: self.file_display.dnd_bind('<<Drop>>', self.on_drop))

        # ========= 実行 =========
        self.exec_button = ctk.CTkButton(self, text="実行", command=self.execute)
        self.exec_button.pack(pady=20)

    # === 各種処理 ===
    def select_base_root(self): pass
    def reset_google_token(self): pass
    def fetch_google_events(self): pass
    def select_event(self, value): pass
    def select_files(self): pass
    def execute(self): pass

    # 転送用のファイルを選択する
    def select_files(self):
        paths = filedialog.askopenfilenames(title="ファイルを選択")
        for path in paths:
            if path not in self.file_paths:
                self.file_paths.append(path)

        # 表示更新
        self.file_display.delete("1.0", ctk.END)
        for path in self.file_paths:
            self.file_display.insert(ctk.END, f"{path}\n")

    # ドラッグ＆ドロップでファイルを受け取る
    def on_drop(self, event):
        dropped = self.tk.splitlist(event.data)
        for path in dropped:
            path = path.strip("{").strip("}")
            if path not in self.file_paths:
                self.file_paths.append(path)

        # 表示更新
        self.file_display.delete("1.0", ctk.END)
        for path in self.file_paths:
            self.file_display.insert(ctk.END, f"{path}\n")
    
    # 保存先の親フォルダを選択
    def select_base_root(self):
        selected = filedialog.askdirectory(title="保存先の親フォルダを選択", initialdir=self.base_root)
        if selected:
            self.base_root = selected
            self.base_dir_display.configure(text=f"保存先の親フォルダ: {selected}")
            save_base_root(selected)
    
    # zipファイルを展開
    def extract_zip_smart(self, zip_path, output_base_dir):
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        extract_dir = os.path.join(output_base_dir, zip_name)
        os.makedirs(extract_dir, exist_ok=True)

        # 一時展開先を作成（安全な中間フォルダ）
        temp_dir = os.path.join(extract_dir, "_temp")
        os.makedirs(temp_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # 再帰的にファイルがある階層を探す
        def find_deepest_dir_with_files(start_path):
            for root, dirs, files in os.walk(start_path):
                if files:
                    return root
            return start_path  # ファイルがない場合も戻す

        source_dir = find_deepest_dir_with_files(temp_dir)

        # ファイルとフォルダを extract_dir に移動
        for item in os.listdir(source_dir):
            src_path = os.path.join(source_dir, item)
            dest_path = os.path.join(extract_dir, item)
            if os.path.isdir(src_path):
                shutil.move(src_path, dest_path)
            else:
                shutil.move(src_path, dest_path)

        # 一時展開ディレクトリを削除
        shutil.rmtree(temp_dir)
        print(f"[展開完了] {zip_path} → {extract_dir}")

    # イベント名を自動入力
    def autofill_event_name(self):
        try:
            name = get_hit_keywords_events()
            if name:
                self.event_entry.delete(0, ctk.END)
                self.event_entry.insert(0, name)
                messagebox.showinfo("成功", f"イベント取得: {name}")
            else:
                messagebox.showwarning("なし", "予定が見つかりませんでした。")
        except Exception as e:
            logging.error("処理失敗", exc_info=True)
            messagebox.showerror("エラー", f"カレンダー取得に失敗しました: {str(e)}")

    # Googleカレンダーから予定を取得
    def fetch_events_list(self):
        self.status_label.configure(text="Googleカレンダーから予定を取得中…")
        threading.Thread(target=self._fetch_events_background, daemon=True).start()

    # Googleアカウント認証と予定取得
    def _fetch_events_background(self):
        try:
            events = get_hit_keywords_events()
            if events:
                self.event_combo.configure(values=events)
                self.event_combo.set(events[-1])
                self.set_event_entry(events[-1])
                self.status_label.configure(text=f"✅ Google認証成功、予定を {len(events)} 件取得しました")
            else:
                self.status_label.configure(text="該当予定が見つかりませんでした")
                messagebox.showinfo("なし", "予定が見つかりませんでした。")
        except Exception as e:
            self.status_label.configure(text="取得中にエラー")
            logging.error("Google予定取得失敗", exc_info=True)
            messagebox.showerror("取得エラー", f"Google予定取得時にエラー: {str(e)}")

    # イベント名入力
    def set_event_entry(self, selected_event):
        self.event_entry.delete(0, ctk.END)
        self.event_entry.insert(0, selected_event)

    # Googleアカウントのトークンをリセット
    def reset_google_token(self):
        if os.path.exists(TOKEN_PATH):
            # トークンリセット
            os.remove(TOKEN_PATH)

            # イベント一覧（ドロップダウン）をクリア
            self.event_combo.set("")
            self.event_combo.configure(values=[])

            # イベント名入力欄をクリア
            self.event_entry.delete(0, ctk.END)

            # 展開先フォルダ名入力欄もクリア（任意）
            self.subfolder_entry.delete(0, ctk.END)
            self.status_label.configure(text="Googleアカウントを認証してください")
            messagebox.showinfo("認証情報削除", "Google認証情報を削除しました。\n次回起動時に再認証されます。")
        else:
            messagebox.showinfo("情報なし", "認証トークンが見つかりませんでした。")

    # キーワード編集画面展開
    def open_keyword_editor(self):
        KeywordEditor(self)
        
    # キーワード編集画面展開
    def open_format_editor(self):
        FormatEditor(self)

    def execute(self):
        if not self.file_paths:
            messagebox.showwarning("未選択", "ファイルが選択されていません。")
            return

        # イベント名取得
        event_name = self.event_entry.get().strip()
        if not event_name:
            proceed = messagebox.askyesno("未入力確認", "イベント名が未入力です。\nこのまま続行しますか？")
            if not proceed:
                return

        # 保存先サブフォルダ名取得
        subfolder = self.subfolder_entry.get().strip()

        # 所定の親ディレクトリ
        base_root = self.base_root
        event_dir = os.path.join(base_root, event_name)
        final_dest_dir = os.path.join(event_dir, subfolder)
        os.makedirs(final_dest_dir, exist_ok=True)

        os.makedirs(final_dest_dir, exist_ok=True)  # 必要なら作成

        for path in self.file_paths:
            filename = os.path.basename(path)
            dest_path = os.path.join(final_dest_dir, filename)

            try:
                # zipファイルの場合：コピー → 展開 → 削除
                if filename.lower().endswith(".zip"):
                    extract_and_copy_images(path, final_dest_dir)
                else:
                    # 通常ファイルはコピーだけ
                    shutil.copy2(path, dest_path)
            except PermissionError:
                messagebox.showerror("コピー失敗", f"アクセスが拒否されました：{filename}。\n他のアプリケーションで開いていないか確認してください。")
            except Exception as e:
                logging.error("処理失敗", exc_info=True)
                messagebox.showerror("エラー", f"{filename} の処理中にエラー: {str(e)}")
                return

        messagebox.showinfo("完了", f"すべてのファイルを「{final_dest_dir}」に処理しました。")
        # ✅ 成功時に file_paths をクリアして Text欄もリセット
        self.file_paths.clear()
        self.file_display.delete("1.0", ctk.END)

# キーワード編集画面クラス
class KeywordEditor(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("キーワード編集")
        self.geometry("500x250")
        self.transient(master)  # ← メイン画面を背後に保つ

        ctk.CTkLabel(self, text="キーワードをカンマ区切りで入力してください:").pack(pady=10)

        # キーワード入力用のテキストボックス表示
        self.textbox = ctk.CTkTextbox(self, width=450, height=120)
        self.textbox.pack(pady=5)
        self.textbox.insert("1.0", ", ".join(load_keywords()))

        ctk.CTkButton(self, text="保存", command=self.save).pack(pady=10)

    # キーワードのロードと保存
    def save(self):

        raw = self.textbox.get("1.0", ctk.END)
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        save_keywords(keywords)
        messagebox.showinfo("保存完了", "キーワードを保存しました。")
        self.destroy()

# イベントフォーマット編集画面クラス
class FormatEditor(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("イベントフォーマット編集")
        self.geometry("400x250")
        self.transient(master)
        info_text = (
            "フォーマットで使用可能な変数:\n"
            "{date} または {date:<strftime形式>} - 予定の日付\n"
            "{event} - イベント名\n\n"
            "日付フォーマットの例:\n"
            '例: "{date:%Y-%m-%d}_{event}" → "2025-05-29_撮影会"'
        )
        info_box = ctk.CTkTextbox(self, height=120, width=460, wrap="word")
        info_box.insert("1.0", info_text)
        info_box.configure(state="disabled", border_width=0, fg_color="transparent")
        info_box.pack(pady=(10, 5))
        self.entry = ctk.CTkEntry(self)
        self.entry.pack(pady=5, padx=10, fill="x")

        self.entry.insert(0, load_event_format())

        save_button = ctk.CTkButton(self, text="保存", command=self.save_format)
        save_button.pack(pady=10)

    def save_format(self):
        format_str = self.entry.get().strip()
        if not validate_format(format_str):
            messagebox.showerror("フォーマットエラー", "有効な {event} または {date} が含まれていないか、構文エラーがあります。")
            return
        format_str = self.entry.get().strip()
        if format_str:
            save_event_format(format_str)
            messagebox.showinfo("保存完了", "フォーマットを保存しました。")
        self.destroy()



if __name__ == "__main__":
    app = FileMoverApp()
    app.mainloop()
