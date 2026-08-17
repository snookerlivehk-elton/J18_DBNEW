from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Canonical Models (数据库结构模型)
# ---------------------------------------------------------

class CanonicalHorse(BaseModel):
    """马匹成绩实体"""
    racing_date: str = Field(description="赛事日期 (YYYY-MM-DD)")
    race_num: int = Field(description="场次号")
    horse_id: str = Field(description="马匹ID")
    horse_name: str = Field(description="马匹名称")
    horse_no: str = Field(description="马号")
    finish_order: str = Field(description="名次")
    final_time: str = Field(description="总时间")
    jockey: str = Field(description="骑师")
    trainer: str = Field(description="练马师")
    win_probability: Optional[float] = Field(None, description="独赢赔率")
    pla_probability: Optional[float] = Field(None, description="位置赔率")

class CanonicalRace(BaseModel):
    """赛事场次实体"""
    racing_date: str = Field(description="赛事日期 (YYYY-MM-DD)")
    race_num: int = Field(description="场次号")
    title: str = Field(description="赛事标题")
    race_class: str = Field(description="班次")
    distance: str = Field(description="途程")
    rating: str = Field(description="评分区间")
    course: str = Field(description="场地")
    track: str = Field(description="赛道")
    ground: str = Field(description="场地状况")
    
    horses: List[CanonicalHorse] = Field(default_factory=list, description="该场次的马匹成绩")


class HistoryResultParser:
    """解析 historyResult JSON 为 Canonical 结构的解析器"""
    
    @staticmethod
    def parse(payload: Dict[str, Any]) -> List[CanonicalRace]:
        """
        解析 historyResult JSON Payload
        :param payload: JSON 字典
        :return: CanonicalRace 列表
        """
        if "data" not in payload:
            return []
            
        outer_data = payload.get("data", {})
        racing_date = outer_data.get("racing_date", "")
        
        inner_data = outer_data.get("data", {})
        if not inner_data:
            return []
            
        races_dict = inner_data.get("races", {})
        
        canonical_races = []
        
        for race_key, race_obj in races_dict.items():
            detail = race_obj.get("detail", {})
            if not detail:
                continue
                
            race_num = detail.get("race_num", 0)
            
            canonical_race = CanonicalRace(
                racing_date=racing_date,
                race_num=race_num,
                title=detail.get("title", ""),
                race_class=detail.get("class", ""),
                distance=detail.get("distance", ""),
                rating=detail.get("rating", ""),
                course=detail.get("course", ""),
                track=detail.get("track", ""),
                ground=detail.get("ground", "")
            )
            
            horses_list = detail.get("horses", [])
            for h in horses_list:
                # 尝试转换赔率为 float，用于统一规范化格式
                win_prob = h.get("win_probability")
                try:
                    win_prob = float(win_prob) if win_prob else None
                except ValueError:
                    win_prob = None
                    
                pla_prob = h.get("pla_probability")
                try:
                    pla_prob = float(pla_prob) if pla_prob else None
                except ValueError:
                    pla_prob = None

                canonical_horse = CanonicalHorse(
                    racing_date=racing_date,
                    race_num=race_num,
                    horse_id=h.get("horse_id", ""),
                    horse_name=h.get("horse_name", ""),
                    horse_no=h.get("horse_no", ""),
                    finish_order=h.get("finish_order", ""),
                    final_time=h.get("final_time", ""),
                    jockey=h.get("jockeyName", ""),
                    trainer=h.get("trainerName", ""),
                    win_probability=win_prob,
                    pla_probability=pla_prob
                )
                canonical_race.horses.append(canonical_horse)
                
            canonical_races.append(canonical_race)
            
        return canonical_races
