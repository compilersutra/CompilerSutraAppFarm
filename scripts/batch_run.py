#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Batch-run catalog apps and write a green/red report."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from csfarm.resolve import FarmSession  # noqa: E402

TIER1_PATH = ROOT / "configs" / "tier1.yaml"


def load_tier1(path: Path = TIER1_PATH) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not data.get("apps"):
        raise SystemExit(f"Invalid tier-1 config: {path}")
    return data


def tier1_targets(*, ci: bool = False) -> list[str]:
    """Return ``type/name@version`` strings from configs/tier1.yaml."""
    data = load_tier1()
    apps = data["apps"]
    if ci:
        subset = set(data.get("ci_subset") or [])
        if not subset:
            raise SystemExit("tier1.yaml ci_subset is empty")
        apps = [a for a in apps if a["id"] in subset]
        missing = subset - {a["id"] for a in apps}
        if missing:
            raise SystemExit(f"ci_subset ids not in apps: {sorted(missing)}")
    return [f"{a['id']}@{a['version']}" for a in apps]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--type", action="append", dest="types", help="Filter type (repeatable)")
    ap.add_argument("--only", action="append", dest="only", help="Only these app ids")
    ap.add_argument(
        "--tier1",
        action="store_true",
        help="Run configs/tier1.yaml apps (full set unless --ci)",
    )
    ap.add_argument(
        "--ci",
        action="store_true",
        help="With --tier1, use ci_subset only (faster Actions gate)",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max apps (0=all)")
    ap.add_argument("--toolchain", default="clang")
    ap.add_argument("--flags", default="baseline")
    ap.add_argument("--skip-test", action="store_true")
    ap.add_argument("--skip-perf", action="store_true")
    ap.add_argument("--continue", dest="cont", action="store_true", help="Skip already-green apps")
    ap.add_argument(
        "--report",
        default=str(ROOT / "results" / "batch" / "report.json"),
        help="Report path",
    )
    args = ap.parse_args()

    session = FarmSession(ROOT, ROOT / "configs" / "default.yaml")

    targets: list[str] | None = None
    if args.tier1:
        targets = tier1_targets(ci=args.ci)
        if args.only:
            want = set(args.only)
            targets = [t for t in targets if t.split("@", 1)[0] in want]
        if args.types:
            targets = [t for t in targets if t.split("/", 1)[0] in args.types]
        if args.limit:
            targets = targets[: args.limit]
    else:
        apps = session.catalog.iter_apps()
        if args.types:
            apps = [a for a in apps if a.type in args.types]
        if args.only:
            want = set(args.only)
            apps = [a for a in apps if a.id in want]
        if args.limit:
            apps = apps[: args.limit]
        targets = [f"{a.id}@{a.identity.default_version}" for a in apps]

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    prior: dict = {}
    if report_path.is_file():
        try:
            prior = json.loads(report_path.read_text(encoding="utf-8")).get("results", {}) or {}
        except json.JSONDecodeError:
            prior = {}

    results: dict[str, dict] = dict(prior) if isinstance(prior, dict) else {}

    for i, target in enumerate(targets, 1):
        key = target
        if args.cont and results.get(key, {}).get("ok") is True:
            print(f"[{i}/{len(targets)}] SKIP green {key}")
            continue

        print(f"[{i}/{len(targets)}] RUN {key} ...", flush=True)
        t0 = time.time()
        try:
            job = session.run(
                target,
                toolchain_id=args.toolchain,
                preset_name=args.flags,
                skip_test=args.skip_test,
                skip_perf=args.skip_perf,
            )
            ok = job.ok
            entry = {
                "ok": ok,
                "seconds": round(time.time() - t0, 1),
                "pipeline": job.pipeline_results,
                "result_dir": job.result_dir,
            }
        except Exception as exc:  # noqa: BLE001
            ok = False
            entry = {"ok": False, "seconds": round(time.time() - t0, 1), "error": str(exc)}

        results[key] = entry
        if ok:
            print(f"  OK ({entry['seconds']}s)")
        else:
            detail = ""
            for st in entry.get("pipeline", []):
                if st.get("status") == "failed":
                    detail = f"{st.get('name')}: {st.get('detail', '')[:160]}"
                    break
            print(f"  FAIL ({entry['seconds']}s) {detail or entry.get('error', '')}")

        green = sum(1 for v in results.values() if v.get("ok"))
        red = sum(1 for v in results.values() if v.get("ok") is False)
        report_path.write_text(
            json.dumps(
                {
                    "green": green,
                    "red": red,
                    "total": len(results),
                    "toolchain": args.toolchain,
                    "flags": args.flags,
                    "tier1": bool(args.tier1),
                    "ci_subset": bool(args.tier1 and args.ci),
                    "results": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    green = sum(1 for v in results.values() if v.get("ok"))
    red = sum(1 for v in results.values() if v.get("ok") is False)
    print(f"\nDone. green={green} red={red} report={report_path}")
    return 0 if red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
