# 项目原创合成材料 / Project-authored synthetic material

两个集合均为本项目设定要求后由 AI 辅助编写的原创合成材料；文本和测试标注以 CC0-1.0 发布（JSON 中简称 `CC0`）。它们不是已发表论文、真实实验记录或人类作者语料。虚构的数值与引用标记仅作为软件测试材料，不能作为研究证据引用。

`smoke.jsonl` 包含14段冒烟样例（中文8段、英文6段），主要覆盖数字、单位、引用占位符、公式、重复术语、否定和适用范围等规则边界。该集合保持固定，供比较不同运行配置时复用。

`prose.jsonl` 补充10段方法设计初稿（中文6段、英文4段）。这些段落描述尚未实施的研究方案，涉及检索证据、来源划分、标注一致性、工具调用、响应延迟与数据最小化。它们用于检查较常见的正式初稿表达，有些段落不含数字，有些包含明确的计划参数。所有方案、评审安排和测量设置均为合成设计，没有宣称已招募参与者、完成实验、获得结果或发表文献。

两个文件使用相同 JSONL 字段：`id`、`language`、`text`、`protected_terms`、`synthetic`、`license`、`source`。`protected_terms` 是须原样保留的术语，不是对语义保真的完整定义。任何规则检查通过仍要求人工复核。

新增补充集属于开发材料，不是留出测试集。作者已知这些输入，也可能用它们发现并修正程序问题，因此不能据此声称对未见论文或真实用户稿件的泛化能力。样例在运行前确定，不根据模型输出挑选。若进行评测，应公开全部样例及原始输出、失败、保留原文和警告，不能仅展示成功片段或过滤不理想的结果。

实际运行记录位于 [`artifacts/`](../artifacts/)，说明见[测试与限制](../docs/evaluation.md)。运行须与本地模型队列协调，使用新的结果文件记录配置，不覆盖原有实测记录。不要为取得更好结果覆盖已有样例；新增样例应保留原始运行记录和语料哈希。两套材料都不支持商业检测器降分效果、通过率或人类身份结论。

## English

Both corpora are original, project-authored, AI-assisted synthetic fixtures released under CC0-1.0. They are not published papers, real experimental records, or a human-authorship dataset. The frozen `smoke.jsonl` contains 8 Chinese and 6 English cases targeting visible fidelity constraints. The additional `prose.jsonl` contains 6 Chinese and 4 English methodological proposals, with a more typical formal draft style and a mix of numerical and nonnumerical content.

The proposals describe hypothetical future protocols rather than completed research. They contain no claimed experimental results or published sources. They share the evaluator's input schema, and protected terms do not constitute a complete semantic check.

The supplement is development material, not a held-out benchmark. Cases are authored before evaluation and are not selected based on model outputs. Publish every case and unedited outcome, including failures, warnings, and retained source text. Do not filter results to create a success impression. Adding this dataset does not mean inference has been run, and neither corpus demonstrates commercial detector effectiveness or generalization to real manuscripts.
