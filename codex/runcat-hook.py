#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Adapted for runcat-ai-metrics from RunCat Neo integration examples.
# Modifications: usage aggregation, countdowns, and DeepSeek balance integration.
"""RunCat Neo custom metrics producer for Codex lifecycle hooks."""

import fcntl
import json
import math
import shutil
import subprocess
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path


OUT = Path(os.environ.get("RUNCAT_OUT_FILE", str(Path.home() / ".codex" / "runcat-usage.json")))

TIMEZONE = os.environ.get("RUNCAT_TIMEZONE", "Asia/Shanghai")


def format_tokens(value):
    for scale, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= scale:
            return f"{value / scale:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{value:,.0f}"


def usage_metrics(report, today):
    rows = report.get("daily")
    if not isinstance(rows, list):
        raise ValueError("ccusage response has no daily array")
    totals = {1: 0, 7: 0, 30: 0}
    for row in rows:
        day = date.fromisoformat(row["date"])
        tokens = row["totalTokens"]
        if isinstance(tokens, bool) or not isinstance(tokens, (int, float)) or not math.isfinite(tokens) or tokens < 0:
            raise ValueError("Invalid daily token total")
        for days in totals:
            if today - timedelta(days=days - 1) <= day <= today:
                totals[days] += tokens
    metrics = [
        {"title": "Today tokens", "formattedValue": format_tokens(totals[1])},
        {"title": "7d tokens", "formattedValue": format_tokens(totals[7])},
        {"title": "30d tokens", "formattedValue": format_tokens(totals[30])},
        {"title": "30d daily average", "formattedValue": format_tokens(totals[30] / 30)},
    ]

    return metrics


def load_usage_metrics():
    installed = Path.home() / ".codex/runcat-tools/node_modules/.bin/ccusage"
    executable = os.environ.get("RUNCAT_CCUSAGE") or (str(installed) if installed.exists() else shutil.which("ccusage"))
    if not executable:
        raise RuntimeError("ccusage is not installed; see the sample README")
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    result = subprocess.run(
        [executable, "codex", "daily", "--since", str(today - timedelta(days=29)),
         "--until", str(today), "--timezone", TIMEZONE, "--json", "--offline", "--no-cost"],
        capture_output=True, text=True, check=True, timeout=90,
    )
    return usage_metrics(json.loads(result.stdout), today)


def percentage_metric(title, used_percentage):
    if not isinstance(used_percentage, (int, float)):
        return None
    clamped_percentage = max(0.0, min(float(used_percentage), 100.0))
    normalized_value = clamped_percentage / 100
    formatted_percentage = f"{clamped_percentage:.1f}".rstrip("0").rstrip(".")
    return {
        "title": title,
        "formattedValue": f"{formatted_percentage}%",
        "normalizedValue": round(normalized_value, 4),
    }


def window_title(window_minutes):
    if not isinstance(window_minutes, (int, float)):
        return None
    if window_minutes % 1440 == 0:
        return f"{window_minutes / 1440:g}d"
    if window_minutes % 60 == 0:
        return f"{window_minutes / 60:g}h"
    return f"{window_minutes:g}m"


def latest_token_count(transcript_path):
    if not transcript_path:
        return None
    latest = None
    try:
        with Path(transcript_path).open(encoding="utf-8") as transcript:
            for line in transcript:
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(event, dict):
                    continue
                payload = event.get("payload") or {}
                if not isinstance(payload, dict):
                    continue
                if payload.get("type") == "token_count":
                    latest = payload
    except OSError:
        return None
    return latest


def rate_limit_metrics(token_count):
    rate_limits = (token_count or {}).get("rate_limits") or {}
    metrics = []
    titles = set()
    for key in ("primary", "secondary"):
        limit = rate_limits.get(key) or {}
        title = window_title(limit.get("window_minutes"))
        metric = percentage_metric(title, limit.get("used_percent")) if title else None
        if metric is not None and title not in titles:
            metrics.append(metric)
            titles.add(title)
            reset = limit.get("resets_at")
            if isinstance(reset, (int, float)) and not isinstance(reset, bool) and math.isfinite(reset):
                row = {"title": f"{title} reset", "_resetAt": reset,
                       "_windowSeconds": limit["window_minutes"] * 60}
                update_countdown(row, datetime.now(timezone.utc).timestamp())
                metrics.append(row)
    return metrics


def update_countdown(row, now):
    remaining = max(0, row["_resetAt"] - now)
    minutes = math.ceil(remaining / 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    parts = ([f"{days}d"] if days else []) + ([f"{hours}h"] if hours else []) + [f"{minutes}m"]
    row["formattedValue"] = " ".join(parts) + " remaining" if remaining else "Due — awaiting quota refresh"
    window = row.get("_windowSeconds", 0)
    row["normalizedValue"] = min(1, remaining / window) if window > 0 else 0


def refresh_countdowns():
    if not OUT.exists():
        return
    snapshot = json.loads(OUT.read_text())
    now = datetime.now(timezone.utc).timestamp()
    changed = False
    for row in snapshot.get("metrics", []):
        if "_resetAt" in row:
            update_countdown(row, now)
            changed = True
    # Keep lastUpdatedDate: refreshing a clock is not fresh token/quota data.
    if changed:
        save_snapshot(snapshot)


def write_snapshot(hook_input):
    token_count = latest_token_count(hook_input.get("transcript_path"))
    rate_metrics = rate_limit_metrics(token_count)
    metrics = []
    if not rate_metrics and OUT.exists():
        try:
            previous = json.loads(OUT.read_text())
            rate_metrics = [row for row in previous.get("metrics", [])
                            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[mhd](?: reset)?", row.get("title", ""))]
            if rate_metrics:
                rate_metrics.append({"title": "Quota status", "formattedValue": "Previous snapshot (not refreshed)"})
        except (ValueError, OSError):
            pass
    metrics.extend(rate_metrics)
    try:
        metrics.extend(load_usage_metrics())
    except Exception as error:
        print(f"RunCat usage statistics: {error}", file=sys.stderr)
        metrics.append({"title": "Token statistics", "formattedValue": "Unavailable — check ccusage"})
    snapshot = {
        "title": "Codex",
        "symbol": "camera.aperture",
        "metrics": metrics,
        "lastUpdatedDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    today = next((row for row in metrics if row["title"] == "Today tokens"), None)
    if today:
        snapshot["metricsBarValue"] = today["formattedValue"]
    save_snapshot(snapshot)


def save_snapshot(snapshot):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(prefix=".runcat-", dir=str(OUT.parent))
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            json.dump(snapshot, output, ensure_ascii=False)
        os.replace(temporary_path, OUT)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def main():
    try:
        hook_input = {} if "--refresh-countdown" in sys.argv else json.load(sys.stdin)
        if not isinstance(hook_input, dict):
            hook_input = {}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.with_suffix(".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("{}")
                return
            if "--refresh-countdown" in sys.argv:
                refresh_countdowns()
            else:
                write_snapshot(hook_input)
    except Exception as error:
        print(f"RunCat Codex hook: {error}", file=sys.stderr)
    print("{}")


if __name__ == "__main__":
    main()
