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
        print(f"[INFO] 正在請求資料來源 API... URL={url}")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.HTTPError as e:
        # API 回傳 4xx / 5xx：若為 404 通常代表當天無資料，直接跳過
        status_code = resp.status_code if resp is not None else "N/A"
        if status_code == 404:
            print(f"[INFO] API 回傳 404，{today_str} 無賽事資料，跳過同步。")
            sys.exit(0)
        print(f"[ERROR] API HTTP 請求失敗 (HTTP {status_code})：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] API 請求失敗：{e}")
        sys.exit(1)

    # 5. 先檢查 payload 頂層是否有「無資料/錯誤」標記，避免解析階段誤判
    # 常見格式：{"code": -1, "msg": "no data"} 或 {"code": 0, "data": null}
    if isinstance(payload, dict):
        # 檢查是否有明確的錯誤碼或空資料標記
        payload_code = payload.get("code")
        payload_msg = str(payload.get("msg", ""))
        payload_data = payload.get("data")

        # code != 0 且非 0/None：可能是「無資料」的正確回傳
        if payload_code is not None and payload_code != 0:
            print(f"[INFO] API 回傳錯誤碼 code={payload_code}, msg={payload_msg}，判定為當天無資料，跳過同步。")
            sys.exit(0)

        # data 為 None / 空字串 / 空列表：直接判定無資料
        if payload_data is None or payload_data == "" or (isinstance(payload_data, (list, dict)) and len(payload_data) == 0):
            # 進一步確認：data 是空的，但也可能內層結構有資料 (parser 會處理)
            # 這裡先不直接 exit，交給 parser 再確認一次，避免誤判
            print(f"[INFO] payload['data'] 為空，繼續交給解析器確認是否有內層資料...")

    # 6. 解析資料
    try:
        canonical_races = HistoryResultParser.parse(payload)
    except Exception as e:
        # 解析失敗時，額外印出部分 payload 方便 debug，但不印出整份避免 Log 過大
        snippet = str(payload)[:500] if payload is not None else "None"
        print(f"[WARN] 資料解析失敗，可能是無資料或格式異常：{e}")
        print(f"[WARN] payload 片段：{snippet}")
        print(f"[INFO] 本次解析視為「當天無賽事」，跳過同步。")
        # 解析失敗不應視為 Cron Job 錯誤（可能當天真的沒比賽，API 回傳怪格式）
        sys.exit(0)

    if not canonical_races:
        print(f"[INFO] {today_str} 沒有賽事資料，跳過同步。")
        # 沒有賽事不應視為錯誤，Cron Job 下次再跑即可
        sys.exit(0)

    # 7. 寫入資料庫
    db = SessionLocal()
    try:
        races_synced = crud.sync_races_to_db(db=db, canonical_races=canonical_races, racing_date=today_str)
        horses_count = sum(len(r.horses) for r in canonical_races)
        print(f"[SUCCESS] 同步成功！共寫入/更新 {races_synced} 場賽事，{horses_count} 筆馬匹成績。")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 資料庫寫入失敗：{e}")
        sys.exit(1)
    finally:
        db.close()

    print("[INFO] 每日同步作業完成。")
    print("=" * 50)

if __name__ == "__main__":
    main()
