"""Contract tests for Interface I4 (Boot Verifier).

The fake QEMU (tests/fake_qemu.py) stands in for qemu-system-x86_64 on
PATH; no real QEMU is needed. A live-QEMU test is an integration test
on the implementation machine, not a unit test.
"""

import threading
import time

import pytest

from bios_build_gui import boot_verify
from bios_build_gui.boot_verify import get_qemu_binary, set_qemu_binary, verify_boot


@pytest.fixture(autouse=True)
def reset_qemu_binary():
    yield
    set_qemu_binary(None)


def test_booted_when_shell_prompt_printed(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "prompt")
    booted, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert booted is True
    assert "Shell>" in output


def test_not_booted_when_no_prompt(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "no-prompt")
    booted, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert booted is False
    assert "Booting..." in output


def test_not_booted_on_timeout(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "hang")
    start = time.monotonic()
    booted, _output = verify_boot(tmp_path / "OVMF.fd", timeout=1)
    elapsed = time.monotonic() - start
    assert booted is False
    assert elapsed < 5


def test_slow_prompt_within_timeout(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "slow")
    monkeypatch.setenv("FAKE_QEMU_DELAY", "0.5")
    booted, output = verify_boot(tmp_path / "OVMF.fd", timeout=5)
    assert booted is True
    assert "Shell>" in output


def test_cancellation_kills_qemu(tmp_path, fake_qemu_on_path, monkeypatch):
    monkeypatch.setenv("FAKE_QEMU_MODE", "hang")
    cancel_event = threading.Event()
    timer = threading.Timer(0.5, cancel_event.set)
    timer.start()
    start = time.monotonic()
    try:
        booted, _output = verify_boot(tmp_path / "OVMF.fd", timeout=30, cancel_event=cancel_event)
    finally:
        timer.cancel()
    assert booted is False
    assert time.monotonic() - start < 5


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
