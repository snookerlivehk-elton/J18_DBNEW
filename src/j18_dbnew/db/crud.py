from sqlalchemy.orm import Session
from typing import List

from . import models
from ..parsers.history_result import CanonicalRace, CanonicalHorse

def sync_races_to_db(db: Session, canonical_races: List[CanonicalRace], racing_date: str):
    """
    將解析後的 Canonical 賽事資料同步寫入資料庫
    採用「先刪除該日舊資料，再寫入新資料」的策略，以確保資料一致性並支援重複執行 (Idempotent)
    """
    if not canonical_races:
        return 0

    # 1. 刪除該日期已存在的賽事 (由於設定了 cascade="all, delete-orphan"，關聯的馬匹也會一併被刪除)
    db.query(models.RaceModel).filter(models.RaceModel.racing_date == racing_date).delete()
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
            ground=c_race.ground
        )
        
        # 建立 SQLAlchemy Horse 物件並加入 Race
        for c_horse in c_race.horses:
            db_horse = models.HorseModel(
                horse_id=c_horse.horse_id,
                horse_name=c_horse.horse_name,
                horse_no=c_horse.horse_no,
                finish_order=c_horse.finish_order,
                final_time=c_horse.final_time,
                jockey=c_horse.jockey,
                trainer=c_horse.trainer,
                win_probability=c_horse.win_probability,
                pla_probability=c_horse.pla_probability
            )
            db_race.horses.append(db_horse)
            
        # 將 Race 加入 Session
        db.add(db_race)
        races_added += 1

    # 3. 提交所有變更
    db.commit()
    
    return races_added
