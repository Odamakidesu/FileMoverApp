import customtkinter as ctk
import shutil
import os
import zipfile
import pickle
import datetime
import sys
import logging
import threading
import tempfile
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from tkinter import filedialog, messagebox
from config import (
    load_base_root,
    save_base_root,
    load_keywords,
    save_keywords,
    TOKEN_PATH,
    CREDENTIAL_PATH,
    AUTH_COMPLETE_HTML_PATH,
    SCOPES,
    DEFAULT_KEYWORDS,)
from google.auth.transport.requests import Request

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")
logging.basicConfig(filename="error.log", level=logging.ERROR)

def is_kemono_event(title: str, description: str = "") -> bool:
    combined = (title or "") + " " + (description or "")
    combined = combined.lower()
    for keyword in DEFAULT_KEYWORDS:
        if keyword.lower() in combined:
            return True
    return False

def get_resource_path(filename: str) -> str:
    return os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), filename)

def get_kemono_events(max_results=250):
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
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL_PATH, SCOPES)
                    html_content = AUTH_COMPLETE_HTML_PATH.read_text(encoding="utf-8")
                    print(f"[DEBUG] auth_complete.html path: {html_content}")
                    creds = flow.run_local_server(port=0, timeout_seconds=60, success_html=html_content)
                    
                with open(TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
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

        kemono_events = []
        for event in events_result.get('items', []):
            title = event.get('summary', '')
            description = event.get('description', '')
            if is_kemono_event(title, description):
                start = event['start'].get('dateTime', event['start'].get('date'))
                dt = datetime.datetime.fromisoformat(start)
                date_str = dt.strftime('%Y%m%d')
                kemono_events.append(f'{date_str}_{title}')
        return kemono_events
    except FileNotFoundError as e:
        messagebox.showerror("エラー", "必要なファイル（credentials.json や token.pickle）が見つかりません。")
    except Exception as e:
        logging.error("処理失敗", exc_info=True)
        messagebox.showerror("エラー", f"Google予定取得中にエラーが発生しました: {str(e)}")

class FileMoverApp(ctk.CTk):
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
        
        # キーワード編集画面
        self.keyword_edit_button = ctk.CTkButton(self, text="キーワード編集", command=self.open_keyword_editor)
        self.keyword_edit_button.pack(pady=5)

        # Google Calender認証
        self.event_label = ctk.CTkLabel(self, text="イベント情報")
        self.event_label.pack(anchor="w", padx=20)

        self.google_buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.google_buttons_frame.pack(pady=2)
        self.google_reset = ctk.CTkButton(self.google_buttons_frame, text="Googleアカウント切り替え", command=self.reset_google_token)
        self.google_reset.pack(side="left", padx=5)
        self.google_fetch = ctk.CTkButton(self.google_buttons_frame, text="予定一覧を取得", command=self.fetch_events_list)
        self.google_fetch.pack(side="left", padx=5)
        self.event_combo = ctk.CTkComboBox(self, values=[], width=300, command=self.set_event_entry)
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

        self.file_display = ctk.CTkTextbox(self, height=120)
        self.file_display.pack(padx=20, pady=5, fill="both")

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

    def select_files(self):
        self.file_paths = filedialog.askopenfilenames(title="ファイルを選択")
        self.file_display.delete("1.0", ctk.END)
        for path in self.file_paths:
            self.file_display.insert(ctk.END, f"{path}\n")
    
    def select_base_root(self):
        selected = filedialog.askdirectory(title="保存先の親フォルダを選択", initialdir=self.base_root)
        if selected:
            self.base_root = selected
            self.base_dir_display.configure(text=f"保存先の親フォルダ: {selected}")
            save_base_root(selected)
    
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

    def autofill_event_name(self):
        try:
            name = get_kemono_events()
            if name:
                self.event_entry.delete(0, ctk.END)
                self.event_entry.insert(0, name)
                messagebox.showinfo("成功", f"イベント取得: {name}")
            else:
                messagebox.showwarning("なし", "予定が見つかりませんでした。")
        except Exception as e:
            logging.error("処理失敗", exc_info=True)
            messagebox.showerror("エラー", f"カレンダー取得に失敗しました: {str(e)}")

    def fetch_events_list(self):
        self.status_label.configure(text="Googleカレンダーから予定を取得中…")
        threading.Thread(target=self._fetch_events_background, daemon=True).start()

    def _fetch_events_background(self):
        try:
            events = get_kemono_events()
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

    def set_event_entry(self, selected_event):
        self.event_entry.delete(0, ctk.END)
        self.event_entry.insert(0, selected_event)

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

    def on_fetch_events_clicked(self):
        self.status_label.configure(text="Googleカレンダーから予定を取得中…")
        threading.Thread(target=self.fetch_events_thread).start()

    def fetch_events_thread(self):
        try:
            timeout_flag = {"triggered": False}

            def timeout():
                timeout_flag["triggered"] = True
                self.status_label.configure(text="認証タイムアウト・失敗しました")
                messagebox.showerror("エラー", "Google認証がタイムアウトしました。")

            # タイマーを60秒でスタート
            timer = threading.Timer(60, timeout)
            timer.start()

            events = get_kemono_events()  # 認証含む処理

            timer.cancel()  # 成功したらタイマー止める

            if timeout_flag["triggered"]:
                return
            if events is None:
                self.status_label.configure(text="取得失敗")
                return
            self.event_combo.configure(values=events)
            self.status_label.configure(text=f"予定を {len(events)} 件取得")
        except Exception as e:
            self.status_label.configure(text="取得中にエラー")
            messagebox.showerror("取得エラー", f"Google予定取得時にエラー: {str(e)}")

    def open_keyword_editor(self):
        KeywordEditor(self)

    def execute(self):
        if not self.file_paths:
            messagebox.showwarning("未選択", "ファイルが選択されていません。")
            return

        # イベント名取得
        event_name = self.event_entry.get().strip()
        if not event_name:
            messagebox.showwarning("未入力", "イベント名を入力してください。")
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
                    shutil.copy2(path, dest_path)

                    extract_dir = os.path.join(final_dest_dir, os.path.splitext(filename)[0])
                    os.makedirs(extract_dir, exist_ok=True)

                    with zipfile.ZipFile(dest_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)

                    os.remove(dest_path)  # ← ← zip「だけ」削除

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

class KeywordEditor(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("キーワード編集")
        self.geometry("500x250")
        self.transient(master)  # ← メイン画面を背後に保つ

        ctk.CTkLabel(self, text="キーワードをカンマ区切りで入力してください:").pack(pady=10)

        self.textbox = ctk.CTkTextbox(self, width=450, height=120)
        self.textbox.pack(pady=5)
        self.textbox.insert("1.0", ", ".join(load_keywords()))

        ctk.CTkButton(self, text="保存", command=self.save).pack(pady=10)

    def save(self):

        raw = self.textbox.get("1.0", ctk.END)
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        save_keywords(keywords)
        messagebox.showinfo("保存完了", "キーワードを保存しました。")
        self.destroy()

if __name__ == "__main__":
    app = FileMoverApp()
    app.mainloop()
