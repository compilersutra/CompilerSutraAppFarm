# Docker testing matrix

Two axes:

| Axis | Meaning | How |
|------|---------|-----|
| **Distro** | ubuntu / debian / fedora / arch | One image per Dockerfile |
| **CPU arch** | `amd64`, `arm64`, … | Needs working buildx + QEMU |

**Recommended:** distro matrix on **amd64** first.

## Quick start (amd64)

```bash
cd ~/projects/CompilerSutraAppFarm

./scripts/docker_matrix.sh build
./scripts/docker_matrix.sh run ubuntu registries
./scripts/docker_matrix.sh run ubuntu plan database/sqlite@3.53 --flags baseline
```

Host path for plan output: `results/plan/.../plan.json`  
(inside the container the tree is mounted at `/farm`).

## App `run` inside Docker

`docker run` mounts the host repo at `/farm`. Images use
[`entrypoint.sh`](entrypoint.sh) to mark `/farm` (and `*`) as a git
`safe.directory` before invoking `csfarm`, so host-owned `cache/` works.

```bash
./scripts/docker_matrix.sh run ubuntu run database/sqlite@3.53 --flags baseline
```

For the full catalog smoke matrix, prefer host `csfarm run` /
`scripts/batch_run.py`. Use Docker to validate the CLI and sample apps across
distros.

## Arm64

This host’s buildx may only list amd64. Cross-building arm64 needs QEMU + a
buildx driver that advertises `linux/arm64`, or a native ARM machine.

```bash
unset CSFARM_PLATFORM
./scripts/docker_matrix.sh build

# later, when platforms allow:
CSFARM_PLATFORM=linux/arm64 ./scripts/docker_matrix.sh build-platform
```

## Files

| Path | Role |
|------|------|
| `docker/Dockerfile.ubuntu` | Ubuntu 24.04 |
| `docker/Dockerfile.debian` | Debian 12 |
| `docker/Dockerfile.fedora` | Fedora 41 |
| `docker/Dockerfile.arch` | Arch rolling |
| `docker/entrypoint.sh` | git safe.directory, then `csfarm` |
| `scripts/docker_matrix.sh` | Build / run matrix |
