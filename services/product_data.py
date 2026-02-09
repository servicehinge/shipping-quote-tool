import json
import math
import streamlit as st
import config


def _load_from_google_sheets() -> dict:
    """從 Google Sheets「產品資料」工作表讀取產品資料"""
    from services.google_sheets import get_or_create_worksheet

    ws = get_or_create_worksheet(config.SHEET_NAME_PRODUCTS)
    records = ws.get_all_records()

    products = {}
    for row in records:
        model = str(row.get("產品型號", "")).strip()
        if not model:
            continue
        sets_per_carton = row.get("sets_per_carton", 0)
        weight_kg = row.get("weight_kg", 0)
        try:
            sets_per_carton = int(sets_per_carton)
            weight_kg = float(weight_kg)
        except (ValueError, TypeError):
            continue

        if model not in products:
            products[model] = []
        products[model].append({
            "sets_per_carton": sets_per_carton,
            "weight_kg": weight_kg,
        })

    return products


def _load_from_json() -> dict:
    """從本機 products.json 讀取（備用）"""
    with open(config.PRODUCTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def load_products() -> dict:
    """載入產品資料（優先 Google Sheets，失敗時用本機 JSON）"""
    try:
        products = _load_from_google_sheets()
        if products:
            return products
    except Exception as e:
        st.warning(f"Google Sheets 讀取失敗，改用本機資料: {e}")
    return _load_from_json()


def get_product_models(products: dict) -> list[str]:
    """取得所有產品型號，排序"""
    return sorted(products.keys())


def get_packing_options(products: dict, model: str) -> list[dict]:
    """取得指定型號的所有包裝規格"""
    return products.get(model, [])


def calculate_shipment(packing_option: dict, quantity_sets: int) -> dict:
    """
    計算箱數和總重量

    Args:
        packing_option: {"sets_per_carton": 3, "weight_kg": 9.33}
        quantity_sets: 業務輸入的組數

    Returns:
        {"num_cartons": 10, "total_weight_kg": 93.3}
    """
    sets_per_carton = packing_option["sets_per_carton"]
    weight_per_carton = packing_option["weight_kg"]

    num_cartons = math.ceil(quantity_sets / sets_per_carton)
    total_weight = round(num_cartons * weight_per_carton, 2)

    return {
        "num_cartons": num_cartons,
        "total_weight_kg": total_weight,
    }


def format_packing_label(option: dict) -> str:
    """格式化包裝規格顯示文字"""
    return f"{option['sets_per_carton']} sets/箱, 每箱 {option['weight_kg']} kg"
