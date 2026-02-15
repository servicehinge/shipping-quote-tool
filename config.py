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

# Shippo API (domestic shipping)
SHIPPO_API_TOKEN = _get_secret("SHIPPO_API_TOKEN")

# Domestic sender presets
DOMESTIC_SENDERS = {
    "WLOK": {
        "street1": "861 Production Place",
        "city": "Holland",
        "state": "MI",
        "zip": "49423",
        "country": "US",
    },
    "Gladstone": {
        "street1": "2750 E. Mission Blvd.",
        "city": "Ontario",
        "state": "CA",
        "zip": "91761",
        "country": "US",
    },
}

# Default carton dimensions for Shippo (cm)
DEFAULT_CARTON_LENGTH_CM = 30
DEFAULT_CARTON_WIDTH_CM = 23
DEFAULT_CARTON_HEIGHT_CM = 19

# Domestic pricing: Shippo cost x DOMESTIC_MARKUP + fixed basic cost
DOMESTIC_MARKUP = 1.25

# Ocean shipping (Projects): TW → US warehouse + insurance
OCEAN_COST_PER_KG = 0.55
OCEAN_INSURANCE = 100.0
DOMESTIC_FIXED_COSTS = [
    (5, 5),    # 1-5 sets: +$5
    (10, 10),  # 6-10 sets: +$10
    (15, 15),  # 11-15 sets: +$15
    (20, 20),  # 16-20 sets: +$20
    (25, 25),  # 21-25 sets: +$25
]  # 25+ sets: prompt user

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
