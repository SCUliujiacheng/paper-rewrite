import pytest

from paper_rewrite.model import ModelError
from paper_rewrite.pipeline import Rewriter


class SequenceModel:
    name = "test-double-not-a-real-benchmark"

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def complete(self, text, seed=0):
        self.calls.append(text)
        result = next(self.outputs)
        if isinstance(result, Exception):
            raise result
        return result


async def test_unsafe_candidate_not_selected_and_rejection_remains_visible():
    rewriter = Rewriter(SequenceModel(["样本量为25例。", "本实验纳入20例样本。 "]))
    result = await rewriter.rewrite("样本量为20例。", "zh", [], 2)
    assert result.output == "本实验纳入20例样本。"
    assert result.segments[0].attempts[0].audit.blocked
    assert result.segments[0].status == "rewritten"
    assert result.requires_review
    assert result.detector_status == "not_run"


async def test_all_unsafe_candidates_retain_source_not_fake_success():
    result = await Rewriter(SequenceModel(["只有40例。"])).rewrite("只有20例。", "zh", [], 1)
    assert result.output == "只有20例。"
    assert result.status == "unchanged"
    assert result.segments[0].status == "retained"


async def test_structure_never_sent_and_separator_preserved():
    model = SequenceModel(["本次测试共用20个样本。"])
    result = await Rewriter(model).rewrite(
        "# 标题\r\n\r\n本次使用20个样本。\r\n\r\n```python\r\nx = 1\r\n```", "zh", [], 1
    )
    assert model.calls == ["本次使用20个样本。"]
    assert result.output == "# 标题\r\n\r\n本次测试共用20个样本。\r\n\r\n```python\r\nx = 1\r\n```"


async def test_failed_generation_preserved_and_not_completed():
    result = await Rewriter(SequenceModel([ModelError("inference failed")])).rewrite(
        "研究结论尚待验证。", "zh", [], 1
    )
    assert result.status == "failed"
    assert result.output == "研究结论尚待验证。"
    assert result.segments[0].attempts[0].error


async def test_english_rewrite_same_pipeline_and_hashes_bound_to_text():
    result = await Rewriter(SequenceModel(["We repeated the experiment 5 times."])).rewrite(
        "The experiment was repeated 5 times.", "en", [], 1
    )
    assert result.output == "We repeated the experiment 5 times."
    assert result.source_sha256 != result.output_sha256
    assert len(result.source_sha256) == 64


@pytest.mark.parametrize("candidates", [0, 4])
async def test_candidate_limits_before_inference(candidates):
    with pytest.raises(ValueError):
        await Rewriter(SequenceModel([])).rewrite("Text", "en", [], candidates)


async def test_protected_term_not_in_a_paragraph_does_not_block_other_paragraphs():
    result = await Rewriter(SequenceModel(["BM25适用于检索。", "本实验重复5次。"])).rewrite(
        "BM25用于检索。\n\n实验重复5次。", "zh", ["BM25"], 1
    )
    assert result.segments[1].status == "rewritten"


async def test_truncated_paragraph_does_not_cancel_later_paragraph():
    model = SequenceModel([ModelError("model_output_truncated"), "本实验重复5次。"])
    result = await Rewriter(model).rewrite("研究尚待验证。\n\n实验重复5次。", candidates=1)
    assert result.output == "研究尚待验证。\n\n本实验重复5次。"
    assert result.status == "partial"
    assert [segment.status for segment in result.segments] == ["failed", "rewritten"]
    assert len(model.calls) == 2


async def test_single_truncation_is_failed_not_unchanged():
    result = await Rewriter(SequenceModel([ModelError("model_output_truncated")])).rewrite(
        "研究尚待验证。", candidates=1
    )
    assert result.status == "failed"


async def test_service_failure_does_not_repeat_timeout_for_every_paragraph():
    model = SequenceModel([ModelError("model_unavailable_or_invalid_response")])
    result = await Rewriter(model).rewrite("研究尚待验证。\n\n实验重复5次。", candidates=1)
    assert result.status == "failed"
    assert len(model.calls) == 1
