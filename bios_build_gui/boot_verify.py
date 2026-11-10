"""Boot Verifier (Interface I4).

Launches QEMU with the produced OVMF.fd as a pflash drive, captures
serial output, and returns ``booted`` (true when the UEFI shell prompt
is observed within the timeout) plus the captured output. The verifier
returns as soon as ``Shell>`` is observed; it does not wait out the
full timeout. QEMU is killed after the verdict, and also on
cancellation or GUI close.

The QEMU binary is ``qemu-system-x86_64`` by default; the caller (the
GUI, from settings) can override it with ``set_qemu_binary``. KVM
acceleration is used when ``/dev/kvm`` is present and accessible,
otherwise the verifier falls back to TCG (software emulation).
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time

SHELL_PROMPT = "Shell>"
DEFAULT_TIMEOUT = 60

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
    """Boot ``image_path`` in QEMU; return ``(booted, output)``.

    ``timeout`` is in seconds (default 60). ``cancel_event`` is a
    ``threading.Event`` (or None). A successful build with a failed boot
    verify is a separate verdict from the build verdict; this function
    only reports whether the shell prompt appeared.
    """
    proc = subprocess.Popen(
        _qemu_command(str(image_path)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        errors="replace",
    )
    lines: list[str] = []
    output_queue: queue.Queue = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                output_queue.put(line)
        except ValueError:
            pass
        finally:
            output_queue.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    deadline = time.monotonic() + timeout
    booted = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            item = output_queue.get(timeout=min(0.05, remaining))
        except queue.Empty:
            if cancel_event is not None and cancel_event.is_set():
                break
            continue
        if item is None:
            break  # QEMU exited.
        lines.append(item)
        if SHELL_PROMPT in item:
            booted = True
            break
        if cancel_event is not None and cancel_event.is_set():
            break
    _terminate(proc)
    # Drain lines that were already queued (best effort).
    while True:
        try:
            item = output_queue.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        lines.append(item)
    return booted, "".join(lines)


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
