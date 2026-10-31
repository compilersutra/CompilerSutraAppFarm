# SPDX-License-Identifier: Apache-2.0
"""Host readiness checks — compilers, fetch tools, optional qemu/csperf."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from csfarm.runner_meta import detect_host_isa


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    required: bool
    detail: str


def _which(cmd: str) -> Check:
    path = shutil.which(cmd)
    required = cmd in {"git", "cmake", "make", "curl", "python3"}
    if path:
        return Check(cmd, True, required, path)
    return Check(cmd, False, required, "not on PATH")


def run_doctor(root: Path) -> list[Check]:
    checks: list[Check] = [
        Check(
            "python",
            sys.version_info >= (3, 11),
            True,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        Check("host_isa", True, True, detect_host_isa()),
        _which("git"),
        _which("cmake"),
        _which("make"),
        _which("curl"),
        _which("clang"),
        _which("gcc"),
        _which("autoreconf"),
        _which("meson"),
        _which("nasm"),
        _which("qemu-aarch64"),
        _which("csperf"),
    ]
    have_cc = shutil.which("clang") or shutil.which("gcc")
    checks.append(
        Check("c_compiler", bool(have_cc), True, have_cc or "need clang or gcc")
    )
    catalog = root / "apps"
    n_apps = len(list(catalog.glob("*/*/app.json"))) if catalog.is_dir() else 0
    checks.append(Check("catalog", n_apps >= 1, True, f"{n_apps} apps"))
    tier1 = root / "configs" / "tier1.yaml"
    checks.append(Check("tier1.yaml", tier1.is_file(), False, str(tier1) if tier1.is_file() else "missing"))
    return checks


def doctor_ok(checks: list[Check]) -> bool:
    return all(c.ok for c in checks if c.required)
