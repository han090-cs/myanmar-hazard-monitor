#!/usr/bin/env python3
"""
Bring data from your weather website (myanmar-weather) into the hazard monitor.

    # one-time, with the weather project unzipped next to this one: stations, hospitals and the alerts it holds
    python scripts/import_weather_site_data.py --weather-dir ../myanmar-weather-v6_16_2

    # regularly (for example in GitHub Actions): official DMH alerts from your deployed weather website
    python scripts/import_weather_site_data.py --api-base https://your-weather-site.example

    python scripts/import_weather_site_data.py --selftest        # offline test

What is copied
  data/ref/dmh_river_stations.json  the DMH river gauging stations (47 located) named in DMH flood warnings.
                                    scripts/fetch_river_forecast.py uses them instead of its own guessed list.
  data/hospitals.geojson            1,136 public hospitals (MIMU / CDE-Myanmar, 2020, CC BY 4.0). Not a live list.
  data/official_alerts.json         official DMH warnings as stored by the weather website, plus how the last DMH
                                    import went. Warnings are copied as they are; nothing is reinterpreted.

An empty alert list does not prove that DMH has issued no warning: the file also says when the importer last
succeeded and what went wrong, and the map shows that.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
STATIONS_OUT = DATA_DIR / "ref" / "dmh_river_stations.json"
HOSPITALS_OUT = DATA_DIR / "hospitals.geojson"
ALERTS_OUT = DATA_DIR / "official_alerts.json"
USER_AGENT = "myanmar-hazard-monitor/1.0 (+https://github.com)"
ALERT_TYPES = {"heavy_rain", "cyclone", "depression", "strong_wind", "untimely_rain", "flood", "tsunami",
               "weather_early_warning", "other"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, separators=(",", ":"))
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


# --------------------------------------------------------------------------------------
# Pure conversions (tested offline)
# --------------------------------------------------------------------------------------

def convert_stations(source: dict[str, Any]) -> dict[str, Any]:
    stations = []
    for st in source.get("stations", []):
        if st.get("lat") is None or st.get("lon") is None:
            continue
        stations.append({"id": st.get("id"), "name_en": st.get("name_en"), "name_my": st.get("name_my") or "",
                         "river": st.get("river") or "", "region": st.get("region") or "",
                         "lat": round(float(st["lat"]), 4), "lon": round(float(st["lon"]), 4)})
    return {"source": "DMH river gauging stations named in DMH flood warnings, via the myanmar-weather project "
                      "(town coordinates from GeoNames, CC BY 4.0)",
            "imported_utc": now_iso(), "stations": stations}


def convert_hospitals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = []
    for r in rows:
        try:
            lat, lon = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (9.0 <= lat <= 29.0 and 92.0 <= lon <= 102.0):
            continue
        props = {"n": r.get("name_my") or "", "ne": r.get("name_en") or "", "l": r.get("level_my") or "",
                 "le": r.get("level_en") or "", "b": str(r.get("beds") or ""), "t": r.get("township_my") or "",
                 "te": r.get("township_en") or "", "r": r.get("region_my") or "", "re": r.get("region_en") or "",
                 "c": r.get("confidence") or ""}
        features.append({"type": "Feature", "properties": props,
                         "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}})
    return {"type": "FeatureCollection",
            "properties": {"source": "MIMU / CDE-Myanmar, Public Hospitals in Myanmar (2020), CC BY 4.0, via the "
                                     "myanmar-weather project. Not a live list.", "imported_utc": now_iso()},
            "features": features}


def normalise_alert(a: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Accepts both the stored form (id, valid_from, title{my,en}) and the /api/dmh/alerts form."""
    alert_id = a.get("id") or a.get("alert_id")
    valid_from, valid_to = a.get("valid_from"), a.get("valid_to")
    title = a.get("title") if isinstance(a.get("title"), dict) else {"en": a.get("title") or "", "my": ""}
    if not alert_id or not valid_from or not valid_to or not (title.get("en") or title.get("my")):
        return None
    kind = a.get("type") if a.get("type") in ALERT_TYPES else "other"
    url = a.get("url") if isinstance(a.get("url"), str) and a["url"].startswith("https://") else None
    links = a.get("links") if isinstance(a.get("links"), dict) else {}
    links = {k: v for k, v in links.items() if isinstance(v, str) and v.startswith("https://")}
    return {"id": str(alert_id), "type": kind, "regions": [str(r) for r in (a.get("regions") or [])],
            "valid_from": valid_from, "valid_to": valid_to,
            "title": {"my": title.get("my") or "", "en": title.get("en") or ""},
            "summary": a.get("summary") if isinstance(a.get("summary"), dict) else None,
            "url": url, "links": links, "stations": list(a.get("stations") or []),
            "retrieved_at": a.get("retrieved_at")}


def build_alerts(alerts: list[dict[str, Any]], status: dict[str, Any], origin: str) -> dict[str, Any]:
    cleaned = [x for x in (normalise_alert(a) for a in alerts) if x]
    cleaned.sort(key=lambda a: a["valid_from"], reverse=True)
    return {"schema_version": 1, "generated_utc": now_iso(), "origin": origin,
            "source": "Department of Meteorology and Hydrology (DMH), Myanmar, via the myanmar-weather project",
            "status": {"last_attempt_at": status.get("last_attempt_at"), "last_success_at": status.get("last_success_at"),
                       "last_error": status.get("last_error")},
            "alerts": cleaned[:60]}


# --------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------

def from_weather_dir(root: Path, alerts_only: bool) -> None:
    if not alerts_only:
        stations = json.loads((root / "risk_engine/data/dmh_river_stations.json").read_text(encoding="utf-8"))
        out = convert_stations(stations)
        write_json(STATIONS_OUT, out)
        print(f"stations: {len(out['stations'])} -> {STATIONS_OUT.relative_to(ROOT)}")

        con = sqlite3.connect(str(root / "data/hospitals.db"))
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute("select * from hospitals")]
        con.close()
        hospitals = convert_hospitals(rows)
        write_json(HOSPITALS_OUT, hospitals)
        print(f"hospitals: {len(hospitals['features'])} of {len(rows)} -> {HOSPITALS_OUT.relative_to(ROOT)}")

    store = json.loads((root / "risk_engine/data/official_alerts.json").read_text(encoding="utf-8"))
    try:
        state = json.loads((root / "risk_engine/data/official_alerts_state.json").read_text(encoding="utf-8"))
    except Exception:
        state = {}
    status = (state or {}).get("source", {})
    write_json(ALERTS_OUT, build_alerts(store.get("alerts", []), status, "weather-dir"))
    print(f"alerts: {len(store.get('alerts', []))} stored; last DMH import error: {status.get('last_error')}")


def from_api(base: str) -> None:
    import requests

    url = base.rstrip("/") + "/api/dmh/alerts"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=40)
    response.raise_for_status()
    payload = response.json()
    status = payload.get("source_status") or {}
    # the API reports status under different keys than the state file: accept both spellings
    status = {"last_attempt_at": status.get("last_attempt_at") or status.get("last_attempt"),
              "last_success_at": status.get("last_success_at") or status.get("last_success"),
              "last_error": status.get("last_error")}
    write_json(ALERTS_OUT, build_alerts(payload.get("alerts", []), status, "api"))
    print(f"alerts from {url}: {len(payload.get('alerts', []))}")


def selftest() -> int:
    st = convert_stations({"stations": [{"id": "a", "name_en": "A", "name_my": "က", "river": "R", "region": "X", "lat": 21.0, "lon": 96.0},
                                         {"id": "b", "name_en": "B", "lat": None, "lon": None}]})
    assert len(st["stations"]) == 1 and st["stations"][0]["name_my"] == "က"
    hp = convert_hospitals([{"name_my": "ဆ", "name_en": "H", "lat": "16.8", "lon": "96.1", "beds": 50},
                            {"name_en": "far", "lat": 50, "lon": 10}, {"name_en": "bad", "lat": "x", "lon": 1}])
    assert len(hp["features"]) == 1 and hp["features"][0]["properties"]["b"] == "50"
    good = {"id": "d1", "type": "heavy_rain", "regions": ["Kachin"], "valid_from": "2026-10-14T00:00:00+00:00",
            "valid_to": "2026-10-15T00:00:00+00:00", "title": {"en": "Heavy Rainfall Warning No.(1)", "my": "x"},
            "url": "https://www.moezala.gov.mm/x", "links": {"en": "https://a", "my": "javascript:alert(1)"}}
    out = build_alerts([good, {"id": "bad"}, {**good, "id": "d2", "type": "weird", "url": "http://insecure"}],
                       {"last_error": "boom"}, "weather-dir")
    assert len(out["alerts"]) == 2 and out["status"]["last_error"] == "boom"
    d2 = next(a for a in out["alerts"] if a["id"] == "d2")
    assert d2["type"] == "other" and d2["url"] is None
    d1 = next(a for a in out["alerts"] if a["id"] == "d1")
    assert d1["links"] == {"en": "https://a"}
    api_form = normalise_alert({"id": "z", "type": "flood", "regions": ["Sagaing"], "valid_from": "a", "valid_to": "b",
                                "title": {"en": "t", "my": ""}})
    assert api_form and api_form["type"] == "flood"
    print("weather-site import self-test passed")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weather-dir", type=Path, help="folder of the unzipped myanmar-weather project")
    parser.add_argument("--api-base", help="base URL of your deployed weather website (official alerts only)")
    parser.add_argument("--alerts-only", action="store_true", help="with --weather-dir: skip stations and hospitals")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.weather_dir:
        from_weather_dir(args.weather_dir, args.alerts_only)
        return 0
    if args.api_base:
        from_api(args.api_base)
        return 0
    parser.error("give --weather-dir, --api-base or --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
