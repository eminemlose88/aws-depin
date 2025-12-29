我将实现“全网扫描”功能，确保本地数据库与 AWS 真实状态保持同步。

1.  **`logic.py`**:
    *   新增 `scan_all_instances(ak, sk, region)` 函数：列出指定区域内的所有实例（包括运行中和已停止的）。返回包含实例 ID、IP、状态和标签的详细列表。

2.  **`db.py`**:
    *   新增 `sync_instances(user_id, credential_id, region, aws_instances)` 函数：对比 AWS 返回的实例列表与数据库记录。
        *   **发现新机器**: 如果 AWS 有但数据库无，自动插入新记录。尝试从 AWS 标签中读取 `Project` 字段，若没有则标记为 `Manual/Unknown`。
        *   **发现已销毁**: 如果数据库显示活跃，但 AWS 上查不到或状态为 `terminated`，自动将数据库状态更新为 `terminated`。
        *   **状态更新**: 如果状态不一致（如从 `pending` 变为 `running`），更新数据库状态。

3.  **`app.py`**:
    *   在 **“⚙️ 实例监控”** 选项卡中增加 **“🌍 全网扫描 & 同步”** 按钮。
    *   点击后逻辑：
        *   遍历用户的所有 AWS 凭证。
        *   对每个凭证，遍历所有支持的区域（基于 `AMI_MAPPING`）。
        *   调用 `scan_all_instances` 获取 AWS 数据。
        *   调用 `sync_instances` 同步数据库。
        *   最后显示同步报告：“发现了 X 台新机器，更新了 Y 台机器的状态”。

这样可以确保无论用户是通过本平台还是 AWS 控制台操作，数据都能保持一致。