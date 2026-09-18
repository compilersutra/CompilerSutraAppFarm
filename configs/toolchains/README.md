# Toolchain definitions

Each file is one compiler people can select.

## Quick customize

1. Edit **`configs/default.yaml`** → `toolchains.enabled`:

```yaml
toolchains:
  default: clang
  enabled:
    - clang
    - gcc
    # - aocc
    # - custom-clang
```

2. Edit or add a YAML here (`clang.yaml`, `gcc.yaml`, …) — set `cc` / `cxx` or absolute `cc_path` / `cxx_path`.

3. Or define inline under `toolchains.define` in `default.yaml` (no new file).

4. Check:

```bash
csfarm registries
csfarm plan database/sqlite --toolchain clang
```

`enabled: false` in a toolchain file keeps it on disk but out of the active list unless you also put its id in `toolchains.enabled`.
