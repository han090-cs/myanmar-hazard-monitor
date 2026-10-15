#!/usr/bin/env python3
"""
Rainfall forecast and a simple early-warning level for every township in Myanmar.

    python scripts/fetch_rain_forecast.py             # writes data/rain_forecast.json
    python scripts/fetch_rain_forecast.py --selftest  # offline test of the calculations

For the centre point of each township it reads hourly rainfall from the Open-Meteo forecast API: the last 72 hours
and the next 72 hours. From that it works out
  * past72  rain that already fell in the last 72 hours (wet ground)
  * next24  rain in the next 24 hours
  * next72  rain in the next 72 hours
  * max24   the heaviest 24 hour window inside the next 72 hours
and a warning level 0-3.

The level is a rule of thumb, not a flood model and not an official warning:
  1. base level from max24 using the India Meteorological Department "heavy / very heavy / extremely heavy"
     rain classes (64.5, 115.6 and 204.5 mm in 24 h);
  2. +1 when the last 72 hours were already very wet (150 mm or more);
  3. +1 when at least 15 % of the township is in the "previously flooded" layer.
  Steps 2 and 3 only apply when the base level is at least 1. The result is capped at 3.
These rules have NOT been checked against past floods. Use it as a prompt to look closer and follow DMH announcements.

A point forecast at a township centre says little about rain elsewhere in a large township.
Data: Open-Meteo (non-commercial free tier, attribution required; check their current terms).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
ADMIN_FILE = Path(os.environ.get("ADMIN_FILE", DATA_DIR / "ref" / "admin3_mmr.geojson"))
STATS_FILE = DATA_DIR / "flood_prone_stats.json"
OUT_FILE = DATA_DIR / "rain_forecast.json"

API = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "myanmar-hazard-monitor/1.0 (+https://github.com)"
CHUNK = 40
HEAVY_MM = (64.5, 115.6, 204.5)      # IMD classes for rain in 24 hours
WET_SOIL_MM = 150.0
PRONE_SHARE_PCT = 15.0
MAX_MISSING_FRACTION = 0.2
LOG = logging.getLogger("rain")


# --------------------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------------------

def rolling_max(values: list[float], window: int = 24) -> float:
    if not values:
        return 0.0
    if len(values) <= window:
        return sum(values)
    current = sum(values[:window])
    best = current
    for i in range(window, len(values)):
        current += values[i] - values[i - window]
        best = max(best, current)
    return best


def split_hours(times: list[str], values: list[Optional[float]], now_hour: str) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Split an hourly series into (past, future) around the current hour. ISO time strings sort correctly."""
    past, future = [], []
    for stamp, value in zip(times, values):
        (future if stamp >= now_hour else past).append(value)
    return past, future


def clean(values: list[Optional[float]]) -> tuple[list[float], float]:
    """Replace missing values by 0 and report the share that was missing."""
    if not values:
        return [], 1.0
    missing = sum(1 for v in values if v is None)
    return [0.0 if v is None else float(v) for v in values], missing / len(values)


def classify(max24: float, past72: float, prone_pct: float) -> tuple[int, int, list[str]]:
    """Return (level, base_level, reasons). See the module docstring for the rules."""
    base = sum(1 for threshold in HEAVY_MM if max24 >= threshold)
    level, reasons = base, []
    if base >= 1:
        if past72 >= WET_SOIL_MM:
            level += 1
            reasons.append("wet")
        if prone_pct >= PRONE_SHARE_PCT:
            level += 1
            reasons.append("prone")
    return min(level, 3), base, reasons


def summarise(times: list[str], values: list[Optional[float]], now_hour: str) -> Optional[dict[str, float]]:
    past_raw, future_raw = split_hours(times, values, now_hour)
    past, miss_past = clean(past_raw[-72:])
    future, miss_future = clean(future_raw[:72])
    if len(future) < 24 or miss_future > MAX_MISSING_FRACTION or miss_past > 0.5:
        return None
    return {"past72": round(sum(past), 1), "next24": round(sum(future[:24]), 1),
            "next72": round(sum(future), 1), "max24": round(rolling_max(future, 24), 1)}


# --------------------------------------------------------------------------------------
# Network + files
# --------------------------------------------------------------------------------------

def _get(params: dict[str, Any], retries: int = 4) -> Any:
    import requests

    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            response = requests.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=90)
            if response.status_code == 429 or response.status_code >= 500:
                raise RuntimeError(f"HTTP {response.status_code}")
            if response.status_code >= 400:
                raise ValueError(f"HTTP {response.status_code}: {response.text[:200]}")
            return response.json()
        except ValueError:
            raise
        except Exception as exc:
            last = exc
            LOG.warning("Request failed (%s); retry %d/%d", str(exc)[:120], attempt + 1, retries)
            time.sleep(5 * (attempt + 1) ** 2)
    raise RuntimeError(f"Open-Meteo request failed: {last}")


def fetch_chunk(coords: list[tuple[float, float]]) -> list[dict[str, Any]]:
    base = {"latitude": ",".join(f"{c[0]:.4f}" for c in coords), "longitude": ",".join(f"{c[1]:.4f}" for c in coords),
            "hourly": "precipitation", "timezone": "GMT"}
    try:
        payload = _get({**base, "past_hours": 72, "forecast_hours": 72})
    except ValueError:                     # older API behaviour: whole days only
        payload = _get({**base, "past_days": 3, "forecast_days": 4})
    locations = payload if isinstance(payload, list) else [payload]
    if len(locations) != len(coords):
        raise RuntimeError(f"Expected {len(coords)} locations, got {len(locations)}")
    return locations


def load_townships() -> list[dict[str, Any]]:
    from shapely.geometry import shape

    data = json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    towns = []
    for feature in data["features"]:
        p = feature["properties"]
        point = shape(feature["geometry"]).representative_point()
        towns.append({"n": p["n"], "nm": p.get("nm", ""), "s": p["s"], "sm": p.get("sm", ""),
                      "lat": round(point.y, 4), "lon": round(point.x, 4)})
    return towns


def run() -> int:
    now = datetime.now(timezone.utc)
    now_hour = now.strftime("%Y-%m-%dT%H:00")
    towns = load_townships()
    try:
        shares = json.loads(STATS_FILE.read_text(encoding="utf-8")).get("township_shares", {})
    except Exception:
        shares = {}
    rows: list[dict[str, Any]] = []
    failed = 0
    for i in range(0, len(towns), CHUNK):
        chunk = towns[i:i + CHUNK]
        try:
            locations = fetch_chunk([(t["lat"], t["lon"]) for t in chunk])
        except Exception as exc:
            LOG.warning("Chunk %d failed: %s", i // CHUNK, str(exc)[:160])
            failed += len(chunk)
            continue
        for town, location in zip(chunk, locations):
            hourly = location.get("hourly") or {}
            summary = summarise(list(hourly.get("time") or []), list(hourly.get("precipitation") or []), now_hour)
            if summary is None:
                failed += 1
                continue
            key = f"{town['n']}|{town['s']}"
            prone = float((shares.get(key) or {}).get("share_pct") or 0.0)
            level, base, reasons = classify(summary["max24"], summary["past72"], prone)
            rows.append({"k": key, **town, **summary, "prone": round(prone, 1), "lv": level, "base": base, "why": reasons})
        time.sleep(1.0)
    if not rows:
        LOG.error("No township forecast could be built; previous file kept.")
        return 1
    rows.sort(key=lambda r: (r["lv"], r["next72"]), reverse=True)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "schema_version": 1, "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "from_hour_utc": now_hour,
        "source": "Open-Meteo forecast API", "township_count": len(rows), "failed": failed, "townships": rows,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT_FILE)
    LOG.info("Wrote %d townships (%d failed). Levels: %s", len(rows), failed,
             {lv: sum(1 for r in rows if r["lv"] == lv) for lv in range(4)})
    return 0 if failed < len(towns) * 0.5 else 1


def selftest() -> int:
    assert rolling_max([1.0] * 10, 24) == 10.0
    series = [0.0] * 30 + [5.0] * 24 + [0.0] * 18
    assert rolling_max(series, 24) == 120.0
    assert rolling_max([], 24) == 0.0

    times = [f"2026-10-{14 + h // 24:02d}T{h % 24:02d}:00" for h in range(48)]
    past, future = split_hours(times, [1.0] * 48, "2026-10-14T12:00")
    assert len(past) == 12 and len(future) == 36

    assert classify(10, 0, 0) == (0, 0, [])
    assert classify(70, 0, 0) == (1, 1, [])
    assert classify(70, 200, 0) == (2, 1, ["wet"])
    assert classify(70, 200, 40) == (3, 1, ["wet", "prone"])
    assert classify(250, 200, 40)[0] == 3                       # capped
    assert classify(30, 300, 90) == (0, 0, [])                  # extras never create a warning on their own

    hours = [f"2026-10-{11 + h // 24:02d}T{h % 24:02d}:00" for h in range(144)]
    values: list[Optional[float]] = [1.0] * 72 + [2.0] * 72
    s = summarise(hours, values, "2026-10-14T00:00")
    assert s == {"past72": 72.0, "next24": 48.0, "next72": 144.0, "max24": 48.0}, s
    values[100] = None
    assert summarise(hours, values, "2026-10-14T00:00") is not None
    assert summarise(hours, [None] * 144, "2026-10-14T00:00") is None
    print("rain self-test passed")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="offline test of the calculations")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return selftest() if args.selftest else run()


if __name__ == "__main__":
    sys.exit(main())
