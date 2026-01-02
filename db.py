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

# --- Authentication Helpers (Streamlit-Authenticator) ---

def fetch_all_users():
    """
    Fetch all users from profiles table.
    Returns a dictionary formatted for streamlit-authenticator.
    """
    client = get_supabase()
    if not client: return {}
    
    try:
        # Fetch all profiles
        response = client.table("profiles").select("*").execute()
        if not response.data:
            return {}
            
        users_dict = {}
        for user in response.data:
            username = user.get("username")
            if username:
                users_dict[username] = {
                    "email": user.get("email"),
                    "name": username, # Force name to be username
                    "password": user.get("password"), # Hashed password
                    "id": user.get("id") # Keep ID for reference
                }
        return users_dict
    except Exception as e:
        print(f"Error fetching users: {e}")
        return {}

def register_user_db(email, username, password_hash, new_uuid=None):
    """
    Register or update a user in the database.
    If email exists, update the record (preserves ID).
    If new, insert with new UUID.
    """
    client = get_supabase()
    if not client: return False, "Database connection failed"
    
    try:
        # 1. Check if email exists
        res = client.table("profiles").select("id").eq("email", email).execute()
        
        if res.data:
            # Update existing user
            user_id = res.data[0]['id']
            client.table("profiles").update({
                "username": username,
                # "name": name, # Removed
                "password": password_hash
            }).eq("id", user_id).execute()
            return True, "User updated successfully (ID preserved)"
        else:
            # Insert new user
            # Note: We can't easily insert into profiles if it's linked to auth.users via foreign key
            # unless we also create a user in auth.users.
            # However, since we are moving AWAY from Supabase Auth for login,
            # we might encounter RLS or FK issues if we try to insert a random UUID.
            # Ideally, we should still use Supabase Auth to generate the UUID, 
            # OR we must ensure 'profiles' is decoupled.
            # For this hybrid approach, we will assume we can insert.
            
            import uuid
            new_id = str(uuid.uuid4()) if not new_uuid else new_uuid
            
            client.table("profiles").insert({
                "id": new_id,
                "email": email,
                "username": username,
                # "name": name, # Removed
                "password": password_hash
            }).execute()
            return True, "User registered successfully"
            
    except Exception as e:
        print(f"Registration error: {e}")
        return False, str(e)

def reload_schema_cache():
    """
    Force Supabase PostgREST to reload its schema cache.
    This is required after making structural changes (like adding columns)
    so that the API recognizes them immediately.
    """
    client = get_supabase()
    if not client: return False, "No client"
    
    try:
        # Execute the raw SQL command to notify pgrst
        # Note: This requires the Postgres role used by the client to have permission to NOTIFY.
        # Standard 'service_role' or 'postgres' users have this.
        # If using 'anon' or 'authenticated', it might fail depending on RLS/Grants,
        # but usually 'authenticated' can't do this. 
        # However, we'll try to use the rpc call if a stored procedure existed, 
        # or just try a raw query if the client supports it (supabase-py client doesn't expose raw SQL easily for non-admin).
        
        # Actually, standard Supabase client doesn't support executing arbitrary SQL string directly
        # unless we use the rpc() interface to call a function.
        # 
        # WORKAROUND: We can't execute "NOTIFY pgrst" directly via the JS/Python client unless we have a stored procedure for it.
        # 
        # BUT, the user likely has access to the dashboard.
        # Since we can't easily run raw SQL from here without a pre-existing RPC function,
        # we will return a message instructing the user OR try to assume there's a helper.
        
        # Let's try to query a system table or something harmless that might trigger a check, 
        # but real schema reload needs the NOTIFY command.
        
        # If we can't run it, we must guide the user.
        # Wait! If the user has the 'postgres' connection string (unlikely in this app context), they could.
        # 
        # Let's provide a UI instruction instead if we can't automate it.
        pass 
    except Exception as e:
        print(f"Reload schema failed: {e}")

    return False, "请在 Supabase SQL Editor 中执行: NOTIFY pgrst, 'reload schema';"

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

def add_aws_credential(user_id, alias, ak, sk, proxy=None):
    """Add a new AWS credential for the user."""
    client = get_supabase()
    if not client: return None
    
    try:
        data = {
            "user_id": user_id,
            "alias_name": alias,
            "access_key_id": ak.strip(),
            "secret_access_key": sk.strip(),
            "status": "active", # Default status
            "proxy_url": proxy.strip() if proxy else None
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

def update_aws_credential(cred_id, user_id, alias, ak, sk, proxy, status='active'):
    """Update an existing AWS credential using standard UPDATE."""
    client = get_supabase()
    if not client: return False, "Database connection failed"
    
    try:
        data = {
            # "id": cred_id, # Remove ID for standard update
            "user_id": user_id,
            "alias_name": alias,
            "access_key_id": ak.strip(),
            "secret_access_key": sk.strip(),
            "proxy_url": proxy.strip() if proxy else None,
            "status": status,
            "last_checked": datetime.now().isoformat()
        }
        
        # Revert to standard update to avoid unique constraint violations
        client.table("aws_credentials").update(data).eq("id", cred_id).execute()
        
        # Debug: Check if update worked
        updated_row = client.table("aws_credentials").select("proxy_url").eq("id", cred_id).single().execute()
        print(f"DEBUG Update Result: {updated_row.data}")
        
        return True, "Success"
    except Exception as e:
        error_msg = str(e)
        print(f"Error updating credential: {error_msg}")
        return False, error_msg

def delete_instance(instance_id):
    """Delete an instance record from the database."""
    client = get_supabase()
    if not client: return
    try:
        client.table("instances").delete().eq("instance_id", instance_id).execute()
        print(f"Deleted instance record: {instance_id}")
    except Exception as e:
        print(f"Error deleting instance: {e}")

def get_credential_vcpu_usage(credential_id):
    """
    Calculate total vCPU usage for a credential based on local DB.
    """
    client = get_supabase()
    if not client: return 0
    
    try:
        # Fetch vcpu_count for all active instances
        response = client.table("instances") \
            .select("vcpu_count") \
            .eq("credential_id", credential_id) \
            .neq("status", "terminated") \
            .neq("status", "shutting-down") \
            .execute()
        
        total = 0
        if response.data:
            for row in response.data:
                count = row.get("vcpu_count")
                if count: # Handle None
                    total += int(count)
        return total
    except Exception as e:
        print(f"Error calculating vCPU usage: {e}")
        return 0


# --- Instance Management ---

def get_all_instance_types():
    """Retrieve all instance types from the database."""
    client = get_supabase()
    if not client: return []
    try:
        response = client.table("aws_instance_types").select("*").order("instance_type").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching instance types: {e}")
        return []

def log_instance(user_id, credential_id, instance_id, ip, region, project_name, status="active", private_key=None, specs=None):
    """
    Log instance details to Supabase 'instances' table with user_id association.
    Encodes private key if provided.
    Supports optional specs dictionary for detailed configuration logging.
    """
    client = get_supabase()
    if not client:
        print("Supabase credentials not found. Skipping DB logging.")
        return

    encrypted_key = encrypt_key(private_key) if private_key else None

    # Parse initial project name to set booleans
    p_name = project_name or "Pending"
    
    # Initialize booleans based on project_name input (for backward compatibility / initial install)
    is_titan = "Titan" in p_name
    is_nexus = "Nexus" in p_name
    is_shardeum = "Shardeum" in p_name
    is_babylon = "Babylon" in p_name
    is_meson = "Meson" in p_name or "GagaNode" in p_name
    is_proxy = "Proxy" in p_name or "Dante" in p_name or "Squid" in p_name

    try:
        data = {
            "user_id": user_id,
            "credential_id": credential_id,
            "instance_id": instance_id,
            "ip_address": ip,
            "region": region,
            "project_name": p_name, # FIXED: Ensure project_name is provided (NOT NULL constraint)
            "status": status,
            "private_key": encrypted_key,
            "proj_titan": is_titan,
            "proj_nexus": is_nexus,
            "proj_shardeum": is_shardeum,
            "proj_babylon": is_babylon,
            "proj_meson": is_meson,
            "proj_proxy": is_proxy
        }
        
        # Add specs if provided
        if specs:
            data.update({
                "instance_type": specs.get("instance_type"),
                "vcpu_count": specs.get("vcpu_count"),
                "memory_gb": specs.get("memory_gb"),
                "os_name": specs.get("os_name"),
                "disk_info": specs.get("disk_info")
            })

        client.table("instances").insert(data).execute()
        print(f"Logged instance {instance_id} to database.")
    except Exception as e:
        print(f"Error logging to database: {e}")
        raise # Re-raise exception to trigger rollback in app.py

def get_user_instances(user_id):
    """
    Retrieve all instances associated with a specific User ID.
    Order by created_at descending.
    Fetches boolean project columns.
    """
    client = get_supabase()
    if not client:
        return []

    try:
        # Fetch instances and join with aws_credentials to get alias name if needed
        # Explicitly select columns to ensure we get the new booleans
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
    Smart merge: Deduplicates entries.
    """
    client = get_supabase()
    if not client: return
    try:
        # 1. Fetch current project name
        res = client.table("instances").select("project_name").eq("instance_id", instance_id).single().execute()
        current_name = res.data.get("project_name", "") if res.data else ""
        
        # 2. Determine new name (Smart Merge)
        if not current_name or current_name in ["Pending", "Unknown"]:
            # If current is empty or placeholder, just take the new one
            # Clean it up first though
            new_name = ", ".join(sorted(list(set(p.strip() for p in project_name.split(',') if p.strip()))))
        else:
            # Merge logic
            current_set = set(p.strip() for p in current_name.split(',') if p.strip())
            new_set = set(p.strip() for p in project_name.split(',') if p.strip())
            
            # Union
            merged_set = current_set.union(new_set)
            
            # Sort for consistency
            new_name = ", ".join(sorted(list(merged_set)))
        
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

def update_instance_projects_status(instance_id, detected_projects):
    """
    Update the boolean project flags for an instance.
    detected_projects: List of strings (e.g. ['Titan', 'Nexus'])
    Only sets flags to TRUE if detected; does NOT unset existing flags to avoid overwriting.
    """
    client = get_supabase()
    if not client: return
    
    try:
        data = {}
        # Normalize input list
        proj_list = [p.strip() for p in detected_projects]
        
        # Check and set corresponding booleans
        # Note: We only update to True if detected. We generally don't set to False automatically
        # to prevent transient detection failures from wiping out status.
        if any("Titan" in p for p in proj_list): data["proj_titan"] = True
        if any("Nexus" in p for p in proj_list): data["proj_nexus"] = True
        if any("Shardeum" in p for p in proj_list): data["proj_shardeum"] = True
        if any("Babylon" in p for p in proj_list): data["proj_babylon"] = True
        if any("Meson" in p for p in proj_list) or any("Gaga" in p for p in proj_list): data["proj_meson"] = True
        if any("Proxy" in p for p in proj_list) or any("Dante" in p for p in proj_list): data["proj_proxy"] = True
        
        if data:
            client.table("instances") \
                .update(data) \
                .eq("instance_id", instance_id) \
                .execute()
            print(f"Updated instance {instance_id} projects: {data.keys()}")
    except Exception as e:
        print(f"Error updating instance projects: {e}")

def sync_instances(user_id, credential_id, region, aws_instances):
    """
    Sync AWS instances with database records.
    aws_instances: List of dicts from scan_all_instances
    Optimized: Uses batch insert for new instances.
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
    
    new_instances_data = []

    # 2. Process AWS instances (Collect New & Update Existing)
    for aws_id, aws_info in aws_map.items():
        aws_status = aws_info['status']
        
        if aws_id not in db_map:
            # Found NEW instance - Add to batch list
            if aws_status != 'terminated': # Don't import terminated instances
                # Initialize booleans (default False)
                # For newly discovered instances via sync, we don't know the project yet unless we probe.
                # So we leave them False.
                new_instances_data.append({
                    "user_id": user_id,
                    "credential_id": credential_id,
                    "instance_id": aws_id,
                    "ip_address": aws_info['ip_address'],
                    "region": region,
                    "project_name": aws_info.get('project_name') or "Pending", # Re-enabled with fallback
                    "status": aws_status,
                    "proj_titan": False,
                    "proj_nexus": False,
                    "proj_shardeum": False,
                    "proj_babylon": False,
                    "proj_meson": False,
                    "proj_proxy": False
                })
        
        elif aws_status == 'terminated':
            # Always delete terminated instances from DB, even if status didn't change
            delete_instance(aws_id)
            stats["updated"] += 1
            
        elif db_map[aws_id] != aws_status:
            # Status changed (and not terminated)
            update_instance_status(aws_id, aws_status)
            stats["updated"] += 1

    # 3. Batch Insert New Instances
    if new_instances_data:
        try:
            print(f"DEBUG: Attempting to batch insert {len(new_instances_data)} instances...")
            client.table("instances").insert(new_instances_data).execute()
            stats["new"] += len(new_instances_data)
            print("DEBUG: Batch insert successful.")
        except Exception as e:
            print(f"Error batch importing instances: {e}")
            # Try fallback: Insert one by one to find the specific error or succeed partially
            print("DEBUG: Retrying with single inserts...")
            for item in new_instances_data:
                try:
                    client.table("instances").insert(item).execute()
                    stats["new"] += 1
                except Exception as inner_e:
                    print(f"Failed to insert instance {item['instance_id']}: {inner_e}")

    # 4. Process Missing instances (Mark as Terminated -> Delete)
    for db_id, db_status in db_map.items():
        if db_id not in aws_map:
            # If missing from AWS, delete it (it's gone)
            delete_instance(db_id)
            stats["updated"] += 1
            
    return stats
