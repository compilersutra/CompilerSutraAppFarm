#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Batch-run catalog apps and write a green/red report."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from csfarm.resolve import FarmSession  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--type", action="append", dest="types", help="Filter type (repeatable)")
    ap.add_argument("--only", action="append", dest="only", help="Only these app ids")
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
    apps = session.catalog.iter_apps()
    if args.types:
        apps = [a for a in apps if a.type in args.types]
    if args.only:
        want = set(args.only)
        apps = [a for a in apps if a.id in want]
    if args.limit:
        apps = apps[: args.limit]

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    prior: dict = {}
    if report_path.is_file():
        try:
            prior = json.loads(report_path.read_text(encoding="utf-8")).get("results", {}) or {}
        except json.JSONDecodeError:
            prior = {}

    results: dict[str, dict] = dict(prior) if isinstance(prior, dict) else {}

    for i, app in enumerate(apps, 1):
        target = f"{app.id}@{app.identity.default_version}"
        key = target
        if args.cont and results.get(key, {}).get("ok") is True:
            print(f"[{i}/{len(apps)}] SKIP green {key}")
            continue

        print(f"[{i}/{len(apps)}] RUN {key} ...", flush=True)
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
