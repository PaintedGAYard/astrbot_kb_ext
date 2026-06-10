# AstrBot KB External Access — ChangeLog

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
