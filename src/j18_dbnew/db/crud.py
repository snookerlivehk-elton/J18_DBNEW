from sqlalchemy.orm import Session
from typing import List

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
