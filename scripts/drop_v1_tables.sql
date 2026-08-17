-- =====================================================
-- 清理舊版資料庫腳本 (Drop Legacy V1 Tables)
-- 執行時機：
-- 1. 確認 races_v2 / horses_v2 已經成功建立並同步完所有資料。
-- 2. 在 Railway Postgres 的 SQL Console 或 psql 執行以下指令。
-- =====================================================

DROP TABLE IF EXISTS horses CASCADE;
DROP TABLE IF EXISTS races CASCADE;

-- (可選) 檢查剩餘的資料表，確認僅剩 V2 版本
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';
