# HKJC 歷史補充資料第一版實作清單

本清單根據 `docs/hkjc_history_data_development_manual.md` 與現有專案實際結構整理，目的是把手冊規格轉成可直接施工的第一版開發任務。

## 1. 實作目標

第一版實作目標如下：

- 以現有賽果資料庫為起點
- 建立馬匹歷史出賽索引
- 由歷史索引整理待抓場次清單
- 逐場抓取 HKJC 三個補充來源：
  - `競賽事件報告`
  - `沿路走勢評述`
  - `分段時間及位置`
- 將資料以唯一鍵去重後寫入資料庫
- 以 `race_fetch_registry` 追蹤來源級狀態

## 2. 實作原則

- 不破壞既有 `historyResult -> races_v2 / horses_v2` 主流程
- 新功能以擴充資料層方式接入
- 以場次為抓取與回填單位
- 逐來源獨立寫入與獨立標記狀態
- 已存在資料預設跳過，不重複寫入
- 分段資料固定 6 段輸出，不足段數補 `null`

## 3. 現有檔案落點

### 3.1 必改既有檔案

- `src/j18_dbnew/db/models.py`
- `src/j18_dbnew/db/crud.py`
- `main.py`

### 3.2 高機率新增檔案

- `src/j18_dbnew/parsers/horse_history.py`
- `src/j18_dbnew/parsers/incident_report.py`
- `src/j18_dbnew/parsers/running_comment.py`
- `src/j18_dbnew/parsers/sectional_time.py`
- `src/j18_dbnew/scrapers/horse_history.py`
- `src/j18_dbnew/scrapers/incident_report.py`
- `src/j18_dbnew/scrapers/running_comment.py`
- `src/j18_dbnew/scrapers/sectional_time.py`
- `scripts/backfill_hkjc_history.py`
- `scripts/cron_hkjc_history_fetch.py`

### 3.3 次高機率修改檔案

- `templates/index.html`
- `README.md`

## 4. Phase 2 對應施工項目：Schema 與 ORM

### 4.1 `models.py`

需新增以下 ORM model：

- `HorseRaceHistoryModel`
- `RaceSectionalSummaryModel`
- `HorseSectionalDetailModel`
- `HorseIncidentReportModel`
- `HorseRunningCommentModel`
- `RaceFetchRegistryModel`

### 4.2 唯一鍵與索引

需在 model 層加入唯一鍵或等效唯一索引：

- `horse_race_history`：`horse_id + race_date + race_no`
- `race_sectional_summary`：`race_date + race_no`
- `horse_sectional_detail`：`race_date + race_no + horse_id`
- `horse_incident_report`：`race_date + race_no + horse_id`
- `horse_running_comment`：`race_date + race_no + horse_id`
- `race_fetch_registry`：`race_date + race_no + source_type`

### 4.3 分段欄位

`race_sectional_summary` 需包含：

- `section_count`
- `race_finish_time`
- `race_cumulative_time_1` 到 `race_cumulative_time_6`
- `race_section_time_1` 到 `race_section_time_6`

`horse_sectional_detail` 需包含：

- `finish_position`
- `finish_time`
- `section_count`
- `horse_position_1` 到 `horse_position_6`
- `horse_distance_from_leader_1` 到 `horse_distance_from_leader_6`
- `horse_section_time_1` 到 `horse_section_time_6`
- `horse_section_rank_1` 到 `horse_section_rank_6`
- `horse_split_time_1a` 到 `horse_split_time_6b`

## 5. Phase 2 對應施工項目：CRUD 與資料層

### 5.1 `crud.py` 需新增的功能

- `upsert_horse_race_history(...)`
- `upsert_race_sectional_summary(...)`
- `upsert_horse_sectional_detail(...)`
- `upsert_horse_incident_report(...)`
- `upsert_horse_running_comment(...)`
- `upsert_race_fetch_registry(...)`
- `get_race_fetch_registry(...)`
- `list_missing_sources_for_race(...)`
- `build_race_task_candidates(...)`

### 5.2 `crud.py` 需補充的查詢能力

- 依 `race_date + race_no` 查該場預期馬匹數
- 依 `race_date + race_no` 查該場已完成哪些來源
- 依 `fetch_status` 查缺漏場次
- 查某批馬匹對應到的歷史場次集合

### 5.3 寫入原則

- 所有寫入前先查唯一鍵
- 已存在資料跳過
- 支援 `record_count`
- 支援 `skipped_existing_count`
- 支援來源級 `success / partial / failed`

## 6. Phase 3 對應施工項目：馬匹歷史索引

### 6.1 新增 scraper

檔案：

- `src/j18_dbnew/scrapers/horse_history.py`

責任：

- 接收 `horse_id`
- 取得馬匹歷史頁
- 返回原始 HTML 或標準化抽取結果

### 6.2 新增 parser

檔案：

- `src/j18_dbnew/parsers/horse_history.py`

責任：

- 抽取歷史出賽資料
- 正規化：
  - `race_date`
  - `race_no`
  - `racecourse`
  - `race_name`
  - `distance_m`
  - `class_name`
  - `placing`

### 6.3 需完成的流程

- 從現有 `horses_v2` 取得馬匹清單
- 逐匹抓歷史
- 寫入 `horse_race_history`
- 驗證重跑不重複寫入

## 7. Phase 4 對應施工項目：待抓場次與 registry

### 7.1 待抓場次生成

根據 `horse_race_history` 建立場次集合：

- `race_date`
- `race_no`
- `racecourse`
- `discovered_from_horse_count`
- `discovered_at`

### 7.2 registry 功能

需支援：

- 建立來源狀態初值
- 更新 `pending / success / partial / failed`
- 記錄：
  - `last_error`
  - `expected_horse_count`
  - `record_count`
  - `retry_count`
  - `last_fetched_at`

### 7.3 核心規則

- 同一場即使被多匹馬命中，也只建立一筆場次任務
- 每一場的三個來源要分開追蹤狀態

## 8. Phase 5 對應施工項目：競賽事件報告

### 8.1 新增 scraper

- `src/j18_dbnew/scrapers/incident_report.py`

責任：

- 以賽日為單位抓 `racereportfull`
- 根據目標 `race_no` 抽出目標場資料

### 8.2 新增 parser

- `src/j18_dbnew/parsers/incident_report.py`

責任：

- 抽出：
  - `race_date`
  - `race_no`
  - `race_index`
  - `horse_id`
  - `horse_code`
  - `horse_name`
  - `horse_no`
  - `placing`
  - `draw`
  - `jockey_id`
  - `jockey_name`
  - `incident_report_text`

### 8.3 實作檢查點

- `無特別報告。` 需正常寫入
- 筆數需可對齊預期馬匹數
- 日期參數必須使用 `Date=YYYY/MM/DD`

## 9. Phase 6 對應施工項目：沿路走勢評述

### 9.1 新增 scraper

- `src/j18_dbnew/scrapers/running_comment.py`

責任：

- 以場次為單位抓 `corunning`

### 9.2 新增 parser

- `src/j18_dbnew/parsers/running_comment.py`

責任：

- 抽出：
  - `race_date`
  - `race_no`
  - `race_index`
  - `horse_id`
  - `horse_code`
  - `horse_name`
  - `horse_no`
  - `placing`
  - `jockey_name`
  - `gear`
  - `running_comment_text`

### 9.3 實作檢查點

- 日期格式必須使用 `Date=YYYYMMDD`
- 場次必須顯式傳 `raceno`
- 逐馬筆數需與該場馬匹數交叉驗證

## 10. Phase 7 對應施工項目：分段時間與完成時間

### 10.1 新增 scraper

- `src/j18_dbnew/scrapers/sectional_time.py`

責任：

- 以場次為單位抓 `displaysectionaltime`

### 10.2 新增 parser

- `src/j18_dbnew/parsers/sectional_time.py`

責任：

- 抽出場次摘要：
  - `race_finish_time`
  - `section_count`
  - `race_cumulative_time_1` 到 `race_cumulative_time_6`
  - `race_section_time_1` 到 `race_section_time_6`

- 抽出逐馬資料：
  - `finish_position`
  - `finish_time`
  - `horse_position_1` 到 `horse_position_6`
  - `horse_distance_from_leader_1` 到 `horse_distance_from_leader_6`
  - `horse_section_time_1` 到 `horse_section_time_6`
  - `horse_section_rank_1` 到 `horse_section_rank_6`
  - `horse_split_time_1a` 到 `horse_split_time_6b`

### 10.3 實作檢查點

- 日期格式必須使用 `racedate=DD/MM/YYYY`
- 固定 6 段輸出
- 超出 `section_count` 的欄位需補 `null`
- 第一版若頁面未直接提供分段排名，`horse_section_rank_n` 先填 `null`

## 11. Phase 8 對應施工項目：整體回填流程

### 11.1 新增主回填腳本

- `scripts/backfill_hkjc_history.py`

建議責任：

- 讀取馬匹來源
- 生成場次任務
- 逐場判斷缺失來源
- 依序抓：
  - `incident_report`
  - `running_comment`
  - `sectional`
- 調用 parser
- 調用 CRUD 去重寫入
- 更新 registry

### 11.2 入口模式

需支援：

- 按馬匹批次回填
- 按賽日回填
- 按單場回填

### 11.3 狀態與 QA

需輸出：

- `total_target_races`
- `success_races`
- `partial_races`
- `failed_races`
- `missing_horse_count`
- `parse_warning_count`

## 12. Phase 9 對應施工項目：API、排程與監控

### 12.1 `main.py`

可評估新增：

- 手動單場補抓 API
- 手動按賽日補抓 API
- registry 狀態查詢 API
- 缺漏場次查詢 API

### 12.2 排程腳本

新增：

- `scripts/cron_hkjc_history_fetch.py`

建議責任：

- 定時檢查缺漏場次
- 執行增量補抓
- 記錄批次摘要

### 12.3 UI 與文件

次高優先修改：

- `templates/index.html`
- `README.md`

可做內容：

- 顯示補充資料摘要
- 顯示來源完成狀態
- 補充操作方式與環境變數

## 13. 不建議第一版直接動的地方

- 不建議把 HKJC 補充資料混進既有 `history_result.py`
- 不建議直接改造 `sync_races_to_db(...)` 成補充資料主流程
- 不建議第一版就做全文摘要、NLP 標註或大量推導欄位
- 不建議在未完成 registry 前直接進入全量自動排程

## 14. 第一版驗收清單

### 14.1 Schema 驗收

- 所有新表可建立
- 唯一鍵與索引正確
- 不影響既有主資料流程

### 14.2 單來源驗收

- `incident_report` 可獨立抓取、解析、入庫
- `running_comment` 可獨立抓取、解析、入庫
- `sectional` 可獨立抓取、解析、入庫

### 14.3 流程驗收

- 可從一批馬匹建立歷史出賽索引
- 可整理待抓場次
- 可逐場補抓缺失來源
- 可重跑且不重複寫入

### 14.4 QA 驗收

- `success / partial / failed` 狀態正確
- 固定 6 段補 `null` 正確
- 預期馬匹數與實際覆蓋數可交叉驗證
- 長期失敗與缺漏可被追蹤

## 15. 建議施工順序

1. 先改 `models.py`
2. 再改 `crud.py`
3. 做 `horse_history` scraper/parser
4. 做場次任務與 registry
5. 做 `incident_report`
6. 做 `running_comment`
7. 做 `sectional_time`
8. 串主回填腳本
9. 最後才補 API / cron / UI

## 16. 對應手冊

本實作清單對應主手冊如下：

- 規格主文件：`docs/hkjc_history_data_development_manual.md`
- 本文件用途：將主手冊轉成第一版可施工的實作藍圖
