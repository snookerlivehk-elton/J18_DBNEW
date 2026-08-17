"""
SpeedPro 自動爬取 Cron Job 腳本 (cron_speedpro_fetch.py)

用途：
    從 HKJC SpeedPro 的 sg_race_*.json (能量評分) 與 fg_race_*.json (賽績指引) 端點
    自動抓取「未來 2 天內有賽事」的 SpeedPro 資料，寫入 kv_store_v2 表格。

注意（與 hkjc_analytics 同步）：
    SpeedPro 數據只會在「開賽前 24 小時內」才會更新，因此本腳本會：
      1. 先查詢 races_v2 中「今天 + 明天」是否有賽事。
      2. 針對每個候選日期，判斷「現在 HK 時間是否 >= 比賽日 00:00 - 36 小時」
         （也就是大約在比賽日前一天中午之後才開始嘗試爬，避免爬到空/舊資料）。
      3. 環境變數可覆蓋：SPEEDPRO_START_HOURS_BEFORE（預設 36 小時）
                         SPEEDPRO_END_HOURS_AFTER（預設 12 小時，賽後仍可重爬 12 小時）。

核對去重邏輯（重點）：
    1. 每一場賽事 (racing_date + race_num) 會以 KV key 記錄爬取結果與狀態：
        - speedpro_energy:{date}:{rn}    → 能量評分 JSON
        - speedpro_energy_info:{date}:{rn} → 爬取中繼資訊 (hash, 抓取時間, 筆數)
        - speedpro_formguide:{date}:{rn} → 賽績指引 JSON
        - speedpro_retry:{date}:{rn}     → 重試狀態 (done 旗標 / 下次重試時間 / 次數)
    2. 每次執行前先檢查上述 key：
        - 若 speedpro_retry:{date}:{rn} 的 done=True 且 speedpro_energy 資料完整
          → 直接跳過，不重複爬取。
        - 若上次失敗但未到「下次重試時間」 → 跳過，留待 Cron 下次再試。
    3. 提供分散式鎖 job_lock:speedpro_fetch，避免 Cron 重入。

使用方式 (建議設定 Hourly 每小時執行一次)：
    python scripts/cron_speedpro_fetch.py

環境變數 (必填/選填)：
    - DATABASE_URL                  ：(必填) PostgreSQL 連線字串
    - SPEEDPRO_ENERGY_URL_TEMPLATE  ：(必填) 例如 https://consvc.hkjc.com/.../sg_race_{}
    - SPEEDPRO_FORMGUIDE_URL_TEMPLATE：(必填) 例如 https://consvc.hkjc.com/.../fg_race_{}
    - TARGET_DATE                   ：(選填) 強制指定目標日期 YYYY-MM-DD 或 YYYY/MM/DD
    - FORCE_SPEEDPRO_FETCH          ：(選填) 1/true/yes 時，忽略重複核對+時間窗口，強制重爬
    - FORCE_FORMGUIDE               ：(選填) 1/true/yes 時，忽略 FormGuide 重複核對
    - SPEEDPRO_RETRY_MINUTES        ：(選填) 失敗後重試間隔分鐘，預設 90 分鐘
    - SPEEDPRO_START_HOURS_BEFORE   ：(選填) 開賽前多少小時開始爬，預設 36 (提前一天中午開始嘗試)
    - SPEEDPRO_END_HOURS_AFTER      ：(選填) 開賽後多少小時停止爬，預設 12 (賽後最終修正)
    - SPEEDPRO_LOOKAHEAD_DAYS       ：(選填) 往前看多幾天找目標賽事，預設 2 (今天 + 明天)
    - RACE_NOS                      ：(選填) 只爬指定場次，例如 "1,3,5"
"""

import os
import sys
import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# 將 src 目錄加入 Python 路徑
root_path = str(Path(__file__).resolve().parent.parent)
src_path = str(Path(root_path) / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from j18_dbnew.scrapers.speedpro_energy import SpeedProEnergyScraper
from j18_dbnew.scrapers.speedpro_formguide import SpeedProFormGuideScraper
from j18_dbnew.db.database import SessionLocal, engine, Base
from j18_dbnew.db import models, crud


# ============================================================
# 常數 / 工具函數
# ============================================================

LOCK_KEY = "job_lock:speedpro_fetch"
LOCK_TTL_MIN = 15  # 鎖 TTL，超過 15 分鐘自動過期（避免崩潰後永久鎖住）


def _get_today_hk_str() -> str:
    """取得香港時間 (UTC+8) 今天日期，格式 YYYY-MM-DD"""
    utc_now = datetime.datetime.utcnow()
    hk_time = utc_now + datetime.timedelta(hours=8)
    return hk_time.strftime("%Y-%m-%d")


def _now_hk() -> datetime.datetime:
    """取得現在的香港時間 datetime (帶時區意義，單純加 8 小時)"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def _parse_date_str(s: str) -> Optional[str]:
    """兼容 YYYY-MM-DD / YYYY/MM/DD，統一輸出 YYYY-MM-DD"""
    s = str(s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            return d.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def _sha256_json(v) -> str:
    """對 JSON 內容做 sha256，用於比對資料是否變動"""
    payload = json.dumps(v, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ============================================================
# 分散式鎖
# ============================================================

def _acquire_lock(db) -> bool:
    """嘗試取得爬取鎖；成功返回 True，若已有未過期的鎖返回 False"""
    now = _now_hk()
    cfg = crud.get_kv(db, LOCK_KEY)
    if cfg and isinstance(cfg.value, str):
        try:
            ts = datetime.datetime.fromisoformat(cfg.value)
            if (now - ts) < datetime.timedelta(minutes=LOCK_TTL_MIN):
                return False
        except Exception:
            pass
    crud.upsert_kv(db, LOCK_KEY, now.isoformat(), "SpeedPro Cron 分散式鎖 (HK Time)")
    return True


def _release_lock(db):
    """釋放爬取鎖"""
    try:
        crud.delete_kv(db, LOCK_KEY)
    except Exception:
        pass


# ============================================================
# 時間窗口 / 目標日期解析
# ============================================================

def _env_int(name: str, default: int) -> int:
    """安全地解析環境變數為整數，失敗回傳 default"""
    v = str(os.environ.get(name, "")).strip()
    if v.isdigit():
        return int(v)
    return default


def _start_hours_before() -> int:
    """開賽前多少小時開始爬，預設 36 小時（SpeedPro 約在此時更新）"""
    return _env_int("SPEEDPRO_START_HOURS_BEFORE", 36)


def _end_hours_after() -> int:
    """開賽後多少小時停止爬（賽後仍可能有最後修正），預設 12 小時"""
    return _env_int("SPEEDPRO_END_HOURS_AFTER", 12)


def _lookahead_days() -> int:
    """往前看多幾天找目標賽事，預設 2 天（今天 + 明天）"""
    return max(1, _env_int("SPEEDPRO_LOOKAHEAD_DAYS", 2))


def _is_within_fetch_window(racedate_str: str, now_hk: datetime.datetime,
                            start_hours_before: int, end_hours_after: int) -> Tuple[bool, str]:
    """
    判斷某個賽事日期是否處於「可爬取時間窗口」內
    窗口區間：[racedate 00:00 - start_hours_before , racedate 23:59 + end_hours_after]
    返回：(是否在窗口內, 解釋文字)
    """
    try:
        d = datetime.datetime.strptime(racedate_str, "%Y-%m-%d").date()
    except Exception:
        return False, "invalid_date"
    # 窗口起點：比賽日 00:00 減 start_hours_before（例如比賽日前一天 00:00）
    window_start = datetime.datetime.combine(d, datetime.time.min) - datetime.timedelta(hours=start_hours_before)
    # 窗口終點：比賽日 23:59 再加 end_hours_after（例如比賽日隔日中午 12:00）
    window_end = datetime.datetime.combine(d, datetime.time.max) + datetime.timedelta(hours=end_hours_after)
    if now_hk < window_start:
        delta = (window_start - now_hk)
        return False, f"too_early (還要等 {int(delta.total_seconds() // 3600)} 小時才進入窗口)"
    if now_hk > window_end:
        return False, "too_late (比賽已結束超過窗口)"
    return True, "ok"


def _candidate_racedates(db, now_hk: datetime.datetime) -> List[str]:
    """
    找所有候選賽事日期並通過時間窗口過濾：
      1. 若有 TARGET_DATE 環境變數 → 只回傳它（忽略窗口，手動指定代表使用者想強制爬）
      2. 否則回傳 races_v2 中 [今天, 今天+lookahead_days) 區間內有賽事且在窗口內的日期
    """
    env_date = os.environ.get("TARGET_DATE", "").strip()
    if env_date:
        parsed = _parse_date_str(env_date)
        return [parsed] if parsed else []

    lookahead = _lookahead_days()
    today_str = _get_today_hk_str()
    today_d = datetime.datetime.strptime(today_str, "%Y-%m-%d").date()
    start_h = _start_hours_before()
    end_h = _end_hours_after()
    force_all = str(os.environ.get("FORCE_SPEEDPRO_FETCH", "")).strip().lower() in ("1", "true", "yes")

    # 查詢 races_v2 中此日期區間內所有有賽事的相異日期
    from sqlalchemy import func as sa_func
    try:
        end_d = today_d + datetime.timedelta(days=lookahead)
        rows = (
            db.query(sa_func.distinct(models.RaceModel.racing_date))
            .filter(models.RaceModel.racing_date >= today_str)
            .filter(models.RaceModel.racing_date < end_d.isoformat())
            .all()
        )
    except Exception as e:
        print(f"[WARN] 查詢 races_v2 候選日期失敗，退化成只抓今天：{e}")
        rows = [(today_str,)]

    out = []
    for (rd,) in rows:
        rd_s = str(rd or "").strip()
        if not rd_s:
            continue
        if force_all:
            out.append(rd_s)
            continue
        ok, reason = _is_within_fetch_window(rd_s, now_hk, start_h, end_h)
        if ok:
            out.append(rd_s)
        else:
            print(f"[INFO] 跳過日期 {rd_s}：{reason}")
    return out


def _retry_minutes() -> int:
    """重試間隔分鐘，預設 90 分鐘"""
    return _env_int("SPEEDPRO_RETRY_MINUTES", 90)


def _wanted_race_nos(all_race_nos):
    """從 RACE_NOS / RACE_NO 環境變數過濾場次"""
    only_nos = os.environ.get("RACE_NOS", "").strip()
    only_no = os.environ.get("RACE_NO", "").strip()
    wanted = set()
    if only_nos:
        for part in only_nos.split(","):
            part = part.strip()
            if part.isdigit():
                wanted.add(int(part))
    elif only_no.isdigit():
        wanted.add(int(only_no))
    if wanted:
        return [rn for rn in all_race_nos if int(rn) in wanted]
    return all_race_nos


# ============================================================
# SpeedPro 結果完整性核對 (用於去重判斷)
# ============================================================

def _is_energy_payload_done(data_map: Dict[int, Any]) -> Tuple[bool, str]:
    """
    判斷 Energy 資料是否「足夠完整」可視為完成，避免重複爬取：
      - 至少 6 匹馬的資料
      - 同時存在 status_rating 與 energy_assess 的覆蓋率 >= 60%
    """
    if not isinstance(data_map, dict) or not data_map:
        return False, "empty"
    rows = list(data_map.values())
    total = len(rows)
    both = 0
    has_energy = 0
    has_status = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        ea = r.get("energy_assess")
        sr = r.get("status_rating")
        if ea is not None:
            has_energy += 1
        if sr is not None:
            has_status += 1
        if ea is not None and sr is not None:
            both += 1
    if total < 6:
        return False, f"too_few_rows:{total}"
    if has_energy == 0 or has_status == 0:
        return False, "missing_required_fields"
    if (both / float(total)) < 0.6:
        return False, f"low_coverage:{both}/{total}"
    return True, "ok"


def _is_formguide_payload_done(data_map: Dict[int, Any]) -> bool:
    """
    判斷 FormGuide 資料是否足夠完整：
      - 非空，且每匹馬至少有 intro_comment 或 trial_comment 其中一個
    """
    if not isinstance(data_map, dict) or not data_map:
        return False
    ok_cnt = 0
    for v in data_map.values():
        if not isinstance(v, dict):
            continue
        intro = str(v.get("intro_comment", "")).strip()
        trial = str(v.get("trial_comment", "")).strip()
        if intro or trial:
            ok_cnt += 1
    # 至少 60% 的馬匹有評論才算完整
    return (ok_cnt / max(1, len(data_map))) >= 0.6


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("[J18_SPEEDPRO_CRON] 開始執行 SpeedPro 自動爬取作業")

    # 1. 驗證環境變數與 DB 連線
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[ERROR] 缺少環境變數 DATABASE_URL，無法連線至資料庫。")
        sys.exit(1)

    energy_tpl = os.environ.get("SPEEDPRO_ENERGY_URL_TEMPLATE", "")
    fg_tpl = os.environ.get("SPEEDPRO_FORMGUIDE_URL_TEMPLATE", "")
    if (not energy_tpl) and (not fg_tpl):
        print("[WARN] SPEEDPRO_ENERGY_URL_TEMPLATE / SPEEDPRO_FORMGUIDE_URL_TEMPLATE 皆未設定，結束作業。")
        sys.exit(0)

    # 2. 確保 kv_store_v2 表存在
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[WARN] 建立/檢查資料表時發生錯誤（可能已存在）：{e}")

    db = SessionLocal()
    try:
        # 3. 取得鎖，避免 Cron 重入
        if not _acquire_lock(db):
            print("[INFO] 已有正在執行的 SpeedPro Cron Job（鎖未過期），跳過本次。")
            return

        force_all = str(os.environ.get("FORCE_SPEEDPRO_FETCH", "")).strip().lower() in ("1", "true", "yes")
        force_fg = str(os.environ.get("FORCE_FORMGUIDE", "")).strip().lower() in ("1", "true", "yes")
        now_hk = _now_hk()

        # 4. 取得所有符合時間窗口的候選賽事日期
        racedates = _candidate_racedates(db, now_hk)
        if not racedates:
            print("[INFO] 目前沒有任何賽事日期落在 SpeedPro 可爬取時間窗口內，結束作業。")
            return
        print(f"[INFO] 本次目標賽事日期：{racedates} (香港時間)")
        start_h = _start_hours_before()
        end_h = _end_hours_after()
        print(f"[INFO] 爬取時間窗口：開賽前 {start_h} 小時 ~ 開賽後 {end_h} 小時")

        scraper = SpeedProEnergyScraper() if energy_tpl else None
        fg_scraper = SpeedProFormGuideScraper() if fg_tpl else None
        any_work = False

        # 5. 逐日期、逐場爬取 + 去重核對
        for racedate_str in racedates:
            all_race_nos = crud.list_race_nos_by_date(db, racedate_str)
            race_nos = _wanted_race_nos(all_race_nos)
            if not race_nos:
                print(f"[INFO] {racedate_str} 沒有任何賽事場次，跳過。")
                continue
            print(f"[INFO] [{racedate_str}] 預計處理場次：{sorted(race_nos)}")

            for rn in race_nos:
                rn_int = int(rn)
                snap_key = f"speedpro_energy:{racedate_str}:{rn_int}"
                retry_key = f"speedpro_retry:{racedate_str}:{rn_int}"
                fg_snap_key = f"speedpro_formguide:{racedate_str}:{rn_int}"
                info_key = f"speedpro_energy_info:{racedate_str}:{rn_int}"

                # ---------- 5a. Energy 去重核對 ----------
                energy_done = False
                if scraper is not None:
                    snap_cfg = crud.get_kv(db, snap_key)
                    if snap_cfg and isinstance(snap_cfg.value, dict):
                        ok, _reason = _is_energy_payload_done(snap_cfg.value)
                        if ok and (not force_all):
                            energy_done = True

                    # Energy 已完成 → 只補 FormGuide（若有需要）
                    if energy_done:
                        if fg_scraper is not None:
                            fg_cfg = crud.get_kv(db, fg_snap_key)
                            needs_fg = (not fg_cfg) or (not isinstance(fg_cfg.value, dict)) or (not fg_cfg.value)
                            if (not needs_fg) and isinstance(fg_cfg.value, dict):
                                needs_fg = not _is_formguide_payload_done(fg_cfg.value)
                            if force_fg or needs_fg:
                                try:
                                    fg_data = fg_scraper.scrape(rn_int)
                                    if fg_data:
                                        normalized_fg = {
                                            str(int(k)): v for k, v in fg_data.items()
                                            if str(k).isdigit() and isinstance(v, dict)
                                        }
                                        crud.upsert_kv(
                                            db, fg_snap_key, normalized_fg,
                                            f"SpeedPro FormGuide（{racedate_str} R{rn_int}）"
                                        )
                                        print(f"[OK ] {fg_snap_key} rows={len(normalized_fg)}")
                                except Exception as e:
                                    print(f"[ERR] 爬取 FormGuide {fg_snap_key}: {e}")
                        continue  # Energy 已 done，直接跳下一場

                    # ---------- 5b. 檢查重試狀態 (避免失敗後每小時狂打 API) ----------
                    retry_state = {}
                    if not force_all:
                        retry_cfg = crud.get_kv(db, retry_key)
                        retry_state = retry_cfg.value if retry_cfg and isinstance(retry_cfg.value, dict) else {}
                        done = bool(retry_state.get("done") is True)
                        last_err = str(retry_state.get("last_error") or "").strip().lower()
                        if done and last_err == "expired":
                            # 已過期的狀態可以重試
                            pass
                        elif done:
                            # 已標記完成，不再爬
                            if fg_scraper is not None and force_fg:
                                try:
                                    fg_data = fg_scraper.scrape(rn_int)
                                    if fg_data:
                                        normalized_fg = {
                                            str(int(k)): v for k, v in fg_data.items()
                                            if str(k).isdigit() and isinstance(v, dict)
                                        }
                                        crud.upsert_kv(db, fg_snap_key, normalized_fg,
                                                       f"SpeedPro FormGuide（{racedate_str} R{rn_int}）")
                                        print(f"[OK ] {fg_snap_key} rows={len(normalized_fg)}")
                                except Exception as e:
                                    print(f"[ERR] 爬取 FormGuide {fg_snap_key}: {e}")
                            continue

                        next_retry_at = retry_state.get("next_retry_at")
                        if isinstance(next_retry_at, str) and next_retry_at.strip():
                            try:
                                nr = datetime.datetime.fromisoformat(next_retry_at)
                                if now_hk < nr:
                                    continue  # 還沒到重試時間，跳過
                            except Exception:
                                pass

                    attempt = int(retry_state.get("attempt_count") or 0) + 1
                    any_work = True

                    # ---------- 5c. 爬取 Energy ----------
                    err = ""
                    data_map = {}
                    try:
                        data_map = scraper.scrape(rn_int)
                    except Exception as e:
                        err = f"fetch_error:{e}"
                        data_map = {}

                    # 預期馬匹數量校驗（避免只有幾筆就當成成功）
                    exp_cnt = crud.expected_horse_count(db, racedate_str, rn_int)
                    if exp_cnt and isinstance(data_map, dict) and data_map:
                        if len(data_map) < max(6, int(exp_cnt * 0.6)):
                            err = f"insufficient_rows:{len(data_map)}/{exp_cnt}"

                    ok, reason = (True, "ok") if (not err) else (False, err)
                    if ok:
                        ok, reason = _is_energy_payload_done(data_map)

                    if ok:
                        # 寫入 Energy 結果 + info
                        normalized = {
                            str(int(k)): v for k, v in data_map.items()
                            if str(k).isdigit() and isinstance(v, dict)
                        }
                        crud.upsert_kv(
                            db, snap_key, normalized,
                            f"SpeedPro 能量評分（{racedate_str} R{rn_int}）"
                        )
                        info_val = {
                            "racedate": racedate_str,
                            "race_no": rn_int,
                            "captured_at": now_hk.isoformat(),
                            "raw_hash": _sha256_json(normalized),
                            "rows": len(normalized),
                        }
                        crud.upsert_kv(
                            db, info_key, info_val,
                            f"SpeedPro 能量評分抓取資訊（{racedate_str} R{rn_int}）"
                        )
                        # 標記 retry_state = done
                        state = {
                            "done": True,
                            "attempt_count": attempt,
                            "last_attempt_at": now_hk.isoformat(),
                            "next_retry_at": None,
                            "last_error": None,
                        }
                        crud.upsert_kv(
                            db, retry_key, state,
                            f"SpeedPro 重試狀態（{racedate_str} R{rn_int}）"
                        )
                        print(f"[OK ] {snap_key} rows={len(normalized)} (done={attempt} 次嘗試)")

                        # Energy 成功後順便抓 FormGuide（如果設定了 scraper）
                        if fg_scraper is not None:
                            try:
                                fg_data = fg_scraper.scrape(rn_int)
                                if fg_data:
                                    normalized_fg = {
                                        str(int(k)): v for k, v in fg_data.items()
                                        if str(k).isdigit() and isinstance(v, dict)
                                    }
                                    crud.upsert_kv(
                                        db, fg_snap_key, normalized_fg,
                                        f"SpeedPro FormGuide（{racedate_str} R{rn_int}）"
                                    )
                                    print(f"[OK ] {fg_snap_key} rows={len(normalized_fg)}")
                            except Exception as e:
                                print(f"[WARN] 爬取 FormGuide {fg_snap_key}: {e}")
                        continue

                    # ---------- 5d. 失敗 → 安排下次重試 ----------
                    minutes = _retry_minutes()
                    next_at = (now_hk + datetime.timedelta(minutes=minutes)).isoformat()
                    state = {
                        "done": False,
                        "attempt_count": attempt,
                        "last_attempt_at": now_hk.isoformat(),
                        "next_retry_at": next_at,
                        "last_error": str(reason),
                    }
                    crud.upsert_kv(
                        db, retry_key, state,
                        f"SpeedPro 重試狀態（{racedate_str} R{rn_int}）"
                    )
                    print(f"[RETRY] {racedate_str} R{rn_int} 失敗，原因={reason}；{minutes} 分後再試 (next={next_at})")

                else:
                    # ---------- 5e. 只有 FormGuide 要爬 (Energy 關閉) ----------
                    if fg_scraper is not None:
                        fg_cfg = crud.get_kv(db, fg_snap_key)
                        needs_fg = (not fg_cfg) or (not isinstance(fg_cfg.value, dict)) or (not fg_cfg.value)
                        if (not needs_fg) and isinstance(fg_cfg.value, dict):
                            needs_fg = not _is_formguide_payload_done(fg_cfg.value)
                        if force_fg or needs_fg or force_all:
                            any_work = True
                            try:
                                fg_data = fg_scraper.scrape(rn_int)
                                if fg_data:
                                    normalized_fg = {
                                        str(int(k)): v for k, v in fg_data.items()
                                        if str(k).isdigit() and isinstance(v, dict)
                                    }
                                    crud.upsert_kv(
                                        db, fg_snap_key, normalized_fg,
                                        f"SpeedPro FormGuide（{racedate_str} R{rn_int}）"
                                    )
                                    print(f"[OK ] {fg_snap_key} rows={len(normalized_fg)}")
                            except Exception as e:
                                print(f"[ERR] 爬取 FormGuide {fg_snap_key}: {e}")

        if not any_work:
            print(f"[INFO] 所有日期 {racedates} 的場次皆已完成爬取或未到重試時間，本次無需執行任何作業。")
        print("[INFO] SpeedPro 自動爬取作業完成。")

    finally:
        _release_lock(db)
        try:
            db.close()
        except Exception:
            pass
    print("=" * 60)


if __name__ == "__main__":
    main()
