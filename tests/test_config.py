"""Contract tests for Interface I1 (Config Model, schema v1).

The tests use a stub adapter so the Config Model is tested without an
EDK II tree. The stub exposes the same attributes the real OvmfPkg
adapter exposes: PLATFORM, SUPPORTED_ARCHITECTURES,
SUPPORTED_BUILD_TARGETS, SUPPORTED_TOOLCHAINS and get_pcd_names().
"""

import json

import pytest

from bios_build_gui.config import BuildConfig, FieldError, load_config, save_config, validate


class StubAdapter:
    """Minimal stand-in for the OvmfPkg adapter."""

    PLATFORM = "OvmfPkg"
    SUPPORTED_ARCHITECTURES = {"X64"}
    SUPPORTED_BUILD_TARGETS = {"DEBUG", "RELEASE", "NOOPT"}
    SUPPORTED_TOOLCHAINS = {"GCC"}
    PCD_NAMES = {
        "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel",
        "gEfiMdeModulePkgTokenSpaceGuid.PcdStatusCodeMemorySize",
    }

    def get_pcd_names(self):
        return set(self.PCD_NAMES)


@pytest.fixture
def adapter():
    return StubAdapter()


@pytest.fixture
def valid_config():
    return BuildConfig(
        schema_version="1",
        platform="OvmfPkg",
        architecture="X64",
        build_target="DEBUG",
        toolchain="GCC",
        pcds={"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel": "0x8000004F"},
    )


def codes(errors):
    return [e.code for e in errors]


def test_valid_config_passes_validation(valid_config, adapter):
    assert validate(valid_config, adapter) == []


def test_unknown_platform(valid_config, adapter):
    valid_config.platform = "ArmVirtPkg"
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["unknown_platform"]
    assert errors[0].field == "platform"


def test_unsupported_architecture(valid_config, adapter):
    valid_config.architecture = "AARCH64"
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["unsupported_architecture"]
    assert errors[0].field == "architecture"


def test_empty_build_target(valid_config, adapter):
    valid_config.build_target = ""
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["empty_value"]
    assert errors[0].field == "build_target"


def test_empty_toolchain(valid_config, adapter):
    valid_config.toolchain = ""
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["empty_value"]
    assert errors[0].field == "toolchain"


def test_unsupported_build_target(valid_config, adapter):
    valid_config.build_target = "SUPERFAST"
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["unsupported_build_target"]
    assert errors[0].field == "build_target"


def test_unsupported_toolchain(valid_config, adapter):
    valid_config.toolchain = "CLANGPDB"
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["unsupported_toolchain"]
    assert errors[0].field == "toolchain"


def test_invalid_pcd_name(valid_config, adapter):
    valid_config.pcds = {"NotARealPcd": "1"}
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["invalid_pcd"]
    assert errors[0].field == "pcds"
    assert "NotARealPcd" in errors[0].message


def test_invalid_pcd_value_type(valid_config, adapter):
    valid_config.pcds = {"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel": 1234}
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["invalid_pcd_value"]
    assert errors[0].field == "pcds"


def test_multiple_field_errors_are_all_reported(valid_config, adapter):
    valid_config.platform = "ArmVirtPkg"
    valid_config.architecture = "IA32"
    valid_config.build_target = ""
    errors = validate(valid_config, adapter)
    assert codes(errors) == ["unknown_platform", "unsupported_architecture", "empty_value"]


def test_field_error_is_a_dataclass_with_field_message_code():
    err = FieldError(field="pcds", message="bad pcd", code="invalid_pcd")
    assert err.field == "pcds"
    assert err.message == "bad pcd"
    assert err.code == "invalid_pcd"


def test_unknown_schema_version_rejected_with_version_named(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2",
                "platform": "OvmfPkg",
                "architecture": "X64",
                "build_target": "DEBUG",
                "toolchain": "GCC",
                "pcds": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="2"):
        load_config(path)


def test_json_round_trip_preserves_config(tmp_path, valid_config):
    path = tmp_path / "configs" / "test.json"
    save_config(valid_config, path)
    loaded = load_config(path)
    assert loaded == valid_config


def test_save_creates_parent_directories(tmp_path, valid_config):
    path = tmp_path / "a" / "b" / "config.json"
    save_config(valid_config, path)
    assert path.exists()


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.json")


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config(path)


def test_load_missing_field_raises(tmp_path):
    path = tmp_path / "incomplete.json"
    path.write_text(
        json.dumps({"schema_version": "1", "platform": "OvmfPkg"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="architecture"):
        load_config(path)


def test_pcd_validation_skipped_when_adapter_has_no_pcd_set(valid_config):
    class NoPcdAdapter(StubAdapter):
        get_pcd_names = None

    valid_config.pcds = {"Anything.AtAll": "1"}
    assert validate(valid_config, NoPcdAdapter()) == []
