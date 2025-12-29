import streamlit as st
import json
import os
import pandas as pd
import time
from logic import launch_base_instance, AMI_MAPPING, get_instance_status, terminate_instance, scan_all_instances, check_account_health, check_capacity
from templates import PROJECT_REGISTRY, generate_script
from db import log_instance, get_user_instances, update_instance_status, add_aws_credential, get_user_credentials, delete_aws_credential, sync_instances, update_credential_status, get_instance_private_key, update_instance_health, update_instance_project
from auth import login_page, get_current_user, sign_out
from monitor import check_instance_process, install_project_via_ssh, detect_installed_project
from billing import check_balance, get_user_profile, add_balance, process_daily_billing, calculate_daily_cost, BASE_DAILY_FEE, EC2_INSTANCE_FEE, LIGHTSAIL_INSTANCE_FEE, GFW_CHECK_FEE

# Import Admin Dashboard
from admin import admin_dashboard

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

# Force refresh user role from DB to ensure instant admin access after DB update
if user:
    try:
        current_profile = get_user_profile(user.id)
        if current_profile:
            role = current_profile.get("role", "user")
            st.session_state["user_role"] = role
    except Exception as e:
        print(f"Role refresh failed: {e}")

# --- Admin Mode Router ---
if "admin_mode" in st.session_state and st.session_state["admin_mode"]:
    admin_dashboard()
    st.stop() # Stop rendering the rest of the app

# --- Main App (Authenticated) ---

st.sidebar.markdown(f"👤 **{user.email}**")

# Billing Info in Sidebar
profile = get_user_profile(user.id)
balance = float(profile.get("balance", 0.0) if profile else 0.0)
st.sidebar.markdown("---")
st.sidebar.markdown(f"💰 **余额: ${balance:.2f}**")
if balance <= 0:
    st.sidebar.error("⚠️ 余额不足，服务受限")

# Admin Entry Button
if "user_role" in st.session_state and st.session_state["user_role"] == 'admin':
    st.sidebar.markdown("---")
    if st.sidebar.button("🛡️ 进入管理员后台", type="primary"):
        st.session_state["admin_mode"] = True
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("登出"):
    sign_out()
    st.rerun()

st.title("AWS DePIN Launcher (Pro)")
st.markdown("多账号管理与一键部署平台。")

# Tabs
tab_creds, tab_deploy, tab_manage, tab_billing = st.tabs(["🔑 凭证管理", "🚀 部署节点", "⚙️ 实例监控", "💳 会员中心"])

# Load existing config
config = load_config()
default_region = config.get('region', 'us-east-1')
default_project = config.get('project', list(PROJECT_REGISTRY.keys())[0])

# ====================
# TAB 1: Credentials Management
# ====================
with tab_creds:
    st.header("AWS 凭证管理")
    
    # 1.1 Batch Import Section
    with st.expander("📥 批量导入凭证", expanded=False):
        st.caption("格式：`备注, AccessKey, SecretKey` (每行一个，使用英文逗号分隔)")
        batch_input = st.text_area("粘贴凭证列表", height=150, placeholder="Account1, AKIA..., wJalr...\nAccount2, AKIA..., 8klM...")
        
        if st.button("开始批量导入"):
            if not batch_input.strip():
                st.error("请输入凭证信息")
            else:
                lines = batch_input.strip().split('\n')
                success_count = 0
                fail_count = 0
                
                progress_bar = st.progress(0)
                
                for i, line in enumerate(lines):
                    try:
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 3:
                            alias, ak, sk = parts[0], parts[1], parts[2]
                            if add_aws_credential(user.id, alias, ak, sk):
                                success_count += 1
                            else:
                                fail_count += 1
                        else:
                            fail_count += 1
                    except Exception:
                        fail_count += 1
                    progress_bar.progress((i + 1) / len(lines))
                
                st.success(f"导入完成: 成功 {success_count}, 失败 {fail_count}")
                time.sleep(1)
                st.rerun()

    st.divider()

    # 1.2 Single Add & List (Existing)
    col_add, col_check = st.columns([3, 1])
    with col_add:
        st.markdown("在此添加你的 AWS Access Keys。部署时可直接选择，无需重复输入。")
    with col_check:
        if st.button("🏥 一键体检 (含配额)", help="检查所有账号的状态及配额"):
            # Check balance first
            allowed, msg = check_balance(user.id)
            if not allowed:
                st.error(msg)
            else:
                with st.spinner("正在检查所有账号健康状态与配额..."):
                    creds = get_user_credentials(user.id)
                    if not creds:
                        st.warning("无账号可检查")
                    else:
                        progress_bar = st.progress(0)
                        for i, cred in enumerate(creds):
                            # Basic Health Check
                            res = check_account_health(cred['access_key_id'], cred['secret_access_key'])
                            update_credential_status(cred['id'], res['status'])
                            
                            # Quota Check if active
                            quota_msg = ""
                            if res['status'] == 'active':
                                cap = check_capacity(cred['access_key_id'], cred['secret_access_key'], default_region)
                                quota_msg = f" | 配额: {cap['used']}/{cap['limit']}"
                            
                            if res['status'] != 'active':
                                st.toast(f"{cred['alias_name']}: {res['msg']}", icon="⚠️")
                            else:
                                st.toast(f"{cred['alias_name']}: 正常 {quota_msg}", icon="✅")
                            
                            progress_bar.progress((i + 1) / len(creds))
                            
                        st.success("检查完成！")
                        time.sleep(1)
                        st.rerun()

    # Add new credential (Single)
    with st.expander("➕ 添加单条凭证", expanded=False):
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
# TAB 2: Deploy (Updated Flow)
# ====================
with tab_deploy:
    if not creds:
        st.warning("请先在“凭证管理”页面添加 AWS 凭证。")
    else:
        st.sidebar.header("部署配置")
        # Region selection
        region_options = list(AMI_MAPPING.keys())
        try:
            r_index = region_options.index(default_region)
        except ValueError:
            r_index = 0
        region = st.sidebar.selectbox("AWS Region", region_options, index=r_index)

        st.info("💡 **新流程**: 先启动基础实例，然后在“实例监控”页安装具体项目。")

        st.subheader("启动基础实例 (Base Instance)")
        
        # 2.1 Batch Launch Selection
        st.write("选择要部署的 AWS 账号 (可多选):")
        
        # Filter active creds
        active_creds = [c for c in creds if c.get('status') != 'suspended']
        
        cred_options = {f"{c['alias_name']} ({c['access_key_id'][:6]}...)": c['id'] for c in active_creds}
        
        selected_cred_labels = st.multiselect(
            "目标账号", 
            options=list(cred_options.keys()),
            default=[]
        )
        
        if st.button("🚀 批量启动实例", type="primary"):
            if not selected_cred_labels:
                st.error("请至少选择一个账号")
            else:
                # Balance Check
                allowed, msg = check_balance(user.id)
                if not allowed:
                    st.error(f"❌ {msg}")
                else:
                    # Confirm Launch
                    target_creds = [next(c for c in creds if c['id'] == cred_options[label]) for label in selected_cred_labels]
                    
                    progress_bar = st.progress(0)
                    status_area = st.empty()
                    results = []
                    
                    for i, cred in enumerate(target_creds):
                        status_area.text(f"正在检查配额: {cred['alias_name']}...")
                        
                        # Quota Check
                        try:
                            cap = check_capacity(cred['access_key_id'], cred['secret_access_key'], region)
                            if cap['available'] < 1:
                                results.append(f"⚠️ {cred['alias_name']}: 跳过 - 配额不足 (已用 {cap['used']}/{cap['limit']})")
                                progress_bar.progress((i + 1) / len(target_creds))
                                continue
                        except Exception as e:
                            results.append(f"⚠️ {cred['alias_name']}: 配额检查失败 - {e}")
                            # Optionally continue or skip? Continue but risky. Let's try to launch.
                        
                        status_area.text(f"正在启动: {cred['alias_name']}...")
                        try:
                            result = launch_base_instance(
                                cred['access_key_id'],
                                cred['secret_access_key'],
                                region
                            )
                            
                            if result['status'] == 'success':
                                log_instance(
                                    user_id=user.id,
                                    credential_id=cred['id'],
                                    instance_id=result['id'],
                                    ip=result['ip'],
                                    region=region,
                                    project_name="Pending",
                                    status="active",
                                    private_key=result.get('private_key')
                                )
                                results.append(f"✅ {cred['alias_name']}: 成功 ({result['id']})")
                            else:
                                results.append(f"❌ {cred['alias_name']}: 失败 - {result['msg']}")
                        except Exception as e:
                            results.append(f"❌ {cred['alias_name']}: 异常 - {str(e)}")
                            
                        progress_bar.progress((i + 1) / len(target_creds))
                    
                    status_area.empty()
                    st.success("批量操作完成！")
                    with st.expander("查看详细结果", expanded=True):
                        for r in results:
                            st.write(r)

# ====================
# TAB 3: Manage Instances
# ====================
with tab_manage:
    st.header("全平台实例监控")
    
    col_refresh, col_scan = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 深度刷新 (项目状态)", help="同时检查AWS实例状态和项目运行情况"):
            with st.spinner("正在进行全量深度检查..."):
                # 1. Fetch current instances from DB
                current_instances = get_user_instances(user.id)
                
                # 2. Filter valid ones (Running only)
                targets = [i for i in current_instances if i['status'] == 'running']
                
                if not targets:
                    st.info("没有运行中的实例需检查")
                    time.sleep(1)
                    st.rerun()
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, inst in enumerate(targets):
                        status_text.text(f"Checking {inst['ip_address']} ({inst['project_name']})...")
                        
                        # SSH Check
                        pkey = get_instance_private_key(inst['instance_id'])
                        if pkey:
                            # 1. Auto-detect project if Pending or forcing refresh
                            detected_proj, det_msg = detect_installed_project(inst['ip_address'], pkey)
                            
                            if detected_proj:
                                # If we detected a project and it's different from DB (or DB is Pending), update it
                                if detected_proj != inst['project_name']:
                                    update_instance_project(inst['instance_id'], detected_proj)
                                    inst['project_name'] = detected_proj # Update local var for next check
                                    st.toast(f"Detected {detected_proj} on {inst['ip_address']}", icon="✅")
                            
                            # 2. Check health based on (possibly updated) project
                            is_healthy, msg = check_instance_process(inst['ip_address'], pkey, inst['project_name'])
                            new_health = "Healthy" if is_healthy else f"Error: {msg}"
                        else:
                            new_health = "Error: Missing Private Key"
                        
                        update_instance_health(inst['instance_id'], new_health)
                        progress_bar.progress((idx + 1) / len(targets))
                    
                    status_text.empty()
                    st.success("深度检查完成！")
                    time.sleep(1)
                    st.rerun()
            
    with col_scan:
        if st.button("🌍 全网扫描 & 同步"):
            allowed, msg = check_balance(user.id)
            if not allowed:
                st.error(msg)
            else:
                if not creds:
                    st.error("请先添加 AWS 凭证")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_steps = len(creds) * len(AMI_MAPPING)
                    current_step = 0
                    total_new = 0
                    total_updated = 0
                    
                    for cred in creds:
                        if cred.get('status') == 'suspended':
                            current_step += len(AMI_MAPPING)
                            progress_bar.progress(min(current_step / total_steps, 1.0))
                            continue

                        for region_code in AMI_MAPPING.keys():
                            current_step += 1
                            progress = current_step / total_steps
                            progress_bar.progress(progress)
                            status_text.text(f"Scanning: {cred['alias_name']} - {region_code}...")
                            
                            aws_instances = scan_all_instances(
                                cred['access_key_id'], 
                                cred['secret_access_key'], 
                                region_code
                            )
                            
                            if aws_instances:
                                res = sync_instances(user.id, cred['id'], region_code, aws_instances)
                                total_new += res['new']
                                total_updated += res['updated']
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    st.success(f"扫描完成！新增 {total_new}，更新 {total_updated}。")
                    time.sleep(2)
                    st.rerun()

    with st.spinner("正在同步数据..."):
        db_instances = get_user_instances(user.id)
        
        if not db_instances:
            st.info("暂无实例。")
        else:
            # ... (Existing grouping logic) ...
            batch_map = {}
            cred_lookup = {c['id']: c for c in creds}

            for inst in db_instances:
                c_id = inst['credential_id']
                if not c_id or c_id not in cred_lookup: continue
                r = inst['region']
                if c_id not in batch_map: batch_map[c_id] = {}
                if r not in batch_map[c_id]: batch_map[c_id][r] = []
                batch_map[c_id][r].append(inst['instance_id'])
            
            real_time_status = {}
            for c_id, regions in batch_map.items():
                cred = cred_lookup[c_id]
                if cred.get('status') == 'suspended': continue
                for r, i_ids in regions.items():
                    status_dict = get_instance_status(cred['access_key_id'], cred['secret_access_key'], r, i_ids)
                    real_time_status.update(status_dict)
            
            display_data = []
            for inst in db_instances:
                i_id = inst['instance_id']
                cred_info = inst.get('aws_credentials', {})
                cred_status = cred_info.get('status', 'active') if cred_info else 'active'
                
                if cred_status == 'suspended':
                    current_status = "account-suspended"
                else:
                    current_status = real_time_status.get(i_id, inst['status'])
                
                if current_status != inst['status'] and current_status != "account-suspended":
                    update_instance_status(i_id, current_status)
                
                alias = cred_info.get('alias_name', 'Unknown') if cred_info else 'Unknown'
                health = inst.get('health_status', 'Unknown')

                display_data.append({
                    "Account": alias,
                    "Project": inst['project_name'],
                    "Instance ID": i_id,
                    "IP Address": inst['ip_address'],
                    "Region": inst['region'],
                    "Status": current_status,
                    "Health": health,
                    "Created": inst['created_at'][:16].replace('T', ' '),
                    "_cred_id": inst['credential_id'],
                    "_has_key": bool(inst.get('private_key'))
                })
            
            df = pd.DataFrame(display_data).drop(columns=["_cred_id", "_has_key"])
            st.dataframe(df, width="stretch")
            
            st.divider()

            # --- Advanced Actions & Installation ---
            st.subheader("🛠️ 深度运维 & 项目安装")
            
            col_target, col_actions = st.columns([2, 2])
            
            with col_target:
                ssh_ready_instances = [d for d in display_data if d['Status'] == 'running' and d['_has_key']]
                if not ssh_ready_instances:
                    st.caption("没有可操作的实例")
                    selected_ssh_instance = None
                else:
                    # Search for Instance
                    inst_search_term = st.text_input("🔍 搜索实例 (ID/IP/项目) - 输入后按回车", key="single_inst_search").strip().lower()
                    
                    filtered_instances = []
                    for d in ssh_ready_instances:
                        search_str = f"{d['Instance ID']} {d['IP Address']} {d['Project']} {d['Account']}".lower()
                        if not inst_search_term or inst_search_term in search_str:
                            filtered_instances.append(d)
                            
                    if not filtered_instances and inst_search_term:
                        st.caption("无匹配实例")
                        selected_ssh_instance = None
                    else:
                        selected_ssh_instance = st.selectbox(
                            "选择目标实例",
                            [d['Instance ID'] for d in filtered_instances],
                            format_func=lambda x: f"{x} - {next((d['Project'] for d in filtered_instances if d['Instance ID'] == x), '')} ({next((d['IP Address'] for d in filtered_instances if d['Instance ID'] == x), '')})"
                        )

            with col_actions:
                if selected_ssh_instance:
                    target_info = next((d for d in display_data if d['Instance ID'] == selected_ssh_instance), None)
                    
                    # Install Project UI
                    with st.expander("📦 安装/切换项目", expanded=True):
                        proj_options = list(PROJECT_REGISTRY.keys())
                        target_proj = st.selectbox("选择要安装的项目", proj_options)
                        
                        # Params inputs
                        proj_conf = PROJECT_REGISTRY[target_proj]
                        input_params = {}
                        for p in proj_conf['params']:
                            input_params[p] = st.text_input(f"{p}", key=f"inst_{p}")
                            
                        if st.button("开始安装", type="primary"):
                            # Validate Params
                            missing_params = [p for p in proj_conf['params'] if not input_params.get(p)]
                            if missing_params:
                                st.error(f"请填写必要参数: {', '.join(missing_params)}")
                            else:
                                allowed, msg = check_balance(user.id)
                                if not allowed:
                                    st.error(msg)
                                else:
                                    with st.spinner("正在通过 SSH 安装..."):
                                        pkey = get_instance_private_key(selected_ssh_instance)
                                        if not pkey:
                                            st.error("无法解密私钥")
                                        else:
                                            script = generate_script(target_proj, **input_params)
                                            res = install_project_via_ssh(target_info['IP Address'], pkey, script)
                                            
                                            if res['status'] == 'success':
                                                update_instance_project(selected_ssh_instance, target_proj)
                                                st.success(f"安装指令已发送！")
                                                st.info("请稍后刷新查看状态。")
                                                with st.expander("查看输出"):
                                                    st.code(res['output'])
                                            else:
                                                st.error(f"安装失败: {res['msg']}")

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("🔍 深度检测"):
                             # Balance Check
                            allowed, msg = check_balance(user.id)
                            if not allowed:
                                st.error(msg)
                            else:
                                with st.spinner("Checking..."):
                                    pkey = get_instance_private_key(selected_ssh_instance)
                                    if pkey:
                                        is_healthy, msg = check_instance_process(target_info['IP Address'], pkey, target_info['Project'])
                                        new_health = "Healthy" if is_healthy else f"Error: {msg}"
                                        update_instance_health(selected_ssh_instance, new_health)
                                        if is_healthy: st.success(msg)
                                        else: st.error(msg)
                                        time.sleep(1)
                                        st.rerun()

            # --- 3.1 Batch Project Installation ---
            st.divider()
            st.subheader("📦 批量项目安装")
            
            # Filter SSH-ready instances
            ssh_ready_instances = [d for d in display_data if d['Status'] == 'running' and d['_has_key']]
            
            if not ssh_ready_instances:
                st.caption("没有可操作的实例 (需 Running 且有私钥)")
            else:
                # Project Selection First
                col_proj, col_params = st.columns([1, 2])
                with col_proj:
                    proj_options = list(PROJECT_REGISTRY.keys())
                    target_proj = st.selectbox("选择要安装的项目", proj_options, key="batch_proj_select")
                
                with col_params:
                    proj_conf = PROJECT_REGISTRY[target_proj]
                    input_params = {}
                    for p in proj_conf['params']:
                        input_params[p] = st.text_input(f"{p}", key=f"batch_inst_{p}").strip()

                # Instance Selection
                st.write("选择目标实例:")
                
                instance_options = {f"{d['Instance ID']} ({d['IP Address']}) - {d['Account']}": d['Instance ID'] for d in ssh_ready_instances}
                selected_inst_labels = st.multiselect(
                    "勾选实例",
                    options=list(instance_options.keys()),
                    default=[]
                )
                
                if st.button("🚀 开始批量安装", type="primary"):
                    if not selected_inst_labels:
                        st.error("请选择至少一个实例")
                    else:
                        # Validate Params
                        missing_params = [p for p in proj_conf['params'] if not input_params.get(p)]
                        if missing_params:
                            st.error(f"请填写必要参数: {', '.join(missing_params)}")
                        else:
                            allowed, msg = check_balance(user.id)
                            if not allowed:
                                st.error(msg)
                            else:
                                # Generate script once
                                script = generate_script(target_proj, **input_params)
                                
                                progress_bar = st.progress(0)
                                status_area = st.empty()
                                results = []
                                target_ids = [instance_options[l] for l in selected_inst_labels]
                                
                                for i, i_id in enumerate(target_ids):
                                    target_data = next(d for d in display_data if d['Instance ID'] == i_id)
                                    status_area.text(f"Installing on {target_data['IP Address']}...")
                                    
                                    pkey = get_instance_private_key(i_id)
                                    if pkey:
                                        res = install_project_via_ssh(target_data['IP Address'], pkey, script)
                                        if res['status'] == 'success':
                                            update_instance_project(i_id, target_proj)
                                            results.append(f"✅ {target_data['IP Address']}: 指令已发送")
                                        else:
                                            results.append(f"❌ {target_data['IP Address']}: {res['msg']}")
                                    else:
                                        results.append(f"❌ {target_data['IP Address']}: 无法获取私钥")
                                    
                                    progress_bar.progress((i + 1) / len(target_ids))
                                
                                status_area.empty()
                                st.success("批量安装指令发送完成！")
                                with st.expander("查看详细结果", expanded=True):
                                    for r in results:
                                        st.write(r)

            # Terminate (No balance check needed for cleanup?)
            st.divider()
            st.subheader("⚠️ 危险操作")
            
            active_instances = [d for d in display_data if d['Status'] not in ['terminated', 'shutting-down', 'account-suspended']]
            
            # Search for Terminate Instance
            term_search_term = st.text_input("🔍 搜索要关闭的实例 (ID/IP) - 输入后按回车筛选", key="term_inst_search").strip().lower()
            
            filtered_term_instances = []
            for d in active_instances:
                search_str = f"{d['Instance ID']} {d['IP Address']}".lower()
                if not term_search_term or term_search_term in search_str:
                    filtered_term_instances.append(d)
            
            if not filtered_term_instances and term_search_term:
                 st.caption("无匹配实例")
                 instance_to_term = None
            else:
                instance_to_term = st.selectbox("选择要关闭的实例", [d['Instance ID'] for d in filtered_term_instances], key="term_select") if filtered_term_instances else None
            
            if instance_to_term and st.button("🛑 关闭实例", type="primary"):
                target = next((d for d in display_data if d['Instance ID'] == instance_to_term), None)
                if target:
                    cred = cred_lookup.get(target['_cred_id'])
                    if cred:
                        terminate_instance(cred['access_key_id'], cred['secret_access_key'], target['Region'], instance_to_term)
                        update_instance_status(instance_to_term, "shutting-down")
                        st.success("已关闭")
                        time.sleep(1)
                        st.rerun()

# ====================
# TAB 4: Billing Center
# ====================
with tab_billing:
    st.header("💳 会员中心")
    
    col_bal, col_daily = st.columns(2)
    
    with col_bal:
        st.metric("当前余额", f"${balance:.4f}")
        
        with st.expander("充值 (模拟)", expanded=True):
            amount = st.number_input("充值金额 ($)", min_value=1.0, value=10.0, step=1.0)
            if st.button("确认充值"):
                if add_balance(user.id, amount, "用户充值"):
                    st.success(f"成功充值 ${amount}！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("充值失败")

    with col_daily:
        daily_est = calculate_daily_cost(user.id)
        st.metric("预计每日消耗", f"${daily_est:.4f}")
        st.caption("包含基础费 + 实例维护费 + 增值服务费")
        
        if st.button("手动触发日结 (测试用)"):
            process_daily_billing(user.id)
            st.success("结算完成")
            time.sleep(1)
            st.rerun()

    st.subheader("收费标准")
    st.markdown(f"""
    - **基础费用**: ${BASE_DAILY_FEE} / 天 (仅当绑定了AWS账号时收取)
    - **EC2 实例托管**: ${EC2_INSTANCE_FEE} / 个 / 天
    - **GFW 自动检测**: ${GFW_CHECK_FEE} / 个 / 天 (即将上线)
    - **Lightsail 实例**: ${LIGHTSAIL_INSTANCE_FEE} / 个 / 天
    
    > ℹ️ 余额为 0 时将停止自动替补与深度检测服务。
    """)
