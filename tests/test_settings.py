"""Tests for the Settings module."""

import json

from bios_build_gui import settings as settings_mod
from bios_build_gui.settings import Settings, load_settings, save_settings


def test_load_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_mod.shutil, "which", lambda name: "/usr/bin/qemu-system-x86_64"
    )
    loaded = load_settings(tmp_path / "settings.json")
    assert loaded.edk2_path == ""
    assert loaded.qemu_path == "/usr/bin/qemu-system-x86_64"


def test_load_missing_file_qemu_path_empty_when_no_qemu_on_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod.shutil, "which", lambda name: None)
    loaded = load_settings(tmp_path / "settings.json")
    assert loaded.qemu_path == ""


def test_save_then_load_preserves_settings(tmp_path):
    original = Settings(edk2_path="/home/user/edk2", qemu_path="/usr/bin/qemu-system-x86_64")
    path = tmp_path / "settings.json"
    save_settings(original, path)
    assert load_settings(path) == original


def test_missing_qemu_path_key_defaults_to_qemu_on_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_mod.shutil, "which", lambda name: "/opt/qemu/bin/qemu-system-x86_64"
    )
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"edk2_path": "/home/user/edk2"}), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.edk2_path == "/home/user/edk2"
    assert loaded.qemu_path == "/opt/qemu/bin/qemu-system-x86_64"


def test_explicit_empty_qemu_path_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_mod.shutil, "which", lambda name: "/usr/bin/qemu-system-x86_64"
    )
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"edk2_path": "/home/user/edk2", "qemu_path": ""}), encoding="utf-8"
    )
    loaded = load_settings(path)
    assert loaded.qemu_path == ""


def test_corrupt_json_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod.shutil, "which", lambda name: None)
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = load_settings(path)
    assert loaded == Settings(edk2_path="", qemu_path="")


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    save_settings(Settings(edk2_path="/x", qemu_path="/y"), path)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "edk2_path": "/x",
        "qemu_path": "/y",
    }
