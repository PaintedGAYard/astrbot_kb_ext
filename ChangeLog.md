# AstrBot KB External Access — ChangeLog

## v0.5.0 (2026-06-10)

### 新增

- `astr_kb_upload` 新增 `wait_completion` 参数，支持异步后台上传
- `astr_kb_upload` 新增 `timeout`（默认 100s）和 `max_retries`（默认 3）参数
- `astr_kb_upload_batch` — 批量上传工具，逐个同步阻断
- `astr_kb_check_upload` — 查询异步上传向量化完成状态
- `astr_kb_estimate_upload_time` — 根据文件大小和类型预估向量化耗时，含推荐轮询间隔
- `astr_kb_schedule_check` — 使用服务器系统时钟安排 FutureTask，避免 agent 时间偏差
- `avg_embedding_time` 插件配置项（默认 1.5s/切片）
- 异步上传并发锁，同一时间只允许一个 wait_completion=false（#32）

### 变更

- SKILL.md 拆分为 9 个独立 skill 文件，每个工具/策略一个，英文 Anthropic 风格
- 所有文档注释重写，消除误导性 "120s 框架限制" 描述，改为策略切换指引
- `kb_uploader.py` 重构，支持共享 pending_store 和完成回调
- `build.ps1` 自动从 metadata.yaml 读取版本号
- 并发拒绝消息增加 future_task 链式回调指引
- access_control.py 注释更新，移除过时的 select_knowledgebase 引用
- 配置文件 schema 增加 `avg_embedding_time` 顶层字段

### 修复

- 修复 check_upload_status 跨工具调用查不到结果的问题（改用共享 pending_store）
- 修复异步上传完成回调释放并发锁的竞争条件
- 修复 XLSX/DOCX 估算偏小导致同步超时的问题（文档增加准确性警告）

---

## v0.4.1 (2026-06-10)

### 新增

- `astr_kb_upload` 新增 `timeout`（默认 180s，0=无限）和 `max_retries`（默认 3）参数
- `astr_kb_upload_batch` — 批量上传工具，接受文件列表逐个上传，失败跳过继续（#31）

### 变更

- 更新 SKILL.md 以记录 timeout/retry/batch 能力

---

## v0.4.0 (2026-06-10)

### 新增

- `astr_kb_search_ext` — 受插件白名单控制的搜索工具（#23）
- `astr_kb_create` 新增 `embedding_provider` / `rerank_provider` 参数，支持模糊匹配（#26）
- `astr_kb_upload` 新增 `binary` 参数，支持 base64 编码的二进制文件上传（#29）
- `astr_kb_upload` 新增 `sandbox_path` 参数，通过沙箱 Python 执行直接读取二进制文件（#30）

### 修复

- 修复上传进度回调非异步导致的 TypeError（#22）
- 修复配置文件 BOM 读取错误（#19）
- 修复 `_api_save_config` 缺少 return 导致的 500 错误（#25）
- 修复创建知识库后自动白名单未持久化的问题（#27）

### 变更

- 重写 SKILL.md 为面向 Agent 的格式（#24）
- 移除 session config 补丁，不再尝试兼容内置搜索（#28）
- 上传文件格式列表改为穷举式，明确标记不支持 doc/ppt 等格式

---


### 新增

- `astr_kb_delete` — Agent 可删除知识库，删除后自动清理白名单孤儿条目
- `astr_kb_delete_document` — Agent 可删除知识库中的指定文档
- 删除操作前自动请求用户确认（除非传入 confirm=true）
- 配置持久化辅助方法 `_persist_config()`

## v0.2.1 (2026-06-10)

### 变更

- 白名单和黑名单配置项改用知识库选择器下拉框（`_special: select_knowledgebase`）
- 完善国际化支持（中英双语 metadata、config、docstring、SKILL.md）
- 构建产物包含 README.md

## v0.2.0 (2026-06-10)

### 变更

- 修复 `llm_tool` 导入路径（`astrbot.api.star` → `astrbot.api`）
- 修复 SKILL.md frontmatter `name` 格式
- 移除运行时 SKILL.md 同步逻辑，改用插件静态 `skills/` 目录
- 移除所有对 `astrbot.core.*` 内部模块的顶层导入
- 清理文档字符串与注释

## v0.1.0 (2026-06-10)

### 初始版本

- 实现三个 `@llm_tool`：`astr_kb_list`、`astr_kb_upload`、`astr_kb_create`
- 实现白名单/黑名单访问控制
- 实现上传进度收集与一次性结果返回
- 提供 `_conf_schema.json` 配置 Schema
- 随插件提供 SKILL.md
