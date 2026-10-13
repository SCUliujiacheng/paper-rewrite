# 改稿台：第一版设计

中文科研写作者希望修改 AI 初稿的表达，保留论点、数据和引用，并比较检测结果。中文先验收，英文通过同一条真实模型链路后发布独立英文仓库。用户已授权自行研发、测试及发布，不再逐项审批。

## 方案

采用公开的 `jialinyyzz/humanizer` 专项改写权重作为可替换后端，原创 Python 服务和中文优先的 React 工作台。不是自主训练模型，也不是给上游程序换名字。保留上游提示格式和归属说明，不转发上游训练数据。DIPPER 适合英文实验对照但显存要求高；从零微调需要许可清晰的数据和独立评测，暂不选择。

## 第一版交付范围

- 本机浏览器工作台与 CLI；中文、英文界面；文本 / Markdown 导入，逐段处理和原文对照，TXT / JSON 报告下载。
- 单篇最多 12000 字符，最多 60 个段落；每段最多 1000 字符，超长段落拒绝并说明拆分；默认每段 2 个候选，允许 1–3 个。有风险的段落保留原文，不静默改写错误内容。
- 调用 localhost llama.cpp `/completion`，使用上游训练时的原始提示格式。请求超时、不可用、截断、无输出均明确失败，绝不以规则替换伪装模型成功。
- 对数字（含常见中文数词与单位）、引文标记、网址、LaTeX 公式、代码和用户指定原样保留的术语做差异检查。数字与单位按整体比较。否定和确定性变化为风险提示。检查未发现问题不代表语义等价：每份报告要求人工复核。
- Markdown 标题、表格、代码块、参考文献段落不改写。保留空白分隔符。单段失败可保留原文并继续，模型连接失败不标记整篇成功。
- 检测结果独立于改写；第一版提供 GPTZero 官方 API 适配与手工报告导入，未运行显示“未检测”。仅配置密钥且用户明确点击外部检测后发送文本；不自动上传、无隐形采样付费循环。保留检测器名称、版本、时间、原始字段与文本哈希，两个检测器分数不合成虚假统一“AI率”。
- 中文与英文合成学术样例，明确为软件回归 / 冒烟集而非人类论文或未见分布泛化证据。公布实际模型运行、失败和原文保留情况。无商业检测密钥则明确未验证降分效果。
- 公开中文仓库 `paper-rewrite-zh`；英文实测可用后发布 `paper-rewrite`，共用代码，仅默认语言与首页不同。CI 覆盖 Python、前端、依赖审计与双语行为。

## 边界与隐私

软件不生成虚构引文、实验数据或作者经历，不证明内容由人独立完成，不承诺各平台通过率。学术用户应遵守所在机构的 AI 使用与披露规则。没有账号、追踪、远端日志或自动保存稿件；只在内存处理，导出由用户决定。服务只绑定 127.0.0.1，校验 Host / Origin；模型地址仅启动配置且限制 loopback，不能由请求任意设置。外部检测密钥只读环境变量，不写入仓库或回显。

## 实现接口

`audit(source, candidate, protected_terms=[]) -> AuditResult`，issues 有 code / severity / before / after；`blocked` 为硬性约束失败。

`split_document(text) -> list[Segment]`，segment 含 id / text / separator / rewriteable。不改段落不能调用模型。

`Rewriter.rewrite(text, language, protected_terms, candidates) -> RewriteReport`，报告含 source / output / segments / warnings / model / elapsed_seconds / requires_review=true / detector_status=not_run / source_sha256 / output_sha256。段落含 original / output / status(rewritten,retained,skipped,failed) / audit / attempts；所有被拒绝候选和原因都记录。

API: GET `/api/health`; POST `/api/rewrite` JSON {text,language:zh|en,protected_terms:string[],candidates:1..3}; POST `/api/check` {source,candidate,protected_terms}; POST `/api/detect` {source,candidate,consent:true}; POST `/api/detector-report` 验证手工导入检测报告的文本哈希。模型请求可中断，API 单并发，忙时 429。请求体大小受限。

## 验收

测试先于实现。覆盖数值单位替换、数字不变但关系反转、重复引文数量、保护词重复、Markdown 代码与引用、长输入、换行、多语言、模型失败、截断、XSS、跨站请求、外部检测未授权、错误密钥不泄漏、检测报告与文本不匹配。真实模型至少中英各 6 段，完整公开样例输出，不能用单元测试替代模型效果。桌面与移动视口操作验证；独立代码审查后才发布。
