import streamlit as st
import json
import os
import pandas as pd
import time
import extra_streamlit_components as stx
from logic import launch_base_instance, AMI_MAPPING, get_instance_status, terminate_instance, scan_all_instances, check_account_health, check_capacity
from templates import PROJECT_REGISTRY, generate_script
from db import log_instance, get_user_instances, update_instance_status, add_aws_credential, get_user_credentials, delete_aws_credential, sync_instances, update_credential_status, get_instance_private_key, update_instance_health, update_instance_project
from db import log_instance, get_user_instances, update_instance_status, add_aws_credential, get_user_credentials, delete_aws_credential, sync_instances, update_credential_status, get_instance_private_key, update_instance_health, update_instance_projects_status
from billing import get_user_profile, add_balance, calculate_daily_cost, process_daily_billing, BASE_DAILY_FEE, EC2_INSTANCE_FEE, GFW_CHECK_FEE, LIGHTSAIL_INSTANCE_FEE
from auth import login_page, get_current_user, sign_out
from monitor import check_instance_process, install_project_via_ssh, detect_installed_project

# Import Admin Dashboard
from admin import admin_dashboard

from admin import admin_dashboard
st.set_page_config(page_title="AWS DePIN Launcher", page_icon="🚀", layout="wide")

# Initialize Cookie Manager (Must be done in the main script flow)
# cookie_manager = stx.CookieManager(key="auth_cookie_manager")

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
tab_creds, tab_deploy, tab_manage, tab_billing, tab_tools = st.tabs(["🔑 凭证管理", "🚀 部署节点", "⚙️ 实例监控", "💳 会员中心", "🛠️ 工具箱"])

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
        st.caption("格式：`备注, AccessKey, SecretKey, Proxy(可选)` (每行一个，使用英文逗号分隔)")
        batch_input = st.text_area("粘贴凭证列表", height=150, placeholder="Account1, AKIA..., wJalr..., http://user:pass@ip:port\nAccount2, AKIA..., 8klM...")
        
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
                            proxy = parts[3] if len(parts) > 3 else None
                            if add_aws_credential(user.id, alias, ak, sk, proxy):
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
                            proxy_url = cred.get('proxy_url')
                            # Check if proxy is needed but missing
                            if not proxy_url:
                                st.warning(f"⚠️ {cred['alias_name']}: 建议配置代理以提高连接稳定性")
                            
                            res = check_account_health(cred['access_key_id'], cred['secret_access_key'], proxy_url=proxy_url)
                            # update_credential_status called below with quota info
                            
                            # Quota Check if active
                            quota_msg = ""
                            if res['status'] == 'active':
                                cap = check_capacity(cred['access_key_id'], cred['secret_access_key'], default_region, proxy_url=proxy_url)
                                quota_msg = f" | 配额: {cap['used']}/{cap['limit']}"
                                # Update with quota info
                                update_credential_status(cred['id'], res['status'], limit=cap['limit'], used=cap['used'])
                            else:
                                # Update without quota info if not active
                                update_credential_status(cred['id'], res['status'])
                        
                            if res['status'] != 'active':
                                st.toast(f"{cred['alias_name']}: {res['msg']}", icon="⚠️")
                            else:
                                st.toast(f"{cred['alias_name']}: 正常 {quota_msg}", icon="✅")
                            
                            progress_bar.progress((i + 1) / len(creds))
                            
                        st.success("检查完成！")
                        # Clear cache to force reload
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()

    # Add new credential (Single)
    with st.expander("➕ 添加单条凭证", expanded=False):
        with st.form("add_cred_form"):
            alias = st.text_input("备注名称 (如: 公司测试号)", placeholder="My AWS Account")
            ak = st.text_input("Access Key ID", type="password")
            sk = st.text_input("Secret Access Key", type="password")
            proxy = st.text_input("代理地址 (可选)", placeholder="http://user:pass@ip:port")
            submitted = st.form_submit_button("保存凭证")
            if submitted:
                if not alias or not ak or not sk:
                    st.error("请填写完整信息")
                else:
                    res = add_aws_credential(user.id, alias, ak, sk, proxy)
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
                limit = cred.get('vcpu_limit', 0)
                used = cred.get('vcpu_used', 0)
                
                if last_checked:
                    st.markdown(f"**配额: {used} / {limit}**")
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
        
        # 2.0 Launch Mode Selection (Custom Only)
        st.write("配置实例规格:")
        
        col_cpu, col_mem, col_fam, col_os = st.columns(4)
        
        with col_cpu:
            cpu_cores = st.selectbox("CPU 核数", [1, 2, 4, 8, 16, 32, 48, 64], index=1)
            
        with col_mem:
            mem_size = st.selectbox("内存大小 (GB)", [1, 2, 4, 8, 16, 32, 64, 128], index=2)
            
        with col_fam:
            fam_type = st.selectbox("实例系列", ["通用型 (T/M)", "计算型 (C)", "内存型 (R)"], index=0)
            
        with col_os:
            os_type = st.selectbox("操作系统", ["Amazon Linux 2023", "Ubuntu 22.04 LTS"], index=0)

        # Logic to determine instance type
        target_instance_type = 't2.micro' # Default fallback
        
        # Simple mapping logic
        if fam_type == "通用型 (T/M)":
            if cpu_cores == 1 and mem_size == 1: target_instance_type = 't2.micro'
            elif cpu_cores == 2 and mem_size == 4: target_instance_type = 't3.medium'
            elif cpu_cores == 2 and mem_size == 8: target_instance_type = 'm5.large'
            elif cpu_cores == 4 and mem_size == 16: target_instance_type = 'm5.xlarge'
            elif cpu_cores == 8 and mem_size == 32: target_instance_type = 'm5.2xlarge'
            else: target_instance_type = 'm5.large' # Fallback
            
        elif fam_type == "计算型 (C)":
            if cpu_cores == 2 and mem_size == 4: target_instance_type = 'c5.large'
            elif cpu_cores == 4 and mem_size == 8: target_instance_type = 'c5.xlarge'
            elif cpu_cores == 8 and mem_size == 16: target_instance_type = 'c5.2xlarge'
            else: target_instance_type = 'c5.large'
            
        elif fam_type == "内存型 (R)":
            if cpu_cores == 2 and mem_size == 16: target_instance_type = 'r5.large'
            elif cpu_cores == 4 and mem_size == 32: target_instance_type = 'r5.xlarge'
            else: target_instance_type = 'r5.large'

        st.caption(f"匹配到的实例类型: **{target_instance_type}**")
        
        image_type_code = 'al2023' if "Amazon" in os_type else 'ubuntu'
        
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
                    
                    from concurrent.futures import ThreadPoolExecutor, as_completed

                    def launch_worker(cred):
                        # Quota Check
                        try:
                            proxy_url = cred.get('proxy_url')
                            cap = check_capacity(cred['access_key_id'], cred['secret_access_key'], region, proxy_url=proxy_url)
                            if cap['available'] < 1:
                                return f"⚠️ {cred['alias_name']}: 跳过 - 配额不足 (已用 {cap['used']}/{cap['limit']})"
                        except Exception as e:
                            pass # Try launch anyway as per original logic

                        try:
                            proxy_url = cred.get('proxy_url')
                            result = launch_base_instance(
                                cred['access_key_id'],
                                cred['secret_access_key'],
                                region,
                                instance_type=target_instance_type,
                                image_type=image_type_code,
                                proxy_url=proxy_url
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
                                return f"✅ {cred['alias_name']}: 成功 ({result['id']})"
                            else:
                                return f"❌ {cred['alias_name']}: 失败 - {result['msg']}"
                        except Exception as e:
                            return f"❌ {cred['alias_name']}: 异常 - {str(e)}"

                    with ThreadPoolExecutor(max_workers=10) as executor:
                        future_to_cred = {executor.submit(launch_worker, cred): cred for cred in target_creds}
                        
                        completed_count = 0
                        total_count = len(target_creds)
                        
                        for future in as_completed(future_to_cred):
                            cred = future_to_cred[future]
                            try:
                                res = future.result()
                                results.append(res)
                            except Exception as exc:
                                results.append(f"❌ {cred['alias_name']}: 线程异常 - {str(exc)}")
                            
                            completed_count += 1
                            progress_bar.progress(completed_count / total_count)
                            status_area.text(f"处理进度: {completed_count}/{total_count}")
                    
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
            # Clear cache to force reload
            if "display_data" in st.session_state:
                del st.session_state["display_data"]
            
            with st.spinner("正在进行全量深度检查 (并发优化版)..."):
                # 1. Fetch current instances from DB
                current_instances = get_user_instances(user.id)
                
                # 2. Filter valid ones (Running only)
                targets = [i for i in current_instances if i['status'] == 'running']
                
                if not targets:
                    st.info("没有运行中的实例需检查")
                    time.sleep(1)
                    st.rerun()
                else:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Function to process single instance
                    def process_instance(inst):
                        try:
                            # Use local decryption to save DB call
                            pkey_str = None
                            if inst.get('private_key'):
                                try:
                                    pkey_str = decrypt_key(inst['private_key'])
                                except:
                                    return (inst['ip_address'], "Key Decrypt Fail")
                            
                            if pkey_str:
                                # 1. Auto-detect project
                                detected_projs, det_msg = detect_installed_project(inst['ip_address'], pkey_str)
                                
                                if detected_projs:
                                    update_instance_projects_status(inst['instance_id'], detected_projs)
                                
                                # 2. Check health
                                check_str = ", ".join(detected_projs) if detected_projs else (inst.get('project_name') or "")
                                is_healthy, msg = check_instance_process(inst['ip_address'], pkey_str, check_str)
                                new_health = "Healthy" if is_healthy else f"Error: {msg}"
                                update_instance_health(inst['instance_id'], new_health)
                                return (inst['ip_address'], "Done")
                            else:
                                update_instance_health(inst['instance_id'], "Error: Missing Private Key")
                                return (inst['ip_address'], "No Key")
                        except Exception as e:
                            return (inst['ip_address'], f"Ex: {str(e)}")

                    # Use ThreadPoolExecutor for parallel execution
                    total = len(targets)
                    completed = 0
                    
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        future_to_ip = {executor.submit(process_instance, inst): inst['ip_address'] for inst in targets}
                        
                        for future in as_completed(future_to_ip):
                            ip = future_to_ip[future]
                            try:
                                res_ip, res_msg = future.result()
                                status_text.text(f"Checked {res_ip}: {res_msg}")
                            except Exception as exc:
                                status_text.text(f"Error checking {ip}: {exc}")
                            
                            completed += 1
                            progress_bar.progress(completed / total)
                    
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
                            
                            proxy_url = cred.get('proxy_url')
                            aws_instances = scan_all_instances(
                                cred['access_key_id'], 
                                cred['secret_access_key'], 
                                region_code,
                                proxy_url=proxy_url
                            )
                            
                            if aws_instances:
                                res = sync_instances(user.id, cred['id'], region_code, aws_instances)
                                total_new += res['new']
                                total_updated += res['updated']
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    st.success(f"扫描完成！新增 {total_new}，更新 {total_updated}。")
                    # Clear cache to reflect new data
                    if "display_data" in st.session_state:
                        del st.session_state["display_data"]
                    time.sleep(2)
                    st.rerun()

    # Load data (Cached or Fresh)
    if "display_data" not in st.session_state:
        with st.spinner("正在同步数据..."):
            db_instances = get_user_instances(user.id)
            
            if not db_instances:
                st.info("暂无实例。")
                display_data = []
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
                        proxy_url = cred.get('proxy_url')
                        status_dict = get_instance_status(cred['access_key_id'], cred['secret_access_key'], r, i_ids, proxy_url=proxy_url)
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

                    # Construct Project string dynamically from booleans
                    active_projects = []
                    if inst.get('proj_titan'): active_projects.append("Titan")
                    if inst.get('proj_nexus'): active_projects.append("Nexus")
                    if inst.get('proj_shardeum'): active_projects.append("Shardeum")
                    if inst.get('proj_babylon'): active_projects.append("Babylon")
                    if inst.get('proj_meson'): active_projects.append("Meson")
                    if inst.get('proj_proxy'): active_projects.append("Proxy")
                    
                    # Fallback to legacy or pending if no booleans set
                    project_display = ", ".join(active_projects) if active_projects else (inst.get('project_name') or "Pending")

                    display_data.append({
                        "Account": alias,
                        "Project": project_display,
                        "Instance ID": i_id,
                        "IP Address": inst['ip_address'],
                        "Region": inst['region'],
                        "Status": current_status,
                        "Health": health,
                        "Type": inst.get('instance_type', 'N/A') if 'instance_type' in inst else 'N/A', # Fallback
                        "Created": inst['created_at'][:16].replace('T', ' '),
                        "_cred_id": inst['credential_id'],
                        "_has_key": bool(inst.get('private_key'))
                    })
            
            st.session_state["display_data"] = display_data
    
    # Use cached data
    display_data = st.session_state["display_data"]
    
    if display_data:
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
                            f"选择目标实例 (匹配: {len(filtered_instances)})",
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
                                                # Map target_proj to keys
                                                db_key = ""
                                                if "Titan" in target_proj: db_key = "Titan"
                                                elif "Nexus" in target_proj: db_key = "Nexus"
                                                elif "Shardeum" in target_proj: db_key = "Shardeum"
                                                elif "Babylon" in target_proj: db_key = "Babylon"
                                                elif "Meson" in target_proj: db_key = "Meson"
                                                elif "Gaga" in target_proj: db_key = "Meson"
                                                
                                                if db_key:
                                                    update_instance_projects_status(selected_ssh_instance, [db_key])
                                                
                                                st.success(f"安装指令已发送！")
                                                # Clear cache
                                                if "display_data" in st.session_state:
                                                    del st.session_state["display_data"]
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(f"安装失败: {res['msg']}")
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
                batch_nexus_wallets = [] # For Nexus special batch handling
                
                for p in proj_conf['params']:
                    if target_proj == "Nexus_Prover" and p == "wallet_address":
                         # Special handling for Nexus batch wallets
                         raw_wallets = st.text_area(f"批量输入 {p} (每行一个)", key=f"batch_inst_{p}", height=150, help="每行一个钱包地址，将自动分配给选中的实例").strip()
                         if raw_wallets:
                             batch_nexus_wallets = [line.strip() for line in raw_wallets.split('\n') if line.strip()]
                         input_params[p] = "BATCH_PLACEHOLDER" # Placeholder
                    else:
                        input_params[p] = st.text_input(f"{p}", key=f"batch_inst_{p}").strip()

            # Instance Selection
            st.write("选择目标实例:")
            
            # Filter logic: Deduplicate (Hide installed) & Requirements
            filtered_ready_instances = []
            
            for d in ssh_ready_instances:
                # 1. Smart Deduplication: Prevent re-installing the SAME project
                # Check if target_proj is already in the comma-separated project list
                current_projects = [p.strip() for p in d['Project'].split(',')]
                if target_proj in current_projects:
                    continue
                
                # 1b. Special Case: Treat "Titan Network" and "Titan_Network" as same if needed
                # (Not strictly needed if names match registry keys exactly)
                    
                # 2. Requirements Check
                i_type = d.get('Type', 'N/A')
                # If N/A (old data), we might let it pass or warn. Let's let it pass but maybe warn in label.
                
                filtered_ready_instances.append(d)
            
            if not filtered_ready_instances:
                st.warning("没有符合条件的空闲实例 (可能硬件规格不满足要求)")
            
            instance_options = {f"{d['Instance ID']} ({d['IP Address']}) - {d['Type']} - {d['Account']} - [{d['Project']}]": d['Instance ID'] for d in filtered_ready_instances}
            selected_inst_labels = st.multiselect(
                "勾选实例",
                options=list(instance_options.keys()),
                default=[]
            )
            
            if st.button("🚀 开始批量安装", type="primary"):
                if not selected_inst_labels:
                    st.error("请选择至少一个实例")
                else:
                    target_ids = [instance_options[l] for l in selected_inst_labels]
                    
                    # Validate Nexus Batch Count
                    if target_proj == "Nexus_Prover" and "wallet_address" in proj_conf['params']:
                        if len(batch_nexus_wallets) != len(target_ids):
                            st.error(f"钱包地址数量 ({len(batch_nexus_wallets)}) 与 选中实例数量 ({len(target_ids)}) 不匹配！")
                            st.stop()
                    
                    # Validate Params (Standard)
                    missing_params = [p for p in proj_conf['params'] if not input_params.get(p)]
                    if missing_params:
                        st.error(f"请填写必要参数: {', '.join(missing_params)}")
                    else:
                        allowed, msg = check_balance(user.id)
                        if not allowed:
                            st.error(msg)
                        else:
                            # Generate script loop
                            progress_bar = st.progress(0)
                            status_area = st.empty()
                            results = []
                            
                            from concurrent.futures import ThreadPoolExecutor, as_completed

                            def install_worker(i_id, target_data, current_params):
                                try:
                                    script = generate_script(target_proj, **current_params)
                                    pkey = get_instance_private_key(i_id)
                                    
                                    if pkey:
                                        res = install_project_via_ssh(target_data['IP Address'], pkey, script)
                                        if res['status'] == 'success':
                                            # Map target_proj to keys
                                            db_key = ""
                                            if "Titan" in target_proj: db_key = "Titan"
                                            elif "Nexus" in target_proj: db_key = "Nexus"
                                            elif "Shardeum" in target_proj: db_key = "Shardeum"
                                            elif "Babylon" in target_proj: db_key = "Babylon"
                                            elif "Meson" in target_proj: db_key = "Meson"
                                            elif "Gaga" in target_proj: db_key = "Meson"
                                            
                                            if db_key:
                                                update_instance_projects_status(i_id, [db_key])
                                                
                                            return f"✅ {target_data['IP Address']}: 指令已发送"
                                        else:
                                            return f"❌ {target_data['IP Address']}: {res['msg']}"
                                    else:
                                        return f"❌ {target_data['IP Address']}: 无法获取私钥"
                                except Exception as e:
                                    return f"❌ {target_data['IP Address']}: 异常 - {str(e)}"

                            with ThreadPoolExecutor(max_workers=20) as executor:
                                futures = []
                                for i, i_id in enumerate(target_ids):
                                    target_data = next(d for d in display_data if d['Instance ID'] == i_id)
                                    
                                    # Prepare Params
                                    current_params = input_params.copy()
                                    if target_proj == "Nexus_Prover" and batch_nexus_wallets:
                                        current_params['wallet_address'] = batch_nexus_wallets[i]
                                    
                                    futures.append(executor.submit(install_worker, i_id, target_data, current_params))
                                
                                completed_count = 0
                                total_count = len(target_ids)

                                for future in as_completed(futures):
                                    try:
                                        res_msg = future.result()
                                        results.append(res_msg)
                                    except Exception as exc:
                                        results.append(f"❌ (Unknown): 线程异常 - {exc}")
                                    
                                    completed_count += 1
                                    progress_bar.progress(completed_count / total_count)
                                    status_area.text(f"安装进度: {completed_count}/{total_count}")
                            
                            status_area.empty()
                            # Clear cache
                            if "display_data" in st.session_state:
                                del st.session_state["display_data"]
                            st.success("批量安装指令发送完成！")
                            with st.expander("查看详细结果", expanded=True):
                                for r in results:
                                    st.write(r)

        # Terminate (No balance check needed for cleanup?)
        st.divider()
        st.subheader("⚠️ 危险操作")
        
        active_instances = [d for d in display_data if d['Status'] not in ['terminated', 'shutting-down', 'account-suspended']]
        
        # Search for Terminate Instance
        term_search_term = st.text_input("🔍 搜索要关闭的实例 (ID/IP/项目/账号) - 输入后按回车筛选", key="term_inst_search").strip().lower()
        
        filtered_term_instances = []
        for d in active_instances:
            search_str = f"{d['Instance ID']} {d['IP Address']} {d['Project']} {d['Account']}".lower()
            if not term_search_term or term_search_term in search_str:
                filtered_term_instances.append(d)
        
        if not filtered_term_instances and term_search_term:
             st.caption("无匹配实例")
             instance_to_term = None
        else:
            instance_to_term = st.selectbox(
                f"选择要关闭的实例 (匹配: {len(filtered_term_instances)})", 
                [d['Instance ID'] for d in filtered_term_instances], 
                key="term_select",
                format_func=lambda x: f"{x} - {next((d['Project'] for d in filtered_term_instances if d['Instance ID'] == x), '')} ({next((d['IP Address'] for d in filtered_term_instances if d['Instance ID'] == x), '')})"
            ) if filtered_term_instances else None
        
        if instance_to_term and st.button("🛑 关闭实例", type="primary"):
            target = next((d for d in display_data if d['Instance ID'] == instance_to_term), None)
            if target:
                cred = cred_lookup.get(target['_cred_id'])
                if cred:
                        proxy_url = cred.get('proxy_url')
                        terminate_instance(cred['access_key_id'], cred['secret_access_key'], target['Region'], instance_to_term, proxy_url=proxy_url)
                        update_instance_status(instance_to_term, "shutting-down")
                        # Clear cache
                        if "display_data" in st.session_state:
                            del st.session_state["display_data"]
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

# ====================
# TAB 5: Toolbox
# ====================
with tab_tools:
    st.header("🛠️ 实用工具箱")
    
    st.subheader("批量生成钱包 (EVM)")
    st.markdown("批量生成以太坊兼容 (EVM) 钱包地址，可用于 Shardeum 等项目。")
    
    with st.form("wallet_gen_form"):
        gen_count = st.number_input("生成数量", min_value=1, max_value=1000, value=10, step=1)
        submitted = st.form_submit_button("开始生成")
        
    if submitted:
        try:
            from eth_account import Account
            # Enable features just in case, though create() is standard
            Account.enable_unaudited_hdwallet_features()
            
            wallets = []
            progress_bar = st.progress(0)
            
            for i in range(gen_count):
                acct = Account.create()
                wallets.append({
                    "Address": acct.address,
                    "Private Key": acct.key.hex()
                })
                progress_bar.progress((i + 1) / gen_count)
                
            df_wallets = pd.DataFrame(wallets)
            
            st.success(f"成功生成 {gen_count} 个钱包！")
            
            # Show preview
            st.dataframe(df_wallets.head(10))
            if gen_count > 10:
                st.caption(f"仅显示前 10 个，共 {gen_count} 个。请下载完整文件。")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # CSV for Download (Full)
                csv_full = df_wallets.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 下载完整列表 (含私钥)",
                    data=csv_full,
                    file_name=f'generated_wallets_{int(time.time())}.csv',
                    mime='text/csv',
                )
            
            with col2:
                # CSV for Faucet Script (Address Only, No Header)
                csv_simple = df_wallets['Address'].to_csv(index=False, header=False).encode('utf-8')
                st.download_button(
                    label="📥 下载地址列表 (适配领水脚本)",
                    data=csv_simple,
                    file_name='wallets.csv',
                    mime='text/csv',
                    help="仅包含地址列，无表头，可直接用于 discord_faucet.py"
                )
                
        except ImportError:
            st.error("缺少依赖库 `eth-account`。请联系管理员安装。")
        except Exception as e:
            st.error(f"生成失败: {str(e)}")

    st.divider()

