#!/usr/bin/env python3
"""
One-time (offline) builder for the static reference data used by the site.

Inputs  (your files; point the options at wherever you unzipped them)
  --geojson-dir   folder with mmr_admin0.geojson and mmr_admin3.geojson (from mmr_admin_boundaries_geojson.zip)
  --flood-csv     myanmar-admin1-flood.csv (point list, one row per 0.00225 degree grid cell and event)

Outputs (committed to the repository, so GitHub Actions never needs the big source files)
  data/ref/myanmar_outline.geojson     simplified country outline (used to hide everything outside Myanmar)
  data/ref/admin3_mmr.geojson          simplified township polygons with English + Burmese names
  data/flood_prone.geojson             historical flood-prone cells merged into polygons (3 classes)
  data/flood_prone_stats.json          per township / state totals for the side panel

Needs: pip install shapely numpy pandas rasterio
Run  : python scripts/build_reference_data.py --geojson-dir /path/to/geojson --flood-csv /path/to/flood.csv

About the flood CSV: it has no date, event or source column. Many grid cells appear several times (1 to 6).
This script treats the number of repeats as "number of flood events that reached the cell". That is an
assumption about the file, not something it states, so the site labels the layer accordingly.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
GRID = 250.0 / 111319.49   # 0.0022457882 degrees (250 m): measured from the file, not 0.00225
COORD_DECIMALS = 4
ADMIN3_TOL = 0.002             # simplification of township polygons (degrees)
OUTLINE_TOL = 0.004
FLOOD_TOL = 0.0025
MIN_PIECE_CELLS = 10           # drop flood-prone specks smaller than this many cells
CLASS_NAMES = {1: "Once", 2: "Several times", 3: "Often"}


def round_geom(geom):
    return shapely.set_precision(geom, 10 ** -COORD_DECIMALS)


def dump_geojson(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}  {len(text) / 1e6:.2f} MB  {len(features)} features")


def load_geojson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def build_boundaries(geojson_dir: Path):
    # --- country outline
    outline_src = shape(load_geojson(geojson_dir / "mmr_admin0.geojson")[0]["geometry"])
    outline = round_geom(outline_src.simplify(OUTLINE_TOL, preserve_topology=True))
    dump_geojson(ROOT / "data/ref/myanmar_outline.geojson",
                 [{"type": "Feature", "properties": {"name": "Myanmar"}, "geometry": mapping(outline)}])

    # --- townships
    features, units = [], []
    for feat in load_geojson(geojson_dir / "mmr_admin3.geojson"):
        p = feat["properties"]
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        simple = round_geom(geom.simplify(ADMIN3_TOL, preserve_topology=True))
        props = {"n": p["adm3_name"], "nm": p.get("adm3_name1") or "", "d": p.get("adm2_name") or "",
                 "dm": p.get("adm2_name1") or "", "s": p["adm1_name"], "sm": p.get("adm1_name1") or "",
                 "p": p.get("adm3_pcode") or ""}
        features.append({"type": "Feature", "properties": props, "geometry": mapping(simple)})
        units.append((geom, props))          # full-detail geometry for assigning cells
    dump_geojson(ROOT / "data/ref/admin3_mmr.geojson", features)
    return outline_src, units


def build_flood_prone(csv_path: Path, outline, units):
    df = pd.read_csv(csv_path, skiprows=[1], usecols=["latitude", "longitude"])
    print(f"flood csv rows: {len(df):,}")
    lon0, north = float(df.longitude.min()), float(df.latitude.max())
    ix = np.rint((df.longitude.to_numpy() - lon0) / GRID).astype(np.int64)
    iy = np.rint((north - df.latitude.to_numpy()) / GRID).astype(np.int64)
    resid = max(np.abs((df.longitude.to_numpy() - lon0) / GRID - ix).max(),
                np.abs((north - df.latitude.to_numpy()) / GRID - iy).max())
    assert resid < 0.35, f"grid does not line up (residual {resid:.2f} cells)"
    ny, nx = int(iy.max()) + 1, int(ix.max()) + 1
    counts = np.zeros((ny, nx), dtype=np.uint8)
    np.add.at(counts, (iy, ix), 1)
    cls = np.zeros_like(counts)
    cls[counts == 1] = 1
    cls[(counts >= 2) & (counts <= 3)] = 2
    cls[counts >= 4] = 3
    print("cells per class:", {k: int((cls == k).sum()) for k in (1, 2, 3)}, "max repeats", int(counts.max()))

    # cell centres -> township
    rows, cols = np.nonzero(cls)
    lon = lon0 + cols * GRID
    lat = north - rows * GRID
    points = shapely.points(lon, lat)
    tree = STRtree([g for g, _ in units])
    pt_idx, unit_idx = tree.query(points, predicate="within")
    township_of = np.full(len(points), -1, dtype=np.int32)
    township_of[pt_idx] = unit_idx
    inside = township_of >= 0
    print(f"cells inside a township: {inside.sum():,} of {len(points):,}")

    # areas
    cell_ha = (GRID * 111.32 * np.cos(np.radians(lat)) * GRID * 110.57) * 100.0
    stats: dict[int, float] = {}
    for u in np.unique(township_of[inside]):
        stats[int(u)] = float(cell_ha[township_of == u].sum())
    total_ha = float(cell_ha[inside].sum())

    towns = []
    for u, ha in stats.items():
        props = units[u][1]
        area_ha = units[u][0].area * (111.32 * math.cos(math.radians(props_lat(units[u][0]))) * 110.57) * 100.0
        towns.append({"township": props["n"], "township_my": props["nm"], "state_region": props["s"],
                      "state_region_my": props["sm"], "area_ha": round(ha, 1),
                      "share_pct": round(100.0 * ha / area_ha, 2) if area_ha else None})
    towns.sort(key=lambda e: e["area_ha"], reverse=True)
    by_state: dict[str, dict] = {}
    for t in towns:
        s = by_state.setdefault(t["state_region"], {"state_region": t["state_region"],
                                                    "state_region_my": t["state_region_my"], "area_ha": 0.0})
        s["area_ha"] += t["area_ha"]
    stats_json = {
        "total_area_ha": round(total_ha, 1),
        "township_count": len(towns),
        "top_townships": towns[:10],
        "township_shares": {f"{t['township']}|{t['state_region']}": {"area_ha": t["area_ha"], "share_pct": t["share_pct"]}
                            for t in towns},
        "by_state_region": sorted(({**v, "area_ha": round(v["area_ha"], 1)} for v in by_state.values()),
                                  key=lambda e: e["area_ha"], reverse=True),
        "note": "Cells counted once however often they repeat in the source file.",
    }
    (ROOT / "data/flood_prone_stats.json").write_text(
        json.dumps(stats_json, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote data/flood_prone_stats.json; total flood-prone area (ha):", round(total_ha))

    # polygons per class
    from rasterio.features import shapes
    from rasterio.transform import Affine

    transform = Affine(GRID, 0, lon0 - GRID / 2, 0, -GRID, north + GRID / 2)
    min_ha = MIN_PIECE_CELLS * GRID * 111.32 * GRID * 110.57 * 100.0 * 0.95
    out_tree_geoms = [g for g, _ in units]
    features = []
    for code in (1, 2, 3):                      # low first so that "often" is drawn last (on top)
        mask = cls == code
        pieces = []
        for geom_dict, value in shapes(mask.astype(np.uint8), mask=mask, transform=transform, connectivity=8):
            if value != 1:
                continue
            g = shape(geom_dict)
            if g.area < (min_ha / 100.0) / (111.32 * 110.57 * 0.95):
                continue
            g = g.simplify(FLOOD_TOL, preserve_topology=True)
            if g.is_empty:
                continue
            pieces.append(g)
        keep = []
        for g in pieces:
            rp = g.representative_point()
            hit = tree.query(rp, predicate="within")
            if len(hit) == 0:
                continue
            props_u = units[int(hit[0])][1]
            lat_c = rp.y
            ha = g.area * (111.32 * math.cos(math.radians(lat_c)) * 110.57) * 100.0
            if ha < min_ha:
                continue
            keep.append({"type": "Feature", "geometry": mapping(round_geom(g)),
                         "properties": {"layer": "floodprone", "class_code": code, "class": CLASS_NAMES[code],
                                        "township": props_u["n"], "township_my": props_u["nm"],
                                        "state_region": props_u["s"], "state_region_my": props_u["sm"],
                                        "area_ha": round(ha, 1)}})
        print(f"class {code}: {len(keep)} polygons")
        features.extend(keep)
    dump_geojson(ROOT / "data/flood_prone.geojson", features)
    del out_tree_geoms


def props_lat(geom) -> float:
    return geom.representative_point().y


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geojson-dir", required=True, type=Path)
    parser.add_argument("--flood-csv", required=True, type=Path)
    args = parser.parse_args()
    outline, units = build_boundaries(args.geojson_dir)
    build_flood_prone(args.flood_csv, outline, units)


if __name__ == "__main__":
    main()
