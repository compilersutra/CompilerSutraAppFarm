# SPDX-License-Identifier: Apache-2.0

# Recipe authoring

A version lives at `apps/<type>/<name>/versions/<ver>/recipe.json`.
Schema: [`schemas/recipe.schema.json`](../schemas/recipe.schema.json).

## Minimum

```json
{
  "version": "1.0.0",
  "source": { "kind": "archive", "url": "https://example.com/app-1.0.0.tar.gz", "ref": "" },
  "build": { "system": "configure", "args": [] },
  "test": { "command": ["./app", "--version"], "timeout_sec": 60 }
}
```

## Source

| `kind` | When |
|--------|------|
| `git` (default) | `url` + `ref` (tag/commit). Submodules are fetched shallow. |
| `archive` | Release tarball. Prefer this when git needs autotools bootstrap or baseruby. |

## Build systems

`cmake` · `configure` · `make` · `meson` · `custom` (`commands` is a list of argv lists).

Keep builds CI-friendly: no network after fetch, no `sudo`, no full `make check` unless that is the point.

## Test

- **Functional** (tier-1): round-trip, eval, or `nginx -t` with a local prefix.
- **Smoke**: `--version` / artifact `test -f` — say so in the version README.
- Timeouts: 30–120s for smoke; longer only if the binary is slow to start.

## Perf

`perf.csperf.workload` should do a little work, not only `--version`, when you care about timing.
Without `csperf` on `PATH`, AppFarm writes **wall-clock** samples (`tool: csfarm`, `hardware_counters: false`).
That is not a hardware performance claim. See [PERF.md](PERF.md).

## Checklist

- [ ] `csfarm plan type/name@version --flags baseline` resolves
- [ ] `csfarm run type/name@version --flags baseline --skip-perf` is green
- [ ] Do not commit `cache/`, `work/`, or `results/`
