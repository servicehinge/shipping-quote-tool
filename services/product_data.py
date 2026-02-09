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


def calculate_shipment(options: list[dict], quantity_sets: int) -> dict:
    """
    自動計算最佳裝箱方式：先用最大箱裝滿，剩餘用對應的小箱

    Args:
        options: [{"sets_per_carton": 1, "weight_kg": 3.95}, ...] 該型號所有包裝規格
        quantity_sets: 業務輸入的組數

    Returns:
        {
            "num_cartons": 2,
            "total_weight_kg": 23.04,
            "breakdown": [
                {"sets_per_carton": 4, "weight_kg": 15.3, "count": 1},
                {"sets_per_carton": 2, "weight_kg": 7.74, "count": 1},
            ]
        }
    """
    # 建立 sets → weight 對照表，依 sets 由大到小排序
    opts_sorted = sorted(options, key=lambda o: o["sets_per_carton"], reverse=True)
    sets_to_weight = {o["sets_per_carton"]: o["weight_kg"] for o in opts_sorted}

    remaining = quantity_sets
    breakdown = []  # [{sets_per_carton, weight_kg, count}]

    for opt in opts_sorted:
        s = opt["sets_per_carton"]
        if s <= 0 or remaining <= 0:
            continue
        count = remaining // s
        if count > 0:
            breakdown.append({
                "sets_per_carton": s,
                "weight_kg": opt["weight_kg"],
                "count": count,
            })
            remaining -= count * s

    # 若仍有剩餘（沒有剛好整除的箱規），用最小箱裝
    if remaining > 0 and opts_sorted:
        smallest = opts_sorted[-1]  # sets 最小的選項
        breakdown.append({
            "sets_per_carton": smallest["sets_per_carton"],
            "weight_kg": smallest["weight_kg"],
            "count": math.ceil(remaining / smallest["sets_per_carton"]),
        })

    num_cartons = sum(b["count"] for b in breakdown)
    total_weight = round(sum(b["weight_kg"] * b["count"] for b in breakdown), 2)

    return {
        "num_cartons": num_cartons,
        "total_weight_kg": total_weight,
        "breakdown": breakdown,
    }
