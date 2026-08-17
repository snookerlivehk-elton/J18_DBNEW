# historyResult to Canonical Spec

此文件定義了如何將 `historyResult` 的 JSON Payload 解析為資料庫的 Canonical Model。

## 1. 源資料 (Source Payload)
`historyResult` API 返回單日賽事資料。其核心結構如下：
- `data.racing_date`: 賽事日期 (YYYY-MM-DD)
- `data.data.races`: 字典，Key 為場次號 (`race_num`)。
  - `[race_num].detail`: 該場次的詳細資訊。
    - `race_num`: 場次號
    - `title`: 賽事標題
    - `class`: 班次
    - `distance`: 途程 (例如 1650米)
    - `course`: 場地 (草地 / 泥地)
    - `track`: 賽道 (例如 "C" 賽道)
    - `horses`: 馬匹結果陣列。

## 2. Canonical Model

### 2.1 CanonicalRace (賽事場次表)
- `racing_date` (String): 賽事日期，如 `2026-07-15`
- `race_num` (Integer): 場次號，如 `1`
- `title` (String): 賽事標題
- `race_class` (String): 班次，如 `第四班`
- `distance` (String): 途程，如 `1650米`
- `rating` (String): 評分區間，如 `40-0`
- `course` (String): 場地，如 `草地`
- `track` (String): 賽道，如 `"C" 賽道`
- `ground` (String): 場地狀況，如 `好地`

### 2.2 CanonicalHorse (馬匹成績表)
- `racing_date` (String): 關聯賽事日期
- `race_num` (Integer): 關聯場次號
- `horse_id` (String): 馬匹唯一代碼，如 `HK_2023_J080`
- `horse_name` (String): 馬匹名稱
- `horse_no` (String): 馬號 (排位)
- `finish_order` (String): 名次，如 `1`
- `final_time` (String): 總時間，如 `1:40.05`
- `jockey` (String): 騎師
- `trainer` (String): 練馬師
- `win_probability` (Float): 獨贏賠率 (來自 win_probability)
- `pla_probability` (Float): 位置賠率 (來自 pla_probability)

## 3. 解析邏輯
1. 提取外層的 `data.racing_date`。
2. 遍歷 `data.data.races` 提取每場賽事的 `detail`。
3. 將 `detail` 映射為 `CanonicalRace`。
4. 遍歷 `detail.horses` 陣列，映射每一項為 `CanonicalHorse`，並補充外鍵 `racing_date` 和 `race_num`。
