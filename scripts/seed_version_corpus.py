#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Seed apps/*/versions/<ver>/{lifecycle,dependencies,recipe,README} for ALL apps."""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"

DISTROS = ("arch", "debian", "fedora", "rhel", "ubuntu")


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def distro_block(
    *,
    releases: dict[str, list[str]],
    packages: dict[str, dict[str, list[str]]],
    install: dict[str, dict[str, str]],
    notes: dict[str, str] | None = None,
) -> dict:
    notes = notes or {}
    out: dict = {}
    for d in DISTROS:
        out[d] = {
            "releases": releases.get(d, []),
            "packages": packages.get(d, {"build": [], "runtime": []}),
            "install": install.get(d, {"build": "", "runtime": ""}),
        }
        if d in notes:
            out[d]["notes"] = notes[d]
    return out


def linux_deps(
    *,
    version: str,
    summary: str,
    common_build: list[str],
    common_runtime: list[str],
    packages: dict[str, dict[str, list[str]]],
    install: dict[str, dict[str, str]],
    releases: dict[str, list[str]] | None = None,
    compiler_notes: str = "",
    references: list[str] | None = None,
    notes: dict[str, str] | None = None,
) -> dict:
    releases = releases or {
        "arch": ["rolling"],
        "debian": ["12", "13"],
        "fedora": ["40", "41", "42"],
        "rhel": ["8", "9"],
        "ubuntu": ["22.04", "24.04"],
    }
    return {
        "version": version,
        "summary": summary,
        "compiler_notes": compiler_notes,
        "references": references or [],
        "os": {
            "linux": {
                "common": {"build": common_build, "runtime": common_runtime},
                "distros": distro_block(
                    releases=releases, packages=packages, install=install, notes=notes
                ),
            },
            "macos": {
                "notes": "Secondary target; prefer Linux for the compiler farm.",
                "install": {
                    "build": "xcode-select --install || true\nbrew install python openssl",
                    "runtime": "brew install openssl",
                },
            },
            "windows": {
                "notes": "Use WSL2 (Ubuntu) and follow os.linux.distros.ubuntu.",
            },
        },
    }


def version_readme(app: str, ver: str, life: dict) -> str:
    return textwrap.dedent(
        f"""\
        # {app} {ver}

        | Field | Value |
        |-------|-------|
        | Channel | `{life.get("channel", "—")}` |
        | Status | **{life.get("status", "unknown")}** |
        | Released | {life.get("released") or "—"} |
        | Security support ends | {life.get("security_support_ends") or "—"} |
        | Support ended | {life.get("support_ended") or "—"} |

        Source: {life.get("source") or "—"}

        ## Files in this folder

        | File | Purpose |
        |------|---------|
        | `lifecycle.json` | Support / EOL metadata |
        | `dependencies.yaml` | Required packages + Linux distro install commands |
        | `recipe.json` | Fetch / build / test / csperf hooks for csfarm |
        """
    )


def dump_yaml(data: dict) -> str:
    """Minimal YAML dumper (no PyYAML required for nested dict/list/str)."""

    def emit(obj: object, indent: int = 0) -> list[str]:
        sp = "  " * indent
        lines: list[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{sp}{k}:")
                    lines.extend(emit(v, indent + 1))
                elif v is None:
                    lines.append(f"{sp}{k}: null")
                elif isinstance(v, bool):
                    lines.append(f"{sp}{k}: {'true' if v else 'false'}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{sp}{k}: {v}")
                else:
                    s = str(v)
                    if "\n" in s:
                        lines.append(f"{sp}{k}: |")
                        for ln in s.splitlines():
                            lines.append(f"{sp}  {ln}")
                    elif any(c in s for c in ":#{}[]&*!|>'\"%@`"):
                        lines.append(f'{sp}{k}: "{s}"')
                    else:
                        lines.append(f"{sp}{k}: {s}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    lines.append(f"{sp}-")
                    lines.extend(emit(item, indent + 1))
                else:
                    s = str(item)
                    if any(c in s for c in ":#{}[]&*!|>'\"%@`"):
                        lines.append(f'{sp}- "{s}"')
                    else:
                        lines.append(f"{sp}- {s}")
        return lines

    return "\n".join(emit(data)) + "\n"


def seed_version(
    app_dir: Path,
    *,
    ver: str,
    life: dict,
    deps: dict,
    recipe: dict,
) -> None:
    d = app_dir / "versions" / ver
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    write_json(d / "lifecycle.json", life)
    (d / "dependencies.yaml").write_text(dump_yaml(deps), encoding="utf-8")
    write_json(d / "recipe.json", recipe)
    (d / "README.md").write_text(
        version_readme(app_dir.name, ver, life), encoding="utf-8"
    )


def reset_versions(app_dir: Path) -> None:
    v = app_dir / "versions"
    if v.exists():
        shutil.rmtree(v)
    v.mkdir(parents=True)


# --- shared apt/dnf package helpers -------------------------------------------------

def c_build_packages() -> dict[str, dict[str, list[str]]]:
    return {
        "arch": {
            "build": ["base-devel", "git", "python", "openssl", "zlib"],
            "runtime": ["openssl", "zlib"],
        },
        "debian": {
            "build": [
                "build-essential",
                "git",
                "python3",
                "libssl-dev",
                "zlib1g-dev",
            ],
            "runtime": ["libssl3", "zlib1g"],
        },
        "fedora": {
            "build": ["gcc", "gcc-c++", "git", "python3", "openssl-devel", "zlib-devel"],
            "runtime": ["openssl", "zlib"],
        },
        "rhel": {
            "build": ["gcc", "gcc-c++", "git", "python3", "openssl-devel", "zlib-devel"],
            "runtime": ["openssl", "zlib"],
        },
        "ubuntu": {
            "build": [
                "build-essential",
                "git",
                "python3",
                "libssl-dev",
                "zlib1g-dev",
            ],
            "runtime": ["libssl3", "zlib1g"],
        },
    }


def c_install() -> dict[str, dict[str, str]]:
    return {
        "arch": {
            "build": "sudo pacman -Syu --needed base-devel git python openssl zlib",
            "runtime": "sudo pacman -S --needed openssl zlib",
        },
        "debian": {
            "build": "sudo apt-get update && sudo apt-get install -y build-essential git python3 libssl-dev zlib1g-dev",
            "runtime": "sudo apt-get update && sudo apt-get install -y libssl3 zlib1g",
        },
        "fedora": {
            "build": "sudo dnf install -y gcc gcc-c++ git python3 openssl-devel zlib-devel",
            "runtime": "sudo dnf install -y openssl zlib",
        },
        "rhel": {
            "build": "sudo dnf install -y gcc gcc-c++ git python3 openssl-devel zlib-devel",
            "runtime": "sudo dnf install -y openssl zlib",
        },
        "ubuntu": {
            "build": "sudo apt-get update && sudo apt-get install -y build-essential git python3 libssl-dev zlib1g-dev",
            "runtime": "sudo apt-get update && sudo apt-get install -y libssl3 zlib1g",
        },
    }


def seed_mongodb() -> None:
    app = APPS / "database" / "mongodb"
    reset_versions(app)
    series = [
        ("8.3", "stable", "2026-05", "2029-10-31", None, "supported", False, "r8.3.0"),
        ("8.2", "rapid", "2025-09", None, "2026-07-31", "expired", True, "r8.2.0"),
        ("8.1", "rapid", "2025-06", None, "2025-09-30", "expired", True, "r8.1.0"),
        ("8.0", "stable", "2024-10", "2029-10-31", None, "supported", False, "r8.0.0"),
        ("7.3", "rapid", "2024-03", None, "2024-10-02", "expired", True, "r7.3.0"),
        ("7.2", "rapid", "2024-01", None, "2024-03-27", "expired", True, "r7.2.0"),
        ("7.1", "rapid", "2023-10", None, "2024-01-23", "expired", True, "r7.1.0"),
        ("7.0", "stable", "2023-08", "2027-08-31", None, "supported", False, "r7.0.14"),
    ]
    pkgs = c_build_packages()
    for d in DISTROS:
        pkgs[d]["build"] = list(
            dict.fromkeys(
                pkgs[d]["build"]
                + (["python-pip", "curl"] if d == "arch" else ["python3-pip", "libcurl4-openssl-dev"] if d in ("debian", "ubuntu") else ["python3-pip", "libcurl-devel"])
            )
        )
        if d == "arch":
            pkgs[d]["runtime"] = ["openssl", "curl", "zlib"]
        elif d in ("debian", "ubuntu"):
            pkgs[d]["runtime"] = ["libssl3", "libcurl4", "zlib1g"]
        else:
            pkgs[d]["runtime"] = ["openssl", "libcurl", "zlib"]
    installs = c_install()
    for ver, channel, released, sec, ended, status, atlas, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "atlas_only": atlas,
            "source": "https://endoflife.date/mongodb",
            "notes": "Compiler-farm series folder; pin git ref in recipe.json.",
        }
        deps = linux_deps(
            version=ver,
            summary=f"MongoDB {ver} source-build dependencies",
            common_build=[
                "python3",
                "pip",
                "gcc/g++ or clang/clang++",
                "git",
                "openssl devel",
                "libcurl devel",
                "zlib devel",
            ],
            common_runtime=["openssl", "libcurl", "zlib"],
            packages=pkgs,
            install=installs,
            compiler_notes="C++ / SCons. Prefer clang-17+/gcc-12+ for 8.x; clang-16+/gcc-11+ for 7.x.",
            references=[
                "https://endoflife.date/mongodb",
                "https://github.com/mongodb/mongo",
            ],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/mongodb/mongo.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {
                "system": "custom",
                "commands": [
                    ["python3", "buildscripts/scons.py", "install-mongod", "--disable-warnings-as-errors"]
                ],
            },
            "test": {"command": ["./build/install/bin/mongod", "--version"], "timeout_sec": 120},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 3,
                    "workload": ["./build/install/bin/mongod", "--version"],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "database/mongodb",
            "type": "database",
            "name": "mongodb",
            "display_name": "MongoDB",
            "languages": ["c++"],
            "build_systems": ["scons"],
            "default_version": "8.3",
            "correctness": "smoke",
            "perf_backend": "cpu",
            "description": "Document DB — all EOL series under versions/ with deps per Linux distro.",
            "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
        },
    )


def seed_mysql() -> None:
    app = APPS / "database" / "mysql"
    reset_versions(app)
    series = [
        ("9.7", "lts", "2026-04-21", "2034-04-21", None, "supported", "mysql-9.7.2"),
        ("9.6", "innovation", "2026-01-20", None, "2026-04-21", "expired", "mysql-9.6.1"),
        ("9.5", "innovation", "2025-10-21", None, "2026-01-20", "expired", "mysql-9.5.2"),
        ("8.4", "lts", "2024-04-10", "2032-04-30", None, "supported", "mysql-8.4.11"),
        ("8.0", "lts", "2018-04-08", None, "2026-04-30", "expired", "mysql-8.0.46"),
    ]
    pkgs = c_build_packages()
    for d in DISTROS:
        extra = {
            "arch": ["cmake", "ncurses", "libaio"],
            "debian": ["cmake", "libncurses-dev", "libaio-dev", "bison"],
            "fedora": ["cmake", "ncurses-devel", "libaio-devel", "bison"],
            "rhel": ["cmake", "ncurses-devel", "libaio-devel", "bison"],
            "ubuntu": ["cmake", "libncurses-dev", "libaio-dev", "bison"],
        }[d]
        pkgs[d]["build"] = list(dict.fromkeys(pkgs[d]["build"] + extra))
    installs = c_install()
    for ver, channel, released, sec, ended, status, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "source": "https://endoflife.date/mysql",
            "notes": "Oracle MySQL LTS/Innovation lines.",
        }
        deps = linux_deps(
            version=ver,
            summary=f"MySQL {ver} CMake source-build dependencies",
            common_build=["cmake", "gcc/g++ or clang", "bison", "ncurses devel", "openssl devel", "libaio"],
            common_runtime=["openssl", "ncurses", "libaio"],
            packages=pkgs,
            install=installs,
            compiler_notes="C/C++ via CMake. Use farm toolchains.enabled for CC/CXX.",
            references=["https://endoflife.date/mysql", "https://github.com/mysql/mysql-server"],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/mysql/mysql-server.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {
                "system": "cmake",
                "args": ["-DWITH_DEBUG=OFF", "-DCMAKE_BUILD_TYPE=Release", "-DDOWNLOAD_BOOST=1"],
            },
            "test": {"command": ["ctest", "--output-on-failure", "-j", "4"], "timeout_sec": 7200},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 3,
                    "workload": ["./runtime_output_directory/mysqld", "--version"],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "database/mysql",
            "type": "database",
            "name": "mysql",
            "display_name": "MySQL",
            "languages": ["c", "c++"],
            "build_systems": ["cmake"],
            "default_version": "9.7",
            "correctness": "upstream_tests",
            "perf_backend": "cpu",
            "description": "MySQL — LTS/Innovation series folders with per-distro deps.",
            "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
        },
    )


def seed_postgres() -> None:
    app = APPS / "database" / "postgres"
    reset_versions(app)
    series = [
        ("18", "stable", "2025-09-25", "2030-11-14", None, "supported", "REL_18_STABLE"),
        ("17", "stable", "2024-09-26", "2029-11-08", None, "supported", "REL_17_STABLE"),
        ("16", "stable", "2023-09-14", "2028-11-09", None, "supported", "REL_16_STABLE"),
        ("15", "stable", "2022-10-13", "2027-11-11", None, "supported", "REL_15_STABLE"),
        ("14", "stable", "2021-09-30", "2026-11-12", None, "supported", "REL_14_STABLE"),
        ("13", "stable", "2020-09-24", None, "2025-11-13", "expired", "REL_13_STABLE"),
    ]
    pkgs = c_build_packages()
    for d in DISTROS:
        extra = {
            "arch": ["bison", "flex", "readline", "libxml2", "icu"],
            "debian": ["bison", "flex", "libreadline-dev", "libxml2-dev", "libicu-dev"],
            "fedora": ["bison", "flex", "readline-devel", "libxml2-devel", "libicu-devel"],
            "rhel": ["bison", "flex", "readline-devel", "libxml2-devel", "libicu-devel"],
            "ubuntu": ["bison", "flex", "libreadline-dev", "libxml2-dev", "libicu-dev"],
        }[d]
        pkgs[d]["build"] = list(dict.fromkeys(pkgs[d]["build"] + extra))
    installs = c_install()
    for ver, channel, released, sec, ended, status, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "source": "https://endoflife.date/postgresql",
            "notes": "PostgreSQL major version (5-year support).",
        }
        deps = linux_deps(
            version=ver,
            summary=f"PostgreSQL {ver} configure/meson source-build dependencies",
            common_build=["bison", "flex", "readline devel", "openssl devel", "icu devel", "libxml2"],
            common_runtime=["openssl", "readline", "icu", "libxml2"],
            packages=pkgs,
            install=installs,
            compiler_notes="Mostly C. Good clang/gcc matrix target.",
            references=["https://endoflife.date/postgresql", "https://github.com/postgres/postgres"],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/postgres/postgres.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {"system": "configure", "args": ["--enable-debug"]},
            "test": {"command": ["make", "check"], "timeout_sec": 7200},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 3,
                    "workload": ["./src/backend/postgres", "--version"],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "database/postgres",
            "type": "database",
            "name": "postgres",
            "display_name": "PostgreSQL",
            "languages": ["c"],
            "build_systems": ["configure", "meson"],
            "default_version": "18",
            "correctness": "upstream_tests",
            "perf_backend": "cpu",
            "description": "PostgreSQL majors with lifecycle + per-distro deps.",
            "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
        },
    )


def seed_sqlite() -> None:
    app = APPS / "database" / "sqlite"
    reset_versions(app)
    # SQLite only supports major 3; seed recent release lines as corpus pins
    series = [
        ("3.53", "stable", "2026-07-24", None, None, "supported", "version-3.53.4"),
        ("3.50", "stable", "2025-05-29", None, None, "supported", "version-3.50.0"),
        ("3.49", "stable", "2025-02-06", None, None, "supported", "version-3.49.0"),
        ("3.47", "stable", "2024-10-21", None, None, "supported", "version-3.47.0"),
        ("3.46", "stable", "2024-05-23", None, None, "supported", "version-3.46.1"),
    ]
    pkgs = c_build_packages()
    installs = c_install()
    for ver, channel, released, sec, ended, status, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "source": "https://endoflife.date/sqlite",
            "notes": "Only SQLite 3 is supported upstream; folders are release-line pins for the farm.",
        }
        deps = linux_deps(
            version=ver,
            summary=f"SQLite {ver} configure/make dependencies",
            common_build=["gcc or clang", "tcl (for tests)", "readline optional"],
            common_runtime=[],
            packages=pkgs,
            install=installs,
            compiler_notes="Pure C — excellent compiler codegen / sanitize target.",
            references=["https://endoflife.date/sqlite", "https://github.com/sqlite/sqlite"],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/sqlite/sqlite.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {"system": "configure", "args": []},
            "test": {"command": ["make", "test"], "timeout_sec": 3600},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 5,
                    "workload": ["./sqlite3", ":memory:", "select 1;"],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "database/sqlite",
            "type": "database",
            "name": "sqlite",
            "display_name": "SQLite",
            "languages": ["c"],
            "build_systems": ["configure", "make"],
            "default_version": "3.53",
            "correctness": "upstream_tests",
            "perf_backend": "cpu",
            "description": "SQLite 3.x release-line folders with per-distro deps.",
            "flags": {
                "cflags": ["-DSQLITE_ENABLE_FTS5"],
                "cxxflags": [],
                "ldflags": [],
            },
        },
    )


def seed_redis() -> None:
    app = APPS / "systems" / "redis"
    reset_versions(app)
    series = [
        ("8.10", "stable", "2026-07-29", None, None, "supported", "8.10.1"),
        ("8.8", "stable", "2026-05-25", None, None, "supported", "8.8.2"),
        ("8.6", "stable", "2026-02-11", None, None, "supported", "8.6.6"),
        ("8.4", "stable", "2025-11-18", None, None, "supported", "8.4.6"),
        ("8.2", "stable", "2025-08-04", "2030-09-01", None, "supported", "8.2.9"),
        ("8.0", "stable", "2025-05-02", "2026-12-01", None, "supported", "8.0.6"),
        ("7.4", "stable", "2024-07-29", "2029-12-01", None, "supported", "7.4.11"),
        ("7.2", "stable", "2023-08-15", "2029-12-01", None, "supported", "7.2.16"),
        ("6.2", "stable", "2021-02-22", "2027-04-01", None, "supported", "6.2.24"),
        ("7.0", "stable", "2022-04-27", None, "2024-07-29", "expired", "7.0.15"),
    ]
    pkgs = c_build_packages()
    installs = c_install()
    for ver, channel, released, sec, ended, status, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "source": "https://endoflife.date/redis",
            "notes": "Redis OSS release line.",
        }
        deps = linux_deps(
            version=ver,
            summary=f"Redis {ver} Make source-build dependencies",
            common_build=["gcc or clang", "make", "pkg-config", "openssl (TLS builds)"],
            common_runtime=[],
            packages=pkgs,
            install=installs,
            compiler_notes="Mostly C. Fast compile cycle for toolchain matrices.",
            references=["https://endoflife.date/redis", "https://github.com/redis/redis"],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/redis/redis.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {"system": "make", "args": ["BUILD_TLS=no"]},
            "test": {"command": ["./src/redis-server", "--version"], "timeout_sec": 120},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 5,
                    "workload": ["./src/redis-benchmark", "-n", "10000", "-q"],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "systems/redis",
            "type": "systems",
            "name": "redis",
            "display_name": "Redis",
            "languages": ["c"],
            "build_systems": ["make"],
            "default_version": "8.10",
            "correctness": "smoke",
            "perf_backend": "cpu",
            "description": "Redis release lines with lifecycle + per-distro deps.",
            "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
        },
    )


def seed_ffmpeg() -> None:
    app = APPS / "media" / "ffmpeg"
    reset_versions(app)
    series = [
        ("9.0", "stable", "2026-08-04", None, None, "supported", "n9.0.1"),
        ("8.1", "stable", "2026-03-16", None, None, "supported", "n8.1.2"),
        ("8.0", "stable", "2025-08-22", None, None, "supported", "n8.0.3"),
        ("7.1", "lts", "2024-09-30", None, None, "supported", "n7.1.5"),
        ("7.0", "stable", "2024-04-05", None, "2026-06-22", "expired", "n7.0.3"),
        ("6.1", "stable", "2023-11-11", None, None, "supported", "n6.1.6"),
        ("5.1", "lts", "2022-07-22", None, None, "supported", "n5.1.10"),
        ("4.4", "stable", "2021-04-08", None, None, "supported", "n4.4.8"),
    ]
    pkgs = c_build_packages()
    for d in DISTROS:
        extra = {
            "arch": ["yasm", "nasm", "pkgconf"],
            "debian": ["yasm", "nasm", "pkg-config"],
            "fedora": ["yasm", "nasm", "pkgconf"],
            "rhel": ["yasm", "nasm", "pkgconf"],
            "ubuntu": ["yasm", "nasm", "pkg-config"],
        }[d]
        pkgs[d]["build"] = list(dict.fromkeys(pkgs[d]["build"] + extra))
    installs = c_install()
    for ver, channel, released, sec, ended, status, ref in series:
        life = {
            "version": ver,
            "channel": channel,
            "released": released,
            "security_support_ends": sec,
            "support_ended": ended,
            "status": status,
            "source": "https://endoflife.date/ffmpeg",
            "notes": "FFmpeg release / LTS line for vectorization & codegen stress.",
        }
        deps = linux_deps(
            version=ver,
            summary=f"FFmpeg {ver} configure source-build dependencies",
            common_build=["yasm/nasm", "pkg-config", "gcc or clang"],
            common_runtime=[],
            packages=pkgs,
            install=installs,
            compiler_notes="Heavy C + asm — strong -O3 / LTO / march matrix candidate.",
            references=["https://endoflife.date/ffmpeg", "https://github.com/FFmpeg/FFmpeg"],
        )
        recipe = {
            "version": ver,
            "source": {"url": "https://github.com/FFmpeg/FFmpeg.git", "ref": ref},
            "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
            "build": {
                "system": "configure",
                "args": ["--disable-doc", "--disable-network", "--cc=${CC}"],
            },
            "test": {"command": ["make", "fate-tiny"], "timeout_sec": 3600},
            "perf": {
                "csperf": {
                    "enabled": True,
                    "backend": "cpu",
                    "warmup_runs": 1,
                    "repeat_runs": 5,
                    "workload": [
                        "./ffmpeg",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc=duration=2:size=640x360:rate=30",
                        "-f",
                        "null",
                        "-",
                    ],
                }
            },
        }
        seed_version(app, ver=ver, life=life, deps=deps, recipe=recipe)
    write_json(
        app / "app.json",
        {
            "id": "media/ffmpeg",
            "type": "media",
            "name": "ffmpeg",
            "display_name": "FFmpeg",
            "languages": ["c", "assembly"],
            "build_systems": ["configure"],
            "default_version": "9.0",
            "correctness": "fate_smoke",
            "perf_backend": "cpu",
            "description": "FFmpeg release/LTS lines with lifecycle + per-distro deps.",
            "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
        },
    )


def main() -> None:
    seed_mongodb()
    seed_mysql()
    seed_postgres()
    seed_sqlite()
    seed_redis()
    seed_ffmpeg()
    print("Seeded version corpora for: mongodb mysql postgres sqlite redis ffmpeg")


if __name__ == "__main__":
    main()
