-- 1. 用户资料表 (Profiles)
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

-- 2. 交易流水表 (Transactions)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 4) NOT NULL, -- 正数为充值，负数为扣费
    type TEXT NOT NULL, -- deposit, daily_fee, service_fee
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 3. 每日计费日志 (Billing Logs)
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

-- 4. 索引
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_logs_user ON billing_logs(user_id);

-- 5. RLS 权限策略
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own transactions" ON transactions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own billing logs" ON billing_logs
    FOR SELECT USING (auth.uid() = user_id);

-- 6. 自动创建 Profile 触发器
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, balance)
  VALUES (new.id, new.email, 0.0000);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
