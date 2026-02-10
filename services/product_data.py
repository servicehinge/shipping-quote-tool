import json
import math
import re
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


def sync_products_from_source() -> int:
    """從「原始檔案」sheet 同步到「產品資料」sheet，回傳同步筆數"""
    from services.google_sheets import get_or_create_worksheet

    src_ws = get_or_create_worksheet("原始檔案")
    dst_ws = get_or_create_worksheet(config.SHEET_NAME_PRODUCTS)

    all_vals = src_ws.get_all_values()

    rows = []
    seen = set()

    for i in range(1, len(all_vals)):
        row = all_vals[i]
        col_c = row[2].strip() if len(row) > 2 else ""   # 規格
        col_d = row[3].strip() if len(row) > 3 else ""   # 修正規格
        col_g = row[6].strip() if len(row) > 6 else ""   # 每盒顆數
        col_i = row[8].strip() if len(row) > 8 else ""   # 每箱盒數
        col_n = row[13].strip() if len(row) > 13 else ""  # 每箱毛重

        # 如果 D 欄空，從 C + G 產生
        model = col_d
        if not model and col_c and col_g:
            g_match = re.match(r"(\d+)", col_g)
            if g_match:
                if re.search(r"-X\d+", col_c):
                    model = col_c
                else:
                    model = f"{col_c}-X{g_match.group(1)}"

        if not model:
            continue

        # 解析 sets_per_carton
        s_match = re.match(r"(\d+)", col_i)
        if not s_match:
            continue
        sets_per_carton = int(s_match.group(1))
        if sets_per_carton <= 0:
            continue

        # 解析 weight
        try:
            weight = float(col_n)
        except (ValueError, TypeError):
            continue
        if weight <= 0:
            continue
        weight = round(weight, 2)

        # 去重
        key = (model, sets_per_carton)
        if key in seen:
            continue
        seen.add(key)

        rows.append([model, sets_per_carton, weight])

    # 排序
    rows.sort(key=lambda r: (r[0], r[1]))

    # 寫入產品資料 sheet
    header = ["產品型號", "sets_per_carton", "weight_kg"]
    dst_ws.clear()
    dst_ws.update([header] + rows, value_input_option="USER_ENTERED")

    return len(rows)


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
