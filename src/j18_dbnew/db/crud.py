from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional

from . import models
from ..parsers.history_result import CanonicalRace, CanonicalHorse

def sync_races_to_db(db: Session, canonical_races: List[CanonicalRace], racing_date: str = None):
    """
    將解析後的 Canonical 賽事資料同步寫入資料庫
    採用「先刪除該日舊資料，再寫入新資料」的策略，以確保資料一致性並支援重複執行 (Idempotent)

    racing_date 参数可选；若为 None，则根据传入的 canonical_races 内实际出现的日期去重后批量处理
    """
    if not canonical_races:
        return 0

    # 收集所有实际涉及的日期，确保跨日期批量导入时也能正确去重
    if racing_date:
        dates_to_clean = {racing_date}
    else:
        dates_to_clean = {r.racing_date for r in canonical_races if r.racing_date}

    # 1. 刪除涉及日期已存在的賽事 (由於設定了 cascade="all, delete-orphan"，關聯的馬匹也會一併被刪除)
    if dates_to_clean:
        db.query(models.RaceModel).filter(models.RaceModel.racing_date.in_(list(dates_to_clean))).delete(synchronize_session=False)
        db.commit()

    # 2. 準備寫入新的賽事與馬匹資料
    races_added = 0
    for c_race in canonical_races:
        # 建立 SQLAlchemy Race 物件
        db_race = models.RaceModel(
            racing_date=c_race.racing_date,
            race_num=c_race.race_num,
            title=c_race.title,
            race_class=c_race.race_class,
            distance=c_race.distance,
            rating=c_race.rating,
            course=c_race.course,
            track=c_race.track,
            ground=c_race.ground,
            times=getattr(c_race, "times", None),
            sectional_times=getattr(c_race, "sectional_times", None),
            scene_result_payout=getattr(c_race, "scene_result_payout", None),
            famous_like_count=getattr(c_race, "famous_like_count", None),
            promote=getattr(c_race, "promote", None),
            discount4=getattr(c_race, "discount4", None)
        )

        # 建立 SQLAlchemy Horse 物件並加入 Race
        for c_horse in c_race.horses:
            db_horse = models.HorseModel(
                horse_id=c_horse.horse_id,
                brandNum=getattr(c_horse, "brandNum", ""),
                horse_name=c_horse.horse_name,
                horse_no=c_horse.horse_no,
                finish_order=c_horse.finish_order,
                final_time=c_horse.final_time,
                jockey=c_horse.jockey,
                trainer=c_horse.trainer,
                win_probability=c_horse.win_probability,
                pla_probability=c_horse.pla_probability,
                sections=getattr(c_horse, "sections", None),
                barDraw=getattr(c_horse, "barDraw", ""),
                handicapWeight=getattr(c_horse, "handicapWeight", ""),
                sceneWeight=getattr(c_horse, "sceneWeight", ""),
                horseWeight=getattr(c_horse, "horseWeight", ""),
                lastSixRun=getattr(c_horse, "lastSixRun", ""),
                runnerRating=getattr(c_horse, "runnerRating", ""),
                age=getattr(c_horse, "age", ""),
                sex=getattr(c_horse, "sex", ""),
                gear=getattr(c_horse, "gear", ""),
                importType=getattr(c_horse, "importType", ""),
                scratched=getattr(c_horse, "scratched", False)
            )
            db_race.horses.append(db_horse)

        # 將 Race 加入 Session
        db.add(db_race)
        races_added += 1

    # 3. 提交所有變更
    db.commit()

    return races_added

def get_sync_status(db: Session) -> Dict[str, Any]:
    """
    查詢資料庫中的同步狀態 (最早/最晚同步日期、總賽事數、總馬匹紀錄數)
    """
    min_date = db.query(func.min(models.RaceModel.racing_date)).scalar()
    max_date = db.query(func.max(models.RaceModel.racing_date)).scalar()
    total_races = db.query(func.count(models.RaceModel.id)).scalar() or 0
    total_horses = db.query(func.count(models.HorseModel.id)).scalar() or 0
    unique_days = db.query(func.count(func.distinct(models.RaceModel.racing_date))).scalar() or 0

    return {
        "earliest_date": min_date,
        "latest_date": max_date,
        "total_races": total_races,
        "total_horses": total_horses,
        "unique_days_synced": unique_days
    }


# ============================================================
# Key-Value Store 通用操作 (用於 SpeedPro 結果存儲 / 重複核對 / Cron 狀態)
# ============================================================

def _now_iso() -> str:
    """取得香港時間 (UTC+8) 現在的 ISO 字串，用於 timestamp 記錄"""
    import datetime
    utc_now = datetime.datetime.utcnow()
    hk_time = utc_now + datetime.timedelta(hours=8)
    return hk_time.isoformat()


def get_kv(db: Session, key: str) -> Optional[models.KVStoreModel]:
    """
    根據 key 查詢 KV 紀錄；若不存在返回 None
    """
    if not key:
        return None
    return db.query(models.KVStoreModel).filter(models.KVStoreModel.key == key).first()


def upsert_kv(db: Session, key: str, value: Any, description: str = None) -> models.KVStoreModel:
    """
    新增或更新 KV 紀錄 (Idempotent：重複呼叫只會更新 value 與 timestamp)
    """
    if not key:
        raise ValueError("upsert_kv: key 不能為空")
    now = _now_iso()
    exist = get_kv(db, key)
    if exist:
        exist.value = value
        exist.updated_at = now
        if description and not exist.description:
            exist.description = description
    else:
        exist = models.KVStoreModel(
            key=key,
            value=value,
            description=description,
            created_at=now,
            updated_at=now
        )
        db.add(exist)
    db.commit()
    db.refresh(exist)
    return exist


def delete_kv(db: Session, key: str) -> bool:
    """
    刪除指定 key 的 KV 紀錄；成功返回 True，不存在返回 False
    """
    if not key:
        return False
    exist = get_kv(db, key)
    if not exist:
        return False
    db.delete(exist)
    db.commit()
    return True


def list_race_nos_by_date(db: Session, racing_date: str) -> List[int]:
    """
    查詢指定日期 (YYYY-MM-DD) 在 races_v2 中所有已存在的賽事場次編號
    若當天沒有任何賽事，返回 [1..9] 的預設範圍（保守嘗試）
    """
    if not racing_date:
        return list(range(1, 10))
    rows = (
        db.query(models.RaceModel.race_num)
        .filter(models.RaceModel.racing_date == racing_date)
        .order_by(models.RaceModel.race_num.asc())
        .all()
    )
    out = []
    for (rn,) in rows:
        try:
            rn_int = int(rn or 0)
            if rn_int > 0:
                out.append(rn_int)
        except Exception:
            continue
    return out if out else list(range(1, 10))


def expected_horse_count(db: Session, racing_date: str, race_no: int) -> Optional[int]:
    """
    查詢指定日期+場次預期有多少匹馬（用於校驗 SpeedPro 爬取結果的完整性）
    若查不到該場次，返回 None
    """
    try:
        race = (
            db.query(models.RaceModel.id)
            .filter(models.RaceModel.racing_date == racing_date)
            .filter(models.RaceModel.race_num == int(race_no))
            .first()
        )
        if not race:
            return None
        cnt = db.query(models.HorseModel.id).filter(models.HorseModel.race_id == int(race[0])).count()
        return int(cnt) if cnt else None
    except Exception:
        return None
