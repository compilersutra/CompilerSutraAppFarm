# Changelog

All notable changes to CompilerSutra AppFarm are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Tier-1 trusted core: `configs/tier1.yaml`, `batch_run.py --tier1` / `--ci`
- Functional tests for most tier-1 recipes (round-trip / eval / config check)
- `.github/workflows/tier1.yml` (CI subset + nightly full)
- `docs/tier1-matrix.md` + `scripts/tier1_matrix.py`

## [0.1.0] — 2026-09-18

### Added

- `csfarm` CLI: `list`, `registries`, `flags`, `plan`, `run`, `matrix-plan`
- Catalog of **115** OSS apps under `apps/<type>/<app>/versions/...`
- Flag overlay composer (all → preset → type → app → recipe → CLI)
- Fetch/build/test/perf pipeline with archive + git sources
- `scripts/batch_run.py` green/red batch report
- Docker distro images: Ubuntu, Debian, Fedora, Arch (`scripts/docker_matrix.sh`)
- Unit tests for catalog ordering, overlays, and toolchain config
- Docs: README, ARCHITECTURE, RELEASE, VISION, CONTRIBUTING
- Docker entrypoint marks host-mounted `/farm` as git `safe.directory`

### Known limitations (alpha)

- Many recipes use **smoke** tests (artifact/`--version`), not full upstream suites
- Host batch is the validated path; Docker sample `csfarm run` works with
  the entrypoint; full in-image farm rebuilds are still incomplete
- `database/mongodb` recipe builds mongo-c-driver, not full `mongod`
- Arm64 image cross-build requires extra buildx/QEMU setup on amd64 hosts

[0.1.0]: https://github.com/compilersutra/CompilerSutraAppFarm/releases/tag/v0.1.0
