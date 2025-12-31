-- 1. Add boolean columns for each project
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_titan BOOLEAN DEFAULT FALSE;
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_nexus BOOLEAN DEFAULT FALSE;
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_shardeum BOOLEAN DEFAULT FALSE;
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_babylon BOOLEAN DEFAULT FALSE;
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_meson BOOLEAN DEFAULT FALSE;
ALTER TABLE instances ADD COLUMN IF NOT EXISTS proj_proxy BOOLEAN DEFAULT FALSE;

-- 2. Migrate existing data (Best effort mapping)
UPDATE instances SET proj_titan = TRUE WHERE project_name ILIKE '%Titan%';
UPDATE instances SET proj_nexus = TRUE WHERE project_name ILIKE '%Nexus%';
UPDATE instances SET proj_shardeum = TRUE WHERE project_name ILIKE '%Shardeum%';
UPDATE instances SET proj_babylon = TRUE WHERE project_name ILIKE '%Babylon%';
UPDATE instances SET proj_meson = TRUE WHERE project_name ILIKE '%Meson%' OR project_name ILIKE '%GagaNode%';
UPDATE instances SET proj_proxy = TRUE WHERE project_name ILIKE '%Proxy%' OR project_name ILIKE '%Dante%' OR project_name ILIKE '%Squid%';

-- 3. Drop the old column
-- ALTER TABLE instances DROP COLUMN project_name;
-- (Commented out for safety, user can uncomment to execute final cleanup)
