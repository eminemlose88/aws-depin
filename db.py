import os
import streamlit as st
from supabase import create_client, Client, ClientOptions
from datetime import datetime
from crypto import encrypt_key, decrypt_key

# Initialize Supabase client
# Try to get credentials from environment variables first, then from streamlit secrets
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url and hasattr(st, "secrets") and "secrets" in st.secrets:
    url = st.secrets["secrets"].get("SUPABASE_URL")
    key = st.secrets["secrets"].get("SUPABASE_KEY")
elif not url and hasattr(st, "secrets"): # Handle flat secrets structure
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

# WARNING: Global client removed to prevent session leakage.
# All authenticated operations must use the session-specific client.
_global_supabase: Client = None

# Only initialize global client if strictly necessary for anonymous access, 
# AND explicitly disable persistence to prevent state pollution.
if url and key:
    try:
        _global_supabase = create_client(
            url, 
            key,
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False, # CRITICAL: Disable persistence
                storage=None
            )
        )
    except Exception as e:
        print(f"Failed to initialize global Supabase client: {e}")

def create_supabase_client():
    """
    Create a new Supabase client instance.
    CRITICAL: Must disable session persistence to prevent session leakage between users
    on shared file systems (like Streamlit Cloud).
    """
    if url and key:
        return create_client(
            url, 
            key,
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False, # CRITICAL: Disable persistence
                storage=None
            )
        )
    return None

def get_supabase():
    """
    Get the appropriate Supabase client.
    Prioritizes the session-specific client if logged in.
    Fallback to global client (which is now stateless/anonymous).
    """
    if "supabase_client" in st.session_state:
        return st.session_state["supabase_client"]
    return _global_supabase

def check_db_connection():
    """
    Check if the database connection is valid and the table exists.
    Returns True if OK, False otherwise.
    """
    client = get_supabase()
    if not client:
        return False
    try:
        # Try to select 1 row to check if table exists
        client.table("instances").select("id").limit(1).execute()
        return True
    except Exception as e:
        # Check if error contains "relation" and "does not exist"
        err_msg = str(e).lower()
        if "relation" in err_msg and "does not exist" in err_msg:
            st.error("🚨 数据库表尚未创建！")
            st.warning("请复制项目根目录下的 `schema.sql` 内容，并在 Supabase SQL Editor 中运行它。")
            with open("schema.sql", "r", encoding="utf-8") as f:
                st.code(f.read(), language="sql")
        else:
            print(f"Database check failed: {e}")
        return False

# --- AWS Credentials Management ---

def add_aws_credential(user_id, alias, ak, sk):
    """Add a new AWS credential for the user."""
    client = get_supabase()
    if not client: return None
    
    try:
        data = {
            "user_id": user_id,
            "alias_name": alias,
            "access_key_id": ak.strip(),
            "secret_access_key": sk.strip(),
            "status": "active" # Default status
        }
        response = client.table("aws_credentials").insert(data).execute()
        return response.data
    except Exception as e:
        print(f"Error adding credential: {e}")
        return None

def get_user_credentials(user_id):
    """Get all AWS credentials for the user."""
    client = get_supabase()
    if not client: return []
    
    try:
        response = client.table("aws_credentials") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error fetching credentials: {e}")
        return []

def delete_aws_credential(cred_id):
    """Delete an AWS credential."""
    client = get_supabase()
    if not client: return
    
    try:
        client.table("aws_credentials").delete().eq("id", cred_id).execute()
    except Exception as e:
        print(f"Error deleting credential: {e}")

def update_credential_status(cred_id, status, limit=None, used=None):
    """Update the health status of a credential."""
    client = get_supabase()
    if not client: return
    
    try:
        data = {
            "status": status,
            "last_checked": datetime.utcnow().isoformat()
        }
        if limit is not None: data["vcpu_limit"] = limit
        if used is not None: data["vcpu_used"] = used
        
        client.table("aws_credentials") \
            .update(data) \
            .eq("id", cred_id) \
            .execute()
    except Exception as e:
        print(f"Error updating credential status: {e}")

# --- Instance Management ---

def log_instance(user_id, credential_id, instance_id, ip, region, project_name, status="active", private_key=None):
    """
    Log instance details to Supabase 'instances' table with user_id association.
    Encodes private key if provided.
    """
    client = get_supabase()
    if not client:
        print("Supabase credentials not found. Skipping DB logging.")
        return

    encrypted_key = encrypt_key(private_key) if private_key else None

    try:
        data = {
            "user_id": user_id,
            "credential_id": credential_id,
            "instance_id": instance_id,
            "ip_address": ip,
            "region": region,
            "project_name": project_name,
            "status": status,
            "private_key": encrypted_key
        }
        client.table("instances").insert(data).execute()
        print(f"Logged instance {instance_id} to database.")
    except Exception as e:
        print(f"Error logging to database: {e}")

def get_user_instances(user_id):
    """
    Retrieve all instances associated with a specific User ID.
    Order by created_at descending.
    """
    client = get_supabase()
    if not client:
        return []

    try:
        # Fetch instances and join with aws_credentials to get alias name if needed
        # Supabase-py join syntax can be tricky, simple select first
        response = client.table("instances") \
            .select("*, aws_credentials(alias_name, access_key_id)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error fetching instances: {e}")
        check_db_connection()
        return []

def get_instance_private_key(instance_id):
    """Retrieve and decrypt the private key for a specific instance."""
    client = get_supabase()
    if not client: return None
    try:
        response = client.table("instances") \
            .select("private_key") \
            .eq("instance_id", instance_id) \
            .single() \
            .execute()
        if response.data and response.data.get("private_key"):
            return decrypt_key(response.data["private_key"])
        return None
    except Exception as e:
        print(f"Error fetching private key: {e}")
        return None

def update_instance_status(instance_id, new_status):
    """
    Update the status of an instance in the database.
    """
    client = get_supabase()
    if not client:
        return

    try:
        client.table("instances") \
            .update({"status": new_status}) \
            .eq("instance_id", instance_id) \
            .execute()
        print(f"Updated instance {instance_id} status to {new_status}")
    except Exception as e:
        print(f"Error updating instance status: {e}")

def update_instance_project(instance_id, project_name):
    """
    Update the project name of an instance in the database.
    Appends the new project name if it doesn't exist, comma-separated.
    """
    client = get_supabase()
    if not client: return
    try:
        # 1. Fetch current project name
        res = client.table("instances").select("project_name").eq("instance_id", instance_id).single().execute()
        current_name = res.data.get("project_name", "") if res.data else ""
        
        # 2. Determine new name
        if not current_name or current_name in ["Pending", "Unknown"]:
            new_name = project_name
        else:
            # Check if already exists
            current_list = [p.strip() for p in current_name.split(',')]
            if project_name in current_list:
                new_name = current_name # No change
            else:
                new_name = f"{current_name}, {project_name}"
        
        # 3. Update
        if new_name != current_name:
            client.table("instances") \
                .update({"project_name": new_name}) \
                .eq("instance_id", instance_id) \
                .execute()
            print(f"Updated instance {instance_id} project to {new_name}")
    except Exception as e:
        print(f"Error updating instance project: {e}")

def update_instance_health(instance_id, health_status):
    """Update the health check status of an instance."""
    client = get_supabase()
    if not client: return
    try:
        client.table("instances") \
            .update({"health_status": health_status}) \
            .eq("instance_id", instance_id) \
            .execute()
    except Exception as e:
        print(f"Error updating instance health: {e}")

def sync_instances(user_id, credential_id, region, aws_instances):
    """
    Sync AWS instances with database records.
    aws_instances: List of dicts from scan_all_instances
    """
    client = get_supabase()
    if not client: return {"new": 0, "updated": 0}
    
    stats = {"new": 0, "updated": 0}
    
    # 1. Get DB instances for this credential and region
    try:
        db_res = client.table("instances") \
            .select("instance_id, status") \
            .eq("credential_id", credential_id) \
            .eq("region", region) \
            .execute()
        db_map = {r['instance_id']: r['status'] for r in db_res.data}
    except Exception as e:
        print(f"Sync DB fetch error: {e}")
        return stats

    aws_map = {i['instance_id']: i for i in aws_instances}

    # 2. Process AWS instances (New & Update)
    for aws_id, aws_info in aws_map.items():
        aws_status = aws_info['status']
        
        if aws_id not in db_map:
            # Found NEW instance
            if aws_status != 'terminated': # Don't import terminated instances
                try:
                    data = {
                        "user_id": user_id,
                        "credential_id": credential_id,
                        "instance_id": aws_id,
                        "ip_address": aws_info['ip_address'],
                        "region": region,
                        "project_name": aws_info['project_name'],
                        "status": aws_status
                    }
                    client.table("instances").insert(data).execute()
                    stats["new"] += 1
                except Exception as e:
                    print(f"Error importing instance {aws_id}: {e}")
        
        elif db_map[aws_id] != aws_status:
            # Status changed
            update_instance_status(aws_id, aws_status)
            stats["updated"] += 1

    # 3. Process Missing instances (Mark as Terminated)
    # If in DB (and not terminated) but NOT in AWS list -> likely terminated long ago or region mismatch
    # (Note: describe_instances usually returns terminated instances for a short while, then they disappear)
    for db_id, db_status in db_map.items():
        if db_id not in aws_map and db_status != 'terminated':
            update_instance_status(db_id, 'terminated')
            stats["updated"] += 1
            
    return stats
