"""Boot Verifier (Interface I4 v2).

Launches QEMU with the produced OVMF.fd as a pflash drive, drives the
Boot Manager menu to the UEFI shell, and returns ``(verdict, output)``.

``verdict`` is one of ``"booted"`` (the ``Shell>`` prompt was observed
within the timeout), ``"boot_to_shell_fail"`` (the firmware reached
BdsDxe / the Boot Manager but ``Shell>`` was not observed within the
timeout), or ``"not_booted"`` (the firmware never reached BdsDxe).
The verifier returns as soon as ``Shell>`` is observed; it does not
wait out the full timeout. QEMU is killed after the verdict, and also
on cancellation or GUI close. An interaction trace is appended to the
returned output after a marker line.

The QEMU binary is ``qemu-system-x86_64`` by default; the caller (the
GUI, from settings) can override it with ``set_qemu_binary``. KVM
acceleration is used when ``/dev/kvm`` is present and accessible,
otherwise the verifier falls back to TCG (software emulation).

The reader is chunk-based (``os.read``), not line-based: the real
``Shell>`` prompt has no trailing newline, so a line reader cannot
deliver it promptly. Popen runs in binary mode (``bufsize=0``,
``stdin=PIPE``); the reader decodes chunks as UTF-8 with
``errors="replace"``. Keypresses are written by the polling thread as
``bytes``.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time

SHELL_PROMPT = "Shell>"
BDS_PROMPT = "Press any key to enter the Boot Manager Menu"
MENU_TITLE = "Please select boot device:"
SHELL_ENTRY = "EFI Internal Shell"
DEFAULT_TIMEOUT = 30

VERDICT_BOOTED = "booted"
VERDICT_BOOT_TO_SHELL_FAIL = "boot_to_shell_fail"
VERDICT_NOT_BOOTED = "not_booted"

TRACE_MARKER = "--- Boot verify trace (verifier-added, not serial output) ---"

_KEY_SPACE = b" "
_KEY_DOWN = b"\x1b[B"
_KEY_ENTER = b"\r"

_qemu_binary = "qemu-system-x86_64"


def set_qemu_binary(path) -> None:
    """Override the QEMU binary (or None to reset to the default)."""
    global _qemu_binary
    _qemu_binary = path or "qemu-system-x86_64"


def get_qemu_binary() -> str:
    """Return the QEMU binary the verifier will launch."""
    return _qemu_binary


def _kvm_available() -> bool:
    return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)


def _qemu_command(image_path):
    command = [
        get_qemu_binary(),
        "-machine",
        "q35",
        "-m",
        "1024",
        "-drive",
        f"if=pflash,format=raw,unit=0,file={image_path},readonly=on",
        "-display",
        "none",
        "-serial",
        "stdio",
    ]
    if _kvm_available():
        command += ["-accel", "kvm"]
    return command


def verify_boot(image_path, timeout=DEFAULT_TIMEOUT, cancel_event=None):
    """Boot ``image_path`` in QEMU; return ``(verdict, output)``.

    ``timeout`` is in seconds (default 30). ``cancel_event`` is a
    ``threading.Event`` (or None). The verdict is ``"booted"`` when the
    UEFI shell prompt is observed, ``"boot_to_shell_fail"`` when the
    firmware reached the Boot Manager but the shell was not observed,
    and ``"not_booted"`` when the firmware never reached the Boot
    Manager. A successful build with a failed boot verify is a
    separate verdict from the build verdict.
    """
    start = time.monotonic()
    trace: list[str] = []

    def _record(event):
        trace.append(f"[+{time.monotonic() - start:.2f}s] {event}")

    proc = subprocess.Popen(
        _qemu_command(str(image_path)),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )
    _record("QEMU started")
    output_queue: queue.Queue = queue.Queue()

    def _reader():
        try:
            while True:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    break
                output_queue.put(chunk.decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            pass
        finally:
            output_queue.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    deadline = time.monotonic() + timeout
    accumulated = ""
    phase = "watching"
    bds_seen = False
    ansi_diag_recorded = False
    verdict = VERDICT_NOT_BOOTED

    def _send(data, event):
        """Write keypress bytes to QEMU's stdin; False if QEMU exited."""
        try:
            proc.stdin.write(data)
            proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            return False
        _record(event)
        return True

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            item = output_queue.get(timeout=min(0.05, remaining))
        except queue.Empty:
            pass  # No new chunk; run the phase checks on what we have.
        else:
            if item is None:
                break  # QEMU exited.
            accumulated += item
        if SHELL_PROMPT in accumulated:
            verdict = VERDICT_BOOTED
            _record("Shell> observed")
            break
        if cancel_event is not None and cancel_event.is_set():
            break
        # ANSI diagnostic: the short marker is present but the full
        # prompt substring never matched (an escape may split it).
        if not ansi_diag_recorded and "BdsDxe" in accumulated and BDS_PROMPT not in accumulated:
            ansi_diag_recorded = True
            _record("BdsDxe marker seen but prompt substring not matched (ANSI split?)")
        if phase == "watching" and BDS_PROMPT in accumulated:
            bds_seen = True
            _record("BdsDxe prompt detected")
            if not _send(_KEY_SPACE, "sent keypress to enter menu (space)"):
                break
            phase = "menu_entered"
        elif phase == "menu_entered" and MENU_TITLE in accumulated:
            _record("menu detected")
            if SHELL_ENTRY in accumulated:
                _record("EFI Internal Shell entry confirmed")
                if not _send(_KEY_DOWN, "sent Down"):
                    break
                if not _send(_KEY_ENTER, "sent Enter"):
                    break
            else:
                _record("EFI Internal Shell entry absent")
            phase = "menu_driven"
    # The verdict, by what was observed.
    if verdict != VERDICT_BOOTED:
        verdict = VERDICT_BOOT_TO_SHELL_FAIL if bds_seen else VERDICT_NOT_BOOTED
    if phase == "menu_entered":
        _record("menu not detected")
    _record(f"verdict: {verdict}")
    _terminate(proc)
    try:
        if proc.stdin is not None:
            proc.stdin.close()
    except (BrokenPipeError, ValueError, OSError):
        pass
    _record("QEMU terminated")
    # Drain chunks that were already queued (best effort).
    while True:
        try:
            item = output_queue.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        accumulated += item
    output = accumulated + "\n" + TRACE_MARKER + "\n" + "\n".join(trace) + "\n"
    return verdict, output


def _terminate(proc):
    try:
        proc.terminate()
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
        proc.wait()
