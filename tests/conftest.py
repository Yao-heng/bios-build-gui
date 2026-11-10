"""pytest fixtures: a minimal EDK II tree and a fake QEMU on PATH."""

import os
import shutil
import stat
from pathlib import Path

import pytest

from bios_build_gui.adapters import ovmf

# Minimal but realistic OvmfPkg DSC (subset of the stock file's constructs).
FIXTURE_DSC = """\
## @file
# Fixture OvmfPkgX64 DSC (minimal, for tests).
#
[Defines]
  PLATFORM_NAME                  = Ovmf
  PLATFORM_GUID                  = 5a9e7754-d81b-49ea-85ad-69eaa7b1539b
  PLATFORM_VERSION               = 0.1
  DSC_SPECIFICATION              = 0x00010005
  OUTPUT_DIRECTORY               = Build/OvmfX64
  SUPPORTED_ARCHITECTURES        = X64
  BUILD_TARGETS                  = NOOPT|DEBUG|RELEASE
  SKUID_IDENTIFIER               = DEFAULT
  FLASH_DEFINITION               = OvmfPkg/OvmfPkgX64.fdf
  DEFINE SECURE_BOOT_ENABLE      = FALSE

!include OvmfPkg/Include/Dsc/TestPcds.dsc.inc

[LibraryClasses]
  BaseLib|MdePkg/Library/BaseLib/BaseLib.inf

[PcdsFixedAtBuild]
  gEfiMdeModulePkgTokenSpaceGuid.PcdStatusCodeMemorySize|1
  gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler|0x10
  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x8000004F

[PcdsDynamicDefault]
  gEfiMdeModulePkgTokenSpaceGuid.PcdEmuVariableNvStoreReserved|0
  gUefiOvmfPkgTokenSpaceGuid.PcdPciIoBase|0x0

[Components]
  OvmfPkg/Sec/SecMain.inf
"""

FIXTURE_INC = """\
[PcdsFixedAtBuild]
  gEfiMdeModulePkgTokenSpaceGuid.PcdResetOnMemoryTypeInformationChange|FALSE
"""

FIXTURE_DEC = """\
[Defines]
  PACKAGE_NAME = MdePkg

[PcdsFixedAtBuild]
  gEfiMdePkgTokenSpaceGuid.PcdMaximumGuidedExtractHandler|0x10
  gEfiMdePkgTokenSpaceGuid.PcdDecOnlyExample|42
"""

FIXTURE_FDF = """\
## @file
# Fixture OvmfPkgX64 FDF (minimal, for tests).
#

[Defines]
  FLASH_DEFINITION = OvmfPkg/OvmfPkgX64.fdf

[FD.OVMF]
BaseAddress   = 0xFFC00000
Size          = 0x400000
ErasePolarity = 1
BlockSize     = 0x10000
NumBlocks     = 0x40

0x00000000|0x300000
FV = FVMAIN_COMPACT

0x300000|0x100000
FV = SECFV

[FV.SECFV]
FvNameGuid         = 763BED0D-DE9F-48F5-81F1-3E90E1B1A015
BlockSize          = 0x1000

[FV.FVMAIN_COMPACT]
FvNameGuid         = 9A0B2D2B-F394-44D6-9713-CE3E9D5E9B6A
BlockSize          = 0x1000
"""


@pytest.fixture
def edk2_tree(tmp_path):
    """A minimal EDK II tree layout (no git, no real BaseTools build).

    The OvmfPkg adapter workspace is pointed at this tree for the test
    and reset afterwards.
    """
    tree = tmp_path / "edk2"
    (tree / "OvmfPkg" / "Include" / "Dsc").mkdir(parents=True)
    (tree / "MdePkg").mkdir(parents=True)
    (tree / "BaseTools" / "BinWrappers" / "PosixLike").mkdir(parents=True)
    (tree / "Conf").mkdir(parents=True)
    (tree / "edksetup.sh").write_text("# stub edksetup.sh\n", encoding="utf-8")
    (tree / "OvmfPkg" / "OvmfPkgX64.dsc").write_text(FIXTURE_DSC, encoding="utf-8")
    (tree / "OvmfPkg" / "OvmfPkgX64.fdf").write_text(FIXTURE_FDF, encoding="utf-8")
    (tree / "OvmfPkg" / "Include" / "Dsc" / "TestPcds.dsc.inc").write_text(
        FIXTURE_INC, encoding="utf-8"
    )
    (tree / "MdePkg" / "MdePkg.dec").write_text(FIXTURE_DEC, encoding="utf-8")
    build_wrapper = tree / "BaseTools" / "BinWrappers" / "PosixLike" / "build"
    build_wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    build_wrapper.chmod(build_wrapper.stat().st_mode | stat.S_IEXEC)
    ovmf.set_workspace(tree)
    yield tree
    ovmf.set_workspace(None)


@pytest.fixture
def fake_qemu_on_path(tmp_path, monkeypatch):
    """Place the fake qemu-system-x86_64 on PATH."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    src = Path(__file__).parent / "fake_qemu.py"
    dest = bindir / "qemu-system-x86_64"
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    return bindir
