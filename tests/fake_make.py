#!/usr/bin/env python3
"""Fake ``make`` for build-runner pre-build tests.

Appends the invocation to FAKE_MAKE_MARKER and exits with FAKE_MAKE_EXIT
(default 0).
"""

import os
import sys


def main():
    marker = os.environ.get("FAKE_MAKE_MARKER")
    if marker:
        with open(marker, "a", encoding="utf-8") as f:
            f.write("make " + " ".join(sys.argv[1:]) + "\n")
    return int(os.environ.get("FAKE_MAKE_EXIT", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
