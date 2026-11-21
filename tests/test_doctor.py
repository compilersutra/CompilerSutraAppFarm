# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import csfarm.doctor as doctor

ROOT = Path(__file__).resolve().parents[1]


def _stub_which(monkeypatch: object, which: object) -> None:
    monkeypatch.setattr(doctor.shutil, "which", which)


def test_doctor_reports_working_compilers(monkeypatch: object) -> None:
    _stub_which(monkeypatch, lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(doctor, "_probe_compiler", lambda cc: (True, "ok"))
    checks = doctor.run_doctor(ROOT)
    by_name = {c.name: c for c in checks}
    assert by_name["clang_compile"].ok is True
    assert by_name["gcc_compile"].ok is True
    assert by_name["compiler_smoke"].ok is True
    assert doctor.doctor_ok(checks) is True


def test_doctor_accepts_one_working_compiler(monkeypatch: object) -> None:
    _stub_which(monkeypatch, lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        doctor,
        "_probe_compiler",
        lambda cc: (False, "missing SDK") if cc.endswith("clang") else (True, "ok"),
    )
    checks = doctor.run_doctor(ROOT)
    by_name = {c.name: c for c in checks}
    assert by_name["clang_compile"].ok is False
    assert by_name["gcc_compile"].ok is True
    assert by_name["compiler_smoke"].ok is True
    assert doctor.doctor_ok(checks) is True


def test_doctor_fails_when_no_compiler_can_compile(monkeypatch: object) -> None:
    _stub_which(monkeypatch, lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(doctor, "_probe_compiler", lambda cc: (False, "missing SDK"))
    checks = doctor.run_doctor(ROOT)
    by_name = {c.name: c for c in checks}
    assert by_name["compiler_smoke"].ok is False
    assert "missing SDK" in by_name["compiler_smoke"].detail
    assert doctor.doctor_ok(checks) is False


def test_probe_compiler_captures_failure_detail(tmp_path: Path) -> None:
    cc = tmp_path / "broken-cc"
    cc.write_text("#!/bin/sh\necho 'no such sysroot: MacOSX.sdk' >&2\nexit 1\n", encoding="utf-8")
    cc.chmod(0o755)
    ok, detail = doctor._probe_compiler(str(cc))
    assert ok is False
    assert "no such sysroot" in detail
