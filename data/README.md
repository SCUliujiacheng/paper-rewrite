# 合成回归语料 / Synthetic smoke corpus

`smoke.jsonl` 固定包含 14 条：中文 8 条、英文 6 条。文本为本项目人工设定要求后由 AI 辅助编写的虚构实验描述；不来自真实论文，不可作为真实研究结果引用。文本和测试标注以 CC0-1.0 发布。

这些样例覆盖数值、引用、方法名称、局限和不确定性。它们同时用于开发和冒烟验证，不是未见测试集，也不是“真实人类文本”。不得把改写成功数当成检测通过率或泛化成绩。

字段：`id` 为稳定标识，`language` 为文本语言，`text` 为原文，`protected_terms` 为原样保留的术语。不要为了得到更好结果而覆盖已有样例；新增样例应保留原始运行记录和语料哈希。

These 14 fictional academic passages (8 Chinese, 6 English) are AI-assisted synthetic software fixtures released under CC0-1.0. They are neither published findings nor a held-out detector benchmark. Do not cite their numerical statements as research evidence.
