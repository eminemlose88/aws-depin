我将对系统进行重大升级，引入 SSH 密钥管理和深度监控功能。

1.  **依赖库**:
    *   新增 `paramiko` 用于 SSH 连接。
    *   新增 `cryptography` 用于私钥加密存储。

2.  **`crypto.py` (新增)**:
    *   实现 `encrypt_key(key_text)` 和 `decrypt_key(encrypted_text)` 函数，使用对称加密（Fernet）保护数据库中的私钥。密钥将从环境变量或 Streamlit Secrets 中读取。

3.  **`schema.sql`**:
    *   更新 `instances` 表，增加 `private_key` (Text) 和 `health_status` (Text) 字段。

4.  **`logic.py`**:
    *   修改 `launch_instance`:
        *   为每次部署创建一个唯一的 AWS Key Pair（命名规则 `depin-key-{project}-{timestamp}`）。
        *   获取 `KeyMaterial`（私钥）。
        *   启动实例时指定该 `KeyName`。
        *   返回私钥内容供上层加密存储。

5.  **`monitor.py` (新增)**:
    *   `check_instance_health(ip, private_key_pem, project_name)`: 使用 Paramiko 连接 SSH，运行 `docker ps` 检查特定容器是否运行。
    *   `install_project_via_ssh(ip, private_key_pem, script)`: 通过 SSH 发送并执行安装脚本，用于“强制修复”或“新安装”。

6.  **`db.py`**:
    *   更新 `log_instance` 以接收和存储加密后的私钥。
    *   更新 `instances` 表查询逻辑。

7.  **`app.py`**:
    *   集成 `crypto.py` 和 `monitor.py`。
    *   更新部署流程：启动后加密私钥并存入 DB。
    *   更新“实例监控”表格：
        *   新增 **"🔍 深度检测"** 按钮：触发 SSH 检查，更新健康状态。
        *   新增 **"🔧 强制修复"** 按钮：如果检测出容器丢失，一键重装。

**安全说明**: 私钥将加密存储在数据库中，只有应用运行时持有解密密钥（Master Key）才能读取，确保安全性。