from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, Boolean, JSON
from sqlalchemy.orm import relationship
from .database import Base

class RaceModel(Base):
    """
    對應 PostgreSQL 中的賽事場次表 (V2)
    """
    __tablename__ = "races_v2"

    id = Column(Integer, primary_key=True, index=True)
    racing_date = Column(String, index=True, nullable=False) # 賽事日期 YYYY-MM-DD
    race_num = Column(Integer, nullable=False)               # 場次號
    title = Column(String, nullable=True)                    # 賽事標題 (如: 第 1 場)
    race_name = Column(String, nullable=True)                # 賽事名稱 (如: 摩法神采讓賽)
    race_class = Column(String, nullable=True)               # 班次
    distance = Column(String, nullable=True)                 # 途程
    rating = Column(String, nullable=True)                   # 評分區間
    course = Column(String, nullable=True)                   # 場地
    track = Column(String, nullable=True)                    # 賽道
    ground = Column(String, nullable=True)                   # 場地狀況

    # V2 新增的 JSON 欄位
    times = Column(JSON, nullable=True)                      # 賽事總分段時間字串陣列
    sectional_times = Column(JSON, nullable=True)            # 賽事每段明細時間與 split
    scene_result_payout = Column(JSON, nullable=True)        # 派彩結果
    famous_like_count = Column(JSON, nullable=True)          # 名家按讚與推介數據
    promote = Column(JSON, nullable=True)                    # 走勢推介資料
    discount4 = Column(JSON, nullable=True)                  # 賠率折讓與異動分析

    # 建立與馬匹的關聯，當賽事被刪除時，關聯的馬匹也會被刪除 (cascade)
    horses = relationship("HorseModel", back_populates="race", cascade="all, delete-orphan")

    # 確保同一天同一場次不會重複建立
    __table_args__ = (
        UniqueConstraint('racing_date', 'race_num', name='_racing_date_race_num_uc_v2'),
    )


class HorseModel(Base):
    """
    對應 PostgreSQL 中的馬匹成績表 (V2)
    """
    __tablename__ = "horses_v2"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races_v2.id"), nullable=False) # 外鍵關聯到賽事表
    
    horse_id = Column(String, index=True, nullable=True)     # 馬匹唯一代碼
    brandNum = Column(String, nullable=True)                 # 烙號
    horse_name = Column(String, nullable=True)               # 馬匹名稱
    horse_no = Column(String, nullable=True)                 # 馬號
    finish_order = Column(String, nullable=True)             # 名次
    final_time = Column(String, nullable=True)               # 總時間
    sections = Column(JSON, nullable=True)                   # 分段時間與排名 (JSON)
    win_probability = Column(Float, nullable=True)           # 獨贏賠率
    pla_probability = Column(Float, nullable=True)           # 位置賠率
    jockey = Column(String, nullable=True)                   # 騎師
    trainer = Column(String, nullable=True)                  # 練馬師

    # V2 新增的馬匹細節欄位
    barDraw = Column(String, nullable=True)                  # 檔位
    handicapWeight = Column(String, nullable=True)           # 負磅
    sceneWeight = Column(String, nullable=True)              # 排位體重
    horseWeight = Column(String, nullable=True)              # 體重增減
    lastSixRun = Column(String, nullable=True)               # 近六次賽績
    runnerRating = Column(String, nullable=True)             # 馬匹評分
    age = Column(String, nullable=True)                      # 年齡
    sex = Column(String, nullable=True)                      # 性別
    gear = Column(String, nullable=True)                     # 配備
    importType = Column(String, nullable=True)               # 進口類別
    scratched = Column(Boolean, nullable=True, default=False)# 是否退出

    # 建立與賽事的關聯
    race = relationship("RaceModel", back_populates="horses")
