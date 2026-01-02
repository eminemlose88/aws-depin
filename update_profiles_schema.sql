-- Add authentication fields to profiles table
-- This allows us to use streamlit-authenticator while keeping the same user IDs

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS username TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS password TEXT; -- Stores the hashed password

-- Ensure existing users can still be updated securely
-- The RLS policies might need a tweak to allow users to update their own 'password' field
-- (The existing "Users can update own profile" policy should cover this)

-- Create an index on username for fast lookups
CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username);
