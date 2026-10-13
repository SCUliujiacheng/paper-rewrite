"""Exercise release boundaries with a real temporary Git inventory."""

import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


def load_builder():
    script = Path(__file__).parents[1] / "scripts" / "build_bundle.py"
    assert script.is_file(), "Release builder must exist"
    spec = importlib.util.spec_from_file_location("bundle_builder", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, text in {
        "LICENSE": "test license",
        "NOTICE": "test attribution",
        "README.md": "install instructions",
        "pyproject.toml": "[project]\nname='toy'",
        "uv.lock": "version = 1",
        "src/paper_rewrite/__init__.py": "# original application",
        "scripts/example.py": "# project script",
        "docs/setup.md": "setup",
        "data/smoke.jsonl": '{"synthetic":true}',
    }.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    (root / "web/dist/assets").mkdir(parents=True)
    (root / "web/dist/index.html").write_text('<script src="/assets/main.js"></script>')
    (root / "web/dist/assets/main.js").write_text("console.log('built application')")
    return root


def output_path(root, name="paper-rewrite.zip"):
    return root / ".local" / "release" / name


def test_bundle_contains_tracked_source_built_frontend_and_licenses_only(release_repo):
    builder = load_builder()
    for name in [".env", "private-draft.txt", "weights.gguf", ".local/private.txt"]:
        file = release_repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("private untracked contents")
    output = output_path(release_repo)
    builder.build_bundle(release_repo, output)
    with zipfile.ZipFile(output) as bundle:
        names = bundle.namelist()
        assert "LICENSE" in names and "NOTICE" in names
        assert "src/paper_rewrite/__init__.py" in names
        assert "web/dist/index.html" in names and "web/dist/assets/main.js" in names
        assert ".env" not in names and "private-draft.txt" not in names
        assert "weights.gguf" not in names
        assert not any(name.startswith((".git/", ".local/")) for name in names)
        manifest = json.loads(bundle.read("bundle-manifest.json"))
        assert str(release_repo) not in json.dumps(manifest)
        entries = {entry["path"]: entry for entry in manifest["files"]}
        assert entries["LICENSE"]["sha256"] == hashlib.sha256(b"test license").hexdigest()
        assert entries["LICENSE"]["size"] == 12
    checksum = output.with_suffix(".zip.sha256").read_text(encoding="ascii")
    assert checksum == hashlib.sha256(output.read_bytes()).hexdigest() + "  paper-rewrite.zip\n"


def test_equal_inputs_produce_byte_identical_zip_despite_file_timestamps(release_repo):
    builder = load_builder()
    first, second = output_path(release_repo, "first.zip"), output_path(release_repo, "second.zip")
    builder.build_bundle(release_repo, first)
    tracked = release_repo / "LICENSE"
    import os

    os.utime(tracked, (1700000000, 1700000000))
    builder.build_bundle(release_repo, second)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("existing", ["zip", "checksum"])
def test_existing_release_or_checksum_is_never_overwritten(release_repo, existing):
    builder = load_builder()
    output = output_path(release_repo)
    target = output if existing == "zip" else output.with_suffix(".zip.sha256")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing artifact")
    with pytest.raises(FileExistsError):
        builder.build_bundle(release_repo, output)
    assert target.read_bytes() == b"existing artifact"


def test_missing_built_index_refuses_to_make_release(release_repo):
    builder = load_builder()
    (release_repo / "web/dist/index.html").unlink()
    output = output_path(release_repo)
    with pytest.raises(ValueError, match="index.html"):
        builder.build_bundle(release_repo, output)
    assert not output.exists()


@pytest.mark.parametrize("name", [".env", "config/.env.production", "config/live.env"])
def test_even_tracked_sensitive_environment_files_refuse_release(release_repo, name):
    builder = load_builder()
    target = release_repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SECRET=value")
    subprocess.run(["git", "-C", str(release_repo), "add", name], check=True)
    with pytest.raises(ValueError, match="Sensitive"):
        builder.build_bundle(release_repo, output_path(release_repo))


def test_tracked_model_and_local_artifacts_are_excluded(release_repo):
    builder = load_builder()
    for name in ["toy.gguf", "model.safetensors", ".local/token.txt"]:
        target = release_repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("not source")
        subprocess.run(["git", "-C", str(release_repo), "add", name], check=True)
    output = output_path(release_repo)
    builder.build_bundle(release_repo, output)
    with zipfile.ZipFile(output) as bundle:
        assert "toy.gguf" not in bundle.namelist()
        assert "model.safetensors" not in bundle.namelist()
        assert ".local/token.txt" not in bundle.namelist()


def test_frontend_symlink_outside_source_refuses_release(release_repo, tmp_path):
    builder = load_builder()
    private = tmp_path / "private.txt"
    private.write_text("private")
    link = release_repo / "web/dist/assets/private.txt"
    try:
        link.symlink_to(private)
    except OSError as error:
        pytest.skip(f"Host does not permit test symlink: {error}")
    with pytest.raises(ValueError, match="Unsafe"):
        builder.build_bundle(release_repo, output_path(release_repo))


def test_incomplete_tracked_inventory_refuses_release(release_repo):
    builder = load_builder()
    subprocess.run(["git", "-C", str(release_repo), "rm", "--cached", "LICENSE"], check=True)
    with pytest.raises(ValueError, match="LICENSE"):
        builder.build_bundle(release_repo, output_path(release_repo))


def test_output_must_stay_inside_local_release_directory(release_repo, tmp_path):
    builder = load_builder()
    with pytest.raises(ValueError, match=".local/release"):
        builder.build_bundle(release_repo, tmp_path / "outside.zip")


@pytest.mark.parametrize("name", ["../private.txt", "/absolute.txt", "C:/private.txt", "a\\b.txt"])
def test_unsafe_inventory_paths_are_rejected_before_reading(release_repo, monkeypatch, name):
    builder = load_builder()
    monkeypatch.setattr(builder, "_inventory", lambda root: [name])
    with pytest.raises(ValueError, match="Unsafe"):
        builder.build_bundle(release_repo, output_path(release_repo))


def test_resolved_source_outside_root_is_rejected(release_repo, tmp_path, monkeypatch):
    builder = load_builder()
    private = tmp_path / "private.txt"
    private.write_text("private")
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == release_repo / "LICENSE":
            return private
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match="Unsafe"):
        builder.build_bundle(release_repo, output_path(release_repo))


def test_local_directory_is_excluded_regardless_of_filename_case(release_repo):
    builder = load_builder()
    target = release_repo / ".LOCAL/private.txt"
    target.parent.mkdir()
    target.write_text("private runtime data")
    subprocess.run(["git", "-C", str(release_repo), "add", ".LOCAL/private.txt"], check=True)
    output = output_path(release_repo)
    builder.build_bundle(release_repo, output)
    with zipfile.ZipFile(output) as bundle:
        assert ".LOCAL/private.txt" not in bundle.namelist()
