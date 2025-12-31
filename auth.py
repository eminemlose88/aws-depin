import streamlit as st
import extra_streamlit_components as stx
from db import create_supabase_client
import time
from datetime import datetime, timedelta

# Note: We do NOT import the global 'supabase' object anymore for auth.
# We create a new client for each session to prevent session leakage.

# Removed @st.cache_resource to avoid CachedWidgetWarning
def get_cookie_manager():
    return stx.CookieManager(key="auth_cookie_manager")

cookie_manager = get_cookie_manager()

def sign_up(email, password):
    """Register a new user with Supabase Auth."""
    try:
        # Create a temporary client for sign up
        client = create_supabase_client()
        if not client: return {"error": "Database connection failed"}
        
        response = client.auth.sign_up({
            "email": email,
            "password": password
        })
        return response
    except Exception as e:
        return {"error": str(e)}

def sign_in(email, password):
    """Log in an existing user and store client in session."""
    try:
        # Create a dedicated client for this user session
        client = create_supabase_client()
        if not client: return {"error": "Database connection failed"}
        
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # If successful, store the authenticated client in session state
        if response.user:
            st.session_state["supabase_client"] = client
            st.session_state["user"] = response.user
            
            # Save session to cookies (expires in 7 days)
            if response.session:
                cookie_manager.set('supabase_access_token', response.session.access_token, expires_at=datetime.now() + timedelta(days=7), key="set_access_token")
                cookie_manager.set('supabase_refresh_token', response.session.refresh_token, expires_at=datetime.now() + timedelta(days=7), key="set_refresh_token")
            
            # Fetch User Role
            try:
                profile = client.table("profiles").select("role").eq("id", response.user.id).single().execute()
                if profile.data:
                    st.session_state["user_role"] = profile.data.get("role", "user")
                else:
                    st.session_state["user_role"] = "user"
            except Exception as e:
                print(f"Error fetching role: {e}")
                st.session_state["user_role"] = "user"

        return response
    except Exception as e:
        return {"error": str(e)}

def sign_out():
    """Log out the current user."""
    try:
        # Clear cookies
        cookie_manager.delete('supabase_access_token')
        cookie_manager.delete('supabase_refresh_token')
        
        if "supabase_client" in st.session_state:
            st.session_state["supabase_client"].auth.sign_out()
            del st.session_state["supabase_client"]
        
        keys_to_clear = ["user", "user_role", "admin_mode"]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
            
    except Exception as e:
        print(f"Sign out error: {e}")

def get_current_user():
    """Get the currently logged-in user from the session."""
    # First check if we have a user object in session
    if "user" in st.session_state:
        # Ensure role is loaded if missing (e.g. page refresh)
        if "user_role" not in st.session_state and "supabase_client" in st.session_state:
             try:
                client = st.session_state["supabase_client"]
                profile = client.table("profiles").select("role").eq("id", st.session_state["user"].id).single().execute()
                if profile.data:
                    st.session_state["user_role"] = profile.data.get("role", "user")
             except:
                 pass
        return st.session_state["user"]
        
    # If not, check if we have a client and try to fetch user
    if "supabase_client" in st.session_state:
        try:
            user_response = st.session_state["supabase_client"].auth.get_user()
            if user_response and user_response.user:
                st.session_state["user"] = user_response.user
                
                # Fetch role
                try:
                    profile = st.session_state["supabase_client"].table("profiles").select("role").eq("id", user_response.user.id).single().execute()
                    st.session_state["user_role"] = profile.data.get("role", "user") if profile.data else "user"
                except:
                    st.session_state["user_role"] = "user"

                return user_response.user
        except Exception:
            pass
            
    # Try to restore from cookies
    try:
        access_token = cookie_manager.get('supabase_access_token')
        refresh_token = cookie_manager.get('supabase_refresh_token')
        
        if access_token and refresh_token:
            client = create_supabase_client()
            if client:
                res = client.auth.set_session(access_token, refresh_token)
                if res.user:
                    st.session_state["supabase_client"] = client
                    st.session_state["user"] = res.user
                    
                    # Fetch Role
                    try:
                        profile = client.table("profiles").select("role").eq("id", res.user.id).single().execute()
                        st.session_state["user_role"] = profile.data.get("role", "user") if profile.data else "user"
                    except:
                        st.session_state["user_role"] = "user"
                        
                    return res.user
    except Exception as e:
        print(f"Session restore failed: {e}")
            
    return None

def login_page():
    """Render the login/signup page."""
    st.title("🔐 登录 / 注册")
    
    tab1, tab2 = st.tabs(["登录", "注册新账号"])
    
    with tab1:
        email = st.text_input("邮箱地址", key="login_email")
        password = st.text_input("密码", type="password", key="login_pass")
        if st.button("登录", use_container_width=True):
            if not email or not password:
                st.error("请输入邮箱和密码")
            else:
                with st.spinner("正在登录..."):
                    res = sign_in(email, password)
                    if isinstance(res, dict) and "error" in res:
                        st.error(f"登录失败: {res['error']}")
                    else:
                        st.success("登录成功！")
                        # User and role set in sign_in
                        st.rerun()

    with tab2:
        new_email = st.text_input("邮箱地址", key="signup_email")
        new_pass = st.text_input("设置密码 (至少6位)", type="password", key="signup_pass")
        if st.button("注册", use_container_width=True):
            if not new_email or not new_pass:
                st.error("请输入邮箱和密码")
            elif len(new_pass) < 6:
                st.error("密码长度至少为 6 位")
            else:
                with st.spinner("正在注册..."):
                    res = sign_up(new_email, new_pass)
                    if isinstance(res, dict) and "error" in res:
                        st.error(f"注册失败: {res['error']}")
                    else:
                        st.success("注册成功！请检查邮箱并确认验证链接（如果已启用邮箱验证），然后登录。")
                        # Ensure profile is created (trigger handles it, but double check logic if needed)
