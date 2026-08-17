"""
SpeedPro 能量評分爬取器 (SpeedPro Energy Scraper)

資料來源：HKJC SpeedPro 頁面的 sg_race_{race_no}.json 端點
端點 URL 不可寫死，必須從環境變數 SPEEDPRO_ENERGY_URL_TEMPLATE 讀取
模板範例：https://consvc.hkjc.com/-/media/Sites/JCRW/SpeedPro/current/sg_race_{}
        （其中 {} 會替換為賽事場次編號 race_no）
"""

import os
import json
from typing import Dict, Any

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


class SpeedProEnergyScraper:
    """爬取 SpeedPro sg_race_*.json 中的能量評分 (Energy) 與狀態評級 (Status)"""

    def __init__(self):
        # 嚴禁在程式碼中寫死 URL，必須透過環境變數設定
        self.base_url_template = os.getenv(
            "SPEEDPRO_ENERGY_URL_TEMPLATE",
            ""
        )

    def scrape(self, race_no: int) -> Dict[int, Dict[str, Any]]:
        """
        根據場次編號爬取 SpeedPro 能量評分
        :param race_no: 場次號 (1, 2, 3, ...)
        :return: { horse_no(int) -> {energy_required, energy_assess, status_rating, energy_diff} }
        """
        if not self.base_url_template:
            # 環境變數未設定，直接返回空，讓 Cron Job 判斷無資料跳過
            print("[WARN] SPEEDPRO_ENERGY_URL_TEMPLATE 環境變數未設定，跳過 SpeedPro Energy 爬取")
            return {}

        url = self.base_url_template.format(int(race_no))
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://racing.hkjc.com/"
                },
                timeout=30,
            )
        except Exception as e:
            print(f"[WARN] SpeedPro Energy 請求失敗 R{race_no}: {e}")
            return {}

        # HTTP 狀態不為 200 代表該場次無資料或 API 掛了
        if r.status_code != 200:
            return {}

        # HKJC 的 JSON 通常是 utf-8-sig (帶 BOM)，需要特別處理
        try:
            r.encoding = "utf-8-sig"
            data = r.json()
        except Exception:
            try:
                data = json.loads(r.content.decode("utf-8-sig"))
            except Exception:
                return {}

        out: Dict[int, Dict[str, Any]] = {}

        # 常見結構：{"zh-hk": {"SpeedPRO": [runner1, runner2, ...]}}
        if not isinstance(data, dict):
            return out
        zh = data.get("zh-hk") or data.get("zhHK") or data.get("zh") or data
        if not isinstance(zh, dict) or "SpeedPRO" not in zh:
            # 兼容直接外層就是 SpeedPRO 陣列的格式
            runners = data.get("SpeedPRO") if isinstance(data.get("SpeedPRO"), list) else None
            if not runners:
                return out
        else:
            runners = zh.get("SpeedPRO")

        if not isinstance(runners, list):
            return out

        for runner in runners:
            if not isinstance(runner, dict):
                continue
            try:
                horse_no = int(runner.get("runnernumber", runner.get("runnerno", 0)))
            except (ValueError, TypeError):
                continue
            if not horse_no:
                continue

            # 解析 A: 所需能量 Energy Required
            energy_req_str = _pick_text(runner, ["energyrequired", "energy_required", "req_energy"])
            try:
                energy_required = float(energy_req_str) if energy_req_str else None
            except (ValueError, TypeError):
                energy_required = None

            # 解析 B: SpeedPro 能量評分 Energy Assess
            energy_assess_str = _pick_text(runner, ["speedproenergy", "speedpro_energy", "assess_energy"])
            try:
                energy_assess = float(energy_assess_str) if energy_assess_str else None
            except (ValueError, TypeError):
                energy_assess = None

            # 解析狀態評級 (Fitness/Status Rating, 0~3 個大拇指)
            fitness_str = _pick_text(runner, ["fitnessrating", "fitness_rating", "statusrating", "status_rating"])
            try:
                status_rating = int(fitness_str) if fitness_str and fitness_str.isdigit() else None
            except (ValueError, TypeError):
                status_rating = None

            # B - A 差值（正數代表馬匹狀態超過該場次需求）
            energy_diff = None
            if energy_required is not None and energy_assess is not None:
                try:
                    energy_diff = float(energy_assess) - float(energy_required)
                except Exception:
                    energy_diff = None

            out[horse_no] = {
                "energy_required": energy_required,
                "status_rating": status_rating,
                "energy_assess": energy_assess,
                "energy_diff": energy_diff,
            }

        return out
