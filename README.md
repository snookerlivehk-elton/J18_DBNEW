# J18 DBCC (Canonical Parser Scaffold)

此專案用於解析 J18 賽事歷史結果 (historyResult) 並轉換為正規化 (Canonical) 資料結構，以供後續存入資料庫 (PostgreSQL)。

## 專案結構

- `docs/` - 包含資料結構規格 (Canonical Spec) 的文件。
- `src/j18_dbnew/parsers/` - 解析 JSON 並轉換為 Canonical Model 的核心程式碼。
- `scripts/` - 用於測試或執行解析腳本。

## 快速開始

1. 建立虛擬環境並安裝依賴：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # 或在 Windows 上使用 .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. 準備測試資料 (`sample_history_result.json`)。

3. 執行解析腳本：
   ```bash
   python scripts/parse_payload.py --input sample_history_result.json
   ```

## 環境變量

請複製 `.env.example` 為 `.env` 並填寫您的資料庫連線字串。
（注意：`.env` 不會被提交到 Git，請確保密碼安全）
