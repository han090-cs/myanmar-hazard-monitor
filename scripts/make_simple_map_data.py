#!/usr/bin/env python3
"""Bundle the data files into data/js/mapdata.js so index.html also works when it is opened as a plain local file.
Re-run it after the pipeline has produced new data if you want to view that data from a local file.

    python scripts/make_simple_map_data.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {"outline": "data/ref/myanmar_outline.geojson", "admin1": "data/ref/admin1_mmr.geojson",
         "admin3": "data/ref/admin3_mmr.geojson", "floodprone": "data/flood_prone.geojson",
         "proneStats": "data/flood_prone_stats.json",
         # latest pipeline output (the seed files until the pipeline has run)
         "metadata": "data/metadata.json", "summary": "data/summary.json", "flood": "data/flood_zones.geojson",
         "landslide": "data/landslide_zones.geojson", "susceptibility": "data/landslide_susceptibility.geojson",
         "river": "data/river_forecast.json", "events": "data/disaster_events.json", "rain": "data/rain_forecast.json",
         "publicInfo": "data/public_info.json", "hospitals": "data/hospitals.geojson",
         "officialAlerts": "data/official_alerts.json"}
bundle = {k: json.loads((ROOT / v).read_text(encoding="utf-8")) for k, v in FILES.items()}
out = ROOT / "data/js/mapdata.js"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("window.MMDATA=" + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")
