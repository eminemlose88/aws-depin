-- Add proxy_url column to aws_credentials table if it doesn't exist
ALTER TABLE aws_credentials ADD COLUMN IF NOT EXISTS proxy_url TEXT;

-- Verify RLS policies (Ensure users can UPDATE their own rows)
-- This is often missed when switching from INSERT to UPSERT
DROP POLICY IF EXISTS "Users can update own credentials" ON aws_credentials;
CREATE POLICY "Users can update own credentials" ON aws_credentials
    FOR UPDATE USING (auth.uid() = user_id);
