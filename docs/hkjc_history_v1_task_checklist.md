# HKJC 歷史補充資料第一版任務清單

本清單用於將 `docs/hkjc_history_v1_implementation_checklist.md` 再細化為可逐項勾選的任務列表，方便按階段、按檔案、按模組推進。

---

## A. 規格確認

- [ ] 確認主手冊 `docs/hkjc_history_data_development_manual.md` 已作為唯一規格來源
- [ ] 確認第一版實作清單 `docs/hkjc_history_v1_implementation_checklist.md` 已作為施工藍圖
- [ ] 再次確認正式需求表述不再變動
- [ ] 再次確認抓取單位固定為 `場次`
- [ ] 再次確認分段資料固定 `6 段輸出`
- [ ] 再次確認第一版預設策略為 `已存在即跳過`
- [ ] 再次確認第一版不做內容覆寫
- [ ] 再次確認 `null` 不代表抓取失敗

---

## B. Schema 與 ORM

### B1. `models.py`

- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `HorseRaceHistoryModel`
- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `RaceSectionalSummaryModel`
- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `HorseSectionalDetailModel`
- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `HorseIncidentReportModel`
- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `HorseRunningCommentModel`
- [ ] 在 `src/j18_dbnew/db/models.py` 新增 `RaceFetchRegistryModel`

### B2. 唯一鍵與索引

- [ ] 為 `horse_race_history` 定義唯一鍵 `horse_id + race_date + race_no`
- [ ] 為 `race_sectional_summary` 定義唯一鍵 `race_date + race_no`
- [ ] 為 `horse_sectional_detail` 定義唯一鍵 `race_date + race_no + horse_id`
- [ ] 為 `horse_incident_report` 定義唯一鍵 `race_date + race_no + horse_id`
- [ ] 為 `horse_running_comment` 定義唯一鍵 `race_date + race_no + horse_id`
- [ ] 為 `race_fetch_registry` 定義唯一鍵 `race_date + race_no + source_type`
- [ ] 為常用查詢欄位建立必要索引

### B3. 分段欄位

- [ ] 在 `race_sectional_summary` 建立 `section_count`
- [ ] 在 `race_sectional_summary` 建立 `race_finish_time`
- [ ] 在 `race_sectional_summary` 建立 `race_cumulative_time_1 ~ 6`
- [ ] 在 `race_sectional_summary` 建立 `race_section_time_1 ~ 6`
- [ ] 在 `horse_sectional_detail` 建立 `finish_position`
- [ ] 在 `horse_sectional_detail` 建立 `finish_time`
- [ ] 在 `horse_sectional_detail` 建立 `horse_position_1 ~ 6`
- [ ] 在 `horse_sectional_detail` 建立 `horse_distance_from_leader_1 ~ 6`
- [ ] 在 `horse_sectional_detail` 建立 `horse_section_time_1 ~ 6`
- [ ] 在 `horse_sectional_detail` 建立 `horse_section_rank_1 ~ 6`
- [ ] 在 `horse_sectional_detail` 建立 `horse_split_time_1a ~ 6b`

### B4. 通用欄位

- [ ] 各新表加入 `source_url`
- [ ] 各新表加入 `scraped_at`
- [ ] `race_fetch_registry` 加入 `fetch_status`
- [ ] `race_fetch_registry` 加入 `record_count`
- [ ] `race_fetch_registry` 加入 `last_error`
- [ ] `race_fetch_registry` 加入 `retry_count`
- [ ] `race_fetch_registry` 加入 `expected_horse_count`
- [ ] `race_fetch_registry` 加入 `first_fetched_at`
- [ ] `race_fetch_registry` 加入 `last_fetched_at`

---

## C. CRUD 與資料層

### C1. 基本 upsert / insert 能力

- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_horse_race_history(...)`
- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_race_sectional_summary(...)`
- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_horse_sectional_detail(...)`
- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_horse_incident_report(...)`
- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_horse_running_comment(...)`
- [ ] 在 `src/j18_dbnew/db/crud.py` 新增 `upsert_race_fetch_registry(...)`

### C2. 查詢與狀態能力

- [ ] 新增 `get_race_fetch_registry(...)`
- [ ] 新增 `list_missing_sources_for_race(...)`
- [ ] 新增 `build_race_task_candidates(...)`
- [ ] 新增按 `fetch_status` 查詢缺漏場次
- [ ] 新增按 `race_date + race_no` 查詢預期馬匹數
- [ ] 新增按 `race_date + race_no` 查詢已完成來源
- [ ] 新增按馬匹批次查歷史場次集合

### C3. 去重規則落地

- [ ] 所有寫入前實作唯一鍵查驗
- [ ] 實作已存在資料跳過邏輯
- [ ] 實作 `record_count` 統計
- [ ] 實作 `skipped_existing_count` 統計
- [ ] 實作 `success / partial / failed` 來源級判定

---

## D. 馬匹歷史索引

### D1. 新增 scraper

- [ ] 建立 `src/j18_dbnew/scrapers/horse_history.py`
- [ ] 定義輸入為 `horse_id`
- [ ] 定義輸出為原始 HTML 或標準化資料
- [ ] 確認來源頁 URL 格式
- [ ] 處理編碼、重試與基本頁面驗證

### D2. 新增 parser

- [ ] 建立 `src/j18_dbnew/parsers/horse_history.py`
- [ ] 抽出 `race_date`
- [ ] 抽出 `race_no`
- [ ] 抽出 `racecourse`
- [ ] 抽出 `race_name`
- [ ] 抽出 `distance_m`
- [ ] 抽出 `class_name`
- [ ] 抽出 `placing`
- [ ] 輸出標準化資料結構

### D3. 寫入與驗證

- [ ] 將歷史資料寫入 `horse_race_history`
- [ ] 驗證同一匹馬同一場不會重複寫入
- [ ] 驗證從現有 `horses_v2` 可以正確取出待處理馬匹

---

## E. 場次任務與 Registry

### E1. 待抓場次生成

- [ ] 從 `horse_race_history` 生成場次集合
- [ ] 對場次集合做去重
- [ ] 保存 `race_date`
- [ ] 保存 `race_no`
- [ ] 保存 `racecourse`
- [ ] 保存 `discovered_from_horse_count`

### E2. Registry 流程

- [ ] 建立 registry 初始記錄
- [ ] 實作 `pending` 狀態
- [ ] 實作 `success` 狀態
- [ ] 實作 `partial` 狀態
- [ ] 實作 `failed` 狀態
- [ ] 實作 `last_error` 更新
- [ ] 實作 `retry_count` 更新
- [ ] 實作 `last_fetched_at` 更新

---

## F. 競賽事件報告

### F1. Scraper

- [ ] 建立 `src/j18_dbnew/scrapers/incident_report.py`
- [ ] 正確組裝 `Date=YYYY/MM/DD`
- [ ] 以賽日為單位抓取 `racereportfull`
- [ ] 能從賽日頁抽出目標 `race_no`
- [ ] 加入基本頁面正確性驗證

### F2. Parser

- [ ] 建立 `src/j18_dbnew/parsers/incident_report.py`
- [ ] 抽出 `race_date`
- [ ] 抽出 `race_no`
- [ ] 抽出 `race_index`
- [ ] 抽出 `horse_id`
- [ ] 抽出 `horse_code`
- [ ] 抽出 `horse_name`
- [ ] 抽出 `horse_no`
- [ ] 抽出 `placing`
- [ ] 抽出 `draw`
- [ ] 抽出 `jockey_id`
- [ ] 抽出 `jockey_name`
- [ ] 抽出 `incident_report_text`

### F3. 驗證

- [ ] 確認 `無特別報告。` 會正常寫入
- [ ] 確認筆數可對齊預期馬匹數
- [ ] 確認錯誤日期參數不會誤判成功

---

## G. 沿路走勢評述

### G1. Scraper

- [ ] 建立 `src/j18_dbnew/scrapers/running_comment.py`
- [ ] 正確組裝 `Date=YYYYMMDD&raceno=N`
- [ ] 以場次為單位抓取 `corunning`
- [ ] 加入日期與場次正確性驗證

### G2. Parser

- [ ] 建立 `src/j18_dbnew/parsers/running_comment.py`
- [ ] 抽出 `race_date`
- [ ] 抽出 `race_no`
- [ ] 抽出 `race_index`
- [ ] 抽出 `horse_id`
- [ ] 抽出 `horse_code`
- [ ] 抽出 `horse_name`
- [ ] 抽出 `horse_no`
- [ ] 抽出 `placing`
- [ ] 抽出 `jockey_name`
- [ ] 抽出 `gear`
- [ ] 抽出 `running_comment_text`

### G3. 驗證

- [ ] 確認場次筆數與預期馬匹數一致
- [ ] 確認未傳 `raceno` 時不會默認誤判成功
- [ ] 確認文字欄位不被截斷

---

## H. 分段時間與完成時間

### H1. Scraper

- [ ] 建立 `src/j18_dbnew/scrapers/sectional_time.py`
- [ ] 正確組裝 `racedate=DD/MM/YYYY&RaceNo=N`
- [ ] 以場次為單位抓取 `displaysectionaltime`
- [ ] 驗證頁面日期與場次正確

### H2. Parser

- [ ] 建立 `src/j18_dbnew/parsers/sectional_time.py`
- [ ] 抽出 `section_count`
- [ ] 抽出 `race_finish_time`
- [ ] 抽出 `race_cumulative_time_1 ~ 6`
- [ ] 抽出 `race_section_time_1 ~ 6`
- [ ] 抽出 `finish_position`
- [ ] 抽出 `finish_time`
- [ ] 抽出 `horse_position_1 ~ 6`
- [ ] 抽出 `horse_distance_from_leader_1 ~ 6`
- [ ] 抽出 `horse_section_time_1 ~ 6`
- [ ] 抽出 `horse_split_time_1a ~ 6b`
- [ ] 先保留 `horse_section_rank_1 ~ 6` 欄位，第一版可填 `null`

### H3. 固定 6 段輸出

- [ ] 實作 `section_count` 驗證
- [ ] 實作不足段數補 `null`
- [ ] 實作超出段數欄位必為 `null`
- [ ] 場次層與逐馬層採用一致補空規則

### H4. 驗證

- [ ] 驗證 5 段賽事會正確補第 6 段為 `null`
- [ ] 驗證完成時間可正常保存
- [ ] 驗證逐馬筆數與預期馬匹數一致

---

## I. 主回填流程

### I1. 回填腳本

- [ ] 建立 `scripts/backfill_hkjc_history.py`
- [ ] 能讀取馬匹來源
- [ ] 能生成場次任務
- [ ] 能逐場判斷缺失來源
- [ ] 能依序抓 `incident_report`
- [ ] 能依序抓 `running_comment`
- [ ] 能依序抓 `sectional`
- [ ] 能調用 parser
- [ ] 能調用 CRUD 去重寫入
- [ ] 能更新 registry

### I2. 回填模式

- [ ] 支援按馬匹批次回填
- [ ] 支援按賽日回填
- [ ] 支援按單場回填

### I3. 輸出摘要

- [ ] 輸出 `total_target_races`
- [ ] 輸出 `success_races`
- [ ] 輸出 `partial_races`
- [ ] 輸出 `failed_races`
- [ ] 輸出 `missing_horse_count`
- [ ] 輸出 `parse_warning_count`

---

## J. API、排程與 UI

### J1. `main.py`

- [ ] 評估新增單場補抓 API
- [ ] 評估新增按賽日補抓 API
- [ ] 評估新增 registry 狀態查詢 API
- [ ] 評估新增缺漏場次查詢 API

### J2. 排程

- [ ] 建立 `scripts/cron_hkjc_history_fetch.py`
- [ ] 支援定時檢查缺漏場次
- [ ] 支援增量補抓
- [ ] 支援批次摘要輸出

### J3. 文件與頁面

- [ ] 視需要調整 `README.md`
- [ ] 視需要調整 `templates/index.html`
- [ ] 補充補抓流程操作說明
- [ ] 補充環境變數說明

---

## K. QA 與驗收

### K1. Schema 驗收

- [ ] 新表可成功建立
- [ ] 唯一鍵與索引正確
- [ ] 不影響既有主流程

### K2. 單來源驗收

- [ ] `incident_report` 可獨立抓取、解析、入庫
- [ ] `running_comment` 可獨立抓取、解析、入庫
- [ ] `sectional` 可獨立抓取、解析、入庫

### K3. 流程驗收

- [ ] 可從一批馬匹建立歷史出賽索引
- [ ] 可整理待抓場次
- [ ] 可逐場補抓缺失來源
- [ ] 可重跑且不重複寫入

### K4. QA 驗收

- [ ] `success / partial / failed` 狀態正確
- [ ] 固定 6 段補 `null` 正確
- [ ] 預期馬匹數與實際覆蓋數可交叉驗證
- [ ] 長期失敗與缺漏可被追蹤

---

## L. 第一版不做

- [ ] 不把 HKJC 補充資料混進既有 `history_result.py`
- [ ] 不把 `sync_races_to_db(...)` 改成補充資料主流程
- [ ] 不在第一版做全文摘要或 NLP 標註
- [ ] 不在未完成 registry 前直接進入全量自動排程

---

## M. 建議施工順序

- [ ] 先改 `models.py`
- [ ] 再改 `crud.py`
- [ ] 再做 `horse_history` scraper/parser
- [ ] 再做場次任務與 registry
- [ ] 再做 `incident_report`
- [ ] 再做 `running_comment`
- [ ] 再做 `sectional_time`
- [ ] 再串主回填腳本
- [ ] 最後才補 API / cron / UI
