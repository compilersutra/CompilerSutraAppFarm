# SPDX-License-Identifier: Apache-2.0
"""Runner / ISA metadata for honest multi-runner results.

Self-contained: ``csfarm`` does not require compilersutra-perf. Optional extra
``.[perf]`` can still be installed for real ``csperf`` measurement.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

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


@dataclass(frozen=True)
class RunnerPlan:
    """Resolved runner label for a plan/run (not a HW perf claim)."""

    runner: str
    isa: str
    emulated: bool


def normalize_isa(value: str | None) -> str:
    if not value:
        return detect_host_isa()
    key = value.strip().lower().replace("-", "_")
    return _ISA_ALIASES.get(key, key)


def detect_host_isa() -> str:
    return normalize_isa(platform.machine())


def is_emulated_runner(runner: str) -> bool:
    return runner.startswith("qemu")


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
    emu = is_emulated_runner(r) if emulated is None else bool(emulated)
    return r, arch, emu


def qemu_user_binary(isa: str | None = None) -> str:
    return f"qemu-{normalize_isa(isa)}"


def resolve_qemu_user_bin(isa: str | None = None) -> str:
    return qemu_user_binary(isa)


def plan_runner(
    *,
    runner: str | None = None,
    isa: str | None = None,
    emulated: bool | None = None,
) -> RunnerPlan:
    r, arch, emu = resolve_runner_meta(runner=runner, isa=isa, emulated=emulated)
    return RunnerPlan(runner=r, isa=arch, emulated=emu)
