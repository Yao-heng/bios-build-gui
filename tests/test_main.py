"""Smoke test for the GUI entry point (bios_build_gui.main).

The GUI cannot be instantiated on this machine (no display; the Qt
platform libraries are not installed), so the test launches main()
with a mocked GUI — exactly what the design specifies. The real GUI
is exercised in the E2E run on the user's PC (CUJ 1-4).
"""

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mocked_gui(monkeypatch):
    """Replace PyQt6.QtWidgets and the MainWindow with mocks."""
    app_class = MagicMock()
    app_instance = app_class.return_value
    app_instance.exec.return_value = 0
    window_class = MagicMock()
    window_instance = window_class.return_value

    qt_widgets = MagicMock()
    qt_widgets.QApplication = app_class
    monkeypatch.setitem(sys.modules, "PyQt6", MagicMock())
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qt_widgets)
    gui_module = MagicMock()
    gui_module.MainWindow = window_class
    monkeypatch.setitem(sys.modules, "bios_build_gui.gui.main_window", gui_module)
    return app_class, app_instance, window_class, window_instance


def test_main_launches_gui(mocked_gui):
    app_class, app_instance, window_class, window_instance = mocked_gui
    import bios_build_gui.main as main_mod

    assert main_mod.main() == 0
    app_class.assert_called_once()
    window_class.assert_called_once()
    window_instance.show.assert_called_once()
    app_instance.exec.assert_called_once()


@pytest.fixture
def real_main_window(monkeypatch):
    """Import the real main_window with PyQt6 stubbed.

    QThread and QMainWindow must be real (stub) classes because the
    module subclasses them; the other Qt names are MagicMocks. The
    verdict -> display-text mapping function itself does not use Qt.
    """
    qtcore = MagicMock()
    qtcore.QThread = type("QThread", (), {"__init__": lambda self, *a, **k: None})
    qtcore.pyqtSignal = lambda *a, **k: MagicMock()
    qtwidgets = MagicMock()
    qtwidgets.QMainWindow = type("QMainWindow", (), {"__init__": lambda self, *a, **k: None})
    monkeypatch.setitem(sys.modules, "PyQt6", MagicMock())
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    sys.modules.pop("bios_build_gui.gui.main_window", None)
    from bios_build_gui.gui import main_window

    return main_window


def test_verify_display_mapping(real_main_window):
    """I4 v2: the verdict -> display-text mapping, all three verdicts
    plus the cancelled case."""
    from bios_build_gui.boot_verify import (
        VERDICT_BOOTED,
        VERDICT_BOOT_TO_SHELL_FAIL,
        VERDICT_NOT_BOOTED,
    )

    fn = real_main_window._verify_display_text
    assert fn(VERDICT_BOOTED, "some output", timeout=30, cancelled=False) == (
        "Booted: UEFI shell prompt observed.\n" + "some output"
    )
    assert fn(VERDICT_BOOT_TO_SHELL_FAIL, "some output", timeout=30, cancelled=False) == (
        "Boot to shell failed: firmware reached the Boot Manager but the "
        "shell prompt was not observed within 30 s.\n" + "some output"
    )
    assert fn(VERDICT_NOT_BOOTED, "some output", timeout=30, cancelled=False) == (
        "Not booted: firmware did not reach the Boot Manager within 30 s.\n" + "some output"
    )
    # A cancelled run shows "Cancelled", not a failure verdict.
    assert fn(VERDICT_BOOT_TO_SHELL_FAIL, "some output", timeout=30, cancelled=True) == "Cancelled"
    assert fn(VERDICT_NOT_BOOTED, "some output", timeout=30, cancelled=True) == "Cancelled"
