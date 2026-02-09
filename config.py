import os
from dotenv import load_dotenv

# Load .env from project root (local development)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _get_secret(key: str, default: str = "") -> str:
    """優先從 Streamlit secrets 讀取，再從環境變數讀取"""
    # 嘗試 Streamlit secrets（Streamlit Cloud 部署時）
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    # 本機開發：從 .env / 環境變數
    return os.getenv(key, default)


FEDEX_API_KEY = _get_secret("FEDEX_API_KEY")
FEDEX_SECRET_KEY = _get_secret("FEDEX_SECRET_KEY")
FEDEX_ACCOUNT_NUMBER = _get_secret("FEDEX_ACCOUNT_NUMBER")
FEDEX_BASE_URL = _get_secret("FEDEX_BASE_URL", "https://apis.fedex.com")

# Sender address (fixed: Taipei office)
SENDER_ADDRESS = {
    "streetLines": ["No.185, Zhiyuan 3rd Rd."],
    "city": "Taipei",
    "stateOrProvinceCode": "",
    "postalCode": "112",
    "countryCode": "TW",
    "residential": False,
}

# Default values
DEFAULT_MARKUP_PERCENT = 15
DEFAULT_EXCHANGE_RATE = 30  # NTD per USD

# Data paths (local fallback)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRODUCTS_JSON = os.path.join(DATA_DIR, "products.json")
HISTORY_CSV = os.path.join(DATA_DIR, "quote_history.csv")

# Google Sheets 設定
GOOGLE_SHEETS_KEY_FILE = os.getenv(
    "GOOGLE_SHEETS_KEY_FILE",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "shipping-quote-486901-dbd435d38327.json",
    ),
)
GOOGLE_SHEETS_SPREADSHEET_ID = _get_secret(
    "GOOGLE_SHEETS_SPREADSHEET_ID",
    "1Bkbj1Iyi-CsSRCEABGlRmxJuvANmQuh41_4uVnHHoo0",
)
# 工作表名稱
SHEET_NAME_PRODUCTS = "產品資料"
SHEET_NAME_HISTORY = "報價紀錄"
