#!/usr/bin/env python3
"""
Usage CSV Importer — Aggregate team usage CSV exports for token/cost analysis.

Parses Cursor team usage CSV exports and produces trend analysis covering:
- Per-user token consumption and cost
- Per-model efficiency comparison
- Cache utilization rates
- Cost trajectory over time
- Session patterns (when and how users interact)

Usage:
    python import-usage-csv.py path/to/export.csv                     # single file
    python import-usage-csv.py data/usage/*.csv                       # multiple files
    python import-usage-csv.py path/to/export.csv --format json       # JSON output
    python import-usage-csv.py path/to/export.csv --output report.md  # custom output

Zero external dependencies — uses Python stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class UsageEvent:
    timestamp: datetime
    date_str: str
    user: str
    kind: str
    model: str
    max_mode: str
    input_with_cache: int
    input_without_cache: int
    cache_read: int
    output_tokens: int
    total_tokens: int
    cost: float
    source_file: str


# ---------------------------------------------------------------------------
# 1. Parsing
# ---------------------------------------------------------------------------
def _parse_int(val: str) -> int:
    try:
        return int(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


def _parse_float(val: str) -> float:
    try:
        return float(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _parse_timestamp(val: str) -> Optional[datetime]:
    val = val.strip().strip('"')
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def parse_csv_file(csv_path: Path) -> List[UsageEvent]:
    """Parse a single Cursor team usage CSV export."""
    events: List[UsageEvent] = []

    try:
        with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = _parse_timestamp(row.get("Date", ""))
                if ts is None:
                    continue

                events.append(UsageEvent(
                    timestamp=ts,
                    date_str=ts.strftime("%Y-%m-%d"),
                    user=row.get("User", "").strip(),
                    kind=row.get("Kind", "").strip(),
                    model=row.get("Model", "").strip(),
                    max_mode=row.get("Max Mode", "").strip(),
                    input_with_cache=_parse_int(row.get("Input (w/ Cache Write)", "0")),
                    input_without_cache=_parse_int(row.get("Input (w/o Cache Write)", "0")),
                    cache_read=_parse_int(row.get("Cache Read", "0")),
                    output_tokens=_parse_int(row.get("Output Tokens", "0")),
                    total_tokens=_parse_int(row.get("Total Tokens", "0")),
                    cost=_parse_float(row.get("Cost", "0")),
                    source_file=csv_path.name,
                ))

    except OSError as e:
        print(f"  WARNING: Could not read {csv_path}: {e}", file=sys.stderr)

    return events


def load_all_csvs(csv_paths: List[Path]) -> List[UsageEvent]:
    """Load events from multiple CSV files, deduplicating by timestamp+user."""
    all_events: List[UsageEvent] = []
    seen: set = set()

    for path in csv_paths:
        if not path.exists():
            print(f"  WARNING: File not found: {path}", file=sys.stderr)
            continue
        events = parse_csv_file(path)
        for e in events:
            key = (e.timestamp.isoformat(), e.user, e.model, e.total_tokens)
            if key not in seen:
                seen.add(key)
                all_events.append(e)

    all_events.sort(key=lambda e: e.timestamp)
    return all_events


# ---------------------------------------------------------------------------
# 2. Analysis Functions
# ---------------------------------------------------------------------------
def analyze_overview(events: List[UsageEvent]) -> Dict:
    """High-level usage summary."""
    users = set(e.user for e in events)
    models = set(e.model for e in events)
    dates = set(e.date_str for e in events)

    total_tokens = sum(e.total_tokens for e in events)
    total_cost = sum(e.cost for e in events)
    total_input = sum(e.input_without_cache for e in events)
    total_cache = sum(e.cache_read for e in events)
    total_output = sum(e.output_tokens for e in events)

    return {
        "total_events": len(events),
        "unique_users": len(users),
        "users": sorted(users),
        "unique_models": len(models),
        "models": sorted(models),
        "date_range": {
            "first": min(dates) if dates else "",
            "last": max(dates) if dates else "",
            "days": len(dates),
        },
        "totals": {
            "tokens": total_tokens,
            "input_tokens": total_input,
            "cache_read_tokens": total_cache,
            "output_tokens": total_output,
            "cost": round(total_cost, 2),
        },
        "averages": {
            "tokens_per_request": round(total_tokens / len(events)) if events else 0,
            "cost_per_request": round(total_cost / len(events), 4) if events else 0,
            "requests_per_day": round(len(events) / len(dates), 1) if dates else 0,
        },
    }


def analyze_per_user(events: List[UsageEvent]) -> Dict:
    """Per-user breakdown."""
    user_events: Dict[str, List[UsageEvent]] = defaultdict(list)
    for e in events:
        user_events[e.user].append(e)

    users: List[Dict] = []
    for user, evts in sorted(user_events.items()):
        total_tokens = sum(e.total_tokens for e in evts)
        total_cost = sum(e.cost for e in evts)
        total_cache = sum(e.cache_read for e in evts)
        total_input = sum(e.input_without_cache for e in evts)

        cache_rate = round(total_cache / (total_cache + total_input) * 100, 1) if (total_cache + total_input) > 0 else 0

        users.append({
            "user": user,
            "requests": len(evts),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 2),
            "avg_tokens_per_request": round(total_tokens / len(evts)) if evts else 0,
            "avg_cost_per_request": round(total_cost / len(evts), 4) if evts else 0,
            "cache_hit_rate": cache_rate,
            "models_used": sorted(set(e.model for e in evts)),
        })

    users.sort(key=lambda u: -u["total_cost"])
    return {"users": users}


def analyze_per_model(events: List[UsageEvent]) -> Dict:
    """Per-model efficiency comparison."""
    model_events: Dict[str, List[UsageEvent]] = defaultdict(list)
    for e in events:
        model_events[e.model].append(e)

    models: List[Dict] = []
    for model, evts in sorted(model_events.items()):
        total_tokens = sum(e.total_tokens for e in evts)
        total_cost = sum(e.cost for e in evts)
        total_cache = sum(e.cache_read for e in evts)
        total_input = sum(e.input_without_cache for e in evts)
        total_output = sum(e.output_tokens for e in evts)

        cache_rate = round(total_cache / (total_cache + total_input) * 100, 1) if (total_cache + total_input) > 0 else 0
        input_output_ratio = round(total_input / total_output, 1) if total_output > 0 else 0

        models.append({
            "model": model,
            "requests": len(evts),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 2),
            "avg_tokens_per_request": round(total_tokens / len(evts)) if evts else 0,
            "avg_cost_per_request": round(total_cost / len(evts), 4) if evts else 0,
            "cache_hit_rate": cache_rate,
            "input_output_ratio": input_output_ratio,
            "avg_output_tokens": round(total_output / len(evts)) if evts else 0,
        })

    models.sort(key=lambda m: -m["total_cost"])
    return {"models": models}


def analyze_daily_trends(events: List[UsageEvent]) -> Dict:
    """Day-by-day usage trends."""
    daily: Dict[str, List[UsageEvent]] = defaultdict(list)
    for e in events:
        daily[e.date_str].append(e)

    days: List[Dict] = []
    for date, evts in sorted(daily.items()):
        total_tokens = sum(e.total_tokens for e in evts)
        total_cost = sum(e.cost for e in evts)
        total_cache = sum(e.cache_read for e in evts)
        total_input = sum(e.input_without_cache for e in evts)
        users = set(e.user for e in evts)

        cache_rate = round(total_cache / (total_cache + total_input) * 100, 1) if (total_cache + total_input) > 0 else 0

        days.append({
            "date": date,
            "requests": len(evts),
            "active_users": len(users),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 2),
            "cache_hit_rate": cache_rate,
        })

    return {"days": days}


def analyze_cache_efficiency(events: List[UsageEvent]) -> Dict:
    """Analyze cache utilization patterns."""
    total_input = sum(e.input_without_cache for e in events)
    total_cache = sum(e.cache_read for e in events)
    total_cache_write = sum(e.input_with_cache for e in events)

    overall_rate = round(total_cache / (total_cache + total_input) * 100, 1) if (total_cache + total_input) > 0 else 0

    cache_rates = []
    for e in events:
        denominator = e.cache_read + e.input_without_cache
        if denominator > 0:
            cache_rates.append(round(e.cache_read / denominator * 100, 1))

    high_cache = sum(1 for r in cache_rates if r >= 70)
    no_cache = sum(1 for r in cache_rates if r == 0)

    per_model: Dict[str, Dict] = {}
    model_events: Dict[str, List[UsageEvent]] = defaultdict(list)
    for e in events:
        model_events[e.model].append(e)
    for model, evts in sorted(model_events.items()):
        m_input = sum(e.input_without_cache for e in evts)
        m_cache = sum(e.cache_read for e in evts)
        rate = round(m_cache / (m_cache + m_input) * 100, 1) if (m_cache + m_input) > 0 else 0
        per_model[model] = {"cache_rate": rate, "requests": len(evts)}

    return {
        "overall_cache_rate": overall_rate,
        "total_cache_read_tokens": total_cache,
        "total_input_tokens": total_input,
        "total_cache_write_tokens": total_cache_write,
        "tokens_saved_by_cache": total_cache,
        "cost_saved_estimate": round(total_cache * 0.000001, 2),
        "high_cache_requests_pct": round(high_cache / len(cache_rates) * 100, 1) if cache_rates else 0,
        "no_cache_requests_pct": round(no_cache / len(cache_rates) * 100, 1) if cache_rates else 0,
        "avg_cache_rate": round(mean(cache_rates), 1) if cache_rates else 0,
        "median_cache_rate": round(median(cache_rates), 1) if cache_rates else 0,
        "per_model": per_model,
    }


def analyze_cost_outliers(events: List[UsageEvent]) -> Dict:
    """Identify expensive requests for optimization."""
    sorted_by_cost = sorted(events, key=lambda e: -e.cost)
    top_expensive = []
    for e in sorted_by_cost[:15]:
        top_expensive.append({
            "date": e.date_str,
            "user": e.user,
            "model": e.model,
            "total_tokens": e.total_tokens,
            "input_tokens": e.input_without_cache,
            "cache_tokens": e.cache_read,
            "output_tokens": e.output_tokens,
            "cost": e.cost,
        })

    sorted_by_tokens = sorted(events, key=lambda e: -e.total_tokens)
    top_token = []
    for e in sorted_by_tokens[:10]:
        top_token.append({
            "date": e.date_str,
            "user": e.user,
            "model": e.model,
            "total_tokens": e.total_tokens,
            "cost": e.cost,
        })

    costs = [e.cost for e in events]
    avg_cost = mean(costs) if costs else 0
    expensive_count = sum(1 for c in costs if c > avg_cost * 3)

    return {
        "top_expensive_requests": top_expensive,
        "top_token_requests": top_token,
        "requests_over_3x_avg_cost": expensive_count,
        "avg_cost": round(avg_cost, 4),
    }


# ---------------------------------------------------------------------------
# 3. Report Renderer
# ---------------------------------------------------------------------------
def render_report(
    overview: Dict,
    per_user: Dict,
    per_model: Dict,
    daily: Dict,
    cache: Dict,
    outliers: Dict,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []

    def _h1(t): lines.append(f"# {t}")
    def _h2(t): lines.extend(["", f"## {t}", ""])
    def _h3(t): lines.extend(["", f"### {t}", ""])
    def _p(t): lines.append(t)
    def _blank(): lines.append("")

    _h1("Team Usage Analysis — Cursor AI")
    _p(f"_Auto-generated by `scripts/import-usage-csv.py` on {now}. Do not hand-edit._")
    _blank()

    # --- Overview ---
    _h2("Overview")
    dr = overview.get("date_range", {})
    _p(f"- **Date range**: {dr.get('first', '')} — {dr.get('last', '')} ({dr.get('days', 0)} days)")
    _p(f"- **Total requests**: {overview['total_events']:,}")
    _p(f"- **Active users**: {overview['unique_users']}")
    _p(f"- **Models used**: {', '.join(overview.get('models', []))}")
    totals = overview.get("totals", {})
    _p(f"- **Total tokens**: {totals.get('tokens', 0):,}")
    _p(f"- **Total cost**: ${totals.get('cost', 0):.2f}")
    avgs = overview.get("averages", {})
    _p(f"- **Avg tokens/request**: {avgs.get('tokens_per_request', 0):,}")
    _p(f"- **Avg cost/request**: ${avgs.get('cost_per_request', 0):.4f}")
    _p(f"- **Avg requests/day**: {avgs.get('requests_per_day', 0)}")

    # --- Per User ---
    _h2("Per-User Breakdown")
    _p("| User | Requests | Total Tokens | Total Cost | Avg Tokens/Req | Cache Rate | Models |")
    _p("|---|---:|---:|---:|---:|---:|---|")
    for u in per_user.get("users", []):
        models_str = ", ".join(u["models_used"])
        _p(f"| {u['user']} | {u['requests']} | {u['total_tokens']:,} | ${u['total_cost']:.2f} | {u['avg_tokens_per_request']:,} | {u['cache_hit_rate']}% | {models_str} |")

    # --- Per Model ---
    _h2("Per-Model Comparison")
    _p("| Model | Requests | Total Cost | Avg Cost/Req | Avg Tokens/Req | Cache Rate | I/O Ratio | Avg Output |")
    _p("|---|---:|---:|---:|---:|---:|---:|---:|")
    for m in per_model.get("models", []):
        _p(f"| {m['model']} | {m['requests']} | ${m['total_cost']:.2f} | ${m['avg_cost_per_request']:.4f} | {m['avg_tokens_per_request']:,} | {m['cache_hit_rate']}% | {m['input_output_ratio']} | {m['avg_output_tokens']:,} |")

    # --- Daily Trends ---
    _h2("Daily Trends")
    _p("| Date | Requests | Users | Total Tokens | Cost | Cache Rate |")
    _p("|---|---:|---:|---:|---:|---:|")
    for d in daily.get("days", []):
        _p(f"| {d['date']} | {d['requests']} | {d['active_users']} | {d['total_tokens']:,} | ${d['total_cost']:.2f} | {d['cache_hit_rate']}% |")

    # --- Cache Efficiency ---
    _h2("Cache Efficiency")
    _p(f"- **Overall cache hit rate**: {cache['overall_cache_rate']}%")
    _p(f"- **Total tokens saved by cache**: {cache['total_cache_read_tokens']:,}")
    _p(f"- **Avg per-request cache rate**: {cache['avg_cache_rate']}%")
    _p(f"- **Median per-request cache rate**: {cache['median_cache_rate']}%")
    _p(f"- **Requests with >70% cache**: {cache['high_cache_requests_pct']}%")
    _p(f"- **Requests with 0% cache**: {cache['no_cache_requests_pct']}%")

    pm = cache.get("per_model", {})
    if pm:
        _h3("Cache Rate by Model")
        _p("| Model | Cache Rate | Requests |")
        _p("|---|---:|---:|")
        for model, data in sorted(pm.items(), key=lambda x: -x[1]["cache_rate"]):
            _p(f"| {model} | {data['cache_rate']}% | {data['requests']} |")

    # --- Cost Outliers ---
    _h2("Cost Outliers")
    _p(f"- **Requests >3x avg cost**: {outliers['requests_over_3x_avg_cost']} (avg cost: ${outliers['avg_cost']:.4f})")

    top_exp = outliers.get("top_expensive_requests", [])
    if top_exp:
        _h3("Top 15 Most Expensive Requests")
        _p("| Date | User | Model | Total Tokens | Input | Cache | Output | Cost |")
        _p("|---|---|---|---:|---:|---:|---:|---:|")
        for e in top_exp:
            _p(f"| {e['date']} | {e['user']} | {e['model']} | {e['total_tokens']:,} | {e['input_tokens']:,} | {e['cache_tokens']:,} | {e['output_tokens']:,} | ${e['cost']:.2f} |")

    # --- Recommendations ---
    _h2("Recommendations")
    recs: List[str] = []

    if cache["overall_cache_rate"] < 50:
        recs.append(f"**Cache hit rate is {cache['overall_cache_rate']}%** — consider structuring conversations to maintain context continuity, which improves cache utilization.")

    if outliers["requests_over_3x_avg_cost"] > 5:
        recs.append(f"**{outliers['requests_over_3x_avg_cost']} requests exceed 3x the average cost** — review the top expensive requests above. Large context windows from monolithic files are a common cause.")

    total_cost = overview.get("totals", {}).get("cost", 0)
    days = overview.get("date_range", {}).get("days", 1)
    daily_cost = total_cost / max(days, 1)
    if daily_cost > 5:
        recs.append(f"**Daily cost averages ${daily_cost:.2f}** — consider whether the per-story markdown files are being used effectively to reduce retrieval size.")

    if not recs:
        recs.append("Usage patterns look healthy. No critical optimizations needed.")

    for i, rec in enumerate(recs, 1):
        _p(f"{i}. {rec}")

    return "
".join(lines) + "
"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Import and analyze Cursor team usage CSV exports")
    parser.add_argument("csv_files", nargs="*", help="CSV file(s) to import")
    parser.add_argument("--output", help="Output file path (default: artifacts/analysis/usage-trends.md)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    artifacts_dir = project_root / "artifacts" / "analysis"

    csv_paths: List[Path] = []

    if args.csv_files:
        csv_paths = [Path(f) for f in args.csv_files]
    else:
        data_dir = project_root / "data" / "usage"
        if data_dir.exists():
            csv_paths = sorted(data_dir.glob("*.csv"))

        downloads = Path.home() / "Downloads"
        if not csv_paths and downloads.exists():
            csv_paths = sorted(downloads.glob("team-usage-events-*.csv"))

    if not csv_paths:
        print("ERROR: No CSV files provided or found.", file=sys.stderr)
        print("  Usage: python import-usage-csv.py path/to/export.csv", file=sys.stderr)
        print("  Or place CSVs in data/usage/ directory.", file=sys.stderr)
        return 1

    print(f"
=== Usage CSV Importer ===")
    for p in csv_paths:
        print(f"  Input: {p}")

    print("  Loading events...")
    events = load_all_csvs(csv_paths)
    print(f"  Loaded {len(events)} events (deduplicated)")

    if not events:
        print("  No valid events found.")
        return 1

    print("  Analyzing overview...")
    overview = analyze_overview(events)

    print("  Analyzing per-user...")
    per_user = analyze_per_user(events)

    print("  Analyzing per-model...")
    per_model = analyze_per_model(events)

    print("  Analyzing daily trends...")
    daily = analyze_daily_trends(events)

    print("  Analyzing cache efficiency...")
    cache_data = analyze_cache_efficiency(events)

    print("  Finding cost outliers...")
    outliers = analyze_cost_outliers(events)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = artifacts_dir / ("usage-trends.json" if args.format == "json" else "usage-trends.md")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        data = {
            "generated": datetime.now().isoformat(),
            "overview": overview,
            "per_user": per_user,
            "per_model": per_model,
            "daily": daily,
            "cache": cache_data,
            "outliers": outliers,
        }
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        report = render_report(overview, per_user, per_model, daily, cache_data, outliers)
        out_path.write_text(report, encoding="utf-8")

    print(f"
  Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
