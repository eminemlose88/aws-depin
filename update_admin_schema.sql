-- 1. 更新 Profiles 表，添加 role 字段
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user';

-- 2. 修复指定账号的 Profile (如果不存在则插入，存在则更新为 admin)
-- 你的 UID: b2764540-6cbf-42ef-bde8-051339f5e46c
-- 你的 Email: eminemlose88@gmail.com

INSERT INTO profiles (id, email, balance, role, membership_tier)
VALUES (
    'b2764540-6cbf-42ef-bde8-051339f5e46c', 
    'eminemlose88@gmail.com', 
    1000.0000, -- 初始赠送余额方便测试
    'admin',   -- 设置为管理员
    'pro'      -- 顶级会员
)
ON CONFLICT (id) DO UPDATE SET
    role = 'admin',
    email = EXCLUDED.email; -- 确保邮箱同步

-- 3. 确保管理员可以管理所有人的数据 (RLS 策略更新)
-- Supabase 的 RLS 默认是很严格的，我们需要允许 admin 角色查看所有行

-- 更新 Profiles 策略
CREATE POLICY "Admins can view all profiles" ON profiles
    FOR SELECT USING (
        (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

CREATE POLICY "Admins can update all profiles" ON profiles
    FOR UPDATE USING (
        (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

-- 更新 Billing Logs 策略
CREATE POLICY "Admins can view all billing logs" ON billing_logs
    FOR SELECT USING (
        (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

-- 更新 Transactions 策略
CREATE POLICY "Admins can view all transactions" ON transactions
    FOR SELECT USING (
        (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

-- 更新 Instances 策略
CREATE POLICY "Admins can view all instances" ON instances
    FOR SELECT USING (
        (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );
