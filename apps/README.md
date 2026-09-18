# Apps corpus (linguistic order)

Folders are always listed **A→Z**:

1. **type** (`database`, `media`, `systems`, …)
2. **app** (`mongodb`, `mysql`, …)
3. **version** under `versions/<series>/`

## Universal version folder (every app)

Each `versions/<series>/` contains the same four files:

```text
versions/
  8.0/
    lifecycle.json      # EOL / support status (endoflife.date)
    dependencies.yaml   # packages + Linux distro install (arch/debian/fedora/rhel/ubuntu)
    recipe.json         # fetch / build / test / csperf for csfarm
    README.md           # human summary
```

Do **not** put apps flat at the top level. New apps go under the matching type.

## Bulk catalog (100+)

```bash
python3 scripts/seed_app_catalog.py          # add missing apps (keeps rich trees)
# python3 scripts/seed_app_catalog.py --force  # rewrite catalog-seeded apps
```

Source of truth: `configs/app_catalog.json` (115 entries). Rich multi-version apps (mongodb/mysql/postgres/sqlite/ffmpeg/redis) are left intact.

Re-seed / refresh multi-version corpora for the big six:

```bash
python3 scripts/seed_version_corpus.py
```

Address a series: `csfarm show database/mongodb@8.3` or `csfarm plan media/ffmpeg@7.1`.
