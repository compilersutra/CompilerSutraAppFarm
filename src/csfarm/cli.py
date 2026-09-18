# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from csfarm import __version__
from csfarm.patterns import OverlayKind
from csfarm.resolve import FarmSession

app = typer.Typer(
    name="csfarm",
    help="CompilerSutra AppFarm — LLVM/PyTorch-style registries, overlays, pipeline.",
    no_args_is_help=True,
)
console = Console()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _session(config: Path | None) -> FarmSession:
    cfg = config or (_repo_root() / "configs" / "default.yaml")
    return FarmSession(_repo_root(), cfg)


@app.callback()
def main() -> None:
    """CompilerSutra AppFarm CLI."""


@app.command("version")
def version_cmd() -> None:
    """Print csfarm version."""
    console.print(__version__)


@app.command("list")
def list_apps(
    type: str | None = typer.Option(None, "--type", "-t", help="Filter by type folder."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """List apps from the app registry (linguistic order)."""
    session = _session(config)
    table = Table(title="App registry (linguistic)")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Default")
    table.add_column("Versions")
    table.add_column("Display")
    refs = session.catalog.iter_apps(type)
    for ref in refs:
        table.add_row(
            ref.id,
            ref.type,
            ref.identity.default_version,
            ", ".join(ref.list_versions()),
            ref.identity.display_name or ref.name,
        )
    console.print(table)


@app.command("show")
def show_app(
    target: str = typer.Argument(..., help="type/name or type/name@version"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Show app identity + selected version recipe."""
    session = _session(config)
    app_ref, ver = session.catalog.parse_target(target)
    version, recipe = app_ref.load_recipe(ver)
    console.print_json(
        json.dumps(
            {
                "app": app_ref.identity.model_dump(),
                "version": version,
                "recipe": recipe.model_dump(),
            },
            indent=2,
        )
    )


@app.command("plan")
def plan_run(
    target: str = typer.Argument(..., help="type/name or type/name@version"),
    toolchain: str | None = typer.Option(
        None,
        "--toolchain",
        "-T",
        help="Toolchain id (default: toolchains.default in config).",
    ),
    flags: str | None = typer.Option(None, "--flags", "-F", help="Preset registry key."),
    cflag: list[str] = typer.Option([], "--cflag", help="CLI overlay CFLAG."),
    cxxflag: list[str] = typer.Option([], "--cxxflag", help="CLI overlay CXXFLAG."),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Dry-run: compose overlays → resolve options → write plan.json."""
    session = _session(config)
    job = session.plan(
        target,
        toolchain_id=toolchain,
        preset_name=flags,
        extra_cflags=cflag,
        extra_cxxflags=cxxflag,
    )
    console.print_json(json.dumps(job.as_dict(), indent=2))


@app.command("run")
def run_app(
    target: str = typer.Argument(..., help="type/name or type/name@version"),
    toolchain: str | None = typer.Option(None, "--toolchain", "-T"),
    flags: str | None = typer.Option(None, "--flags", "-F", help="Preset registry key."),
    cflag: list[str] = typer.Option([], "--cflag"),
    cxxflag: list[str] = typer.Option([], "--cxxflag"),
    skip_test: bool = typer.Option(False, "--skip-test"),
    skip_perf: bool = typer.Option(False, "--skip-perf"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Fetch → build → test → timed workload; write results/run/.../run.json + csperf.json."""
    session = _session(config)
    job = session.run(
        target,
        toolchain_id=toolchain,
        preset_name=flags,
        extra_cflags=cflag,
        extra_cxxflags=cxxflag,
        skip_test=skip_test,
        skip_perf=skip_perf,
    )
    console.print_json(json.dumps(job.as_dict(), indent=2))
    if not job.ok:
        raise typer.Exit(code=1)


def _fmt_flags(vals: list[str] | tuple[str, ...]) -> str:
    return " ".join(vals) if vals else "—"


@app.command("flags")
def list_flags(
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Show option-bag layers + preset registry (overlay kinds)."""
    session = _session(config)
    cc = session.defaults.compiler

    console.print(
        f"[bold]Overlay {OverlayKind.ALL.value}[/bold]  CC={cc.cc}  "
        f"CFLAGS={_fmt_flags(cc.all.cflags)!r}  CXXFLAGS={_fmt_flags(cc.all.cxxflags)!r}"
    )

    if cc.types:
        ttable = Table(title=f"Overlay {OverlayKind.TYPE.value} (compiler.types)")
        ttable.add_column("Type", style="cyan")
        ttable.add_column("CFLAGS")
        ttable.add_column("CXXFLAGS")
        for name in sorted(cc.types, key=str.casefold):
            fs = cc.types[name]
            ttable.add_row(name, _fmt_flags(fs.cflags), _fmt_flags(fs.cxxflags))
        console.print(ttable)

    if cc.apps:
        atable = Table(title=f"Overlay {OverlayKind.FARM_APP.value} (compiler.apps)")
        atable.add_column("App", style="cyan")
        atable.add_column("CFLAGS")
        atable.add_column("CXXFLAGS")
        for name in sorted(cc.apps, key=str.casefold):
            fs = cc.apps[name]
            atable.add_row(name, _fmt_flags(fs.cflags), _fmt_flags(fs.cxxflags))
        console.print(atable)

    ptable = Table(title="Preset registry (replace_base overlays)")
    ptable.add_column("Preset", style="cyan")
    ptable.add_column("CFLAGS")
    ptable.add_column("CXXFLAGS")
    ptable.add_column("LDFLAGS")
    for name, preset in session.presets.items():
        ptable.add_row(
            name,
            _fmt_flags(preset.cflags),
            _fmt_flags(preset.cxxflags),
            _fmt_flags(preset.ldflags),
        )
    console.print(ptable)

    console.print("\nCompose: " + " → ".join(k.value for k in OverlayKind))
    console.print("Patterns: docs/ARCHITECTURE.md (LLVM option bags / PyTorch registry)")


@app.command("registries")
def registries_cmd(
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Dump editable toolchain hub + preset/app registries."""
    session = _session(config)
    hub = session.defaults.toolchains
    console.print_json(
        json.dumps(
            {
                "toolchains": {
                    "default": hub.default,
                    "enabled": hub.enabled,
                    "matrix_uses": session.enabled_toolchains(),
                    "available": session.toolchains.keys(),
                    "details": session.toolchain_details(),
                    "customize": "Edit configs/default.yaml → toolchains.enabled / define, "
                    "or files under configs/toolchains/",
                },
                "presets": session.presets.keys(),
                "apps": session.apps.keys(),
            },
            indent=2,
        )
    )


@app.command("matrix-plan")
def matrix_plan(
    type: str | None = typer.Option(None, "--type", "-t"),
    config: Path | None = typer.Option(None, "--config", "-c"),
) -> None:
    """Emit matrix jobs: apps × toolchains.enabled × flag_presets."""
    session = _session(config)
    apps = session.catalog.iter_apps(type)
    tc_ids = session.enabled_toolchains()
    jobs = []
    for ref in apps:
        for tc in tc_ids:
            for preset in session.defaults.matrix.flag_presets:
                jobs.append(
                    {
                        "app": ref.id,
                        "version": ref.identity.default_version,
                        "toolchain": tc,
                        "flags": preset,
                    }
                )
    console.print_json(
        json.dumps(
            {
                "toolchains": tc_ids,
                "flag_presets": session.defaults.matrix.flag_presets,
                "jobs": jobs,
                "count": len(jobs),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
