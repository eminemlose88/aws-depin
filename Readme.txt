项目设计文档：AWS DePIN 批量发射器 (AWS DePIN Launcher)
1. 项目概述
这是一个基于本地运行的轻量级 Web 应用。旨在帮助用户通过图形界面输入 AWS 凭证（AK/SK），自动在指定的 AWS 区域启动 EC2 实例，并自动注入 UserData 脚本以部署 Titan Network（或其他 DePIN 项目）节点。

2. 技术栈
编程语言: Python 3.9+

前端框架: Streamlit (用于快速构建 Web UI)

AWS SDK: Boto3 (用于连接 AWS API)

配置管理: JSON (用于保存 Titan Hash 等常用配置)

3. 功能需求
3.1 核心功能
凭证输入: 用户界面提供文本框输入 Access Key ID 和 Secret Access Key。

配置管理:

支持选择 AWS 区域 (Region)，如 us-east-1, us-east-2, ap-northeast-1。

自动匹配 AMI: 根据选择的区域，自动映射对应的 Amazon Linux 2023 镜像 ID。

身份码设置: 用户只需输入一次 TITAN_HASH，支持保存到本地，下次自动加载。

一键部署: 点击“启动实例”按钮后，程序自动完成以下流程：

验证 AWS 连接。

生成包含 Docker 安装、Titan 部署、身份绑定的 Shell 脚本。

调用 AWS API 启动 t2.micro 实例。

状态反馈:

在界面显示运行日志（如：“正在连接...”、“实例已创建...”、“IP分配中...”）。

部署成功后，高亮显示实例 ID 和公网 IP。

3.2 扩展性（可选）
支持下拉菜单选择不同的 DePIN 项目（目前默认 Titan，未来可扩展 Meson/Grass）。

4. 详细设计
4.1 文件结构
Plaintext

aws-depin-launcher/
├── app.py              # 主程序入口 (Streamlit UI 代码)
├── logic.py            # 核心逻辑 (Boto3 AWS 操作函数)
├── config.json         # 用户配置文件 (保存 Hash 和默认区域)
└── requirements.txt    # 依赖库列表
4.2 区域与 AMI 映射表 (Hardcoded in Logic)
为了简化用户操作，需要在代码中内置常用区域的 Amazon Linux 2023 AMI ID（x86_64架构）：

us-east-1 (弗吉尼亚): ami-051f7e7f6c2f40dc1

us-east-2 (俄亥俄): ami-0900fe555666598a2

us-west-2 (俄勒冈): ami-04e914639d0cca79a

ap-northeast-1 (东京): ami-023ff3d4ab11b2525 (注：AI 在编写代码时应自动去搜索或预填这些最新的 AMI ID)

4.3 UI 布局设计
侧边栏 (Sidebar):

输入框: Titan Identity Hash (默认加载本地配置)

下拉框: 选择 AWS 区域

按钮: 保存默认配置

主界面 (Main):

标题: "🚀 AWS DePIN 节点发射器"

输入框 1: Access Key ID (密码模式，显示为 ***)

输入框 2: Secret Access Key (密码模式，显示为 ***)

大按钮: 开始部署 (Deploy)

日志输出区: 部署过程中的文本流显示在这里。

结果展示区: 成功后显示绿色的卡片，包含 IP 和 Instance ID。