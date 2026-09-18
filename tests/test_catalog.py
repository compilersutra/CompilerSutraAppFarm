# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from csfarm.patterns import OverlayKind, Registry
from csfarm.resolve import FarmSession


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_linguistic_order() -> None:
    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")
    types = session.catalog.iter_types()
    assert types == sorted(types, key=str.casefold)
    names = [a.name for a in session.catalog.iter_apps("database")]
    assert names == sorted(names, key=str.casefold)
    assert "sqlite" in names and "mongodb" in names
    assert len(session.apps) >= 100


def test_registries_linguistic() -> None:
    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")
    assert session.toolchains.keys() == sorted(session.toolchains.keys(), key=str.casefold)
    assert "clang" in session.toolchains.keys()
    assert "sanitize" in session.presets.keys()
    assert session.apps.keys() == sorted(session.apps.keys(), key=str.casefold)
    assert session.apps.contains("database/sqlite")


def test_overlay_compose_and_pipeline() -> None:
    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")
    job = session.plan(
        "database/sqlite",
        toolchain_id="clang",
        preset_name="sanitize",
        extra_cflags=["-march=native"],
    )
    flags = job.compiler.flags.cflags
    assert "-fsanitize=address,undefined" in flags
    assert "-O2" not in flags
    assert "-DSQLITE_THREADSAFE=1" in flags
    assert "-DSQLITE_ENABLE_FTS5" in flags
    assert "-march=native" in flags
    kinds = [o["kind"] for o in job.overlays]
    assert OverlayKind.ALL.value in kinds
    assert OverlayKind.PRESET.value in kinds
    assert OverlayKind.FARM_APP.value in kinds
    assert OverlayKind.CLI.value in kinds
    assert any(o["key"] == "sanitize" for o in job.overlays)
    assert job.csperf_command is not None
    assert job.csperf_command[0] == "csperf"
    assert any(r["name"] == "resolve_flags" for r in job.pipeline_results)


def test_generic_all_and_type_overlay() -> None:
    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")
    job = session.plan("media/ffmpeg", toolchain_id="gcc")
    assert "-O2" in job.compiler.flags.cflags
    assert "-fno-strict-aliasing" in job.compiler.flags.cflags
    assert job.compiler.cc == "gcc"


def test_enabled_toolchains_from_config() -> None:
    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")
    assert session.defaults.toolchains.enabled == ["clang", "gcc"]
    assert session.enabled_toolchains() == ["clang", "gcc"]
    assert session.defaults.toolchains.default == "clang"
    assert "aocc" in session.toolchains.keys()
    assert "custom-clang" in session.toolchains.keys()
    details = session.toolchain_details()
    assert details["clang"]["cc"] == "clang"
    assert details["custom-clang"]["in_enabled_list"] is False


def test_registry_duplicate() -> None:
    reg: Registry[int] = Registry("t")
    reg.register("a", 1)
    try:
        reg.register("a", 2)
        assert False, "expected KeyError"
    except KeyError:
        pass
    reg.register("a", 2, overwrite=True)
    assert reg.get("a") == 2
