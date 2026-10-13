import json
from importlib.resources import files

from paper_rewrite.settings import default_language


def test_edition_default_is_explicit_and_packaged(monkeypatch):
    monkeypatch.delenv("PAPER_LANGUAGE", raising=False)
    edition = json.loads(files("paper_rewrite").joinpath("edition.json").read_text())
    assert edition["default_language"] in {"zh", "en"}
    assert default_language() == edition["default_language"]


def test_valid_language_override(monkeypatch):
    monkeypatch.setenv("PAPER_LANGUAGE", "en")
    assert default_language() == "en"
    monkeypatch.setenv("PAPER_LANGUAGE", "zh")
    assert default_language() == "zh"


def test_invalid_override_uses_edition_default(monkeypatch):
    monkeypatch.setenv("PAPER_LANGUAGE", "wrong")
    edition = json.loads(files("paper_rewrite").joinpath("edition.json").read_text())
    assert default_language() == edition["default_language"]
