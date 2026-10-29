"""Build and validate a Plesk release ZIP without secrets or local data.

From the Vault-Backend directory:
    python .\\scripts\\make_plesk_release.py
"""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_INCLUDES = (
    "Dockerfile",
    "docker-compose.prod.yml",
    "entrypoint.sh",
    "manage.py",
    "requirements.txt",
    ".dockerignore",
    ".env.example",
    ".env.plesk.example",
    "apps",
    "config",
    "PLESK_PANEL_DEPLOY_GUIDE.md",
)

SAFE_ENV_TEMPLATES = {".env.example", ".env.plesk.example"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "staticfiles",
    "media",
    ".idea",
    ".vscode",
}
SKIP_NAMES = {"db.sqlite3", ".ds_store", "id_rsa", "id_ed25519"}
SKIP_SUFFIXES = {
    ".zip",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
    ".pyc",
    ".pyo",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


def is_private_or_generated(relative: Path) -> bool:
    parts = tuple(part.lower() for part in relative.parts)
    name = parts[-1]
    return (
        any(part in SKIP_DIRS for part in parts[:-1])
        or name in SKIP_NAMES
        or (name.startswith(".env") and name not in SAFE_ENV_TEMPLATES)
        or Path(name).suffix.lower() in SKIP_SUFFIXES
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--include",
        nargs="+",
        default=DEFAULT_INCLUDES,
        help="Files/directories to place at the ZIP root",
    )
    args = parser.parse_args()

    root = Path(os.path.abspath(args.root))
    if not root.is_dir():
        parser.error(f"Project directory does not exist: {root}")

    release_name = f"vault-api-plesk-release-{datetime.now():%Y%m%d-%H%M%S}.zip"
    output = Path(os.path.abspath(args.output or root / release_name))
    if not output.parent.is_dir():
        parser.error("Output directory does not exist")
    if output.exists():
        parser.error(f"Output already exists; choose a new release name: {output}")

    members: dict[str, Path] = {}
    for item in args.include:
        raw_source = root / item
        if raw_source.is_symlink():
            parser.error(f"Symlink not allowed in release: {item}")
        source = Path(os.path.abspath(raw_source))
        if not source.exists():
            parser.error(f"Include does not exist: {item}")
        if not source.is_relative_to(root):
            parser.error(f"Include escapes project directory: {item}")

        candidates = source.rglob("*") if source.is_dir() else (source,)
        for path in candidates:
            if not path.is_file():
                continue
            if path.is_symlink():
                parser.error(f"Symlink not allowed in release: {path}")
            relative = path.relative_to(root)
            if is_private_or_generated(relative):
                if source.is_file():
                    parser.error(f"Private/generated file explicitly included: {relative}")
                continue
            members[relative.as_posix()] = path

    required_files = {
        "Dockerfile",
        "docker-compose.prod.yml",
        "entrypoint.sh",
        "manage.py",
        "requirements.txt",
        ".dockerignore",
        ".env.example",
        ".env.plesk.example",
        "PLESK_PANEL_DEPLOY_GUIDE.md",
    }
    missing = sorted(required_files - members.keys())
    if missing:
        parser.error(f"Required files missing from release: {', '.join(missing)}")
    if not members:
        parser.error("Nothing to package")

    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for archive_name, path in sorted(members.items()):
            archive.write(path, archive_name)

    with ZipFile(output) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or any(
            is_private_or_generated(Path(name)) for name in names
        ):
            output.unlink(missing_ok=True)
            raise SystemExit("Release validation failed; ZIP removed")

    print(f"Created {output} ({len(names)} files; no .env or generated database)")


if __name__ == "__main__":
    main()
