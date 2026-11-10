# BIOS Build GUI

A desktop tool that builds a bootable UEFI firmware image from the
EDK II OvmfPkg platform package and verifies it boots in QEMU.

Workflow: select platform → configure → build → verify. The platform
is fixed to **OvmfPkg** in v1 (architecture X64 only); the build
produces `OVMF.fd`, which the tool boots in QEMU and checks for the
UEFI shell prompt.

See [docs/design.md](docs/design.md) for the approved design
(EGM: Brainstorm → Draft → Review → Resolve → Implement).

## Pinned versions

| Component | Version |
| --- | --- |
| EDK II | edk2-stable202608 |
| QEMU | 11.1.3 |
| GCC | 12 (major; exact patch version recorded at E2E time) |
| Python | 3.10+ |
| PyQt6 | 6.12.0 |

Note: CVE-2026-97631 (PXE, CVSS 9.5) has no stable patch in
edk2-stable202608. The upgrade to edk2-stable202611 (due 2026-11-20)
is a planned future improvement; the demo does not use PXE.

## Install

```bash
git clone https://github.com/Yao-heng/bios-build-gui.git
cd bios-build-gui
python -m venv .venv
.venv/bin/pip install -e .
```

For development (tests, lint):

```bash
.venv/bin/pip install -r requirements-dev.txt
```

## Launch

```bash
bios-build-gui
```

On first launch the Settings panel asks for the EDK II tree path
(the directory containing `edksetup.sh`). The build is disabled
until every prerequisite check passes.

## Tests

```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check bios_build_gui/ tests/
```

Contract and unit tests run anywhere (fixtures + a fake QEMU stand in
for the toolchain). A real EDK II build and QEMU boot are verified
only in the E2E run on a machine with the pinned toolchain installed
(see the design doc, §7 / CUJ 1–4) — they are not faked here.

## Layout

- `bios_build_gui/config.py` — Config Model (I1) + validation
- `bios_build_gui/adapters/ovmf.py` — OvmfPkg adapter (I2): generate
  + DSC/FDF import
- `bios_build_gui/build_runner.py` — Build Runner (I3)
- `bios_build_gui/boot_verify.py` — Boot Verifier (I4)
- `bios_build_gui/prereq.py` — Prerequisite Checker (I5)
- `bios_build_gui/settings.py` — `settings.json` (gitignored)
- `bios_build_gui/gui/main_window.py` — PyQt6 main window
- `bios_build_gui/main.py` — GUI entry point
- `tests/` — contract + unit tests (fixtures under `tests/fixtures/`)
- `docs/design.md` — approved design
