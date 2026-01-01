-- ==========================================
-- FIX PERMISSIONS FOR 'instances' TABLE
-- ==========================================

-- 1. Enable RLS on the table (just in case)
ALTER TABLE instances ENABLE ROW LEVEL SECURITY;

-- 2. DELETE Policy (Crucial for removing terminated instances)
DROP POLICY IF EXISTS "Users can delete own instances" ON instances;
CREATE POLICY "Users can delete own instances" ON instances
    FOR DELETE
    USING (auth.uid() = user_id);

-- 3. UPDATE Policy
DROP POLICY IF EXISTS "Users can update own instances" ON instances;
CREATE POLICY "Users can update own instances" ON instances
    FOR UPDATE
    USING (auth.uid() = user_id);

-- 4. INSERT Policy
DROP POLICY IF EXISTS "Users can insert own instances" ON instances;
CREATE POLICY "Users can insert own instances" ON instances
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 5. SELECT Policy
DROP POLICY IF EXISTS "Users can view own instances" ON instances;
CREATE POLICY "Users can view own instances" ON instances
    FOR SELECT
    USING (auth.uid() = user_id);
