# 项目说明

本文件是仓库级项目说明，供后续开发、排查和生成知识库文件前快速查询。每次进入本项目工作时，应先阅读本文件，再结合当前任务读取相关代码、测试和生成结果。

当前仓库根目录为 `/Users/simon/code/kb_ingest`。历史对话中如出现旧路径 `/Users/simon/PyCharmMiscProject/kb_ingest`，除非用户特别说明，否则应按当前根目录处理。

## 项目定位

本项目是离线知识库文件生成工具，用于把 PDF、Word、Markdown、TXT 等原始业务材料转换为符合知识库规范的 Markdown 条目。工具本身不参与线上应用运行，只负责解析、切分、整理、写入和校验知识库源文件。

## 技术栈

- 运行时：Python 3.10+。
- CLI：`ingest.py`，也可通过 npm bin `union_kb_ingest` 调用。
- 配置：`config/config.yaml`，支持 `KB_*` 环境变量覆盖。
- 文档解析：`docling-parse` 用于 PDF 内嵌文本抽取；`docling-slim` 的 DOCX/Markdown 后端用于 Word 和 Markdown 转换。
- 旧版 Word：通过本机 LibreOffice/`soffice` 转为 DOCX 后解析。
- 大模型：可选 Z.AI SDK `zai-sdk==0.2.2`，调用 GLM 兼容接口生成结构化知识条目。
- 序列化：PyYAML 写入 Markdown Front Matter。
- 测试：Python `unittest`，当前测试集中在规范化和校验质量规则。
- npm 包装：`package.json` 提供 `npm pack --dry-run` 的打包检查和 `bin/union_kb_ingest` 命令入口。

## 目录结构

- `ingest.py`：命令行入口，提供 `parse`、`draft`、`validate` 三个子命令，串联解析、切分、规范化、写入和校验。
- `app_config.py`：读取 YAML 配置，并用环境变量覆盖 LLM 与草稿生成参数。
- `schemas.py`：定义核心数据结构，包括 `ParsedBlock`、`ParsedDocument`、`KnowledgeItem`、`ValidationIssue`。
- `parser.py`：遍历输入文件，解析 PDF/DOCX/DOC/Markdown/TXT，生成统一 Markdown，并从标题、正文和文件名推断文档大类、小类、关键词和同级关联候选。
- `splitter.py`：按章节和字符窗口合并、切分 `ParsedBlock`，控制单次生成上下文长度。
- `normalizer.py`：将 `ParsedBlock` 转为 `KnowledgeItem`。启用 LLM 时构造提示词、解析 JSON、重试并做事实覆盖校验；未启用 LLM 时使用保守启发式模板兜底。
- `writer.py`：把 `KnowledgeItem` 渲染为带 YAML Front Matter 的 Markdown，并按 `source_order` 生成固定宽度排序前缀。
- `validator.py`：校验生成 Markdown 的必填元数据、正文五节结构、核心章节内容、缩写覆盖、分类关系字段和批量分类退化风险。
- `prompts/知识库建立规范.md`：LLM 生成条目的格式和质量规范来源。
- `config/config.yaml`：本地默认配置。不要在文档、日志或提交说明中暴露真实密钥值。
- `input/`：默认原始文件输入目录。
- `parsed/`：`parse` 子命令输出的中间 Markdown 目录。
- `result/`：`draft` 子命令输出的最终知识库 Markdown 目录。
- `tests/`：单元测试目录。
- `bin/union_kb_ingest`：npm bin 包装脚本，转调 `python3 ingest.py`。

## 核心数据模型

- `ParsedDocument` 表示单个来源文档的解析结果，包含来源路径、来源文件名、统一 Markdown 和片段列表。
- `ParsedBlock` 表示一个待整理片段，承载来源章节、正文、页码、顺序、辅助上下文、分类画像、关键词、小类和关联信息。
- `KnowledgeItem` 表示最终写入的知识库条目，包含元数据、正文、来源追踪、分类关系和审核状态。
- `ValidationIssue` 表示校验阶段发现的错误或警告。

## 数据流

1. 输入文件放入 `input/`，或通过 `--input` 指定文件/目录。
2. `parser.iter_input_files()` 递归筛选支持的文件类型。
3. `parser.parse_document()` 按文件类型抽取文本或转换为 Markdown。
4. `parser._markdown_to_blocks()` 按 Markdown 标题切出 `ParsedBlock`。
5. 解析阶段为每个片段补充大类、小类、关键词、文档说明、同级小类和结构化关联候选。
6. `splitter.split_blocks()` 合并短父章节与子章节，并按 `draft.max_chars` 切分过长片段。
7. `ingest._attach_block_context()` 为片段附加文档目录、分类信息、上下片段摘要等辅助上下文。
8. `normalizer.normalize_block()` 将片段整理为一个或多个 `KnowledgeItem`。
9. `normalizer._postprocess_item()` 补写分类摘要、关联能力、来源依据，并清理非来源章节页码痕迹。
10. `writer.write_item()` 以 `000001-...md` 文件名写入 `result/`。
11. `validator.validate_dir()` 对生成结果做结构和质量校验。

## 业务流程

### 只解析中间稿

```bash
python ingest.py parse
```

默认读取 `input/`，输出到 `parsed/`。适合先检查解析质量、标题恢复、页眉页脚噪声和章节切分效果。

### 生成知识库草稿

```bash
python ingest.py draft
```

默认读取 `input/`，输出到 `result/`。如果 `result/` 已有有效文件，命令会询问是否覆盖；确认后会删除旧生成文件再重新生成。

`draft` 会根据 `config/config.yaml` 的 `draft.max_chars`、`draft.context_chars`、`draft.outline_max_sections` 控制单片段长度和辅助上下文规模。启用 LLM 时，大模型只应依据原文和规范生成条目；程序负责 JSON 解析、重试、事实覆盖校验、来源追踪和格式补写。

### 校验生成结果

```bash
python ingest.py validate
```

默认校验 `result/`。有 `error` 时返回非零退出码；`warning` 用于提示正文长度、章节完整性、分类退化、缩写未进入核心正文等质量问题。

## 模块协作说明

- 解析层只处理通用文档格式、结构噪声、章节标题和分类画像，不应写入业务域专属关键词过滤。
- 切分层只负责控制片段大小和结构完整性，不负责创造业务语义。
- 规范化层是业务语义生成的核心。启用 LLM 时，提示词要求模型依据原文生成分类、标签、角色、风险等级和正文五节；未启用 LLM 时只提供保守兜底。
- 后处理层保证输出格式统一，包括分类摘要、关联能力章节、来源依据和页码追踪。
- 校验层只做跨场景质量约束，不应引入某个业务场景专属判断。

## 质量约束

- 输出 Markdown 必须包含 YAML Front Matter。
- `doc_type` 只能是 `biz` 或 `function`。
- 正文应包含 `# 标题`，以及 `## 1. 核心内容`、`## 2. 适用边界`、`## 3. 使用要求`、`## 4. 关联能力`、`## 5. 来源依据`。
- 来源页码只应进入 Front Matter 的 `source_pages`/`source_trace` 和正文 `## 5. 来源依据`。
- 术语、定义、缩写、简称、阈值、单位、时间、数量、例外条件和禁止要求必须进入核心正文，不能只出现在元数据或来源依据。
- `category`、`subcategory`、`category_keywords`、`related_items` 应尽量来自原文结构、标题和正文语义。
- 关键词过滤只允许处理跨场景结构性噪声，例如模板字段、空值占位和固定章节标题。

## 安全与配置注意事项

- `config/config.yaml` 可能含有本地模型服务密钥。说明、日志、提交信息和问题反馈中不得复刻真实密钥值。
- 旧版 `.doc` 解析会调用本机 LibreOffice 命令，属于本地转换流程。
- PDF 解析只抽取内嵌文本，不做 OCR，不加载视觉/版面模型。
- 项目说明和通用代码不能依赖当前 `input/` 中的单一样本文档内容。

## 验证命令

最小代码验证：

```bash
python -m unittest
```

生成结果验证：

```bash
python ingest.py validate
```

解析链路抽查：

```bash
python ingest.py parse
```

打包检查：

```bash
npm run pack:check
```

## 常见改动面

- 调整输入格式或解析质量：优先看 `parser.py`，并用 `parse` 检查中间 Markdown。
- 调整切分粒度或上下文：优先看 `splitter.py`、`ingest._attach_block_context()` 和 `config/config.yaml` 的 `draft` 配置。
- 调整 LLM 输出质量：优先看 `normalizer._build_prompt()`、JSON 解析/重试逻辑和事实覆盖校验。
- 调整最终 Markdown 格式：优先看 `schemas.KnowledgeItem.metadata()`、`writer.py` 和 `normalizer._postprocess_item()`。
- 调整校验规则：优先看 `validator.py`，保持规则跨场景通用。
- 调整命令入口或发布包：优先看 `ingest.py`、`bin/union_kb_ingest`、`package.json`。

## 后续工作约定

- 每次开始处理本仓库任务，先阅读本文件和 `AGENTS.md`。
- 后续对话中的项目路径以 `/Users/simon/code/kb_ingest` 为准；历史旧路径只作为迁移前参考。
- 修改前先确认相关模块当前行为，避免基于旧记忆或单一样本推断。
- 修改后只验证当前仓库代码和生成结果；除非明确要求，不复制文件到其他项目，也不重建其他项目向量库。
- 若任务涉及外部 SDK、CLI、模型接口或发布流程，使用官方文档或本地实测确认行为。
