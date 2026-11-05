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

## Maintainer seeding (optional)

`configs/app_catalog.json` lists the corpus. Seeding scripts are for maintainers
expanding the farm — prefer hand-edited recipes for reviews:

```bash
python3 scripts/seed_app_catalog.py          # add missing apps (keeps rich trees)
python3 scripts/seed_version_corpus.py       # refresh multi-version big apps
```

Address a series: `csfarm show database/mongodb@8.3` or `csfarm plan media/ffmpeg@7.1`.
