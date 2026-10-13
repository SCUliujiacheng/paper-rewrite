"""Conservative visible-fact checks, never a proof of semantic equivalence."""

import json
import re
from collections import Counter
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    before: str
    after: str


class AuditResult(BaseModel):
    blocked: bool
    issues: list[Issue] = Field(default_factory=list)
    requires_review: Literal[True] = True


_ARABIC = r"[+−-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?"
_CHINESE = r"[负負]?[零〇一二两兩三四五六七八九十百千万萬亿億]+(?:点[零〇一二三四五六七八九]+)?"
_UNITS = (
    r"(?:percent|per mille|milligrams?|kilograms?|grams?|milliliters?|liters?|"
    r"millimet(?:er|re)s?|centimet(?:er|re)s?|met(?:er|re)s?|seconds?|minutes?|hours?|"
    r"μg|µg|ug|mg|kg|g|ng|pg|mL|ml|μL|µL|uL|L|mm|cm|km|nm|μm|µm|m|"
    r"ms|s|min|h|Hz|kHz|MHz|GHz|Pa|kPa|MPa|W|kW|MW|V|mV|A|mA|mol|mmol|"
    r"°\s*[CF]|℃|℉|%|％|‰|毫克|千克|微克|纳克|皮克|克|毫升|微升|升|"
    r"毫米|厘米|微米|纳米|米|秒|分钟|小时|"
    r"年|月|天|日|岁|倍|次|个|例|名|组|项|人|种|篇|份|台|万元|元)"
    r"(?:[²³]|\^\d+)?(?:\s*/\s*[A-Za-zμµ]+(?:[²³]|\^\d+)?)?(?![A-Za-zμµ])"
)
_NUMBER = re.compile(
    rf"(?:{_ARABIC}|{_CHINESE})\s*(?:至|到|[–—~-])\s*"
    rf"(?:{_ARABIC}|{_CHINESE})(?:\s*{_UNITS})?"
    rf"|{_CHINESE}分之{_CHINESE}(?:\s*{_UNITS})?"
    rf"|{_ARABIC}(?:\s*{_UNITS})?|(?:百分之|千分之){_CHINESE}"
    rf"|{_CHINESE}\s*{_UNITS}|(?<=[为有共约是至第]){_CHINESE}"
)
_AUTHOR = r"[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)*"
_AUTHOR_GROUP = rf"{_AUTHOR}(?:\s*(?:&|and|,)\s*{_AUTHOR})*(?:\s+et\s+al\.)?"
_CITATIONS = re.compile(
    r"\[\s*\d+(?:\s*[,，;；–—-]\s*\d+)*\s*\]"
    r"|\[[^\]\n]*@[\w:.-]+[^\]\n]*\]"
    r"|[（(][^()（）\n]*\b(?:19|20)\d{2}[a-z]?[^()（）\n]*[）)]"
    rf"|\b{_AUTHOR_GROUP}\s*\((?:19|20)\d{{2}}[a-z]?\)"
    r"|[\u4e00-\u9fff]{2,6}(?:等)?\s*[（(](?:19|20)\d{2}[a-z]?[）)]"
)
_URL = re.compile(r"https?://[^\s<>\"'`\[\]（）)]+")
_LATEX = re.compile(
    r"(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$[^$\n]*?(?<!\\)\$"
    r"|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]"
    r"|\\begin\{([^}]+)\}[\s\S]*?\\end\{\1\}"
)
_CODE = re.compile(
    r"^\s*(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\s*\1\s*$|`+[^`\n]+`+",
    re.MULTILINE,
)
_CONTAINER_PREFIX = re.compile(r"^(?: {0,3}(?:>[ \t]?|(?:[-+*]|\d+[.)])[ \t]+))+")
_COMPARISON = re.compile(
    r">=|<=|==|!=|[><≥≤≠≈]"
    r"|不低于|不高于|不少于|不多于|大于|小于|高于|低于|超过|至少|至多|等于"
    r"|\b(?:greater than|less than|higher than|lower than|at least|at most|"
    r"more than|fewer than|no more than|no less than)\b",
    re.IGNORECASE,
)
_OPERAND = rf"(?:{_ARABIC}(?:\s*{_UNITS})?|[A-Za-z][A-Za-z0-9_]*(?:组|值|指标)?)"
_RELATION = re.compile(
    rf"{_OPERAND}\s*(?:(?:is|was|were)\s+)?(?:{_COMPARISON.pattern})\s*{_OPERAND}",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"没有|并非|未曾|未能|无法|不能|不|未|无|否认"
    r"|\b(?:not|no|never|neither|without|cannot|doesn't|didn't|isn't|aren't)\b",
    re.IGNORECASE,
)
_CERTAINTY = re.compile(
    r"可能|或许|也许|似乎|提示|推测|倾向|必然|一定|确定|证明|证实|显然"
    r"|\b(?:may|might|could|possibly|perhaps|suggests?|indicates?|likely|"
    r"certainly|definitely|always|proves?|demonstrates?|establishes?)\b",
    re.IGNORECASE,
)


def _tokens(pattern: re.Pattern[str], text: str, *, compact: bool = False) -> list[str]:
    values = [match.group(0) for match in pattern.finditer(text)]
    return [re.sub(r"\s+", "", value) for value in values] if compact else values


def _summary(tokens: list[str]) -> str:
    return json.dumps(dict(Counter(tokens)), ensure_ascii=False, sort_keys=True)


def _nested_code(text: str) -> list[str]:
    """Recognize container fences while preserving the original code verbatim."""
    lines = text.splitlines(keepends=True)
    blocks: list[str] = []
    cursor = 0
    while cursor < len(lines):
        line = lines[cursor]
        if not _CONTAINER_PREFIX.match(line):
            cursor += 1
            continue
        content = _CONTAINER_PREFIX.sub("", line).lstrip(" \t")
        opening = re.match(r"(`{3,}|~{3,})", content)
        if not opening:
            cursor += 1
            continue
        marker = opening.group(1)
        closing = re.compile(rf"{re.escape(marker[0])}{{{len(marker)},}}[ \t]*")
        end = cursor + 1
        while end < len(lines):
            content = _CONTAINER_PREFIX.sub("", lines[end]).lstrip(" \t").rstrip("\r\n")
            end += 1
            if closing.fullmatch(content):
                break
        blocks.append("".join(lines[cursor:end]))
        cursor = end
    return blocks


def _malformed(text: str) -> bool:
    stripped = text.strip()
    if not stripped or any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        return True
    if re.match(r"(?:<!doctype|<html\b|<body\b|<script\b)", stripped, re.IGNORECASE):
        return True
    if re.match(
        r"(?:here (?:is|are) (?:the |a )?(?:rewritten|revised)|"
        r"(?:改写|修改|润色)(?:后的)?(?:文本|版本|结果)[：:])",
        stripped,
        re.IGNORECASE,
    ):
        return True
    if stripped.startswith(("{", "[")):
        try:
            return isinstance(json.loads(stripped), (dict, list))
        except json.JSONDecodeError:
            return stripped.startswith('{"')
    return False


def audit(source: str, candidate: str, protected_terms: list[str] | None = None) -> AuditResult:
    """Compare occurrence counts of visible facts; warn about lexical polarity shifts.

    The rules intentionally reject some harmless notation changes. They cannot verify
    argument meaning, citation placement, or arbitrary entity/value associations.
    """
    issues: list[Issue] = []
    if not source.strip() or _malformed(candidate):
        issues.append(
            Issue(code="invalid_output", severity="error", before=source, after=candidate)
        )

    checks: list[tuple[str, Callable[[str], list[str]]]] = [
        ("numbers", lambda text: _tokens(_NUMBER, text, compact=True)),
        (
            "comparisons",
            lambda text: (
                _tokens(_COMPARISON, text, compact=True) + _tokens(_RELATION, text, compact=True)
            ),
        ),
        ("citations", lambda text: _tokens(_CITATIONS, text, compact=True)),
        ("urls", lambda text: [value.rstrip(".,;:，。；：！!") for value in _tokens(_URL, text)]),
        ("latex", lambda text: _tokens(_LATEX, text)),
        ("code", lambda text: _tokens(_CODE, text) + _nested_code(text)),
        (
            "protected_terms",
            lambda text: [
                term
                for term in dict.fromkeys(protected_terms or [])
                if term
                for _ in range(text.count(term))
            ],
        ),
    ]
    for code, extract in checks:
        before, after = extract(source), extract(candidate)
        if Counter(before) != Counter(after):
            issues.append(
                Issue(code=code, severity="error", before=_summary(before), after=_summary(after))
            )
    for code, pattern in (("negation", _NEGATION), ("certainty", _CERTAINTY)):
        before, after = _tokens(pattern, source.lower()), _tokens(pattern, candidate.lower())
        if Counter(before) != Counter(after):
            issues.append(
                Issue(code=code, severity="warning", before=_summary(before), after=_summary(after))
            )
    return AuditResult(blocked=any(issue.severity == "error" for issue in issues), issues=issues)
