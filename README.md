# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 CompilerSutra

# CompilerSutra AppFarm

[![CI](https://github.com/compilersutra/CompilerSutraAppFarm/actions/workflows/ci.yml/badge.svg)](https://github.com/compilersutra/CompilerSutraAppFarm/actions/workflows/ci.yml)

Typed open-source **application farm** for compiler testing: pick an app and
version, compose toolchain flags, then **fetch → build → test → measure**.

CLI: **`csfarm`**. Optional timing via
[`csperf`](https://github.com/compilersutra) when installed; otherwise AppFarm
records honest wall-clock samples (`tool: csfarm`, not hardware counters).

**Status: v0.1.1 alpha** — usable on a Linux host with clang/gcc. See
[Status](#status) and [`docs/VISION.md`](docs/VISION.md) for what is and is not claimed.

## Quick start

```bash
git clone https://github.com/compilersutra/CompilerSutraAppFarm.git
cd CompilerSutraAppFarm
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

csfarm doctor
csfarm list
csfarm run database/sqlite@3.53 --flags baseline
```

Batch smoke (catalog defaults):

```bash
python3 scripts/batch_run.py --flags baseline
# or continue after interrupts:
python3 scripts/batch_run.py --continue --flags baseline
```

**Tier-1** (trusted core — see [`configs/tier1.yaml`](configs/tier1.yaml),
matrix: [`docs/tier1-matrix.md`](docs/tier1-matrix.md)):

```bash
python3 scripts/batch_run.py --tier1 --flags baseline --skip-perf
# faster CI subset:
python3 scripts/batch_run.py --tier1 --ci --flags baseline --skip-perf
```

Optional local tools (nasm, etc.) live under `tools/` when you build them;
`csfarm` prepends `tools/bin` automatically when present.

## What you get

| Piece | Role |
|-------|------|
| `apps/<type>/<app>/` | Catalog: identity, versions, recipes |
| `configs/default.yaml` | Enabled toolchains, flag presets, csperf defaults |
| `configs/toolchains/*.yaml` | clang / gcc / aocc / custom-clang |
| `csfarm run` | Full pipeline → `results/run/.../run.json` (+ `csperf.json`) |
| `scripts/batch_run.py` | Green/red report → `results/batch/report.json` |
| `docker/` | Distro images for the **tool** (ubuntu/debian/fedora/arch) |

Apps are ordered **type → name → version** (A–Z), not a flat dump.

## Layout

```text
apps/<type>/<app>/
  app.json
  versions/<series>/
    lifecycle.json      # support / EOL notes
    dependencies.yaml   # distro package hints
    recipe.json         # source, build, test, perf
    README.md
configs/
docker/
scripts/
src/csfarm/
docs/
```

## CLI

```bash
csfarm list
csfarm flags
csfarm doctor
csfarm plan database/sqlite@3.53 --flags baseline
csfarm run  database/sqlite@3.53 --flags baseline
csfarm compare results/batch/old.json results/batch/new.json
csfarm report results/batch/report.json -o results/batch/report.md
csfarm matrix-plan --type database
```

Addressing:

| Form | Meaning |
|------|---------|
| `database/sqlite` | type/name (default version from `app.json`) |
| `database/sqlite@3.53` | pinned version folder |

## Compilers and flags

Edit [`configs/default.yaml`](configs/default.yaml):

```yaml
toolchains:
  default: clang
  enabled:
    - clang
    - gcc
```

Or set `cc_path` / `cxx_path` under [`configs/toolchains/`](configs/toolchains/).

Flag layers (preset **replaces** the `all` base; other layers append):

| Layer | Where |
|-------|--------|
| `compiler.all` | `configs/default.yaml` |
| `compiler.presets.*` | `--flags` |
| `compiler.types.<type>` | same file |
| `compiler.apps.<id>` | same file |
| `flags` | `app.json` |
| `toolchain` | `recipe.json` |
| CLI | `--cflag` / `--cxxflag` |

Architecture notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Docker

Image matrix (amd64) — see [`docker/README.md`](docker/README.md):

```bash
./scripts/docker_matrix.sh build
./scripts/docker_matrix.sh run ubuntu registries
./scripts/docker_matrix.sh run ubuntu run database/sqlite@3.53 --flags baseline
```

Images use `docker/entrypoint.sh` so host-mounted `/farm` gets `git safe.directory`
before `csfarm`. Host batch runs remain the primary path for the full smoke
matrix. Arm64 cross-build needs buildx+QEMU (or a native ARM host).

## Perf / csperf

- With `csperf` on `PATH`: recipes can hand off measurement.
- Without it: `csfarm run` still writes timed workload samples as `csperf.json`
  (`tool: csfarm`).

## Status

| Claim | v0.1.1 |
|-------|--------|
| Catalog size | **115** apps |
| Tier-1 set | **14** apps in [`configs/tier1.yaml`](configs/tier1.yaml) |
| Host smoke (`clang` + `baseline`) | **115/115** on a developed Linux host |
| “Full upstream test suites for every app” | **No** — many recipes use build/smoke checks |
| Docker: build tool images | **Yes** (amd64) |
| Docker: full farm from scratch | **Not yet** |
| `database/mongodb` | Builds **mongo-c-driver** (full `mongod` not wired) |
| CI | Unit + CLI smoke (`.github/workflows/ci.yml`); tier-1 subset on path changes |

Release notes: [`CHANGELOG.md`](CHANGELOG.md) · contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) ·
checklist: [`docs/RELEASE.md`](docs/RELEASE.md).

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check src tests
```

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
