"""Settings store.

The tool's settings live in ``<project>/settings.json`` (in the tool's
repo root; gitignored — it contains machine-specific paths). Format::

    {"edk2_path": "<path>", "qemu_path": "<path>"}

``qemu_path`` is optional: when the key is absent from the file, it
defaults to the QEMU found on PATH. An explicitly empty ``qemu_path``
is preserved as-is (round-trip safe).

``load_settings`` / ``save_settings`` accept an optional ``path`` so tests
can use a temporary file; the default is the project's ``settings.json``.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

SETTINGS_FILENAME = "settings.json"
DEFAULT_QEMU_BINARY = "qemu-system-x86_64"


@dataclass
class Settings:
    """Machine-specific paths. Empty means "not configured"."""

    edk2_path: str = ""
    qemu_path: str = ""


def _default_settings_path() -> Path:
    # <project> is the repo root: the parent of the bios_build_gui package.
    return Path(__file__).resolve().parent.parent / SETTINGS_FILENAME


def load_settings(path=None) -> Settings:
    """Load settings; returns defaults when the file is missing or corrupt."""
    path = Path(path) if path is not None else _default_settings_path()
    if not path.exists():
        return Settings(edk2_path="", qemu_path=shutil.which(DEFAULT_QEMU_BINARY) or "")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Settings(edk2_path="", qemu_path=shutil.which(DEFAULT_QEMU_BINARY) or "")
    if not isinstance(data, dict):
        return Settings(edk2_path="", qemu_path=shutil.which(DEFAULT_QEMU_BINARY) or "")
    edk2_path = data.get("edk2_path", "")
    if not isinstance(edk2_path, str):
        edk2_path = ""
    qemu_path = data.get("qemu_path", None)
    if qemu_path is None:
        qemu_path = shutil.which(DEFAULT_QEMU_BINARY) or ""
    elif not isinstance(qemu_path, str):
        qemu_path = ""
    return Settings(edk2_path=edk2_path, qemu_path=qemu_path)


def save_settings(settings: Settings, path=None) -> None:
    """Save settings (parent directories are created)."""
    path = Path(path) if path is not None else _default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"edk2_path": settings.edk2_path, "qemu_path": settings.qemu_path}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
