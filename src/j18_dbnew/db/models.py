from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base

class RaceModel(Base):
    """
    對應 PostgreSQL 中的賽事場次表
    """
    __tablename__ = "races"

    id = Column(Integer, primary_key=True, index=True)
    racing_date = Column(String, index=True, nullable=False) # 賽事日期 YYYY-MM-DD
    race_num = Column(Integer, nullable=False)               # 場次號
    title = Column(String, nullable=True)                    # 賽事標題
    race_class = Column(String, nullable=True)               # 班次
    distance = Column(String, nullable=True)                 # 途程
    rating = Column(String, nullable=True)                   # 評分區間
    course = Column(String, nullable=True)                   # 場地
    track = Column(String, nullable=True)                    # 賽道
    ground = Column(String, nullable=True)                   # 場地狀況

    # 建立與馬匹的關聯，當賽事被刪除時，關聯的馬匹也會被刪除 (cascade)
    horses = relationship("HorseModel", back_populates="race", cascade="all, delete-orphan")

    # 確保同一天同一場次不會重複建立
    __table_args__ = (
        UniqueConstraint('racing_date', 'race_num', name='_racing_date_race_num_uc'),
    )


class HorseModel(Base):
    """
    對應 PostgreSQL 中的馬匹成績表
    """
    __tablename__ = "horses"

    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False) # 外鍵關聯到賽事表
    
    horse_id = Column(String, index=True, nullable=True)     # 馬匹唯一代碼
    horse_name = Column(String, nullable=True)               # 馬匹名稱
    horse_no = Column(String, nullable=True)                 # 馬號
    finish_order = Column(String, nullable=True)             # 名次
    final_time = Column(String, nullable=True)               # 總時間
    jockey = Column(String, nullable=True)                   # 騎師
    trainer = Column(String, nullable=True)                  # 練馬師
    win_probability = Column(Float, nullable=True)           # 獨贏賠率
    pla_probability = Column(Float, nullable=True)           # 位置賠率

    # 建立與賽事的關聯
    race = relationship("RaceModel", back_populates="horses")
