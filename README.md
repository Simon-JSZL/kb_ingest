# 离线知识库文件生成工具

这个目录是离线辅助工具，不参与线上应用运行。

目标：

1. 批量读取 PDF、Word、Markdown、TXT 文档。
2. 通过 Docling slim 的离线文本解析能力生成统一 Markdown 中间格式。
3. 按章节、场景、规则、指标等粒度切割。
4. 可选调用大模型，把内容整理为项目知识库规范要求的 Markdown 文件。
5. 默认生成 `status: draft` 草稿，不进入现有 RAG 检索。

启用大模型时，工具会把 `prompts/联合运维知识库建立规范.md` 作为格式和质量约束放入提示词，要求模型依据原文语义判断业务场景、模块、角色、标签和风险等级。代码中的启发式生成只作为未启用大模型或调用失败时的兜底，不使用预设业务关键词去指导大模型输出。

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

生成草稿：

```bash
python ingest.py draft
```

如果 `drafts/` 中已有草稿文件，命令会先询问是否覆盖。选择 `y` 后会清空 `drafts/`、`approved/` 和 `result/` 中已有生成文件，再重新生成；选择其他内容会直接退出，避免多次生成结果相互影响。

只解析为中间 Markdown：

```bash
python ingest.py parse
```

校验草稿：

```bash
python ingest.py validate
```

审核后复制到知识库：

```bash
python ingest.py promote
```

默认目录为 `input/`、`parsed/`、`drafts/`、`approved/` 和 `result/`。只有需要处理其他目录时，才使用 `--input`、`--output` 或 `--result-dir` 覆盖。

## 大模型配置

默认不强制调用大模型，会使用启发式模板生成 `draft` 文件。

如果要启用大模型整理，修改 `config/config.yaml`：

```yaml
llm:
  enabled: true
  base_url: "https://your-model-endpoint"
  api_key: "your-api-key"
  model: "your-model"
  timeout_seconds: 120
  max_tokens: 4096
  temperature: 0.1
```

也可以继续使用环境变量覆盖配置文件：

```bash
export KB_LLM_ENABLED=true
export KB_LLM_BASE_URL="https://your-model-endpoint"
export KB_LLM_API_KEY="your-api-key"
export KB_LLM_MODEL="your-model"
```

`base_url` 必须填写完整的大模型调用地址，工具不会自动拼接任何路径。工具不 import 项目 `src` 代码。

## 与线上项目的关系

这个工具只产出符合规范的 `*.md` 文件。确认无误后，人工把 `status: draft` 改为 `active`，再放入 `result/`，后续由线上知识库加载流程处理。

建议线上打包时排除整个 `tools/kb_ingest` 目录。
