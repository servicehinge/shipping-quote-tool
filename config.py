import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

FEDEX_API_KEY = os.getenv("FEDEX_API_KEY", "")
FEDEX_SECRET_KEY = os.getenv("FEDEX_SECRET_KEY", "")
FEDEX_ACCOUNT_NUMBER = os.getenv("FEDEX_ACCOUNT_NUMBER", "")
FEDEX_BASE_URL = os.getenv("FEDEX_BASE_URL", "https://apis.fedex.com")

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

# Data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRODUCTS_JSON = os.path.join(DATA_DIR, "products.json")
HISTORY_CSV = os.path.join(DATA_DIR, "quote_history.csv")
