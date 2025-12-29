import streamlit as st
import json
import os
import pandas as pd
from logic import launch_instance, AMI_MAPPING, get_instance_status, terminate_instance
from templates import PROJECT_REGISTRY, generate_script
from db import log_instance, get_user_instances, update_instance_status

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

# Set page configuration
st.set_page_config(page_title="AWS DePIN Launcher", page_icon="🚀", layout="wide")

st.title("AWS DePIN Launcher (Modular)")
st.markdown("模块化部署平台：支持多种 DePIN 项目一键部署与管理。")

# Tabs for different functionalities
tab_deploy, tab_manage = st.tabs(["🚀 部署新节点", "⚙️ 管理实例"])

# Load existing config
config = load_config()
default_region = config.get('region', 'us-east-1')
default_project = config.get('project', list(PROJECT_REGISTRY.keys())[0])

# ====================
# TAB 1: Deploy
# ====================
with tab_deploy:
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

    # Display Project Description
    project_info = PROJECT_REGISTRY[project_name]
    st.sidebar.info(f"**{project_name}**\n\n{project_info['description']}")

    if st.sidebar.button("保存默认配置"):
        save_config({'region': region, 'project': project_name})

    # --- Main Interface ---
    st.subheader("1. 配置项目参数")
    st.markdown(f"填写 **{project_name}** 所需的参数：")

    # Dynamic Form Generation
    input_params = {}
    missing_params = []

    with st.container(border=True):
        for param in project_info['params']:
            val = st.text_input(f"Enter {param}", key=f"param_{project_name}_{param}")
            input_params[param] = val.strip()
            if not val.strip():
                missing_params.append(param)

    st.subheader("2. AWS 凭证")
    col1, col2 = st.columns(2)
    with col1:
        ak = st.text_input("Access Key ID", type="password", key="deploy_ak")
    with col2:
        sk = st.text_input("Secret Access Key", type="password", key="deploy_sk")

    st.markdown("---")

    # Launch Button
    if st.button("🚀 立即部署", type="primary", use_container_width=True):
        if not ak or not sk:
            st.error("❌ 请输入 AWS Access Key 和 Secret Key")
        elif missing_params:
            st.error(f"❌ 缺少项目参数: {', '.join(missing_params)}")
        else:
            status_container = st.status("正在初始化部署流程...", expanded=True)
            try:
                # 1. Generate Script
                status_container.write("🔨 正在生成 User Data 脚本...")
                user_data = generate_script(project_name, **input_params)
                
                # 2. Launch Instance
                status_container.write(f"☁️ 正在连接 AWS {region} 并启动实例...")
                result = launch_instance(ak, sk, region, user_data, project_name)
                
                if result['status'] == 'success':
                    # 3. Log to DB
                    status_container.write("💾 正在记录部署信息到数据库...")
                    log_instance(
                        access_key_id=ak,
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
                    - **Project:** `{project_name}`
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
# TAB 2: Manage Instances
# ====================
with tab_manage:
    st.header("实例管理")
    st.markdown("查看并管理此 Access Key 下的所有实例。")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        manage_ak = st.text_input("Access Key ID", type="password", key="manage_ak")
    with col_m2:
        manage_sk = st.text_input("Secret Access Key", type="password", key="manage_sk")
        
    if st.button("🔍 查询我的实例", key="btn_query"):
        if not manage_ak or not manage_sk:
            st.error("请输入 AWS 凭证以查询实例。")
        else:
            with st.spinner("正在从数据库和 AWS 获取数据..."):
                # 1. Get from DB
                db_instances = get_user_instances(manage_ak)
                
                if not db_instances:
                    st.warning("未找到该账号的部署记录。")
                else:
                    # 2. Group by region to batch AWS calls
                    region_map = {}
                    for inst in db_instances:
                        r = inst['region']
                        if r not in region_map:
                            region_map[r] = []
                        region_map[r].append(inst['instance_id'])
                    
                    # 3. Check Real-time Status
                    real_time_status = {}
                    for r, ids in region_map.items():
                        status_dict = get_instance_status(manage_ak, manage_sk, r, ids)
                        real_time_status.update(status_dict)
                    
                    # 4. Prepare Display Data
                    display_data = []
                    for inst in db_instances:
                        i_id = inst['instance_id']
                        current_status = real_time_status.get(i_id, "unknown/terminated")
                        
                        # Update DB if status changed (optional optimization)
                        if current_status != inst['status']:
                            update_instance_status(i_id, current_status)
                        
                        display_data.append({
                            "Project": inst['project_name'],
                            "Instance ID": i_id,
                            "IP Address": inst['ip_address'],
                            "Region": inst['region'],
                            "AWS Status": current_status,
                            "Deployed At": inst['created_at']
                        })
                    
                    # 5. Render Table
                    df = pd.DataFrame(display_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # 6. Action: Terminate
                    st.subheader("⚠️ 危险操作")
                    term_col1, term_col2 = st.columns([3, 1])
                    with term_col1:
                        instance_to_term = st.selectbox("选择要关闭的实例 ID", [d['Instance ID'] for d in display_data])
                    with term_col2:
                        if st.button("🛑 关闭实例", type="primary"):
                            # Find region for selected instance
                            target_region = next((d['Region'] for d in display_data if d['Instance ID'] == instance_to_term), None)
                            if target_region:
                                with st.spinner(f"正在关闭 {instance_to_term}..."):
                                    res = terminate_instance(manage_ak, manage_sk, target_region, instance_to_term)
                                    if res['status'] == 'success':
                                        st.success(f"已发送关闭指令: {instance_to_term}")
                                        update_instance_status(instance_to_term, "shutting-down")
                                    else:
                                        st.error(f"关闭失败: {res['msg']}")
                            else:
                                st.error("无法定位实例区域。")
