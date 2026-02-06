import os
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


def _ensure_csv():
    """確保 CSV 檔案存在"""
    os.makedirs(os.path.dirname(config.HISTORY_CSV), exist_ok=True)
    if not os.path.exists(config.HISTORY_CSV):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(config.HISTORY_CSV, index=False)


def _cleanup_old_records(df: pd.DataFrame) -> pd.DataFrame:
    """移除超過 3 個月的紀錄"""
    if df.empty:
        return df
    cutoff = datetime.now() - timedelta(days=90)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df[df["timestamp"] >= cutoff].copy()


def save_quote(quote_data: dict):
    """儲存一筆報價紀錄"""
    _ensure_csv()
    df = pd.read_csv(config.HISTORY_CSV)
    df = _cleanup_old_records(df)

    quote_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = pd.DataFrame([quote_data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(config.HISTORY_CSV, index=False)


def load_history() -> pd.DataFrame:
    """載入歷史紀錄（自動清除超過 3 個月的資料）"""
    _ensure_csv()
    df = pd.read_csv(config.HISTORY_CSV)
    df = _cleanup_old_records(df)
    # Save cleaned data back
    df.to_csv(config.HISTORY_CSV, index=False)
    return df


def export_history_excel(df: pd.DataFrame) -> bytes:
    """將 DataFrame 匯出為 Excel bytes"""
    # Rename columns to Chinese labels
    df_export = df.rename(columns=COLUMN_LABELS)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="運費報價紀錄")
    return output.getvalue()
