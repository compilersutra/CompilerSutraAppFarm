#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Distro (± CPU arch) matrix — plain `docker` (no compose/buildx plugins required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM="${CSFARM_PLATFORM:-}"   # e.g. linux/arm64
PLATFORMS="${CSFARM_PLATFORMS:-linux/amd64,linux/arm64}"

# Required for reproducible builds; buildx binary may live in ~/.docker/cli-plugins
export DOCKER_BUILDKIT=1
export BUILDKIT_PROGRESS="${BUILDKIT_PROGRESS:-plain}"
export PATH="${HOME}/.docker/cli-plugins:${PATH}"

docker_build() {
  local plat_args=()
  if [[ -n "$PLATFORM" ]]; then
    plat_args=(--platform "$PLATFORM")
    # Fail early if this builder cannot target that arch (common on amd64 hosts
    # without a working QEMU+buildx container driver).
    if command -v docker >/dev/null && docker buildx version >/dev/null 2>&1; then
      local plats
      plats="$(docker buildx inspect 2>/dev/null | awk '/Platforms:/{print; exit}' || true)"
      if [[ -n "$plats" && "$plats" != *"${PLATFORM#linux/}"* && "$plats" != *"$PLATFORM"* ]]; then
        cat >&2 <<EOF
ERROR: current buildx builder does not list $PLATFORM
  $plats

This host can run the amd64 distro matrix fine. Cross-building arm64 needs either:
  1) a native ARM machine / cloud arm64 runner, or
  2) a working QEMU + buildx setup (docker-buildx-plugin + binfmt)

Stick to amd64 for now:
  unset CSFARM_PLATFORM
  ./scripts/docker_matrix.sh build
  ./scripts/docker_matrix.sh run ubuntu registries
EOF
        exit 1
      fi
    fi
  fi
  docker build "${plat_args[@]}" --pull "$@"
}

IMAGES=(
  "ubuntu|docker/Dockerfile.ubuntu|csfarm/ubuntu-clang:local"
  "debian|docker/Dockerfile.debian|csfarm/debian-clang:local"
  "fedora|docker/Dockerfile.fedora|csfarm/fedora-clang:local"
  "arch|docker/Dockerfile.arch|csfarm/arch-clang:local"
)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/docker_matrix.sh build [distro]        # all, or one of ubuntu|debian|fedora|arch
  ./scripts/docker_matrix.sh build-platform        # rebuild using CSFARM_PLATFORM (e.g. arm64)
  ./scripts/docker_matrix.sh registries
  ./scripts/docker_matrix.sh plan <target> [args]
  ./scripts/docker_matrix.sh run <distro> <args…>

Env:
  CSFARM_PLATFORM    e.g. linux/arm64 — build/run that arch (needs binfmt/qemu)

Notes:
  - `csfarm plan` writes results/plan/.../plan.json — NOT csperf.json
  - csperf.json appears only after a real `csperf run`
  - On the host path is: results/...  (inside container: /farm/results/...)
  - This Docker has no `buildx` plugin — use build-platform, not buildx-push
EOF
}

platform_flags() {
  if [[ -n "$PLATFORM" ]]; then
    echo --platform "$PLATFORM"
  fi
}

image_for() {
  local want="$1" row name dockerfile image
  for row in "${IMAGES[@]}"; do
    IFS='|' read -r name dockerfile image <<<"$row"
    if [[ "$name" == "$want" ]]; then
      echo "$image"
      return 0
    fi
  done
  return 1
}

ensure_image() {
  local image="$1" dockerfile="$2"
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "Image $image missing — building..."
    docker_build -f "$ROOT/$dockerfile" -t "$image" "$ROOT"
  fi
}

cmd="${1:-}"
shift || true

case "$cmd" in
  build)
    only="${1:-}"
    for row in "${IMAGES[@]}"; do
      IFS='|' read -r name dockerfile image <<<"$row"
      if [[ -n "$only" && "$name" != "$only" ]]; then
        continue
      fi
      echo "======== build $image ========"
      docker_build -f "$ROOT/$dockerfile" -t "$image" "$ROOT"
    done
    ;;
  build-platform)
    if [[ -z "$PLATFORM" ]]; then
      echo "Set CSFARM_PLATFORM first, e.g.:" >&2
      echo "  CSFARM_PLATFORM=linux/arm64 ./scripts/docker_matrix.sh build-platform" >&2
      exit 1
    fi
    echo "Using DOCKER_BUILDKIT=1 + --platform $PLATFORM (qemu/binfmt required)"
    for row in "${IMAGES[@]}"; do
      IFS='|' read -r name dockerfile image <<<"$row"
      # tag includes arch to avoid clobbering amd64 :local
      arch_tag="${image%:local}:$(echo "$PLATFORM" | tr '/' '-')"
      echo "======== build $arch_tag ========"
      docker_build -f "$ROOT/$dockerfile" -t "$arch_tag" "$ROOT"
    done
    ;;
  buildx-push)
    echo "ERROR: docker buildx is not installed on this host." >&2
    echo "Use instead:" >&2
    echo "  CSFARM_PLATFORM=linux/arm64 ./scripts/docker_matrix.sh build-platform" >&2
    echo "  CSFARM_PLATFORM=linux/arm64 ./scripts/docker_matrix.sh run ubuntu registries" >&2
    exit 1
    ;;
  registries|list|flags)
    for row in "${IMAGES[@]}"; do
      IFS='|' read -r name dockerfile image <<<"$row"
      run_image="$image"
      if [[ -n "$PLATFORM" ]]; then
        run_image="${image%:local}:$(echo "$PLATFORM" | tr '/' '-')"
        if ! docker image inspect "$run_image" >/dev/null 2>&1; then
          echo "Missing $run_image — run: CSFARM_PLATFORM=$PLATFORM ./scripts/docker_matrix.sh build-platform" >&2
          exit 1
        fi
      else
        ensure_image "$image" "$dockerfile"
      fi
      echo "======== $name ($cmd) @ ${PLATFORM:-host} ========"
      # shellcheck disable=SC2046
      docker run --rm $(platform_flags) -v "$ROOT:/farm:rw" -w /farm "$run_image" "$cmd"
    done
    ;;
  plan)
    target="${1:?target required}"
    shift || true
    for row in "${IMAGES[@]}"; do
      IFS='|' read -r name dockerfile image <<<"$row"
      run_image="$image"
      if [[ -n "$PLATFORM" ]]; then
        run_image="${image%:local}:$(echo "$PLATFORM" | tr '/' '-')"
        if ! docker image inspect "$run_image" >/dev/null 2>&1; then
          echo "Missing $run_image — run: CSFARM_PLATFORM=$PLATFORM ./scripts/docker_matrix.sh build-platform" >&2
          exit 1
        fi
      else
        ensure_image "$image" "$dockerfile"
      fi
      echo "======== $name plan $target ========"
      # shellcheck disable=SC2046
      docker run --rm $(platform_flags) -v "$ROOT:/farm:rw" -w /farm "$run_image" plan "$target" "$@"
    done
    ;;
  run)
    distro="${1:?distro required: ubuntu|debian|fedora|arch}"
    shift
    image="$(image_for "$distro")" || { echo "unknown distro: $distro" >&2; exit 1; }
    run_image="$image"
    if [[ -n "$PLATFORM" ]]; then
      run_image="${image%:local}:$(echo "$PLATFORM" | tr '/' '-')"
      if ! docker image inspect "$run_image" >/dev/null 2>&1; then
        echo "Missing $run_image — building once..."
        dockerfile=""
        for row in "${IMAGES[@]}"; do
          IFS='|' read -r name dockerfile img <<<"$row"
          [[ "$name" == "$distro" ]] && break
        done
        docker_build -f "$ROOT/$dockerfile" -t "$run_image" "$ROOT"
      fi
    else
      for row in "${IMAGES[@]}"; do
        IFS='|' read -r name dockerfile img <<<"$row"
        if [[ "$name" == "$distro" ]]; then
          ensure_image "$image" "$dockerfile"
          break
        fi
      done
    fi
    # shellcheck disable=SC2046
    # Use image ENTRYPOINT (entrypoint.sh → git safe.directory, then csfarm)
    docker run --rm $(platform_flags) -v "$ROOT:/farm:rw" -w /farm "$run_image" "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
