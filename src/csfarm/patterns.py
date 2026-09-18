# SPDX-License-Identifier: Apache-2.0
"""
LLVM / PyTorch-style core patterns for AppFarm.

Analogies
---------
LLVM
  - Option bags     → like ``CodeGenOptions`` / ``LangOptions`` / ``TargetOptions``
  - Overlay layers  → like cl:: defaults then -mllvm / -C flags (specificity order)
  - Pass pipeline   → like ``PassBuilder`` / ``PassManager`` (fetch→build→test→perf)
  - Registry        → like pass registry / target registry

PyTorch
  - Registry        → like ``torch.ops`` / ``@register`` module registries
  - Option compose  → like Hydra/OmegaConf structured configs + overrides
  - nn.Module tree  → typed app catalog (type → app → version) as a hierarchy
  - state_dict      → serializable ResolvedJob / result artifacts
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Registry — PyTorch ``torch.ops`` / LLVM pass-registry style
# ---------------------------------------------------------------------------


class Registry(Generic[T]):
    """Named object registry with linguistic (casefold A–Z) iteration."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._items: dict[str, T] = {}

    def register(self, key: str, value: T, *, overwrite: bool = False) -> T:
        k = key.strip()
        if not k:
            raise ValueError(f"{self.name}: empty registry key")
        if k in self._items and not overwrite:
            raise KeyError(f"{self.name}: duplicate key {k!r}")
        self._items[k] = value
        return value

    def get(self, key: str) -> T:
        try:
            return self._items[key]
        except KeyError as exc:
            known = ", ".join(self.keys()) or "(empty)"
            raise KeyError(f"{self.name}: unknown {key!r}; known: {known}") from exc

    def contains(self, key: str) -> bool:
        return key in self._items

    def keys(self) -> list[str]:
        return sorted(self._items.keys(), key=str.casefold)

    def items(self) -> list[tuple[str, T]]:
        return [(k, self._items[k]) for k in self.keys()]

    def values(self) -> list[T]:
        return [self._items[k] for k in self.keys()]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())


def register_fn(registry: Registry[T], key: str) -> Callable[[T], T]:
    """Decorator: ``@register_fn(REGISTRY, "cmake")`` — PyTorch-style."""

    def deco(obj: T) -> T:
        registry.register(key, obj)
        return obj

    return deco


# ---------------------------------------------------------------------------
# Option bags — LLVM ``CodeGenOptions`` style (immutable-ish dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlagOptions:
    """Small option bag for flag lists (append-merge semantics)."""

    cflags: tuple[str, ...] = ()
    cxxflags: tuple[str, ...] = ()
    ldflags: tuple[str, ...] = ()

    def extended(self, other: FlagOptions) -> FlagOptions:
        """Append-merge like composing LLVM cl:: lists / PyTorch cfg overlays."""
        return FlagOptions(
            cflags=self.cflags + other.cflags,
            cxxflags=self.cxxflags + other.cxxflags,
            ldflags=self.ldflags + other.ldflags,
        )

    @classmethod
    def from_lists(
        cls,
        cflags: Iterable[str] | None = None,
        cxxflags: Iterable[str] | None = None,
        ldflags: Iterable[str] | None = None,
    ) -> FlagOptions:
        return cls(
            cflags=tuple(cflags or ()),
            cxxflags=tuple(cxxflags or ()),
            ldflags=tuple(ldflags or ()),
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "cflags": list(self.cflags),
            "cxxflags": list(self.cxxflags),
            "ldflags": list(self.ldflags),
        }


@dataclass(frozen=True)
class CompilerOptions:
    """Like LLVM ``CodeGenOptions`` + toolchain triple selection."""

    cc: str = "clang"
    cxx: str = "clang++"
    flags: FlagOptions = field(default_factory=FlagOptions)
    env: tuple[tuple[str, str], ...] = ()

    def with_flags(self, flags: FlagOptions) -> CompilerOptions:
        return replace(self, flags=self.flags.extended(flags))

    def with_tools(self, *, cc: str | None = None, cxx: str | None = None) -> CompilerOptions:
        return replace(self, cc=cc or self.cc, cxx=cxx or self.cxx)

    def env_map(self) -> dict[str, str]:
        base = {
            "CC": self.cc,
            "CXX": self.cxx,
            "CFLAGS": " ".join(self.flags.cflags),
            "CXXFLAGS": " ".join(self.flags.cxxflags),
            "LDFLAGS": " ".join(self.flags.ldflags),
        }
        base.update(dict(self.env))
        return base


@dataclass(frozen=True)
class CsperfOptions:
    """Runtime measurement options bag (handed to ``csperf``)."""

    enabled: bool = True
    binary: str = "csperf"
    backend: str = "cpu"
    warmup_runs: int = 1
    repeat_runs: int = 5
    no_perf: bool = False
    cpu_affinity: int | None = None
    report_format: str = "both"
    extra_args: tuple[str, ...] = ()
    output_name: str = "csperf.json"
    workload: tuple[str, ...] = ()
    input: str | None = None

    def overlay(self, **kwargs: object) -> CsperfOptions:
        """Field override like PyTorch cfg merge / LLVM option override."""
        return replace(self, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Overlay layers — Hydra-style compose / LLVM specificity order
# ---------------------------------------------------------------------------


class OverlayKind(StrEnum):
    """Specificity order (low → high). Mirrors LLVM default < flag < attr."""

    ALL = "all"  # generic for every app
    PRESET = "preset"  # named pipeline like -O2 / sanitize
    TYPE = "type"  # database/, media/, …
    FARM_APP = "farm_app"  # configs compiler.apps[id]
    APP_JSON = "app_json"  # apps/.../app.json flags
    RECIPE = "recipe"  # versions/<ver>/recipe.json
    CLI = "cli"  # command-line overrides


# Linguistic display order follows enum definition order
OVERLAY_ORDER: tuple[OverlayKind, ...] = tuple(OverlayKind)


@dataclass(frozen=True)
class FlagOverlay:
    """One named layer in the option compose stack."""

    kind: OverlayKind
    key: str  # e.g. "all", "sanitize", "database", "database/sqlite", "cli"
    flags: FlagOptions
    replace_base: bool = False  # presets replace ALL like LLVM -O3 vs default


@dataclass
class OverlayComposer:
    """
    Compose FlagOptions through ordered overlays.

    Semantics (LLVM-ish):
      - Normal layers **append** (like accumulating -f flags)
      - A layer with ``replace_base=True`` (presets) **replaces** the current
        accumulated base before later layers append again
    """

    layers: list[FlagOverlay] = field(default_factory=list)

    def add(self, overlay: FlagOverlay) -> None:
        self.layers.append(overlay)

    def compose(self) -> tuple[FlagOptions, list[FlagOverlay]]:
        applied: list[FlagOverlay] = []
        acc = FlagOptions()
        for layer in self.layers:
            acc = layer.flags if layer.replace_base else acc.extended(layer.flags)
            applied.append(layer)
        return acc, applied


# ---------------------------------------------------------------------------
# Pipeline — LLVM PassManager / PyTorch forward stages
# ---------------------------------------------------------------------------


class StageStatus(StrEnum):
    PENDING = "pending"
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"


@dataclass
class StageResult:
    name: str
    status: StageStatus
    detail: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass
class JobContext:
    """Mutable run context threaded through pipeline stages (like PM analysis)."""

    app_id: str
    version: str
    toolchain_id: str
    compiler: CompilerOptions
    csperf: CsperfOptions
    work_dir: str = ""
    result_dir: str = ""
    extras: dict[str, object] = field(default_factory=dict)
    results: list[StageResult] = field(default_factory=list)


class Stage:
    """One pipeline stage — LLVM Pass / PyTorch module step."""

    name: str = "stage"

    def run(self, ctx: JobContext) -> StageResult:  # pragma: no cover - interface
        raise NotImplementedError


class Pipeline:
    """Ordered stage list — like ``PassManager`` or ``nn.Sequential``."""

    def __init__(self, stages: Iterable[Stage] | None = None) -> None:
        self.stages: list[Stage] = list(stages or [])

    def add(self, stage: Stage) -> None:
        self.stages.append(stage)

    def run(self, ctx: JobContext) -> JobContext:
        for stage in self.stages:
            result = stage.run(ctx)
            ctx.results.append(result)
            if result.status == StageStatus.FAILED:
                break
        return ctx


# Plan-only stages (MVP): resolve + emit, no real fetch/build yet


class ResolveFlagsStage(Stage):
    name = "resolve_flags"

    def run(self, ctx: JobContext) -> StageResult:
        env = ctx.compiler.env_map()
        ctx.extras["env"] = env
        return StageResult(
            name=self.name,
            status=StageStatus.OK,
            detail=f"CC={env['CC']} CFLAGS={env['CFLAGS']!r}",
            artifacts={"env": "extras.env"},
        )


class EmitCsperfStage(Stage):
    name = "emit_csperf"

    def run(self, ctx: JobContext) -> StageResult:
        if not ctx.csperf.enabled:
            return StageResult(name=self.name, status=StageStatus.SKIPPED, detail="csperf disabled")
        cmd = build_csperf_argv(ctx.csperf, output=f"{ctx.result_dir}/{ctx.csperf.output_name}")
        ctx.extras["csperf_command"] = cmd
        return StageResult(
            name=self.name,
            status=StageStatus.OK,
            detail=" ".join(cmd),
            artifacts={"csperf_command": "extras.csperf_command"},
        )


def build_csperf_argv(opts: CsperfOptions, *, output: str) -> list[str]:
    cmd: list[str] = [
        opts.binary,
        "run",
        "--backend",
        opts.backend,
        "--warmup-runs",
        str(opts.warmup_runs),
        "--repeat-runs",
        str(opts.repeat_runs),
        "--report-format",
        opts.report_format,
        "--output",
        output,
    ]
    if opts.no_perf:
        cmd.append("--no-perf")
    if opts.cpu_affinity is not None:
        cmd.extend(["--cpu-affinity", str(opts.cpu_affinity)])
    if opts.input:
        cmd.extend(["--input", opts.input])
    cmd.extend(opts.extra_args)
    if opts.workload:
        cmd.extend(["--", *opts.workload])
    return cmd


def default_plan_pipeline() -> Pipeline:
    """Default plan pipeline — LLVM default pipeline analogue."""
    return Pipeline([ResolveFlagsStage(), EmitCsperfStage()])
