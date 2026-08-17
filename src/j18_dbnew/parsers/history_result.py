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
    brandNum: Optional[str] = Field(None, description="烙号")
    horse_name: str = Field(description="马匹名称")
    horse_no: str = Field(description="马号")
    finish_order: str = Field(description="名次")
    final_time: str = Field(description="总时间")
    jockey: str = Field(description="骑师")
    trainer: str = Field(description="练马师")
    win_probability: Optional[float] = Field(None, description="独赢赔率")
    pla_probability: Optional[float] = Field(None, description="位置赔率")
    sections: Optional[Dict[str, Any]] = Field(None, description="段速信息 (解析后的 Dict)")
    
    # 新增马匹细节栏位
    barDraw: Optional[str] = Field(None, description="档位")
    handicapWeight: Optional[str] = Field(None, description="负磅")
    sceneWeight: Optional[str] = Field(None, description="排位体重")
    horseWeight: Optional[str] = Field(None, description="体重增减")
    lastSixRun: Optional[str] = Field(None, description="近六次赛绩")
    runnerRating: Optional[str] = Field(None, description="马匹评分")
    age: Optional[str] = Field(None, description="年龄")
    sex: Optional[str] = Field(None, description="性别")
    gear: Optional[str] = Field(None, description="配备")
    importType: Optional[str] = Field(None, description="进口类别")
    scratched: bool = Field(False, description="是否退出")

class CanonicalRace(BaseModel):
    """赛事场次实体"""
    racing_date: str = Field(description="赛事日期 (YYYY-MM-DD)")
    race_num: int = Field(description="场次号")
    title: str = Field(description="赛事标题")
    race_name: str = Field(description="赛事名称")
    race_class: str = Field(description="班次")
    distance: str = Field(description="途程")
    rating: str = Field(description="评分区间")
    course: str = Field(description="场地")
    track: str = Field(description="赛道")
    ground: str = Field(description="场地状况")
    
    # 新增赛事 JSON 栏位
    times: Optional[List[str]] = Field(None, description="赛事总分段时间")
    sectional_times: Optional[List[Any]] = Field(None, description="赛事每段明细时间与 split")
    scene_result_payout: Optional[Dict[str, Any]] = Field(None, description="派彩结果")
    famous_like_count: Optional[Dict[str, Any]] = Field(None, description="名家按赞与推介数据")
    promote: Optional[Dict[str, Any]] = Field(None, description="走势推介资料")
    discount4: Optional[Dict[str, Any]] = Field(None, description="赔率折让与异动分析")
    
    horses: List[CanonicalHorse] = Field(default_factory=list, description="该场次的马匹成绩")


class HistoryResultParser:
    """解析 historyResult JSON 为 Canonical 结构的解析器"""
    
    @staticmethod
    def parse(payload) -> List["CanonicalRace"]:
        """
        解析 historyResult JSON Payload
        兼容三种格式：
          1) 字典外层：{"data": {"racing_date": ..., "data": {"races": {...}}}}
          2) 列表外层 (单个/多个日期合并列表)：[ {字典外层1}, {字典外层2}, ... ]
          3) payload 本身就是内层 {"racing_date": ..., "data": {...}}
        :param payload: JSON 字典或列表
        :return: CanonicalRace 列表
        """
        all_races: List[CanonicalRace] = []

        # 情况 2：外层是列表，递归逐项解析
        if isinstance(payload, list):
            for item in payload:
                all_races.extend(HistoryResultParser.parse(item))
            return all_races

        # 仅接受字典
        if not isinstance(payload, dict):
            return []

        # 情况 1/3：定位 {racing_date: ..., data: {...}} 层
        if "data" in payload and isinstance(payload.get("data"), dict) and ("racing_date" in payload.get("data", {})):
            # 情况 1：payload = {"data": {racing_date + races data}, ...} -> 剥一层
            inner_root = payload.get("data", {})
        elif "racing_date" in payload or ("data" in payload and isinstance(payload.get("data"), dict) and "races" in payload.get("data", {})):
            # 情况 3：payload 本身已经是 {racing_date + data}
            inner_root = payload
        else:
            return []

        racing_date = str(inner_root.get("racing_date", ""))
        inner_data = inner_root.get("data", {})
        if not isinstance(inner_data, dict):
            return []

        races_dict = inner_data.get("races", {})
        if not isinstance(races_dict, dict):
            return []

        for race_key, race_obj in races_dict.items():
            if not isinstance(race_obj, dict):
                continue
            detail = race_obj.get("detail", {})
            if not isinstance(detail, dict):
                continue

            race_num = detail.get("race_num", 0)

            canonical_race = CanonicalRace(
                racing_date=racing_date,
                race_num=race_num,
                title=detail.get("title", ""),
                race_name=detail.get("race_name", ""),
                race_class=detail.get("class", ""),
                distance=detail.get("distance", ""),
                rating=detail.get("rating", ""),
                course=detail.get("course", ""),
                track=detail.get("track", ""),
                ground=detail.get("ground", ""),
                times=detail.get("times", []),
                sectional_times=detail.get("sectional_times", []),
                scene_result_payout=race_obj.get("scene_result_payout", {}),
                famous_like_count=race_obj.get("famous_like_count", {}),
                promote=race_obj.get("promote", {}),
                discount4=race_obj.get("discount4", {})
            )

            horses_list = detail.get("horses", [])
            if not isinstance(horses_list, list):
                horses_list = []
            for h in horses_list:
                if not isinstance(h, dict):
                    continue
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

                sections_data = h.get("sections")

                canonical_horse = CanonicalHorse(
                    racing_date=racing_date,
                    race_num=race_num,
                    horse_id=str(h.get("horse_id", "")),
                    brandNum=str(h.get("brandNum", "")),
                    horse_name=str(h.get("horse_name", "")),
                    horse_no=str(h.get("horse_no", "")),
                    finish_order=str(h.get("finish_order", "")),
                    final_time=str(h.get("final_time", "")),
                    jockey=str(h.get("jockeyName", "")),
                    trainer=str(h.get("trainerName", "")),
                    win_probability=win_prob,
                    pla_probability=pla_prob,
                    sections=sections_data,
                    barDraw=str(h.get("barDraw", "")),
                    handicapWeight=str(h.get("handicapWeight", "")),
                    sceneWeight=str(h.get("sceneWeight", "")),
                    horseWeight=str(h.get("horseWeight", "")),
                    lastSixRun=str(h.get("lastSixRun", "")),
                    runnerRating=str(h.get("runnerRating", "")),
                    age=str(h.get("age", "")),
                    sex=str(h.get("sex", "")),
                    gear=str(h.get("gear", "")),
                    importType=str(h.get("importType", "")),
                    scratched=bool(h.get("scratched", False))
                )
                canonical_race.horses.append(canonical_horse)

            all_races.append(canonical_race)

        return all_races
