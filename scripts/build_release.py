#!/usr/bin/env python3
"""Build HACS and manual-install release archives reproducibly."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "custom_components" / "jg_energy_manager"
DIST = ROOT / "dist"


def add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        archive.write(path, (prefix / path.relative_to(source)).as_posix())


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_package.py")], check=True)
    version = json.loads((DOMAIN / "manifest.json").read_text(encoding="utf-8"))["version"]
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir()

    hacs_zip = DIST / "jg_energy_manager.zip"
    with zipfile.ZipFile(hacs_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        add_tree(archive, DOMAIN, Path())

    manual_zip = DIST / f"jg-energy-manager-v{version}.zip"
    with zipfile.ZipFile(manual_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        add_tree(archive, DOMAIN, Path("custom_components/jg_energy_manager"))
        for name in ("README.md", "CHANGELOG.md", "SECURITY.md"):
            archive.write(ROOT / name, name)

    checksums = DIST / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in (hacs_zip, manual_zip)),
        encoding="ascii",
    )
    print(f"Built {hacs_zip.relative_to(ROOT)}")
    print(f"Built {manual_zip.relative_to(ROOT)}")
    print(f"Built {checksums.relative_to(ROOT)}")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_release_archive.py")],
        check=True,
    )


if __name__ == "__main__":
    main()
