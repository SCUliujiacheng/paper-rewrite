import pytest

from paper_rewrite.guards import audit


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
