import json

import pytest

from paper_rewrite.guards import audit
from paper_rewrite.pipeline import Rewriter

_PLANNED_PROTOCOL = (
    "To assess annotation agreement, the protocol would ask 3 reviewers to evaluate each "
    "response independently before discussing disagreements. A set of 20 practice items "
    "would be used to clarify the decision rules and would remain separate from the "
    "evaluation material. Each judgment would include a short rationale linking the "
    "decision to the supplied evidence. The proposed analysis would retain initial "
    "judgments alongside the discussion record, allowing disagreements about the rules "
    "to be distinguished from uncertainty within the material itself."
)
_ASSERTED_PROTOCOL = (
    "To assess annotation agreement, the protocol asks 3 reviewers to evaluate each "
    "response independently before discussing disagreements. A set of 20 practice items "
    "would clarify decision rules and remain separate from evaluation material. Each "
    "judgment includes a short rationale linking the decision to supplied evidence. The "
    "proposed analysis retains initial judgments alongside the discussion record, allowing "
    "disagreements about rules to be distinguished from uncertainty within the material itself."
)
_CHINESE_PLANNED_PROSE = (
    "数据最小化原则拟贯穿研究材料的收集、处理与共享环节。方案计划优先使用经参与者确认可以提供的内容，"
    "并在进入分析流程前移除与研究问题无关的身份信息。对于必须保留的背景字段，需要分别说明其分析用途"
    "及访问范围。共享材料的形式拟根据复核需求确定，同时提供字段说明与处理步骤，使外部评审能够理解"
    "分析依据及其边界。"
)
_CHINESE_ASSERTED_PROSE = (
    "数据最小化原则将贯穿研究材料的收集、处理与共享全过程。方案拟优先采用经参与者确认提供的内容，"
    "并在进入分析流程前剔除与研究问题无关的身份信息。对于必须保留的背景字段，需分别阐明其分析用途"
    "及访问范围。共享材料的形式将根据复核需求确定，同时附上字段说明与处理步骤，以便外部评审理解"
    "分析依据及其边界。"
)


@pytest.mark.parametrize(
    ("source", "candidate", "code"),
    [
        ("质量为 5 mg，体积为 8 mL。", "质量为 5 mL，体积为 8 mg。", "numbers"),
        ("比例为 12.5%。", "比例为 13.5%。", "numbers"),
        ("共有三十例患者。", "共有三十一例患者。", "numbers"),
        ("温度为 -5 °C。", "温度为 5 °C。", "numbers"),
        ("浓度为 2 μg/mL。", "浓度为 2 mg/mL。", "numbers"),
        ("A > B，样本为 10 个。", "A < B，样本为 10 个。", "comparisons"),
        ("A > B。", "B > A。", "comparisons"),
        ("指标低于 10%。", "指标高于 10%。", "comparisons"),
        ("支持这一结论[1]，另有发现[1]。", "支持这一结论[1]。", "citations"),
        ("已有研究[1, 3–5]。", "已有研究[1, 3–6]。", "citations"),
        ("已有研究（Wang et al., 2023）。", "已有研究（Li et al., 2023）。", "citations"),
        ("See https://example.org/paper?id=1.", "See https://example.org/paper?id=2.", "urls"),
        ("关系为 $x^2+y^2=1$。", "关系为 $x^2-y^2=1$。", "latex"),
        (r"关系为 \(x+y\)。", r"关系为 \(x-y\)。", "latex"),
        ("调用 `fit(x)` 得到结果。", "调用 `fit(y)` 得到结果。", "code"),
        ("```py\nx=1\n```", "```py\nx=2\n```", "code"),
    ],
)
def test_blocks_changes_to_visible_protected_facts(source, candidate, code):
    result = audit(source, candidate)
    assert result.blocked
    assert any(issue.code == code and issue.severity == "error" for issue in result.issues)
    assert result.requires_review is True


def test_preserves_repeated_protected_terms():
    result = audit(
        "自监督学习优于基线；自监督学习仍有局限。", "自监督学习优于基线，仍有局限。", ["自监督学习"]
    )
    assert result.blocked
    issue = next(issue for issue in result.issues if issue.code == "protected_terms")
    assert "自监督学习" in issue.before
    assert issue.before != issue.after


@pytest.mark.parametrize(
    "candidate",
    ["", " \r\n ", '{"rewrite": "changed"}', "<html>result</html>", "Here is the rewritten text:"],
)
def test_rejects_empty_or_model_wrappers(candidate):
    result = audit("这是待改写的论文正文。", candidate)
    assert result.blocked
    assert any(issue.code == "invalid_output" for issue in result.issues)


@pytest.mark.parametrize(
    ("source", "candidate", "code"),
    [
        ("实验未发现差异。", "实验发现差异。", "negation"),
        ("The effect is not significant.", "The effect is significant.", "negation"),
        ("这可能与环境有关。", "这必然与环境有关。", "certainty"),
        (
            "The result may indicate an association.",
            "The result proves an association.",
            "certainty",
        ),
    ],
)
def test_flags_negation_and_certainty_for_review(source, candidate, code):
    result = audit(source, candidate)
    assert not result.blocked
    assert any(issue.code == code and issue.severity == "warning" for issue in result.issues)
    assert result.requires_review


def test_accepts_prose_changes_with_intact_facts_without_claiming_equivalence():
    result = audit("实验纳入 12 例，剂量为 5 mg[2]。", "本实验共纳入12例，使用剂量为5mg[2]。")
    assert not result.blocked
    assert result.issues == []
    assert result.model_dump() == {"blocked": False, "issues": [], "requires_review": True}


def test_checks_introduced_facts_as_well_as_removed_facts():
    assert audit("实验观察到差异。", "实验观察到 20% 的差异。").blocked


def test_preserves_occurrences_instead_of_only_unique_urls():
    assert audit("见 https://example.org 和 https://example.org", "见 https://example.org").blocked


@pytest.mark.parametrize(
    ("source", "candidate", "code"),
    [
        ("Wang (2023) reports an effect.", "Li (2023) reports an effect.", "citations"),
        ("张三（2023）报告了差异。", "李四（2023）报告了差异。", "citations"),
        ("样本数为三十。", "样本数为三十一。", "numbers"),
        ("比例为百分之十二。", "比例为百分之十三。", "numbers"),
        ("The rate was 5 percent.", "The rate was 5 per mille.", "numbers"),
        ("A is greater than B.", "B is greater than A.", "comparisons"),
        ("A组高于B组。", "B组高于A组。", "comparisons"),
    ],
)
def test_blocks_additional_common_academic_fact_formats(source, candidate, code):
    result = audit(source, candidate)
    assert result.blocked
    assert any(issue.code == code for issue in result.issues)


def test_does_not_mistake_discourse_words_for_chinese_quantities():
    result = audit("一方面，结果一致。另一方面，仍需验证。", "结果一致，但仍需要验证。")
    assert not result.blocked


def test_does_not_parse_the_start_of_an_english_word_as_a_unit():
    result = audit("We compared 12 models.", "We compared 12 networks.")
    assert not result.blocked


@pytest.mark.parametrize(
    ("source", "candidate", "code"),
    [
        ("显著性水平为 .05。", "显著性水平为 05。", "numbers"),
        ("随访三至五天。", "随访四至五天。", "numbers"),
        ("比例为三分之二。", "比例为三分之一。", "numbers"),
        ("质量为 5 微克。", "质量为 5 纳克。", "numbers"),
        ("Wang and Li (2023) report results.", "Chen and Li (2023) report results.", "citations"),
        (
            "Smith & Jones (2023) report results.",
            "Brown & Jones (2023) report results.",
            "citations",
        ),
        ("已有研究[@smith2023]。", "已有研究[@wang2023]。", "citations"),
    ],
)
def test_blocks_reviewed_quantity_and_citation_gaps(source, candidate, code):
    result = audit(source, candidate)
    assert result.blocked
    assert any(issue.code == code and issue.severity == "error" for issue in result.issues)


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        ("显著性水平采用 .05。", "采用显著性水平.05。"),
        ("随访三至五天。", "进行三至五天随访。"),
        ("比例三分之二。", "三分之二的比例。"),
        ("质量 5 微克。", "5微克的质量。"),
        ("Wang and Li (2023) report results.", "Results from Wang and Li(2023) are reported."),
        ("Smith & Jones (2023) report results.", "Results from Smith & Jones(2023) are reported."),
        ("已有研究[@smith2023]。", "先前研究[@smith2023]。"),
    ],
)
def test_allows_prose_changes_around_unchanged_reviewed_facts(source, candidate):
    result = audit(source, candidate)
    assert not result.blocked
    assert result.requires_review


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        (
            "> ```python\n> result = first + second\n> ```",
            "> ```python\n> result = first - second\n> ```",
        ),
        (
            "- ```python\n  result = first + second\n  ```",
            "- ```python\n  result = first - second\n  ```",
        ),
    ],
)
def test_direct_audit_protects_fences_nested_in_markdown_containers(source, candidate):
    result = audit(source, candidate)
    assert result.blocked
    assert any(issue.code == "code" for issue in result.issues)


def test_unchanged_nested_code_allows_changes_in_surrounding_prose():
    code = "> ```python\n> result = first + second\n> ```"
    assert not audit("原文说明。\n\n" + code, "新的说明。\n\n" + code).blocked


def test_warns_when_recorded_candidate_removes_repeated_proposed_modality():
    result = audit(_PLANNED_PROTOCOL, _ASSERTED_PROTOCOL)
    assert not result.blocked
    issue = next(issue for issue in result.issues if issue.code == "certainty")
    assert issue.severity == "warning"
    assert json.loads(issue.before) == {"would": 5}
    assert json.loads(issue.after) == {"would": 1}
    assert result.requires_review


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        (
            "The protocol would ask reviewers for feedback.",
            "The protocol asks reviewers for feedback.",
        ),
        (
            "Reviewers should retain their initial judgments.",
            "Reviewers retain their initial judgments.",
        ),
    ],
)
def test_warns_when_plans_or_recommendations_become_assertions(source, candidate):
    result = audit(source, candidate)
    assert not result.blocked
    assert any(issue.code == "certainty" and issue.severity == "warning" for issue in result.issues)


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        (
            "The protocol would ask reviewers for feedback.",
            "Reviewers would give protocol feedback.",
        ),
        (
            "Reviewers should retain their initial judgments.",
            "Initial judgments should be retained.",
        ),
        ("The shoulder protocol remains valid.", "The protocol remains valid."),
    ],
)
def test_does_not_warn_when_modal_occurrences_are_unchanged(source, candidate):
    assert audit(source, candidate).issues == []


async def test_existing_pipeline_withholds_recorded_candidate_with_modality_warning():
    class RecordedOutputModel:
        name = "recorded-candidate-fixture"

        async def complete(self, text, seed=0, protected_terms=()):
            return _ASSERTED_PROTOCOL

    report = await Rewriter(RecordedOutputModel()).rewrite(_PLANNED_PROTOCOL, "en", [], 1)
    assert report.output == _PLANNED_PROTOCOL
    assert report.status == "unchanged"
    assert report.segments[0].status == "retained"
    attempt = report.segments[0].attempts[0]
    assert attempt.text == _ASSERTED_PROTOCOL
    assert any(issue.code == "certainty" for issue in attempt.audit.issues)
    assert "candidates_require_manual_review" in report.warnings


def test_warns_when_frozen_chinese_candidate_loses_proposal_markers():
    result = audit(_CHINESE_PLANNED_PROSE, _CHINESE_ASSERTED_PROSE)
    assert not result.blocked
    warnings = [issue for issue in result.issues if issue.code == "certainty"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert json.loads(warnings[0].before) == {"拟": 2, "计划": 1, "确定": 1}
    assert json.loads(warnings[0].after) == {"拟": 1, "确定": 1}


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        ("本研究拟开展评价。", "本研究将开展评价。"),
        ("本研究计划开展评价。", "本研究将开展评价。"),
        ("本研究打算开展评价。", "本研究开展评价。"),
        ("模拟数据拟用于评价。", "模拟数据用于评价。"),
    ],
)
def test_warns_when_chinese_proposals_become_stronger_assertions(source, candidate):
    result = audit(source, candidate)
    assert not result.blocked
    assert any(issue.code == "certainty" and issue.severity == "warning" for issue in result.issues)


@pytest.mark.parametrize(
    ("source", "candidate"),
    [
        ("本研究拟开展评价。", "本研究拟进行评价。"),
        ("本研究计划开展评价。", "本研究计划进行评价。"),
        ("本研究打算开展评价。", "本研究打算进行评价。"),
        ("我们使用模拟数据。", "我们使用合成数据。"),
        ("我们使用虚拟环境。", "我们使用测试环境。"),
        ("我们比较拟合模型。", "我们比较回归模型。"),
        ("文本包含拟人表达。", "文本包含人格化表达。"),
        ("文本包含拟声词。", "文本包含声音词。"),
    ],
)
def test_preserves_chinese_proposal_counts_and_ignores_nonproposal_words(source, candidate):
    assert audit(source, candidate).issues == []


async def test_existing_pipeline_withholds_frozen_chinese_proposal_change():
    class RecordedChineseOutputModel:
        name = "recorded-candidate-fixture"

        async def complete(self, text, seed=0, protected_terms=()):
            return _CHINESE_ASSERTED_PROSE

    report = await Rewriter(RecordedChineseOutputModel()).rewrite(
        _CHINESE_PLANNED_PROSE, "zh", [], 1
    )
    assert report.output == _CHINESE_PLANNED_PROSE
    assert report.status == "unchanged"
    assert report.segments[0].status == "retained"
    assert report.segments[0].attempts[0].text == _CHINESE_ASSERTED_PROSE
    assert "candidates_require_manual_review" in report.warnings
