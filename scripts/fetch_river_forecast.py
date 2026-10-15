#!/usr/bin/env python3
"""
River flood forecast for Myanmar's main rivers (GloFAS river discharge via the Open-Meteo Flood API).

    python scripts/fetch_river_forecast.py             # writes data/river_forecast.json
    python scripts/fetch_river_forecast.py --selftest  # offline test of the maths (no network)

How it works
  1. Each named river point is "snapped" once to the neighbouring 0.05 degree cell with the largest
     discharge, because GloFAS only carries discharge for river cells. The result is cached in
     data/river_thresholds.json.
  2. Flood thresholds (2, 5 and 20 year return levels) are estimated once from the annual maxima of the
     1984-onwards GloFAS history with a Gumbel fit and cached for 180 days.
  3. Every run fetches the next 30 days of forecast discharge and compares the peak with the thresholds.

This is a river-discharge forecast for a few dozen points. It is NOT an inundation map and it misses small
rivers, flash floods and urban flooding. Coordinates in RIVER_POINTS are approximate: check the snapped
positions in data/river_forecast.json on a map.

Data: Open-Meteo Flood API, which serves GloFAS (Copernicus Emergency Management Service). Open-Meteo's free
tier is for non-commercial use and requires attribution; check their current terms.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
OUT_FILE = DATA_DIR / "river_forecast.json"
CACHE_FILE = DATA_DIR / "river_thresholds.json"
STATIONS_FILE = DATA_DIR / "ref" / "dmh_river_stations.json"

API = "https://flood-api.open-meteo.com/v1/flood"
USER_AGENT = "myanmar-hazard-monitor/1.0 (+https://github.com)"
FORECAST_DAYS = 30
PAST_DAYS = 7
HISTORY_START_YEAR = 1984
MIN_YEARS_FOR_THRESHOLDS = 20
CACHE_MAX_AGE_DAYS = 180
SNAP_STEP = 0.05
CHUNK = 20            # coordinates per request
LEVEL_NAMES = {0: "normal", 1: "elevated", 2: "high", 3: "severe"}

LOG = logging.getLogger("river")

# name, river, latitude, longitude  (approximate positions ON the river; they are snapped automatically)
RIVER_POINTS: list[tuple[str, str, float, float]] = [
    ("Myitkyina", "Ayeyarwady", 25.35, 97.42),
    ("Bhamo", "Ayeyarwady", 24.27, 97.23),
    ("Katha", "Ayeyarwady", 24.18, 96.33),
    ("Mandalay", "Ayeyarwady", 21.95, 96.06),
    ("Nyaung-U (Bagan)", "Ayeyarwady", 21.20, 94.88),
    ("Magway", "Ayeyarwady", 20.15, 94.92),
    ("Pyay", "Ayeyarwady", 18.82, 95.22),
    ("Hinthada", "Ayeyarwady", 17.65, 95.45),
    ("Pantanaw", "Ayeyarwady", 16.99, 95.45),
    ("Homalin", "Chindwin", 24.87, 94.90),
    ("Mawlaik", "Chindwin", 23.64, 94.41),
    ("Kalewa", "Chindwin", 23.20, 94.30),
    ("Monywa", "Chindwin", 22.10, 95.10),
    ("Taungoo", "Sittaung", 18.94, 96.45),
    ("Bago", "Bago", 17.33, 96.48),
    ("Hpa-An", "Thanlwin", 16.88, 97.65),
    ("Mawlamyine", "Thanlwin", 16.48, 97.62),
    ("Paletwa", "Kaladan", 21.30, 92.85),
    ("Sittwe", "Kaladan", 20.15, 92.88),
    ("Dawei", "Tanintharyi", 14.08, 98.20),
]


def load_points() -> list[tuple[str, str, float, float, str, str]]:
    """River points as (name, river, lat, lon, name_my, station_id).

    Uses the DMH gauging stations imported from the weather website (data/ref/dmh_river_stations.json) when that
    file exists, and otherwise the approximate list above. A DMH station sits at its town, so GloFAS discharge is
    taken from the nearest river cell (see snap_point); the DMH warning and danger levels are not in the file.
    """
    try:
        stations = json.loads(STATIONS_FILE.read_text(encoding="utf-8")).get("stations", [])
    except Exception:
        stations = []
    points = [(st["name_en"], st["river"], float(st["lat"]), float(st["lon"]), st.get("name_my") or "", st.get("id") or "")
              for st in stations if st.get("lat") is not None and st.get("lon") is not None]
    if points:
        return points
    return [(n, r, la, lo, "", "") for n, r, la, lo in RIVER_POINTS]


# --------------------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------------------

def gumbel_return_levels(annual_maxima: list[float], periods=(2, 5, 20)) -> Optional[dict[str, float]]:
    """Return levels from a method-of-moments Gumbel fit. None when there is too little or flat data."""
    values = [float(v) for v in annual_maxima if v is not None and not math.isnan(float(v))]
    if len(values) < MIN_YEARS_FOR_THRESHOLDS:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    sd = math.sqrt(var)
    if sd <= 0 or mean <= 0:
        return None
    beta = sd * math.sqrt(6.0) / math.pi
    mu = mean - 0.5772156649 * beta
    return {f"t{p}": round(mu - beta * math.log(-math.log(1.0 - 1.0 / p)), 1) for p in periods}


def annual_maxima(times: list[str], values: list[Optional[float]], last_year: int) -> list[float]:
    """Max discharge per calendar year for years that have (almost) complete data."""
    by_year: dict[int, list[float]] = {}
    for stamp, value in zip(times, values):
        if value is None:
            continue
        year = int(stamp[:4])
        if HISTORY_START_YEAR <= year <= last_year:
            by_year.setdefault(year, []).append(float(value))
    return [max(v) for y, v in sorted(by_year.items()) if len(v) >= 330]


def classify(discharge: Optional[float], thresholds: Optional[dict[str, float]]) -> Optional[int]:
    """0 normal, 1 elevated (>= 2-yr), 2 high (>= 5-yr), 3 severe (>= 20-yr). None without thresholds."""
    if discharge is None or not thresholds:
        return None
    if discharge >= thresholds["t20"]:
        return 3
    if discharge >= thresholds["t5"]:
        return 2
    if discharge >= thresholds["t2"]:
        return 1
    return 0


def parse_locations(payload: Any) -> list[dict[str, Any]]:
    """Open-Meteo returns one object for one coordinate and a list for several."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "daily" in payload:
        return [payload]
    raise ValueError("Unexpected Open-Meteo response")


# --------------------------------------------------------------------------------------
# Network
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
            raise                      # client error: retrying will not help
        except Exception as exc:       # network / 5xx / rate limit
            last = exc
            LOG.warning("Request failed (%s); retry %d/%d", str(exc)[:120], attempt + 1, retries)
            time.sleep(5 * (attempt + 1) ** 2)
    raise RuntimeError(f"Open-Meteo request failed: {last}")


def _fetch(coords: list[tuple[float, float]], **extra: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(0, len(coords), CHUNK):
        chunk = coords[i:i + CHUNK]
        params = {"latitude": ",".join(f"{c[0]:.4f}" for c in chunk),
                  "longitude": ",".join(f"{c[1]:.4f}" for c in chunk), **extra}
        out.extend(parse_locations(_get(params)))
        time.sleep(1.0)
    if len(out) != len(coords):
        raise RuntimeError(f"Expected {len(coords)} locations, got {len(out)}")
    return out


def _series(location: dict[str, Any], key: str = "river_discharge") -> tuple[list[str], list[Optional[float]]]:
    daily = location.get("daily") or {}
    return list(daily.get("time") or []), list(daily.get(key) or [])


def snap_point(lat: float, lon: float) -> tuple[float, float]:
    """Pick the neighbouring cell with the largest mean discharge: that is the river cell."""
    offsets = [(dy * SNAP_STEP, dx * SNAP_STEP) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    coords = [(round(lat + dy, 4), round(lon + dx, 4)) for dy, dx in offsets]
    locations = _fetch(coords, daily="river_discharge", past_days=30, forecast_days=1)
    best, best_mean = coords[4], -1.0
    for coord, location in zip(coords, locations):
        _, values = _series(location)
        nums = [v for v in values if v is not None]
        if nums and sum(nums) / len(nums) > best_mean:
            best, best_mean = coord, sum(nums) / len(nums)
    return best


def estimate_thresholds(lat: float, lon: float, last_year: int) -> Optional[dict[str, float]]:
    loc = _fetch([(lat, lon)], daily="river_discharge",
                 start_date=f"{HISTORY_START_YEAR}-01-01", end_date=f"{last_year}-12-31")[0]
    times, values = _series(loc)
    return gumbel_return_levels(annual_maxima(times, values, last_year))


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def run() -> int:
    now = datetime.now(timezone.utc)
    last_year = now.year - 1
    cache = _load_json(CACHE_FILE) or {}
    stale = True
    if cache.get("computed_utc"):
        try:
            age = now - datetime.fromisoformat(cache["computed_utc"].replace("Z", "+00:00"))
            stale = age > timedelta(days=CACHE_MAX_AGE_DAYS)
        except ValueError:
            stale = True
    points_cache: dict[str, Any] = cache.get("points", {}) if not stale else {}

    # 1) snap + thresholds (only for points not cached yet)
    all_points = load_points()
    for name, river, lat, lon, _name_my, _sid in all_points:
        entry = points_cache.get(name)
        if entry and entry.get("lat") is not None:
            continue
        try:
            slat, slon = snap_point(lat, lon)
            thresholds = estimate_thresholds(slat, slon, last_year)
            points_cache[name] = {"lat": slat, "lon": slon, "thresholds": thresholds}
            LOG.info("%s: snapped to %.3f, %.3f, thresholds %s", name, slat, slon, thresholds)
        except Exception as exc:
            LOG.warning("%s: could not prepare (%s)", name, str(exc)[:160])
    cache_out = {"computed_utc": cache.get("computed_utc") if not stale and cache.get("computed_utc")
                 else now.strftime("%Y-%m-%dT%H:%M:%SZ"), "points": points_cache}
    _write_json(CACHE_FILE, cache_out)

    ready = [(n, r, la, lo, nm, sid) for n, r, la, lo, nm, sid in all_points if (points_cache.get(n) or {}).get("lat") is not None]
    if not ready:
        LOG.error("No river point could be prepared; previous forecast kept.")
        return 1

    # 2) forecast
    coords = [(points_cache[n]["lat"], points_cache[n]["lon"]) for n, _, _, _, _, _ in ready]
    daily_vars = "river_discharge,river_discharge_max"
    try:
        locations = _fetch(coords, daily=daily_vars, past_days=PAST_DAYS, forecast_days=FORECAST_DAYS)
    except ValueError:      # ensemble-max variable not accepted: fall back to the plain forecast
        daily_vars = "river_discharge"
        locations = _fetch(coords, daily=daily_vars, past_days=PAST_DAYS, forecast_days=FORECAST_DAYS)

    today = now.strftime("%Y-%m-%d")
    points: list[dict[str, Any]] = []
    for (name, river, _, _, name_my, station_id), location in zip(ready, locations):
        times, q = _series(location)
        _, qmax = _series(location, "river_discharge_max")
        if not times or not any(v is not None for v in q):
            continue
        thresholds = points_cache[name].get("thresholds")
        future = [(t, v) for t, v in zip(times, q) if t >= today and v is not None]
        if not future:
            continue
        peak_date, peak = max(future, key=lambda item: item[1])
        fmax = [v for t, v in zip(times, qmax) if t >= today and v is not None] if qmax else []
        points.append({
            "name": name, "name_my": name_my, "station_id": station_id, "river": river,
            "lat": points_cache[name]["lat"], "lon": points_cache[name]["lon"],
            "thresholds": thresholds,
            "level": classify(peak, thresholds),
            "level_max": classify(max(fmax), thresholds) if fmax else None,
            "peak_q": round(peak, 1), "peak_date": peak_date,
            "now_q": round(next((v for t, v in zip(times, q) if t == today and v is not None), future[0][1]), 1),
            "series": {"start": times[0], "q": [None if v is None else round(v, 1) for v in q]},
        })
    if not points:
        LOG.error("Forecast came back empty; previous forecast kept.")
        return 1

    _write_json(OUT_FILE, {
        "schema_version": 1, "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "GloFAS via Open-Meteo Flood API", "forecast_days": FORECAST_DAYS,
        "thresholds_note": f"Gumbel fit of annual maxima {HISTORY_START_YEAR}-{last_year}",
        "points": points,
    })
    LOG.info("Wrote %d river points (%d with thresholds).", len(points), sum(1 for p in points if p["thresholds"]))
    return 0


def selftest() -> int:
    # Evenly spaced Gumbel quantiles (mu=1000, beta=200) -> the fit should recover the true return levels
    maxima = [1000 - 200 * math.log(-math.log((i + 0.5) / 40)) for i in range(40)]
    levels = gumbel_return_levels(maxima)
    assert levels and levels["t2"] < levels["t5"] < levels["t20"], levels
    truth = {p: 1000 - 200 * math.log(-math.log(1 - 1 / int(p[1:]))) for p in ("t2", "t5", "t20")}
    for key, expected in truth.items():
        assert abs(levels[key] - expected) / expected < 0.08, (key, levels[key], expected)
    assert gumbel_return_levels(maxima[:10]) is None
    assert gumbel_return_levels([5.0] * 40) is None

    thr = {"t2": 100.0, "t5": 200.0, "t20": 300.0}
    assert [classify(v, thr) for v in (50, 100, 250, 999)] == [0, 1, 2, 3]
    assert classify(10, None) is None and classify(None, thr) is None

    times = [(datetime(1990, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(366 * 2)]
    vals: list[Optional[float]] = [float(i % 50) for i in range(len(times))]
    assert len(annual_maxima(times, vals, 1991)) == 2
    assert annual_maxima(times[:100], vals[:100], 1991) == []          # incomplete year dropped

    one = {"daily": {"time": ["2026-01-01"], "river_discharge": [1.0]}}
    assert parse_locations(one) == [one] and parse_locations([one, one]) == [one, one]
    print("river self-test passed", levels)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="offline test of the calculations")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.selftest:
        return selftest()
    return run()


if __name__ == "__main__":
    sys.exit(main())
