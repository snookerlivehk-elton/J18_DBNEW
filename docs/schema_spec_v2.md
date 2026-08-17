# J18_DBNEW 資料庫與解析器開發手冊 (Schema Spec V2)

本手冊定義了從 `historyResult` API 提取所有完整數據並寫入關聯式資料庫的綱要結構。

## 1. 架構變更策略
由於舊的 `races` 與 `horses` 資料表缺少大量欄位，為避免在 Railway 上產生資料庫 Schema 遷移 (Migration) 衝突，本次升級將建立全新的資料表：
- 賽事表：`races_v2`
- 馬匹成績表：`horses_v2`

應用程式啟動時會自動建立這兩張新表，舊表可保留作為備份或後續手動刪除。

## 2. 資料表定義 (SQLAlchemy Models)

### 2.1 賽事表 (`races_v2`)
記錄賽事層級的基本資訊、整體時間與派彩/預測資料。

| 欄位名稱 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 主鍵 |
| `racing_date` | String | 賽事日期 (YYYY-MM-DD) |
| `race_num` | Integer | 場次號 |
| `title` | String | 賽事標題 (如：第 1 場) |
| `race_name` | String | 賽事名稱 (如：摩法神采讓賽) |
| `race_class` | String | 班次 |
| `distance` | String | 途程 |
| `rating` | String | 評分區間 |
| `course` | String | 場地 |
| `track` | String | 賽道 |
| `ground` | String | 場地狀況 |
| `times` | JSON | 賽事總分段時間字串陣列 |
| `sectional_times` | JSON | 賽事每段明細時間與 split |
| `scene_result_payout` | JSON | 派彩結果 (各玩法勝出組合與派彩) |
| `famous_like_count` | JSON | 名家按讚與推介數據 |
| `promote` | JSON | 走勢推介資料 |
| `discount4` | JSON | 賠率折讓與異動分析 |

### 2.2 馬匹成績表 (`horses_v2`)
記錄個別馬匹的賽後成績與詳細靜態/動態數據。

| 欄位名稱 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 主鍵 |
| `race_id` | Integer (FK) | 關聯 `races_v2.id` |
| `horse_id` | String | 馬匹唯一代碼 (如：HK_2023_J080) |
| `brandNum` | String | 烙號 (如：J080) |
| `horse_name` | String | 馬匹名稱 |
| `horse_no` | String | 馬號 |
| `finish_order` | String | 最終名次 |
| `final_time` | String | 完成時間 |
| `sections` | JSON | 分段時間與排名 (包含各段 position, distance, sectional_time) |
| `win_probability` | Float | 獨贏賠率 |
| `pla_probability` | Float | 位置賠率 |
| `jockey` | String | 騎師 |
| `trainer` | String | 練馬師 |
| `barDraw` | String | 檔位 |
| `handicapWeight` | String | 負磅 |
| `sceneWeight` | String | 排位體重 |
| `horseWeight` | String | 體重增減 |
| `lastSixRun` | String | 近六次賽績 |
| `runnerRating` | String | 馬匹評分 |
| `age` | String | 年齡 |
| `sex` | String | 性別 |
| `gear` | String | 配備 |
| `importType` | String | 進口類別 |
| `scratched` | Boolean| 是否退出 |

## 3. 解析器映射規則 (Parser Mapping)
`HistoryResultParser.parse` 必須攔截並安全地提取上述 JSON 節點。對於 JSON 型態的欄位 (如 `times`, `sections`, `scene_result_payout`)，Pydantic 模型應定義為 `Optional[Dict[str, Any]]` 或 `Optional[List[Any]]`，並在存入 SQLAlchemy 時由底層自動序列化或透過 `json.dumps()` 處理。

## 4. UI 呈現更新
`index.html` 將升級顯示：
1. 賽事標頭追加：總完成時間與派彩摘要入口 (可選)。
2. 馬匹列表追加：檔位、負磅、排位體重、體重增減、馬匹評分、近六次賽績、配備、分段走位詳情。
