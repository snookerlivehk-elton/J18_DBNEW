# Railway 設定每日定時同步 (Cron Job) 操作手冊

本手冊指導您如何在 Railway 上設定 Cron Jobs，利用 `scripts/daily_sync.py` 自動檢查並同步當天賽事資料。

## 1. 設定步驟

### Step 1: 進入服務設定
打開您的 Railway 專案 (J18_DBNEW)，進入 **J18_DBNEW** 服務的頁面。
點擊左側選單的 **Settings** (設定) 索引標籤。

### Step 2: 設定 Cron Jobs
在 Settings 頁面中，找到 **Cron Jobs** (定時任務) 區塊。
點擊 **+ Add Cron Job** (新增定時任務) 按鈕。

### Step 3: 新增第一個任務 (每日 01:00)
根據您的需求，每天香港時間 01:00 嘗試抓取當天的資料。
**注意**：Railway Cron 的排程時區預設為 **UTC**。因此：
- 香港時間 (UTC+8) **01:00** = UTC **17:00** (前一天)

填寫以下資訊：
- **Schedule (排程)**：點擊切換到 `Standard CRON syntax` (標準 Cron 語法)
- **Syntax**：`0 17 * * *` (代表每日 17:00 UTC)
- **Start Command (啟動指令)**：
  ```bash
  python scripts/daily_sync.py
  ```
- **Name (名稱)**：Daily Sync 01:00 (HKT)
- 點擊 **Add Cron** 或 **Save** 儲存。

### Step 4: 新增第二個任務 (每日 23:00)
確保晚上比賽完結後抓最新的最終賽果。
- 香港時間 (UTC+8) **23:00** = UTC **15:00**

再次點擊 **+ Add Cron Job**：
- **Syntax**：`0 15 * * *` (代表每日 15:00 UTC)
- **Start Command**：
  ```bash
  python scripts/daily_sync.py
  ```
- **Name**：Daily Sync 23:00 (HKT)
- 儲存設定。

## 2. 驗證方式
設定完成後，您可以：
1. 點擊 Cron Job 右側的 **Run** (立即執行) 按鈕，手動觸發一次，觀察 Deploy Logs 是否顯示 `[SUCCESS]`。
2. 或者返回主頁面觀察「資料庫同步狀態」的「最晚同步日期」是否更新。
3. 如果當天沒有賽事，Log 會正常顯示 `[INFO] ... 沒有賽事資料，跳過同步。`，這是正常狀況，不會報錯。
