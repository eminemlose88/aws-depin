import streamlit as st
from datetime import datetime, date
from db import get_supabase

# --- Constants ---
BASE_DAILY_FEE = 0.25
EC2_INSTANCE_FEE = 0.20
LIGHTSAIL_INSTANCE_FEE = 0.10
GFW_CHECK_FEE = 0.05

def get_user_profile(user_id):
    """Fetch user profile including balance."""
    client = get_supabase()
    if not client: return None
    
    try:
        res = client.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return None

def check_balance(user_id, required_amount=0):
    """
    Check if user has sufficient balance and is allowed to perform actions.
    Returns: (allowed: bool, msg: str)
    """
    profile = get_user_profile(user_id)
    if not profile:
        return False, "无法获取用户信息"
        
    balance = float(profile.get("balance", 0))
    
    if balance <= 0:
        return False, "余额不足 (≤0)，请充值以恢复服务。"
        
    if balance < required_amount:
        return False, f"余额不足 (需 {required_amount}, 当前 {balance})"
        
    return True, "OK"

def add_balance(user_id, amount, description="充值"):
    """
    Add balance to user account.
    """
    client = get_supabase()
    if not client: return False
    
    try:
        # 1. Get current balance
        profile = get_user_profile(user_id)
        current_balance = float(profile.get("balance", 0))
        new_balance = current_balance + amount
        
        # 2. Update profile
        client.table("profiles").update({"balance": new_balance}).eq("id", user_id).execute()
        
        # 3. Log transaction
        client.table("transactions").insert({
            "user_id": user_id,
            "amount": amount,
            "type": "deposit" if amount > 0 else "refund",
            "description": description
        }).execute()
        
        return True
    except Exception as e:
        print(f"Error adding balance: {e}")
        return False

def calculate_daily_cost(user_id):
    """
    Calculate the projected daily cost based on current resources.
    """
    client = get_supabase()
    if not client: return 0.0
    
    try:
        # 1. Count active instances
        # Assume all in 'instances' table are EC2 for now (or add type column later)
        res = client.table("instances").select("id", "status", "health_status").eq("user_id", user_id).neq("status", "terminated").execute()
        active_instances = res.data
        ec2_count = len(active_instances)
        
        # 2. Check enabled features
        profile = get_user_profile(user_id)
        auto_replace = profile.get("auto_replace_enabled", False)
        gfw_check = profile.get("gfw_check_enabled", False)
        
        # 3. Calculate
        # Base fee applies if ANY account exists? Or just if user is active?
        # Requirement: "用户无账号时停止计费" -> interpreted as "No AWS Credentials added"
        cred_res = client.table("aws_credentials").select("id").eq("user_id", user_id).execute()
        has_credentials = len(cred_res.data) > 0
        
        total = 0.0
        if has_credentials:
            total += BASE_DAILY_FEE
            
            if auto_replace:
                total += ec2_count * EC2_INSTANCE_FEE
                
            if gfw_check:
                total += ec2_count * GFW_CHECK_FEE
                
        return total
        
    except Exception as e:
        print(f"Error calculating cost: {e}")
        return 0.0

def process_daily_billing(user_id):
    """
    Execute the daily billing logic. 
    Should be called once per day per user (e.g. via Cron or lazy trigger).
    """
    client = get_supabase()
    if not client: return
    
    today = date.today().isoformat()
    
    # Check if already billed today
    try:
        log = client.table("billing_logs").select("id").eq("user_id", user_id).eq("date", today).execute()
        if log.data:
            return # Already billed
    except Exception:
        pass
        
    # Calculate
    cost = calculate_daily_cost(user_id)
    if cost <= 0: return 
    
    # Deduct
    try:
        profile = get_user_profile(user_id)
        current_balance = float(profile.get("balance", 0))
        new_balance = current_balance - cost
        
        # Update Profile
        client.table("profiles").update({"balance": new_balance}).eq("id", user_id).execute()
        
        # Log Transaction
        client.table("transactions").insert({
            "user_id": user_id,
            "amount": -cost,
            "type": "daily_fee",
            "description": f"日结账单 ({today})"
        }).execute()
        
        # Log Billing Detail
        # For simplicity, we just log total now. ideally split it.
        client.table("billing_logs").insert({
            "user_id": user_id,
            "date": today,
            "total_fee": cost
        }).execute()
        
        print(f"Billed user {user_id}: {cost}")
        
    except Exception as e:
        print(f"Billing failed: {e}")

def require_balance(func):
    """Decorator to enforce balance check before action."""
    def wrapper(*args, **kwargs):
        # We need user_id. In Streamlit app, it's usually st.session_state.user.id
        # This decorator assumes it's running in Streamlit context
        if "user" in st.session_state and st.session_state.user:
            user_id = st.session_state.user.id
            allowed, msg = check_balance(user_id)
            if not allowed:
                st.error(f"⛔ {msg}")
                return None
        return func(*args, **kwargs)
    return wrapper
