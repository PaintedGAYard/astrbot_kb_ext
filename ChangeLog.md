# AstrBot KB External Access — ChangeLog

## v0.2.2 (2026-06-10)

### 变更

- 新增插件页面（Pages）实现知识库选择器，保存纯 kb_id
- 新增三个 Web API 端点支持插件页面
- 移除 `_special: select_knowledgebase` 依赖
- 清理调试代码和文档字符串

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
