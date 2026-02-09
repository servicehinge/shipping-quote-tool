"""
Google Sheets 連線模組
共用的 gspread client 和工作表存取
"""

import os
import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Module-level cache for standalone (non-Streamlit) use
_cached_client = None


def _get_credentials() -> Credentials:
    """從 Streamlit secrets 或本機 JSON 檔取得 Google 憑證"""
    # 優先使用 Streamlit secrets（部署到 Cloud 時）
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            try:
                if "gcp_service_account" in st.secrets:
                    info = dict(st.secrets["gcp_service_account"])
                    return Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception:
                pass
    except ImportError:
        pass

    # 本機開發：使用 JSON key 檔案
    key_path = config.GOOGLE_SHEETS_KEY_FILE
    if key_path and os.path.exists(key_path):
        return Credentials.from_service_account_file(key_path, scopes=SCOPES)

    raise FileNotFoundError(
        "找不到 Google Service Account 憑證。"
        "請設定 GOOGLE_SHEETS_KEY_FILE 環境變數或 Streamlit secrets。"
    )


def get_gspread_client() -> gspread.Client:
    """取得 gspread client"""
    global _cached_client

    # 嘗試使用 Streamlit cache
    try:
        import streamlit as st

        @st.cache_resource(ttl=600)
        def _st_cached_client():
            creds = _get_credentials()
            return gspread.authorize(creds)

        return _st_cached_client()
    except Exception:
        pass

    # Fallback: module-level cache for standalone scripts
    if _cached_client is None:
        creds = _get_credentials()
        _cached_client = gspread.authorize(creds)
    return _cached_client


def get_spreadsheet() -> gspread.Spreadsheet:
    """取得主要的 Google Spreadsheet"""
    client = get_gspread_client()
    return client.open_by_key(config.GOOGLE_SHEETS_SPREADSHEET_ID)


def get_or_create_worksheet(name: str, rows: int = 1000, cols: int = 20) -> gspread.Worksheet:
    """取得或建立指定名稱的工作表"""
    spreadsheet = get_spreadsheet()
    try:
        return spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
