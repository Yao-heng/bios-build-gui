"""Prerequisite Checker (Interface I5).

``check(settings)`` returns a list of ``CheckResult`` (one per item:
EDK II tree, BaseTools binaries, GCC, QEMU, Python/PyQt), each with
``name``, ``status`` (``ok`` | ``missing`` | ``mismatched``),
``found_version`` (string or None), ``expected_version`` (string) and
``fix_hint`` (what to install or change). One function per check item,
so a new prerequisite can be added without touching the others.

"Mismatched" is uniform: the found version does not satisfy the pinned
requirement (EDK II/QEMU: exact match; GCC: same major; Python/PyQt6:
at or above the pinned minimum). A newer version that does not satisfy
the pin is ``mismatched``; the fix hint names the expected and found
versions and the upgrade procedure.

Pinned versions (from the design's Pinned versions table): EDK II
``edk2-stable202608``, GCC major ``12``, QEMU ``11.1.3``, Python
minimum ``3.10``, PyQt6 minimum ``6.0.0`` (the PyQt6 major version; the
exact version validated at implementation is PyQt6 6.12.0, recorded in
``requirements.txt``).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PINNED_EDK2_TAG = "edk2-stable202608"
PINNED_GCC_MAJOR = 12
PINNED_QEMU_VERSION = "11.1.3"
PINNED_PYTHON_MINIMUM = (3, 10)
PINNED_PYQT6_MINIMUM = "6.0.0"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass
class CheckResult:
    """One prerequisite check result."""

    name: str
    status: str  # ok | missing | mismatched
    found_version: str | None
    expected_version: str
    fix_hint: str


def check(settings) -> list[CheckResult]:
    """Check every prerequisite against the settings; return the results."""
    return [
        _check_edk2_tree(settings),
        _check_basetools(settings),
        _check_gcc(),
        _check_qemu(settings),
        _check_python_pyqt(),
    ]


def _check_edk2_tree(settings):
    name = "EDK II tree"
    expected = PINNED_EDK2_TAG
    path = Path(settings.edk2_path) if settings.edk2_path else None
    if path is None or not path.is_dir():
        return CheckResult(
            name,
            "missing",
            None,
            expected,
            f"EDK II tree not found at {settings.edk2_path!r}. "
            f"Set the EDK II path in Settings to a checkout of tag {expected}.",
        )
    missing = []
    if not (path / "edksetup.sh").is_file():
        missing.append("edksetup.sh")
    if not (path / "OvmfPkg" / "OvmfPkgX64.dsc").is_file():
        missing.append("OvmfPkg/OvmfPkgX64.dsc")
    if missing:
        return CheckResult(
            name,
            "missing",
            None,
            expected,
            f"EDK II tree at {path} is missing: {', '.join(missing)}. "
            f"Use a checkout of tag {expected}.",
        )
    tag = _git_describe_tags(path)
    if not tag:
        return CheckResult(
            name,
            "mismatched",
            None,
            expected,
            f"Could not determine the EDK II version (no git tags in {path}). "
            f"Use a git checkout of tag {expected}.",
        )
    if tag != expected:
        return CheckResult(
            name,
            "mismatched",
            tag,
            expected,
            f"EDK II tag is {tag}, expected {expected}. "
            f"Check out tag {expected} (upgrading a pin is an explicit, tested event).",
        )
    return CheckResult(name, "ok", tag, expected, "")


def _git_describe_tags(path):
    try:
        proc = subprocess.run(
            ["git", "describe", "--tags"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    tag = proc.stdout.strip()
    return tag or None


def _check_basetools(settings):
    name = "BaseTools binaries"
    expected = "built"
    path = Path(settings.edk2_path) if settings.edk2_path else None
    wrapper = (
        path / "BaseTools" / "BinWrappers" / "PosixLike" / "build" if path is not None else None
    )
    if wrapper is not None and wrapper.is_file():
        return CheckResult(name, "ok", "built", expected, "")
    return CheckResult(
        name,
        "missing",
        None,
        expected,
        "Run `make -C BaseTools` in the EDK II tree (after sourcing `edksetup.sh`).",
    )


def _check_gcc():
    name = "GCC"
    expected = str(PINNED_GCC_MAJOR)
    if shutil.which("gcc") is None:
        return CheckResult(
            name,
            "missing",
            None,
            expected,
            "gcc was not found on PATH. Install GCC 12 (e.g. `apt install gcc-12`) "
            "and ensure `gcc` on PATH is version 12.",
        )
    first_line = _first_line_of(["gcc", "--version"])
    match = _VERSION_RE.search(first_line)
    version = match.group(0) if match else (first_line or None)
    major = int(match.group(1)) if match else None
    if major is None:
        return CheckResult(
            name,
            "mismatched",
            version,
            expected,
            f"Could not parse the GCC version from {first_line!r}. Install GCC 12.",
        )
    if major != PINNED_GCC_MAJOR:
        return CheckResult(
            name,
            "mismatched",
            version,
            expected,
            f"GCC version is {version} (major {major}), expected major "
            f"{PINNED_GCC_MAJOR}. Install GCC 12 (e.g. `apt install gcc-12`) "
            "and ensure `gcc` on PATH is version 12.",
        )
    return CheckResult(name, "ok", version, expected, "")


def _check_qemu(settings):
    name = "QEMU"
    expected = PINNED_QEMU_VERSION
    binary = (settings.qemu_path or "").strip() or "qemu-system-x86_64"
    if Path(binary).is_absolute():
        resolved = binary if Path(binary).exists() else None
    else:
        resolved = shutil.which(binary)
    if resolved is None:
        return CheckResult(
            name,
            "missing",
            None,
            expected,
            f"QEMU ({binary}) was not found. Install QEMU {expected} and ensure "
            "qemu-system-x86_64 is on PATH (or set its path in Settings).",
        )
    first_line = _first_line_of([resolved, "--version"])
    match = _VERSION_RE.search(first_line)
    version = match.group(0) if match else (first_line or None)
    if version is None:
        return CheckResult(
            name,
            "mismatched",
            None,
            expected,
            f"Could not parse the QEMU version. Install QEMU {expected}.",
        )
    if version != expected:
        return CheckResult(
            name,
            "mismatched",
            version,
            expected,
            f"QEMU version is {version}, expected {expected}. "
            f"Install QEMU {expected} (upgrading a pin is an explicit, tested event).",
        )
    return CheckResult(name, "ok", version, expected, "")


def _check_python_pyqt():
    name = "Python/PyQt"
    expected = f"Python >={_format_version(PINNED_PYTHON_MINIMUM)}, PyQt6 >={PINNED_PYQT6_MINIMUM}"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info[:2] < PINNED_PYTHON_MINIMUM:
        return CheckResult(
            name,
            "mismatched",
            py_version,
            expected,
            f"Python {py_version} is below the minimum "
            f"{_format_version(PINNED_PYTHON_MINIMUM)}. Use Python 3.10 or newer.",
        )
    try:
        from PyQt6.QtCore import QT_VERSION_STR

        qt_version = QT_VERSION_STR
    except ImportError:
        qt_version = None
    if qt_version is None:
        return CheckResult(
            name,
            "mismatched",
            py_version,
            expected,
            "PyQt6 is not installed. Install it with `pip install -r requirements.txt`.",
        )
    if _version_tuple(qt_version) < _version_tuple(PINNED_PYQT6_MINIMUM):
        return CheckResult(
            name,
            "mismatched",
            f"Python {py_version}, PyQt6 {qt_version}",
            expected,
            f"PyQt6 {qt_version} is below the minimum {PINNED_PYQT6_MINIMUM}. Upgrade PyQt6.",
        )
    return CheckResult(name, "ok", f"Python {py_version}, PyQt6 {qt_version}", expected, "")


def _first_line_of(command):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if not proc.stdout:
        return ""
    return proc.stdout.splitlines()[0]


def _version_tuple(version):
    parts = []
    for piece in str(version).split("."):
        digits = re.match(r"\d+", piece)
        parts.append(int(digits.group(0)) if digits else 0)
    return tuple(parts)


def _format_version(version_tuple):
    return ".".join(str(part) for part in version_tuple)
