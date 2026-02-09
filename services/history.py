import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import config


COLUMNS = [
    "timestamp",
    "product_model",
    "packing_config",
    "quantity_sets",
    "num_cartons",
    "total_weight_kg",
    "destination_state",
    "destination_zip",
    "service_type",
    "service_name",
    "shipping_cost_ntd",
    "exchange_rate",
    "usd_cost",
    "markup_percent",
    "quoted_price_usd",
    "cost_per_kg_ntd",
]

COLUMN_LABELS = {
    "timestamp": "日期時間",
    "product_model": "產品型號",
    "packing_config": "包裝規格",
    "quantity_sets": "數量(sets)",
    "num_cartons": "箱數",
    "total_weight_kg": "總重量(kg)",
    "destination_state": "州別",
    "destination_zip": "ZIP Code",
    "service_type": "服務類型",
    "service_name": "服務名稱",
    "shipping_cost_ntd": "運費成本(NT$)",
    "exchange_rate": "匯率",
    "usd_cost": "美金成本(USD)",
    "markup_percent": "加成(%)",
    "quoted_price_usd": "報價金額(USD)",
    "cost_per_kg_ntd": "每KG成本(NT$)",
}

# Google Sheets 標題列（與 COLUMNS 對應的中文）
SHEET_HEADER = [COLUMN_LABELS.get(c, c) for c in COLUMNS]


def _get_history_worksheet():
    """取得 Google Sheets 報價紀錄工作表"""
    from services.google_sheets import get_or_create_worksheet

    ws = get_or_create_worksheet(config.SHEET_NAME_HISTORY)
    return ws


def _ensure_header(ws):
    """確保工作表有標題列"""
    first_row = ws.row_values(1)
    if not first_row or first_row[0] != SHEET_HEADER[0]:
        ws.update([SHEET_HEADER], value_input_option="USER_ENTERED")


def _cleanup_old_records_sheet(ws):
    """移除 Google Sheets 上超過 3 個月的紀錄"""
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return  # 只有標題或空表

    cutoff = datetime.now() - timedelta(days=90)
    rows_to_delete = []

    for i, row in enumerate(all_values[1:], start=2):  # 從第2列開始（跳過標題）
        try:
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if ts < cutoff:
                rows_to_delete.append(i)
        except (ValueError, IndexError):
            continue

    # 從最後一列開始刪（避免列號位移）
    for row_idx in reversed(rows_to_delete):
        ws.delete_rows(row_idx)


def save_quote(quote_data: dict):
    """儲存一筆報價紀錄到 Google Sheets"""
    ws = _get_history_worksheet()
    _ensure_header(ws)

    quote_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 按 COLUMNS 順序組成一列
    row = [str(quote_data.get(col, "")) for col in COLUMNS]
    ws.append_row(row, value_input_option="USER_ENTERED")


def load_history() -> pd.DataFrame:
    """從 Google Sheets 載入歷史紀錄（自動清除超過 3 個月的資料）"""
    ws = _get_history_worksheet()
    _ensure_header(ws)

    # 清除過期紀錄
    _cleanup_old_records_sheet(ws)

    # 讀取所有資料
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(records)

    # 將中文欄名對應回英文欄名
    reverse_labels = {v: k for k, v in COLUMN_LABELS.items()}
    df = df.rename(columns=reverse_labels)

    # 確保所有必要欄位存在
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # 轉換數字欄位
    numeric_cols = [
        "quantity_sets", "num_cartons", "total_weight_kg",
        "shipping_cost_ntd", "exchange_rate", "usd_cost",
        "markup_percent", "quoted_price_usd", "cost_per_kg_ntd",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[COLUMNS]


def export_history_excel(df: pd.DataFrame) -> bytes:
    """將 DataFrame 匯出為 Excel bytes"""
    df_export = df.rename(columns=COLUMN_LABELS)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="運費報價紀錄")
    return output.getvalue()
