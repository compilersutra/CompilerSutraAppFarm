# Release checklist (v0.1.x alpha)

## Before tagging

- [ ] `pytest` green
- [ ] `ruff check src tests` clean (or documented exceptions)
- [ ] README **Status** table still matches reality
- [ ] `CHANGELOG.md` updated for the version
- [ ] No secrets, `cache/`, `work/`, or huge `results/` in the commit
- [ ] `pyproject.toml` version matches the tag (`0.1.0` → `v0.1.0`)

## Suggested smoke before publish

```bash
source .venv/bin/activate
pip install -e '.[dev]'
pytest
csfarm list | head
csfarm run compression/zstd@1.5.6 --flags baseline
csfarm run database/sqlite@3.53 --flags baseline
./scripts/docker_matrix.sh run ubuntu registries
```

## Tag

```bash
git tag -a v0.1.0 -m "CompilerSutra AppFarm 0.1.0 alpha"
git push origin v0.1.0
```

## Do not claim in 0.1.x release notes

- Full upstream correctness for all 115 apps
- Docker from-scratch farm parity with host
- Production support / stable recipe ABI

Those belong in a later **1.0** once CI covers a tier-1 set with real tests and
Docker `run` is fixed (git safe.directory + richer image deps).
