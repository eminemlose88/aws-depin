-- 修复 "Could not find a relationship" 错误
-- 原因：Supabase (PostgREST) 需要明确的外键约束才能进行表连接查询 (Join)。
-- 虽然 transactions 和 profiles 都关联了 auth.users，但它们之间没有直接关联。
-- 我们需要手动添加外键约束，告诉数据库 transactions.user_id 对应 profiles.id。

-- 1. 为 transactions 表添加关联到 profiles 的外键
ALTER TABLE transactions
DROP CONSTRAINT IF EXISTS fk_transactions_profiles; -- 防止重复报错

ALTER TABLE transactions
ADD CONSTRAINT fk_transactions_profiles
FOREIGN KEY (user_id)
REFERENCES profiles (id)
ON DELETE CASCADE;

-- 2. 为 billing_logs 表添加关联到 profiles 的外键 (用于财务统计)
ALTER TABLE billing_logs
DROP CONSTRAINT IF EXISTS fk_billing_logs_profiles;

ALTER TABLE billing_logs
ADD CONSTRAINT fk_billing_logs_profiles
FOREIGN KEY (user_id)
REFERENCES profiles (id)
ON DELETE CASCADE;

-- 3. 为 instances 表添加关联到 profiles 的外键 (用于显示实例归属)
ALTER TABLE instances
DROP CONSTRAINT IF EXISTS fk_instances_profiles;

ALTER TABLE instances
ADD CONSTRAINT fk_instances_profiles
FOREIGN KEY (user_id)
REFERENCES profiles (id)
ON DELETE CASCADE;

-- 4. 刷新 PostgREST 缓存 (让更改立即生效)
NOTIFY pgrst, 'reload config';
