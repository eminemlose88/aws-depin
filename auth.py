import streamlit as st
from db import supabase

def sign_up(email, password):
    """Register a new user with Supabase Auth."""
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        return response
    except Exception as e:
        return {"error": str(e)}

def sign_in(email, password):
    """Log in an existing user."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return response
    except Exception as e:
        return {"error": str(e)}

def sign_out():
    """Log out the current user."""
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Sign out error: {e}")

def get_current_user():
    """Get the currently logged-in user from the session."""
    try:
        user = supabase.auth.get_user()
        return user.user if user else None
    except Exception:
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
                        st.session_state["user"] = res.user
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
                        # For some Supabase configs, auto-login happens, for others email confirm is needed.
                        # We'll ask user to login.
