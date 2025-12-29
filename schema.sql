-- Create instances table
CREATE TABLE IF NOT EXISTS instances (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    access_key_id TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    ip_address TEXT,
    region TEXT NOT NULL,
    project_name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Create index for faster lookup by access_key_id
CREATE INDEX IF NOT EXISTS idx_instances_ak ON instances(access_key_id);

-- Optional: Enable Row Level Security (RLS) if you want to restrict access further
-- For now, we assume the backend handles logic.
