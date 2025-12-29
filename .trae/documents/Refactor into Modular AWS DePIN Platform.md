我将按照要求将应用重构为模块化、可扩展的平台：

1.  **`requirements.txt`**: 添加 `supabase` and `cryptography`。
2.  **`templates.py`**: 创建此文件以管理项目脚本。
    *   实现 `PROJECT_REGISTRY`，包含 "Titan Network"（从 logic.py 迁移）和 "Meson (GagaNode)" 模板。
    *   实现 `generate_script(project_name, **kwargs)` 用于渲染 UserData 脚本。
3.  **`db.py`**: 创建此文件用于 Supabase 集成。
    *   实现 `log_instance` 函数以记录部署详情。
    *   使用环境变量获取凭证（如果缺失则优雅降级）。
4.  **`logic.py`**: 重构 AWS 逻辑。
    *   移除 `generate_user_data`（逻辑已移至 templates）。
    *   更新 `launch_instance` 以接收已渲染的 `user_data` 和 `project_name`。
    *   添加 `TagSpecifications` 将实例 Name 标签设为 `{project_name}-Worker`。
5.  **`app.py`**: 更新 UI 以支持模块化。
    *   侧边栏：选择项目（Project）和区域（Region）。
    *   主界面：根据所选项目的 `params` 动态渲染输入表单。
    *   发射流程：编排 `generate_script` -> `launch_instance` -> `log_instance`。

这实现了脚本逻辑（templates）、业务逻辑（app）和基础设施逻辑（logic/db）的完全分离。