# SPDX-License-Identifier: Apache-2.0

# Architecture

Patterns used by CompilerSutra AppFarm. We deliberately mirror **LLVM** and
**PyTorch** shapes so the farm stays familiar to compiler / ML systems engineers.

## 1. Option bags (LLVM `CodeGenOptions` / `LangOptions`)

Immutable option objects hold related knobs:

| AppFarm | LLVM analogue | PyTorch analogue |
|---------|---------------|------------------|
| `CompilerOptions` | `CodeGenOptions` | structured cfg object |
| `FlagOptions` | cl:: list options | dtype/device kwargs |
| `CsperfOptions` | profiler/run opts | `torch.profiler` cfg |

Resolved env (`CC`, `CFLAGS`, …) is derived from the bag — not ad-hoc strings
scattered through the CLI.

## 2. Overlay compose (LLVM specificity / Hydra)

Flags go through `OverlayComposer`:

```text
ALL → PRESET(replace) → TYPE → FARM_APP → APP_JSON → RECIPE → CLI
```

- Normal layers **append** (like stacking `-f` flags).
- `PRESET` uses `replace_base=True` (pick sanitize / optimize instead of default).

## 3. Registry (LLVM pass registry / PyTorch `torch.ops`)

`FarmSession` owns:

- `toolchains` — clang, gcc, …
- `presets` — baseline, optimize, sanitize, lto
- `apps` — `database/mysql`, … (linguistic keys)

Lookup is by name; iteration is A–Z, never raw filesystem order.

## 4. Pipeline / PassManager

`Pipeline` + `Stage` ≈ LLVM `PassManager` / PyTorch `nn.Sequential`:

```text
ResolveFlags → Fetch → Build → Test → Perf
```

`plan` stops after resolve (+ emit csperf argv). `run` executes the full chain.
`JobContext` is threaded through stages like an analysis/context object.

## 5. Hierarchy (typed corpus tree)

```text
type (database) → app (mysql) → version (8.0) → recipe
```

Catalog walk is linguistic at every level.

## 6. Session (`LLVMContext`-like)

`FarmSession(root, config)` loads YAML once, fills registries, and exposes
`plan()` / `run()`. The CLI is a thin front-end over the session.

## Code map

| File | Role |
|------|------|
| `patterns.py` | Registry, options, overlays, pipeline |
| `resolve.py` | FarmSession + compose + plan/run |
| `runners.py` | Fetch / build / test / perf stages |
| `models.py` | Pydantic I/O schemas (YAML/JSON on disk) |
| `catalog.py` | Typed tree discovery |
| `cli.py` | Typer UI over FarmSession |
