# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from csfarm.patterns import FlagOptions


class FlagSet(BaseModel):
    """Reusable cflags / cxxflags / ldflags bundle."""

    cflags: list[str] = Field(default_factory=list)
    cxxflags: list[str] = Field(default_factory=list)
    ldflags: list[str] = Field(default_factory=list)

    def extend_into(self, cflags: list[str], cxxflags: list[str], ldflags: list[str]) -> None:
        cflags.extend(self.cflags)
        cxxflags.extend(self.cxxflags)
        ldflags.extend(self.ldflags)


class CompilerPreset(FlagSet):
    """Named flag preset (baseline, optimize, sanitize, …)."""


class CompilerConfig(BaseModel):
    """
    Flag layers (most generic → most specific; all append except preset):

    1. ``all`` / legacy top-level cflags — generic for every app
    2. ``presets.<name>`` — replaces the ``all`` opt set when selected
    3. ``types.<type>`` — all apps under that type
    4. ``apps.<type/name>`` — one app (farm-wide customization)
    5. app.json ``flags`` — app-local customization
    6. recipe ``toolchain`` — version pin
    7. CLI ``--cflag`` / ``--cxxflag``
    """

    cc: str = "clang"
    cxx: str = "clang++"
    # Legacy aliases still accepted; folded into ``all`` on load
    cflags: list[str] = Field(default_factory=list)
    cxxflags: list[str] = Field(default_factory=list)
    ldflags: list[str] = Field(default_factory=list)
    all: FlagSet = Field(default_factory=FlagSet)
    types: dict[str, FlagSet] = Field(default_factory=dict)
    apps: dict[str, FlagSet] = Field(default_factory=dict)
    presets: dict[str, CompilerPreset] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fold_legacy_into_all(self) -> CompilerConfig:
        # Top-level cflags/cxxflags/ldflags are generic-for-all (legacy + shorthand).
        if self.cflags or self.cxxflags or self.ldflags:
            merged = FlagSet(
                cflags=[*self.all.cflags, *self.cflags],
                cxxflags=[*self.all.cxxflags, *self.cxxflags],
                ldflags=[*self.all.ldflags, *self.ldflags],
            )
            self.all = merged
            self.cflags = []
            self.cxxflags = []
            self.ldflags = []
        return self


class CsperfConfig(BaseModel):
    enabled: bool = True
    binary: str = "csperf"
    backend: str = "cpu"
    warmup_runs: int = 1
    repeat_runs: int = 5
    no_perf: bool = False
    cpu_affinity: int | None = None
    report_format: str = "both"
    extra_args: list[str] = Field(default_factory=list)
    output_name: str = "csperf.json"


class FarmConfig(BaseModel):
    name: str = "CompilerSutraAppFarm"
    apps_root: str = "apps"
    cache_root: str = "cache"
    work_root: str = "work"
    results_root: str = "results"
    sort: str = "linguistic"


class MatrixConfig(BaseModel):
    # If empty, falls back to toolchains.enabled from ToolchainsHubConfig
    toolchains: list[str] = Field(default_factory=list)
    flag_presets: list[str] = Field(default_factory=lambda: ["baseline"])
    fail_on_build_error: bool = True
    fail_on_test_error: bool = True
    fail_on_regress_pct: float | None = 5.0


class Toolchain(BaseModel):
    """One compiler toolchain — edit YAML under configs/toolchains/ or inline."""

    id: str
    display_name: str | None = None
    description: str | None = None
    cc: str
    cxx: str
    # Optional absolute paths if binaries are not on PATH
    cc_path: str | None = None
    cxx_path: str | None = None
    version_command: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    # Toolchain-local base flags (applied with ALL before presets)
    cflags: list[str] = Field(default_factory=list)
    cxxflags: list[str] = Field(default_factory=list)
    ldflags: list[str] = Field(default_factory=list)
    enabled: bool = True

    def resolved_cc(self) -> str:
        return self.cc_path or self.cc

    def resolved_cxx(self) -> str:
        return self.cxx_path or self.cxx


class ToolchainsHubConfig(BaseModel):
    """
    Easy customization hub — edit ``enabled`` / ``default`` / ``define`` in
    configs/default.yaml so people can switch compilers without code changes.
    """

    dir: str = "configs/toolchains"
    default: str = "clang"
    # Primary list people edit (shown by ``csfarm registries``)
    enabled: list[str] = Field(default_factory=lambda: ["clang", "gcc"])
    # Inline toolchain defs / overrides (merged on top of YAML files)
    define: dict[str, Toolchain] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _inject_define_ids(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        define = data.get("define") or {}
        if isinstance(define, dict):
            fixed: dict[str, object] = {}
            for key, val in define.items():
                if isinstance(val, dict):
                    item = dict(val)
                    item.setdefault("id", key)
                    fixed[key] = item
                else:
                    fixed[key] = val
            data = dict(data)
            data["define"] = fixed
        return data

    def matrix_toolchain_ids(self, matrix: MatrixConfig) -> list[str]:
        """Prefer matrix.toolchains when set; else toolchains.enabled."""
        ids = list(matrix.toolchains) if matrix.toolchains else list(self.enabled)
        # linguistic order for stable matrices
        return sorted(ids, key=str.casefold)


class FarmDefaults(BaseModel):
    farm: FarmConfig = Field(default_factory=FarmConfig)
    toolchains: ToolchainsHubConfig = Field(default_factory=ToolchainsHubConfig)
    compiler: CompilerConfig = Field(default_factory=CompilerConfig)
    csperf: CsperfConfig = Field(default_factory=CsperfConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)


class AppIdentity(BaseModel):
    id: str
    type: str
    name: str
    display_name: str | None = None
    languages: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)
    default_version: str
    correctness: str | None = None
    perf_backend: str = "cpu"
    description: str | None = None
    # App-local flag customization (applies to every version unless recipe adds more)
    flags: FlagSet = Field(default_factory=FlagSet)


class SourceSpec(BaseModel):
    url: str
    ref: str = ""
    subdir: str | None = None
    kind: str | None = None  # "git" (default) or "archive"


class ToolchainOverride(BaseModel):
    cc: str | None = None
    cxx: str | None = None
    cflags: list[str] = Field(default_factory=list)
    cxxflags: list[str] = Field(default_factory=list)
    ldflags: list[str] = Field(default_factory=list)


class BuildSpec(BaseModel):
    system: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    workdir: str | None = None
    commands: list[list[str]] = Field(default_factory=list)


class TestSpec(BaseModel):
    command: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout_sec: int | None = None


class CsperfRecipe(BaseModel):
    enabled: bool = True
    backend: str | None = None
    warmup_runs: int | None = None
    repeat_runs: int | None = None
    no_perf: bool | None = None
    cpu_affinity: int | None = None
    report_format: str | None = None
    extra_args: list[str] = Field(default_factory=list)
    workload: list[str] = Field(default_factory=list)
    input: str | None = None


class PerfSpec(BaseModel):
    csperf: CsperfRecipe | None = None


class Recipe(BaseModel):
    version: str
    source: SourceSpec
    toolchain: ToolchainOverride = Field(default_factory=ToolchainOverride)
    build: BuildSpec
    test: TestSpec | None = None
    perf: PerfSpec | None = None


class FlagLayers(BaseModel):
    """Resolved layers for debugging / plan output (linguistic key order in maps)."""

    all: FlagSet
    preset: str | None = None
    type: FlagSet = Field(default_factory=FlagSet)
    farm_app: FlagSet = Field(default_factory=FlagSet)
    app_json: FlagSet = Field(default_factory=FlagSet)
    recipe: FlagSet = Field(default_factory=FlagSet)
    cli: FlagSet = Field(default_factory=FlagSet)


class ResolvedFlags(BaseModel):
    cc: str
    cxx: str
    cflags: list[str]
    cxxflags: list[str]
    ldflags: list[str]
    env: dict[str, str]
    layers: FlagLayers | None = None


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_farm_defaults(path: Path) -> FarmDefaults:
    return FarmDefaults.model_validate(load_yaml(path))


def load_toolchain(path: Path) -> Toolchain:
    return Toolchain.model_validate(load_yaml(path))


def merge_compiler_flags(
    defaults: CompilerConfig,
    toolchain: Toolchain,
    recipe: Recipe,
    *,
    app_id: str | None = None,
    app_type: str | None = None,
    app_flags: FlagSet | None = None,
    preset_name: str | None = None,
    extra_cflags: list[str] | None = None,
    extra_cxxflags: list[str] | None = None,
    extra_ldflags: list[str] | None = None,
) -> ResolvedFlags:
    """
    Deprecated thin wrapper — prefer ``FarmSession.compose_flags`` / ``plan``.

    Kept so older call sites still work; implements the same overlay order.
    """
    from csfarm.patterns import FlagOverlay, OverlayComposer, OverlayKind

    def _fo(fs: FlagSet) -> FlagOptions:
        return FlagOptions.from_lists(fs.cflags, fs.cxxflags, fs.ldflags)

    composer = OverlayComposer()
    composer.add(FlagOverlay(OverlayKind.ALL, "all", _fo(defaults.all)))
    if preset_name:
        if preset_name not in defaults.presets:
            known = ", ".join(sorted(defaults.presets, key=str.casefold)) or "(none)"
            raise KeyError(f"Unknown flag preset {preset_name!r}; known: {known}")
        p = defaults.presets[preset_name]
        composer.add(
            FlagOverlay(OverlayKind.PRESET, preset_name, _fo(p), replace_base=True)
        )
    type_key = app_type or (app_id.split("/", 1)[0] if app_id and "/" in app_id else None)
    if type_key:
        composer.add(
            FlagOverlay(OverlayKind.TYPE, type_key, _fo(defaults.types.get(type_key, FlagSet())))
        )
    if app_id:
        composer.add(
            FlagOverlay(
                OverlayKind.FARM_APP, app_id, _fo(defaults.apps.get(app_id, FlagSet()))
            )
        )
    composer.add(FlagOverlay(OverlayKind.APP_JSON, "app.json", _fo(app_flags or FlagSet())))
    composer.add(
        FlagOverlay(
            OverlayKind.RECIPE,
            "recipe",
            FlagOptions.from_lists(
                recipe.toolchain.cflags, recipe.toolchain.cxxflags, recipe.toolchain.ldflags
            ),
        )
    )
    composer.add(
        FlagOverlay(
            OverlayKind.CLI,
            "cli",
            FlagOptions.from_lists(extra_cflags, extra_cxxflags, extra_ldflags),
        )
    )
    merged, applied = composer.compose()

    cc = recipe.toolchain.cc or toolchain.cc or defaults.cc
    cxx = recipe.toolchain.cxx or toolchain.cxx or defaults.cxx
    cc = cc.replace("${CC}", toolchain.cc).replace("${CXX}", toolchain.cxx)
    cxx = cxx.replace("${CC}", toolchain.cc).replace("${CXX}", toolchain.cxx)
    env = {
        "CC": cc,
        "CXX": cxx,
        "CFLAGS": " ".join(merged.cflags),
        "CXXFLAGS": " ".join(merged.cxxflags),
        "LDFLAGS": " ".join(merged.ldflags),
        **toolchain.env,
    }
    by_kind = {o.kind: o for o in applied}
    layers = FlagLayers(
        all=FlagSet(**by_kind[OverlayKind.ALL].flags.as_dict()),
        preset=preset_name,
        type=FlagSet(**by_kind.get(OverlayKind.TYPE, applied[0]).flags.as_dict())
        if OverlayKind.TYPE in by_kind
        else FlagSet(),
        farm_app=FlagSet(**by_kind[OverlayKind.FARM_APP].flags.as_dict())
        if OverlayKind.FARM_APP in by_kind
        else FlagSet(),
        app_json=FlagSet(**by_kind[OverlayKind.APP_JSON].flags.as_dict()),
        recipe=FlagSet(**by_kind[OverlayKind.RECIPE].flags.as_dict()),
        cli=FlagSet(**by_kind[OverlayKind.CLI].flags.as_dict()),
    )
    return ResolvedFlags(
        cc=cc,
        cxx=cxx,
        cflags=list(merged.cflags),
        cxxflags=list(merged.cxxflags),
        ldflags=list(merged.ldflags),
        env=env,
        layers=layers,
    )


def build_csperf_command(
    farm_csperf: CsperfConfig,
    recipe: Recipe,
    output_path: Path,
    *,
    flags: ResolvedFlags | None = None,
) -> list[str] | None:
    """Build a `csperf run ...` argv from farm defaults + recipe overrides."""
    spec = recipe.perf.csperf if recipe.perf else None
    if spec is None:
        return None
    enabled = farm_csperf.enabled if spec.enabled is None else spec.enabled
    if not enabled:
        return None

    backend = spec.backend or farm_csperf.backend
    warmup = farm_csperf.warmup_runs if spec.warmup_runs is None else spec.warmup_runs
    repeats = farm_csperf.repeat_runs if spec.repeat_runs is None else spec.repeat_runs
    no_perf = farm_csperf.no_perf if spec.no_perf is None else spec.no_perf
    affinity = farm_csperf.cpu_affinity if spec.cpu_affinity is None else spec.cpu_affinity
    report = spec.report_format or farm_csperf.report_format

    cmd: list[str] = [
        farm_csperf.binary,
        "run",
        "--backend",
        backend,
        "--warmup-runs",
        str(warmup),
        "--repeat-runs",
        str(repeats),
        "--report-format",
        report,
        "--output",
        str(output_path),
    ]
    if no_perf:
        cmd.append("--no-perf")
    if affinity is not None:
        cmd.extend(["--cpu-affinity", str(affinity)])

    if spec.input:
        cmd.extend(["--input", spec.input])

    cmd.extend(farm_csperf.extra_args)
    cmd.extend(spec.extra_args)

    if spec.workload:
        cmd.extend(["--", *spec.workload])

    if flags is not None:
        _ = flags

    return cmd
