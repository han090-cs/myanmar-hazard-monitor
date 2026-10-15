#!/usr/bin/env python3
"""
Build demo.html: the full web app with made-up sample data embedded, so it can be tried on a phone
without Earth Engine, GitHub Actions or a web server.

    python scripts/make_demo.py            # writes demo.html next to index.html

The sample polygons are invented blobs. They are NOT real flooding or landslides.
Uses only the Python standard library.
"""
from __future__ import annotations

import json
import re
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MY = {
    "Ayeyarwady": "ဧရာဝတီ", "Bago": "ပဲခူး", "Sagaing": "စစ်ကိုင်း", "Chin": "ချင်း",
    "Kachin": "ကချင်", "Rakhine": "ရခိုင်", "Shan": "ရှမ်း", "Kayin": "ကရင်", "Mon": "မွန်",
}


def blob(cx: float, cy: float, rx: float, ry: float, seed: int, n: int = 28):
    rnd = random.Random(seed)
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 0.72 + 0.5 * rnd.random()
        ring.append([round(cx + rx * k * math.cos(a), 5), round(cy + ry * k * math.sin(a), 5)])
    ring.append(ring[0])
    return ring


def area_ha(ring) -> float:
    pts = ring[:-1]
    s = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    deg2 = abs(s) / 2.0
    lat = sum(p[1] for p in pts) / len(pts)
    return deg2 * (111.32 * math.cos(math.radians(lat))) * 110.57 * 100.0


def feature(i, ring, township, state, extra):
    props = {"township": township, "state_region": state, "state_region_my": MY[state],
             "area_ha": round(area_ha(ring), 1), **extra}
    return {"type": "Feature", "id": i, "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def totals(features, key=None):
    out = {}
    for f in features:
        p = f["properties"]
        e = out.setdefault((p["township"], p["state_region"]),
                           {"township": p["township"], "state_region": p["state_region"],
                            "state_region_my": p["state_region_my"], "area_ha": 0.0})
        e["area_ha"] += p["area_ha"]
    return sorted(out.values(), key=lambda e: e["area_ha"], reverse=True)


def demo_alerts(now):
    """One made-up warning so the demo can show the DMH panel and the highlighted regions."""
    iso_ = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"schema_version": 1, "generated_utc": iso_(now), "origin": "demo",
            "source": "DEMO - not a real warning",
            "status": {"last_attempt_at": iso_(now), "last_success_at": iso_(now), "last_error": None},
            "alerts": [{"id": "demo-1", "type": "heavy_rain", "regions": ["Rakhine", "Ayeyarwady", "Tanintharyi"],
                        "valid_from": iso_(now - timedelta(hours=3)), "valid_to": iso_(now + timedelta(hours=30)),
                        "title": {"my": "(DEMO) ဥပမာသတိပေးချက် - တကယ့်သတိပေးချက် မဟုတ်ပါ", "en": "(DEMO) Example warning - not a real warning"},
                        "summary": None, "url": None, "links": {}, "stations": [], "retrieved_at": iso_(now)}]}


def demo_rain(now):
    """Made-up township rainfall for the demo page: heavy rain in the west and the delta."""
    rnd = random.Random(11)
    admin = json.loads((ROOT / "data/ref/admin3_mmr.geojson").read_text(encoding="utf-8"))["features"]
    shares = json.loads((ROOT / "data/flood_prone_stats.json").read_text(encoding="utf-8")).get("township_shares", {})
    wet = {"Rakhine": 1.0, "Ayeyarwady": 0.9, "Tanintharyi": 0.8, "Yangon": 0.7, "Mon": 0.6, "Kayin": 0.5}
    rows = []
    for f in admin:
        p = f["properties"]
        coords = f["geometry"]["coordinates"]
        ring = coords[0][0] if f["geometry"]["type"] == "MultiPolygon" else coords[0]
        lon = sum(c[0] for c in ring) / len(ring)
        lat = sum(c[1] for c in ring) / len(ring)
        key = f"{p['n']}|{p['s']}"
        w = wet.get(p["s"].split(" ")[0], 0.15) * rnd.uniform(0.5, 1.3)
        max24 = round(w * 190, 1)
        past72 = round(w * rnd.uniform(60, 260), 1)
        prone = float((shares.get(key) or {}).get("share_pct") or 0.0)
        base = sum(1 for t in (64.5, 115.6, 204.5) if max24 >= t)
        level, why = base, []
        if base >= 1 and past72 >= 150:
            level += 1; why.append("wet")
        if base >= 1 and prone >= 15:
            level += 1; why.append("prone")
        rows.append({"k": key, "n": p["n"], "nm": p["nm"], "s": p["s"], "sm": p["sm"], "lat": round(lat, 3), "lon": round(lon, 3),
                     "past72": past72, "next24": round(max24 * 0.8, 1), "next72": round(max24 * 1.7, 1), "max24": max24,
                     "prone": round(prone, 1), "lv": min(level, 3), "base": base, "why": why})
    rows.sort(key=lambda r: (r["lv"], r["next72"]), reverse=True)
    return {"schema_version": 1, "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "DEMO", "township_count": len(rows), "townships": rows}


def build_data():
    now = datetime.now(timezone.utc)
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")

    flood_spec = [  # cx, cy, rx, ry, township, state
        (95.30, 16.90, 0.30, 0.18, "Demo Township A", "Ayeyarwady"),
        (95.75, 17.45, 0.16, 0.30, "Demo Township B", "Bago"),
        (96.55, 18.20, 0.12, 0.34, "Demo Township C", "Bago"),
        (95.05, 21.60, 0.26, 0.14, "Demo Township D", "Sagaing"),
        (94.85, 22.70, 0.18, 0.26, "Demo Township E", "Sagaing"),
        (97.35, 25.20, 0.14, 0.12, "Demo Township F", "Kachin"),
        (94.20, 20.30, 0.22, 0.10, "Demo Township G", "Rakhine"),
    ]
    flood = [feature(i + 1, blob(cx, cy, rx, ry, 10 + i), tn, st, {"layer": "flood"})
             for i, (cx, cy, rx, ry, tn, st) in enumerate(flood_spec)]

    hills = [  # cx, cy, base radius, township, state
        (93.55, 22.40, 0.55, "Demo Hill Township 1", "Chin"),
        (97.60, 26.10, 0.50, "Demo Hill Township 2", "Kachin"),
        (94.25, 19.60, 0.45, "Demo Hill Township 3", "Rakhine"),
        (97.40, 21.30, 0.50, "Demo Hill Township 4", "Shan"),
        (98.20, 17.00, 0.40, "Demo Hill Township 5", "Kayin"),
    ]
    slide, n = [], 0
    for h, (cx, cy, r, tn, st) in enumerate(hills):
        for code, name, scale in ((1, "Low", 1.0), (2, "Moderate", 0.62), (3, "High", 0.3)):
            if code == 3 and h == 3:
                continue
            n += 1
            slide.append(feature(n, blob(cx, cy, r * scale, r * scale * 0.8, 100 + n), tn, st,
                                 {"layer": "landslide", "hazard": name, "hazard_code": code}))

    susc, sn = [], 0
    for h, (cx, cy, r, tn, st) in enumerate(hills):
        for code, name, scale in ((1, "Low", 1.7), (2, "Moderate", 1.25), (3, "High", 0.85)):
            sn += 1
            susc.append(feature(sn, blob(cx, cy, r * scale, r * scale * 0.8, 300 + sn), tn, st,
                                {"layer": "susceptibility", "hazard": name, "hazard_code": code}))

    # made-up river points: (name, river, lat, lon, base m3/s, rise factor over 30 days)
    river_spec = [
        ("Myitkyina", "Ayeyarwady", 25.35, 97.42, 3000, 0.8), ("Mandalay", "Ayeyarwady", 21.95, 96.06, 9000, 1.9),
        ("Magway", "Ayeyarwady", 20.15, 94.92, 11000, 2.4), ("Pyay", "Ayeyarwady", 18.82, 95.22, 12000, 3.0),
        ("Homalin", "Chindwin", 24.87, 94.90, 2500, 1.6), ("Monywa", "Chindwin", 22.10, 95.10, 4500, 1.3),
        ("Taungoo", "Sittaung", 18.94, 96.45, 600, 2.2), ("Hpa-An", "Thanlwin", 16.88, 97.65, 5000, 1.1),
    ]
    start = (now - timedelta(days=7)).date()
    points = []
    for i, (name, riv, la, lo, base, rise) in enumerate(river_spec):
        series = [round(base * (0.9 + (rise - 0.9) * math.sin(math.pi * k / 36) ** 2), 1) for k in range(37)]
        thr = {"t2": round(base * 1.4, 1), "t5": round(base * 1.9, 1), "t20": round(base * 2.6, 1)}
        peak = max(series[7:])
        level = 3 if peak >= thr["t20"] else 2 if peak >= thr["t5"] else 1 if peak >= thr["t2"] else 0
        pk_i = 7 + series[7:].index(peak)
        points.append({"name": name, "river": riv, "lat": la, "lon": lo, "thresholds": thr, "level": level,
                       "level_max": min(3, level + 1), "peak_q": peak,
                       "peak_date": (start + timedelta(days=pk_i)).strftime("%Y-%m-%d"), "now_q": series[7],
                       "series": {"start": start.strftime("%Y-%m-%d"), "q": series}})
    river = {"schema_version": 1, "generated_utc": iso(now), "source": "DEMO", "forecast_days": 30, "points": points}

    hz = lambda c: [f for f in slide if f["properties"]["hazard_code"] == c]
    top_f = [{**e, "area_ha": round(e["area_ha"], 1)} for e in totals(flood)]
    warned = totals(hz(3) + hz(2))
    summary = {
        "schema_version": 1, "generated_utc": iso(now), "admin_level": "township",
        "satellite": {"sensor": "Sentinel-1 IW GRD (VV+VH)", "latest_scene_utc": iso(now - timedelta(hours=5)),
                      "scene_count": 42, "window_start_utc": iso(now - timedelta(days=12)),
                      "window_end_utc": iso(now), "baseline_period": "DEMO", "last_checked_utc": iso(now)},
        "rainfall": {"source": "DEMO", "window_start_utc": iso(now - timedelta(days=7)),
                     "window_end_utc": iso(now - timedelta(hours=8)), "data_age_days": 0.3,
                     "max_7d_mm": 312.0, "stale": False},
        "flood": {"updated_utc": iso(now), "total_area_ha": round(sum(f["properties"]["area_ha"] for f in flood), 1),
                  "polygon_count": len(flood), "townships_affected": len(top_f), "top_townships": top_f[:10],
                  "by_state_region": []},
        "landslide": {"updated_utc": iso(now),
                      "high_ha": round(sum(f["properties"]["area_ha"] for f in hz(3)), 1),
                      "moderate_ha": round(sum(f["properties"]["area_ha"] for f in hz(2)), 1),
                      "low_ha": round(sum(f["properties"]["area_ha"] for f in hz(1)), 1),
                      "polygon_count": len(slide), "townships_warned": len(warned),
                      "townships_high": len(totals(hz(3))), "townships_moderate": len(totals(hz(2))),
                      "townships_low": len(totals(hz(1))),
                      "top_townships": [{**e, "area_ha": round(e["area_ha"], 1)} for e in warned[:10]]},
    }
    meta = {"schema_version": 1, "last_run_utc": iso(now), "run_status": "ok", "admin_level": "township",
            "layers": {"flood": {"status": "updated", "sha256": None, "updated_utc": iso(now)},
                       "landslide": {"status": "updated", "sha256": None, "updated_utc": iso(now)}}}
    fc = lambda feats: {"type": "FeatureCollection", "features": feats}
    return {"flood": fc(flood), "landslide": fc(slide), "susceptibility": fc(susc), "river": river,
            "rain": demo_rain(now), "officialAlerts": demo_alerts(now), "summary": summary, "metadata": meta,
            "events": {"schema_version": 1, "generated_utc": None, "checked_utc": None, "source_checks": {}, "events": [],
                       "disclaimer": "Demo mode contains no real event feed; do not use demo data for warnings."}}


def main():
    demo = build_data()
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
    assert "</script" not in js.lower()
    payload = json.dumps(demo, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html, css_count = re.subn(
        r'<link rel="stylesheet" href="css/style\.css(?:\?[^"]*)?">',
        "<style>\n" + css + "\n</style>", html, count=1)
    html = re.sub(
        r'<link id="leaflet-css" rel="stylesheet" href="[^"]+">',
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">', html, count=1)
    # The standalone demo needs the library loaded synchronously before the embedded app.
    html = re.sub(r'<script src="js/repair-worker\.js(?:\?[^"]*)?"></script>', '', html, count=1)
    html = re.sub(r'<script src="js/leaflet-css-fallback\.js(?:\?[^"]*)?"></script>', '', html, count=1)
    html, js_count = re.subn(
        r'<script src="js/leaflet-loader\.js(?:\?[^"]*)?"></script>',
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n'
        + "<script>if (location.protocol === 'file:') { document.write('<script src=\"data/js/mapdata.js\"><\\/script>'); }</script>\n"
        + "<script>window.MM_DEMO=" + payload + ";</script>\n<script>\n" + js + "\n</script>",
        html, count=1)
    assert css_count == 1 and js_count == 1, "Could not inline CSS/JS into demo.html"
    html = html.replace("<title>Myanmar Hazard Monitor — Live Events &amp; Risk Map</title>", "<title>Myanmar Hazard Demo</title>")
    # the single-file demo has no icons or manifest next to it
    for rel in ("icon", "apple-touch-icon", "manifest"):
        html = "\n".join(line for line in html.split("\n") if f'<link rel="{rel}"' not in line)
    assert "css/style.css" not in html and "js/app.js" not in html
    out = ROOT / "demo.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
