"""Build a reviewed source ZIP plus prebuilt frontend, without running build/install tools."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

REQUIRED = {"LICENSE", "NOTICE", "README.md", "pyproject.toml", "uv.lock"}
EXCLUDED_DIRS = {
    ".git",
    ".local",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
MODEL_SUFFIXES = {".gguf", ".safetensors", ".pt", ".pth", ".ckpt", ".onnx", ".bin"}
SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials.json", "secrets.json", "token.json"}


def _relative_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or PureWindowsPath(name).drive
        or "\\" in name
        or ":" in name
        or any(ord(char) < 32 for char in name)
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError("Unsafe archive path")
    return path.as_posix()


def _sensitive(name: str) -> bool:
    parts = [part.lower() for part in PurePosixPath(name).parts]
    return any(
        part == ".env"
        or part.startswith(".env.")
        or part.endswith(".env")
        or ".env." in part
        or part in SECRET_NAMES
        or Path(part).suffix in {".pem", ".key"}
        for part in parts
    )


def _excluded(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool({part.lower() for part in path.parts} & EXCLUDED_DIRS)
        or path.suffix.lower() in MODEL_SUFFIXES
    )


def _read_source(root: Path, name: str) -> bytes:
    target = root / name
    try:
        resolved = target.resolve(strict=True)
    except OSError:
        raise ValueError(f"Missing source file: {name}") from None
    if not resolved.is_relative_to(root):
        raise ValueError(f"Unsafe source path: {name}")
    # Reject links in every path component, including links that happen to point inside.
    current = root
    for part in PurePosixPath(name).parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"Unsafe linked source path: {name}")
    if not target.is_file():
        raise ValueError(f"Unsafe non-file source entry: {name}")
    return target.read_bytes()


def _inventory(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        check=True,
        capture_output=True,
    )
    return [name.decode("utf-8") for name in result.stdout.split(b"\0") if name]


def build_bundle(root: str | Path, output: str | Path) -> Path:
    root = Path(root).resolve(strict=True)
    output = Path(output)
    if not output.is_absolute():
        output = root / output
    release_dir = (root / ".local/release").resolve()
    if (
        not release_dir.is_relative_to(root)
        or not output.resolve().is_relative_to(release_dir)
        or output.suffix.lower() != ".zip"
    ):
        raise ValueError("Output must be a ZIP inside .local/release")
    if any(char in output.name for char in "\r\n"):
        raise ValueError("Unsafe release filename")
    checksum = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or output.is_symlink() or checksum.exists() or checksum.is_symlink():
        raise FileExistsError("Release ZIP or checksum already exists")

    sources: dict[str, bytes] = {}
    for item in _inventory(root):
        name = _relative_name(item)
        if _excluded(name) or name.startswith("web/dist/"):
            continue
        if _sensitive(name):
            raise ValueError(f"Sensitive tracked filename: {name}")
        if name == "bundle-manifest.json":
            raise ValueError("Reserved bundle-manifest.json already tracked")
        sources[name] = _read_source(root, name)
    missing = sorted(REQUIRED - sources.keys())
    if missing:
        raise ValueError("Required files must be tracked: " + ", ".join(missing))
    if not any(name.startswith("src/") for name in sources):
        raise ValueError("Required application source must be tracked")

    frontend = root / "web/dist"
    if not (frontend / "index.html").is_file():
        raise ValueError("Build web/dist/index.html before packaging")
    for file in frontend.rglob("*"):
        name = _relative_name(file.relative_to(root).as_posix())
        if file.is_symlink() or file.is_junction() or not file.resolve().is_relative_to(root):
            raise ValueError(f"Unsafe frontend path: {name}")
        if file.is_dir():
            continue
        if _sensitive(name):
            raise ValueError(f"Sensitive frontend filename: {name}")
        if not _excluded(name):
            sources[name] = _read_source(root, name)
    # Reading index through _read_source also validates linked parent directories.
    if "web/dist/index.html" not in sources:
        raise ValueError("Unsafe or missing web/dist/index.html")

    manifest = {
        "format": 1,
        "kind": "source-with-prebuilt-frontend",
        "files": [
            {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(sources.items())
        ],
    }
    sources["bundle-manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation refuses overwrite, even if another process races the preflight check.
    with output.open("xb") as handle:
        with zipfile.ZipFile(handle, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(sources.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with checksum.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(f"{digest}  {output.name}\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="ZIP path inside .local/release")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        output = build_bundle(root, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Packaging failed: {error}\n")
    print(f"Created {output.name} and {output.name}.sha256")


if __name__ == "__main__":
    main()
