# AWS DePIN Launcher

**AWS DePIN Launcher** 是一个模块化、可扩展的 Web 应用程序，旨在帮助用户快速在 AWS EC2 上部署各种 DePIN (Decentralized Physical Infrastructure Network) 节点项目。

目前支持一键部署 **Titan Network** 和 **Meson (GagaNode)**，并支持通过配置文件轻松扩展更多项目。

## 🚀 功能特性

*   **模块化架构**: 项目脚本逻辑与主程序分离，易于扩展。
*   **多项目支持**:
    *   **Titan Network**: 基于 Docker 容器化部署。
    *   **Meson (GagaNode)**: 基于二进制文件部署。
    *   **Shardeum + Titan (Combo)**: 适合 16GB+ 内存机型，同时运行 Shardeum 验证节点与 Titan（流量掩护）。
    *   **Babylon + Traffmonetizer (Combo)**: 适合存储型节点，同时运行 Babylon 验证节点与 Traffmonetizer（流量掩护）。
*   **自动化运维**:
    *   自动匹配 Amazon Linux 2023 AMI。
    *   自动配置安全组（自动开放 8080, 9001, 10001, 26656 等必要端口）。
    *   自动生成 UserData 启动脚本。
    *   自动分配公网 IP 并打上项目标签 (`Project`, `Name`)。
*   **动态 UI**: 基于 Streamlit，根据所选项目自动渲染所需的参数输入框。
*   **多账号实例管理**:
    *   **自动记录**: 部署成功后，实例信息自动存入 Supabase 数据库，并与 Access Key 绑定。
    *   **实时监控**: 在“管理实例”页面，输入 AK/SK 即可查询该账号下的所有实例，并实时同步 AWS 运行状态。
    *   **一键关闭**: 支持直接在界面上关闭（Terminate）指定实例。
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

### 3. 配置数据库 (Supabase)

为了启用实例管理功能，你需要一个 Supabase 项目：

1.  登录 [Supabase](https://supabase.com/) 创建新项目。
2.  进入 SQL Editor，运行项目根目录下的 `schema.sql` 脚本，创建数据库表。
3.  获取 `Project URL` 和 `anon public key`。

### 4. 配置环境变量

**本地运行:**
Windows PowerShell:
```powershell
$env:SUPABASE_URL="your_supabase_url"
$env:SUPABASE_KEY="your_supabase_anon_key"
```

Linux/Mac:
```bash
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_anon_key"
```

**Streamlit Community Cloud 部署:**
1.  在 Streamlit Cloud 控制台，进入 App Settings -> Secrets。
2.  添加以下内容：
    ```toml
    SUPABASE_URL = "your_supabase_url"
    SUPABASE_KEY = "your_supabase_anon_key"
    ```

### 5. 启动应用
```bash
streamlit run app.py
```
启动后，浏览器将自动打开 `http://localhost:8501`。

## 📖 使用指南

### 部署节点 (Deploy Tab)
1.  **侧边栏配置**: 选择 AWS Region 和 Project。
    *   *推荐尝试新的 Combo 组合拳模板以最大化收益。*
2.  **启动基础实例**: 点击“批量启动实例”，系统将自动配置安全组并启动纯净的 Amazon Linux 环境。
3.  **批量安装项目**: 切换到 **“实例监控”** 页面，在底部选择 **“批量项目安装”**，选择刚刚启动的实例，一键下发安装指令。
    *   **Shardeum**: 安装后访问 `https://<IP>:8080` (密码为部署时设置的密码) 进行质押。
    *   **Babylon**: 安装后会自动作为 Systemd 服务运行。
4.  **输入凭证**: 在“凭证管理”页面批量导入或添加 AWS AK/SK。

### 管理实例 (Manage Tab)
1.  切换到 **⚙️ 管理实例** 选项卡。
2.  输入 AWS AK/SK（用于验证身份和查询 AWS API）。
3.  点击 **🔍 查询我的实例**。
4.  列表将显示该账号历史部署的所有实例及其当前的实时状态（Running/Terminated）。
5.  如需关闭机器，在下方选择实例 ID 并点击 **🛑 关闭实例**。

## 📂 项目结构

*   `app.py`: Streamlit 主程序，负责 UI 渲染和流程编排。
*   `templates.py`: **核心配置**。定义了支持的项目列表、所需参数以及 Shell 启动脚本模板。
*   `logic.py`: AWS 交互逻辑。负责调用 boto3 启动实例、查询状态、关闭实例。
*   `db.py`: 数据库交互逻辑。负责连接 Supabase 并记录数据。
*   `schema.sql`: 数据库建表脚本。
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
