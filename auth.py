import streamlit as st
import streamlit_authenticator as stauth
from db import create_supabase_client, fetch_all_users, register_user_db
import time

# Note: We do NOT import the global 'supabase' object anymore for auth.
# We create a new client for each session to prevent session leakage.

def init_authenticator():
    """
    Initialize Streamlit Authenticator with data from Supabase.
    """
    # 1. Fetch Users from DB
    users_dict = fetch_all_users()
    
    # 2. Configure Credentials
    credentials = {
        "usernames": users_dict
    }

    # 3. Initialize Authenticator
    authenticator = stauth.Authenticate(
        credentials,
        "aws_depin_tool_cookie", # Cookie Name
        "random_signature_key_change_this", # Key
        cookie_expiry_days=30,
        auto_hash=False # We handle hashing manually during register
    )
    
    st.session_state["auth_credentials"] = credentials
    return authenticator, credentials

def login_page(authenticator, credentials):
    """Render the login/signup page using Authenticator."""
    
    result = authenticator.login(location="main")
    if isinstance(result, tuple) and len(result) == 3:
        name, authentication_status, username = result
    else:
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
    
    # Handle Authentication Status
    st.session_state["authentication_status"] = authentication_status
    st.session_state["username"] = username
    st.session_state["name"] = name
    if authentication_status:
        # Success logic handled in app.py (rerun or main app render)
        # We just need to ensure the user ID is in session for DB queries
        user_info = credentials.get('usernames', {}).get(username)
        if user_info:
            st.session_state["user_id"] = user_info.get("id")
            st.session_state["user_role"] = "user" # Default, or fetch from DB if needed
            
            # Initialize Supabase Client for this session
            if "supabase_client" not in st.session_state:
                st.session_state["supabase_client"] = create_supabase_client()
        
        return True
    elif authentication_status is False:
        st.error("用户名/密码错误")
        return False
        
    elif authentication_status is None:
        # Show Register Tab if not logged in
        with st.expander("还没有账号？点击注册"):
            register_form(authenticator)
        return False

def register_form(authenticator):
    """Handle new user registration."""
    with st.form("register_form"):
        st.subheader("注册新账号 / 迁移旧账号")
        st.info("如果您是旧用户，请使用相同的邮箱注册，系统会自动关联您的旧数据。")
        
        email = st.text_input("邮箱 (必须是唯一的)")
        username = st.text_input("用户名 (用于登录)")
        name = st.text_input("昵称")
        password = st.text_input("密码", type="password")
        password_confirm = st.text_input("确认密码", type="password")
        
        submit = st.form_submit_button("注册")
        
        if submit:
            if not email or not username or not password:
                st.error("请填写所有必填项")
            elif password != password_confirm:
                st.error("两次输入的密码不一致")
            else:
                try:
                    # Hash password
                    # Try-catch block to handle different streamlit-authenticator versions
                    try:
                         # Newer versions might require a single string or different init
                         hashed_pw = stauth.Hasher([password]).generate()[0]
                    except TypeError:
                         # Fallback or alternate signature check
                         hashed_pw = stauth.Hasher().hash(password)
                    
                    # Register in DB
                    success, msg = register_user_db(email, username, name, hashed_pw, password)
                    
                    if success:
                        st.success("注册成功！请使用新账号登录。")
                        # Optional: Force reload to update authenticator config
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"注册失败: {msg}")
                except Exception as e:
                    st.error(f"注册异常: {e}")

def ensure_session_state(credentials):
    """
    Ensure critical session state variables (like user_id) are initialized.
    This is necessary because if a user is auto-logged in via cookie, 
    the login_page() logic might be skipped.
    """
    if "user_id" not in st.session_state:
        if "username" in st.session_state:
            username = st.session_state["username"]
            user_info = credentials.get('usernames', {}).get(username)
            if user_info:
                st.session_state["user_id"] = user_info.get("id")
                st.session_state["user_role"] = "user" # Default
                
                # Initialize Supabase Client
                if "supabase_client" not in st.session_state:
                    st.session_state["supabase_client"] = create_supabase_client()
                return True
        return False # Failed to restore
    return True # Already set

# Legacy functions kept for reference/compatibility if needed, 
# but they are effectively replaced by Authenticator logic.
def sign_out():
    pass # Authenticator handles this via authenticator.logout()
