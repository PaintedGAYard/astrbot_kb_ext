<!--
MIT License

Copyright (c) 2026 Mingxi "Lucien" Du

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

# AstrBot Knowledge Base Extended Access — ChangeLog

## v1.0.1b (2026-06-13)

### 修复

- **.doc 上传失败**：`_doc_to_markdown()` 新增 `pywin32` (Word COM) 提取方法，解决旧版二进制 .doc 文件无法提取文本的问题（#1）
- **提取后 file_type 错误**：提取成功的 Markdown 内容不再沿用原文件扩展名作为 `file_type`，改为传递 `"md"`，避免 AstrBot 内核按二进制格式重新解析导致失败

### 变更

- `UploadParams` 新增 `extracted_as_markdown` 标记，提取逻辑与上传逻辑解耦
- 临时文件 `_replace_ext` 辅助函数移除（不再需要）
- `UploadResult` 新增 `detail` 字段，修复 `_run_upload()` 传入 `detail=...` 导致批量上传崩溃的 bug

### 文档规范

- 修复 `upload_to_knowledge_base` docstring 缺失 `Args:` 段落的问题，所有 `@llm_tool` 的 `Args:` 补全 `event` 参数、统一为 Python 类型（`str`/`int`/`float`/`bool` 替代 `string`/`number`）
- 按 `design/Working Guidelines.md` 全面对齐 docstring：移除中英双语冗余、移除函数名自解释时的多余摘要、移除实现细节、补充 `Raises:` 和副作用说明
- 按新版 Language Usage Guideline 将所有源码文档和行内注释转为英文
- 更新 `.github/copilot-instructions.md` 反映最新编码规范

## v1.0.0b (2026-06-13)

### 重构

- 完整架构重构，严格遵循编码规范：
  - `UploadParams` / `UploadResult` 数据类取代 9+ 参数的方法签名
  - `_AsyncUploadTask` 类封装异步上传的 shield/wait/store 模式
  - `MarkdownExtractor` 独立模块（从 `kb_uploader.py` 提取）
  - `tool_error_handler` 装饰器统一工具层异常处理
  - `_read_sandbox_file` 方法消除沙箱读取代码重复
- 所有内部方法返回 `UploadResult` 数据类（结构化），不再返回 LLM 风格消息
- 文档注释精简为纯接口契约，移除所有实现细节和冗余注释

### 修复

- 修复批量上传工具调用 `r.get("success")` 访问 `UploadResult` 数据类的运行时崩溃

### 变更

- 以 `metadata.yaml` 为唯一版本源，`__init__.py` 动态读取
- `.xlsx` / `.xls` / `.doc` 文本化由插件自动处理，对 Agent 透明
- 构建脚本排除 `__pycache__`
- SKILL 文件去重，文件格式表仅在 index 保留

---

## v0.7.0 (2026-06-12)

### 新增

- 独立 xlsx→markdown 文本化引擎：使用 openpyxl 自行构建 Markdown 表格，
  完全绕过 AstrBot 内置的 pandas.to_html() 产生的 NaN 问题
- `KnowledgeBaseUploader._extract_markdown()` / `_xlsx_to_markdown()` —
  格式无关的文本提取框架，当前支持 xlsx，预留扩展点
- MIT License（`Copyright (c) 2026 Mingxi "Lucien" Du`），全量源码/提示文件头部

### 变更

- 全名改为 **AstrBot Knowledge Base Extended Access**（原名 KB External Access）
- 项目结构扁平化：插件文件直接从 `src/` 加载，移除嵌套的 `src/astrbot_kb_ext_access/`
- `build.ps1` 增加 `-Exclude "__pycache__"`，构建产物不再包含缓存目录
- 估算算法回退：xlsx `text_ratio` 从 2.0 恢复为 0.1（NaN 问题已通过预处理解决）
- 估算精度说明更新：反映新的 xlsx→markdown 预处理策略

### 修复

- 修复 `upload_bytes()` 缺少 `return await self._upload_with_retry()` 调用，
  sandbox_path 模式上传实际未生效的 bug

---

## v0.6.2 (2026-06-11)

### 变更

- 更新README

## v0.6.1 (2026-06-11)

### 变更

- 添加LICENSE

---

## v0.6.0 (2026-06-11)

### 变更

- 版本号集中管理：统一以 `metadata.yaml` 为唯一版本源
- `__init__.py` 改为从 `metadata.yaml` 动态读取 `__version__`，消除硬编码和过期问题
- `build.ps1` 保持从 `metadata.yaml` 读取版本号（已有逻辑）
- 清理所有 SKILL.md 中与 docstring 重复的参数表和返回格式说明
- 修改所有工具返回格式

---

## v0.5.1 (2026-06-11)

### 变更

- `astr_kb_schedule_check` 从一次性模式改为重复 cron 模式（`interval_seconds`），不再需要回调链
- 轮询间隔下限从 30s 提高至 180s（3 分钟）
- 清理所有 SKILL.md 和 docstring 中的冗余/误导性内容，移除 "120s 框架限制" 相关描述

---

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
