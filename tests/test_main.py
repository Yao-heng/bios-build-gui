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
