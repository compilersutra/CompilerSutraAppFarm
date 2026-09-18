# SPDX-License-Identifier: Apache-2.0
"""Resolve farm YAML + app/recipe into LLVM-style option bags via OverlayComposer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from csfarm.catalog import AppRef, Catalog
from csfarm.models import (
    CsperfConfig,
    FarmDefaults,
    FlagSet,
    Recipe,
    Toolchain,
    load_farm_defaults,
    load_toolchain,
)
from csfarm.patterns import (
    CompilerOptions,
    CsperfOptions,
    FlagOptions,
    FlagOverlay,
    JobContext,
    OverlayComposer,
    OverlayKind,
    Pipeline,
    Registry,
    StageStatus,
    default_plan_pipeline,
)
from csfarm.runners import default_run_pipeline


def flagset_to_options(fs: FlagSet) -> FlagOptions:
    return FlagOptions.from_lists(fs.cflags, fs.cxxflags, fs.ldflags)


@dataclass(frozen=True)
class ResolvedCompileJob:
    """Serializable job view — PyTorch state_dict analogue for one plan/run."""

    app_id: str
    version: str
    toolchain_id: str
    preset: str | None
    compiler: CompilerOptions
    csperf: CsperfOptions
    overlays: list[dict[str, object]]
    pipeline_results: list[dict[str, object]]
    csperf_command: list[str] | None
    result_dir: str
    mode: str = "plan"
    ok: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "app_id": self.app_id,
            "version": self.version,
            "toolchain_id": self.toolchain_id,
            "preset": self.preset,
            "compiler": {
                "cc": self.compiler.cc,
                "cxx": self.compiler.cxx,
                "flags": self.compiler.flags.as_dict(),
                "env": self.compiler.env_map(),
            },
            "csperf": {
                "enabled": self.csperf.enabled,
                "backend": self.csperf.backend,
                "warmup_runs": self.csperf.warmup_runs,
                "repeat_runs": self.csperf.repeat_runs,
                "workload": list(self.csperf.workload),
            },
            "overlays": self.overlays,
            "pipeline_results": self.pipeline_results,
            "csperf_command": self.csperf_command,
            "result_dir": self.result_dir,
        }


class FarmSession:
    """
    Session owning registries — like an LLVM ``LLVMContext`` + pass registry,
    or a PyTorch package hub for apps/toolchains/presets.
    """

    def __init__(self, root: Path, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self.defaults: FarmDefaults = load_farm_defaults(config_path)
        self.catalog = Catalog(root / self.defaults.farm.apps_root)

        self.toolchains: Registry[Toolchain] = Registry("toolchain")
        self.presets: Registry[FlagOptions] = Registry("preset")
        self.apps: Registry[AppRef] = Registry("app")

        self._load_toolchains()
        self._load_presets()
        self._load_apps()

    def _load_toolchains(self) -> None:
        hub = self.defaults.toolchains
        tc_dir = self.root / hub.dir
        if tc_dir.is_dir():
            for path in sorted(tc_dir.glob("*.yaml"), key=lambda p: p.stem.casefold()):
                if path.name.lower() == "readme.yaml":
                    continue
                tc = load_toolchain(path)
                self.toolchains.register(tc.id, tc, overwrite=True)

        # Inline define: overrides or adds (PyTorch registry overwrite)
        for key, tc in hub.define.items():
            # Ensure id matches registry key
            if tc.id != key:
                tc = tc.model_copy(update={"id": key})
            self.toolchains.register(key, tc, overwrite=True)

    def enabled_toolchains(self) -> list[str]:
        """Active toolchain ids from config (linguistic)."""
        return self.defaults.toolchains.matrix_toolchain_ids(self.defaults.matrix)

    def toolchain_details(self) -> dict[str, dict[str, object]]:
        details: dict[str, dict[str, object]] = {}
        for tid in self.toolchains:
            tc = self.toolchains.get(tid)
            details[tid] = {
                "display_name": tc.display_name,
                "description": tc.description,
                "cc": tc.resolved_cc(),
                "cxx": tc.resolved_cxx(),
                "cflags": tc.cflags,
                "cxxflags": tc.cxxflags,
                "ldflags": tc.ldflags,
                "env": tc.env,
                "file_enabled": tc.enabled,
                "in_enabled_list": tid in set(self.defaults.toolchains.enabled)
                | set(self.defaults.matrix.toolchains),
            }
        return details

    def _load_presets(self) -> None:
        for name in sorted(self.defaults.compiler.presets, key=str.casefold):
            preset = self.defaults.compiler.presets[name]
            self.presets.register(name, flagset_to_options(preset), overwrite=True)

    def _load_apps(self) -> None:
        for ref in self.catalog.iter_apps():
            self.apps.register(ref.id, ref, overwrite=True)

    def compose_flags(
        self,
        *,
        app: AppRef,
        recipe: Recipe,
        toolchain: Toolchain,
        preset_name: str | None = None,
        extra_cflags: list[str] | None = None,
        extra_cxxflags: list[str] | None = None,
        extra_ldflags: list[str] | None = None,
    ) -> tuple[CompilerOptions, list[FlagOverlay]]:
        """Build CompilerOptions via OverlayComposer (LLVM option specificity)."""
        cc_cfg = self.defaults.compiler
        composer = OverlayComposer()

        # 1) ALL — generic for every app
        composer.add(
            FlagOverlay(
                kind=OverlayKind.ALL,
                key="all",
                flags=flagset_to_options(cc_cfg.all),
            )
        )

        # 2) PRESET — replaces base (like selecting -O3 pipeline)
        if preset_name:
            preset_flags = self.presets.get(preset_name)
            composer.add(
                FlagOverlay(
                    kind=OverlayKind.PRESET,
                    key=preset_name,
                    flags=preset_flags,
                    replace_base=True,
                )
            )

        # 3) Toolchain-local flags (configs/toolchains/<id>.yaml) — survive presets
        composer.add(
            FlagOverlay(
                kind=OverlayKind.ALL,
                key=f"toolchain:{toolchain.id}",
                flags=FlagOptions.from_lists(toolchain.cflags, toolchain.cxxflags, toolchain.ldflags),
            )
        )

        # 4) TYPE
        type_fs = cc_cfg.types.get(app.type, FlagSet())
        composer.add(
            FlagOverlay(kind=OverlayKind.TYPE, key=app.type, flags=flagset_to_options(type_fs))
        )

        # 4) FARM_APP
        farm_fs = cc_cfg.apps.get(app.id, FlagSet())
        composer.add(
            FlagOverlay(
                kind=OverlayKind.FARM_APP,
                key=app.id,
                flags=flagset_to_options(farm_fs),
            )
        )

        # 5) APP_JSON
        composer.add(
            FlagOverlay(
                kind=OverlayKind.APP_JSON,
                key=f"{app.id}#app.json",
                flags=flagset_to_options(app.identity.flags),
            )
        )

        # 6) RECIPE
        composer.add(
            FlagOverlay(
                kind=OverlayKind.RECIPE,
                key=f"{app.id}@{recipe.version}",
                flags=FlagOptions.from_lists(
                    recipe.toolchain.cflags,
                    recipe.toolchain.cxxflags,
                    recipe.toolchain.ldflags,
                ),
            )
        )

        # 7) CLI
        composer.add(
            FlagOverlay(
                kind=OverlayKind.CLI,
                key="cli",
                flags=FlagOptions.from_lists(extra_cflags, extra_cxxflags, extra_ldflags),
            )
        )

        merged, applied = composer.compose()

        cc = recipe.toolchain.cc or toolchain.resolved_cc() or cc_cfg.cc
        cxx = recipe.toolchain.cxx or toolchain.resolved_cxx() or cc_cfg.cxx
        cc = cc.replace("${CC}", toolchain.resolved_cc()).replace("${CXX}", toolchain.resolved_cxx())
        cxx = cxx.replace("${CC}", toolchain.resolved_cc()).replace("${CXX}", toolchain.resolved_cxx())

        opts = CompilerOptions(
            cc=cc,
            cxx=cxx,
            flags=merged,
            env=tuple(sorted(toolchain.env.items())),
        )
        return opts, applied

    def compose_csperf(self, recipe: Recipe, farm: CsperfConfig | None = None) -> CsperfOptions:
        farm_cs = farm or self.defaults.csperf
        spec = recipe.perf.csperf if recipe.perf else None
        base = CsperfOptions(
            enabled=farm_cs.enabled,
            binary=farm_cs.binary,
            backend=farm_cs.backend,
            warmup_runs=farm_cs.warmup_runs,
            repeat_runs=farm_cs.repeat_runs,
            no_perf=farm_cs.no_perf,
            cpu_affinity=farm_cs.cpu_affinity,
            report_format=farm_cs.report_format,
            extra_args=tuple(farm_cs.extra_args),
            output_name=farm_cs.output_name,
        )
        if spec is None:
            return base.overlay(enabled=False)
        return base.overlay(
            enabled=base.enabled if spec.enabled is None else spec.enabled,
            backend=spec.backend or base.backend,
            warmup_runs=base.warmup_runs if spec.warmup_runs is None else spec.warmup_runs,
            repeat_runs=base.repeat_runs if spec.repeat_runs is None else spec.repeat_runs,
            no_perf=base.no_perf if spec.no_perf is None else spec.no_perf,
            cpu_affinity=base.cpu_affinity if spec.cpu_affinity is None else spec.cpu_affinity,
            report_format=spec.report_format or base.report_format,
            extra_args=base.extra_args + tuple(spec.extra_args),
            workload=tuple(spec.workload),
            input=spec.input,
        )

    def plan(
        self,
        target: str,
        *,
        toolchain_id: str | None = None,
        preset_name: str | None = None,
        extra_cflags: list[str] | None = None,
        extra_cxxflags: list[str] | None = None,
        pipeline: Pipeline | None = None,
    ) -> ResolvedCompileJob:
        app, ver = self.catalog.parse_target(target)
        version, recipe = app.load_recipe(ver)
        tid = toolchain_id or self.defaults.toolchains.default
        toolchain = self.toolchains.get(tid)

        compiler, overlays = self.compose_flags(
            app=app,
            recipe=recipe,
            toolchain=toolchain,
            preset_name=preset_name,
            extra_cflags=extra_cflags,
            extra_cxxflags=extra_cxxflags,
        )
        csperf = self.compose_csperf(recipe)

        result_dir = str(
            self.root
            / self.defaults.farm.results_root
            / "plan"
            / app.type
            / app.name
            / version
            / tid
            / (preset_name or "default")
        )

        ctx = JobContext(
            app_id=app.id,
            version=version,
            toolchain_id=tid,
            compiler=compiler,
            csperf=csperf,
            result_dir=result_dir,
        )
        pipe = pipeline or default_plan_pipeline()
        pipe.run(ctx)

        overlay_dicts = [
            {
                "kind": o.kind.value,
                "key": o.key,
                "replace_base": o.replace_base,
                "flags": o.flags.as_dict(),
            }
            for o in overlays
        ]
        pipe_results = [
            {"name": r.name, "status": r.status.value, "detail": r.detail}
            for r in ctx.results
        ]
        cmd = ctx.extras.get("csperf_command")
        job = ResolvedCompileJob(
            app_id=app.id,
            version=version,
            toolchain_id=tid,
            preset=preset_name,
            compiler=compiler,
            csperf=csperf,
            overlays=overlay_dicts,
            pipeline_results=pipe_results,
            csperf_command=list(cmd) if isinstance(cmd, list) else None,
            result_dir=result_dir,
        )

        # Persist plan artifacts (plan does NOT run csperf — no csperf.json yet)
        out = Path(result_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps(job.as_dict(), indent=2) + "\n", encoding="utf-8")
        (out / "README.md").write_text(
            "\n".join(
                [
                    f"# Plan: {app.id}@{version}",
                    "",
                    f"- toolchain: `{tid}`",
                    f"- preset: `{preset_name or 'default'}`",
                    "",
                    "## Files",
                    "",
                    "| File | Meaning |",
                    "|------|---------|",
                    "| `plan.json` | Resolved flags + intended `csperf` argv (this command) |",
                    "| `csperf.json` | **Only after** a real `csperf run` — not created by `csfarm plan` |",
                    "",
                    "## Next",
                    "",
                    "```bash",
                    " ".join(job.csperf_command or ["# no csperf workload"]),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return job

    def run(
        self,
        target: str,
        *,
        toolchain_id: str | None = None,
        preset_name: str | None = None,
        extra_cflags: list[str] | None = None,
        extra_cxxflags: list[str] | None = None,
        skip_test: bool = False,
        skip_perf: bool = False,
        pipeline: Pipeline | None = None,
    ) -> ResolvedCompileJob:
        """Fetch → build → test → timed workload (real execution pipeline)."""
        app, ver = self.catalog.parse_target(target)
        version, recipe = app.load_recipe(ver)
        tid = toolchain_id or self.defaults.toolchains.default
        toolchain = self.toolchains.get(tid)
        preset = preset_name or "default"

        compiler, overlays = self.compose_flags(
            app=app,
            recipe=recipe,
            toolchain=toolchain,
            preset_name=preset_name,
            extra_cflags=extra_cflags,
            extra_cxxflags=extra_cxxflags,
        )
        csperf = self.compose_csperf(recipe)

        result_dir = (
            self.root
            / self.defaults.farm.results_root
            / "run"
            / app.type
            / app.name
            / version
            / tid
            / preset
        )
        source_dir = (
            self.root
            / self.defaults.farm.cache_root
            / "sources"
            / app.type
            / app.name
            / version
        )
        build_dir = (
            self.root
            / self.defaults.farm.work_root
            / tid
            / preset
            / app.type
            / app.name
            / version
        )

        result_dir.mkdir(parents=True, exist_ok=True)

        ctx = JobContext(
            app_id=app.id,
            version=version,
            toolchain_id=tid,
            compiler=compiler,
            csperf=csperf,
            result_dir=str(result_dir),
        )
        ctx.extras.update(
            {
                "recipe": recipe,
                "source_dir": str(source_dir),
                "build_dir": str(build_dir),
                "skip_test": skip_test,
                "skip_perf": skip_perf,
            }
        )

        pipe = pipeline or default_run_pipeline()
        pipe.run(ctx)

        ok = all(r.status != StageStatus.FAILED for r in ctx.results)
        overlay_dicts = [
            {
                "kind": o.kind.value,
                "key": o.key,
                "replace_base": o.replace_base,
                "flags": o.flags.as_dict(),
            }
            for o in overlays
        ]
        pipe_results = [
            {"name": r.name, "status": r.status.value, "detail": r.detail}
            for r in ctx.results
        ]
        cmd = ctx.extras.get("csperf_command")
        job = ResolvedCompileJob(
            app_id=app.id,
            version=version,
            toolchain_id=tid,
            preset=preset_name,
            compiler=compiler,
            csperf=csperf,
            overlays=overlay_dicts,
            pipeline_results=pipe_results,
            csperf_command=list(cmd) if isinstance(cmd, list) else None,
            result_dir=str(result_dir),
            mode="run",
            ok=ok,
        )
        (result_dir / "run.json").write_text(
            json.dumps(job.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
        return job
