"""Contract tests for Interface I5 (Prerequisite Checker).

Subprocess calls (gcc --version, qemu --version, git describe --tags)
and shutil.which are mocked so the tests are deterministic on any
machine; the EDK II tree itself is a real fixture directory.
"""

import sys
import types
from unittest import mock

import pytest

from bios_build_gui import prereq
from bios_build_gui.prereq import CheckResult, check
from bios_build_gui.settings import Settings


def _completed(returncode=0, stdout=""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _fake_run_factory(*, git_tag="edk2-stable202608", gcc="12.3.0", qemu="11.1.3"):
    """Return a fake subprocess.run dispatching on the command."""

    def fake_run(command, **kwargs):
        if command[:2] == ["git", "describe"]:
            if git_tag is None:
                return _completed(returncode=128, stdout="")
            return _completed(stdout=git_tag + "\n")
        if command[:2] == ["gcc", "--version"]:
            return _completed(stdout=f"gcc (Ubuntu {gcc}-1ubuntu1~22.04) {gcc}\n")
        if command[0].endswith("qemu-system-x86_64") and command[1:] == ["--version"]:
            return _completed(stdout=f"QEMU emulator version {qemu}\n")
        raise AssertionError(f"unexpected command: {command}")

    return fake_run


def _fake_which_factory(*, gcc=True, qemu=True):
    def fake_which(name):
        if name == "gcc" and gcc:
            return "/usr/bin/gcc"
        if name == "qemu-system-x86_64" and qemu:
            return "/usr/bin/qemu-system-x86_64"
        return None

    return fake_which


@pytest.fixture
def settings(edk2_tree):
    return Settings(edk2_path=str(edk2_tree), qemu_path="")


@pytest.fixture
def all_ok_mocks(monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory())
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    return monkeypatch


def test_each_result_has_five_fields(settings, all_ok_mocks):
    results = check(settings)
    assert [r.name for r in results] == [
        "EDK II tree",
        "BaseTools binaries",
        "GCC",
        "QEMU",
        "Python/PyQt",
    ]
    for result in results:
        assert isinstance(result, CheckResult)
        assert result.status in ("ok", "missing", "mismatched")
        assert isinstance(result.expected_version, str) and result.expected_version
        assert isinstance(result.fix_hint, str)


def test_all_ok(settings, all_ok_mocks):
    results = check(settings)
    assert [r.status for r in results] == ["ok"] * 5
    by_name = {r.name: r for r in results}
    assert by_name["EDK II tree"].found_version == "edk2-stable202608"
    assert by_name["GCC"].found_version == "12.3.0"
    assert by_name["QEMU"].found_version == "11.1.3"
    assert "3." in by_name["Python/PyQt"].found_version


def test_missing_edk2_tree(all_ok_mocks):
    results = check(Settings(edk2_path="/does/not/exist", qemu_path=""))
    edk2 = results[0]
    assert edk2.status == "missing"
    assert edk2.found_version is None
    assert "/does/not/exist" in edk2.fix_hint


def test_edk2_tree_missing_files(tmp_path, all_ok_mocks):
    tree = tmp_path / "edk2"
    tree.mkdir()
    results = check(Settings(edk2_path=str(tree), qemu_path=""))
    assert results[0].status == "missing"
    assert "edksetup.sh" in results[0].fix_hint


def test_edk2_wrong_tag(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory(git_tag="edk2-stable202502"))
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    results = check(settings)
    edk2 = results[0]
    assert edk2.status == "mismatched"
    assert edk2.found_version == "edk2-stable202502"
    assert edk2.expected_version == "edk2-stable202608"
    assert "edk2-stable202502" in edk2.fix_hint


def test_edk2_tarball_no_git_tags(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory(git_tag=None))
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    results = check(settings)
    edk2 = results[0]
    assert edk2.status == "mismatched"
    assert edk2.found_version is None
    assert "git checkout" in edk2.fix_hint


def test_basetools_missing(edk2_tree, all_ok_mocks):
    (edk2_tree / "BaseTools" / "BinWrappers" / "PosixLike" / "build").unlink()
    results = check(Settings(edk2_path=str(edk2_tree), qemu_path=""))
    basetools = results[1]
    assert basetools.status == "missing"
    assert "make -C BaseTools" in basetools.fix_hint


def test_gcc_missing(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory())
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory(gcc=False))
    results = check(settings)
    gcc = results[2]
    assert gcc.status == "missing"
    assert "gcc" in gcc.fix_hint.lower()


def test_gcc_wrong_major(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory(gcc="13.3.0"))
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    results = check(settings)
    gcc = results[2]
    assert gcc.status == "mismatched"
    assert gcc.found_version == "13.3.0"
    assert gcc.expected_version == "12"
    assert "13.3.0" in gcc.fix_hint and "12" in gcc.fix_hint


def test_qemu_missing(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory())
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory(qemu=False))
    results = check(settings)
    qemu = results[3]
    assert qemu.status == "missing"
    assert "QEMU" in qemu.fix_hint


def test_qemu_wrong_version(settings, monkeypatch):
    monkeypatch.setattr(prereq.subprocess, "run", _fake_run_factory(qemu="11.1.0"))
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    results = check(settings)
    qemu = results[3]
    assert qemu.status == "mismatched"
    assert qemu.found_version == "11.1.0"
    assert qemu.expected_version == "11.1.3"


def test_qemu_path_from_settings(edk2_tree, tmp_path, monkeypatch):
    # The configured path must exist (a configured path that does not
    # exist is reported missing); the version output is mocked.
    fake_qemu = tmp_path / "qemu-system-x86_64"
    fake_qemu.write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        if command[:2] == ["git", "describe"]:
            return _completed(stdout="edk2-stable202608\n")
        if command[:2] == ["gcc", "--version"]:
            return _completed(stdout="gcc (Ubuntu 12.3.0-1ubuntu1~22.04) 12.3.0\n")
        if command == [str(fake_qemu), "--version"]:
            return _completed(stdout="QEMU emulator version 11.1.3\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(prereq.subprocess, "run", fake_run)
    monkeypatch.setattr(prereq.shutil, "which", _fake_which_factory())
    results = check(Settings(edk2_path=str(edk2_tree), qemu_path=str(fake_qemu)))
    assert results[3].status == "ok"


def test_python_below_minimum(settings, all_ok_mocks, monkeypatch):
    import collections

    VersionInfo = collections.namedtuple(
        "VersionInfo", ["major", "minor", "micro", "releaselevel", "serial"]
    )
    monkeypatch.setattr(sys, "version_info", VersionInfo(3, 9, 18, "final", 0))
    results = check(settings)
    python = results[4]
    assert python.status == "mismatched"
    assert "3.9" in python.found_version


def test_pyqt_missing(settings, all_ok_mocks, monkeypatch):
    # Block both the package and the already-cached submodule, or the
    # from-import would resolve from the sys.modules cache.
    blocked = {"PyQt6": None, "PyQt6.QtCore": None}
    with mock.patch.dict(sys.modules, blocked):
        results = check(settings)
    python = results[4]
    assert python.status == "mismatched"
    assert "PyQt6 is not installed" in python.fix_hint


def test_check_result_fields():
    result = CheckResult(
        name="GCC",
        status="ok",
        found_version="12.3.0",
        expected_version="12",
        fix_hint="",
    )
    assert result.name == "GCC"
    assert result.status == "ok"
    assert result.found_version == "12.3.0"
    assert result.expected_version == "12"
    assert result.fix_hint == ""
