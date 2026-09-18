# SPDX-License-Identifier: Apache-2.0
"""Runner / ISA metadata for honest multi-runner results."""

from __future__ import annotations

import platform

# Host / Docker / QEMU / bare metal — keep small and explicit.
KNOWN_RUNNERS = frozenset({"host", "docker", "qemu-user", "hw"})

_ISA_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "i386": "x86",
    "i686": "x86",
    "aarch64": "aarch64",
    "arm64": "aarch64",
    "armv7l": "arm",
    "armv8l": "aarch64",
    "ppc64le": "ppc64le",
    "riscv64": "riscv64",
    "s390x": "s390x",
}


def normalize_isa(value: str | None) -> str:
    if not value:
        return detect_host_isa()
    key = value.strip().lower().replace("-", "_")
    return _ISA_ALIASES.get(key, key)


def detect_host_isa() -> str:
    return normalize_isa(platform.machine())


def resolve_runner_meta(
    *,
    runner: str | None = None,
    isa: str | None = None,
    emulated: bool | None = None,
) -> tuple[str, str, bool]:
    """
    Return ``(runner, isa, emulated)``.

    Defaults: runner=host, isa=host machine, emulated=True only for qemu-*.
    """
    r = (runner or "host").strip().lower()
    if r not in KNOWN_RUNNERS:
        known = ", ".join(sorted(KNOWN_RUNNERS))
        raise ValueError(f"Unknown runner {runner!r}; known: {known}")
    arch = normalize_isa(isa)
    emu = r.startswith("qemu") if emulated is None else bool(emulated)
    return r, arch, emu
