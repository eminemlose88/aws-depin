import streamlit as st
import json
import os
from logic import launch_instance, AMI_MAPPING
from templates import PROJECT_REGISTRY, generate_script
from db import log_instance

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
st.set_page_config(page_title="AWS DePIN Launcher", page_icon="🚀", layout="centered")

st.title("AWS DePIN Launcher (Modular)")
st.markdown("模块化部署平台：支持多种 DePIN 项目一键部署。")

# Load existing config
config = load_config()
default_region = config.get('region', 'us-east-1')
default_project = config.get('project', list(PROJECT_REGISTRY.keys())[0])

# --- Sidebar ---
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

# Create a container for the form
with st.container(border=True):
    for param in project_info['params']:
        # Try to pre-fill from config if available (optional feature)
        # For now, just empty or previously entered in session state
        val = st.text_input(f"Enter {param}", key=f"param_{project_name}_{param}")
        input_params[param] = val.strip()
        if not val.strip():
            missing_params.append(param)

st.subheader("2. AWS 凭证")
col1, col2 = st.columns(2)
with col1:
    ak = st.text_input("Access Key ID", type="password")
with col2:
    sk = st.text_input("Secret Access Key", type="password")

st.markdown("---")

# Launch Button
if st.button("🚀 立即部署", type="primary", use_container_width=True):
    # Validation
    if not ak or not sk:
        st.error("❌ 请输入 AWS Access Key 和 Secret Key")
    elif missing_params:
        st.error(f"❌ 缺少项目参数: {', '.join(missing_params)}")
    else:
        # Execution
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
                    instance_id=result['id'],
                    ip=result['ip'],
                    region=region,
                    project_name=project_name,
                    status="launched"
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
                AWS 正在初始化环境并执行 `{project_name}` 的安装脚本。
                """)
            else:
                status_container.update(label="部署失败", state="error", expanded=True)
                st.error(f"❌ 启动失败: {result['msg']}")
                
        except Exception as e:
            status_container.update(label="发生系统错误", state="error")
            st.error(f"异常详情: {str(e)}")
