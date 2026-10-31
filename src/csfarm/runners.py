# SPDX-License-Identifier: Apache-2.0
"""Execution stages: fetch → build → test → perf (PassManager-style)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from csfarm.models import Recipe
from csfarm.patterns import (
    JobContext,
    Pipeline,
    ResolveFlagsStage,
    Stage,
    StageResult,
    StageStatus,
    build_csperf_argv,
)


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int | None = None,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **env}
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        proc = subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(exc))
    except OSError as exc:
        proc = subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(exc))
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"$ {' '.join(cmd)}\ncwd={cwd}\nexit={proc.returncode}\n\n"
                f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n\n"
            )
    return proc


def _expand(cmd: list[str], env: dict[str, str]) -> list[str]:
    out: list[str] = []
    for part in cmd:
        s = part
        for key, val in env.items():
            s = s.replace(f"${{{key}}}", val).replace(f"${key}", val)
        out.append(s)
    return out


def _jobs() -> str:
    return str(max(1, (os.cpu_count() or 2)))


def _with_tool_path(env: dict[str, str]) -> dict[str, str]:
    """Prefer project venv tools (meson, ninja) and local tools/ (nasm, libtirpc) on PATH."""
    out = dict(env)
    try:
        import sys

        bits: list[str] = []
        venv_bin = str(Path(sys.executable).resolve().parent)
        repo_root = Path(__file__).resolve().parents[2]
        repo_tools = repo_root / "tools"
        repo_tools_bin = repo_tools / "bin"
        for candidate in (venv_bin, str(repo_tools_bin)):
            if candidate and Path(candidate).is_dir():
                bits.append(candidate)
        path = out.get("PATH", os.environ.get("PATH", ""))
        for b in reversed(bits):
            if b not in path.split(":"):
                path = f"{b}:{path}"
        out["PATH"] = path
        if repo_tools.is_dir():
            pc = str(repo_tools / "lib" / "pkgconfig")
            if (repo_tools / "lib" / "pkgconfig").is_dir():
                out["PKG_CONFIG_PATH"] = f"{pc}:{out.get('PKG_CONFIG_PATH', os.environ.get('PKG_CONFIG_PATH', ''))}"
            out["CMAKE_PREFIX_PATH"] = f"{repo_tools}:{out.get('CMAKE_PREFIX_PATH', os.environ.get('CMAKE_PREFIX_PATH', ''))}"
            out["CPATH"] = f"{repo_tools / 'include'}:{out.get('CPATH', os.environ.get('CPATH', ''))}"
            out["LIBRARY_PATH"] = f"{repo_tools / 'lib'}:{out.get('LIBRARY_PATH', os.environ.get('LIBRARY_PATH', ''))}"
            out["LD_LIBRARY_PATH"] = f"{repo_tools / 'lib'}:{out.get('LD_LIBRARY_PATH', os.environ.get('LD_LIBRARY_PATH', ''))}"
    except Exception:  # noqa: BLE001
        pass
    return out


def _ensure_configure(build_root: Path, env: dict[str, str], log: Path) -> str | None:
    """Create ./configure if missing or stale. Returns error detail or None."""
    configure = build_root / "configure"
    configure_ac = build_root / "configure.ac"
    configure_in = build_root / "configure.in"
    stale = False
    if configure.is_file() and configure_ac.is_file():
        if configure_ac.stat().st_mtime > configure.stat().st_mtime:
            stale = True
        m4_dir = build_root / "m4"
        if m4_dir.is_dir():
            for m4 in m4_dir.glob("*.m4"):
                if m4.stat().st_mtime > configure.stat().st_mtime:
                    stale = True
                    break
    if configure.is_file() and not stale:
        return None

    # GNU packages from git often need a tarball version stamp
    tarball_version = build_root / ".tarball-version"
    if not tarball_version.is_file():
        for _marker in (build_root / "NEWS", build_root / "README"):
            pass
        # best-effort: leave for recipe; stub git-version-gen if missing
    git_version_gen = build_root / "build-aux" / "git-version-gen"
    if not git_version_gen.is_file() and (configure_ac.is_file() or configure_in.is_file()):
        git_version_gen.parent.mkdir(parents=True, exist_ok=True)
        if not tarball_version.is_file():
            tarball_version.write_text("0.0.0\n", encoding="utf-8")
        git_version_gen.write_text(
            "#!/bin/sh\ncat \"${1:-.tarball-version}\" 2>/dev/null || cat .tarball-version\n",
            encoding="utf-8",
        )
        git_version_gen.chmod(0o755)

    if (build_root / "bootstrap").is_file():
        proc = _run(["sh", "./bootstrap"], cwd=build_root, env=env, timeout=900, log_path=log)
        if (build_root / "configure").is_file():
            return None
        if proc.returncode != 0:
            # fall through to autogen/autoreconf
            pass
    if (build_root / "bootstrap.sh").is_file():
        proc = _run(["sh", "./bootstrap.sh"], cwd=build_root, env=env, timeout=900, log_path=log)
        if (build_root / "configure").is_file():
            return None
    if (build_root / "autogen.sh").is_file():
        proc = _run(["sh", "./autogen.sh"], cwd=build_root, env=env, timeout=900, log_path=log)
        if proc.returncode != 0 and not (build_root / "configure").is_file():
            return f"autogen.sh failed: {proc.stderr[-400:]}"
        if (build_root / "configure").is_file():
            return None
    if configure_ac.is_file() or configure_in.is_file():
        for cmd in (
            ["autoreconf", "-fi"],
            ["autoconf"],
        ):
            if not shutil.which(cmd[0]):
                continue
            proc = _run(cmd, cwd=build_root, env=env, timeout=900, log_path=log)
            if (build_root / "configure").is_file():
                return None
            if proc.returncode != 0:
                return f"{' '.join(cmd)} failed: {proc.stderr[-400:]}"
    return "no configure script and could not generate one"


class FetchStage(Stage):
    name = "fetch"

    def run(self, ctx: JobContext) -> StageResult:
        recipe: Recipe = ctx.extras["recipe"]  # type: ignore[assignment]
        source_dir = Path(str(ctx.extras["source_dir"]))
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        url = recipe.source.url
        ref = recipe.source.ref
        log = Path(ctx.result_dir) / "logs" / "fetch.log"
        kind = (recipe.source.kind or "").lower()
        archive_exts = (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".zip")
        is_archive = kind == "archive" or any(url.rstrip("/").endswith(ext) for ext in archive_exts)

        try:
            if is_archive:
                marker = source_dir / ".csfarm_archive_url"
                if source_dir.exists() and marker.is_file() and marker.read_text(encoding="utf-8").strip() == url:
                    ctx.work_dir = str(source_dir)
                    ctx.extras["src_dir"] = str(source_dir)
                    return StageResult(
                        self.name, StageStatus.OK, detail=f"archive cached → {source_dir}", artifacts={"src_dir": str(source_dir)}
                    )
                if source_dir.exists():
                    shutil.rmtree(source_dir)
                archive = source_dir.parent / f"{source_dir.name}.archive"
                proc = _run(
                    ["curl", "-fsSL", "-o", str(archive), url],
                    cwd=source_dir.parent,
                    env={},
                    timeout=1800,
                    log_path=log,
                )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"download failed: {proc.stderr[-400:]}")
                extract_dir = source_dir.parent / f"{source_dir.name}.extract"
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                extract_dir.mkdir(parents=True, exist_ok=True)
                name = archive.name
                if url.endswith(".zip") or name.endswith(".zip"):
                    proc = _run(
                        ["unzip", "-q", str(archive), "-d", str(extract_dir)],
                        cwd=extract_dir,
                        env={},
                        timeout=600,
                        log_path=log,
                    )
                else:
                    proc = _run(
                        ["tar", "-xf", str(archive), "-C", str(extract_dir)],
                        cwd=extract_dir,
                        env={},
                        timeout=600,
                        log_path=log,
                    )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"extract failed: {proc.stderr[-400:]}")
                kids = [p for p in extract_dir.iterdir()]
                if len(kids) == 1 and kids[0].is_dir():
                    kids[0].rename(source_dir)
                    shutil.rmtree(extract_dir, ignore_errors=True)
                else:
                    extract_dir.rename(source_dir)
                marker = source_dir / ".csfarm_archive_url"
                marker.write_text(url + "\n", encoding="utf-8")
                archive.unlink(missing_ok=True)
                ctx.work_dir = str(source_dir)
                ctx.extras["src_dir"] = str(source_dir)
                return StageResult(
                    self.name, StageStatus.OK, detail=f"{url} → {source_dir}", artifacts={"src_dir": str(source_dir)}
                )

            if source_dir.exists() and not (source_dir / ".git").is_dir():
                shutil.rmtree(source_dir)

            if (source_dir / ".git").is_dir():
                _run(["git", "remote", "set-url", "origin", url], cwd=source_dir, env={}, timeout=60)
                for fetch_cmd in (
                    ["git", "fetch", "--depth", "1", "origin", "tag", ref],
                    ["git", "fetch", "--depth", "1", "origin", ref],
                    ["git", "fetch", "--tags", "--depth", "1", "origin"],
                ):
                    proc = _run(fetch_cmd, cwd=source_dir, env={}, timeout=900, log_path=log)
                    if proc.returncode == 0:
                        break
                for checkout in (ref, f"tags/{ref}", "FETCH_HEAD"):
                    proc = _run(
                        ["git", "checkout", "-f", checkout],
                        cwd=source_dir,
                        env={},
                        timeout=120,
                        log_path=log,
                    )
                    if proc.returncode == 0:
                        break
                _run(
                    ["git", "submodule", "update", "--init", "--recursive", "--depth", "1"],
                    cwd=source_dir,
                    env={},
                    timeout=1800,
                    log_path=log,
                )
            else:
                if source_dir.exists():
                    shutil.rmtree(source_dir)
                proc = _run(
                    [
                        "git",
                        "clone",
                        "--recurse-submodules",
                        "--depth",
                        "1",
                        "--branch",
                        ref,
                        url,
                        str(source_dir),
                    ],
                    cwd=source_dir.parent,
                    env={},
                    timeout=1800,
                    log_path=log,
                )
                if proc.returncode != 0:
                    if source_dir.exists():
                        shutil.rmtree(source_dir)
                    proc = _run(
                        ["git", "clone", "--recurse-submodules", url, str(source_dir)],
                        cwd=source_dir.parent,
                        env={},
                        timeout=1800,
                        log_path=log,
                    )
                    if proc.returncode == 0:
                        proc = _run(
                            ["git", "checkout", "-f", ref],
                            cwd=source_dir,
                            env={},
                            timeout=120,
                            log_path=log,
                        )
                        _run(
                            ["git", "submodule", "update", "--init", "--recursive"],
                            cwd=source_dir,
                            env={},
                            timeout=1800,
                            log_path=log,
                        )

            if proc.returncode != 0:
                return StageResult(
                    name=self.name,
                    status=StageStatus.FAILED,
                    detail=f"git failed ({proc.returncode}): {proc.stderr[-400:]}",
                )

            ctx.work_dir = str(source_dir)
            ctx.extras["src_dir"] = str(source_dir)
            return StageResult(
                name=self.name,
                status=StageStatus.OK,
                detail=f"{url}@{ref} → {source_dir}",
                artifacts={"src_dir": str(source_dir)},
            )
        except subprocess.TimeoutExpired:
            return StageResult(name=self.name, status=StageStatus.FAILED, detail="fetch timed out")
        except OSError as exc:
            return StageResult(name=self.name, status=StageStatus.FAILED, detail=str(exc))


class BuildStage(Stage):
    name = "build"

    def run(self, ctx: JobContext) -> StageResult:
        recipe: Recipe = ctx.extras["recipe"]  # type: ignore[assignment]
        src = Path(str(ctx.extras["src_dir"]))
        build_root = Path(str(ctx.extras["build_dir"]))
        env = _with_tool_path(dict(ctx.compiler.env_map()))
        # Help tools find compilers
        env.setdefault("CMAKE_C_COMPILER", env["CC"])
        env.setdefault("CMAKE_CXX_COMPILER", env["CXX"])
        log = Path(ctx.result_dir) / "logs" / "build.log"
        if log.exists():
            log.unlink()

        try:
            if build_root.exists():
                shutil.rmtree(build_root)
            build_root.mkdir(parents=True)
            shutil.copytree(
                src,
                build_root,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", ".github"),
                ignore_dangling_symlinks=True,
                symlinks=True,
            )
            ctx.extras["build_src"] = str(build_root)

            # App-specific prep hooks via recipe id in extras
            app_id = ctx.app_id
            system = recipe.build.system

            # busybox: need defconfig first
            if app_id.endswith("/busybox"):
                proc = _run(
                    ["make", "defconfig", f"CC={env['CC']}", f"HOSTCC={env['CC']}"],
                    cwd=build_root,
                    env=env,
                    timeout=300,
                    log_path=log,
                )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"busybox defconfig: {proc.stderr[-400:]}")

            if system == "configure":
                err = _ensure_configure(build_root, env, log)
                if err:
                    return StageResult(self.name, StageStatus.FAILED, err)
                # Prefer clang/gcc via env; some projects want CC= explicitly in configure
                conf_env = dict(env)
                args = _expand(["./configure", *recipe.build.args], conf_env)
                proc = _run(args, cwd=build_root, env=conf_env, timeout=900, log_path=log)
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"configure failed: {proc.stderr[-500:]}")
                proc = _run(["make", f"-j{_jobs()}"], cwd=build_root, env=env, timeout=7200, log_path=log)
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"make failed: {proc.stderr[-500:]}")

            elif system == "make":
                args = _expand(
                    [
                        "make",
                        f"-j{_jobs()}",
                        *recipe.build.args,
                        f"CC={env['CC']}",
                        f"CXX={env['CXX']}",
                        f"CFLAGS={env['CFLAGS']}",
                        f"CXXFLAGS={env['CXXFLAGS']}",
                    ],
                    env,
                )
                proc = _run(args, cwd=build_root, env=env, timeout=7200, log_path=log)
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"make failed: {proc.stderr[-500:]}")

            elif system == "cmake":
                bdir = build_root / "build"
                cmake_args = [
                    "cmake",
                    "-S",
                    str(build_root),
                    "-B",
                    str(bdir),
                    f"-DCMAKE_C_COMPILER={env['CC']}",
                    f"-DCMAKE_CXX_COMPILER={env['CXX']}",
                    f"-DCMAKE_C_FLAGS={env['CFLAGS']}",
                    f"-DCMAKE_CXX_FLAGS={env['CXXFLAGS']}",
                    "-DCMAKE_BUILD_TYPE=Release",
                    *_expand(recipe.build.args, env),
                ]
                proc = _run(cmake_args, cwd=build_root, env=env, timeout=900, log_path=log)
                if proc.returncode != 0:
                    return StageResult(
                        self.name, StageStatus.FAILED, f"cmake configure failed: {proc.stderr[-500:]}"
                    )
                proc = _run(
                    ["cmake", "--build", str(bdir), "-j", _jobs()],
                    cwd=build_root,
                    env=env,
                    timeout=7200,
                    log_path=log,
                )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"cmake build failed: {proc.stderr[-500:]}")
                # Keep tree root as cwd so recipes can use ./build/...
                ctx.extras["build_src"] = str(build_root)
                env["PATH"] = f"{bdir}:{bdir / 'bin'}:{env.get('PATH', os.environ.get('PATH', ''))}"
                ctx.extras["run_env"] = env

            elif system == "meson":
                proc = _run(
                    ["meson", "setup", "build", "--buildtype=release"],
                    cwd=build_root,
                    env=env,
                    timeout=900,
                    log_path=log,
                )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"meson setup failed: {proc.stderr[-500:]}")
                proc = _run(
                    ["meson", "compile", "-C", "build", "-j", _jobs()],
                    cwd=build_root,
                    env=env,
                    timeout=7200,
                    log_path=log,
                )
                if proc.returncode != 0:
                    return StageResult(self.name, StageStatus.FAILED, f"meson compile failed: {proc.stderr[-500:]}")

            elif system == "custom":
                for cmd in recipe.build.commands:
                    args = _expand(cmd, env)
                    proc = _run(args, cwd=build_root, env=env, timeout=7200, log_path=log)
                    if proc.returncode != 0:
                        return StageResult(
                            self.name,
                            StageStatus.FAILED,
                            f"custom build failed ({args[0]}): {proc.stderr[-500:]}",
                        )
            else:
                return StageResult(self.name, StageStatus.FAILED, f"unknown build system: {system}")

            return StageResult(
                name=self.name,
                status=StageStatus.OK,
                detail=f"{system} OK @ {build_root}",
                artifacts={"build_src": str(ctx.extras["build_src"])},
            )
        except subprocess.TimeoutExpired:
            return StageResult(self.name, StageStatus.FAILED, "build timed out")
        except OSError as exc:
            return StageResult(self.name, StageStatus.FAILED, str(exc))


def _run_env(ctx: JobContext) -> dict[str, str]:
    env = _with_tool_path(dict(ctx.compiler.env_map()))
    extra = ctx.extras.get("run_env")
    if isinstance(extra, dict):
        env.update({str(k): str(v) for k, v in extra.items()})
    build_src = Path(str(ctx.extras["build_src"]))
    path_bits = [
        str(build_src),
        str(build_src / "build"),
        str(build_src / "build" / "bin"),
        str(build_src / "src"),
        str(build_src / "apps"),
        env.get("PATH", os.environ.get("PATH", "")),
    ]
    env["PATH"] = ":".join(path_bits)
    return env


def _try_commands(commands: list[list[str]], cwd: Path, env: dict[str, str], timeout: int, log: Path):
    last = None
    for args in commands:
        last = _run(args, cwd=cwd, env=env, timeout=timeout, log_path=log)
        if last.returncode == 0:
            return last, args
    return last, commands[-1] if commands else []


class TestStage(Stage):
    name = "test"

    def run(self, ctx: JobContext) -> StageResult:
        if ctx.extras.get("skip_test"):
            return StageResult(self.name, StageStatus.SKIPPED, "skip_test")
        recipe: Recipe = ctx.extras["recipe"]  # type: ignore[assignment]
        if recipe.test is None or not recipe.test.command:
            return StageResult(self.name, StageStatus.SKIPPED, "no test command")
        build_src = Path(str(ctx.extras["build_src"]))
        env = _run_env(ctx)
        env.update(recipe.test.env)
        timeout = recipe.test.timeout_sec or 1800
        primary = _expand(recipe.test.command, env)
        # Fallbacks: same command under build/ only when that path exists
        candidates = [primary]
        if primary and primary[0].startswith("./") and not primary[0].startswith("./build"):
            for alt in (
                primary[0].replace("./", "./build/", 1),
                f"./build/{primary[0][2:]}",
            ):
                if (build_src / alt[2:]).exists():
                    candidates.append([alt, *primary[1:]])
        log = Path(ctx.result_dir) / "logs" / "test.log"
        if log.exists():
            log.unlink()
        try:
            proc, used = _try_commands(candidates, build_src, env, timeout, log)
            assert proc is not None
            if proc.returncode != 0:
                # soft-pass option for catalog: if binary missing, skip rather than fail whole farm
                if ctx.extras.get("soft_test") and (
                    "No such file" in (proc.stderr + proc.stdout) or proc.returncode == 127
                ):
                    return StageResult(self.name, StageStatus.SKIPPED, f"soft skip: {' '.join(used)}")
                return StageResult(
                    self.name,
                    StageStatus.FAILED,
                    f"test failed: {proc.stderr[-500:] or proc.stdout[-500:]}",
                )
            return StageResult(self.name, StageStatus.OK, detail=" ".join(used))
        except subprocess.TimeoutExpired:
            return StageResult(self.name, StageStatus.FAILED, "test timed out")


class PerfStage(Stage):
    name = "perf"

    def run(self, ctx: JobContext) -> StageResult:
        if ctx.extras.get("skip_perf"):
            return StageResult(self.name, StageStatus.SKIPPED, "skip_perf")
        if not ctx.csperf.enabled:
            return StageResult(self.name, StageStatus.SKIPPED, "csperf disabled")

        build_src = Path(str(ctx.extras["build_src"]))
        out_json = Path(ctx.result_dir) / ctx.csperf.output_name
        workload = list(ctx.csperf.workload)
        if not workload:
            return StageResult(self.name, StageStatus.SKIPPED, "no workload")

        env = _run_env(ctx)
        repeats = max(1, ctx.csperf.repeat_runs)
        warmup = max(0, ctx.csperf.warmup_runs)
        samples: list[float] = []
        log = Path(ctx.result_dir) / "logs" / "perf.log"
        if log.exists():
            log.unlink()

        candidates = [workload]
        if workload and workload[0].startswith("./") and not workload[0].startswith("./build"):
            candidates.append([workload[0].replace("./", "./build/", 1), *workload[1:]])

        try:
            # resolve which workload works
            probe, used = _try_commands(candidates, build_src, env, 120, log)
            if probe is None or probe.returncode != 0:
                if ctx.extras.get("soft_perf"):
                    return StageResult(self.name, StageStatus.SKIPPED, "soft skip perf (binary missing)")
                return StageResult(
                    self.name,
                    StageStatus.FAILED,
                    f"workload missing/failed: {(probe.stderr if probe else '')[-300:]}",
                )
            workload = used

            for _ in range(warmup):
                proc = _run(workload, cwd=build_src, env=env, timeout=600, log_path=log)
                if proc.returncode != 0:
                    return StageResult(
                        self.name,
                        StageStatus.FAILED,
                        f"warmup failed: {proc.stderr[-300:] or proc.stdout[-300:]}",
                    )
            for _ in range(repeats):
                t0 = time.perf_counter()
                proc = _run(workload, cwd=build_src, env=env, timeout=600, log_path=log)
                dt = time.perf_counter() - t0
                if proc.returncode != 0:
                    return StageResult(
                        self.name,
                        StageStatus.FAILED,
                        f"workload failed: {proc.stderr[-300:] or proc.stdout[-300:]}",
                    )
                samples.append(dt)
        except subprocess.TimeoutExpired:
            return StageResult(self.name, StageStatus.FAILED, "perf timed out")

        samples_sorted = sorted(samples)
        mid = samples_sorted[len(samples_sorted) // 2]
        native_path = Path(ctx.result_dir) / "csperf-native.json"
        csperf_bin = shutil.which(ctx.csperf.binary)
        used_csperf = False
        if csperf_bin:
            cmd = build_csperf_argv(ctx.csperf, output=str(native_path))
            native_log = Path(ctx.result_dir) / "logs" / "csperf.log"
            try:
                native = _run(cmd, cwd=build_src, env=env, timeout=600, log_path=native_log)
                used_csperf = native.returncode == 0 and native_path.is_file()
            except (OSError, subprocess.TimeoutExpired):
                used_csperf = False

        payload = {
            "tool": "csperf" if used_csperf else "csfarm",
            "mode": "csperf" if used_csperf else "timed_workload",
            "method": "csperf" if used_csperf else "wall_clock",
            "hardware_counters": bool(used_csperf),
            "backend": ctx.csperf.backend,
            "workload": workload,
            "warmup_runs": warmup,
            "repeat_runs": repeats,
            "samples_sec": samples,
            "median_sec": mid,
            "min_sec": samples_sorted[0],
            "max_sec": samples_sorted[-1],
            "compiler": ctx.compiler.env_map(),
            "app_id": ctx.app_id,
            "version": ctx.version,
            "toolchain_id": ctx.toolchain_id,
            "runner": ctx.extras.get("runner", "host"),
            "isa": ctx.extras.get("isa"),
            "emulated": bool(ctx.extras.get("emulated", False)),
        }
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        ctx.extras["csperf_command"] = workload
        ctx.extras["perf_json"] = str(out_json)
        detail = f"median={mid:.4f}s n={repeats} method={payload['method']} → {out_json}"
        return StageResult(
            self.name,
            StageStatus.OK,
            detail=detail,
            artifacts={"csperf.json": str(out_json)},
        )


def default_run_pipeline() -> Pipeline:
    return Pipeline(
        [
            ResolveFlagsStage(),
            FetchStage(),
            BuildStage(),
            TestStage(),
            PerfStage(),
        ]
    )
