"""Contract tests for Interface I2 (OvmfPkg adapter) — generate() and the
runtime-derived PCD set.

Import tests live in the same file and are added with the import
implementation (design step 5).
"""

import json
from pathlib import Path

import pytest

from bios_build_gui.adapters import ovmf
from bios_build_gui.config import BuildConfig, validate


@pytest.fixture
def config():
    return BuildConfig(
        schema_version="1",
        platform="OvmfPkg",
        architecture="X64",
        build_target="DEBUG",
        toolchain="GCC",
        pcds={"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel": "0x8000004F"},
    )


def test_generate_produces_dsc_fdf_command_and_image_path(edk2_tree, config):
    stock_dsc = edk2_tree / "OvmfPkg" / "OvmfPkgX64.dsc"
    stock_fdf = edk2_tree / "OvmfPkg" / "OvmfPkgX64.fdf"
    stock_dsc_before = stock_dsc.read_text(encoding="utf-8")
    stock_fdf_before = stock_fdf.read_text(encoding="utf-8")

    dsc_path, fdf_path, command, image_path = ovmf.generate(config)

    assert dsc_path == edk2_tree / "Generated" / "OvmfPkgX64.dsc"
    assert fdf_path == edk2_tree / "Generated" / "OvmfPkgX64.fdf"
    assert command == [
        "build",
        "-p",
        "Generated/OvmfPkgX64.dsc",
        "-a",
        "X64",
        "-t",
        "GCC",
        "-b",
        "DEBUG",
    ]
    assert image_path == edk2_tree / "Build" / "OvmfX64" / "DEBUG_GCC" / "FV" / "OVMF.fd"

    generated_dsc = dsc_path.read_text(encoding="utf-8")
    assert "!include OvmfPkg/OvmfPkgX64.dsc" in generated_dsc
    # No [Defines] section: a second one after the !include makes the
    # EDK II parser drop the stock defines (error 5000, E2E 2026-11-11).
    assert "[Defines]" not in generated_dsc
    assert "FLASH_DEFINITION" not in generated_dsc
    assert "[PcdsFixedAtBuild]" in generated_dsc
    assert "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x8000004F" in generated_dsc
    assert fdf_path.read_text(encoding="utf-8") == stock_fdf_before

    # Generation never overwrites a stock file.
    assert stock_dsc.read_text(encoding="utf-8") == stock_dsc_before
    assert stock_fdf.read_text(encoding="utf-8") == stock_fdf_before


def test_generate_release_build_target(edk2_tree, config):
    config.build_target = "RELEASE"
    _dsc, _fdf, command, image_path = ovmf.generate(config)
    assert command[-2:] == ["-b", "RELEASE"]
    assert image_path == edk2_tree / "Build" / "OvmfX64" / "RELEASE_GCC" / "FV" / "OVMF.fd"


def test_generate_with_no_pcds_still_emits_pcd_section(edk2_tree, config):
    config.pcds = {}
    dsc_path, _fdf, _cmd, _img = ovmf.generate(config)
    assert "[PcdsFixedAtBuild]" in dsc_path.read_text(encoding="utf-8")


def test_generate_requires_workspace(config):
    ovmf.set_workspace(None)
    with pytest.raises(RuntimeError, match="workspace"):
        ovmf.generate(config)


def test_generate_missing_stock_dsc_raises(edk2_tree, config):
    (edk2_tree / "OvmfPkg" / "OvmfPkgX64.dsc").unlink()
    with pytest.raises(FileNotFoundError, match="OvmfPkgX64.dsc"):
        ovmf.generate(config)


def test_generate_missing_stock_fdf_raises(edk2_tree, config):
    (edk2_tree / "OvmfPkg" / "OvmfPkgX64.fdf").unlink()
    with pytest.raises(FileNotFoundError, match="OvmfPkgX64.fdf"):
        ovmf.generate(config)


def test_get_pcd_names_from_tree(edk2_tree):
    names = ovmf.get_pcd_names()
    # From the fixture DSC's own PCD sections.
    assert "gEfiMdeModulePkgTokenSpaceGuid.PcdStatusCodeMemorySize" in names
    assert "gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler" in names
    assert "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel" in names
    assert "gEfiMdeModulePkgTokenSpaceGuid.PcdEmuVariableNvStoreReserved" in names
    assert "gUefiOvmfPkgTokenSpaceGuid.PcdPciIoBase" in names
    # From the !include'd .dsc.inc file.
    assert "gEfiMdeModulePkgTokenSpaceGuid.PcdResetOnMemoryTypeInformationChange" in names
    # From the DEC file of a package referenced by the DSC.
    assert "gEfiMdePkgTokenSpaceGuid.PcdDecOnlyExample" in names
    # No hard-coded list: the set is exactly what the tree declares.
    assert names == {
        "gEfiMdeModulePkgTokenSpaceGuid.PcdStatusCodeMemorySize",
        "gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler",
        "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel",
        "gEfiMdeModulePkgTokenSpaceGuid.PcdEmuVariableNvStoreReserved",
        "gUefiOvmfPkgTokenSpaceGuid.PcdPciIoBase",
        "gEfiMdeModulePkgTokenSpaceGuid.PcdResetOnMemoryTypeInformationChange",
        "gEfiMdePkgTokenSpaceGuid.PcdDecOnlyExample",
    }


def test_get_pcd_names_requires_workspace():
    ovmf.set_workspace(None)
    with pytest.raises(RuntimeError, match="workspace"):
        ovmf.get_pcd_names()


def test_validate_with_real_adapter(edk2_tree):
    good = BuildConfig(
        platform="OvmfPkg",
        architecture="X64",
        build_target="DEBUG",
        toolchain="GCC",
        pcds={"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel": "0x8000004F"},
    )
    assert validate(good, ovmf) == []
    bad = BuildConfig(
        platform="OvmfPkg",
        architecture="X64",
        build_target="DEBUG",
        toolchain="GCC",
        pcds={"NotARealPcd": "1"},
    )
    errors = validate(bad, ovmf)
    assert [e.code for e in errors] == ["invalid_pcd"]


# --- import() (design step 5) -------------------------------------------


def _fixture_path(name):
    return Path(__file__).parent / "fixtures" / name


def test_import_stock_dsc_fdf_yields_expected_config():
    config, _warnings = ovmf.import_config(
        _fixture_path("OvmfPkgX64.dsc"), _fixture_path("OvmfPkgX64.fdf")
    )
    expected = json.loads(_fixture_path("expected_config.json").read_text(encoding="utf-8"))
    assert config == BuildConfig(**expected)
    assert config.platform == "OvmfPkg"
    assert config.architecture == "X64"
    assert config.build_target == "DEBUG"
    assert config.toolchain == "GCC"
    # Spot-check values against the stock DSC (hand-verified).
    assert config.pcds["gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel"] == "0x8000004F"
    assert config.pcds["gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler"] == "0x10"
    assert config.pcds["gEfiMdeModulePkgTokenSpaceGuid.PcdSetupVideoHorizontalResolution"] == "640"
    assert config.pcds["gEfiMdePkgTokenSpaceGuid.PcdPlatformBootTimeOut"] == "0"
    assert len(config.pcds) == 62


def test_import_unmapped_fields_appear_in_warnings():
    _config, warnings = ovmf.import_config(
        _fixture_path("OvmfPkgX64.dsc"), _fixture_path("OvmfPkgX64.fdf")
    )
    names = [w["name"] for w in warnings]
    assert any(name.startswith("include:") for name in names)
    assert "SECURE_BOOT_ENABLE" in names  # a DEFINE
    assert any(name.startswith("LibraryClasses.") for name in names)
    assert "OvmfPkg/ResetVector/ResetVector.inf" in names  # a component
    assert not any(name.startswith("!") for name in names)  # no directives
    assert len(warnings) > 0


def test_import_duplicate_pcd_warning():
    _config, warnings = ovmf.import_config(
        _fixture_path("OvmfPkgX64.dsc"), _fixture_path("OvmfPkgX64.fdf")
    )
    dup = [w for w in warnings if w["name"] == "gEfiMdeModulePkgTokenSpaceGuid.PcdMaxVariableSize"]
    assert len(dup) == 1
    assert "0x8400" in dup[0]["value"] and "0x2000" in dup[0]["value"]


def test_import_missing_dsc_raises():
    with pytest.raises(FileNotFoundError, match="DSC"):
        ovmf.import_config("/does/not/exist.dsc", None)


def test_import_missing_fdf_raises():
    with pytest.raises(FileNotFoundError, match="FDF"):
        ovmf.import_config(_fixture_path("OvmfPkgX64.dsc"), "/does/not/exist.fdf")


def test_import_without_fdf_skips_fdf_check():
    config, warnings = ovmf.import_config(_fixture_path("OvmfPkgX64.dsc"), None)
    assert config.platform == "OvmfPkg"
    assert not any(w["name"] == "FDF" for w in warnings)


def test_import_fdf_without_ovmf_warns(tmp_path):
    fdf = tmp_path / "other.fdf"
    fdf.write_text("[FD.OTHER]\nBaseAddress = 0x0\n", encoding="utf-8")
    _config, warnings = ovmf.import_config(_fixture_path("OvmfPkgX64.dsc"), fdf)
    assert any(w["name"] == "FDF" for w in warnings)


def test_import_resolves_includes_in_tree(edk2_tree):
    config, warnings = ovmf.import_config(
        edk2_tree / "OvmfPkg" / "OvmfPkgX64.dsc",
        edk2_tree / "OvmfPkg" / "OvmfPkgX64.fdf",
    )
    # The PCD from the !include'd .dsc.inc file is imported.
    assert (
        config.pcds["gEfiMdeModulePkgTokenSpaceGuid.PcdResetOnMemoryTypeInformationChange"]
        == "FALSE"
    )
    names = [w["name"] for w in warnings]
    assert not any(name.startswith("include:") for name in names)
    assert "SECURE_BOOT_ENABLE" in names
    assert "LibraryClasses.BaseLib" in names
    assert "OvmfPkg/Sec/SecMain.inf" in names


def test_import_round_trip_preserves_pcds(edk2_tree):
    config, _warnings = ovmf.import_config(
        _fixture_path("OvmfPkgX64.dsc"), _fixture_path("OvmfPkgX64.fdf")
    )
    dsc_path, _fdf_path, command, _image = ovmf.generate(config)
    generated = dsc_path.read_text(encoding="utf-8")
    assert "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x8000004F" in generated
    assert "gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler|0x10" in generated
    assert "gEfiMdeModulePkgTokenSpaceGuid.PcdSetupVideoHorizontalResolution|640" in generated
    assert command == [
        "build",
        "-p",
        "Generated/OvmfPkgX64.dsc",
        "-a",
        "X64",
        "-t",
        "GCC",
        "-b",
        "DEBUG",
    ]
