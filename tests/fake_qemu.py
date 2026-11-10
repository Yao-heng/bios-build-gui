#!/usr/bin/env python3
"""Fake qemu-system-x86_64 for boot-verify tests.

Modes (env FAKE_QEMU_MODE):

* ``prompt`` (default): print the UEFI shell prompt and exit 0.
* ``no-prompt``: exit 0 without printing the prompt.
* ``slow``: sleep FAKE_QEMU_DELAY seconds (default 2), then print the prompt.
* ``hang``: sleep until killed.

If ``--version`` is in argv, print a version line and exit 0 (the version
comes from FAKE_QEMU_VERSION, default ``11.1.3``).
"""

import os
import sys
import time


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
