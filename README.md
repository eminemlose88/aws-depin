# AWS DePIN Launcher

**AWS DePIN Launcher** 是一个模块化、可扩展的 Web 应用程序，旨在帮助用户快速在 AWS EC2 上部署各种 DePIN (Decentralized Physical Infrastructure Network) 节点项目。

目前支持一键部署 **Titan Network** 和 **Meson (GagaNode)**，并支持通过配置文件轻松扩展更多项目。

## 🚀 功能特性

*   **模块化架构**: 项目脚本逻辑与主程序分离，易于扩展。
*   **多项目支持**:
    *   **Titan Network**: 基于 Docker 容器化部署。
    *   **Meson (GagaNode)**: 基于二进制文件部署。
*   **自动化运维**:
    *   自动匹配 Amazon Linux 2023 AMI。
    *   自动生成 UserData 启动脚本。
    *   自动分配公网 IP 并打上项目标签 (`Project`, `Name`)。
*   **动态 UI**: 基于 Streamlit，根据所选项目自动渲染所需的参数输入框。
*   **部署记录**: 集成 Supabase 数据库，自动记录部署历史（实例 ID、IP、区域等）。
*   **安全**: AWS 凭证仅在内存中使用，不保存到本地。

## 🛠️ 安装与运行

### 1. 克隆仓库
```bash
git clone https://github.com/eminemlose88/aws-depin.git
cd aws-depin
```

### 2. 安装依赖
建议使用 Python 3.9+ 环境。
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量 (可选)
如果需要将部署记录保存到 Supabase 数据库，请设置以下环境变量。如果不设置，程序将跳过数据库记录步骤，但仍可正常部署节点。

**Windows PowerShell:**
```powershell
$env:SUPABASE_URL="your_supabase_url"
$env:SUPABASE_KEY="your_supabase_anon_key"
```

**Linux/Mac:**
```bash
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_anon_key"
```

### 4. 启动应用
```bash
streamlit run app.py
```
启动后，浏览器将自动打开 `http://localhost:8501`。

## 📖 使用指南

1.  **侧边栏配置**:
    *   选择 **AWS Region** (如 `us-east-1`, `ap-northeast-1`)。
    *   选择 **Project** (如 `Titan Network`, `Meson (GagaNode)`)。
    *   点击“保存默认配置”可记住你的选择。

2.  **填写参数**:
    *   主界面会自动显示该项目所需的参数（例如 Titan 需要 `identity_code`，Meson 需要 `token`）。

3.  **输入凭证**:
    *   输入你的 AWS `Access Key ID` 和 `Secret Access Key`。

4.  **立即部署**:
    *   点击 **🚀 立即部署** 按钮。
    *   系统将自动连接 AWS，生成启动脚本，并启动 EC2 实例。
    *   部署成功后，界面会显示实例 ID 和公网 IP，节点将在后台自动安装并上线（通常需 3-5 分钟）。

## 📂 项目结构

*   `app.py`: Streamlit 主程序，负责 UI 渲染和流程编排。
*   `templates.py`: **核心配置**。定义了支持的项目列表、所需参数以及 Shell 启动脚本模板。
*   `logic.py`: AWS 交互逻辑。负责调用 boto3 启动实例、打标签等。
*   `db.py`: 数据库交互逻辑。负责连接 Supabase 并记录数据。
*   `requirements.txt`: 项目依赖列表。

## 🔗 扩展新项目

要添加新的 DePIN 项目，只需修改 `templates.py` 中的 `PROJECT_REGISTRY` 字典：

```python
PROJECT_REGISTRY = {
    "NewProject": {
        "description": "Description of the new project",
        "params": ["param1", "param2"],
        "script_template": """#!/bin/bash
echo "Installing NewProject..."
# Use {param1} and {param2} in your script
"""
    },
    # ... existing projects
}
```
无需修改前端代码，UI 会自动适配。

## 📝 License
MIT License
