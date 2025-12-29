我将创建以下 3 个文件来构建 "AWS DePIN Launcher" 应用：

1. **`requirements.txt`**:

   * 添加 `streamlit` 和 `boto3` 依赖。

2. **`logic.py`**:

   * 定义 `AMI_MAPPING`，包含 `us-east-1`, `us-east-2`, `us-west-2`, `ap-northeast-1` 的 Amazon Linux 2023 AMI ID。

   * 实现 `generate_user_data(titan_hash)`，生成 Base64 编码的启动脚本（安装 Docker 并运行 Titan Edge）。

   * 实现 `launch_instance(ak, sk, region, titan_hash)`：

     * 使用 `boto3` 连接 AWS。

     * 根据区域选择 AMI 启动 `t2.micro` 实例。

     * 自动分配公网 IP，无密钥启动。

     * 处理异常并返回状态字典。

3. **`app.py`**:

   * 构建 Streamlit 界面。

   * **侧边栏**：输入 Titan Hash 和 Region，支持保存/读取 `config.json`。

   * **主界面**：输入 AWS Access Key 和 Secret Key（密码模式），以及“🚀 立即发射”按钮。

   * **交互**：点击按钮后调用 `logic.py`，并显示进度和结果（成功/失败）。

