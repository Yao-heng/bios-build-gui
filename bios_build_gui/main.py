"""GUI entry point.

Launched with the ``bios-build-gui`` console script (installed by
``pip install -e .``). There is no headless CLI in v1; headless
verification is driven by pytest integration tests that call the
Application Core functions directly.
"""

import sys

from PyQt6.QtWidgets import QApplication

from bios_build_gui.gui.main_window import MainWindow


def main():
    """Launch the GUI; return the application exit code."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
