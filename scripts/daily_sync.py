"""
每日自動同步腳本 (Daily Sync Scheduler Script)

用途：
    嘗試從遠端 historyResult API 抓取「今天」的賽事資料並寫入資料庫。
    適用於 Cron Job (例如 Railway 的 Cron 功能)，建議設定在每天 01:00 及 23:00 執行。

使用方式：
    python scripts/daily_sync.py

執行邏輯：
    1. 檢查 DATABASE_URL 與 J18_HISTORY_RESULT_URL 環境變數。
    2. 獲取「今天」日期 (UTC+8，香港時間)。
    3. 呼叫 historyResult API 查詢今天是否有賽事。
    4. 若有賽事，則寫入/覆蓋更新到 races_v2 / horses_v2。
"""

import os
import sys
import datetime
import requests

# 將 src 目錄加入 Python 路徑，確保能正確匯入模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from j18_dbnew.parsers.history_result import HistoryResultParser
from j18_dbnew.db.database import SessionLocal, engine, Base
from j18_dbnew.db import models, crud

def get_today_hk() -> str:
    """
    取得香港時區 (UTC+8) 的今天日期字串 YYYY-MM-DD
    """
    utc_now = datetime.datetime.utcnow()
    hk_time = utc_now + datetime.timedelta(hours=8)
    return hk_time.strftime('%Y-%m-%d')

def main():
    print("=" * 50)
    print("[J18_DAILY_SYNC] 開始執行每日同步作業")
    
    # 1. 驗證環境變數
    base_url = os.getenv("J18_HISTORY_RESULT_URL")
    db_url = os.getenv("DATABASE_URL")
    
    if not base_url:
        print("[ERROR] 缺少環境變數 J18_HISTORY_RESULT_URL，無法進行同步。")
        sys.exit(1)
    if not db_url:
        print("[ERROR] 缺少環境變數 DATABASE_URL，無法連線至資料庫。")
        sys.exit(1)

    # 2. 確保資料表存在 (若是首次執行則自動建立)
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[WARN] 建立資料表時發生錯誤 (可能已存在)：{e}")

    # 3. 取得今天日期
    today_str = get_today_hk()
    print(f"[INFO] 香港時間今天日期：{today_str}")

    # 4. 呼叫遠端 API
    url = f"{base_url}?date={today_str}"
    try:
        print(f"[INFO] 正在請求資料來源 API...")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        print(f"[ERROR] API 請求失敗：{e}")
        sys.exit(1)

    # 5. 解析資料
    try:
        canonical_races = HistoryResultParser.parse(payload)
    except Exception as e:
        print(f"[ERROR] 資料解析失敗：{e}")
        sys.exit(1)

    if not canonical_races:
        print(f"[INFO] {today_str} 沒有賽事資料，跳過同步。")
        # 沒有賽事不應視為錯誤，Cron Job 下次再跑即可
        sys.exit(0)

    # 6. 寫入資料庫
    db = SessionLocal()
    try:
        races_synced = crud.sync_races_to_db(db=db, canonical_races=canonical_races, racing_date=today_str)
        print(f"[SUCCESS] 同步成功！共寫入/更新 {races_synced} 場賽事。")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 資料庫寫入失敗：{e}")
        sys.exit(1)
    finally:
        db.close()

    print("=" * 50)

if __name__ == "__main__":
    main()
