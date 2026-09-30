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
    "Santa Fe (LV)": {
        "street1": "6101 N. Hollywood Blvd",
        "street2": "Suite 105",
        "city": "Las Vegas",
        "state": "NV",
        "zip": "89115",
        "country": "US",
    },
}

# Common destinations (quick pick)
COMMON_DESTINATIONS = {
    "Mayflowers": {"zip": "11238", "country": "US"},
    "San Diego Hardware": {"zip": "92123", "country": "US"},
    "IML Dallas": {"zip": "76011", "country": "US"},
}

# Destination countries for the International tab only.
# Keys are FedEx country codes. "label" is what the UI shows: never surface the
# bare code for Canada, because "CA" reads as California to the sales team.
INTL_COUNTRIES = {
    "US": {
        "label": "United States",
        "postal_regex": r"^\d{5}(?:-\d{4})?$",
        "postal_label": "郵遞區號 ZIP Code",
        "postal_term": "ZIP Code",
        "postal_placeholder": "90001",
        "postal_error": "ZIP Code 需為 5 碼數字\nZIP Code must be 5 digits",
        "address_placeholder": "例 Example: 1234 Main St, Los Angeles, CA 90001",
    },
    "CA": {
        "label": "Canada",
        # A1A 1A1. D/F/I/O/Q/U are never used; W/Z never lead.
        "postal_regex": r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d$",
        "postal_label": "郵遞區號 Postal Code",
        "postal_term": "Postal Code",
        "postal_placeholder": "M5V 3A8",
        "postal_error": "加拿大郵遞區號格式為 A1A 1A1\nCanadian postal code must look like A1A 1A1",
        "address_placeholder": "例 Example: 100 Queen St W, Toronto, ON M5H 2N2",
    },
}
DEFAULT_INTL_COUNTRY = "US"

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
    (5, 10),   # 1-5 sets: +$10
    (10, 15),  # 6-10 sets: +$15
    (15, 20),  # 11-15 sets: +$20
    (20, 25),  # 16-20 sets: +$25
    (25, 30),  # 21-25 sets: +$30
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
DEFAULT_EXCHANGE_RATE = 28  # NTD per USD

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
