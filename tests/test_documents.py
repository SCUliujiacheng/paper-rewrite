import pytest

from paper_rewrite.documents import split_document


def test_keeps_exact_crlf_and_blank_line_separators():
    text = "\r\n\r\n第一段。\r\n第二行。\r\n \r\n\r\n另一段。\r\n"
    segments = split_document(text)
    assert "".join(segment.text + segment.separator for segment in segments) == text
    prose = [segment for segment in segments if segment.rewriteable]
    assert [segment.text for segment in prose] == ["第一段。\r\n第二行。", "另一段。"]
    assert prose[0].separator == "\r\n \r\n\r\n"
    assert prose[1].separator == "\r\n"


def test_keeps_headings_tables_fences_and_references_out_of_model():
    text = (
        "# 方法\n正文段落。\n\n| 组 | 值 |\n| --- | --- |\n| A | 5 |\n\n"
        "```python\nx = 1\n\nprint(x)\n```\n\n## 参考文献\n"
        "[1] Wang (2023). Paper.\n\n[2] Li (2024). Paper.\n"
    )
    segments = split_document(text)
    assert "".join(segment.text + segment.separator for segment in segments) == text
    assert [segment.text for segment in segments if segment.rewriteable] == ["正文段落。"]
    assert [segment.id for segment in segments] == list(range(len(segments)))
    assert all(
        segment.model_dump()["rewriteable"] is False
        for segment in segments
        if "x =" in segment.text
    )


@pytest.mark.parametrize("text", ["", " \r\n\t"])
def test_rejects_documents_without_content(text):
    with pytest.raises(ValueError):
        split_document(text)


def test_rejects_oversized_document():
    with pytest.raises(ValueError):
        split_document("字" * 12001)


def test_rejects_long_prose_paragraph():
    with pytest.raises(ValueError):
        split_document("字" * 1001)


def test_accepts_long_code_block_without_splitting_or_rewriting():
    text = "```text\n" + "a" * 1100 + "\n```"
    segments = split_document(text)
    assert len(segments) == 1
    assert not segments[0].rewriteable
    assert segments[0].text == text


def test_limits_prose_paragraph_count():
    with pytest.raises(ValueError):
        split_document("\n\n".join(["正文"] * 61))
    assert len(split_document("\n\n".join(["正文"] * 60))) == 60


def test_accepts_boundary_length_paragraph():
    assert split_document("字" * 1000)[0].rewriteable


def test_protects_unclosed_fence_until_document_end():
    text = "前言。\n\n~~~python\nx=1\n\n更多代码"
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == ["前言。"]
    assert "".join(segment.text + segment.separator for segment in segments) == text


def test_protects_setext_heading_and_plain_reference_heading():
    text = "方法\n====\n正文。\n\nReferences\n\nSmith, J. (2023). Title."
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == ["正文。"]
    assert "".join(segment.text + segment.separator for segment in segments) == text


def test_protects_indented_code_and_markdown_structural_blocks():
    text = (
        "正文。\n\n    x = 1\n    print(x)\n\n---\n\n"
        "[paper]: https://example.org\n\n[1] Wang, J. (2023). Title."
    )
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == ["正文。"]
    assert "".join(segment.text + segment.separator for segment in segments) == text


def test_does_not_treat_underscore_separated_prose_as_a_code_block():
    text = "这是含有 A_B 变量的正文。"
    assert split_document(text)[0].rewriteable


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_protects_blockquoted_fence_with_blank_code_lines(newline):
    text = newline.join(
        [
            "普通正文。",
            "",
            "> ```python",
            "> result = first + second",
            ">",
            "> print(result)",
            "> ```",
            "",
            "后续正文。",
            "",
        ]
    )
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == [
        "普通正文。",
        "后续正文。",
    ]
    assert "".join(segment.text + segment.separator for segment in segments) == text
    code = [segment for segment in segments if "result =" in segment.text]
    assert len(code) == 1
    assert not code[0].rewriteable
    assert "> print(result)" in code[0].text


@pytest.mark.parametrize(
    "container",
    [
        "- ```python\n  result = first + second\n\n  print(result)\n  ```",
        "1. Example\n\n   ```python\n   result = first + second\n\n   print(result)\n   ```",
        "- Example\n  - Nested example\n\n    ~~~python\n    result = first + second"
        "\n\n    print(result)\n    ~~~",
    ],
)
def test_preserves_list_containing_code_fences_as_a_whole_block(container):
    text = "普通正文。\n\n" + container + "\n \n\n后续正文。\n"
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == [
        "普通正文。",
        "后续正文。",
    ]
    code = [segment for segment in segments if "result =" in segment.text]
    assert len(code) == 1
    assert code[0].text == container
    assert not code[0].rewriteable
    assert code[0].separator == "\n \n\n"
    assert "".join(segment.text + segment.separator for segment in segments) == text


@pytest.mark.parametrize(
    "heading",
    [
        "## 1. 参考文献",
        "## 6. References",
        "# 2) Bibliography #",
        "3.2 References",
        "4、引用文献",
        "## 六、参考文献",
    ],
)
def test_numbered_reference_heading_protects_all_reference_body(heading):
    text = (
        "正文段落。\r\n\r\n" + heading + "\r\n\r\n"
        "Smith, J. (2023). First paper.\r\n \r\n"
        "Wang, J. (2024). Second paper.\r\n\r\nAppendix text.\r\n"
    )
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == ["正文段落。"]
    assert "".join(segment.text + segment.separator for segment in segments) == text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("首段。\n单换行。\n\n末段。", ["首段。\n单换行。", "末段。"]),
        (
            "\r\nFirst paragraph.\r\n \r\nSecond paragraph.\r\n",
            ["First paragraph.", "Second paragraph."],
        ),
        ("研究中的1. References仅是表达示例。", ["研究中的1. References仅是表达示例。"]),
    ],
)
def test_container_protection_does_not_change_ordinary_paragraph_reconstruction(text, expected):
    segments = split_document(text)
    assert [segment.text for segment in segments if segment.rewriteable] == expected
    assert "".join(segment.text + segment.separator for segment in segments) == text
