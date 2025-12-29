import base64

PROJECT_REGISTRY = {
    "Titan Network": {
        "description": "Titan Edge Mining Node (Docker based)",
        "params": ["identity_code"],
        "script_template": """#!/bin/bash
yum update -y
yum install -y docker
service docker start
systemctl enable docker
docker pull nezha123/titan-edge
sleep 20
# Run the container first
docker run -d --restart always --network host --name titan-edge -v ~/.titanedge:/root/.titanedge nezha123/titan-edge
# Wait a bit for container to be fully up
sleep 10
# Execute bind command
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
    "Shardeum_Titan_Combo": {
        "description": "Alpha Fleet: Shardeum Validator + Titan Network (Camouflage)",
        "params": ["identity_code", "dashboard_password"],
        "script_template": """#!/bin/bash
# 1. System Updates & Docker Install
yum update -y
yum install -y docker curl
service docker start
systemctl enable docker
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 2. Start Titan Network (Camouflage) - Memory Limited 2GB
docker pull nezha123/titan-edge
docker run -d --restart always --network host --memory="2g" --name titan-edge -v ~/.titanedge:/root/.titanedge nezha123/titan-edge
sleep 15
docker exec titan-edge titan-edge bind --hash={identity_code} https://api-test1.container1.titannet.io/api/v2/device/binding

# 3. Prepare Shardeum Environment
export RHOME="/root"
export SERVERIP="$(curl -s ifconfig.me)"
export LOCALLANIP="$(curl -s ifconfig.me)"
export SHMEXT="9001"
export SHMINT="10001"
export DASHPORT="8080"
export P2PPORT="9000"

# 4. Download Shardeum Installer
curl -O https://gitlab.com/shardeum/validator/dashboard/-/raw/main/installer.sh
chmod +x installer.sh

# 5. Run Installer Non-Interactively
# Pipe inputs: y (dashboard), password, confirm password, port, y (listen), y (remote)
printf "y\\n{dashboard_password}\\n{dashboard_password}\\n$DASHPORT\\ny\\ny\\n" | ./installer.sh

# 6. Start the Validator
cd $RHOME/.shardeum
./shell.sh operator-cli start

echo "Deployment Complete. Dashboard: https://$SERVERIP:$DASHPORT"
"""
    },
    "Babylon_Traffmonetizer_Combo": {
        "description": "Beta Fleet: Babylon Node + Traffmonetizer (Camouflage)",
        "params": ["traffmonetizer_token"],
        "script_template": """#!/bin/bash
# 1. System Updates & Docker Install
yum update -y
yum install -y docker jq
service docker start
systemctl enable docker

# 2. Start Traffmonetizer (Camouflage)
docker pull traffmonetizer/cli_v2
docker run -d --restart always --name traffmonetizer traffmonetizer/cli_v2 start accept --token {traffmonetizer_token}

# 3. Install Babylon Node (Pre-built Binary)
cd /root
# Download binary (v0.8.3 example, check for updates)
wget https://github.com/babylonchain/babylon/releases/download/v0.8.3/babylond_v0.8.3_linux_amd64.tar.gz
tar -xvf babylond_v0.8.3_linux_amd64.tar.gz
mv babylond_v0.8.3_linux_amd64/bin/babylond /usr/local/bin/
rm -rf babylond_v0.8.3_linux_amd64*

# Initialize Node
CHAIN_ID="bbn-test-3"
MONIKER="MyDePINNode_$(date +%s)"
babylond init $MONIKER --chain-id $CHAIN_ID

# Download Genesis
wget https://github.com/babylonchain/networks/raw/main/bbn-test-3/genesis.tar.bz2
tar -xjf genesis.tar.bz2 && rm genesis.tar.bz2
mv genesis.json ~/.babylond/config/genesis.json

# Set Peers (Optional but recommended, using public peers)
PEERS="49b4685f16670e784a0fe78f37cd83d5442984c2@198.244.179.31:26656,8da45f9ff83b4f8dd45bbcb4f850999637fbfe3b@121.75.131.236:26656"
sed -i "s/^persistent_peers *=.*/persistent_peers = \\"$PEERS\\"/;" ~/.babylond/config/config.toml

# Create Systemd Service
cat <<EOF > /etc/systemd/system/babylond.service
[Unit]
Description=Babylon Node
After=network-online.target

[Service]
User=root
ExecStart=/usr/local/bin/babylond start
Restart=always
RestartSec=3
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

# Start Service
systemctl daemon-reload
systemctl enable babylond
systemctl start babylond
"""
    },
    "Dante_Socks5_Proxy": {
        "description": "Standard SOCKS5 Proxy Server (Dante)",
        "params": ["proxy_user", "proxy_password", "proxy_port"],
        "script_template": """#!/bin/bash
# ... (Existing Dante Template) ...
yum install -y http://mirror.ghettoforge.org/distributions/gf/gf-release-latest.gf.el7.noarch.rpm
yum install -y dante-server

# Backup original config
cp /etc/sockd.conf /etc/sockd.conf.bak

# Create Config
cat <<EOF > /etc/sockd.conf
logoutput: syslog
user.privileged: root
user.unprivileged: nobody

# The listening network interface or address.
internal: 0.0.0.0 port = {proxy_port}

# The proxying network interface or address.
external: eth0

# socksmethod: username none # No auth
socksmethod: username

# Client access rules
client pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error # connect disconnect
}

# Server operation rules
socks pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: error # connect disconnect
}
EOF

# Create User
useradd {proxy_user}
echo "{proxy_password}" | passwd --stdin {proxy_user}

# Open Port in Firewall (if firewalld is running, though AWS SG handles it mostly)
systemctl start firewalld
firewall-cmd --zone=public --add-port={proxy_port}/tcp --permanent
firewall-cmd --reload

# Start Service
systemctl enable sockd
systemctl start sockd
"""
    },
    "Squid_HTTP_Proxy": {
        "description": "Authenticated HTTP Proxy (Squid)",
        "params": ["proxy_user", "proxy_password"],
        "script_template": """#!/bin/bash
# Install Squid and htpasswd tool
yum update -y
yum install -y squid httpd-tools

# Create Password File
htpasswd -b -c /etc/squid/passwd {proxy_user} {proxy_password}

# Configure Squid
mv /etc/squid/squid.conf /etc/squid/squid.conf.bak

cat <<EOF > /etc/squid/squid.conf
# Auth Configuration
auth_param basic program /usr/lib64/squid/basic_ncsa_auth /etc/squid/passwd
auth_param basic children 5
auth_param basic realm Squid Basic Authentication
auth_param basic credentialsttl 2 hours
acl auth_users proxy_auth REQUIRED

# Access Control
http_access allow auth_users
http_access deny all

# Port
http_port 3128

# Hide headers for anonymity
forwarded_for off
request_header_access Via deny all
request_header_access X-Forwarded-For deny all
EOF

# Start Service
systemctl enable squid
systemctl start squid
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
