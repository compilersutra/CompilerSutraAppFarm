# SPDX-License-Identifier: Apache-2.0

# Vision

## Problem

Compiler teams need to answer: *does this toolchain and these flags still
build and run real applications?* Most of that work lives in closed vendor
matrices. AppFarm makes the same idea open and scriptable.

## Who it is for

- Compiler / toolchain engineers (clang, gcc, custom LLVM builds)
- Labs comparing flag presets (baseline, optimize, sanitize, LTO)
- Anyone who wants a **typed corpus** of apps with reproducible fetch → build → test → measure

## What AppFarm is

- A catalog of OSS apps (`apps/<type>/<app>/versions/…`) with recipes
- Flag overlays (all → preset → type → app → recipe → CLI)
- Runners that produce machine-readable `run.json` / batch reports
- Hooks toward `csperf` for timing when available

## What AppFarm is not

| Claim people might assume | Reality |
|---------------------------|---------|
| All catalog apps have full upstream test suites | Many recipes are **smoke** (build + version / artifact check) |
| Green on host = green in Docker / every ISA | Host smoke and Docker/QEMU/HW are different runners |
| Timed JSON = hardware performance counters | Without `csperf` + real HW, numbers are wall-clock only |
| QEMU user-mode = real silicon | Emulated correctness only — never sell as HW perf |
| 115 apps = production support commitment | **v0.1.0 alpha**; trust the **tier-1** set once it exists |

## Success bar (near term)

1. CI green on every PR  
2. Tier-1 apps with real tests under clang/gcc — see [`tier1.yaml`](../configs/tier1.yaml)  
3. Results always tagged with runner / ISA / emulated  
4. Perf claims only from documented methodology on real hardware  

See also: [RELEASE.md](RELEASE.md), [ARCHITECTURE.md](ARCHITECTURE.md).
