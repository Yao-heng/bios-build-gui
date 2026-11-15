"""Contract tests for Interface I4 v2 (Boot Verifier).

The fake QEMU (tests/fake_qemu.py) stands in for qemu-system-x86_64 on
PATH; no real QEMU is needed. A live-QEMU test is an integration test
on the implementation machine, not a unit test.

I4 v2 (see the boot-verify-menu-drive design doc): ``verify_boot``
returns ``(verdict, output)`` where ``verdict`` is ``"booted"``,
``"boot_to_shell_fail"``, or ``"not_booted"``. The verifier drives the
Boot Manager menu (space, Down, Enter) via QEMU's stdin to reach the
shell, and appends an interaction trace to the output.
"""

import threading
import time

import pytest

from bios_build_gui import boot_verify
from bios_build_gui.boot_verify import (
    VERDICT_BOOTED,
    VERDICT_BOOT_TO_SHELL_FAIL,
    VERDICT_NOT_BOOTED,
    get_qemu_binary,
    set_qemu_binary,
    verify_boot,
)

TRACE_MARKER = "--- Boot verify trace (verifier-added, not serial output) ---"


@pytest.fixture(autouse=True)
def reset_qemu_binary():
    yield
    set_qemu_binary(None)


def test_booted_when_shell_prompt_printed(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "prompt")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert verdict == VERDICT_BOOTED
    assert "Shell>" in output


def test_not_booted_when_no_prompt(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "no-prompt")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert verdict == VERDICT_NOT_BOOTED
    assert "Booting..." in output


def test_not_booted_on_timeout(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "hang")
    start = time.monotonic()
    verdict, _output = verify_boot(tmp_path / "OVMF.fd", timeout=1)
    elapsed = time.monotonic() - start
    assert verdict == VERDICT_NOT_BOOTED
    assert elapsed < 5


def test_slow_prompt_within_timeout(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "slow")
    monkeypatch.setenv("FAKE_QEMU_DELAY", "0.5")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert verdict == VERDICT_BOOTED
    assert "Shell>" in output


def test_cancellation_kills_qemu(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "hang")
    cancel_event = threading.Event()
    timer = threading.Timer(0.5, cancel_event.set)
    timer.start()
    start = time.monotonic()
    try:
        verdict, _output = verify_boot(tmp_path / "OVMF.fd", timeout=30, cancel_event=cancel_event)
    finally:
        timer.cancel()
    assert verdict == VERDICT_NOT_BOOTED
    assert time.monotonic() - start < 5


def test_menu_drive_reaches_shell(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "menu")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert verdict == VERDICT_BOOTED
    assert "Shell>" in output
    # The fake's menu mode prints Shell> with no trailing newline; the
    # chunk reader must still deliver it (the old line reader could
    # not). The trace is the operation record CUJ 1 requires.
    assert TRACE_MARKER in output
    assert "BdsDxe prompt detected" in output
    assert "menu detected" in output
    assert "sent Down" in output
    assert "sent Enter" in output
    assert "Shell> observed" in output
    assert "verdict: booted" in output


def test_menu_no_shell_reports_boot_to_shell_fail(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "menu-no-shell")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=3)
    assert verdict == VERDICT_BOOT_TO_SHELL_FAIL
    assert TRACE_MARKER in output
    assert "menu detected" in output
    assert "verdict: boot_to_shell_fail" in output


def test_prompt_only_no_menu_reports_boot_to_shell_fail(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "prompt-only")
    verdict, output = verify_boot(tmp_path / "OVMF.fd", timeout=3)
    assert verdict == VERDICT_BOOT_TO_SHELL_FAIL
    assert TRACE_MARKER in output
    assert "menu not detected" in output
    assert "verdict: boot_to_shell_fail" in output


def test_qemu_command_uses_kvm_when_available(monkeypatch):
    monkeypatch.setattr(boot_verify, "_kvm_available", lambda: True)
    command = boot_verify._qemu_command("/path/to/OVMF.fd")
    assert command[0] == "qemu-system-x86_64"
    assert "-accel" in command and "kvm" in command
    assert command[-2:] == ["-accel", "kvm"]
    assert "if=pflash,format=raw,unit=0,file=/path/to/OVMF.fd,readonly=on" in command
    assert "-display" in command and "none" in command
    assert "-serial" in command and "stdio" in command


def test_qemu_command_falls_back_to_tcg_without_kvm(monkeypatch):
    monkeypatch.setattr(boot_verify, "_kvm_available", lambda: False)
    command = boot_verify._qemu_command("/path/to/OVMF.fd")
    assert "-accel" not in command


def test_set_qemu_binary_override():
    set_qemu_binary("/opt/qemu/bin/qemu-system-x86_64")
    assert get_qemu_binary() == "/opt/qemu/bin/qemu-system-x86_64"
    set_qemu_binary(None)
    assert get_qemu_binary() == "qemu-system-x86_64"
