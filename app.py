import streamlit as st
import json
import os
import pandas as pd
import time
from logic import launch_instance, AMI_MAPPING, get_instance_status, terminate_instance, scan_all_instances, check_account_health
from templates import PROJECT_REGISTRY, generate_script
from db import log_instance, get_user_instances, update_instance_status, add_aws_credential, get_user_credentials, delete_aws_credential, sync_instances, update_credential_status
from auth import login_page, get_current_user, sign_out

# Set page configuration
st.set_page_config(page_title="AWS DePIN Launcher", page_icon="🚀", layout="wide")

CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config_data):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f)
        st.sidebar.success("配置已保存！")
    except Exception as e:
        st.sidebar.error(f"保存失败: {e}")

# Check authentication status
user = get_current_user()

if not user:
    login_page()
    st.stop()

# --- Main App (Authenticated) ---

st.sidebar.markdown(f"👤 **{user.email}**")
if st.sidebar.button("登出"):
    sign_out()
    st.rerun()

st.title("AWS DePIN Launcher (Pro)")
st.markdown("多账号管理与一键部署平台。")

# Tabs
tab_creds, tab_deploy, tab_manage = st.tabs(["🔑 凭证管理", "🚀 部署节点", "⚙️ 实例监控"])

# Load existing config
config = load_config()
default_region = config.get('region', 'us-east-1')
default_project = config.get('project', list(PROJECT_REGISTRY.keys())[0])

# ====================
# TAB 1: Credentials Management
# ====================
with tab_creds:
    st.header("AWS 凭证管理")
    
    col_add, col_check = st.columns([3, 1])
    with col_add:
        st.markdown("在此添加你的 AWS Access Keys。部署时可直接选择，无需重复输入。")
    with col_check:
        if st.button("🏥 一键体检", help="检查所有账号的可用状态"):
            with st.spinner("正在检查所有账号健康状态..."):
                creds = get_user_credentials(user.id)
                if not creds:
                    st.warning("无账号可检查")
                else:
                    for cred in creds:
                        res = check_account_health(cred['access_key_id'], cred['secret_access_key'])
                        update_credential_status(cred['id'], res['status'])
                        if res['status'] != 'active':
                            st.toast(f"{cred['alias_name']}: {res['msg']}", icon="⚠️")
                    st.success("检查完成！")
                    time.sleep(1)
                    st.rerun()

    # Add new credential
    with st.expander("➕ 添加新凭证", expanded=False):
        with st.form("add_cred_form"):
            alias = st.text_input("备注名称 (如: 公司测试号)", placeholder="My AWS Account")
            ak = st.text_input("Access Key ID", type="password")
            sk = st.text_input("Secret Access Key", type="password")
            submitted = st.form_submit_button("保存凭证")
            if submitted:
                if not alias or not ak or not sk:
                    st.error("请填写完整信息")
                else:
                    res = add_aws_credential(user.id, alias, ak, sk)
                    if res:
                        st.success("凭证添加成功！")
                        st.rerun()
                    else:
                        st.error("添加失败，请重试")

    # List existing credentials
    creds = get_user_credentials(user.id)
    if creds:
        st.subheader("已保存的凭证")
        for cred in creds:
            col1, col2, col3, col4, col5 = st.columns([2, 3, 1, 2, 1])
            with col1:
                st.markdown(f"**{cred['alias_name']}**")
            with col2:
                st.code(cred['access_key_id'])
            with col3:
                # Status Badge
                status = cred.get('status', 'active')
                if status == 'active':
                    st.markdown("🟢 正常")
                elif status == 'suspended':
                    st.markdown("🔴 封禁/验证")
                elif status == 'error':
                    st.markdown("⚠️ 错误")
                else:
                    st.markdown(f"⚪ {status}")
            with col4:
                last_checked = cred.get('last_checked')
                if last_checked:
                    st.caption(f"检查于: {last_checked[:16].replace('T', ' ')}")
                else:
                    st.caption("从未检查")
            with col5:
                if st.button("🗑️", key=f"del_{cred['id']}", help="删除此凭证"):
                    delete_aws_credential(cred['id'])
                    st.rerun()
    else:
        st.info("暂无凭证，请先添加。")

# ====================
# TAB 2: Deploy
# ====================
with tab_deploy:
    if not creds:
        st.warning("请先在“凭证管理”页面添加 AWS 凭证。")
    else:
        # --- Sidebar (Shared Config) ---
        st.sidebar.header("部署配置")

        # Region selection
        region_options = list(AMI_MAPPING.keys())
        try:
            r_index = region_options.index(default_region)
        except ValueError:
            r_index = 0
        region = st.sidebar.selectbox("AWS Region", region_options, index=r_index)

        # Project selection
        project_options = list(PROJECT_REGISTRY.keys())
        try:
            p_index = project_options.index(default_project)
        except ValueError:
            p_index = 0
        project_name = st.sidebar.selectbox("选择项目 (Project)", project_options, index=p_index)

        if st.sidebar.button("保存默认配置"):
            save_config({'region': region, 'project': project_name})

        # --- Main Interface ---
        st.subheader("1. 选择账号与项目")
        
        # Select Credential
        # Filter only active credentials ideally, or show warning
        cred_options = {c['alias_name']: c for c in creds}
        selected_alias = st.selectbox("选择 AWS 账号", list(cred_options.keys()))
        selected_cred = cred_options[selected_alias]
        
        if selected_cred.get('status') == 'suspended':
            st.error("⚠️ 该账号已被标记为封禁/欠费，部署可能会失败！")
        elif selected_cred.get('status') == 'error':
            st.warning("⚠️ 该账号上次检查报错，请确认凭证是否有效。")

        st.subheader("2. 配置项目参数")
        project_info = PROJECT_REGISTRY[project_name]
        st.info(project_info['description'])
        
        # Dynamic Form Generation
        input_params = {}
        missing_params = []

        with st.container(border=True):
            for param in project_info['params']:
                val = st.text_input(f"Enter {param}", key=f"param_{project_name}_{param}")
                input_params[param] = val.strip()
                if not val.strip():
                    missing_params.append(param)

        st.markdown("---")

        # Launch Button
        if st.button("🚀 立即部署", type="primary", use_container_width=True):
            if missing_params:
                st.error(f"❌ 缺少项目参数: {', '.join(missing_params)}")
            else:
                status_container = st.status("正在初始化部署流程...", expanded=True)
                try:
                    # 1. Generate Script
                    status_container.write("🔨 正在生成 User Data 脚本...")
                    user_data = generate_script(project_name, **input_params)
                    
                    # 2. Launch Instance
                    status_container.write(f"☁️ 正在连接 AWS {region} ({selected_alias})...")
                    result = launch_instance(
                        selected_cred['access_key_id'], 
                        selected_cred['secret_access_key'], 
                        region, 
                        user_data, 
                        project_name
                    )
                    
                    if result['status'] == 'success':
                        # 3. Log to DB
                        status_container.write("💾 正在记录部署信息到数据库...")
                        log_instance(
                            user_id=user.id,
                            credential_id=selected_cred['id'],
                            instance_id=result['id'],
                            ip=result['ip'],
                            region=region,
                            project_name=project_name,
                            status="active"
                        )
                        
                        status_container.update(label="部署成功！", state="complete", expanded=False)
                        st.success(f"✅ {project_name} 部署成功！")
                        st.info(f"""
                        **详细信息:**
                        - **Account:** `{selected_alias}`
                        - **Instance ID:** `{result['id']}`
                        - **Public IP:** `{result['ip']}`
                        - **Region:** `{region}`
                        
                        ⏳ **预计 3-5 分钟后上线**。
                        """)
                    else:
                        status_container.update(label="部署失败", state="error", expanded=True)
                        st.error(f"❌ 启动失败: {result['msg']}")
                        
                except Exception as e:
                    status_container.update(label="发生系统错误", state="error")
                    st.error(f"异常详情: {str(e)}")

# ====================
# TAB 3: Manage Instances
# ====================
with tab_manage:
    st.header("全平台实例监控")
    
    col_refresh, col_scan = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 刷新状态"):
            st.rerun()
            
    with col_scan:
        if st.button("🌍 全网扫描 & 同步", help="扫描所有账号下所有区域的实例，并同步到数据库"):
            if not creds:
                st.error("请先添加 AWS 凭证")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_steps = len(creds) * len(AMI_MAPPING)
                current_step = 0
                total_new = 0
                total_updated = 0
                
                status_text.text("正在初始化全网扫描...")
                
                for cred in creds:
                    # Skip suspended accounts to save time/errors
                    if cred.get('status') == 'suspended':
                        status_text.text(f"跳过封禁账号: {cred['alias_name']}...")
                        current_step += len(AMI_MAPPING)
                        progress_bar.progress(min(current_step / total_steps, 1.0))
                        continue

                    for region_code in AMI_MAPPING.keys():
                        current_step += 1
                        progress = current_step / total_steps
                        progress_bar.progress(progress)
                        status_text.text(f"正在扫描: {cred['alias_name']} - {region_code}...")
                        
                        # 1. Scan AWS
                        aws_instances = scan_all_instances(
                            cred['access_key_id'], 
                            cred['secret_access_key'], 
                            region_code
                        )
                        
                        # 2. Sync with DB
                        if aws_instances:
                            res = sync_instances(user.id, cred['id'], region_code, aws_instances)
                            total_new += res['new']
                            total_updated += res['updated']
                
                progress_bar.progress(1.0)
                status_text.empty()
                st.success(f"扫描完成！发现 {total_new} 台新机器，更新了 {total_updated} 台机器的状态。")
                time.sleep(2)
                st.rerun()

    with st.spinner("正在同步数据..."):
        # 1. Get all instances for this user from DB
        db_instances = get_user_instances(user.id)
        
        if not db_instances:
            st.info("暂无实例。")
        else:
            # 2. Group instances by Credential and Region to optimize AWS calls
            # Structure: { cred_id: { region: [instance_ids] } }
            batch_map = {}
            # Helper to quickly find creds
            cred_lookup = {c['id']: c for c in creds}

            for inst in db_instances:
                c_id = inst['credential_id']
                if not c_id or c_id not in cred_lookup: continue # Skip if cred deleted
                
                r = inst['region']
                if c_id not in batch_map: batch_map[c_id] = {}
                if r not in batch_map[c_id]: batch_map[c_id][r] = []
                batch_map[c_id][r].append(inst['instance_id'])
            
            # 3. Fetch Real-time Status from AWS
            real_time_status = {} # {instance_id: status}
            
            for c_id, regions in batch_map.items():
                cred = cred_lookup[c_id]
                # Skip suspended accounts check
                if cred.get('status') == 'suspended':
                    continue
                    
                for r, i_ids in regions.items():
                    # Call AWS
                    status_dict = get_instance_status(
                        cred['access_key_id'], 
                        cred['secret_access_key'], 
                        r, 
                        i_ids
                    )
                    real_time_status.update(status_dict)
            
            # 4. Prepare Display Data
            display_data = []
            for inst in db_instances:
                i_id = inst['instance_id']
                cred_info = inst.get('aws_credentials', {})
                cred_status = cred_info.get('status', 'active') if cred_info else 'active'
                
                # Determine status
                # If we couldn't fetch (e.g. cred deleted or suspended), keep old status or mark unknown
                if cred_status == 'suspended':
                    current_status = "account-suspended"
                else:
                    current_status = real_time_status.get(i_id, inst['status'])
                
                # If AWS says 'terminated' but DB says 'active', update DB
                if current_status != inst['status'] and current_status != "account-suspended":
                    update_instance_status(i_id, current_status)
                
                # Get alias
                alias = cred_info.get('alias_name', 'Unknown/Deleted') if cred_info else 'Unknown'

                display_data.append({
                    "Account": alias,
                    "Project": inst['project_name'],
                    "Instance ID": i_id,
                    "IP Address": inst['ip_address'],
                    "Region": inst['region'],
                    "Status": current_status,
                    "Created": inst['created_at'][:16].replace('T', ' '),
                    "_cred_id": inst['credential_id'] # Hidden for logic
                })
            
            # 5. Render Table
            df = pd.DataFrame(display_data).drop(columns=["_cred_id"])
            st.dataframe(df, use_container_width=True)
            
            # 6. Action: Terminate
            st.subheader("⚠️ 实例操作")
            term_col1, term_col2 = st.columns([3, 1])
            with term_col1:
                # Filter out already terminated instances
                active_instances = [d for d in display_data if d['Status'] not in ['terminated', 'shutting-down', 'account-suspended']]
                if not active_instances:
                    st.caption("没有活跃实例可操作")
                    instance_to_term = None
                else:
                    instance_to_term = st.selectbox(
                        "选择要关闭的实例", 
                        [d['Instance ID'] for d in active_instances],
                        format_func=lambda x: f"{x} ({next((d['Account'] for d in active_instances if d['Instance ID'] == x), '')})"
                    )
            
            with term_col2:
                if instance_to_term:
                    if st.button("🛑 关闭实例", type="primary"):
                        # Find details
                        target = next((d for d in display_data if d['Instance ID'] == instance_to_term), None)
                        if target:
                            cred_id = target['_cred_id']
                            region = target['Region']
                            
                            # Get creds
                            cred = cred_lookup.get(cred_id)
                            if cred:
                                with st.spinner(f"正在关闭 {instance_to_term}..."):
                                    res = terminate_instance(
                                        cred['access_key_id'], 
                                        cred['secret_access_key'], 
                                        region, 
                                        instance_to_term
                                    )
                                    if res['status'] == 'success':
                                        st.success("关闭指令已发送")
                                        update_instance_status(instance_to_term, "shutting-down")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"关闭失败: {res['msg']}")
                            else:
                                st.error("无法找到该实例对应的凭证（可能已被删除）。")

