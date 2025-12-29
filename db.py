import os
from supabase import create_client, Client

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

def log_instance(access_key_id, instance_id, ip, region, project_name, status="active"):
    """
    Log instance details to Supabase 'instances' table.
    """
    if not supabase:
        print("Supabase credentials not found. Skipping DB logging.")
        return

    try:
        data = {
            "access_key_id": access_key_id,
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

def get_user_instances(access_key_id):
    """
    Retrieve all instances associated with a specific Access Key ID.
    Order by created_at descending.
    """
    if not supabase:
        return []

    try:
        response = supabase.table("instances") \
            .select("*") \
            .eq("access_key_id", access_key_id) \
            .order("created_at", desc=True) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Error fetching instances: {e}")
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
