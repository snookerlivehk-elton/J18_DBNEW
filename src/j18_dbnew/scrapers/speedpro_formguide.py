"""
SpeedPro 賽績指引/近績爬取器 (SpeedPro FormGuide Scraper)

資料來源：HKJC SpeedPro 頁面的 fg_race_{race_no}.json 端點
端點 URL 不可寫死，必須從環境變數 SPEEDPRO_FORMGUIDE_URL_TEMPLATE 讀取
模板範例：https://consvc.hkjc.com/-/media/Sites/JCRW/SpeedPro/current/fg_race_{}
        （其中 {} 會替換為賽事場次編號 race_no）
"""

import os
import json
from typing import Dict, Any, List

import requests


def _pick_text(obj: Dict[str, Any], keys) -> str:
    """從多個候選 key 中，撈出第一個有意義的文字值（去掉 NA/空值）"""
    if not isinstance(obj, dict):
        return ""
    for k in list(keys or []):
        v = obj.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in ("na", "n/a", "null", "-"):
            return s
    return ""


class SpeedProFormGuideScraper:
    """爬取 SpeedPro fg_race_*.json 中的馬匹評論、近績記錄 (FormGuide)"""

    def __init__(self):
        # 嚴禁在程式碼中寫死 URL，必須透過環境變數設定
        self.base_url_template = os.getenv(
            "SPEEDPRO_FORMGUIDE_URL_TEMPLATE",
            ""
        )

    def scrape(self, race_no: int) -> Dict[int, Dict[str, Any]]:
        """
        根據場次編號爬取 SpeedPro FormGuide
        :param race_no: 場次號 (1, 2, 3, ...)
        :return: { horse_no(int) -> {horse_name, intro_comment, trial_comment, history:[...] } }
        """
        if not self.base_url_template:
            print("[WARN] SPEEDPRO_FORMGUIDE_URL_TEMPLATE 環境變數未設定，跳過 FormGuide 爬取")
            return {}

        url = self.base_url_template.format(int(race_no))
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://racing.hkjc.com/zh-hk/local/info/speedpro/speedguide"
                },
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] SpeedPro FormGuide 請求失敗 R{race_no}: {e}")
            return {}

        if r.status_code != 200:
            return {}

        try:
            r.encoding = "utf-8-sig"
            data = r.json()
        except Exception:
            try:
                data = json.loads(r.content.decode("utf-8-sig"))
            except Exception:
                return {}

        out: Dict[int, Dict[str, Any]] = {}

        if not isinstance(data, dict) or "SpeedPRO" not in data:
            return out

        runners = data["SpeedPRO"]
        if not isinstance(runners, list):
            return out

        for runner in runners:
            if not isinstance(runner, dict):
                continue
            try:
                horse_no = int(runner.get("runnerno", runner.get("runnernumber", 0)))
            except (ValueError, TypeError):
                continue
            if not horse_no:
                continue

            # 解析近六次賽績 (runnerrecords)
            records = runner.get("runnerrecords", [])
            parsed_records: List[Dict[str, Any]] = []
            if isinstance(records, list):
                for rec in records[:6]:  # 只保留最近 6 筆，節省儲存空間
                    if not isinstance(rec, dict):
                        continue
                    parsed_records.append({
                        "racedate": str(rec.get("racedate", "")).strip(),
                        "dist": str(rec.get("dist", "")).strip(),
                        "going": str(rec.get("going_chi", rec.get("going", ""))).strip(),
                        "fp": str(rec.get("fp", "")).strip(),
                        "pace": str(rec.get("pace_chi", rec.get("pace", ""))).strip(),
                        "wide": str(rec.get("wide", "")).strip(),
                        "comments": str(rec.get("comments_chi", rec.get("comments", ""))).strip(),
                        "incident": str(rec.get("incident_chi", rec.get("incident", ""))).strip(),
                        "health": str(rec.get("healthissue_chi", rec.get("health", ""))).strip(),
                    })

            # 解析馬匹介紹評論 (多種可能 key 兼容)
            intro_comment = _pick_text(
                runner,
                [
                    "comments_chi", "comment_chi", "remark_chi", "profile_chi",
                    "intro_chi", "introduction_chi", "horseintro_chi",
                ],
            )
            # 解析試閘/操練評論
            trial_comment = _pick_text(
                runner,
                [
                    "trialcomment_chi", "trialcomments_chi", "trial_chi", "workoutcomment_chi",
                ],
            )
            # 如果沒有單獨的 trial_comment，但 intro_comment 提到試閘，就把它當成 trial_comment
            if not trial_comment and ("試閘" in intro_comment or "試闸" in intro_comment):
                trial_comment = intro_comment

            horse_name = _pick_text(runner, ["horse_chi", "horsename_chi", "horseName", "horse_name"])

            out[horse_no] = {
                "horse_name": horse_name,
                "history": parsed_records,
                "intro_comment": intro_comment,
                "trial_comment": trial_comment,
            }

        return out
