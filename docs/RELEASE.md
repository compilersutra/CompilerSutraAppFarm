# Release checklist (v0.1.1 alpha)

`v0.1.0` is published. This tree is prepared as **v0.1.1**. Tag only after
push + CI green. Do not claim 1.0.

## Before tagging

- [x] `pytest` green
- [x] `ruff check src tests` clean
- [x] README **Status** table matches reality
- [x] `CHANGELOG.md` `[0.1.1]` written
- [x] `pyproject.toml` / `csfarm.__version__` are `0.1.1`
- [x] No secrets, `cache/`, `work/`, or huge `results/` in the commit
- [x] Push to `main` and confirm GitHub Actions `ci.yml` green
- [ ] Tag `v0.1.1` + GitHub Release from CHANGELOG
- [ ] Repo visibility: public (optional; Apache-2.0 already in tree)

## Suggested smoke before publish

```bash
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check src tests
csfarm doctor
csfarm list | head
csfarm run compression/zstd@1.5.6 --flags baseline
csfarm run database/sqlite@3.53 --flags baseline
./scripts/docker_matrix.sh run ubuntu registries
```

## Tag (only when CI is green)

```bash
git tag -a v0.1.1 -m "CompilerSutra AppFarm 0.1.1 alpha"
git push origin v0.1.1
```

## Do not claim in 0.1.x release notes

- Full upstream correctness for all 115 apps
- Docker from-scratch farm parity with host
- Production support / stable recipe ABI
- QEMU user-mode as hardware performance
