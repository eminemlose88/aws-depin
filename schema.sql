-- 1. 启用 UUID 扩展 (如果尚未启用)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. 创建 AWS 凭证表 (AWS Credentials)
-- 允许一个用户绑定多个 AWS AK
CREATE TABLE IF NOT EXISTS aws_credentials (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    alias_name TEXT, -- 给这个 AK 起个名字，比如 "公司账号", "个人测试"
    access_key_id TEXT NOT NULL,
    secret_access_key TEXT NOT NULL, -- 注意：生产环境建议加密存储，这里简化处理
    status TEXT DEFAULT 'active', -- 账号状态: active, suspended, error
    last_checked TIMESTAMP WITH TIME ZONE, -- 最后检查时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    UNIQUE(user_id, access_key_id)
);

-- 2.1 创建机型规格表 (AWS Instance Types)
CREATE TABLE IF NOT EXISTS aws_instance_types (
    instance_type TEXT PRIMARY KEY,
    vcpu INT,
    memory_gb FLOAT,
    category TEXT,
    arch TEXT DEFAULT 'x86_64'
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
    private_key TEXT, -- 加密存储的 SSH 私钥
    health_status TEXT, -- 深度健康检查状态: Healthy, Missing Container, SSH Error 等
    instance_type TEXT, -- 实例机型 (e.g. t3.medium)
    vcpu_count INT, -- CPU 核数
    memory_gb FLOAT, -- 内存大小 (GB)
    os_name TEXT, -- 操作系统名称
    disk_info TEXT, -- 硬盘信息 (e.g. 30GB gp3)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 4. 会员与计费系统表

-- 用户资料表 (Profiles)
-- 存储余额和会员状态
CREATE TABLE IF NOT EXISTS profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT,
    balance DECIMAL(10, 4) DEFAULT 0.0000, -- 余额
    membership_tier TEXT DEFAULT 'free', -- 会员等级: free, pro
    daily_request_count INT DEFAULT 0,
    last_request_reset TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    auto_replace_enabled BOOLEAN DEFAULT FALSE, -- EC2 自动替补开关
    gfw_check_enabled BOOLEAN DEFAULT FALSE, -- GFW 检测开关
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 交易流水表 (Transactions)
-- 记录充值和扣费
CREATE TABLE IF NOT EXISTS transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 4) NOT NULL, -- 正数为充值，负数为扣费
    type TEXT NOT NULL, -- deposit, daily_fee, service_fee
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 每日计费日志 (Billing Logs)
-- 记录每日结算详情
CREATE TABLE IF NOT EXISTS billing_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    base_fee DECIMAL(10, 4) DEFAULT 0,
    instance_fee DECIMAL(10, 4) DEFAULT 0,
    service_fee DECIMAL(10, 4) DEFAULT 0,
    total_fee DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    UNIQUE(user_id, date)
);

-- 触发器：新用户自动创建 Profile
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, balance)
  VALUES (new.id, new.email, 0.0000);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 绑定触发器到 Auth 表 (如果尚未绑定)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS idx_aws_credentials_user ON aws_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_instances_user ON instances(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_logs_user ON billing_logs(user_id);

-- 6. 开启 RLS (Row Level Security) - 安全关键！
-- 确保用户只能查改自己的数据

ALTER TABLE aws_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_logs ENABLE ROW LEVEL SECURITY;

-- 策略：AWS 凭证表
CREATE POLICY "Users can view own credentials" ON aws_credentials
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own credentials" ON aws_credentials
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own credentials" ON aws_credentials
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own credentials" ON aws_credentials
    FOR DELETE USING (auth.uid() = user_id);

-- 策略：实例表
CREATE POLICY "Users can view own instances" ON instances
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own instances" ON instances
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own instances" ON instances
    FOR UPDATE USING (auth.uid() = user_id);

-- 策略：Profile 表
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- 策略：Transactions 表
CREATE POLICY "Users can view own transactions" ON transactions
    FOR SELECT USING (auth.uid() = user_id);

-- 策略：Billing Logs 表
CREATE POLICY "Users can view own billing logs" ON billing_logs
    FOR SELECT USING (auth.uid() = user_id);
