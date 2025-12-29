-- 1. 更新 Profiles 表，添加 role 字段
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user';

-- 2. 修复指定账号的 Profile (如果不存在则插入，存在则更新为 admin)
INSERT INTO profiles (id, email, balance, role, membership_tier)
VALUES (
    'b2764540-6cbf-42ef-bde8-051339f5e46c', 
    'eminemlose88@gmail.com', 
    1000.0000, 
    'admin',   
    'pro'      
)
ON CONFLICT (id) DO UPDATE SET
    role = 'admin',
    email = EXCLUDED.email; 

-- 3. 修复 RLS 策略 (关键修改)

-- 必须先删除旧策略，否则会报错或产生冲突
DROP POLICY IF EXISTS "Users can view own profile" ON profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON profiles;
DROP POLICY IF EXISTS "Admins can update all profiles" ON profiles;
DROP POLICY IF EXISTS "Admins can view all billing logs" ON billing_logs;
DROP POLICY IF EXISTS "Admins can view all transactions" ON transactions;
DROP POLICY IF EXISTS "Admins can view all instances" ON instances;

-- 策略 1: 基础用户策略 - 允许用户查看自己的所有信息 (包括 role)
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

-- 策略 2: 管理员查看策略 - 避免递归死锁
-- 注意：这里不能直接 SELECT role FROM profiles，因为这会触发 RLS 自身
-- 解决方案：使用 SECURITY DEFINER 函数来安全地检查管理员权限

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM profiles 
    WHERE id = auth.uid() AND role = 'admin'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 现在使用 is_admin() 函数来定义策略

-- Profiles 表策略
CREATE POLICY "Admins can view all profiles" ON profiles
    FOR SELECT USING (is_admin());

CREATE POLICY "Admins can update all profiles" ON profiles
    FOR UPDATE USING (is_admin());

-- Billing Logs 表策略
CREATE POLICY "Admins can view all billing logs" ON billing_logs
    FOR SELECT USING (is_admin());

-- Transactions 表策略
CREATE POLICY "Admins can view all transactions" ON transactions
    FOR SELECT USING (is_admin());

-- Instances 表策略
CREATE POLICY "Admins can view all instances" ON instances
    FOR SELECT USING (is_admin());
