-- Add proxy_url column if missing
ALTER TABLE aws_credentials ADD COLUMN IF NOT EXISTS proxy_url TEXT;

-- ==========================================
-- FIX PERMISSIONS (RLS POLICIES)
-- ==========================================

-- 1. Enable RLS on the table (just in case)
ALTER TABLE aws_credentials ENABLE ROW LEVEL SECURITY;

-- 2. Allow Users to UPDATE their own data
-- First, drop the old policy to avoid conflict errors
DROP POLICY IF EXISTS "Users can update own credentials" ON aws_credentials;

-- Create the new policy
CREATE POLICY "Users can update own credentials" ON aws_credentials
    FOR UPDATE
    USING (auth.uid() = user_id);

-- 3. Verify INSERT policy (ensure it exists)
DROP POLICY IF EXISTS "Users can insert own credentials" ON aws_credentials;
CREATE POLICY "Users can insert own credentials" ON aws_credentials
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 4. Verify SELECT policy
DROP POLICY IF EXISTS "Users can view own credentials" ON aws_credentials;
CREATE POLICY "Users can view own credentials" ON aws_credentials
    FOR SELECT
    USING (auth.uid() = user_id);

-- 5. Verify DELETE policy
DROP POLICY IF EXISTS "Users can delete own credentials" ON aws_credentials;
CREATE POLICY "Users can delete own credentials" ON aws_credentials
    FOR DELETE
    USING (auth.uid() = user_id);
