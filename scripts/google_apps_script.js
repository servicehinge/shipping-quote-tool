/**
 * Google Apps Script：原始檔案 → 產品資料 自動同步
 *
 * 使用方式：
 * 1. 開啟 Google Sheets → Extensions → Apps Script
 * 2. 貼上此程式碼（取代預設內容）
 * 3. 儲存（Ctrl+S）
 * 4. 第一次執行需要授權（點選 syncProducts 函式 → Run → 授權）
 * 5. 設定觸發器：Triggers → Add Trigger → syncProducts → On edit
 *
 * 完成後：
 * - 每次編輯「原始檔案」sheet 會自動同步到「產品資料」sheet
 * - 也可以從選單手動觸發：同步產品資料 → 執行同步
 */

// ── 自訂選單 ──
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('同步產品資料 Sync Products')
    .addItem('執行同步 Run Sync', 'syncProducts')
    .addToUi();
}

// ── 自動觸發（onEdit installable trigger） ──
function onEditTrigger(e) {
  // 只在編輯「原始檔案」sheet 時觸發
  if (!e || !e.source) return;
  var sheet = e.source.getActiveSheet();
  if (sheet.getName() !== '原始檔案') return;
  syncProducts();
}

// ── 主要同步函式 ──
function syncProducts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var srcSheet = ss.getSheetByName('原始檔案');
  var dstSheet = ss.getSheetByName('產品資料');

  if (!srcSheet || !dstSheet) {
    SpreadsheetApp.getUi().alert('找不到「原始檔案」或「產品資料」工作表');
    return;
  }

  var data = srcSheet.getDataRange().getValues();
  var rows = [];       // [產品型號, sets_per_carton, weight_kg]
  var seen = {};       // 去重：model+sets → true

  // 從第 2 列開始（第 1 列是標題）
  for (var i = 1; i < data.length; i++) {
    var row = data[i];

    // Column indices (0-based): C=2, D=3, G=6, I=8, N=13
    var colC = String(row[2] || '').trim();   // 規格（原始）
    var colD = String(row[3] || '').trim();   // 修正規格
    var colG = String(row[6] || '').trim();   // 每盒顆數
    var colI = row[8];                         // 每箱盒數
    var colN = row[13];                        // 每箱毛重

    // 如果 D 欄是空的，自動從 C + G 產生
    var model = colD;
    if (!model && colC && colG) {
      var pcsMatch = colG.match(/(\d+)/);
      if (pcsMatch) {
        // 如果 C 已有 -X 後綴就不再加
        if (colC.match(/-X\d+/)) {
          model = colC;
        } else {
          model = colC + '-X' + pcsMatch[1];
        }
        // 同時回寫 D 欄
        srcSheet.getRange(i + 1, 4).setValue(model);
      }
    }

    if (!model) continue;

    // 解析 sets_per_carton（可能含文字如 "5 (滿箱)"）
    var setsRaw = String(colI || '');
    var setsMatch = setsRaw.match(/(\d+)/);
    if (!setsMatch) continue;
    var setsPerCarton = parseInt(setsMatch[1], 10);
    if (setsPerCarton <= 0) continue;

    // 解析 weight
    var weight = parseFloat(colN);
    if (isNaN(weight) || weight <= 0) continue;
    weight = Math.round(weight * 100) / 100;  // 四捨五入到小數第二位

    // 去重
    var key = model + '|' + setsPerCarton;
    if (seen[key]) continue;
    seen[key] = true;

    rows.push([model, setsPerCarton, weight]);
  }

  // 排序：型號 → sets_per_carton
  rows.sort(function(a, b) {
    if (a[0] < b[0]) return -1;
    if (a[0] > b[0]) return 1;
    return a[1] - b[1];
  });

  // 寫入產品資料 sheet
  dstSheet.clear();

  // 標題列
  var header = [['產品型號', 'sets_per_carton', 'weight_kg']];
  dstSheet.getRange(1, 1, 1, 3).setValues(header);

  // 資料列
  if (rows.length > 0) {
    dstSheet.getRange(2, 1, rows.length, 3).setValues(rows);
  }

  // 計算型號數
  var models = {};
  rows.forEach(function(r) { models[r[0]] = true; });
  var modelCount = Object.keys(models).length;

  SpreadsheetApp.getActiveSpreadsheet().toast(
    '已同步 ' + rows.length + ' 筆資料（' + modelCount + ' 個型號）',
    '產品資料同步完成',
    5
  );
}
