import os
import sys
import json
import argparse

# 将 src 目录加入 PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from j18_dbnew.parsers.history_result import HistoryResultParser

def main():
    parser = argparse.ArgumentParser(description="测试 historyResult 到 Canonical 格式的解析")
    parser.add_argument("--input", required=True, help="输入的 JSON 文件路径")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"错误：找不到文件 {args.input}")
        sys.exit(1)
        
    with open(args.input, 'r', encoding='utf-8') as f:
        payload = json.load(f)
        
    print(f"成功读取 JSON，开始解析...")
    
    canonical_races = HistoryResultParser.parse(payload)
    
    if not canonical_races:
        print("未解析到任何赛事数据。")
        sys.exit(0)
        
    print(f"成功解析 {len(canonical_races)} 场赛事。")
    
    # 打印第一场赛事作为示例
    first_race = canonical_races[0]
    print("\n--- 示例：第一场赛事 ---")
    print(f"日期: {first_race.racing_date}")
    print(f"场次: 第 {first_race.race_num} 场")
    print(f"标题: {first_race.title}")
    print(f"途程: {first_race.distance}")
    print(f"马匹数量: {len(first_race.horses)}")
    
    print("\n前三名马匹:")
    for horse in first_race.horses[:3]:
        print(f"  名次: {horse.finish_order} | 马号: {horse.horse_no} | 名称: {horse.horse_name} | 骑师: {horse.jockey} | 独赢赔率: {horse.win_probability}")

if __name__ == "__main__":
    main()
