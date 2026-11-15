#!/usr/bin/env python3
"""Fake qemu-system-x86_64 for boot-verify tests.

Modes (env FAKE_QEMU_MODE):

* ``prompt`` (default): print the UEFI shell prompt and exit 0.
* ``no-prompt``: exit 0 without printing the prompt.
* ``slow``: sleep FAKE_QEMU_DELAY seconds (default 2), then print the prompt.
* ``hang``: sleep until killed.
* ``menu``: print the BdsDxe prompt, read one byte from stdin, print the
  Boot Manager menu, read bytes until Down (ESC [ B) followed by Enter
  (``\\r``) is seen, then print ``Shell>`` with no trailing newline and
  exit 0. Models the real OVMF menu interaction (see the
  boot-verify-menu-drive design doc).
* ``menu-no-shell``: same as ``menu`` up to the menu, but after
  receiving Down + Enter it never prints ``Shell>`` (sleeps until
  killed). Drives the ``boot_to_shell_fail`` verdict.
* ``prompt-only``: print the BdsDxe prompt and sleep until killed
  (no menu, no shell). Drives ``boot_to_shell_fail`` via the
  menu-not-detected path.

The fake reads stdin with ``sys.stdin.buffer.read(1)`` (byte reads — a
line-based read would block on the space keypress, which has no
newline) and flushes stdout after each print (stdout to a pipe is
block-buffered).

If ``--version`` is in argv, print a version line and exit 0 (the version
comes from FAKE_QEMU_VERSION, default ``11.1.3``).
"""

import os
import sys
import time

BDS_PROMPT = (
    "No bootable option or device was found. BdsDxe: Press any key to enter the Boot Manager Menu."
)
MENU_TITLE = "Please select boot device:"
MENU_ENTRIES = ["EFI Firmware Setup", "EFI Internal Shell"]
MENU_FOOTER = [
    "Use the arrow keys to move the selection.",
    "Press ENTER to select, ESC to exit.",
]


def _read_byte():
    """Read one byte from stdin (b"" on EOF)."""
    return sys.stdin.buffer.read(1)


def _drive_menu():
    """Print the BdsDxe prompt and the menu; wait for Down + Enter.

    Returns True when Down followed by Enter was seen, False when stdin
    closed before that.
    """
    print(BDS_PROMPT, flush=True)
    _read_byte()  # any key enters the menu
    print(MENU_TITLE, flush=True)
    for entry in MENU_ENTRIES:
        print(entry, flush=True)
    for line in MENU_FOOTER:
        print(line, flush=True)
    seen_down = False
    while True:
        byte = _read_byte()
        if not byte:
            return False
        if byte == b"\x1b":
            # Down arrow is ESC [ B; read the next two bytes to confirm.
            rest = _read_byte() + _read_byte()
            if rest == b"[B":
                seen_down = True
            continue
        if byte == b"\r" and seen_down:
            return True
        if byte == b"\r":
            seen_down = False


def main():
    if "--version" in sys.argv:
        print(f"QEMU emulator version {os.environ.get('FAKE_QEMU_VERSION', '11.1.3')}")
        return 0
    mode = os.environ.get("FAKE_QEMU_MODE", "prompt")
    if mode == "prompt":
        print("UEFI Interactive Shell v2.2")
        print("Shell> ")
        sys.stdout.flush()
        return 0
    if mode == "no-prompt":
        print("Booting...")
        sys.stdout.flush()
        return 0
    if mode == "slow":
        time.sleep(float(os.environ.get("FAKE_QEMU_DELAY", "2")))
        print("Shell> ")
        sys.stdout.flush()
        return 0
    if mode == "hang":
        time.sleep(3600)
        return 0
    if mode == "menu":
        if _drive_menu():
            sys.stdout.write("Shell>")
            sys.stdout.flush()
        return 0
    if mode == "menu-no-shell":
        if _drive_menu():
            time.sleep(3600)
        return 0
    if mode == "prompt-only":
        print(BDS_PROMPT, flush=True)
        time.sleep(3600)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
