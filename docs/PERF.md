# SPDX-License-Identifier: Apache-2.0

# Perf methodology

AppFarm can time a recipe workload. That is **not** automatically a hardware
benchmark.

## What a result means

| Field | Meaning |
|-------|---------|
| `tool: csfarm` / `method: wall_clock` | Timed `subprocess` around the workload. No PMU. |
| `tool: csperf` / `hardware_counters: true` | `csperf` was on `PATH` and wrote `csperf-native.json`. |
| `emulated: true` | QEMU or similar — correctness only, never HW perf. |
| `runner` / `isa` | Where it ran. Do not mix host, Docker, and qemu in one table. |

## How we time (fallback)

1. Resolve the workload argv (same as the recipe, with `./build/` fallbacks).
2. Warmup: `warmup_runs` (discarded).
3. Repeats: `repeat_runs`; record wall seconds with `time.perf_counter`.
4. Report min / median / max. No pinning unless `csperf` does it.

## What not to claim

- Host smoke green ≠ fastest compiler.
- Median wall time on a laptop ≠ SPEC / vendor score.
- QEMU user-mode ≠ silicon.
- One run of `./app --version` ≠ application performance.
- Mixing clang and gcc jobs that used different CPUs / load.

## When you publish numbers

- Pin CPU if you can (`taskset` / `csperf` affinity).
- Same machine, quiet system, documented governor.
- State runner, ISA, emulated, toolchain, flags, warmup, repeats.
- Prefer the **tier-1** set over the full 115-app catalog.

See also [VISION.md](VISION.md).
