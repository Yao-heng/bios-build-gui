# BIOS Build GUI

*   **Author:** Valen (via 曜凰)
*   **Status:** Approved (Resolve complete 2026-11-09; acceptance PASS — all 68 themes fixed, no new contradictions)
*   **Date:** 2026-11-09
*   **Related documents:** `~/workspace/designs/bios-build-gui/concepts_brief.md` (brief decisions D1–D7, Brainstorm themes); `~/workspace/designs/bios-build-gui/reviews/consolidated_review_report.md` (Review, 2026-11-09); `~/workspace/designs/bios-build-gui/reviews/resolve_fix_report.md` (Resolve fixes, 2026-11-09); pre-Resolve snapshot: `~/workspace/designs/bios-build-gui/reviews/bios-build-gui-pre-resolve.md`

--------------------------------------------------------------------------------

## Overview

A working BIOS build GUI (desktop application, Python, not a mockup) that drives an EDK II build from configuration to a bootable image. EDK II is TianoCore's UEFI firmware development environment — the reference implementation of UEFI firmware, providing the build tools, libraries, and platform packages. The user selects the platform (OvmfPkg), selects the target architecture (X64), sets build options (build target, toolchain, PCDs — Platform Configuration Database entries), runs the build, and receives a bootable image. Version 1 targets OvmfPkg (QEMU UEFI) and produces OVMF.fd, which boots in QEMU.

For OvmfPkg, the board-level workflow maps as: select platform → OvmfPkg; select chip → target architecture (X64); configure pins → platform settings (build target, toolchain, PCDs).

This tool is a portfolio piece. It was conceived under the Valen identity (the user's anonymous freelance identity; Yao-heng is the user's real-name GitHub account), to demonstrate BIOS and build expertise to prospective clients with a working tool: the GUI invokes the EDK II toolchain, runs a build, and produces a bootable firmware image. **Repo decision changed by the user 2026-11-09 15:25: the tool now lives on his personal GitHub (Yao-heng), not under Valen, because it helps job hunting.** It is now a job-hunting portfolio piece under his real identity; it is no longer a Valen-anonymous piece.

Demo: the tool is demonstrated on the user's machine (screen share or recorded video), where the pinned toolchain is installed. The v1 G2 deliverable is a recorded demo video (screen capture of a full CUJ 1 run) plus a screenshot set in the README (see Verification Plan item (f)). A scripted one-command toolchain setup (installing the pinned EDK II tree, GCC, QEMU, and PyQt6 on a fresh machine) is a future improvement, not a v1 deliverable.

## The Problem

Valen has zero showable firmware work. The OpenBMC GUI tool lives on the Yao-heng GitHub account (linking it would expose the user's real identity), and 24 years of firmware work is proprietary company code. There is nothing a prospective client can see that demonstrates BIOS expertise.

The proposed solution is a BIOS build GUI under Valen. It is a working tool: it captures hardware configuration (platform, architecture, build options, PCDs), drives the EDK II toolchain, runs the build, and produces a bootable image. The first platform is OvmfPkg, chosen because it produces a bootable UEFI image (OVMF.fd) that runs in QEMU with no physical hardware.

## Goals

*   **G1:** A working BIOS build GUI that drives an EDK II build from configuration to a bootable image (OvmfPkg → OVMF.fd → boots in QEMU).
*   **G2:** The tool demonstrates BIOS and build expertise to prospective clients. Acceptance: Verification Plan item (f) — a recorded demo video and README screenshots showing a successful build + boot.
*   **G3:** Version 1 is OvmfPkg only, with a configuration model that can later extend to real-board platforms without a rewrite.
*   **G4:** The tool fails fast with clear messages when its prerequisites (EDK II toolchain, QEMU) are missing or mismatched, and shows live build progress, actionable errors, and the output location.

## Non-Goals

*   **NG1:** Real-board platforms in v1 (after OvmfPkg).
*   **NG2:** Web-based demo.
*   **NG3:** Simulated builds (the build must be an EDK II build).
*   **NG4:** Import of non-OvmfPkg platforms or non-DSC/FDF formats. (Import of OvmfPkg DSC/FDF is in v1 — see Q6, CUJ 4, I2.)
*   **NG5:** A general board-level config model exercised in v1 — v1 exercises only what OvmfPkg needs (target architecture plus build options); the full board-level model (BMC chip, BIOS ROM chip, decode addresses, GPIO) is deferred to the first real-board platform (schema v2).

## Open Questions

*   **Q2:** Pinned compiler toolchain version (GCC version)? **Partially resolved 2026-11-09: GCC 12** (major version pinned, as shipped by Ubuntu 22.04/24.04). The exact GCC patch version on the implementation machine is to be recorded at implementation (Implementation order step 7). All other questions (Q1, Q3–Q7) were resolved during Draft and removed from this section per the template; their resolutions are recorded in the Pinned versions table (Q1/Q3), the GUI/`requirements.txt` (Q4), Alternatives F (Q5), CUJ 4/I2 (Q6), and I1/`config.py` (Q7).

## Critical User Journeys (CUJs)

### CUJ 1: Build OVMF.fd from the GUI

*   **Given**: The tool is installed on a machine with the pinned EDK II toolchain and QEMU. The user opens the GUI.
*   **When**: The user selects platform OvmfPkg, selects target architecture (X64), sets build options (build target, toolchain, PCDs — Platform Configuration Database entries), and presses Build. The GUI shows live build progress. The build completes.
*   **Then**: OVMF.fd is produced. The GUI shows the output path, size, and timestamp, plus the QEMU command to boot it. The user can launch QEMU from the GUI (or copy the command) and observe OVMF.fd booting to the UEFI shell (the firmware's built-in command-line environment; reaching it proves the image boots).

### CUJ 2: Missing toolchain fails fast with a clear message

*   **Given**: The tool is opened on a machine without the EDK II toolchain (or with a mismatched version).
*   **When**: The tool starts up and checks for the EDK II toolchain and QEMU.
*   **Then**: The GUI reports exactly what is missing or mismatched and how to fix it (e.g., the expected EDK II location/version and the install step). It does not proceed to a build that would fail later with an unclear error.

### CUJ 3: Build failure surfaces an actionable error

*   **Given**: The user has configured a build and pressed Build. The EDK II build fails.
*   **When**: The build exits non-zero.
*   **Then**: The GUI shows the error that caused the failure with file/line context, saves the full build log to a file, and offers a retry path (fix the configuration and press Build again — the ordinary flow; there is no separate Retry button or dialog). The user can open the full log.

### CUJ 4: Import an existing OvmfPkg DSC/FDF and rebuild it

*   **Given**: The user has an existing OvmfPkg DSC/FDF pair (e.g., from the EDK II tree or a prior build).
*   **When**: The user chooses Import, selects the DSC file, and the tool parses it into the config model. The user edits a setting (e.g., changes a PCD or build target) and presses Build.
*   **Then**: The GUI shows the imported configuration, the user edits it, and the build produces OVMF.fd from the imported configuration, after the user's edits. Any DSC fields that do not map to the config model are shown as a warning with their names, not silently dropped.

## Technical Plan (Architecture)

### Architecture overview

The tool is a desktop Python application (PyQt6 GUI) that wraps the EDK II build flow. The GUI never builds firmware itself; it captures configuration, generates EDK II platform description files (DSC — Description file — / FDF — Flash Description File) from that configuration, invokes the EDK II `build` command as a subprocess, streams the build output live, and verifies the resulting image by booting it in QEMU. The configuration model is versioned and uses platform adapters: OvmfPkg is the first adapter; a future real-board platform adds a new adapter without changing the GUI or the build runner.

EDK II concepts used in this design: the **EDK II tree** is the checkout of the edk2 repo (at the pinned tag); the **workspace** is the directory containing the tree (where `build` runs); the **build output** is under `Build/<Platform>/<Target>_<Toolchain>/FV/` (e.g. `Build/OvmfX64/DEBUG_GCC/FV/OVMF.fd`).

```text
┌──────────────────────────────────────────────────────────────────┐
│  BIOS Build GUI (PyQt6)                                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Platform   │  │ Config       │  │ Build    │  │ Boot       │  │
│  │ (OvmfPkg)  │  │ Editor       │  │ Log View │  │ Verify     │  │
│  └─────┬──────┘  └──────┬───────┘  └────┬─────┘  └─────┬──────┘  │
└────────┼────────────────┼───────────────┼──────────────┼────────┘
         │                │               │              │
┌────────▼────────────────▼───────────────▼──────────────▼────────┐
│  Application Core (Python, no GUI dependency)                    │
│  The five Python modules (Config Model, EDK II Adapter, Build    │
│  Runner, Prerequisite Checker, Boot Verifier) with no GUI        │
│  dependency; the GUI and the tests call its functions.           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Config Model │  │ EDK II       │  │ Build Runner           │  │
│  │ (schema v1)  │  │ Adapter      │  │ (subprocess, streaming)│  │
│  │              │  │ (DSC/FDF     │  │                        │  │
│  │              │  │  gen + import)│  │                        │  │
│  └──────────────┘  └──────────────┘  └────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                              │
│  │ Prerequisite │  │ Boot         │                              │
│  │ Checker      │  │ Verifier     │                              │
│  └──────────────┘  └──────────────┘                              │
└──────────────────────────────────────────────────────────────────┘
         │                  │                    │           │
    config file        DSC/FDF files        build cmd    QEMU + OVMF.fd
    (JSON, schema v1)  (generated)          (subprocess) (boot check)
```

### Components

*   **GUI (PyQt6):** The only component that depends on PyQt. It renders a fixed platform label ("Platform: OvmfPkg"), the config editor, the build log view, and the boot verification panel, plus a step indicator showing the five steps (select platform → configure → build → verify) with the current step highlighted. It never calls EDK II directly; it calls the Application Core.
*   **Config Model:** The in-memory representation of a build configuration, plus JSON serialisation (schema v1). It is the authoritative representation of what the user configured. It validates itself (see Interface I1).
*   **EDK II Adapter:** Translates between the Config Model and EDK II platform files. Two directions: generate (config → DSC/FDF + build command) and import (DSC/FDF → config). One adapter per platform; OvmfPkg is the only adapter in v1. The GUI obtains the OvmfPkg adapter by directly importing it.
*   **Build Runner:** Invokes the EDK II `build` command as a subprocess, streams stdout/stderr line-by-line to the GUI log view, writes the full log to a file, and returns the exit code. It does not parse build output for success; the exit code is the verdict.
*   **Prerequisite Checker:** Runs at startup (and on demand, via a Re-check button in the prerequisite panel; also automatically when the EDK II path setting changes). Checks for the EDK II tree, the BaseTools binaries, the GCC toolchain, QEMU, and Python/PyQt. Returns a structured result (present/missing/mismatched + version + fix hint) for each item.
*   **Boot Verifier:** Launches QEMU with the produced OVMF.fd, captures serial output, and detects the UEFI shell prompt within a timeout. Returns booted / not-booted + captured output.

### Data flow (build)

1.  Startup: the settings are loaded (`settings.json`; if missing or the EDK II path is unset/invalid, the GUI shows a first-run settings panel with a file-picker). The Prerequisite Checker runs. If anything is missing or mismatched, the GUI shows the failure and the fix hint, and disables Build until the check passes.
2.  User selects platform OvmfPkg (a fixed label in v1). The GUI imports the OvmfPkg adapter directly and shows its config fields.
3.  User configures (architecture, build target, toolchain, PCDs) — or imports an existing DSC/FDF, which populates the same fields.
4.  User presses Build. The Config Model validates itself; on failure, the GUI shows field-level errors and stops. Pressing Build saves the current config to `<project>/configs/last.json` (overwritten each build), so every build is reproducible from a saved config.
5.  EDK II Adapter generates DSC/FDF into the generated-files directory (`<workspace>/Generated/`, inside the EDK II workspace; never overwriting a stock file), assembles the build command, and determines the expected output image path.
6.  Build Runner invokes the build command, streams output to the GUI, and saves the full log.
7.  On exit code 0, the GUI shows the output image path, size, and timestamp, plus the QEMU boot command. On non-zero, the GUI shows the error that caused the failure with file/line context and the log path.
8.  User presses Boot Verify. Boot Verifier launches QEMU with OVMF.fd, waits for the UEFI shell prompt (timeout 60 s by default), and reports booted / not-booted with captured output.

### Pinned versions (v1)

| Component | Pinned version | Source / note |
|---|---|---|
| EDK II | edk2-stable202608 | Latest stable tag, 2026-08-21. Known limitation: CVE-2026-97631 (PXE, CVSS 9.5) has no stable patch yet; planned upgrade to edk2-stable202611 (due 2026-11-20). Demo does not use PXE boot. |
| QEMU | 11.1.3 | Latest stable patch, 2026-10-28 (qemu.org). |
| GCC | 12 (major version pinned; exact patch version recorded at implementation — provisional until recorded) | As shipped by Ubuntu 22.04/24.04. The EDK II toolchain tag `GCC` is a toolchain-family name, not a compiler version (see I1). Toolchain tag was `GCC5` in the original design; edk2-stable202608 removed GCC5 (tools_def.txt v3.06), so the tag is `GCC` (E2E finding, 2026-11-11). |
| Python | 3.10 (minimum version; exact version recorded at implementation — provisional until recorded) | Ubuntu 22.04 default is 3.10. |
| PyQt | PyQt6 (exact version recorded at implementation — provisional until recorded; minimum version enforced by the Prerequisite Checker) | User chose PyQt; PyQt6 is the current major version. |

Upgrading any pinned version is an explicit, tested event (per brief D5): change the pin, rebuild OvmfPkg, boot-verify in QEMU, and record the new pin. The PCD set is re-derived automatically on the next run (no manual refresh). Never upgrade silently. A provisional pin must be recorded (exact version) at implementation (Implementation order step 7) before the design is Approved.

### Interface Registry v1

Each interface is defined once here. Components reference it by name; no component redefines it.

*   **I1 — Config Model (schema v1).** A JSON document with a `schema_version` field (value `"1"`). Fields: `platform` (string, e.g. `"OvmfPkg"`), `architecture` (`"X64"` only in v1), `build_target` (`"DEBUG"` | `"RELEASE"` | `"NOOPT"` — NOOPT means no optimisation), `toolchain` (string, EDK II toolchain tag, e.g. `"GCC"`), `pcds` (object: PCD name → value). The EDK II toolchain tag (e.g. `GCC`) is a toolchain-family name, not a compiler version. The actual compiler is the pinned GCC (major version 12); the tag selects the EDK II toolchain definition, which invokes the installed GCC. Validation: `platform` must have an adapter (the OvmfPkg adapter, directly imported); `architecture` must be one the adapter supports (X64 only in v1); `build_target` and `toolchain` must be non-empty strings AND must be in the adapter's supported sets (the same adapter-checked rule as PCD keys — a value that is not in the supported set is rejected, so a crafted config value cannot inject unexpected arguments into the build command); `pcds` keys must be valid PCD names (adapter-checked, against the runtime-derived PCD set). Validation failure returns a list of field errors; the GUI shows them per field. The API is: class `BuildConfig` (a dataclass) with fields `schema_version: str`, `platform: str`, `architecture: str`, `build_target: str`, `toolchain: str`, `pcds: dict[str, str]`; functions `load_config(path) -> BuildConfig`, `save_config(config, path) -> None`, `validate(config, adapter) -> list[FieldError]` where `FieldError` is a dataclass with `field: str`, `message: str`, `code: str`. `validate` takes the adapter as a parameter (the caller passes the OvmfPkg adapter); `config.py` does not import the adapters package.
*   **I2 — Platform Adapter.** One adapter per platform, imported directly by name. Each adapter implements two functions: `generate(config) -> (dsc_path, fdf_path, build_command, image_path)` and `import(dsc_path, fdf_path) -> (config, warnings)`. `generate` writes DSC/FDF into the generated-files directory (`<workspace>/Generated/`), returns the build command as an argument list (not a shell string), and returns `image_path`, the expected output image path (computed from the EDK II output layout: `Build/OvmfX64/<build_target>_GCC/FV/OVMF.fd` relative to the EDK II workspace). The generated DSC is a thin wrapper: it `!include`s the stock `OvmfPkg/OvmfPkgX64.dsc`, then sets the configured PCD values in a `[PcdsFixedAtBuild]` section (overriding the stock values). It does NOT set `FLASH_DEFINITION`: a second `[Defines]` section after the `!include` makes the EDK II parser drop the stock defines (including `SUPPORTED_ARCHITECTURES`), failing the build with error 5000 (E2E finding, 2026-11-11). The build therefore uses the stock FDF path from the stock DSC; the generated FDF is a copy of the stock `OvmfPkg/OvmfPkgX64.fdf` (the config does not change the flash layout in v1), so the output is identical. Generation never overwrites a stock file. DSC sections the config does not cover are inherited verbatim via the `!include` (they are not regenerated). The adapter derives the offered PCD set at runtime from the installed EDK II tree (parse the PCD declarations in the OvmfPkg DSC and the DEC files it references, via EDK II BaseTools). No hard-coded PCD list. If a PCD in a saved config is no longer present in the tree, validation reports a field error naming the PCD and the installed tag. `import` parses DSC/FDF and returns a config plus a warnings list (name + raw value); any DSC field that does not map to the schema is returned as a warning, never silently dropped. The importer parses DSC using EDK II BaseTools (`Workspace/DscBuildData.py`) from the pinned tree, and FDF using `GenFds/`. If BaseTools' API proves unsuitable at implementation (import weight or API instability across tags), the adapter records the reason in the design doc and implements a bounded hand-written parser supporting only the constructs in OvmfPkg's DSC/FDF. OvmfPkg is the only adapter in v1.
*   **I3 — Build Runner.** Input: a build command (argument list), a working directory (the EDK II workspace), a log file path, an `on_line` callback, and a `cancel_event` (`threading.Event`). Behaviour: invokes the command as a subprocess (no shell), streams stdout/stderr line-by-line to the caller-provided callback (the two streams are merged via `stderr=subprocess.STDOUT` so they reach the callback as one ordered stream), writes the full output to the log file, and returns the exit code. Success is defined solely by exit code 0. The runner does not parse build output for success or failure. On a non-zero exit code, the caller (GUI) extracts the error that caused the failure from the log for display, using `extract_error_block(log_path) -> str` (a function in `build_runner.py`, the module that owns the log file): scan the log from the end backwards; find the last line matching an error pattern; the error block is that line plus the 20 lines preceding it (context) and the 5 lines following it (if any). Error patterns: (a) a line containing `error` (case-insensitive) as a word; (b) a line matching a compiler error with file/line (`*.c(123):` or `*.c:123:`); (c) a line containing `Failed`. If no line matches, fall back to the last 30 lines of the log (the tail). The block includes the file/line if the matched line contains one; otherwise it is shown with log line numbers. Log file path: `<project>/logs/build-<timestamp>.log` (the `logs/` directory is created if needed), where `<project>` is the tool's repository root (the directory containing `bios_build_gui/`, `tests/`, and `logs/`; v1 is run from the repository checkout). **Build policy:** v1 uses EDK II default incremental builds, with a GUI "Clean Build" action that removes the platform's build output directory (`Build/OvmfX64/`) before invoking `build`. **Environment setup:** the runner sets the equivalent environment variables (no shell — it does not source `edksetup.sh`): `WORKSPACE` (the EDK II workspace path), `PACKAGES_PATH` (the EDK II tree path), `EDK_TOOLS_PATH` (the BaseTools binaries directory), `CONF_PATH` (the Conf directory under the workspace), `PYTHON_COMMAND` (the Python interpreter). It sets these in the subprocess environment (via the `env` parameter of `subprocess.Popen`), derived from the settings (EDK II path) and the workspace layout. **BaseTools:** in the pre-build phase, if the BaseTools binaries are missing, the runner builds them once (`make -C BaseTools`, output streamed to the log) and then proceeds. If that fails, the build fails with a clear error. **Teardown:** the runner checks `cancel_event` between output lines and terminates the build subprocess if it is set. The GUI Cancel button sets the event; the GUI creates a new event per build run. Closing the GUI while a build is running terminates the subprocess first.
*   **I4 — Boot Verifier.** Input: the OVMF.fd path, a timeout (default 60 s — an input with a default, configurable by the caller, not a hard constant; the 60 s default must be validated against a DEBUG build under TCG at implementation, the slowest supported path, and the measurement recorded in the design doc), and a `cancel_event` (`threading.Event`, optional). Behaviour: launches QEMU with the image as a pflash drive (pflash — parallel flash — the firmware image is attached as a flash device, not a disk, because UEFI firmware executes from flash), captures serial output, and returns `booted` (true if the UEFI shell prompt is observed within the timeout; the prompt is detected by matching the substring `Shell>` in serial output) plus the captured output. The verifier returns as soon as `Shell>` is observed; it does not wait out the full timeout. The pinned QEMU command is: `qemu-system-x86_64 -machine q35 -m 1024 -drive if=pflash,format=raw,unit=0,file=<image_path>,readonly=on -display none -serial stdio` (single OVMF.fd as a readonly pflash drive; no disk attached, so the firmware falls through to the UEFI shell). The split `OVMF_CODE.fd`/`OVMF_VARS.fd` form is a future improvement (needed only if NVRAM persistence matters). **Acceleration:** detect KVM availability; if `/dev/kvm` is present and accessible, use `-accel kvm`; otherwise fall back to TCG (software emulation, slower). QEMU is launched as a subprocess; the verifier kills it after the verdict, and also if the caller requests cancellation (via `cancel_event`) or the GUI is closed while a boot verify is running.
*   **I5 — Prerequisite Checker.** Input: the settings object (see the Settings module). Output: a list of check results, one per item (EDK II tree, BaseTools binaries, GCC, QEMU, Python/PyQt), each a dataclass `CheckResult` with fields `name`, `status` (`ok` | `missing` | `mismatched`), `found_version` (string or null), `expected_version` (string), and `fix_hint` (string: what to install or change). Per-item criteria:
    *   **EDK II tree:** presence = the directory at `settings.edk2_path` exists AND contains `edksetup.sh` AND contains `OvmfPkg/OvmfPkgX64.dsc`. Version = `git describe --tags` in the tree; if the tree is not a git checkout or has no tags (tarball), `found_version` is `null` and the check reports `mismatched` with a fix hint ("use a git checkout of the pinned tag"). Mismatched = the git tag differs from the pinned tag.
    *   **BaseTools binaries:** presence = the built BaseTools binaries exist in the EDK II tree. If missing, the fix hint is "run `make -C BaseTools` in the EDK II tree (after sourcing `edksetup.sh`)" (the runner also builds them automatically in its pre-build phase — see I3).
    *   **GCC:** presence = `gcc` on PATH; version = parse `gcc --version` first line. Mismatched = the major version differs from the pinned major (12).
    *   **QEMU:** presence = `qemu-system-x86_64` on PATH (or `settings.qemu_path` if set); version = parse `qemu-system-x86_64 --version`. Mismatched = the version string differs from the pinned version (11.1.3).
    *   **Python/PyQt:** version check only (the app runs on Python/PyQt, so a presence check is vacuous). Version = the running interpreter's version and the PyQt6 version. Mismatched = below the pinned minimum (Python 3.10, PyQt6 minimum recorded at implementation).
    *   **`expected_version` source:** hard-coded constants in `prereq.py`, derived from the Pinned versions table.
    *   **"Mismatched" definition (uniform):** the found version does not satisfy the pinned requirement for that item (EDK II/QEMU: exact match; GCC: same major; Python/PyQt6: at or above the pinned minimum). A newer version that does not satisfy the pin is `mismatched` (upgrades are explicit events per D5); the fix hint names the expected and found versions and the upgrade procedure.
    *   The GUI disables Build while any item is not `ok`.

### Settings

The tool's settings live in a JSON file `<project>/settings.json` (in the tool's repo root; gitignored — it contains machine-specific paths). Format: `{"edk2_path": "<path>", "qemu_path": "<path>"}` (`qemu_path` optional; defaults to the QEMU on PATH). Module `bios_build_gui/settings.py` provides `load_settings() -> Settings` (returns defaults if the file is missing) and `save_settings(settings) -> None`. On startup, if `settings.json` is missing or `edk2_path` is unset/invalid, the GUI shows a first-run settings panel with a file-picker for the EDK II tree path; a Settings action in the GUI lets the user change it later.

### Config Schema v1 (summary)

The config is a JSON file, `schema_version` `"1"`. The OvmfPkg adapter reads `platform`, `architecture`, `build_target`, `toolchain`, and `pcds`. The schema is versioned: a future schema v2 adds fields but never renames or removes v1 fields; the loader rejects a config whose `schema_version` it does not recognise, with a clear error naming the version. Schema v2 will add a `board` object (for the first real-board platform: `bmc_chip`, `bios_rom_chip`, `bios_rom_decode`, `bmc_rom_decode`, `gpio`) and a `features` object (for the first feature flag, e.g. Secure Boot enablement); neither is in schema v1.

**Config file lifecycle (GUI):** the GUI has a Save action (Ctrl+S / File menu) writing the current config to a JSON file (default `<project>/configs/<name>.json`, or a user-chosen path via a file dialog) and an Open action (Ctrl+O / File menu) loading a config file. Pressing Build saves the current config to `<project>/configs/last.json` (overwritten each build). The imported config is held in memory until Build (when it is saved to `last.json`) or Save As. The pytest integration tests load config files in the same format.

Example (X64 DEBUG, illustrative — the exact PCD set is derived by the OvmfPkg adapter at runtime from the pinned EDK II tree):

```json
{
  "schema_version": "1",
  "platform": "OvmfPkg",
  "architecture": "X64",
  "build_target": "DEBUG",
  "toolchain": "GCC",
  "pcds": {}
}
```

### Launching the GUI

The tool is a GUI. It is launched with the `bios-build-gui` console script (installed by `pip install -e .`, see `pyproject.toml`), which calls `bios_build_gui.main:main`. There is no headless CLI in v1; headless verification is driven by pytest integration tests that call the Application Core functions directly (see Implementation order steps 3–4 and the Verification Plan).

### Error semantics

*   **Prerequisite failure (I5):** Startup check fails → GUI shows each failed item with its fix hint; Build is disabled. No build is attempted. This is a prerequisite error, not a build error.
*   **Config validation failure (I1):** Field-level errors shown in the editor; Build is not invoked. No files are generated.
*   **Generation failure (I2):** The adapter reports which input it could not translate; no build is invoked. The generated-files directory is left as-is (no partial DSC/FDF is used).
*   **Build failure (I3):** Non-zero exit code → GUI shows the last error block from the log (per the `extract_error_block` rule in I3) with file/line context, the full log path, and a retry path (fix the configuration and press Build again). The output image (if any) is not presented as a success.
*   **Boot verification failure (I4):** Timeout without the shell prompt, or QEMU exits early → GUI shows the captured serial output and the timeout value. The build itself is still reported as successful (build and boot are separate verdicts).

### Import design (DSC/FDF → config)

*   The importer supports the constructs used by OvmfPkg's DSC/FDF (sections, PCD assignments, `!include` of the stock files, library class overrides as warnings). Anything else goes to the warnings list.
*   The importer reads the DSC file and extracts: platform name, supported architectures, build target and toolchain (from the build command or DSC defaults), PCD values (from `[PcdsFixedAtBuild]` — the section where fixed-at-build PCD values are declared — and the related PCD sections `[PcdsDynamicDefault]` and `[PcdsPatchableInModule]`), and library class overrides. A "library class override" is a `[LibraryClasses]` entry mapping a library class to a specific library instance; in v1 these go to the warnings list (the schema has no library-class field). It reads the FDF file and extracts the flash device layout (FD — Flash Device — regions, FV — Firmware Volume — names) — for OvmfPkg this confirms the output is OVMF.fd.
*   The importer parses DSC using EDK II BaseTools (`Workspace/DscBuildData.py`) from the pinned tree, and FDF using `GenFds/` (see I2).
*   Each extracted value maps to a config field. Values that do not map are collected into the warning list (I2) and shown to the user with their raw names, so nothing is silently lost.
*   Import never modifies the source DSC/FDF files. The imported config is held in memory; the user edits it in the GUI, and Build generates fresh DSC/FDF from it.
*   Round-trip goal: import → edit → generate → build should produce an image equivalent to building from the original DSC/FDF. Exact byte-equivalence is not guaranteed (generated DSC/FDF may reorder sections); functional equivalence (same PCDs, same build target, same image boots) is the acceptance criterion.
*   Scope note: import is the largest v1 scope item; its risk is the parser + round-trip fidelity, mitigated by the bounded scope + BaseTools reuse.

### Build execution details

*   The build command is assembled by the OvmfPkg adapter as an argument list, e.g. `build -p Generated/OvmfPkgX64.dsc -a X64 -t GCC -b DEBUG` (relative to the EDK II workspace; `-p` points at the generated DSC, not the stock DSC). The DSC path is fixed to the generated OvmfPkgX64 DSC in v1.
*   **Build policy:** v1 uses EDK II default incremental builds, with a GUI "Clean Build" action that removes `Build/OvmfX64/` before invoking `build` (see I3).
*   The EDK II environment is set up before the build: the runner sets the equivalent environment variables (`WORKSPACE`, `PACKAGES_PATH`, `EDK_TOOLS_PATH`, `CONF_PATH`, `PYTHON_COMMAND`) in the subprocess environment; it does not source `edksetup.sh` (see I3). The setup step is part of the runner's pre-build phase, not the user's responsibility. In the pre-build phase, if the BaseTools binaries are missing, the runner builds them once (`make -C BaseTools`).
*   The build runs in the EDK II workspace as the working directory. The generated DSC/FDF live in the generated-files directory `<workspace>/Generated/` (inside the EDK II workspace, a fixed name that cannot collide with stock files); the adapter returns their paths.
*   Build output is streamed live to the GUI log view and written in full to a log file at `<project>/logs/build-<timestamp>.log` (the `logs/` directory is created if needed; `<project>` is the tool's repository root). The log file path is shown in the GUI after every build, success or failure.
*   Cancellation: the GUI provides a Cancel button during a build; pressing it sets the `cancel_event` and terminates the build subprocess (I3 teardown). Closing the GUI while a build is running terminates the subprocess first.

### Boot verification details

*   QEMU is launched with the produced OVMF.fd as a pflash drive, serial output to stdio, no graphical display. The pinned command is: `qemu-system-x86_64 -machine q35 -m 1024 -drive if=pflash,format=raw,unit=0,file=<image_path>,readonly=on -display none -serial stdio` (see I4 for the acceleration rule and the split CODE/VARS note). No disk is attached, so the firmware falls through to the UEFI shell.
*   The verifier watches serial output for the substring `Shell>` (the UEFI shell prompt) and reports `booted` when it appears, returning early (it does not wait out the full timeout). The timeout is an input to `verify_boot` with a default of 60 s (see I4). If QEMU exits before the prompt, that is a not-booted verdict with the captured output shown.
*   Boot verification is optional and separate from the build verdict: a successful build with a failed boot verify is reported as "build succeeded, boot verify failed", not as a build failure.

## Alternatives Considered

### Alternative A: Web demo (browser-based mockup)

*   **Pros**: Easiest to share with a client (just a URL); no toolchain install needed to view; the most showable form.
*   **Cons**: It would not be a working tool — no actual EDK II build, no bootable image. It would demonstrate web design, not BIOS expertise. It would also be a separate deliverable (a website) rather than the BIOS tool itself.
*   **Reason for Rejection**: The user explicitly chose a working tool over a web demo (2026-11-09). A mockup would not demonstrate BIOS/build capability, which is the point of the portfolio piece.

### Alternative B: OpenBMC GUI variant (extend the existing OpenBMC image-builder GUI)

*   **Pros**: Reuses an existing, working GUI codebase; faster to build; the OpenBMC GUI already handles image building.
*   **Cons**: The OpenBMC GUI lives on the Yao-heng GitHub account — linking it to Valen would expose the user's real identity. It also demonstrates OpenBMC/image-building, not BIOS/EDK II expertise, which is the core skill the portfolio needs to show.
*   **Reason for Rejection**: The user chose the BIOS build GUI over an OpenBMC variant (2026-11-09 10:11). The identity constraint (Valen anonymity) and the expertise signal (BIOS, not OpenBMC) both point to a fresh tool.

### Alternative C: Generate build scripts/commands without executing them

*   **Pros**: Simpler — no subprocess management, no build output streaming, no toolchain dependency at runtime. The tool would be a config-to-script generator.
*   **Cons**: The user would still have to run the build, in a terminal, with the toolchain set up. The tool would not show the build works, and a client could not see a bootable image produced by the tool.
*   **Reason for Rejection**: The user's requirement is a working tool that actually runs builds and produces a bootable image. Script generation alone does not meet G1.

### Alternative D: tkinter (Python stdlib GUI) instead of PyQt

*   **Pros**: Zero third-party dependency (stdlib); same toolkit family as the OpenBMC GUI; smaller install footprint; no licensing or packaging concerns.
*   **Cons**: Plainer default appearance; less polished widgets out of the box; for a portfolio piece a client evaluates, the interface is part of the impression.
*   **Reason for Rejection**: The user chose PyQt (2026-11-09) for its more polished widgets, accepting the third-party dependency cost. The portfolio purpose (G2) makes the interface quality worth the dependency.

### Alternative E: Create-only (no DSC/FDF import)

*   **Pros**: Simpler — no DSC/FDF parser to write or maintain; smaller v1 scope; the "select → configure → build" workflow starts from scratch.
*   **Cons**: A BIOS engineer with an existing OvmfPkg platform cannot bring his own DSC/FDF into the tool; he would have to re-enter everything by hand. The tool would be less useful to someone who already works with EDK II.
*   **Reason for Rejection**: The user chose to include import (2026-11-09). Import makes the tool usable by a working BIOS engineer, not just a newcomer.

### Alternative F: Reuse code/format from the OpenBMC GUI

*   **Pros**: Saves implementation effort (config handling, GUI patterns, build invocation) by reusing existing, working code.
*   **Cons**: Reusing code from the Yao-heng GitHub repo creates a link between Valen and the user's real identity — in the code itself, in file headers, or in the repo history. It also couples this tool's design to the OpenBMC GUI's assumptions.
*   **Reason for Rejection**: Valen anonymity is a hard constraint. Any reuse from the Yao-heng repo breaks it. The tool is fully separate (see Q5 resolution in Open Questions). PyQt (rather than the OpenBMC GUI's toolkit) reinforces the separation.

### Alternative G: Full board-level config model exercised in v1

*   **Pros**: The complete model (BMC chip, BIOS ROM chip, decode addresses, GPIO) would be usable in v1; no later migration of the config schema.
*   **Cons**: OvmfPkg needs none of those fields — building the full model for v1 means designing, validating, and testing fields with no platform that exercises them. It adds scope and risk to v1 without any user-visible benefit.
*   **Reason for Rejection**: The schema does NOT carry the `board` object in v1; the first real-board platform adds a `board` object to the schema in v2 (see Config Schema v1). The full model is deferred to the first real-board platform, when the fields will have a real consumer.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy:** The tool handles no secrets, credentials, or personal data. It makes no network calls and sends no telemetry. It only reads local files (config, DSC/FDF) and invokes local tools (EDK II `build`, QEMU). Generated files (DSC/FDF, build logs, OVMF.fd) are written locally. No data leaves the machine.
*   **Performance & Latency:** An EDK II OvmfPkg build takes minutes (initial estimate: 5–15 minutes for an incremental build depending on the machine; a clean build is longer; to be measured at implementation, not a recorded measurement). The GUI must stay responsive during a build: the build runs in a worker thread (not the UI thread), and log output streams incrementally. The GUI must not freeze or block input while a build runs.
*   **Log retention:** Keep the last 10 build logs in `<project>/logs/`; generated DSC/FDF are overwritten per build; `Build/` cleanup follows the Clean Build policy (I3 / M2).
*   **Rollout & Rollback:** Pinned versions (EDK II, QEMU, GCC, Python, PyQt6) are the rollback point — if a build breaks after a pin change, revert the pin. Upgrading a pin is an explicit, tested event (rebuild OvmfPkg, boot-verify in QEMU, record the new pin). The config schema is versioned; the loader rejects a config whose `schema_version` it does not recognise, with a clear error naming the version. There is no auto-update.

--------------------------------------------------------------------------------

### Additional Resources

*   EDK II stable tag release history and planning (edk2-stable202608 released 2026-08-21; edk2-stable202611 due 2026-11-20): https://edk2.groups.io/g/announce/messages?subsort=1 and https://www.tianocore.org/tianocore-wiki.github.io/releases-history/planning-roadmaps/edk_ii_release_planning.html
*   EDK II source (GitHub): https://github.com/tianocore/edk2
*   TianoCore: https://www.tianocore.org/
*   QEMU download (latest stable 11.1.3, 2026-10-28): https://www.qemu.org/download/
*   CVE-2026-97631 (EDK II PXE buffer overflow, CVSS 9.5, no stable patch yet): https://thehackernews.com/2026/10/critical-16-year-old-uefi-flaw-can-run.html

### Future Improvements

*   **Real-board platform adapters:** the first real-board platform adds a `board` object to the schema (schema v2: `bmc_chip`, `bios_rom_chip`, `bios_rom_decode`, `bmc_rom_decode`, `gpio`).
*   **ArmVirtPkg adapter (AARCH64):** a separate adapter for AArch64 QEMU firmware — different package (ArmVirtPkg, not OvmfPkg), image `QEMU_EFI.fd`, cross-compiler `GCC_AARCH64_PREFIX`, QEMU `-machine virt -cpu cortex-a57`. Not an OvmfPkg feature.
*   **EDK II upgrade to edk2-stable202611:** the planned upgrade (due 2026-11-20) that includes the CVE-2026-97631 fix.
*   **Secure Boot enablement in the GUI:** a feature flag that maps to the relevant PCDs and build options. Requires a schema v2 `features` field.
*   **Build profiles:** saved, named configurations (e.g., "OvmfPkg X64 DEBUG", "OvmfPkg X64 RELEASE") the user can switch between.
*   **Scripted toolchain setup:** a one-command installer for the pinned EDK II tree, GCC, QEMU, and PyQt6, so the tool can be demonstrated on a fresh machine (resolves the Brainstorm Theme 2 tension; v1 demos on the user's machine via screen share/video).
*   **Import fidelity:** round-trip byte-equivalence of generated DSC/FDF (currently the bar is functional equivalence, not byte-equivalence).
*   **Split OVMF_CODE.fd / OVMF_VARS.fd boot:** use the split pflash form instead of the single readonly OVMF.fd (needed only if NVRAM persistence matters).

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create

This is a greenfield project; every file below is created. The repo location is the user's personal GitHub (Yao-heng), decided by the user 2026-11-09 15:25 for job hunting (supersedes the earlier "GitLab Valen_Lee or Valen GitHub, to be decided at implementation time"); the layout below is repo-relative. (27 files.)

#### 1. `README.md` (Create)

*   **Type / Scope**: Project documentation.
*   **Proposed Changes**: Project overview (what it does), prerequisites (pinned versions table), install steps (`pip install -e .`), how to launch the GUI (`bios-build-gui`), and how to run the tests. Links to the design doc (a copy of the design doc lives in the repo as `docs/design.md`, so the link is stable).

#### 2. `requirements.txt` (Create)

*   **Type / Scope**: Dependency pin file (runtime).
*   **Proposed Changes**: Pins PyQt6 (exact version to be recorded at implementation). Python stdlib only otherwise.

#### 3. `requirements-dev.txt` (Create)

*   **Type / Scope**: Dependency pin file (development).
*   **Proposed Changes**: Pins pytest, pytest-cov, and ruff (exact versions recorded at implementation).

#### 4. `pyproject.toml` (Create)

*   **Type / Scope**: Project metadata and entry point.
*   **Proposed Changes**: `[project]` metadata; `[project.scripts]` entry `bios-build-gui = "bios_build_gui.main:main"`. The install step is `pip install -e .` (installs the console script + the runtime deps from `requirements.txt`).

#### 5. `bios_build_gui/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Empty.

#### 6. `bios_build_gui/config.py` (Create)

*   **Type / Scope**: Python module — Config Model (Interface I1).
*   **Proposed Changes**: Defines the config dataclass `BuildConfig` (fields per schema v1: `schema_version`, `platform`, `architecture`, `build_target`, `toolchain`, `pcds`), JSON load/save (`load_config(path) -> BuildConfig`, `save_config(config, path) -> None`), and `validate(config, adapter) -> list[FieldError]` where `FieldError` is a dataclass with `field`, `message`, `code`. Rejects a config whose `schema_version` is not `"1"` with a clear error naming the version. `validate` takes the adapter as a parameter (the caller passes the OvmfPkg adapter); `config.py` does not import the adapters package. Invalid cases: unknown `schema_version` (rejected at load); unknown `platform` (code `unknown_platform`); unsupported `architecture` (code `unsupported_architecture`); empty `build_target`/`toolchain` (code `empty_value`); invalid PCD name (code `invalid_pcd`); PCD value of the wrong type (code `invalid_pcd_value`). No GUI dependency, no EDK II dependency.

#### 7. `bios_build_gui/settings.py` (Create)

*   **Type / Scope**: Python module — Settings store.
*   **Proposed Changes**: `load_settings() -> Settings` (returns defaults if `settings.json` is missing) and `save_settings(settings) -> None`. The settings file is `<project>/settings.json` (JSON: `{"edk2_path": "<path>", "qemu_path": "<path>"}`; `qemu_path` optional, defaults to the QEMU on PATH). No GUI dependency.

#### 8. `bios_build_gui/adapters/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Empty. There is no adapter registry in v1; the OvmfPkg adapter is imported directly.

#### 9. `bios_build_gui/adapters/ovmf.py` (Create)

*   **Type / Scope**: Python module — OvmfPkg adapter (Interface I2).
*   **Proposed Changes**: Implements `generate(config) -> (dsc_path, fdf_path, build_command, image_path)` and `import(dsc_path, fdf_path) -> (config, warnings)`. `generate` writes a thin-wrapper DSC (it `!include`s the stock `OvmfPkg/OvmfPkgX64.dsc`, then sets the configured PCD values in a `[PcdsFixedAtBuild]` section; it does NOT set `FLASH_DEFINITION` — a second `[Defines]` section after the `!include` drops the stock defines, error 5000, E2E 2026-11-11, so the stock FDF path is used) and a generated FDF (a copy of the stock `OvmfPkg/OvmfPkgX64.fdf`) into `<workspace>/Generated/`, returns the build command as an argument list (e.g. `build -p Generated/OvmfPkgX64.dsc -a X64 -t GCC -b DEBUG` for X64), and returns `image_path` (`Build/OvmfX64/<build_target>_GCC/FV/OVMF.fd` relative to the EDK II workspace). `import` parses DSC/FDF into a config using EDK II BaseTools (`Workspace/DscBuildData.py` for DSC, `GenFds/` for FDF) from the pinned tree; unmapped fields go to the warnings list. The adapter derives the offered PCD set at runtime from the installed EDK II tree (parse the PCD declarations in the OvmfPkg DSC and the DEC files it references, via BaseTools). No hard-coded PCD list.

#### 10. `bios_build_gui/build_runner.py` (Create)

*   **Type / Scope**: Python module — Build Runner (Interface I3).
*   **Proposed Changes**: `run_build(command, workdir, log_path, on_line, cancel_event)` — invokes the command as a subprocess (no shell; `shell=False`), merges stdout/stderr via `stderr=subprocess.STDOUT` so the streams reach the callback as one ordered stream, sets the EDK II environment variables (`WORKSPACE`, `PACKAGES_PATH`, `EDK_TOOLS_PATH`, `CONF_PATH`, `PYTHON_COMMAND`) in the subprocess environment (it does not source `edksetup.sh`), streams output line-by-line to the `on_line` callback, writes the full output to `log_path` (`<project>/logs/build-<timestamp>.log`), and returns the exit code. Success is exit code 0 only; the runner does not parse output for success. Pre-build phase: if the BaseTools binaries are missing, build them once (`make -C BaseTools`, output streamed to the log) and then proceed. Teardown: checks `cancel_event` between output lines and terminates the subprocess if set. Also provides `extract_error_block(log_path) -> str` (the error-block rule in I3). The `on_line` callback runs on the worker thread; the GUI forwards lines to the GUI thread via a Qt signal.

#### 11. `bios_build_gui/prereq.py` (Create)

*   **Type / Scope**: Python module — Prerequisite Checker (Interface I5).
*   **Proposed Changes**: `check(settings) -> list[CheckResult]` returns a list of check results (EDK II tree, BaseTools binaries, GCC, QEMU, Python/PyQt), each a `CheckResult` dataclass with `name`, `status` (`ok` | `missing` | `mismatched`), `found_version`, `expected_version`, and `fix_hint`. One function per check item, so a new prerequisite can be added without touching the others. Per-item criteria are in I5. `expected_version` values are hard-coded constants derived from the Pinned versions table.

#### 12. `bios_build_gui/boot_verify.py` (Create)

*   **Type / Scope**: Python module — Boot Verifier (Interface I4).
*   **Proposed Changes**: `verify_boot(image_path, timeout=60, cancel_event=None) -> (booted, output)` — launches QEMU with the pinned command (`qemu-system-x86_64 -machine q35 -m 1024 -drive if=pflash,format=raw,unit=0,file=<image_path>,readonly=on -display none -serial stdio`, with `-accel kvm` when `/dev/kvm` is available, otherwise TCG), watches serial output for the substring `Shell>` (the UEFI shell prompt), returns early when it is observed, kills QEMU after the verdict (and on cancellation via `cancel_event` or GUI close), and returns the verdict plus captured output. The QEMU binary name is `qemu-system-x86_64` (X64 only in v1).

#### 13. `bios_build_gui/gui/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Empty.

#### 14. `bios_build_gui/gui/main_window.py` (Create)

*   **Type / Scope**: Python module — PyQt6 GUI.
*   **Proposed Changes**: The main window with a fixed platform label ("Platform: OvmfPkg"), a step indicator (five steps: select platform → configure → build → verify, current step highlighted), a config editor (fields bound to the Config Model, with per-field validation errors; PCD editor as a table widget with one row per offered PCD, editable values, and an "Add PCD" row), a build log view (streams lines from the Build Runner via a worker thread — a `QThread` owned by the GUI; the `on_line` callback runs on the worker thread and forwards each line via a Qt signal `log_line(str)` so GUI updates happen on the GUI thread, so the UI stays responsive), and a boot verification panel (shows the output image path/size/timestamp, the QEMU command, a Boot Verify button, and the verdict). A Cancel button is shown during a build and during boot verification; pressing it sets the `cancel_event` and terminates the running subprocess (I3/I4 teardown). A Clean Build action (button) removes `Build/OvmfX64/` before invoking `build` (see I3). File menu: Open config (Ctrl+O), Save config (Ctrl+S), Save As, Import DSC/FDF (Ctrl+I — opens a file picker for the DSC file; the FDF is found alongside it by name, or the user picks it too; unmapped fields are shown in a warnings panel). The GUI calls only the Application Core (config, adapter, runner, prereq, boot verify, settings); it never invokes EDK II or QEMU directly. The Build button is disabled while any prerequisite check is not `ok`. The prerequisite panel has a Re-check button; the check also re-runs automatically when the EDK II path setting changes.

#### 15. `bios_build_gui/main.py` (Create)

*   **Type / Scope**: Python module — GUI entry point.
*   **Proposed Changes**: `main()` launches the GUI. Covered by a smoke test (launch the GUI entry point in a test with a mocked GUI). (There is no headless CLI in v1.)

#### 16. `tests/test_config.py` (Create)

*   **Type / Scope**: Contract tests for Interface I1.
*   **Proposed Changes**: Tests: a valid config passes validation; each invalid field produces the expected field error (with the expected `code`: `unknown_platform`, `unsupported_architecture`, `empty_value`, `invalid_pcd`, `invalid_pcd_value`); unknown `schema_version` is rejected with the version named; JSON round-trip (save then load) preserves the config.

#### 17. `tests/test_settings.py` (Create)

*   **Type / Scope**: Tests for the Settings module.
*   **Proposed Changes**: Tests: `load_settings` returns defaults when the file is missing; save then load preserves the settings; a missing `qemu_path` defaults to the QEMU on PATH.

#### 18. `tests/test_ovmf_adapter.py` (Create)

*   **Type / Scope**: Contract tests for Interface I2 (OvmfPkg).
*   **Proposed Changes**: Tests: `generate` produces a DSC/FDF pair, a build command argument list (no shell string), and the expected output image path; `import` of a known OvmfPkg DSC/FDF (fixtures `tests/fixtures/OvmfPkgX64.dsc`, `tests/fixtures/OvmfPkgX64.fdf`) yields the expected config (`tests/fixtures/expected_config.json`); unmapped DSC fields appear in the warnings list; round-trip (import → generate) preserves PCDs, build target, and architecture.

#### 19. `tests/test_build_runner.py` (Create)

*   **Type / Scope**: Contract tests for Interface I3.
*   **Proposed Changes**: Tests: a command that exits 0 returns 0; a command that exits non-zero returns that code; output lines reach the callback in order; the full output is written to the log file; the command is invoked without a shell (assert `shell=False` via `unittest.mock.patch` on `subprocess.Popen`); cancellation (start a long-running dummy command, set the `cancel_event`, assert the subprocess is terminated and `run_build` returns); `extract_error_block` on a synthetic log with a known error line returns a block containing it plus the surrounding context.

#### 20. `tests/test_prereq.py` (Create)

*   **Type / Scope**: Contract tests for Interface I5.
*   **Proposed Changes**: Tests: each check returns the five fields (`name`, `status`, `found_version`, `expected_version`, `fix_hint`); a missing tool reports `missing` with a fix hint; a mismatched version reports `mismatched` with both versions named; a tarball EDK II tree (no git tags) reports `mismatched` with `found_version` null. Missing-tool simulation sets `settings.edk2_path` to a nonexistent path (or patches `shutil.which` to return None).

#### 21. `tests/test_boot_verify.py` (Create)

*   **Type / Scope**: Contract tests for Interface I4.
*   **Proposed Changes**: Tests: with the fake QEMU (see `tests/conftest.py`) that prints the shell prompt, returns `booted=True`; with a fake QEMU that exits early or times out, returns `booted=False` with captured output; cancellation (mock QEMU, set the `cancel_event`, assert QEMU is killed). Timeout tests use a short timeout (e.g. `timeout=1`). (A live-QEMU test is an integration test, not a unit test — see Verification Plan.)

#### 22. `tests/conftest.py` (Create)

*   **Type / Scope**: pytest fixtures (test harness).
*   **Proposed Changes**: Fixtures: a `tmp_path`-based workspace; a fake-QEMU script (`tests/fake_qemu.py`) placed on PATH for boot-verify tests; a helper to set up a minimal EDK II tree layout for prereq tests.

#### 23. `tests/fake_qemu.py` (Create)

*   **Type / Scope**: Fake QEMU for boot-verify tests.
*   **Proposed Changes**: A fake `qemu-system-x86_64` that prints `Shell>` to stdout and exits 0, or sleeps then exits, controlled by an env var.

#### 24. `tests/fixtures/OvmfPkgX64.dsc` (Create)

*   **Type / Scope**: Test fixture (copy of the stock OvmfPkg DSC from the pinned EDK II tree, committed to the repo).
*   **Proposed Changes**: Used by `tests/test_ovmf_adapter.py` for the import tests.

#### 25. `tests/fixtures/OvmfPkgX64.fdf` (Create)

*   **Type / Scope**: Test fixture (copy of the stock OvmfPkg FDF from the pinned EDK II tree, committed to the repo).
*   **Proposed Changes**: Used by `tests/test_ovmf_adapter.py` for the import tests.

#### 26. `tests/fixtures/expected_config.json` (Create)

*   **Type / Scope**: Test fixture (the expected config for the OvmfPkgX64 DSC/FDF fixtures).
*   **Proposed Changes**: platform OvmfPkg, architecture X64, build target DEBUG, toolchain GCC, the PCDs from the fixture DSC. Used by `tests/test_ovmf_adapter.py`.

#### 27. `.gitignore` (Create)

*   **Type / Scope**: Repo hygiene (ignore list).
*   **Proposed Changes**: Ignores `__pycache__/`, `*.pyc`, the virtual environment directory (`.venv`), generated DSC/FDF output (`Generated/`), build logs (`logs/`), build outputs (`Build/`, `OVMF.fd`, `OVMF_CODE.fd`, `OVMF_VARS.fd`), user configs (`configs/`), and the settings file (`settings.json`).

### Implementation order

Contract tests are the first batch of work, before any implementation. Then the Application Core is built bottom-up (no GUI until the engine works headless), then the GUI, then end-to-end verification.

1.  **Contract tests first (I1–I5):** Write `tests/test_config.py`, `tests/test_settings.py`, `tests/test_ovmf_adapter.py`, `tests/test_build_runner.py`, `tests/test_prereq.py`, `tests/test_boot_verify.py` (plus `tests/conftest.py` and `tests/fake_qemu.py`) against the Interface Registry (I1–I5) before implementing the modules. The tests define the interfaces; the implementation must satisfy them.
2.  **Config Model + Settings + OvmfPkg adapter (generate only):** `config.py`, `settings.py`, `adapters/__init__.py`, `adapters/ovmf.py` (`generate` only). Verify: a config generates a DSC/FDF pair, a build command, and the expected image path.
3.  **Build Runner + Prerequisite Checker:** `build_runner.py`, `prereq.py`. Verify: a pytest integration test that calls the core functions directly reports the prerequisites and runs a real EDK II build headless, producing OVMF.fd.
4.  **Boot Verifier:** `boot_verify.py`. Verify: a pytest integration test that calls the core functions directly boots OVMF.fd in QEMU to the UEFI shell.
5.  **Import:** `adapters/ovmf.py` (`import`). Verify: import a known OvmfPkg DSC/FDF (the `tests/fixtures/` files), edit a setting, rebuild, and confirm the image still boots (CUJ 4).
6.  **GUI:** `gui/main_window.py` (PyQt6). Verify: the GUI drives the same core functions; the Build button is disabled when prerequisites fail; the log view streams live; the UI stays responsive during a build (type in the editor and confirm the keystroke registers while a build runs — a manual smoke test with named actions).
7.  **End-to-end verification:** Run CUJ 1–4 on the implementation machine (the user's home PC, one command at a time). Record the pinned versions validated (including the exact GCC version, the exact PyQt6 version, and the exact Python version) in the design doc, and record the G2 demo artifact (recorded demo video + README screenshots) as the G2 acceptance. Also verify the 60 s boot timeout against a DEBUG build under TCG and record the measurement.

### Verification Plan

*   **Compilation/Build**: `python -m compileall bios_build_gui` (all modules compile, including `main.py`). `pip install -e .` installs the console script; `pip install -r requirements.txt` installs PyQt6; `pip install -r requirements-dev.txt` installs pytest, pytest-cov, and ruff.
*   **Unit Tests**: `pytest tests/` — all contract tests pass. The GUI module is excluded from the coverage target (tested by end-to-end verification instead).
*   **Static Analysis & Linting**: `ruff check bios_build_gui/ tests/` — zero errors.
*   **Test Coverage Requirement**: 80%+ branch coverage on the Application Core, measured with `pytest --cov=bios_build_gui --cov-report=term-missing`.
*   **E2E/Integration**: On the implementation machine (user's home PC): (a) a pytest integration test that calls the core functions directly builds OvmfPkg X64 DEBUG and produces OVMF.fd; (b) QEMU boots OVMF.fd to the UEFI shell (CUJ 1); (c) the prerequisite check reports a wrong EDK II path with the wrong path named and a fix hint (CUJ 2); (d) a build with an invalid config, run through the GUI, shows a field error in the editor and no build is attempted (Error semantics "Config validation failure" category); (e) import of an existing OvmfPkg DSC/FDF, edit, rebuild, and boot (CUJ 4); (f) G2 demo artifact: a recorded demo video (screen capture of a full CUJ 1 run — configure → build → boot to the UEFI shell) and a screenshot set in the README (GUI panels, build log, boot verdict) exist and show a successful build + boot. Each E2E step is run on the user's PC, with the output recorded.

--------------------------------------------------------------------------------

## Draft Exit Gate (2026-11-09)

Run per EGM §2.5 (EGM = Elephant-Goldfish Model — the design process used for this document) after the last section was approved and before sending to Review. **Resolve correction (2026-11-09):** Review found that the gate's original Check 1 ("No conflicting definitions found") and Check 4 ("No stale references remain") claims were FALSE — the `import` signature conflict (I2 vs item 6) and the stale NG4/NG5 entries existed at gate time and were found by Review, not by the gate. Both were fixed in Resolve (see the resolve fix report). The corrected checks are below.

### Check 1 — Interface audit: PASS (after Resolve fix)

I1–I5 are defined exactly once, in the Interface Registry (Technical Plan). Every other mention is a reference by ID (I1–I5), not a rewrite. The Error semantics section is organised by interface ID (a reference pattern). Resolve fix: I2's `import` signature is now `import(dsc_path, fdf_path) -> (config, warnings)`, matching item 6 and item 15 — the conflict Review found is closed. No conflicting definitions remain.

### Check 2 — Cross-reference audit: PASS (after fix)

No `§x.y` numeric references are used, so none can dangle. Terms fixed by the gate: PCD is now expanded at first use (CUJ 1: "PCDs — Platform Configuration Database entries"); FD/FV are expanded at first use (Import design: "FD — Flash Device — regions, FV — Firmware Volume — names"); DSC/FDF are introduced as "EDK II platform description files (DSC — Description file — / FDF — Flash Description File)"; EDK II/QEMU standard terms (NOOPT — no optimisation; pflash — parallel flash; GCC toolchain tag — a toolchain-family name, not a compiler version) are defined at first use. The UEFI shell is defined at first use (CUJ 1). The Application Core is defined as a component (Technical Plan Overview).

### Check 3 — Cross-cutting traces: PASS (after fix)

Each concern has a single definition, traced end to end. Written artefacts below.

#### Credentials

| Consumer | Credential source | When obtained | If missing |
|---|---|---|---|
| (none) | — | — | — |

The tool performs no authenticated operations: it invokes only local, unauthenticated tools (EDK II `build`, QEMU) and reads local files. There is no login, no token, no password, no network call anywhere in the design. This is a deliberate "none", not an empty cell.

#### Teardown (subprocess lifecycle)

| Exit path | Build subprocess | QEMU subprocess |
|---|---|---|
| Normal completion | Exits on its own; runner returns exit code | Killed by verifier after verdict |
| User presses Cancel | Terminated by runner (I3, via `cancel_event`) | Terminated by verifier (I4, via `cancel_event`) |
| GUI closed mid-run | Terminated by runner/verifier before close | Terminated by verifier before close |
| Build fails (non-zero) | Already exited; nothing to terminate | Not started |

Gate finding: teardown was undefined in the first draft. Fixed by adding the termination rules to I3, I4, the Build execution details, the GUI (Cancel button), and `build_runner.py` / `boot_verify.py`. (The CLI SIGINT row was removed in Resolve — there is no CLI in v1.)

#### Log

| Item | Definition |
|---|---|
| Writer | Build Runner (I3) |
| Path | `<project>/logs/build-<timestamp>.log` (`logs/` created if needed; `<project>` is the tool's repository root) |
| Content | Full stdout/stderr of the build, in order (merged via `stderr=subprocess.STDOUT`) |
| Shown to user | Log path shown in the GUI after every build; log view streams live |
| On failure | Same file; the GUI extracts the failing error block from it (per the `extract_error_block` rule in I3) |
| Retention | Keep the last 10 build logs in `<project>/logs/` |

Gate finding: the log directory was unspecified in the first draft. Fixed by pinning `<project>/logs/build-<timestamp>.log` in I3, the Build execution details, and `build_runner.py`.

#### Exit code

| Situation | Exit code / verdict |
|---|---|
| Build succeeds | Runner returns 0; GUI reports success |
| Build fails | Runner returns the non-zero code; GUI shows the error + log path |
| Config invalid | No build is invoked; GUI shows field errors |
| Prerequisite fails | No build is invoked; GUI disables Build |
| Boot verify: shell prompt seen | `booted=True` |
| Boot verify: timeout / early QEMU exit | `booted=False` with captured output (build verdict unaffected) |

(The CLI rows were removed in Resolve — there is no CLI in v1.)

#### Error handling

Defined once in the Error semantics section (5 categories: prerequisite, config validation, generation, build, boot verification), each referencing its interface by ID. No second definition elsewhere. The error-block extraction rule is defined in I3 (`extract_error_block`); the retry path is defined as the ordinary flow (fix the configuration and press Build again; no separate Retry button or dialog).

### Default-configuration walkthrough (paper dry-run)

Default config (the example in the Technical Plan — OvmfPkg, X64, DEBUG, GCC, no PCDs):

1.  Startup: settings are loaded (`settings.json`); the Prerequisite Checker runs. EDK II tree found at the configured path (version edk2-stable202608), BaseTools binaries found, GCC 12+ found, QEMU 11.1.3 found, Python 3.10+ and PyQt6 found. All `ok`. Build button enabled.
2.  User selects platform OvmfPkg (a fixed label in v1). The GUI imports the OvmfPkg adapter directly and shows its fields (architecture, build target, toolchain, PCDs).
3.  User leaves the defaults (X64, DEBUG, GCC) and presses Build. Config Model validates: platform has an adapter, architecture X64 is supported, build target and toolchain are in the adapter's supported sets. Validation passes. The config is saved to `<project>/configs/last.json`.
4.  OvmfPkg adapter `generate` writes the wrapper DSC and the generated FDF into `<workspace>/Generated/` and returns the build command (`build -p Generated/OvmfPkgX64.dsc -a X64 -t GCC -b DEBUG`) and the expected image path (`Build/OvmfX64/DEBUG_GCC/FV/OVMF.fd`).
5.  Build Runner checks the BaseTools binaries (present), sets the EDK II environment variables, invokes the build as a subprocess, streams output lines to the GUI log view, and writes the full log to `<project>/logs/build-<timestamp>.log`.
6.  Build exits 0. The GUI shows the output image path, size, and timestamp, plus the QEMU boot command.
7.  User presses Boot Verify. Boot Verifier launches `qemu-system-x86_64 -machine q35 -m 1024 -drive if=pflash,format=raw,unit=0,file=<image_path>,readonly=on -display none -serial stdio` (with `-accel kvm` if available). Serial output contains `Shell>` within 60 s. Verdict: `booted=True`. QEMU is killed.
8.  Walkthrough completes with no stuck step. The only step that depends on the machine is step 5 (the build itself), which is the EDK II toolchain's job, not the tool's.

Gate finding: step 4 exposed that `generate` did not return the image path, so the GUI had no defined source for it. Fixed by extending I2 to return `image_path` (and updating the data flow, `ovmf.py`, and `test_ovmf_adapter.py`).

### Check 4 — Decision-change propagation: PASS (after Resolve fix)

All 7 Open Questions (Q1–Q7) were resolved during Draft and their resolutions are reflected consistently: Q1/Q2/Q3 in the Pinned versions table; Q4 (PyQt) in the GUI component and `requirements.txt`; Q5 (separate) in Alternatives F and the file list (no OpenBMC GUI files or imports); Q6 (import) in the Adapter, CUJ 4, the tests, and Implementation order step 5; Q7 (schema v1) in I1 and `config.py`. Resolve fix: the stale NG4/NG5 entries (which still said "to be decided in the Technical Plan" after the decisions were made) were rewritten to the decided scope; the resolved questions Q1, Q3–Q7 were removed from the Open Questions section (per the template), leaving Q2 (partially resolved) as the only open question. No stale references to the pre-decision wording remain.

### Check 5 — Provenance: PASS (after fix)

Version pins cite their sources in Additional Resources (EDK II release announcements, QEMU download page, CVE-2026-97631 advisory, EDK II GitHub repo, TianoCore). User decisions are dated 2026-11-09. Gate finding: the build-time estimate ("5–15 minutes") was stated as if measured. Fixed in NFR Performance to "initial estimate: 5–15 minutes for an incremental build depending on the machine; a clean build is longer; to be measured at implementation, not a recorded measurement."

### Check 6 — No residual markers: PASS (after Resolve fix)

No `[NEEDS CLARIFICATION]` marker remains in the design body — the only occurrence of the string is this sentence, which names the marker itself. The resolved Open Questions (Q1, Q3–Q7) were removed from the section in Resolve; Q2 remains open (partially resolved — the exact GCC patch version is still to be recorded).

### Check 7 — Brief comparison: PASS (after fix)

Brief decisions D1–D7 each map to a design element: D1 (real tool) → Overview, G1, Alternatives A/C; D2 (EDK II + OvmfPkg + QEMU boot verify) → Technical Plan, CUJ 1; D3 (desktop Python GUI; OpenBMC GUI relationship to pin in Draft) → Q5 resolved (separate), GUI component; D4 (board model exists, v1 exercises only OvmfPkg) → I1 (schema v1 without `board`; v2 adds it), Alternatives G; D5 (pinned versions, upgrades are tested events) → Pinned versions table, NFR Rollout; D6 (startup check, live progress, actionable errors, saved log, output path + next step) → I5, I3, Error semantics, CUJ 2/3; D7 (schema versioned from v1) → I1 `schema_version`, Q7. Rejected options (web demo, OpenBMC variant, script-gen) → Alternatives A/B/C. Gate finding: the brief's Theme 2 tension (desktop + real toolchain is the least showable form; design must scope the demo to his machine or include scripted toolchain setup) was not addressed in the first draft. Fixed by scoping the demo to his machine (screen share/video) in the Overview, and adding scripted toolchain setup to Future Improvements.

### Check 8 — Red Flags: PASS (after fix)

No field is repurposed (`board` and `features` are not in schema v1 at all — they arrive in schema v2 when a real consumer exists). Error semantics exist for all 5 categories. Gate finding: the UEFI shell prompt detection string was an implementation-dependent behaviour not elevated into the contract. Fixed by pinning the substring `Shell>` in I4 and in `boot_verify.py`. No spec references an expired source (pins are current as of 2026-11-09).

--------------------------------------------------------------------------------
