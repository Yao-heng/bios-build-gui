"""Contract tests for Interface I3 (Build Runner)."""

import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from bios_build_gui import build_runner
from bios_build_gui.build_runner import extract_error_block, run_build

DUMMY_OK = [sys.executable, "-u", "-c", "print('hello')"]
DUMMY_LINES = [
    sys.executable,
    "-u",
    "-c",
    "import sys\nfor i in range(5):\n    print(f'line {i}', flush=True)",
]
DUMMY_FAIL = [sys.executable, "-u", "-c", "import sys; sys.exit(3)"]
DUMMY_SLEEP = [sys.executable, "-u", "-c", "import time; time.sleep(30)"]


@pytest.fixture
def fake_make_on_path(tmp_path, monkeypatch):
    """Place a fake `make` on PATH; return the marker file it records to."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    src = Path(__file__).parent / "fake_make.py"
    dest = bindir / "make"
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    marker = tmp_path / "make-calls.txt"
    monkeypatch.setenv("FAKE_MAKE_MARKER", str(marker))
    return marker


def test_exit_zero_returns_zero(tmp_path):
    seen = []
    rc = run_build(DUMMY_OK, tmp_path, tmp_path / "build.log", seen.append, None)
    assert rc == 0
    assert seen == ["hello\n"]
    assert (tmp_path / "build.log").read_text(encoding="utf-8") == "hello\n"


def test_nonzero_exit_returns_that_code(tmp_path):
    rc = run_build(DUMMY_FAIL, tmp_path, tmp_path / "build.log", lambda line: None, None)
    assert rc == 3


def test_output_lines_reach_callback_in_order(tmp_path):
    seen = []
    run_build(DUMMY_LINES, tmp_path, tmp_path / "build.log", seen.append, None)
    assert seen == [f"line {i}\n" for i in range(5)]


def test_full_output_written_to_log(tmp_path):
    log = tmp_path / "build.log"
    run_build(DUMMY_LINES, tmp_path, log, lambda line: None, None)
    assert log.read_text(encoding="utf-8") == "".join(f"line {i}\n" for i in range(5))


def test_command_invoked_without_shell(tmp_path):
    with mock.patch.object(build_runner.subprocess, "Popen", wraps=subprocess.Popen) as popen_mock:
        run_build(DUMMY_OK, tmp_path, tmp_path / "build.log", lambda line: None, None)
    assert popen_mock.called
    assert popen_mock.call_args.kwargs["shell"] is False


def test_environment_variables_set(tmp_path):
    seen = []
    script = (
        "import os, sys; "
        "print(os.environ.get('WORKSPACE', '')); "
        "print(os.environ.get('PACKAGES_PATH', '')); "
        "print(os.environ.get('EDK_TOOLS_PATH', '')); "
        "print(os.environ.get('CONF_PATH', '')); "
        "print(os.environ.get('PYTHON_COMMAND', '')); "
        "print(os.environ.get('PATH', ''))"
    )
    run_build(
        [sys.executable, "-u", "-c", script],
        tmp_path,
        tmp_path / "build.log",
        seen.append,
        None,
    )
    workdir = str(tmp_path.resolve())
    assert seen[0].strip() == workdir
    assert seen[1].strip() == workdir
    assert seen[2].strip() == os.path.join(workdir, "BaseTools")
    assert seen[3].strip() == os.path.join(workdir, "Conf")
    assert seen[4].strip() == sys.executable
    assert seen[5].strip().split(os.pathsep)[0] == os.path.join(
        workdir, "BaseTools", "BinWrappers", "PosixLike"
    )


def test_cancellation_terminates_subprocess(tmp_path):
    cancel_event = threading.Event()
    timer = threading.Timer(0.5, cancel_event.set)
    timer.start()
    start = time.monotonic()
    try:
        rc = run_build(
            DUMMY_SLEEP, tmp_path, tmp_path / "build.log", lambda line: None, cancel_event
        )
    finally:
        timer.cancel()
    assert time.monotonic() - start < 5
    assert rc is not None and rc != 0


def test_extract_error_block_returns_error_with_context(tmp_path):
    lines = [f"ordinary line {i}" for i in range(50)]
    lines[29] = "OvmfPkg/Sec/SecMain.c(123): error C2084: something broke"
    log = tmp_path / "build.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    block = extract_error_block(log)
    assert "OvmfPkg/Sec/SecMain.c(123): error C2084: something broke" in block
    # 20 lines before + the error line + 5 lines after, 1-based numbering.
    assert "10: ordinary line 9" in block
    assert "30: OvmfPkg/Sec/SecMain.c(123): error C2084: something broke" in block
    assert "35: ordinary line 34" in block
    assert "9: ordinary line 8" not in block
    assert "36: ordinary line 35" not in block


def test_extract_error_block_falls_back_to_last_30_lines(tmp_path):
    lines = [f"line {i}" for i in range(50)]
    log = tmp_path / "build.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    block = extract_error_block(log)
    assert "21: line 20" in block
    assert "50: line 49" in block
    assert "20: line 19" not in block


def test_extract_error_block_matches_failed(tmp_path):
    log = tmp_path / "build.log"
    log.write_text("building...\nFailed to build module X\n", encoding="utf-8")
    assert "Failed to build module X" in extract_error_block(log)


def test_extract_error_block_empty_log(tmp_path):
    log = tmp_path / "build.log"
    log.write_text("", encoding="utf-8")
    assert extract_error_block(log) == ""


def test_prebuild_builds_basetools_when_missing(edk2_tree, fake_make_on_path):
    (edk2_tree / "BaseTools" / "BinWrappers" / "PosixLike" / "build").unlink()
    seen = []
    rc = run_build(DUMMY_OK, edk2_tree, edk2_tree / "build.log", seen.append, None)
    assert rc == 0
    assert "hello\n" in seen
    assert fake_make_on_path.exists()
    assert "make -C BaseTools" in fake_make_on_path.read_text(encoding="utf-8")


def test_prebuild_skipped_when_basetools_present(edk2_tree, fake_make_on_path):
    rc = run_build(DUMMY_OK, edk2_tree, edk2_tree / "build.log", lambda line: None, None)
    assert rc == 0
    assert not fake_make_on_path.exists()


def test_prebuild_failure_returns_make_exit_code(edk2_tree, fake_make_on_path, monkeypatch):
    (edk2_tree / "BaseTools" / "BinWrappers" / "PosixLike" / "build").unlink()
    monkeypatch.setenv("FAKE_MAKE_EXIT", "3")
    log = edk2_tree / "build.log"
    rc = run_build(DUMMY_OK, edk2_tree, log, lambda line: None, None)
    assert rc == 3
    assert "BaseTools build failed" in log.read_text(encoding="utf-8")
    assert "hello" not in log.read_text(encoding="utf-8")


def test_no_prebuild_when_not_edk2_workspace(tmp_path, fake_make_on_path):
    rc = run_build(DUMMY_OK, tmp_path, tmp_path / "build.log", lambda line: None, None)
    assert rc == 0
    assert not fake_make_on_path.exists()


def test_old_logs_pruned_to_last_10(tmp_path):
    for i in range(12):
        old = tmp_path / f"build-2026010{i}.log"
        old.write_text("old\n", encoding="utf-8")
        os.utime(old, (1000000 + i, 1000000 + i))
    run_build(DUMMY_OK, tmp_path, tmp_path / "build-new.log", lambda line: None, None)
    remaining = sorted(p.name for p in tmp_path.glob("build-*.log"))
    assert len(remaining) == 10
    assert "build-20260100.log" not in remaining
    assert "build-20260101.log" not in remaining
