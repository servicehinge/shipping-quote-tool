import streamlit as st
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from services.product_data import load_products
from pages.quote import render_quote_page
from pages.history_page import render_history_page

st.set_page_config(
    page_title="K51 國際運費報價系統",
    page_icon="📦",
    layout="wide",
)

# ── Sidebar ──
with st.sidebar:
    st.title("K51 運費報價系統")
    st.divider()

    # Navigation — 支援從歷史紀錄頁跳轉回報價頁
    nav_options = ["運費報價", "歷史紀錄"]
    nav_default = 0
    if "nav_page" in st.session_state:
        target = st.session_state.pop("nav_page")
        if target in nav_options:
            nav_default = nav_options.index(target)
    page = st.radio("頁面", nav_options, index=nav_default, label_visibility="collapsed")

    st.divider()
    st.subheader("FedEx 設定")

    fedex_account = st.text_input(
        "FedEx 帳號 (9碼)",
        value=config.FEDEX_ACCOUNT_NUMBER,
        type="password",
        help="在 FedEx 帳單或 Developer Portal 上可找到的 9 位數帳號",
    )
    st.session_state["fedex_account"] = fedex_account

    # Show environment info
    base_url = config.FEDEX_BASE_URL
    if "sandbox" in base_url:
        st.caption("🟡 測試環境 (Sandbox)")
    else:
        st.caption("🟢 正式環境 (Production)")

# ── Load product data ──
@st.cache_data(ttl=600)
def cached_load_products():
    return load_products()

try:
    products = cached_load_products()
except Exception as e:
    st.error(f"載入產品資料失敗: {e}")
    st.stop()

# ── Render page ──
if page == "運費報價":
    render_quote_page(products)
elif page == "歷史紀錄":
    render_history_page()
