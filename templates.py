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
