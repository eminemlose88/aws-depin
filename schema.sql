-- 1. 启用 UUID 扩展 (如果尚未启用)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. 创建 AWS 凭证表 (AWS Credentials)
-- 允许一个用户绑定多个 AWS AKa
CREATE TABLE IF NOT EXISTS aws_credentials (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    alias_name TEXT, -- 给这个 AK 起个名字，比如 "公司账号", "个人测试"
    access_key_id TEXT NOT NULL,
    secret_access_key TEXT NOT NULL, -- 注意：生产环境建议加密存储，这里简化处理
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    UNIQUE(user_id, access_key_id)
);

-- 3. 更新 instances 表 (Instances)
-- 不再直接存 AK，而是关联 user_id 和 aws_credential_id
-- 如果之前有数据，需要先清空或手动迁移，这里使用 DROP TABLE 重建以确保结构正确
DROP TABLE IF EXISTS instances;

CREATE TABLE IF NOT EXISTS instances (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    credential_id UUID REFERENCES aws_credentials(id) ON DELETE SET NULL, -- 关联具体的 AK
    instance_id TEXT NOT NULL,
    ip_address TEXT,
    region TEXT NOT NULL,
    project_name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 4. 创建索引
CREATE INDEX IF NOT EXISTS idx_aws_credentials_user ON aws_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_instances_user ON instances(user_id);

-- 5. 开启 RLS (Row Level Security) - 安全关键！
-- 确保用户只能查改自己的数据

ALTER TABLE aws_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE instances ENABLE ROW LEVEL SECURITY;

-- 策略：AWS 凭证表
CREATE POLICY "Users can view own credentials" ON aws_credentials
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own credentials" ON aws_credentials
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own credentials" ON aws_credentials
    FOR DELETE USING (auth.uid() = user_id);

-- 策略：实例表
CREATE POLICY "Users can view own instances" ON instances
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own instances" ON instances
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own instances" ON instances
    FOR UPDATE USING (auth.uid() = user_id);
