import streamlit as st
import pandas as pd
import time
from datetime import date
from db import get_supabase
from billing import process_daily_billing

def is_admin():
    """Check if current user is admin."""
    if "user_role" in st.session_state and st.session_state.user_role == 'admin':
        return True
    return False

def get_all_users():
    """Fetch all user profiles."""
    client = get_supabase()
    if not client: return []
    try:
        res = client.table("profiles").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        st.error(f"Fetch users failed: {e}")
        return []

def get_all_transactions():
    """Fetch recent transactions across platform."""
    client = get_supabase()
    if not client: return []
    try:
        # Join with profiles to get email? Supabase join syntax:
        # select("*, profiles(email)")
        res = client.table("transactions").select("*, profiles(email)").order("created_at", desc=True).limit(50).execute()
        return res.data
    except Exception as e:
        st.error(f"Fetch transactions failed: {e}")
        return []

def admin_dashboard():
    """Render the Admin Dashboard."""
    if not is_admin():
        st.error("⛔ Access Denied. Admins only.")
        return

    st.title("🛡️ 管理员后台")
    st.markdown("全平台用户管理与财务监控。")

    tab_users, tab_finance, tab_ops = st.tabs(["👥 用户管理", "💰 财务流水", "⚙️ 全局运维"])

    # --- Tab 1: User Management ---
    with tab_users:
        st.subheader("用户列表")
        users = get_all_users()
        if users:
            # Display as table
            df = pd.DataFrame(users)
            st.dataframe(df[["id", "email", "balance", "role", "membership_tier", "created_at"]], width="stretch")

            st.divider()
            st.subheader("✏️ 余额调整 / 编辑用户")
            
            selected_user_id = st.selectbox(
                "选择用户", 
                [u['id'] for u in users], 
                format_func=lambda x: f"{next((u['email'] for u in users if u['id'] == x), x)} (${next((u['balance'] for u in users if u['id'] == x), 0)})"
            )
            
            if selected_user_id:
                target_user = next((u for u in users if u['id'] == selected_user_id), None)
                
                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_balance = st.number_input("余额 ($)", value=float(target_user.get('balance', 0.0)))
                    with col2:
                        new_role = st.selectbox("角色", ["user", "admin"], index=0 if target_user.get('role') == 'user' else 1)
                    
                    submit = st.form_submit_button("保存修改")
                    
                    if submit:
                        client = get_supabase()
                        try:
                            client.table("profiles").update({
                                "balance": new_balance,
                                "role": new_role
                            }).eq("id", selected_user_id).execute()
                            st.success("用户更新成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")

    # --- Tab 2: Finance ---
    with tab_finance:
        st.subheader("最近 50 笔交易")
        txs = get_all_transactions()
        if txs:
            # Flatten data for display
            display_txs = []
            for t in txs:
                user_email = t['profiles']['email'] if t.get('profiles') else 'Unknown'
                display_txs.append({
                    "Time": t['created_at'],
                    "User": user_email,
                    "Type": t['type'],
                    "Amount": t['amount'],
                    "Description": t['description']
                })
            st.dataframe(pd.DataFrame(display_txs), use_container_width=True)
        else:
            st.info("暂无交易记录")

    # --- Tab 3: Ops ---
    with tab_ops:
        st.subheader("🤖 全局计费触发")
        st.warning("这将对所有用户执行每日扣费逻辑。建议每天仅执行一次。")
        
        if st.button("🔴 立即执行全平台日结"):
            users = get_all_users()
            progress = st.progress(0)
            status = st.empty()
            
            count = 0
            total = len(users)
            
            for i, u in enumerate(users):
                status.text(f"Processing {u['email']}...")
                process_daily_billing(u['id'])
                count += 1
                progress.progress((i + 1) / total)
            
            st.success(f"已处理 {count} 个用户的账单。")

    # Return button
    if st.sidebar.button("⬅️ 返回前台"):
        st.session_state['admin_mode'] = False
        st.rerun()
