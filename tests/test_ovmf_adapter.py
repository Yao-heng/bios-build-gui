"""Contract tests for Interface I2 (OvmfPkg adapter) — generate() and the
runtime-derived PCD set.

Import tests live in the same file and are added with the import
implementation (design step 5).
"""

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
        toolchain="GCC5",
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
        "GCC5",
        "-b",
        "DEBUG",
    ]
    assert image_path == edk2_tree / "Build" / "OvmfX64" / "DEBUG_GCC5" / "FV" / "OVMF.fd"

    generated_dsc = dsc_path.read_text(encoding="utf-8")
    assert "!include OvmfPkg/OvmfPkgX64.dsc" in generated_dsc
    assert "FLASH_DEFINITION = Generated/OvmfPkgX64.fdf" in generated_dsc
    assert "[PcdsFixedAtBuild]" in generated_dsc
    assert (
        "gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x8000004F" in generated_dsc
    )
    assert fdf_path.read_text(encoding="utf-8") == stock_fdf_before

    # Generation never overwrites a stock file.
    assert stock_dsc.read_text(encoding="utf-8") == stock_dsc_before
    assert stock_fdf.read_text(encoding="utf-8") == stock_fdf_before


def test_generate_release_build_target(edk2_tree, config):
    config.build_target = "RELEASE"
    _dsc, _fdf, command, image_path = ovmf.generate(config)
    assert command[-2:] == ["-b", "RELEASE"]
    assert image_path == edk2_tree / "Build" / "OvmfX64" / "RELEASE_GCC5" / "FV" / "OVMF.fd"


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
    assert (
        "gEfiMdeModulePkgTokenSpaceGuid.PcdResetOnMemoryTypeInformationChange" in names
    )
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
        toolchain="GCC5",
        pcds={"gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel": "0x8000004F"},
    )
    assert validate(good, ovmf) == []
    bad = BuildConfig(
        platform="OvmfPkg",
        architecture="X64",
        build_target="DEBUG",
        toolchain="GCC5",
        pcds={"NotARealPcd": "1"},
    )
    errors = validate(bad, ovmf)
    assert [e.code for e in errors] == ["invalid_pcd"]
