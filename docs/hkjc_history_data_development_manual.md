# HKJC 歷史補充資料開發手冊

本手冊用於定義 HKJC 歷史賽事補充資料的抓取、正規化、去重、入庫、回填、驗證與風險管理方案，作為後續 scraper、parser、schema、回填腳本與排程設計的正式依據。

## 目錄

1. 文件目的
2. 正式需求定義
3. 現有專案與資料庫概況
4. 整體資料流程
5. HKJC 資料來源規格
6. 核心資料模型設計
7. 唯一鍵與去重策略
8. 抓取策略與任務拆分
9. Parser 與正規化規範
10. 入庫策略與資料一致性
11. 回填策略
12. 驗證與 QA 流程
13. 錯誤處理與風險管理
14. 分階段開發計劃
15. 後續擴充方向
附錄 A. HKJC 來源頁面規格表
附錄 B. 建議資料表與欄位字典
附錄 C. 去重與回填 SOP

## 1. 文件目的

- 本手冊用於定義 HKJC 歷史賽事補充資料的抓取、正規化、去重與入庫方案。
- 本手冊優先作為開發依據與驗證依據，而不是程式實作文件。
- 所有後續 scraper、parser、schema 與回填腳本，均以本手冊為準。

## 2. 正式需求定義

正式需求表述如下：

> 系統以現有賽果資料庫為起點，透過馬匹歷史出賽紀錄整理待抓場次清單；對每一場歷史賽事，抓取該場的場次完成時間與整體分段時間，以及該場全部馬匹的分段時間、分段排名、競賽事件報告及沿路走勢評述，並以唯一鍵去重後寫入資料庫。

核心原則如下：

- 以現有資料庫為起點。
- 以場次為抓取單位。
- 只要打開某場，就整場入庫。
- 所有資料均以唯一鍵去重。
- 分段資料固定 6 段輸出，不足段數補 `null`。

## 3. 現有專案與資料庫概況

專案目前已有：

- FastAPI API 入口。
- SQLAlchemy ORM 與 CRUD。
- `historyResult` 主資料解析與入庫流程。
- 部分爬蟲與排程腳本。

現有主表：

- `races_v2`
- `horses_v2`
- `kv_store_v2`

本次需求不應直接破壞既有主流程，而應以「擴充資料層」方式接入。

## 4. 整體資料流程

標準流程如下：

1. 由現有 `horses_v2` 或相關主表取得已知馬匹。
2. 抓取每匹馬的歷史出賽紀錄。
3. 整理成待抓場次清單。
4. 按場次抓取 HKJC 補充頁面。
5. 解析為場次層資料與逐馬層資料。
6. 用唯一鍵去重後寫入資料庫。
7. 記錄抓取狀態、失敗原因與回填進度。

資料流程圖文字版：

- 現有賽果資料庫
- 取得已知馬匹
- 抓馬匹歷史出賽
- 整理待抓場次清單
- 按場次抓 HKJC 頁面
- 解析為場次層 / 逐馬層資料
- 按唯一鍵去重
- 寫入資料庫
- 記錄抓取狀態與缺漏

## 5. HKJC 資料來源規格

本系統目前已確認以下主要來源：

### 5.1 競賽事件報告

- 路徑：`/zh-hk/local/information/racereportfull`
- 正確格式：`https://racing.hkjc.com/zh-hk/local/information/racereportfull?Date=YYYY/MM/DD`
- 粒度：逐賽日頁面，頁內包含該日全部場次
- 日期參數：`Date`
- 日期格式：`YYYY/MM/DD`
- 場次參數：無，整頁返回當日所有場次
- 內容層次：賽日層 -> 場次層 -> 逐馬層

### 5.2 沿路走勢評述

- 路徑：`/zh-hk/local/information/corunning`
- 正確格式：`https://racing.hkjc.com/zh-hk/local/information/corunning?Date=YYYYMMDD&raceno=N`
- 粒度：逐場頁面
- 日期參數：`Date`
- 日期格式：`YYYYMMDD`
- 場次參數：`raceno`
- 場次格式：整數，從 `1` 開始
- 內容層次：場次層 -> 逐馬層

### 5.3 分段時間及位置

- 路徑：`/zh-hk/local/information/displaysectionaltime`
- 正確格式：`https://racing.hkjc.com/zh-hk/local/information/displaysectionaltime?racedate=DD/MM/YYYY&RaceNo=N`
- 粒度：逐場頁面
- 日期參數：`racedate`
- 日期格式：`DD/MM/YYYY`
- 場次參數：`RaceNo`
- 場次格式：整數，從 `1` 開始
- 內容層次：場次層 -> 逐馬層 -> 分段點層

### 5.4 統一規則

- `競賽事件報告` 以賽日為單位抓取。
- `沿路走勢評述` 以場次為單位抓取。
- `分段時間及位置` 以場次為單位抓取。
- 所有來源最終需對齊到：`race_date`、`race_no`、`horse_id`。
- 入庫時一律正規化成資料庫標準日期格式。

## 6. 核心資料模型設計

建議把資料拆為兩大類：

- 場次層資料
- 逐馬層資料

建議資料表如下：

- `horse_race_history`
- `race_sectional_summary`
- `horse_sectional_detail`
- `horse_incident_report`
- `horse_running_comment`
- `race_fetch_registry`

設計原則如下：

- 場次層與逐馬層分開存，不把所有內容硬塞進 `horses_v2`。
- 分段資料固定 6 段輸出。
- 所有來源資料保留 `source_url` 與 `scraped_at`。
- 預設去重策略為「已存在即跳過」。
- `無特別報告。` 視為有效資料，不是空值。

## 7. 唯一鍵與去重策略

### 7.1 章節目的

- 定義唯一識別方式、資料去重規則、重複寫入處理方式，以及資料完整性判定基準。

### 7.2 核心原則

- 所有資料寫入前必須先做唯一鍵判斷。
- 去重以業務主鍵為基礎，不以內部流水號作判斷。
- 已存在資料預設跳過，不重複寫入。
- 同一場的不同來源分開判斷完整性，不混為單一完成狀態。
- `null` 只表示來源未提供或該欄位不適用，不代表抓取失敗。
- 抓取失敗、解析失敗、寫入異常，必須由獨立狀態欄位或抓取紀錄表表示。

### 7.3 各資料表唯一鍵

- `horse_race_history`：`horse_id + race_date + race_no`
- `race_sectional_summary`：`race_date + race_no`
- `horse_sectional_detail`：`race_date + race_no + horse_id`
- `horse_incident_report`：`race_date + race_no + horse_id`
- `horse_running_comment`：`race_date + race_no + horse_id`
- `race_fetch_registry`：`race_date + race_no + source_type`

### 7.4 去重行為規則

- 唯一鍵不存在時，允許新增。
- 唯一鍵已存在時，預設跳過，不重寫。
- 重跑同一場次時，不得因重跑而重複新增資料。
- 若同一場僅某個來源未完成時，只補抓該來源，不影響其他已完成來源。

### 7.5 第一版更新策略

- 第一版不以內容變更為覆寫條件。
- 即使重新抓取時發現內容可能更新，只要唯一鍵已存在，仍預設跳過。
- 後續如需支援版本更新，再加入 `content_hash`、`data_version`、`updated_at` 等欄位。

## 8. 抓取策略與任務拆分

### 8.1 核心策略

本系統採用 `以馬找場、以場抓頁、整場入庫` 的策略。

### 8.2 抓取單位

- 邏輯起點單位：馬匹
- 任務執行單位：場次
- 資料入庫單位：
  - 場次層資料為一場一筆
  - 逐馬層資料為一場內每匹馬一筆

### 8.3 系統總流程

1. 從現有資料庫取得待處理馬匹
2. 抓取馬匹歷史出賽紀錄
3. 整理待抓場次清單
4. 對場次清單做場次去重
5. 逐場抓取 HKJC 補充來源頁
6. 解析為場次層與逐馬層資料
7. 依唯一鍵做寫入前去重
8. 寫入資料庫
9. 更新抓取狀態與缺漏紀錄
10. 對失敗或部分成功場次保留重試能力

### 8.4 任務拆分

- 任務 A：馬匹來源整理
- 任務 B：馬匹歷史抓取
- 任務 C：待抓場次生成
- 任務 D：場次補充頁抓取
- 任務 E：解析與正規化
- 任務 F：入庫與狀態更新

### 8.5 執行順序建議

- 第一版固定順序：`A -> B -> C -> D -> E -> F`
- 場次補充頁抓取內部順序：`incident_report -> running_comment -> sectional`

### 8.6 並行策略

- 第一版建議採「場次級可並行，場內來源可序列」。
- 多個場次可以並行抓。
- 同一場內的 3 個來源先按固定順序抓。

## 9. Parser 與正規化規範

### 9.1 核心原則

- 先解析，後入庫。
- 所有唯一鍵欄位必須先正規化，再進行去重。
- 場次層資料與逐馬層資料分開解析。
- 固定 6 段輸出，不足段數補 `null`。
- 來源未提供的欄位可為 `null`，但抓取失敗不得以 `null` 替代。

### 9.2 Parser 對應

- `IncidentReportParser` 對應 `racereportfull`
- `RunningCommentParser` 對應 `corunning`
- `SectionalTimeParser` 對應 `displaysectionaltime`

### 9.3 日期正規化規則

- `racereportfull`：來源格式 `YYYY/MM/DD`
- `corunning`：來源格式 `YYYYMMDD`
- `displaysectionaltime`：來源格式 `DD/MM/YYYY`
- 正規化後一律輸出資料庫標準 `race_date`

### 9.4 場次欄位規範

- `race_no` 一律轉整數
- `race_index` 可保留原始識別資訊，但不作唯一鍵主體
- `distance_m` 一律轉整數
- `class_name`、`rating_range`、`race_name`、`racecourse`、`surface`、`course_code`、`going` 保留原文或標準固定值

### 9.5 馬匹識別規範

- `horse_id` 為逐馬層主識別欄位
- `horse_code` 作輔助欄位
- `horse_name` 保留原文
- `horse_no` 一律轉整數
- 若無法抽到 `horse_id`，可暫以 `horse_name + horse_code` 作輔助識別，但須標記為非理想匹配

### 9.6 文字欄位規範

- `incident_report_text` 保留全文原文
- `running_comment_text` 保留全文原文
- `無特別報告。` 視為有效內容

### 9.7 分段資料規範

- 所有分段資料固定輸出 6 段欄位
- 若來源實際段數少於 6 段，不存在的欄位一律補 `null`
- 同時必須保存 `section_count`

### 9.8 Parser 標準輸出

每個 parser 應產出：

- `source_type`
- `source_url`
- `race_date`
- `race_no`
- `race_level_data`
- `horse_level_data[]`
- `parse_warning[]`
- `section_count`，如適用

## 10. 入庫策略與資料一致性

### 10.1 核心原則

- 所有來源資料必須先解析與正規化，再進行入庫。
- 所有寫入必須先依唯一鍵去重。
- 入庫以來源為單位判斷成功與否，不以整場一次性全有或全無處理。
- 任一來源寫入失敗，不得影響其他已成功來源。
- 所有寫入結果必須同步更新抓取狀態紀錄。

### 10.2 入庫分層

- 索引層：`horse_race_history`
- 場次層：`race_sectional_summary`
- 逐馬層：`horse_sectional_detail`、`horse_incident_report`、`horse_running_comment`
- 狀態層：`race_fetch_registry`

### 10.3 標準入庫順序

1. `horse_race_history`
2. `race_sectional_summary`
3. `horse_sectional_detail`
4. `horse_incident_report`
5. `horse_running_comment`
6. `race_fetch_registry`

### 10.4 狀態判定

- `success`：來源頁成功取得、解析成功、筆數與預期基本一致
- `partial`：來源頁可取得，但只有部分資料成功
- `failed`：抓取、解析或寫入過程未形成可信結果

### 10.5 一致性規則

- 所有逐馬表中的 `race_date + race_no` 必須與對應場次一致
- 同一場內逐馬資料的 `horse_id` 不應重複
- `section_count` 與固定 6 段欄位補空規則必須一致
- 若 `race_sectional_summary` 存在，則 `race_finish_time` 不可缺失

## 11. 回填策略

### 11.1 核心原則

- 回填以場次為執行單位，不以單一馬匹為最終抓取單位。
- 回填來源來自馬匹歷史出賽紀錄，而不是直接掃全站所有歷史賽事。
- 已存在資料預設跳過，只補缺口。
- 同一場的不同來源應獨立判斷是否需要補抓。
- 回填流程必須可按單場、按賽日、按批次重跑。

### 11.2 回填入口

- 入口 A：按馬匹批次回填
- 入口 B：按賽日回填
- 入口 C：按單場回填

### 11.3 標準回填主流程

1. 取得回填入口範圍
2. 整理出待抓場次清單
3. 查詢 `race_fetch_registry`
4. 判斷每場哪些來源尚未完成
5. 只抓需要補抓的來源
6. 解析與正規化
7. 依唯一鍵去重後寫入
8. 更新來源狀態
9. 保留失敗與部分成功資訊供後續重試

### 11.4 回填判斷邏輯

視為不需回填的條件：

- 有對應 `source_type`
- `fetch_status = success`
- 正式資料筆數合理
- 與預期馬匹數一致或可接受

視為需回填的條件：

- 無任何 registry
- `fetch_status = failed`
- `fetch_status = partial`
- 筆數低於預期
- 關鍵欄位大量缺失

### 11.5 重跑策略

- 第一版允許重跑，但重跑不等於覆寫
- 已存在資料跳過
- 缺失資料補寫
- `failed` 來源重抓
- `partial` 來源補齊後升級為 `success`

## 12. 驗證與 QA 流程

### 12.1 核心原則

- 每個來源都必須獨立驗證，不可只驗整場最終結果。
- 驗證必須分層進行，不能只做資料庫最終筆數檢查。
- 去重成功不代表資料完整，完整仍需額外驗證。
- QA 必須同時涵蓋自動驗證與人工抽樣驗證。

### 12.2 驗證分層

- 第一層：來源頁驗證
- 第二層：Parser 驗證
- 第三層：入庫驗證
- 第四層：完整性驗證

### 12.3 來源頁驗證規則

每次抓取後至少檢查：

- `page_url` 是否符合預期來源
- `race_date` 是否與目標一致
- `race_no` 是否與目標一致
- 頁面主標題是否符合來源類型
- 是否存在主要資料表格或主要內容區塊

### 12.4 Parser 驗證規則

每個 parser 完成後至少驗證：

- `race_date` 是否成功正規化
- `race_no` 是否為整數
- `horse_id` 是否成功抽取
- `horse_name` 是否非空
- 逐馬資料是否有筆數
- 場次層資料是否存在
- 固定 6 段欄位是否補齊
- `section_count` 是否合理

### 12.5 完整性驗證規則

每個來源都應與預期馬匹數交叉驗證：

- `expected_horse_count`
- `actual_incident_report_count`
- `actual_running_comment_count`
- `actual_sectional_detail_count`

### 12.6 固定 6 段輸出的 QA 規則

每筆分段資料都必須驗證：

- `section_count` 是否介於 1 到 6
- 所有實際存在的段數欄位應有值
- 超出 `section_count` 的段數欄位應為 `null`
- 場次層與逐馬層必須遵守同一補空規則

## 13. 錯誤處理與風險管理

### 13.1 核心原則

- 錯誤必須被記錄，不可被靜默吞掉。
- 來源異常、解析異常、入庫異常必須分開處理。
- 單場失敗不得中斷整批任務。
- 單一來源失敗不得覆蓋其他已成功來源。
- `partial` 與 `failed` 必須保留重試能力。
- 長期失敗或異常重複出現時，必須升級為人工檢查事項。

### 13.2 錯誤分類

- 類別 A：參數與請求錯誤
- 類別 B：來源頁錯誤
- 類別 C：Parser 錯誤
- 類別 D：資料一致性錯誤
- 類別 E：入庫與流程錯誤

### 13.3 錯誤處理原則

- 參數錯誤導致抓錯頁時，直接標記為 `failed`
- 來源頁結構改版時，優先記錄 `page_structure_changed`
- Parser 若只能產生部分可信資料，標記 `partial`
- 若無法形成可信結構，標記 `failed`
- 第一版以保留既有有效資料與補抓缺漏為原則，不以整場刪除重建作為預設處理策略

### 13.4 建議保留的錯誤欄位

- `fetch_status`
- `last_error`
- `retry_count`
- `parse_warning`
- `expected_horse_count`
- `record_count`
- `skipped_existing_count`
- `last_fetched_at`

### 13.5 建議錯誤碼

- `parameter_error`
- `page_not_found`
- `page_structure_changed`
- `parser_error`
- `missing_main_table`
- `missing_horse_id`
- `record_count_mismatch`
- `db_write_error`
- `registry_update_error`

## 14. 分階段開發計劃

### 14.1 章節目的

- 本章用於將本手冊前述規格轉化為實際可執行的開發順序。
- 本章目標不是羅列所有可能工作，而是定義第一版系統應按什麼次序落地、每個階段要交付什麼，以及何時可進入下一階段。

### 14.2 核心原則

- 先定規格，再寫程式。
- 先建立資料結構，再建立抓取流程。
- 先完成單一來源驗證，再進入批次回填。
- 先確保去重與資料一致性，再做自動化排程。
- 每一階段都必須有明確的完成標準，不以「大致可用」作為結束條件。

### 14.3 階段總覽

- `Phase 1`：手冊與資料模型定稿
- `Phase 2`：資料庫 schema 與 ORM 擴充
- `Phase 3`：馬匹歷史出賽索引流程
- `Phase 4`：待抓場次清單與 registry 流程
- `Phase 5`：競賽事件報告來源打通
- `Phase 6`：沿路走勢評述來源打通
- `Phase 7`：分段時間與完成時間來源打通
- `Phase 8`：整體入庫、回填與 QA 流程整合
- `Phase 9`：批次執行、自動補抓與監控

### 14.4 Phase 1：手冊與資料模型定稿

**目標**

- 完成開發手冊第一版。
- 定義正式需求、資料來源規格、固定 6 段輸出規格、唯一鍵規則與回填原則。

**主要工作**

- 完成主手冊撰寫。
- 完成附錄 A、B、C。
- 定義場次層與逐馬層資料表。
- 定義去重與 `partial / failed / success` 標準。

**交付物**

- `docs/hkjc_history_data_development_manual.md`

**完成標準**

- 手冊內容足以支撐 schema 設計與程式開發。
- 主要名詞、欄位、流程與責任邊界已定稿。

### 14.5 Phase 2：資料庫 schema 與 ORM 擴充

**目標**

- 將手冊中的資料模型轉化為正式資料表與 ORM 定義。

**主要工作**

- 新增 `horse_race_history`
- 新增 `race_sectional_summary`
- 新增 `horse_sectional_detail`
- 新增 `horse_incident_report`
- 新增 `horse_running_comment`
- 新增 `race_fetch_registry`
- 在 ORM 中建立唯一鍵與必要索引

**交付物**

- 新版 `models.py`
- 必要的 `crud.py` 擴充
- schema 說明補充至文件

**完成標準**

- 新資料表可在現有專案中建立。
- 唯一鍵與欄位型別符合手冊規範。
- 不影響既有 `races_v2` / `horses_v2` 主流程。

### 14.6 Phase 3：馬匹歷史出賽索引流程

**目標**

- 從現有馬匹資料出發，建立每匹馬的歷史出賽索引。

**主要工作**

- 設計馬匹歷史來源頁抓取方式。
- 建立馬匹歷史 parser。
- 將歷史出賽資料寫入 `horse_race_history`。
- 驗證 `horse_id + race_date + race_no` 去重規則。

**交付物**

- 馬匹歷史 scraper
- 馬匹歷史 parser
- 馬匹歷史入庫流程

**完成標準**

- 可從現有資料庫中挑選一批馬匹，成功寫入歷史出賽索引。
- 重跑時不會重複寫入同一匹馬的同一場紀錄。

### 14.7 Phase 4：待抓場次清單與 registry 流程

**目標**

- 將逐馬歷史出賽資料整理成場次任務，並建立來源級狀態追蹤能力。

**主要工作**

- 從 `horse_race_history` 生成待抓場次集合。
- 實作場次級去重。
- 建立 `race_fetch_registry` 的建立與更新規則。
- 定義 `pending / success / partial / failed` 實際流轉。

**交付物**

- 場次任務生成邏輯
- registry CRUD 與狀態更新邏輯

**完成標準**

- 同一場若被多匹馬命中，只會生成一筆場次任務。
- 系統可判斷某場哪些來源已完成、哪些仍需補抓。

### 14.8 Phase 5：競賽事件報告來源打通

**目標**

- 打通 `racereportfull` 的抓取、解析、入庫與驗證。

**主要工作**

- 建立競賽事件報告 scraper。
- 建立對應 parser。
- 按目標場次從賽日頁抽出目標場資料。
- 寫入 `horse_incident_report`。
- 更新 `race_fetch_registry` 中的 `incident_report` 狀態。

**交付物**

- `IncidentReportParser`
- `horse_incident_report` 寫入流程
- 來源驗證與 QA 規則的實作版本

**完成標準**

- 任意指定一場，可寫入該場全部馬匹的事件報告。
- `無特別報告。` 可正常保存。
- 逐馬筆數可與預期馬匹數交叉驗證。

### 14.9 Phase 6：沿路走勢評述來源打通

**目標**

- 打通 `corunning` 的抓取、解析、入庫與驗證。

**主要工作**

- 建立沿路走勢評述 scraper。
- 建立對應 parser。
- 寫入 `horse_running_comment`。
- 更新 `race_fetch_registry` 中的 `running_comment` 狀態。

**交付物**

- `RunningCommentParser`
- `horse_running_comment` 寫入流程
- 對應 QA 驗證邏輯

**完成標準**

- 任意指定一場，可寫入該場全部馬匹的走勢評述。
- `gear`、`jockey_name`、`running_comment_text` 可穩定抽取。
- 場次、日期與馬匹數驗證可通過。

### 14.10 Phase 7：分段時間與完成時間來源打通

**目標**

- 打通 `displaysectionaltime` 的抓取、解析、入庫與驗證。

**主要工作**

- 建立分段時間 scraper。
- 建立對應 parser。
- 實作固定 6 段輸出補 `null` 規則。
- 寫入 `race_sectional_summary`
- 寫入 `horse_sectional_detail`
- 更新 `race_fetch_registry` 中的 `sectional` 狀態。

**交付物**

- `SectionalTimeParser`
- 場次摘要與逐馬分段入庫流程
- 固定 6 段輸出驗證邏輯

**完成標準**

- 可正確保存場次完成時間與整體分段時間。
- 可正確保存逐馬分段時間、位置與距離資訊。
- 少於 6 段的賽事可正確補 `null`。

### 14.11 Phase 8：整體入庫、回填與 QA 流程整合

**目標**

- 將各單一來源串成完整回填流程，並建立整體 QA。

**主要工作**

- 實作 `A -> B -> C -> D -> E -> F` 全流程。
- 支援按馬匹批次、按賽日、按單場回填。
- 打通去重、補抓與來源級狀態判定。
- 建立批次層摘要與 QA 報告輸出。

**交付物**

- 主回填腳本或主服務流程
- 完整 registry 流程
- QA 檢查與摘要輸出

**完成標準**

- 可從一批馬匹出發，自動補出多場歷史補充資料。
- 部分成功與失敗場次能被正確標記。
- 重跑時只補缺口，不重複寫入。

### 14.12 Phase 9：批次執行、自動補抓與監控

**目標**

- 讓系統從手動回填工具升級為可持續執行的資料補全流程。

**主要工作**

- 設計批次執行入口。
- 建立定期補抓機制。
- 增加失敗重試與人工檢查輸出。
- 增加完成率、缺漏率、失敗率等監控指標。

**交付物**

- 排程腳本
- 補抓任務入口
- 監控或摘要報表

**完成標準**

- 系統可定期補抓新發現的歷史場次。
- 可追蹤哪些來源長期 `failed` 或 `partial`。
- 可輸出批次執行摘要供人工檢查。

### 14.13 階段間依賴關係

- Phase 2 依賴 Phase 1。
- Phase 3 依賴 Phase 2。
- Phase 4 依賴 Phase 3。
- Phase 5、6、7 依賴 Phase 4，可依序實作，不建議同時全面展開。
- Phase 8 依賴 Phase 5、6、7。
- Phase 9 依賴 Phase 8。

### 14.14 建議實作順序

第一版建議採以下順序：

1. 先完成 Phase 2，落實 schema。
2. 再完成 Phase 3、4，打通索引與場次任務層。
3. 接著依序完成 Phase 5、6、7。
4. 再做 Phase 8 的整體整合。
5. 最後才做 Phase 9 的自動化與監控。

### 14.15 每階段驗收原則

- 每階段都應有可單獨驗證的輸入與輸出。
- 每階段完成後都應至少有一次小規模人工驗證。
- 每階段若未達成去重穩定、資料可驗證、錯誤可追蹤三項條件，不得直接進入下一階段。

### 14.16 可直接寫入手冊的正式文字

- 本系統採分階段開發方式，依序完成手冊定稿、schema 擴充、馬匹歷史索引、場次任務生成、三類 HKJC 來源打通、整體回填整合，以及排程與監控建置。各階段均須有明確交付物與完成標準，並以前一階段可驗證、可去重、可追蹤為進入下一階段之前提。第一版實作不得跳過中間索引層與狀態層，亦不得在未完成單來源驗證前直接進入全量回填。

## 15. 後續擴充方向

### 15.1 章節目的

- 本章用於定義第一版系統完成後的擴充方向，避免在第一版尚未穩定時過早加入高複雜度功能。
- 本章目標是為後續 roadmap 提供優先級與啟動條件，而不是把所有可能需求都塞進第一版。

### 15.2 擴充原則

- 第一版以資料可抓、可驗證、可去重、可回填為優先。
- 所有擴充功能必須建立在既有主流程穩定的前提上。
- 新擴充若會改變唯一鍵、主資料表或回填邏輯，必須先更新手冊再實作。
- 擴充功能優先考慮「提升資料完整率」與「提升維運可視性」，其次才是分析型附加功能。

### 15.3 優先級分層

- `P1`：第一版穩定後，應優先追加的功能
- `P2`：在主要資料流穩定後，建議逐步擴充的功能
- `P3`：偏分析、輔助或運營層功能，可在系統成熟後再做

### 15.4 P1：高優先級擴充

#### 15.4.1 缺漏場次追蹤

**目標**

- 建立一套可直接看出哪些場次、哪些來源仍缺資料的追蹤機制。

**價值**

- 直接提升回填效率。
- 可快速定位長期 `partial` 或 `failed` 的來源。

**建議內容**

- 缺漏場次列表
- 按來源分類的缺漏統計
- 長期失敗場次清單

**啟動條件**

- `race_fetch_registry` 已穩定運作。
- 回填流程已能穩定標記 `success / partial / failed`。

#### 15.4.2 手動重抓工具

**目標**

- 提供人工指定單場、單日或單一來源重跑的能力。

**價值**

- 提升除錯效率。
- 降低修補單一場次缺口的成本。

**建議內容**

- 按 `race_date + race_no` 重抓
- 按賽日重抓
- 按來源類型重抓

**啟動條件**

- 基本回填流程穩定。
- 單場回填入口已完成。

#### 15.4.3 抓取完成率報表

**目標**

- 將目前歷史資料補全進度量化。

**價值**

- 可觀察系統是否真的逐步提高完整率。
- 可作為排程與維運的健康度指標。

**建議內容**

- 來源完成率
- 場次完成率
- `partial` / `failed` 比例
- 每批次新增覆蓋量

**啟動條件**

- 批次摘要與 registry 已可穩定統計。

### 15.5 P2：中優先級擴充

#### 15.5.1 研訊摘要

**目標**

- 補充賽事後續的研訊、裁決或重點摘要資料。

**價值**

- 增加對賽事事件後續結果的追蹤能力。
- 有助建立更完整的歷史事件上下文。

**風險**

- 頁面結構與欄位語意可能與現有來源差異較大。
- 可能需要新增新的事件層資料表。

**啟動條件**

- 既有事件報告來源已穩定。
- 手冊已補充新來源規格。

#### 15.5.2 獸醫報告相關標記

**目標**

- 從既有文字資料中抽取或整理與獸醫結果、再次出賽限制相關的標記。

**價值**

- 可讓下游查詢更容易辨識：
  - 出血
  - 發燒
  - 必須通過獸醫檢驗
  - 必須試閘及格

**風險**

- 第一版若以規則抽取，需非常保守，避免錯誤標註。
- 若從原文抽取結構化標記，屬於派生資料，不應覆蓋原文。

**啟動條件**

- `horse_incident_report` 已穩定累積足夠資料。
- 原文保存策略已穩固。

#### 15.5.3 馬匹裝備變更

**目標**

- 追蹤同一匹馬在歷史賽事中的裝備變化。

**價值**

- 有助於分析馬匹表現與裝備關係。

**風險**

- 需先確認歷史來源頁是否完整提供裝備資料。
- 若裝備縮寫規則不一致，需額外正規化。

**啟動條件**

- `gear` 欄位已在主要來源中穩定抓取。
- 已確認裝備縮寫字典。

### 15.6 P3：低優先級或成熟期擴充

#### 15.6.1 同場更多賽事分析資料

**目標**

- 補充更多非核心但具分析價值的同場資料。

**可能方向**

- 更多賽事分析頁
- 額外報告頁
- 可視化輔助欄位

**啟動條件**

- 核心三類來源完整穩定。
- 主要回填與 QA 流程成熟。

#### 15.6.2 資料品質儀表板

**目標**

- 建立更完整的系統層可視化監控。

**建議內容**

- 批次執行趨勢
- 各來源成功率
- 長期失敗熱點
- 常見錯誤碼統計

**啟動條件**

- 批次執行、重試與錯誤碼資料已累積。

#### 15.6.3 進階查詢與分析輸出

**目標**

- 提供面向分析使用者的聚合查詢、匯出與對比能力。

**可能方向**

- 逐馬歷史補充資料整合檢視
- 按賽日或場次匯出完整補充資料
- 比對不同來源的覆蓋率與完整率

**啟動條件**

- 基礎資料表穩定。
- 核心資料缺漏率已下降至可接受範圍。

### 15.7 擴充時的設計原則

- 新增來源前，必須先補充到 `附錄 A：HKJC 來源頁面規格表`
- 新增資料表前，必須先補充到 `附錄 B：建議資料表與欄位字典`
- 新增回填邏輯前，必須先更新 `附錄 C：去重與回填 SOP`
- 不得直接把派生分析欄位混入原始來源表，除非手冊已明確定義

### 15.8 不建議在第一版提前做的事項

- 以 NLP 或模型自動摘要全文報告
- 對未直接提供的欄位做大量推導
- 尚未穩定前就加入大量新來源頁
- 在未完成 QA 前先做複雜前端展示
- 在未完成 registry 與回填流程前直接做全量自動排程

### 15.9 建議擴充順序

第一版穩定後建議順序如下：

1. 先做缺漏場次追蹤
2. 再做手動重抓工具
3. 接著做抓取完成率報表
4. 然後再考慮研訊摘要與獸醫標記
5. 最後才做進階分析與儀表板

### 15.10 可直接寫入手冊的正式文字

- 本系統後續擴充應遵循「先穩定核心資料流，再增加可視性與分析能力」的原則。第一優先級擴充應聚焦於缺漏追蹤、手動重抓與完成率統計，以提升資料補全效率與維運透明度；第二優先級擴充才逐步加入研訊摘要、獸醫相關標記與裝備變更等高語意資料；至於分析型輸出與儀表板，應待核心來源、去重邏輯、回填流程與 QA 已穩定後再展開，以避免在基礎資料尚未成熟前過度擴張系統邊界。

## 附錄 A：HKJC 來源頁面規格表

### A1. 競賽事件報告

- 用途：取得某一賽日、每一場、全場所有馬匹的競賽事件報告文字
- 路徑：`/zh-hk/local/information/racereportfull`
- 格式：`https://racing.hkjc.com/zh-hk/local/information/racereportfull?Date=YYYY/MM/DD`
- 粒度：逐賽日頁面，頁內包含該日全部場次
- 主要欄位：
  - `race_date`
  - `race_no`
  - `race_index`
  - `race_name`
  - `class`
  - `distance`
  - `placing`
  - `horse_no`
  - `horse_id`
  - `horse_name`
  - `draw`
  - `jockey_id`
  - `jockey_name`
  - `incident_report_text`

### A2. 沿路走勢評述

- 用途：取得某一賽日某一場、全場所有馬匹的走勢評述
- 路徑：`/zh-hk/local/information/corunning`
- 格式：`https://racing.hkjc.com/zh-hk/local/information/corunning?Date=YYYYMMDD&raceno=N`
- 粒度：逐場頁面
- 主要欄位：
  - `race_date`
  - `race_no`
  - `race_index`
  - `race_name`
  - `rating_range`
  - `distance`
  - `racecourse`
  - `going`
  - `placing`
  - `horse_no`
  - `horse_id`
  - `horse_name`
  - `jockey_name`
  - `gear`
  - `running_comment_text`

### A3. 分段時間及位置

- 用途：取得某一賽日某一場的場次完成時間、整體分段時間，以及全場所有馬匹的分段時間、分段排名或位置資訊
- 路徑：`/zh-hk/local/information/displaysectionaltime`
- 格式：`https://racing.hkjc.com/zh-hk/local/information/displaysectionaltime?racedate=DD/MM/YYYY&RaceNo=N`
- 粒度：逐場頁面
- 主要欄位：
  - `race_date`
  - `race_no`
  - `class`
  - `distance`
  - `rating_range`
  - `surface`
  - `course`
  - `going`
  - `race_name`
  - `race_finish_time`
  - `horse_no`
  - `horse_id`
  - `horse_name`
  - `finish_position`
  - `finish_time`
  - `section_position`
  - `distance_from_leader`
  - `horse_sectional_times`
  - `sub_section_times`

## 附錄 B：建議資料表與欄位字典

### B1. `horse_race_history`

- 用途：保存馬匹歷史出賽索引，作為待抓場次清單的來源
- 唯一鍵：`horse_id + race_date + race_no`

建議欄位：

- `id`
- `horse_id`
- `horse_code`
- `horse_name`
- `race_date`
- `race_no`
- `racecourse`
- `race_name`
- `distance_m`
- `class_name`
- `placing`
- `draw`
- `jockey_name`
- `trainer_name`
- `source_url`
- `scraped_at`

### B2. `race_sectional_summary`

- 用途：保存某一場的場次完成時間與整體分段時間
- 唯一鍵：`race_date + race_no`

建議欄位：

- `id`
- `race_date`
- `race_no`
- `race_index`
- `race_name`
- `racecourse`
- `surface`
- `course_code`
- `going`
- `class_name`
- `distance_m`
- `rating_range`
- `section_count`
- `race_finish_time`
- `race_cumulative_time_1` 至 `race_cumulative_time_6`
- `race_section_time_1` 至 `race_section_time_6`
- `source_url`
- `scraped_at`

規則：

- 若某場只有 5 段，則第 6 段相關欄位一律填 `null`

### B3. `horse_sectional_detail`

- 用途：保存某一場每匹馬的完成時間、各分段時間、分段排名或位置資料
- 唯一鍵：`race_date + race_no + horse_id`

建議欄位：

- `id`
- `race_date`
- `race_no`
- `horse_id`
- `horse_code`
- `horse_name`
- `horse_no`
- `finish_position`
- `finish_time`
- `section_count`
- `horse_position_1` 至 `horse_position_6`
- `horse_distance_from_leader_1` 至 `horse_distance_from_leader_6`
- `horse_section_time_1` 至 `horse_section_time_6`
- `horse_section_rank_1` 至 `horse_section_rank_6`
- `horse_split_time_1a` 至 `horse_split_time_6b`
- `source_url`
- `scraped_at`

規則：

- 若頁面未直接提供 `分段排名`，第一版先填 `null`
- 固定 6 段輸出，不足段數一律補 `null`

### B4. `horse_incident_report`

- 用途：保存某一場每匹馬的競賽事件報告
- 唯一鍵：`race_date + race_no + horse_id`

建議欄位：

- `id`
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
- `source_url`
- `scraped_at`

### B5. `horse_running_comment`

- 用途：保存某一場每匹馬的沿路走勢評述
- 唯一鍵：`race_date + race_no + horse_id`

建議欄位：

- `id`
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
- `source_url`
- `scraped_at`

### B6. `race_fetch_registry`

- 用途：記錄某一場哪些來源已抓取、是否成功、是否可重試
- 唯一鍵：`race_date + race_no + source_type`

建議欄位：

- `id`
- `race_date`
- `race_no`
- `source_type`
- `fetch_status`
- `record_count`
- `content_hash`
- `source_url`
- `last_error`
- `first_fetched_at`
- `last_fetched_at`
- `expected_horse_count`
- `retry_count`
- `parse_warning`

## 附錄 C：去重與回填 SOP

### C1. 目的

- 規範 HKJC 歷史補充資料的去重、補抓、回填與重試流程。

### C2. 核心原則

- 以場次為抓取單位，不以單一馬匹為抓取單位。
- 只要定位到某場，即抓取並保存該場全部馬匹資料。
- 所有寫入都必須先做唯一鍵檢查。
- 已存在資料預設跳過，不重複儲存。
- 抓取失敗、頁面缺漏、解析異常，必須記錄，不可用 `null` 假裝成功。
- 場次層資料與逐馬層資料要分開判斷是否完整。

### C3. 去重標準

- `horse_race_history`：`horse_id + race_date + race_no`
- `race_sectional_summary`：`race_date + race_no`
- `horse_sectional_detail`：`race_date + race_no + horse_id`
- `horse_incident_report`：`race_date + race_no + horse_id`
- `horse_running_comment`：`race_date + race_no + horse_id`
- `race_fetch_registry`：`race_date + race_no + source_type`

### C4. 回填流程總則

1. 從現有賽果資料與馬匹歷史資料整理待抓場次清單
2. 對待抓場次逐場檢查 `race_fetch_registry`
3. 判斷哪些來源尚未抓取或抓取失敗
4. 只針對缺失來源重新抓取
5. 解析後逐表做唯一鍵去重
6. 寫入成功後更新抓取狀態
7. 保留失敗紀錄供後續重試

### C5. 狀態定義

- `pending`
- `success`
- `failed`
- `partial`

### C6. 部分成功原則

- 第一版系統應允許部分成功資料落地。
- 若僅部分馬匹資料成功，保留成功資料，將來源標記為 `partial`，留待後續重試補齊。

### C7. `null` 與失敗的區分

- `null` 僅表示該段不存在、該頁未提供欄位、或該欄位確實為空
- `null` 不表示頁面抓不到、parser 壞掉、寫入失敗或內容不完整
- 流程異常必須記錄於 `race_fetch_registry.fetch_status` 與 `race_fetch_registry.last_error`
