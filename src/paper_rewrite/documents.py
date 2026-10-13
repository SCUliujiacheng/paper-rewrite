"""Lossless Markdown/plain-text segmentation with explicit non-prose blocks."""

import re

from pydantic import BaseModel

MAX_DOCUMENT_CHARS = 12000
MAX_PARAGRAPHS = 60
MAX_PARAGRAPH_CHARS = 1000


class Segment(BaseModel):
    id: int
    text: str
    separator: str
    rewriteable: bool


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
_SETEXT = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
_REFERENCES = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*[.)、]?|[一二三四五六七八九十]+[、.])\s*)?"
    r"(?:参考文献|引用文献|references|bibliography)\s*[:：]?\s*$",
    re.IGNORECASE,
)
_QUOTE = re.compile(r"^ {0,3}>")
_LIST = re.compile(r"^( {0,3})(?:[-+*]|\d+[.)])\s+")
_LIST_FENCE = re.compile(r"^[ \t]*(?:(?:[-+*]|\d+[.)])\s+)?(?:>\s*)*(`{3,}|~{3,})")
_STRUCTURAL = re.compile(
    r"^(?: {4}|\t| {0,3}\[[^\]]+\]:| {0,3}\[\d+\]\s+)"
    r"|^ {0,3}(?:\*\s*){3,}$|^ {0,3}(?:-\s*){3,}$|^ {0,3}(?:_\s*){3,}$"
)


def _reference_heading(line: str) -> bool:
    heading = re.sub(r"^#{1,6}\s*", "", line.strip()).rstrip("# ")
    return _REFERENCES.fullmatch(heading) is not None


def _list_code_end(lines: list[str], start: int) -> int | None:
    """Protect a whole list containing fences, including its internal blank lines.

    This is deliberately conservative rather than a complete Markdown parser.
    A non-indented prose line ends the container; trailing blanks stay separators.
    """
    marker = _LIST.match(lines[start])
    if not marker:
        return None
    indent = len(marker.group(1))
    end = start + 1
    last_content = end
    has_fence = _LIST_FENCE.match(lines[start]) is not None
    while end < len(lines):
        line = lines[end]
        if not line.strip():
            end += 1
            continue
        following_marker = _LIST.match(line)
        leading = len(line) - len(line.lstrip(" \t"))
        if leading <= indent and not following_marker:
            break
        if following_marker and len(following_marker.group(1)) < indent:
            break
        has_fence |= _LIST_FENCE.match(line) is not None
        end += 1
        last_content = end
    return last_content if has_fence else None


def split_document(text: str) -> list[Segment]:
    """Return ordered blocks whose text+separator reconstruct the exact input.

    A references section conservatively remains protected through document end.
    Blank lines are separators; single line breaks within prose remain in its text.
    """
    if not text.strip():
        raise ValueError("Document must contain text / 文档不能为空")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise ValueError("Document exceeds 12000 characters / 文档超过12000字符")
    lines = text.splitlines(keepends=True)
    segments: list[Segment] = []
    references = False
    cursor = 0

    def add(raw: str, rewriteable: bool) -> None:
        ending = re.search(r"(?:\r\n|\n|\r)$", raw)
        separator = ending.group(0) if ending else ""
        content = raw[: -len(separator)] if separator else raw
        if rewriteable and len(content) > MAX_PARAGRAPH_CHARS:
            raise ValueError(
                "Paragraph exceeds 1000 characters; split it / 段落超过1000字符，请拆分"
            )
        segments.append(
            Segment(id=len(segments), text=content, separator=separator, rewriteable=rewriteable)
        )

    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip():
            if not segments:
                segments.append(Segment(id=0, text="", separator=line, rewriteable=False))
            else:
                segments[-1].separator += line
            cursor += 1
            continue
        if _reference_heading(line):
            references = True
        if references:
            end = cursor + 1
            while end < len(lines) and lines[end].strip():
                end += 1
            add("".join(lines[cursor:end]), False)
            cursor = end
            continue
        if _QUOTE.match(line):
            end = cursor + 1
            while end < len(lines):
                following = end
                while following < len(lines) and not lines[following].strip():
                    following += 1
                if following == len(lines) or not _QUOTE.match(lines[following]):
                    break
                end = following + 1
            add("".join(lines[cursor:end]), False)
            cursor = end
            continue
        list_end = _list_code_end(lines, cursor)
        if list_end is not None:
            add("".join(lines[cursor:list_end]), False)
            cursor = list_end
            continue
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            closing = re.compile(rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$")
            end = cursor + 1
            while end < len(lines):
                if closing.fullmatch(lines[end].rstrip("\r\n")):
                    end += 1
                    break
                end += 1
            add("".join(lines[cursor:end]), False)
            cursor = end
            continue
        if _HEADING.match(line):
            add(line, False)
            cursor += 1
            continue
        if cursor + 1 < len(lines) and _SETEXT.fullmatch(lines[cursor + 1].strip()):
            add(line + lines[cursor + 1], False)
            cursor += 2
            continue
        if "|" in line:
            end = cursor + 1
            while end < len(lines) and lines[end].strip() and "|" in lines[end]:
                end += 1
            add("".join(lines[cursor:end]), False)
            cursor = end
            continue
        if _STRUCTURAL.match(line.rstrip("\r\n")):
            end = cursor + 1
            while end < len(lines) and _STRUCTURAL.match(lines[end].rstrip("\r\n")):
                end += 1
            add("".join(lines[cursor:end]), False)
            cursor = end
            continue
        end = cursor + 1
        while end < len(lines) and lines[end].strip():
            following = lines[end]
            if (
                _HEADING.match(following)
                or _FENCE.match(following)
                or _QUOTE.match(following)
                or "|" in following
            ):
                break
            if _STRUCTURAL.match(following.rstrip("\r\n")):
                break
            if _reference_heading(following) or _list_code_end(lines, end) is not None:
                break
            if end + 1 < len(lines) and _SETEXT.fullmatch(lines[end + 1].strip()):
                break
            end += 1
        add("".join(lines[cursor:end]), True)
        cursor = end
    if sum(segment.rewriteable for segment in segments) > MAX_PARAGRAPHS:
        raise ValueError("Document exceeds 60 prose paragraphs / 文档超过60个正文段落")
    return segments
