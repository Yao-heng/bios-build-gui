"""Config Model (Interface I1).

Schema v1. A config is a JSON document with ``schema_version`` ``"1"`` and
fields ``platform``, ``architecture``, ``build_target``, ``toolchain`` and
``pcds`` (PCD name -> value, both strings).

Validation (``validate``) takes the platform adapter as a parameter; this
module does not import the adapters package. The adapter must provide:

* ``PLATFORM`` — the platform name it serves (e.g. ``"OvmfPkg"``).
* ``SUPPORTED_ARCHITECTURES`` — the architectures it supports.
* ``SUPPORTED_BUILD_TARGETS`` — the build targets it supports.
* ``SUPPORTED_TOOLCHAINS`` — the EDK II toolchain tags it supports.
* ``get_pcd_names()`` — the PCD set derived at runtime from the installed
  EDK II tree (optional; if the adapter does not provide it, PCD-key
  validation is skipped). If it raises (e.g. the adapter's workspace is
  not configured), the exception propagates: that is a setup error, not a
  field error.

Error codes: ``unknown_platform``, ``unsupported_architecture``,
``empty_value`` (empty build_target / toolchain), ``unsupported_build_target``,
``unsupported_toolchain`` (a non-empty value that is not in the adapter's
supported set — rejected so a crafted config value cannot inject
unexpected arguments into the build command), ``invalid_pcd`` (a PCD name
that is not in the adapter's derived PCD set), ``invalid_pcd_value`` (a
PCD value that is not a string).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1"


@dataclass
class FieldError:
    """One field-level validation error."""

    field: str
    message: str
    code: str


@dataclass
class BuildConfig:
    """A build configuration (schema v1)."""

    schema_version: str = SCHEMA_VERSION
    platform: str = "OvmfPkg"
    architecture: str = "X64"
    build_target: str = "DEBUG"
    toolchain: str = "GCC5"
    pcds: dict[str, str] = field(default_factory=dict)


def load_config(path) -> BuildConfig:
    """Load a config from a JSON file.

    Raises ``ValueError`` (naming the version) when ``schema_version`` is
    not ``"1"``, when a required field is missing, or when the JSON is
    invalid. Raises ``FileNotFoundError`` when the file does not exist.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a JSON object.")
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported config schema_version {version!r} in {path}; "
            f'this tool supports schema_version "{SCHEMA_VERSION}".'
        )
    for name in ("platform", "architecture", "build_target", "toolchain", "pcds"):
        if name not in data:
            raise ValueError(f"Config file {path} is missing required field {name!r}.")
    if not isinstance(data["pcds"], dict):
        raise ValueError(f"Config file {path}: field 'pcds' must be a JSON object.")
    return BuildConfig(
        schema_version=data["schema_version"],
        platform=data["platform"],
        architecture=data["architecture"],
        build_target=data["build_target"],
        toolchain=data["toolchain"],
        pcds=dict(data["pcds"]),
    )


def save_config(config: BuildConfig, path) -> None:
    """Save a config to a JSON file (parent directories are created)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": config.schema_version,
        "platform": config.platform,
        "architecture": config.architecture,
        "build_target": config.build_target,
        "toolchain": config.toolchain,
        "pcds": dict(config.pcds),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(config: BuildConfig, adapter) -> list[FieldError]:
    """Validate a config against the adapter's supported sets.

    Returns a (possibly empty) list of field errors; the GUI shows them
    per field. No build is invoked when the list is non-empty.
    """
    errors: list[FieldError] = []

    platform = getattr(adapter, "PLATFORM", None)
    if config.platform != platform:
        errors.append(
            FieldError(
                field="platform",
                message=f"Unknown platform {config.platform!r}; no adapter is available for it.",
                code="unknown_platform",
            )
        )

    supported_arch = getattr(adapter, "SUPPORTED_ARCHITECTURES", set())
    if config.architecture not in supported_arch:
        errors.append(
            FieldError(
                field="architecture",
                message=(
                    f"Architecture {config.architecture!r} is not supported by "
                    f"the {config.platform} adapter."
                ),
                code="unsupported_architecture",
            )
        )

    _validate_choice(
        errors,
        field="build_target",
        value=config.build_target,
        supported=getattr(adapter, "SUPPORTED_BUILD_TARGETS", set()),
        unsupported_code="unsupported_build_target",
    )
    _validate_choice(
        errors,
        field="toolchain",
        value=config.toolchain,
        supported=getattr(adapter, "SUPPORTED_TOOLCHAINS", set()),
        unsupported_code="unsupported_toolchain",
    )

    _validate_pcds(errors, config, adapter)
    return errors


def _validate_choice(errors, *, field, value, supported, unsupported_code):
    if not isinstance(value, str) or not value:
        errors.append(
            FieldError(
                field=field,
                message=f"{field} must be a non-empty string.",
                code="empty_value",
            )
        )
    elif value not in supported:
        errors.append(
            FieldError(
                field=field,
                message=f"{field} {value!r} is not supported by this adapter.",
                code=unsupported_code,
            )
        )


def _validate_pcds(errors, config, adapter):
    if not isinstance(config.pcds, dict):
        errors.append(
            FieldError(
                field="pcds",
                message="pcds must be an object mapping PCD names to values.",
                code="invalid_pcd",
            )
        )
        return
    get_pcd_names = getattr(adapter, "get_pcd_names", None)
    known = get_pcd_names() if callable(get_pcd_names) else None
    for name, value in config.pcds.items():
        if known is not None and name not in known:
            errors.append(
                FieldError(
                    field="pcds",
                    message=(
                        f"PCD {name!r} is not in the PCD set of the installed "
                        "EDK II tree for this platform."
                    ),
                    code="invalid_pcd",
                )
            )
        if not isinstance(value, str):
            errors.append(
                FieldError(
                    field="pcds",
                    message=f"PCD {name!r} has a non-string value {value!r}.",
                    code="invalid_pcd_value",
                )
            )
