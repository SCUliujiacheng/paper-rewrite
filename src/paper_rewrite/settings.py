"""The two repositories share code; only their packaged default language differs."""

import json
import os
from importlib.resources import files


def default_language() -> str:
    override = os.getenv("PAPER_LANGUAGE")
    if override in {"zh", "en"}:
        return override
    edition = json.loads(files("paper_rewrite").joinpath("edition.json").read_text())
    return "en" if edition.get("default_language") == "en" else "zh"
