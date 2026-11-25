#!/usr/bin/env python3
"""Deterministic validation for the JG Energy Manager repository."""

from __future__ import annotations

import compileall
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "custom_components" / "jg_energy_manager"
EXPECTED_VERSION = "0.3.3"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {err}")


def main() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "RELEASE_CANDIDATE.md",
        ROOT / "hacs.json",
        ROOT / "publish.ps1",
        ROOT / "scripts" / "verify_release_archive.py",
        ROOT / "tests" / "test_released_archive_home_assistant.py",
        DOMAIN_DIR / "manifest.json",
        DOMAIN_DIR / "__init__.py",
        DOMAIN_DIR / "config_flow.py",
        DOMAIN_DIR / "coordinator.py",
        DOMAIN_DIR / "actuator.py",
        DOMAIN_DIR / "session.py",
        DOMAIN_DIR / "runtime.py",
        DOMAIN_DIR / "input_snapshot.py",
        DOMAIN_DIR / "planner.py",
        DOMAIN_DIR / "strings.json",
        DOMAIN_DIR / "translations" / "en.json",
        DOMAIN_DIR / "brand" / "icon.png",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail(f"Missing required files: {', '.join(missing)}")

    manifest = load_json(DOMAIN_DIR / "manifest.json")
    hacs = load_json(ROOT / "hacs.json")
    strings = load_json(DOMAIN_DIR / "strings.json")
    translations = load_json(DOMAIN_DIR / "translations" / "en.json")
    if manifest.get("domain") != "jg_energy_manager":
        fail("manifest domain must be jg_energy_manager")
    if manifest.get("version") != EXPECTED_VERSION:
        fail(f"manifest version must be {EXPECTED_VERSION}")
    if hacs.get("filename") != "jg_energy_manager.zip":
        fail("hacs.json filename must match the release asset")
    if strings != translations:
        fail("strings.json and translations/en.json have drifted")

    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if not re.search(rf'^version\s*=\s*"{re.escape(EXPECTED_VERSION)}"$', project, re.MULTILINE):
        fail("pyproject version does not match manifest")

    if not compileall.compile_dir(DOMAIN_DIR, quiet=1, force=True):
        fail("Python compilation failed")

    forbidden_names = {
        ".env",
        "secrets.yaml",
        "secrets.yml",
        "credentials.json",
        "config_entry-smappee_ev.json",
        "tariff.pdf",
    }
    forbidden_suffixes = {".pem", ".pfx", ".p12", ".key", ".token", ".secret"}
    blocked = []
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".venv", "dist", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.is_file() and (path.name in forbidden_names or path.suffix.lower() in forbidden_suffixes):
            blocked.append(str(path.relative_to(ROOT)))
    if blocked:
        fail(f"Forbidden sensitive files present: {', '.join(blocked)}")

    secret_patterns = {
        "GitHub token": re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
        "OpenAI token": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    leaks: list[str] = []
    for path in ROOT.rglob("*"):
        if any(part in {".git", ".venv", "dist", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml", ".py", ".ps1", ".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in secret_patterns.items():
            if pattern.search(text):
                leaks.append(f"{path.relative_to(ROOT)} ({label})")
    if leaks:
        fail(f"Possible embedded secrets found: {', '.join(leaks)}")

    print(f"Validated JG Energy Manager {EXPECTED_VERSION}")


if __name__ == "__main__":
    main()
