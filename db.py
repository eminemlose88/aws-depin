import os
import streamlit as st
from supabase import create_client, Client
from datetime import datetime

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

supabase: Client = None
if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

def check_db_connection():
    """
    Check if the database connection is valid and the table exists.
    Returns True if OK, False otherwise.
    """
    if not supabase:
        return False
    try:
        # Try to select 1 row to check if table exists
        supabase.table("instances").select("id").limit(1).execute()
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
    if not supabase: return None
    
    try:
        data = {
            "user_id": user_id,
            "alias_name": alias,
            "access_key_id": ak.strip(),
            "secret_access_key": sk.strip(),
            "status": "active" # Default status
        }
        response = supabase.table("aws_credentials").insert(data).execute()
        return response.data
    except Exception as e:
        print(f"Error adding credential: {e}")
        return None

def get_user_credentials(user_id):
    """Get all AWS credentials for the user."""
    if not supabase: return []
    
    try:
        response = supabase.table("aws_credentials") \
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
    if not supabase: return
    
    try:
        supabase.table("aws_credentials").delete().eq("id", cred_id).execute()
    except Exception as e:
        print(f"Error deleting credential: {e}")

def update_credential_status(cred_id, status):
    """Update the health status of a credential."""
    if not supabase: return
    
    try:
        supabase.table("aws_credentials") \
            .update({
                "status": status,
                "last_checked": datetime.utcnow().isoformat()
            }) \
            .eq("id", cred_id) \
            .execute()
    except Exception as e:
        print(f"Error updating credential status: {e}")

# --- Instance Management ---

def log_instance(user_id, credential_id, instance_id, ip, region, project_name, status="active"):
    """
    Log instance details to Supabase 'instances' table with user_id association.
    """
    if not supabase:
        print("Supabase credentials not found. Skipping DB logging.")
        return

    try:
        data = {
            "user_id": user_id,
            "credential_id": credential_id,
            "instance_id": instance_id,
            "ip_address": ip,
            "region": region,
            "project_name": project_name,
            "status": status
        }
        supabase.table("instances").insert(data).execute()
        print(f"Logged instance {instance_id} to database.")
    except Exception as e:
        print(f"Error logging to database: {e}")

def get_user_instances(user_id):
    """
    Retrieve all instances associated with a specific User ID.
    Order by created_at descending.
    """
    if not supabase:
        return []

    try:
        # Fetch instances and join with aws_credentials to get alias name if needed
        # Supabase-py join syntax can be tricky, simple select first
        response = supabase.table("instances") \
            .select("*, aws_credentials(alias_name, access_key_id)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error fetching instances: {e}")
        check_db_connection()
        return []

def update_instance_status(instance_id, new_status):
    """
    Update the status of an instance in the database.
    """
    if not supabase:
        return

    try:
        supabase.table("instances") \
            .update({"status": new_status}) \
            .eq("instance_id", instance_id) \
            .execute()
        print(f"Updated instance {instance_id} status to {new_status}")
    except Exception as e:
        print(f"Error updating instance status: {e}")

def sync_instances(user_id, credential_id, region, aws_instances):
    """
    Sync AWS instances with database records.
    aws_instances: List of dicts from scan_all_instances
    """
    if not supabase: return {"new": 0, "updated": 0}
    
    stats = {"new": 0, "updated": 0}
    
    # 1. Get DB instances for this credential and region
    try:
        db_res = supabase.table("instances") \
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
                    supabase.table("instances").insert(data).execute()
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
