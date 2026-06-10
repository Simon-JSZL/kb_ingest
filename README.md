# 离线知识库文件生成工具

这个目录是离线辅助工具，不参与线上应用运行。

目标：

1. 批量读取 PDF、Word、Markdown、TXT 文档。
2. 通过 Docling slim 的离线文本解析能力生成统一 Markdown 中间格式。
3. 按章节、场景、规则、指标等粒度切割。
4. 可选调用大模型，把内容整理为项目知识库规范要求的 Markdown 文件。
5. 默认生成可直接交给知识库项目使用的 `status: active` Markdown 文件。

启用大模型时，工具只会读取 `prompts/知识库建立规范.md` 作为格式和质量约束，并由代码按当前片段、辅助上下文和输出 JSON 结构组装生成提示词。模型需依据原文语义判断业务场景、模块、角色、标签和风险等级；代码中的启发式生成只作为未启用大模型时的兜底，不使用预设业务关键词去指导大模型输出。

## 安装可选依赖

不建议把这些依赖加入项目根 `requirements.txt`。离线机器单独安装即可：

```bash
python -m pip install -r requirements.txt
```

解析层不使用 OCR，不加载本地视觉/版面模型，也不访问远程模型服务：

- PDF：使用 `docling-parse` 抽取 PDF 内嵌文本和文本行顺序；扫描件或图片型 PDF 不会识别。
- DOCX：使用 Docling 的 Word 后端转为 Markdown。
- 旧版 `.doc`：通过 LibreOffice `soffice` 转为 `.docx` 后再解析；不使用 OCR。
- Markdown / TXT：作为已文本化材料直接读取。

不要安装 `docling` 或 `docling-slim[standard]`，它们会引入 OCR、版面/表格模型、Torch/ONNXRuntime 等重依赖，并可能在运行时下载模型。内网机器建议为离线工具单独准备 Python 3.10+ 环境。

## 基本用法

把文件放入：

```text
input/
```

生成知识库文件：

```bash
python ingest.py draft
```

如果 `result/` 中已有生成文件，命令会提示选择删除重建、从断点继续或退出。断点状态保存在 `result/.draft_progress.json`，大模型多次重试失败退出时会记录当前文件和片段位置，下次可选择从断点继续。

只解析为中间 Markdown：

```bash
python ingest.py parse
```

校验生成结果：

```bash
python ingest.py validate
```

默认目录为 `input/`、`parsed/` 和 `result/`。只有需要处理其他目录时，才使用 `--input` 或 `--output` 覆盖。

`draft` 默认按 `config/config.yaml` 的 `draft.max_chars` 控制单次送入模型的原文长度，并额外提供文档目录和相邻片段摘要作为辅助上下文。这样可以降低私有模型单轮负载，同时尽量保留前后章节关系。命令行仍可用 `--max-chars` 临时覆盖。

每条知识库文件会写入分类画像元数据：`category`、`subcategory`、`category_keywords` 和 `related_items`。这些字段优先来自源文件一级标题、首页标题、章节目录、文件名、当前小类正文和关联小类语义，用于标识知识大类、小类、关键词和条目间关系。后续 RAG 入库和检索时，应把这些字段写入向量库 metadata，并用于分类过滤、查询路由或重排加权，降低不同场景之间因为相似词命中而串场的概率。

生成结果会按原始输入遍历顺序写入 `source_order`，并用 `000001-...md` 这样的文件名前缀保持目录排序与原文从上到下的顺序一致。页码只写入 Front Matter 的 `source_pages`/`source_trace` 和正文 `## 5. 来源依据`，不会进入正文 `## 1. 核心内容` 到 `## 4. 关联能力`。

## 大模型配置

默认不强制调用大模型，会使用启发式模板生成知识库文件。

如果要启用大模型整理，修改 `config/config.yaml`：

```yaml
llm:
  enabled: true
  base_url: "https://open.bigmodel.cn/api/paas/v4/"
  api_key: "your-zhipu-api-key"
  model: "glm-4.7"
  timeout_seconds: 120
  max_tokens: 8192
  temperature: 0.1

draft:
  max_chars: 3600
  context_chars: 800
  outline_max_sections: 40
```

也可以继续使用环境变量覆盖配置文件：

```bash
export KB_LLM_ENABLED=true
export KB_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
export KB_LLM_API_KEY="your-zhipu-api-key"
export KB_LLM_MODEL="glm-4.7"
```

工具通过 Z.AI 新版 Python SDK 调用中文智谱开放平台 GLM，依赖固定为 `zai-sdk==0.2.2`，客户端固定使用官方中文写法 `from zai import ZhipuAiClient`，`base_url` 使用 `https://open.bigmodel.cn/api/paas/v4/`。工具不再包含旧 `zhipuai` SDK、国际版 `ZaiClient` 或 OpenAI 调用路径，也不 import 项目 `src` 代码。

## 与线上项目的关系

这个工具只产出符合规范的 `*.md` 文件到 `result/`，后续由线上知识库加载流程处理。

建议线上打包时排除整个 `tools/kb_ingest` 目录。
