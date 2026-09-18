# Contributing to CompilerSutra AppFarm

Thanks for helping grow the farm. This repo is an **alpha** compiler-testing
harness — small, reviewable changes beat large drive-by recipe dumps.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Adding or fixing an app

1. Prefer editing `apps/<type>/<app>/versions/<ver>/recipe.json`.
2. Keep **test** commands short and deterministic for CI-friendly smoke
   (binary `--version`, or `test -f` on a built library). Call out in the
   version `README.md` if you only smoke-test.
3. Prefer release **archives** when git bootstrap/gnulib is painful.
4. Prove one host run:

   ```bash
   csfarm run <type>/<app>@<ver> --flags baseline
   ```

5. Do not commit `cache/`, `work/`, `results/`, or local `tools/` build trees.

## Recipes checklist

- [ ] `source.url` + `ref` (or `kind: archive`) resolve
- [ ] Build system matches the upstream tree (`cmake` / `configure` / `meson` / `make` / `custom`)
- [ ] Test does not need network, root, or long `make check` unless intentional
- [ ] Perf workload matches the smoke (or is disabled)

## Code changes

- Python **3.11+**, type-friendly, match existing `csfarm` style
- Run `pytest` and `ruff check src tests` before opening a PR
- Keep commits focused; no Cursor/AI co-author trailers

## License

By contributing, you agree your changes are under the Apache License 2.0.
