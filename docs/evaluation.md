# 测试与限制

这里把三件事分开记录：程序是否按预期工作、模型是否真的生成了改写、检测平台是否给了不同分数。前一项通过，不能推出后一项通过。

## 软件测试

Python 测试覆盖文本结构、数字与引文、候选选择、模型错误、API 的本机访问限制、实际断开连接后的取消，以及检测报告校验。模型和检测器的接口测试使用明确标记的夹具，不把预设输出计为真实模型效果。

前端测试覆盖导入、改写参数、取消、修改输入后旧报告失效、两种界面语言、JSON 往返导入及文本安全渲染。浏览器检查另看桌面和手机宽度的实际布局。GitHub Actions 会运行 Windows / Linux 的 Python 测试、前端测试及依赖审计；最新状态以该仓库的 Actions 页面为准。

```sh
uv run pytest -q
uv run ruff check src tests scripts
npm --prefix web test
npm --prefix web run build
npm --prefix web audit
```

## 真实模型复现

固定输入位于 [`data/smoke.jsonl`](../data/smoke.jsonl)：中文 8 段、英文 6 段，全部是虚构的学术描述。它们已经用于开发，不能称为未见测试集。保护词随样例公开；原始输出不应为了展示效果而删改。

启动本机模型后，可在仓库根目录运行：

```sh
uv run python scripts/evaluate.py --output artifacts/my-run.json --candidates 2
```

这条命令不会自行检测外部平台，也不会覆盖已有报告。为记录实际文件，可加上 `--model-file`、`--model-repo`、`--model-revision`、`--runtime`。脚本计算本地文件的 SHA-256；仓库名、修订和运行时描述由操作者提供。文件哈希不能独立证明 HTTP 服务加载的是同一个文件，所以报告保留 `backend_identity_verification: not_verified`，不伪造远程证明。

运行报告中的指标：

| 字段 | 含义 |
| --- | --- |
| `changed_cases` | 最终输出与原文不同的样例数；不是“降 AI 率成功数” |
| `completed` | 所有可处理段落均产生通过规则检查的不同文本 |
| `partial` | 有改写，但另有段落被保留或失败 |
| `unchanged` | 没有候选被选中，或没有可改写正文 |
| `failed` | 没有成功改写且出现模型错误 |
| `rejected_candidates` | 被内容规则拦下的候选数，原文和候选都留在 JSON |
| `warning_cases` | 出现否定或确定性等警告的样例数 |
| `total_seconds` | 本次逐段处理耗时，不是跨硬件性能排名 |

规则检查是为了发现一部分容易看漏的改动。它不能理解所有实体与数值关系，不能证明引用确实支持论点，也不能保证模型没有改变因果、方法细节或适用范围。少量样例没有出现错误，不代表真实论文上不会发生。

## 外部检测仍未实测

当前没有商业检测凭据，也没有本项目的真实前后分数。GPTZero 适配器做过协议夹具测试，但还没有用真实密钥验证。不能据此宣称通过中文论文检测，或把上游模型在别处的结果算作本项目成绩。

如果后续补充效果评测，应单独列出：检测器和版本、测试时间、文本许可与来源、原文/改写哈希、原始报告、失败样例、语义复核方法和费用。不要只展示几段成功样例，也不要把不同供应商的分数合成一个“通用 AI 率”。

## English summary

Software correctness, actual rewriting, and detector effectiveness are separate questions. The frozen corpus is eight Chinese and six English synthetic passages used during development, not a held-out benchmark. `changed_cases` counts changed outputs, not detector wins. JSON reports retain rejected candidates and errors. Local artifact hashes verify a file, not the identity of a running server. No commercial detector effectiveness has been measured, and automated checks do not establish semantic equivalence or human authorship.
