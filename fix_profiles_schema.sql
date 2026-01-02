-- Fix profiles table schema for Streamlit Authenticator
-- 1. Ensure columns exist
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS username TEXT UNIQUE;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS password TEXT;

-- 2. Force PostgREST schema cache reload (CRITICAL for PGRST204 error)
NOTIFY pgrst, 'reload schema';
