# SPDX-License-Identifier: Apache-2.0
"""Compare batch reports and render a markdown dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in {path}")
    return data


def compare_reports(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_r = old.get("results") or {}
    new_r = new.get("results") or {}
    old_keys = set(old_r)
    new_keys = set(new_r)
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    improved: list[str] = []
    regressed: list[str] = []
    unchanged_green: list[str] = []
    unchanged_red: list[str] = []
    for key in sorted(old_keys & new_keys):
        was = bool(old_r[key].get("ok"))
        now = bool(new_r[key].get("ok"))
        if (not was) and now:
            improved.append(key)
        elif was and (not now):
            regressed.append(key)
        elif now:
            unchanged_green.append(key)
        else:
            unchanged_red.append(key)
    return {
        "old_score": {"green": old.get("green"), "red": old.get("red"), "total": old.get("total")},
        "new_score": {"green": new.get("green"), "red": new.get("red"), "total": new.get("total")},
        "added": added,
        "removed": removed,
        "improved": improved,
        "regressed": regressed,
        "unchanged_green": unchanged_green,
        "unchanged_red": unchanged_red,
    }


def dashboard_markdown(report: dict[str, Any]) -> str:
    results: dict[str, Any] = report.get("results") or {}
    green = report.get("green", sum(1 for v in results.values() if v.get("ok")))
    red = report.get("red", sum(1 for v in results.values() if v.get("ok") is False))
    lines = [
        "# AppFarm batch report",
        "",
        f"- green: **{green}**",
        f"- red: **{red}**",
        f"- total: **{report.get('total', len(results))}**",
        f"- toolchain: `{report.get('toolchain', '?')}`",
        f"- flags: `{report.get('flags', '?')}`",
        f"- runner: `{report.get('runner', 'host')}`",
        f"- isa: `{report.get('isa', '?')}`",
        f"- emulated: `{report.get('emulated', False)}`",
        "",
        "| App | Result | Seconds | Stage |",
        "|-----|--------|---------|-------|",
    ]
    for key in sorted(results, key=str.casefold):
        entry = results[key]
        mark = "✅" if entry.get("ok") else "❌"
        stage = ""
        for st in entry.get("pipeline") or []:
            if st.get("status") == "failed":
                stage = str(st.get("name") or "")
                break
        if not stage and entry.get("error"):
            stage = "error"
        lines.append(f"| {key} | {mark} | {entry.get('seconds', '')} | {stage} |")
    lines.append("")
    return "\n".join(lines)


def write_dashboard(report: dict[str, Any], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dashboard_markdown(report)
    if out.suffix.lower() == ".html":
        body = "<pre>\n" + text.replace("&", "&amp;").replace("<", "&lt;") + "\n</pre>\n"
        out.write_text(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>AppFarm report</title></head>"
            f"<body>{body}</body></html>\n",
            encoding="utf-8",
        )
    else:
        out.write_text(text, encoding="utf-8")
    return out
