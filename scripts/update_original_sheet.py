"""
在 Google Sheets「原始檔案」工作表的 D 欄填入修正後的型號名稱
（根據 C 欄規格 + G 欄每盒顆數，加上 -X 後綴）
修改過的儲存格用紅色粗體標示
"""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from services.google_sheets import get_gspread_client


def main():
    client = get_gspread_client()
    spreadsheet = client.open_by_key(config.GOOGLE_SHEETS_SPREADSHEET_ID)
    ws = spreadsheet.worksheet("原始檔案")

    all_vals = ws.get_all_values()
    print(f"總列數: {len(all_vals)}")

    # Prepare column D values
    d_values = []
    modified_rows = []  # track which rows were modified (0-indexed)

    for i, row in enumerate(all_vals):
        if i == 0:
            d_values.append(["修正規格"])
            continue

        c_val = row[2].strip() if len(row) > 2 else ""
        g_val = row[6].strip() if len(row) > 6 else ""

        if not c_val:
            d_values.append([""])
            continue

        # Extract number from G (e.g. '2  PCS' -> 2)
        g_match = re.match(r"(\d+)", g_val)
        if not g_match:
            d_values.append([c_val])
            continue

        g_num = int(g_match.group(1))

        # Check if already has -X suffix
        if re.search(r"-X\d+", c_val):
            d_values.append([c_val])
            continue

        # Add -X suffix
        new_name = f"{c_val}-X{g_num}"
        d_values.append([new_name])
        modified_rows.append(i)

    # Update column D
    cell_range = f"D1:D{len(d_values)}"
    ws.update(cell_range, d_values, value_input_option="USER_ENTERED")
    print(f"D 欄已更新: {len(d_values)} 列")
    print(f"有修改的列: {len(modified_rows)} 列")

    # Format modified cells in red bold
    requests = []
    for row_idx in modified_rows:
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": 3,  # Column D
                        "endColumnIndex": 4,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "foregroundColor": {
                                    "red": 1,
                                    "green": 0,
                                    "blue": 0,
                                },
                                "bold": True,
                            }
                        }
                    },
                    "fields": "userEnteredFormat.textFormat",
                }
            }
        )

    if requests:
        spreadsheet.batch_update({"requests": requests})
        print(f"已將 {len(requests)} 個儲存格設為紅色粗體")

    # Show sample
    print("\n=== 前 20 筆對照 ===")
    print(f"{'C欄(原始)':<25} {'D欄(修正)':<25}")
    print("-" * 50)
    for i in range(1, min(21, len(d_values))):
        c = all_vals[i][2].strip() if len(all_vals[i]) > 2 else ""
        d = d_values[i][0]
        marker = " *" if i in modified_rows else ""
        print(f"{c:<25} {d:<25}{marker}")

    print("\n完成!")


if __name__ == "__main__":
    main()
