-- 1. Create aws_instance_types table
CREATE TABLE IF NOT EXISTS aws_instance_types (
    instance_type TEXT PRIMARY KEY,
    vcpu INT,
    memory_gb FLOAT,
    category TEXT,
    arch TEXT DEFAULT 'x86_64'
);

-- 2. Add columns to instances table
ALTER TABLE instances 
ADD COLUMN IF NOT EXISTS instance_type TEXT,
ADD COLUMN IF NOT EXISTS vcpu_count INT,
ADD COLUMN IF NOT EXISTS memory_gb FLOAT,
ADD COLUMN IF NOT EXISTS os_name TEXT,
ADD COLUMN IF NOT EXISTS disk_info TEXT;

-- 3. Insert Instance Data (General Purpose - T, M)
INSERT INTO aws_instance_types (instance_type, vcpu, memory_gb, category, arch) VALUES
('t2.nano', 1, 0.5, 'General Purpose', 'x86_64'),
('t2.micro', 1, 1, 'General Purpose', 'x86_64'),
('t2.small', 1, 2, 'General Purpose', 'x86_64'),
('t2.medium', 2, 4, 'General Purpose', 'x86_64'),
('t2.large', 2, 8, 'General Purpose', 'x86_64'),
('t2.xlarge', 4, 16, 'General Purpose', 'x86_64'),
('t2.2xlarge', 8, 32, 'General Purpose', 'x86_64'),

('t3.nano', 2, 0.5, 'General Purpose', 'x86_64'),
('t3.micro', 2, 1, 'General Purpose', 'x86_64'),
('t3.small', 2, 2, 'General Purpose', 'x86_64'),
('t3.medium', 2, 4, 'General Purpose', 'x86_64'),
('t3.large', 2, 8, 'General Purpose', 'x86_64'),
('t3.xlarge', 4, 16, 'General Purpose', 'x86_64'),
('t3.2xlarge', 8, 32, 'General Purpose', 'x86_64'),

('m5.large', 2, 8, 'General Purpose', 'x86_64'),
('m5.xlarge', 4, 16, 'General Purpose', 'x86_64'),
('m5.2xlarge', 8, 32, 'General Purpose', 'x86_64'),
('m5.4xlarge', 16, 64, 'General Purpose', 'x86_64'),
('m5.8xlarge', 32, 128, 'General Purpose', 'x86_64'),
('m5.12xlarge', 48, 192, 'General Purpose', 'x86_64'),
('m5.16xlarge', 64, 256, 'General Purpose', 'x86_64'),
('m5.24xlarge', 96, 384, 'General Purpose', 'x86_64'),

('m6i.large', 2, 8, 'General Purpose', 'x86_64'),
('m6i.xlarge', 4, 16, 'General Purpose', 'x86_64'),
('m6i.2xlarge', 8, 32, 'General Purpose', 'x86_64'),
('m6i.4xlarge', 16, 64, 'General Purpose', 'x86_64'),
('m6i.8xlarge', 32, 128, 'General Purpose', 'x86_64'),

('m7i.large', 2, 8, 'General Purpose', 'x86_64'),
('m7i.xlarge', 4, 16, 'General Purpose', 'x86_64'),
('m7i.2xlarge', 8, 32, 'General Purpose', 'x86_64'),

-- Compute Optimized (C)
('c5.large', 2, 4, 'Compute Optimized', 'x86_64'),
('c5.xlarge', 4, 8, 'Compute Optimized', 'x86_64'),
('c5.2xlarge', 8, 16, 'Compute Optimized', 'x86_64'),
('c5.4xlarge', 16, 32, 'Compute Optimized', 'x86_64'),
('c5.9xlarge', 36, 72, 'Compute Optimized', 'x86_64'),
('c5.12xlarge', 48, 96, 'Compute Optimized', 'x86_64'),
('c5.18xlarge', 72, 144, 'Compute Optimized', 'x86_64'),
('c5.24xlarge', 96, 192, 'Compute Optimized', 'x86_64'),

('c6i.large', 2, 4, 'Compute Optimized', 'x86_64'),
('c6i.xlarge', 4, 8, 'Compute Optimized', 'x86_64'),
('c6i.2xlarge', 8, 16, 'Compute Optimized', 'x86_64'),
('c6i.4xlarge', 16, 32, 'Compute Optimized', 'x86_64'),
('c6i.8xlarge', 32, 64, 'Compute Optimized', 'x86_64'),

('c7i.large', 2, 4, 'Compute Optimized', 'x86_64'),
('c7i.xlarge', 4, 8, 'Compute Optimized', 'x86_64'),
('c7i.2xlarge', 8, 16, 'Compute Optimized', 'x86_64'),

-- Memory Optimized (R)
('r5.large', 2, 16, 'Memory Optimized', 'x86_64'),
('r5.xlarge', 4, 32, 'Memory Optimized', 'x86_64'),
('r5.2xlarge', 8, 64, 'Memory Optimized', 'x86_64'),
('r5.4xlarge', 16, 128, 'Memory Optimized', 'x86_64'),
('r5.8xlarge', 32, 256, 'Memory Optimized', 'x86_64'),
('r5.12xlarge', 48, 384, 'Memory Optimized', 'x86_64'),
('r5.16xlarge', 64, 512, 'Memory Optimized', 'x86_64'),
('r5.24xlarge', 96, 768, 'Memory Optimized', 'x86_64'),

('r6i.large', 2, 16, 'Memory Optimized', 'x86_64'),
('r6i.xlarge', 4, 32, 'Memory Optimized', 'x86_64'),
('r6i.2xlarge', 8, 64, 'Memory Optimized', 'x86_64'),
('r6i.4xlarge', 16, 128, 'Memory Optimized', 'x86_64'),
('r6i.8xlarge', 32, 256, 'Memory Optimized', 'x86_64'),

-- Accelerated Computing (G, P)
('g4dn.xlarge', 4, 16, 'Accelerated Computing', 'x86_64'),
('g4dn.2xlarge', 8, 32, 'Accelerated Computing', 'x86_64'),
('g4dn.4xlarge', 16, 64, 'Accelerated Computing', 'x86_64'),
('g4dn.8xlarge', 32, 128, 'Accelerated Computing', 'x86_64'),
('g4dn.12xlarge', 48, 192, 'Accelerated Computing', 'x86_64'),
('g4dn.16xlarge', 64, 256, 'Accelerated Computing', 'x86_64'),

('g5.xlarge', 4, 16, 'Accelerated Computing', 'x86_64'),
('g5.2xlarge', 8, 32, 'Accelerated Computing', 'x86_64'),
('g5.4xlarge', 16, 64, 'Accelerated Computing', 'x86_64'),
('g5.8xlarge', 32, 128, 'Accelerated Computing', 'x86_64'),
('g5.12xlarge', 48, 192, 'Accelerated Computing', 'x86_64'),
('g5.16xlarge', 64, 256, 'Accelerated Computing', 'x86_64'),
('g5.24xlarge', 96, 384, 'Accelerated Computing', 'x86_64'),
('g5.48xlarge', 192, 768, 'Accelerated Computing', 'x86_64'),

('p3.2xlarge', 8, 61, 'Accelerated Computing', 'x86_64'),
('p3.8xlarge', 32, 244, 'Accelerated Computing', 'x86_64'),
('p3.16xlarge', 64, 488, 'Accelerated Computing', 'x86_64')

ON CONFLICT (instance_type) DO NOTHING;
