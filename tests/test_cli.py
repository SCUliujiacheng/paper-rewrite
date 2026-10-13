import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "paper_rewrite.cli", *map(str, args)],
        capture_output=True,
        encoding="utf-8",
    )


def test_cli_check_exports_real_findings_without_model(tmp_path):
    source = tmp_path / "source.txt"
    candidate = tmp_path / "candidate.txt"
    source.write_text("实验重复5次。", encoding="utf-8")
    candidate.write_text("实验重复7次。", encoding="utf-8")
    result = run_cli("check", source, candidate)
    assert result.returncode == 2
    assert json.loads(result.stdout)["blocked"] is True


def test_cli_check_requires_review_even_if_no_obvious_difference(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("研究仍有局限。", encoding="utf-8")
    result = run_cli("check", source, source)
    assert result.returncode == 0
    assert json.loads(result.stdout)["requires_review"] is True


def test_cli_unavailable_model_does_not_write_fake_success(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("实验重复5次。", encoding="utf-8")
    output = tmp_path / "output.txt"
    result = run_cli("rewrite", source, "-o", output, "--model-url", "http://127.0.0.1:1")
    assert result.returncode == 3
    assert not output.exists()


def test_cli_never_overwrites_original_input(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    result = run_cli("rewrite", source, "-o", source, "--model-url", "http://127.0.0.1:1")
    assert result.returncode != 0
    assert source.read_text(encoding="utf-8") == "original"
