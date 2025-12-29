import paramiko
import io
import time
import base64
import socket

def check_instance_process(ip, private_key_str, project_name):
    """
    Connect via SSH and check if the project container is running.
    Returns: (is_healthy: bool, msg: str)
    """
    if not ip or not private_key_str:
        return False, "Missing IP or Private Key"

    key_file = io.StringIO(private_key_str)
    try:
        pkey = paramiko.RSAKey.from_private_key(key_file)
    except Exception:
        # Fallback for other key types if needed, but AWS usually gives RSA
        try:
            key_file.seek(0)
            pkey = paramiko.Ed25519Key.from_private_key(key_file)
        except Exception as e:
            return False, f"Invalid Key Format: {e}"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Default user for Amazon Linux 2023 is 'ec2-user'
        client.connect(hostname=ip, username='ec2-user', pkey=pkey, timeout=10)
        
        # Check Docker containers
        # We look for the container name associated with the project
        # Simple mapping for now based on templates.py
        target_container = ""
        if "Shardeum" in project_name:
             target_container = "shardeum-dashboard"
        elif "Babylon" in project_name:
             # Babylon runs as a systemd service, so we check the process or service
             stdin, stdout, stderr = client.exec_command("systemctl is-active babylond")
             output = stdout.read().decode().strip()
             if output == "active":
                 client.close()
                 return True, "Service 'babylond' is active"
             else:
                 client.close()
                 return False, f"Service 'babylond' is {output}"
        elif "Titan" in project_name:
            target_container = "titan-edge"
        elif "Meson" in project_name:
            # Meson runs as a service usually, check process
            stdin, stdout, stderr = client.exec_command("pgrep -f gaganode")
            output = stdout.read().decode().strip()
            if output:
                client.close()
                return True, "Process 'gaganode' running"
            else:
                client.close()
                return False, "Process 'gaganode' not found"
        else:
            # Default generic check: just check if docker is alive
            target_container = "docker" 

        if target_container:
            cmd = f"sudo docker ps --format '{{{{.Names}}}}' | grep {target_container}"
            stdin, stdout, stderr = client.exec_command(cmd)
            output = stdout.read().decode().strip()
            
            client.close()
            
            if output:
                return True, f"Container '{target_container}' is running"
            else:
                return False, f"Container '{target_container}' not found"
                
        client.close()
        return True, "No specific check defined for this project (assumed healthy)"

    except Exception as e:
        return False, f"SSH Connection Failed: {str(e)}"

def detect_installed_project(ip, private_key_str):
    """
    Connect via SSH and detect if any known project is running.
    Returns: (project_name: str | None, msg: str)
    """
    if not ip or not private_key_str:
        return None, "Missing IP or Private Key"

    key_file = io.StringIO(private_key_str)
    try:
        pkey = paramiko.RSAKey.from_private_key(key_file)
    except Exception:
        try:
            key_file.seek(0)
            pkey = paramiko.Ed25519Key.from_private_key(key_file)
        except Exception as e:
            return None, f"Invalid Key: {e}"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname=ip, username='ec2-user', pkey=pkey, timeout=10)
        
        # 1. Check for Shardeum (Dashboard Container)
        stdin, stdout, stderr = client.exec_command("sudo docker ps --format '{{.Names}}' | grep shardeum-dashboard")
        if stdout.read().decode().strip():
            client.close()
            return "Shardeum_Titan_Combo", "Shardeum Dashboard found"

        # 2. Check for Babylon (System Service)
        stdin, stdout, stderr = client.exec_command("systemctl is-active babylond")
        if stdout.read().decode().strip() == "active":
             client.close()
             return "Babylon_Traffmonetizer_Combo", "Babylon Service active"

        # 3. Check for Titan Network (Docker container 'titan-edge')
        stdin, stdout, stderr = client.exec_command("sudo docker ps --format '{{.Names}}' | grep titan-edge")
        if stdout.read().decode().strip():
            client.close()
            return "Titan Network", "Titan container running"
            
        # 4. Check for Meson / GagaNode (Process 'gaganode')
        stdin, stdout, stderr = client.exec_command("pgrep -f gaganode")
        if stdout.read().decode().strip():
            client.close()
            return "Meson (GagaNode)", "GagaNode process running"
            
        client.close()
        return None, "No known project detected"

    except Exception as e:
        return None, f"SSH Connection Failed: {str(e)}"

def install_project_via_ssh(ip, private_key_str, script_base64):
    """
    Connect via SSH and execute the installation script.
    """
    if not ip or not private_key_str:
        return {"status": "error", "msg": "Missing IP or Private Key"}

    key_file = io.StringIO(private_key_str)
    try:
        pkey = paramiko.RSAKey.from_private_key(key_file)
    except Exception:
        try:
            key_file.seek(0)
            pkey = paramiko.Ed25519Key.from_private_key(key_file)
        except Exception as e:
            return {"status": "error", "msg": f"Invalid Key: {e}"}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname=ip, username='ec2-user', pkey=pkey, timeout=10)
        
        # Decode script
        try:
            script_content = base64.b64decode(script_base64).decode('utf-8')
        except:
            script_content = script_base64 # Assume plain text if fail

        # Write script to file
        create_file_cmd = "cat > /tmp/install_script.sh << 'EOF'\n" + script_content + "\nEOF"
        client.exec_command(create_file_cmd)
        
        # Execute
        # We run it in background or wait? Better to wait for short scripts, 
        # but installation might take long.
        # For now, run blocking to see output.
        stdin, stdout, stderr = client.exec_command("chmod +x /tmp/install_script.sh && sudo /tmp/install_script.sh")
        
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        client.close()
        
        if "error" in err.lower() and "warning" not in err.lower(): 
             # Simple heuristic, might be noisy
             pass

        return {"status": "success", "msg": "Script executed", "output": out, "error": err}

    except Exception as e:
        return {"status": "error", "msg": f"SSH Execution Failed: {str(e)}"}

def check_gfw_status(ip, port=22, timeout=3):
    """
    Check if IP:Port is reachable (TCP Ping).
    Returns: True (Accessible), False (Blocked/Down)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False
