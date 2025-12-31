import base64

PROJECT_REGISTRY = {
    "Titan Network": {
        "description": "Titan Edge Mining Node (Docker based)",
        "params": ["identity_code"],
        "script_template": """#!/bin/bash
# Install dependencies
if [ -f /etc/debian_version ]; then
    apt-get update && apt-get install -y docker.io curl
    systemctl start docker
    systemctl enable docker
else
    yum update -y && yum install -y docker curl
    service docker start
    systemctl enable docker
fi

# Pull Image
docker pull nezha123/titan-edge

# Wait for network/docker
sleep 10

# Run the container
# Use host network for better connectivity or bridge if needed. Host is simpler for binding.
# Volume mapping ensures identity persists.
docker run -d --restart always --network host --name titan-edge \
  -v ~/.titanedge:/root/.titanedge \
  nezha123/titan-edge

# Wait for container initialization
sleep 15

# Bind Identity
# The key issue is that 'titan-edge bind' needs to communicate with the running daemon inside the container
# or update the config file directly.
# The official command is: titan-edge bind --hash=... https://...
docker exec titan-edge titan-edge bind --hash={identity_code} https://api-test1.container1.titannet.io/api/v2/device/binding
"""
    },
    "Meson (GagaNode)": {
        "description": "Meson Network GagaNode (Binary based)",
        "params": ["token"],
        "script_template": """#!/bin/bash
yum update -y
# Install dependencies
yum install -y curl tar ca-certificates

# Download and install GagaNode
curl -o apphub-linux-amd64.tar.gz https://assets.coreservice.io/public/package/60/app-market-gaga-pro/1.0.4/app-market-gaga-pro-1_0_4.tar.gz
tar -zxf apphub-linux-amd64.tar.gz
rm -f apphub-linux-amd64.tar.gz
cd ./apphub-linux-amd64

# Install and start service
sudo ./apphub service install
sudo ./apphub service start
sleep 10

# Set token
sudo ./apps/gaganode/gaganode config set --token={token}

# Restart to apply changes
sudo ./apphub restart
"""
    },
    "Nexus_Prover": {
        "description": "Nexus Prover (Limited to 3 vCPU / 16GB RAM)",
        "params": ["wallet_address"],
        "script_template": """#!/bin/bash
# Install dependencies
if [ -f /etc/debian_version ]; then
    apt-get update && apt-get install -y curl build-essential git unzip
else
    yum update -y && yum install -y curl git unzip
    # Install development tools group for Amazon Linux
    yum groupinstall -y "Development Tools"
fi

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Install Nexus CLI
# Using the official script which installs to ~/.nexus
curl https://cli.nexus.xyz/ | sh

# Wait for install
sleep 10

# Locate CLI Binary
# User suggested path: $HOME/.nexus/nexus-cli
# Default official path: $HOME/.nexus/bin/prover
if [ -f "$HOME/.nexus/nexus-cli" ]; then
    CLI_PATH="$HOME/.nexus/nexus-cli"
elif [ -f "$HOME/.nexus/bin/prover" ]; then
    CLI_PATH="$HOME/.nexus/bin/prover"
elif [ -f "/root/.nexus/bin/prover" ]; then
    CLI_PATH="/root/.nexus/bin/prover"
else
    # Fallback search
    CLI_PATH=$(find $HOME/.nexus -name "prover" -o -name "nexus-cli" | head -n 1)
fi

echo "Using Nexus CLI at: $CLI_PATH"

# Auto Register with Wallet
# Note: Using non-interactive mode if supported, or passing arguments directly
if [ -n "$CLI_PATH" ]; then
    # Register command provided by user
    $CLI_PATH beta-program:cli:register --wallet-address "{wallet_address}" || $CLI_PATH register-user --wallet-address "{wallet_address}" || echo "Registration command failed or not supported in this version, proceeding to start..."
fi

# Configure Systemd Service with Limits
cat <<EOF > /etc/systemd/system/nexus-prover.service
[Unit]
Description=Nexus Prover Service
After=network.target

[Service]
Type=simple
User=root
Environment=NONINTERACTIVE=1
ExecStart=$CLI_PATH start
Restart=always
RestartSec=5
# Resource Limits
CPUQuota=300%
MemoryLimit=16G

[Install]
WantedBy=multi-user.target
EOF

# Enable and Start
systemctl daemon-reload
systemctl enable nexus-prover
systemctl start nexus-prover
"""
    },
    "Nillion_Verifier": {
        "description": "Nillion Verifier (Docker, Limited to 8GB RAM)",
        "params": ["verifier_key"], 
        "script_template": """#!/bin/bash
# Ensure Docker is ready
systemctl start docker

# Pull Image
docker pull nillion/verifier:v1.0.1

# Run with Memory Limit
# Note: Adjust volume mapping as needed for your key file structure
# Here we assume the key is passed directly or handled via env for simplicity in this template
# In production, you'd likely mount a config file.
docker run -d --restart always --name nillion-verifier \\
  --memory="8g" \\
  -e VERIFIER_PRIVATE_KEY="{verifier_key}" \\
  nillion/verifier:v1.0.1 verify --rpc-endpoint "https://testnet-nillion-rpc.nillion-network.xyz"
"""
    },
    "Rivalz_rNode": {
        "description": "Rivalz rNode (Docker, Limited to 4GB RAM)",
        "params": ["wallet_address"],
        "script_template": """#!/bin/bash
# Ensure Docker is ready
systemctl start docker

# Pull Image
docker pull rivalz/rnode:latest

# Run with Memory Limit
docker run -d --restart always --name rivalz-node \\
  --memory="4g" \\
  -e WALLET_ADDRESS="{wallet_address}" \\
  rivalz/rnode:latest
"""
    },
    "Hemera_T3rn": {
        "description": "Hemera / T3rn Executor (Docker, Limited to 2GB RAM)",
        "params": ["private_key"],
        "script_template": """#!/bin/bash
# Ensure Docker is ready
systemctl start docker

# Pull Image (Example image, check official docs for latest)
docker pull t3rn/executor:latest

# Run with Memory Limit
docker run -d --restart always --name t3rn-executor \\
  --memory="2g" \\
  -e PRIVATE_KEY_EXPORT="{private_key}" \\
  -e NODE_ENV="testnet" \\
  t3rn/executor:latest
"""
    }
}

def generate_script(project_name, **kwargs):
    """
    Generate Base64 encoded User Data script for the specified project.
    """
    if project_name not in PROJECT_REGISTRY:
        raise ValueError(f"Project {project_name} not found in registry.")
    
    template = PROJECT_REGISTRY[project_name]["script_template"]
    
    # Check if all required params are provided
    required_params = PROJECT_REGISTRY[project_name]["params"]
    for param in required_params:
        if param not in kwargs or not kwargs[param]:
            raise ValueError(f"Missing required parameter: {param}")
            
    # Render the script
    script = template.format(**kwargs)
    
    # Return Base64 encoded script
    return base64.b64encode(script.encode('utf-8')).decode('utf-8')
