# 外部检测 / External detection

本项目尚未测试商业检测器的检测效果或改写前后降分效果。传输层测试使用本地 HTTP 响应夹具，不调用付费 API。检测分数是供应商预测，不能证明作者身份、学术诚信或语义等价。

Commercial detection effectiveness and before/after score changes have not been tested. Transport tests use local HTTP fixtures, without paid API calls. Detector predictions do not prove authorship, academic integrity, or semantic equivalence.

## 显式授权 / Explicit consent

`GPTZeroDetector(api_key, transport=None, *, timeout_seconds=30)` 提供异步 `compare(source, candidate, consent: bool) -> DetectorReport`。仅 `consent is True` 且密钥非空时，才顺序上传两篇文本至固定的官方 `https://api.gptzero.me/v2/predict/text` 端点；不会重试、自动评测或跟随重定向。调用方只从环境变量读取密钥，不能回显。未同意返回 `not_run`；同意但无密钥返回 `not_configured`；失败返回安全错误代码。文本只在内存处理。

Only literal `True` consent plus a configured key permits two sequential uploads to the fixed official endpoint. There are no retries, automatic evaluations, or redirect following. The caller reads the key from an environment variable and must not echo it. Absent consent returns `not_run`; absent configuration returns `not_configured`; failures return safe codes. Text remains in memory.

## 报告接口 / Report contract

报告可通过 `model_dump(mode="json")` 导出：`detector`, `status`, `model_version`, `measured_at`, `source_sha256`, `output_sha256`, `before`, `after`, `error`, `provenance`, `user_supplied`。状态只允许 `completed | not_configured | not_run | error`。每侧测量包含 `probabilities`, `classification`, `raw`, `model_version`；保留经过校验的原始文档概率、分类和可用的置信字段，不保留供应商返回的文本或未知元数据。概率必须是有限的0–1数值，类别概率之和容差为0.001。不同版本会保留在各侧；未返回版本或双方不同则报告整体为 `unknown`。时间使用带时区的 UTC。

Reports export with `model_dump(mode="json")`. Each side retains validated raw document probabilities and classification, with available confidence fields. Unknown metadata and returned text are excluded. Scores must be finite numbers in [0,1], with class probabilities summing to one within 0.001. Each measurement carries its version; missing or unequal versions yield overall `unknown`. Timestamps are timezone-aware UTC.

`validate_manual_report(payload, source, candidate) -> DetectorReport` 只接收该结构的 GPTZero 报告，重新计算 UTF-8 SHA-256 并校验分数与原始字段一致、时间和状态一致；不一致抛出 `ValueError`。结果强制设置 `provenance="user_supplied"` 与 `user_supplied=true`，不信任导入文件中宣称 API 验证的标志。哈希绑定仅说明报告对应给定文本，不认证供应商或实际检测过程。

Manual import validates the same GPTZero report shape, exact UTF-8 text hashes, raw-score consistency, timestamps, and status. Invalid input raises `ValueError`. The result is always marked `user_supplied`, regardless of incoming flags. Hash binding does not authenticate the provider or establish that a detector actually ran.

## 官方契约来源 / Official contract sources

2026-10-14 核对：[GPTZero 开发者页面](https://gptzero.me/developers)给出 v2 文本端点、`document` 请求字段和 `x-api-key`；[官方结果说明](https://support.gptzero.me/articles/8947054519-how-do-i-use-and-interpret-the-results-from-your-api)说明 `document_classification`、`class_probabilities` 与置信字段。[官方概率说明](https://gptzero.me/news/chicago-booth-2026/)明确文档比较应使用类别概率而不是句级概率均值，并介绍扩展类别。官方链接的 Stoplight 详细文档路由在本次核对时返回404；尚未使用真实密钥验证返回信封与版本字段。

Checked on 2026-10-14: the official developer and support pages document the endpoint, request/authentication fields, classification, and class probabilities. The official probability article distinguishes document class probabilities from sentence averages. The linked detailed Stoplight route returned 404 during this check. Response envelope and version fields have not been verified with a real key.

## 合成样本 / Synthetic corpus

`data/smoke.jsonl` 包含14段项目原创样例（中文8段、英文6段），以CC0发布。所有实验、数值和引文占位符均为虚构，仅用于回归与冒烟测试；不是人类论文语料，也不支持泛化或检测器效果结论。

The 14 project-authored CC0 snippets (8 Chinese, 6 English) contain invented toy experiments, numbers, and placeholder citations. They are regression/smoke fixtures, not a human-paper corpus or evidence of generalization or detector effectiveness.
