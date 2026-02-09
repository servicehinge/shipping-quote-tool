"""
將 products.json 上傳到 Google Sheets「產品資料」工作表

工作表格式：
  產品型號 | sets_per_carton | weight_kg
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from services.google_sheets import get_or_create_worksheet

HEADER = ["產品型號", "sets_per_carton", "weight_kg"]


def main():
    # 讀取 products.json
    with open(config.PRODUCTS_JSON, "r", encoding="utf-8") as f:
        products = json.load(f)

    # 整理成列表
    rows = []
    for model, options in sorted(products.items()):
        for opt in options:
            rows.append([model, opt["sets_per_carton"], opt["weight_kg"]])

    print(f"共 {len(rows)} 筆產品包裝資料")

    # 取得或建立工作表
    ws = get_or_create_worksheet(config.SHEET_NAME_PRODUCTS, rows=len(rows) + 10, cols=5)

    # 清空後寫入
    ws.clear()
    ws.update([HEADER] + rows, value_input_option="USER_ENTERED")

    print(f"已上傳到 Google Sheets 工作表「{config.SHEET_NAME_PRODUCTS}」")
    print(f"共 {len(rows)} 列（不含標題）")


if __name__ == "__main__":
    main()
