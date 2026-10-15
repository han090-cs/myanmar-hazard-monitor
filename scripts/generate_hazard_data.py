#!/usr/bin/env python3
"""
Operational NRT flood & landslide hazard pipeline for Myanmar.

Runs headless inside GitHub Actions, uses Google Earth Engine (service-account
authentication) and writes three small files that the static web app reads:

    data/flood_zones.geojson      newly inundated areas (Sentinel-1 SAR change detection)
    data/landslide_zones.geojson  rainfall x slope landslide hazard classes
    data/summary.json             headline numbers for the dashboard
    data/metadata.json            run status, timestamps, content hashes (used for caching)

FLOOD METHOD (Sentinel-1 IW GRD, VV+VH)
  * COPERNICUS/S1_GRD in Earth Engine is already thermal-noise removed, radiometrically
    calibrated and terrain corrected (sigma0, dB). Incidence-angle edges are masked.
  * Median composite of the last S1_LOOKBACK_DAYS days vs. a dry-season (Jan-Mar) median
    baseline of the most recent completed dry season.
  * Adaptive Lee speckle filter (linear domain) on both composites.
  * Flood = VV drop <= -3 dB  AND  VV low enough to be water  AND  VH low enough to be water
            AND baseline was not water  AND  slope <= 5 deg (SRTM 30 m, radar-shadow guard)
            AND not permanent water (JRC Global Surface Water occurrence).
  * Small speckle patches are removed, the mask is vectorised in tiles, merged,
    Douglas-Peucker simplified (tolerance 0.001 deg) and split by township.

LANDSLIDE METHOD (dynamic index, not a trained model)
  * 7-day antecedent rainfall (GPM IMERG V07, falling back to CHIRPS then ERA5-Land when the
    fresher products are not available in Earth Engine yet) x SRTM slope (>= 20 deg).
  * Rainfall/slope thresholds map to High / Moderate / Low classes. The thresholds are
    heuristic defaults (see LS_RULES) and should be calibrated against local landslide records.

FAULT TOLERANCE
  * If there is no new Sentinel-1 scene / rainfall data, the previous GeoJSON is kept and only
    the timestamps in metadata.json / summary.json are refreshed.
  * Earth Engine failures on a tile are retried, then the tile is split; if too much of the
    country fails, the previous layer is kept and the layer is marked "error".

Run `python scripts/generate_hazard_data.py --selftest` to exercise the post-processing
(union, simplification, township clipping, size fitting) without Earth Engine.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import requests
import shapely
from pyproj import Transformer
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union
from shapely.strtree import STRtree

try:  # Earth Engine is only needed for real runs, not for --selftest
    import ee
except ImportError:  # pragma: no cover
    ee = None  # type: ignore[assignment]

LOG = logging.getLogger("hazard")

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, "") or default))
    except ValueError:
        return default


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", ROOT / ".cache"))
FLOOD_FILE = DATA_DIR / "flood_zones.geojson"
LANDSLIDE_FILE = DATA_DIR / "landslide_zones.geojson"
SUSCEPTIBILITY_FILE = DATA_DIR / "landslide_susceptibility.geojson"
ADMIN_LOCAL_FILE = Path(os.environ.get("ADMIN_FILE", DATA_DIR / "ref" / "admin3_mmr.geojson"))
SUMMARY_FILE = DATA_DIR / "summary.json"
METADATA_FILE = DATA_DIR / "metadata.json"

# Myanmar bounding box: min lon, min lat, max lon, max lat
BBOX = (92.1, 9.5, 101.2, 28.5)

# Flood detection
S1_LOOKBACK_DAYS = _env_int("S1_LOOKBACK_DAYS", 12)
DIFF_THRESHOLD_DB = _env_float("DIFF_THRESHOLD_DB", -3.0)      # VV change vs. dry baseline
WATER_VV_DB = _env_float("WATER_VV_DB", -15.0)                 # VV below this looks like open water
WATER_VH_DB = _env_float("WATER_VH_DB", -22.0)                 # VH below this looks like open water
MAX_FLOOD_SLOPE_DEG = _env_float("MAX_FLOOD_SLOPE_DEG", 5.0)   # radar-shadow / hillside guard
JRC_PERMANENT_OCCURRENCE = _env_float("JRC_PERMANENT_OCCURRENCE", 75.0)  # % of time water
MIN_FLOOD_PIXELS = _env_int("MIN_FLOOD_PIXELS", 4)             # speckle clean-up, in FLOOD_SCALE pixels
FILTER_SCALE = _env_int("FILTER_SCALE", 50)                    # metres, speckle filtering grid
FLOOD_SCALE = _env_int("FLOOD_SCALE", 100)                     # metres, vectorisation grid
LEE_RADIUS = _env_int("LEE_RADIUS", 1)                         # 1 -> 3x3 window
LEE_ENL = _env_float("LEE_ENL", 4.4)                           # equivalent number of looks, S1 GRDH IW
ANGLE_MIN, ANGLE_MAX = 30.5, 45.5                              # degrees, drop IW range edges
BASELINE_START_MONTH, BASELINE_END_MONTH = 1, 3                # dry season Jan-Mar

# Landslide
LS_SLOPE_MIN_DEG = _env_float("LS_SLOPE_MIN_DEG", 20.0)
LS_SCALE = _env_int("LS_SCALE", 250)
RAIN_WINDOW_DAYS = _env_int("RAIN_WINDOW_DAYS", 7)
RAIN_MAX_LATENCY_DAYS = _env_float("RAIN_MAX_LATENCY_DAYS", 6.0)
# (min 7-day rain mm, min mean slope deg) -> class. Evaluated Low -> Moderate -> High, later wins.
LS_RULES = {
    "low": [(50.0, 20.0)],
    "moderate": [(100.0, 25.0), (150.0, 20.0), (75.0, 35.0)],
    "high": [(150.0, 30.0), (250.0, 20.0)],
}
HAZARD_NAMES = {1: "Low", 2: "Moderate", 3: "High"}
# Static "where is the terrain steep" layer (slope only; NOT the NASA LHASA model). Mean slope per cell, degrees.
SUSC_SCALE = _env_int("SUSC_SCALE", 500)
SUSC_LOW_DEG = _env_float("SUSC_LOW_DEG", 20.0)
SUSC_MOD_DEG = _env_float("SUSC_MOD_DEG", 28.0)
SUSC_HIGH_DEG = _env_float("SUSC_HIGH_DEG", 35.0)
SUSC_TILE_DEG = _env_float("SUSC_TILE_DEG", 3.0)

RAIN_SOURCES = [
    # collection, band, multiplier to mm, time step covered by one image
    {"id": "IMERG_V07", "collection": "NASA/GPM_L3/IMERG_V07", "band": "precipitation",
     "factor": 0.5, "step_ms": 30 * 60 * 1000},
    {"id": "CHIRPS_DAILY", "collection": "UCSB-CHG/CHIRPS/DAILY", "band": "precipitation",
     "factor": 1.0, "step_ms": 24 * 3600 * 1000},
    {"id": "ERA5_LAND_DAILY", "collection": "ECMWF/ERA5_LAND/DAILY_AGGR",
     "band": "total_precipitation_sum", "factor": 1000.0, "step_ms": 24 * 3600 * 1000},
]

# Output size / geometry
SIMPLIFY_TOLERANCE = _env_float("SIMPLIFY_TOLERANCE", 0.001)   # degrees (Douglas-Peucker)
MAX_FILE_BYTES = _env_int("MAX_FILE_BYTES", 4_800_000)         # stay under 5 MB
COORD_DECIMALS = 5
MIN_FLOOD_PIECE_HA = _env_float("MIN_FLOOD_PIECE_HA", 1.0)
MIN_LANDSLIDE_PIECE_HA = _env_float("MIN_LANDSLIDE_PIECE_HA", 10.0)
MIN_TOWNSHIP_WARNING_HA = _env_float("MIN_TOWNSHIP_WARNING_HA", 25.0)

# Earth Engine execution
EE_WORKERS = _env_int("EE_WORKERS", 6)
EE_RETRIES = _env_int("EE_RETRIES", 3)
FLOOD_TILE_DEG = _env_float("FLOOD_TILE_DEG", 2.0)
FLOOD_MIN_TILE_DEG = _env_float("FLOOD_MIN_TILE_DEG", 0.25)
LS_TILE_DEG = _env_float("LS_TILE_DEG", 3.0)
LS_MIN_TILE_DEG = _env_float("LS_MIN_TILE_DEG", 0.5)
MAX_FAILED_AREA_FRACTION = _env_float("MAX_FAILED_AREA_FRACTION", 0.2)

USER_AGENT = "myanmar-hazard-monitor/1.0 (+https://github.com)"

# Burmese names of the 15 first-level units, keyed by normalised English name
REGION_NAMES = {
    "kachin": ("Kachin", "ကချင်"),
    "kayah": ("Kayah", "ကယား"),
    "karenni": ("Kayah", "ကယား"),
    "kayin": ("Kayin", "ကရင်"),
    "karen": ("Kayin", "ကရင်"),
    "chin": ("Chin", "ချင်း"),
    "sagaing": ("Sagaing", "စစ်ကိုင်း"),
    "tanintharyi": ("Tanintharyi", "တနင်္သာရီ"),
    "bago": ("Bago", "ပဲခူး"),
    "magway": ("Magway", "မကွေး"),
    "magwe": ("Magway", "မကွေး"),
    "mandalay": ("Mandalay", "မန္တလေး"),
    "mon": ("Mon", "မွန်"),
    "rakhine": ("Rakhine", "ရခိုင်"),
    "arakan": ("Rakhine", "ရခိုင်"),
    "yangon": ("Yangon", "ရန်ကုန်"),
    "rangoon": ("Yangon", "ရန်ကုန်"),
    "shan": ("Shan", "ရှမ်း"),
    "ayeyarwady": ("Ayeyarwady", "ဧရာဝတီ"),
    "ayeyarwaddy": ("Ayeyarwady", "ဧရာဝတီ"),
    "irrawaddy": ("Ayeyarwady", "ဧရာဝတီ"),
    "naypyitaw": ("Nay Pyi Taw", "နေပြည်တော်"),
    "naypyidaw": ("Nay Pyi Taw", "နေပြည်တော်"),
    "nayypyitaw": ("Nay Pyi Taw", "နေပြည်တော်"),
    "unionterritory": ("Nay Pyi Taw", "နေပြည်တော်"),
}


class PipelineError(RuntimeError):
    """Recoverable pipeline failure for one layer."""


class ConfigError(PipelineError):
    """Missing or invalid configuration (for example the Earth Engine secret)."""


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_ms(ms: float) -> datetime:
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_write_bytes(path: Path, payload: bytes) -> bool:
    """Write atomically; return False (and leave the file alone) if the content is identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and path.read_bytes() == payload:
            return False
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return True


def write_json(path: Path, obj: Any) -> None:
    payload = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, payload)


def normalise_region(name: str) -> tuple[str, str]:
    """Map a first-level unit name to (canonical English, Burmese). Unknown names pass through."""
    key = re.sub(r"[^a-z]", "", (name or "").lower())
    for suffix in ("state", "region", "division"):
        if key.endswith(suffix) and len(key) > len(suffix):
            key = key[: -len(suffix)]
    if key in REGION_NAMES:
        return REGION_NAMES[key]
    for candidate in sorted(REGION_NAMES, key=len, reverse=True):
        if key.startswith(candidate):
            return REGION_NAMES[candidate]
    return (name or "Unknown", "")


# --------------------------------------------------------------------------------------
# Administrative boundaries (township names for popups and statistics)
# --------------------------------------------------------------------------------------


@dataclass
class AdminUnit:
    name: str
    state: str
    state_my: str
    geom: Any
    name_my: str = ""


class AdminIndex:
    """Spatial index of township (or district) polygons."""

    def __init__(self, units: list[AdminUnit], level: str):
        self.units = units
        self.level = level
        self.tree = STRtree([u.geom for u in units])
        self.outline = unary_union([u.geom for u in units])
        shapely.prepare(self.outline)

    def intersects_box(self, bounds: tuple[float, float, float, float]) -> bool:
        return bool(self.outline.intersects(box(*bounds)))

    def split(self, geom: Any) -> list[tuple[Any, AdminUnit]]:
        """Clip a polygon by administrative unit. Parts outside every unit are dropped."""
        pieces: list[tuple[Any, AdminUnit]] = []
        for idx in self.tree.query(geom, predicate="intersects"):
            unit = self.units[int(idx)]
            try:
                inter = geom.intersection(unit.geom)
            except shapely.errors.GEOSException:
                inter = shapely.make_valid(geom).intersection(shapely.make_valid(unit.geom))
            parts = polygon_parts(inter)
            if not parts:
                continue
            pieces.append((parts[0] if len(parts) == 1 else MultiPolygon(parts), unit))
        return pieces


def polygon_parts(geom: Any) -> list[Polygon]:
    """Return the polygonal pieces of any geometry (drops points and lines)."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        parts: list[Polygon] = []
        for sub in geom.geoms:
            parts.extend(polygon_parts(sub))
        return parts
    return []


def _download_json(url: str, cache_file: Path, timeout: int = 180) -> Any:
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data
    except Exception as exc:  # network, HTTP or JSON problems
        if cache_file.exists():
            LOG.warning("Download of %s failed (%s); using cached copy", url, exc)
            return json.loads(cache_file.read_text(encoding="utf-8"))
        raise


def _geoboundaries(level: str) -> list[tuple[Any, str]]:
    """Fetch Myanmar boundaries from geoBoundaries (CC BY 4.0). level is ADM1 or ADM3."""
    cache_file = CACHE_DIR / f"mmr_{level.lower()}.geojson"
    try:
        info = requests.get(
            f"https://www.geoboundaries.org/api/current/gbOpen/MMR/{level}/",
            timeout=60, headers={"User-Agent": USER_AGENT})
        info.raise_for_status()
        info_json = info.json()
        if isinstance(info_json, list):
            info_json = info_json[0]
        url = info_json.get("simplifiedGeometryGeoJSON") or info_json["gjDownloadURL"]
        data = _download_json(url, cache_file)
    except Exception as exc:
        if not cache_file.exists():
            raise PipelineError(f"geoBoundaries {level} unavailable: {exc}") from exc
        LOG.warning("geoBoundaries %s API failed (%s); using cached copy", level, exc)
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    out: list[tuple[Any, str]] = []
    for feature in data.get("features", []):
        geom = shape(feature["geometry"])
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        props = feature.get("properties") or {}
        out.append((geom, str(props.get("shapeName") or props.get("NAME") or "Unknown")))
    if not out:
        raise PipelineError(f"geoBoundaries {level} contained no features")
    return out


def _assign_states(units: list[tuple[Any, str]], states: list[tuple[Any, str]]) -> list[AdminUnit]:
    tree = STRtree([g for g, _ in states])
    result: list[AdminUnit] = []
    for geom, name in units:
        point = geom.representative_point()
        hits = tree.query(point, predicate="intersects")
        idx = int(hits[0]) if len(hits) else int(tree.nearest(point))
        state_en, state_my = normalise_region(states[idx][1])
        result.append(AdminUnit(name=name, state=state_en, state_my=state_my, geom=geom))
    return result


def _gaul_fallback() -> AdminIndex:
    """District-level fallback from FAO GAUL inside Earth Engine."""
    if ee is None:
        raise PipelineError("earthengine-api is not installed")
    fc = (ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level2")
          .filter(ee.Filter.eq("ADM0_NAME", "Myanmar")))
    data = fc.getInfo()
    units: list[AdminUnit] = []
    for feature in data.get("features", []):
        geom = shape(feature["geometry"])
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        props = feature.get("properties") or {}
        state_en, state_my = normalise_region(str(props.get("ADM1_NAME", "")))
        units.append(AdminUnit(str(props.get("ADM2_NAME", "Unknown")), state_en, state_my, geom))
    if not units:
        raise PipelineError("GAUL returned no Myanmar districts")
    return AdminIndex(units, "district")


def _local_admin() -> Optional[AdminIndex]:
    """Township polygons shipped with the repository (OCHA/MIMU-based COD-AB, English + Burmese names)."""
    if not ADMIN_LOCAL_FILE.exists():
        return None
    data = json.loads(ADMIN_LOCAL_FILE.read_text(encoding="utf-8"))
    units: list[AdminUnit] = []
    for feature in data.get("features", []):
        geom = shape(feature["geometry"])
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        p = feature.get("properties") or {}
        units.append(AdminUnit(name=str(p.get("n") or "Unknown"), state=str(p.get("s") or ""),
                               state_my=str(p.get("sm") or ""), geom=geom, name_my=str(p.get("nm") or "")))
    if not units:
        return None
    return AdminIndex(units, "township")


def load_admin() -> Optional[AdminIndex]:
    try:
        local = _local_admin()
        if local is not None:
            LOG.info("Loaded %d township polygons from %s", len(local.units), ADMIN_LOCAL_FILE.name)
            return local
    except Exception as exc:
        LOG.warning("Local township file unusable (%s); falling back to geoBoundaries", exc)
    try:
        townships = _geoboundaries("ADM3")
        try:
            states = _geoboundaries("ADM1")
            units = _assign_states(townships, states)
        except PipelineError as exc:
            LOG.warning("State boundaries unavailable (%s); townships get no state label", exc)
            units = [AdminUnit(name, "", "", geom) for geom, name in townships]
        index = AdminIndex(units, "township")
        LOG.info("Loaded %d township polygons", len(units))
        return index
    except Exception as exc:
        LOG.warning("Township boundaries unavailable (%s); trying FAO GAUL districts", exc)
    try:
        index = _gaul_fallback()
        LOG.info("Loaded %d district polygons (fallback)", len(index.units))
        return index
    except Exception as exc:
        LOG.warning("No administrative boundaries available (%s); features will be unnamed", exc)
        return None


# --------------------------------------------------------------------------------------
# Earth Engine
# --------------------------------------------------------------------------------------


def init_earth_engine() -> str:
    """Authenticate with the service-account key in EE_SERVICE_ACCOUNT_KEY. Returns the project id."""
    if ee is None:
        raise ConfigError("The earthengine-api package is not installed.")
    raw = (os.environ.get("EE_SERVICE_ACCOUNT_KEY") or "").strip()
    if not raw:
        raise ConfigError("Secret EE_SERVICE_ACCOUNT_KEY is empty or missing. See README.md.")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        try:
            info = json.loads(base64.b64decode(raw).decode("utf-8"))
        except Exception as exc:
            raise ConfigError("EE_SERVICE_ACCOUNT_KEY is neither JSON nor base64-encoded JSON.") from exc
    if info.get("type") != "service_account" or "private_key" not in info:
        raise ConfigError("EE_SERVICE_ACCOUNT_KEY does not look like a service-account key file.")
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/earthengine",
                "https://www.googleapis.com/auth/cloud-platform"],
    )
    project = os.environ.get("EE_PROJECT") or info.get("project_id")
    if not project:
        raise ConfigError("No Earth Engine project: set the EE_PROJECT variable.")
    ee.Initialize(credentials=credentials, project=project,
                  opt_url="https://earthengine-highvolume.googleapis.com")
    ee.Number(1).getInfo()  # fail fast if credentials or project registration are wrong
    LOG.info("Earth Engine initialised (project %s)", project)
    return project


def bbox_geometry() -> Any:
    return ee.Geometry.Rectangle(list(BBOX), proj="EPSG:4326", geodesic=False)


def myanmar_mask() -> Any:
    """Land mask for Myanmar, buffered 2 km because LSIB is a simplified boundary."""
    fc = (ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
          .filter(ee.Filter.eq("country_na", "Burma"))
          .map(lambda f: f.buffer(2000, 200)))
    return ee.Image(0).byte().paint(fc, 1).selfMask()


def s1_collection() -> Any:
    return (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("resolution_meters", 10))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))


def _mask_incidence_edges(image: Any) -> Any:
    angle = image.select("angle")
    return image.select(["VV", "VH"]).updateMask(angle.gt(ANGLE_MIN).And(angle.lt(ANGLE_MAX)))


def lee_filter(band_db: Any) -> Any:
    """Adaptive Lee speckle filter applied in the linear domain; input and output in dB."""
    linear = ee.Image(10).pow(band_db.divide(10))
    kernel = ee.Kernel.square(radius=LEE_RADIUS, units="pixels")
    mean = linear.reduceNeighborhood(ee.Reducer.mean(), kernel).rename("m")
    variance = linear.reduceNeighborhood(ee.Reducer.variance(), kernel).rename("v")
    cu2 = 1.0 / LEE_ENL
    ci2 = variance.divide(mean.multiply(mean)).max(1e-9)
    weight = ci2.subtract(cu2).divide(ci2.multiply(1.0 + cu2)).clamp(0, 1)
    filtered = mean.add(weight.multiply(linear.subtract(mean)))
    return filtered.log10().multiply(10)


def build_flood_image(window: tuple[str, str], baseline: tuple[str, str], land: Any) -> Any:
    crs = "EPSG:4326"
    s1 = s1_collection()
    recent = (s1.filterDate(*window).map(_mask_incidence_edges).median()
              .reproject(crs=crs, scale=FILTER_SCALE))
    base = (s1.filterDate(*baseline).map(_mask_incidence_edges).median()
            .reproject(crs=crs, scale=FILTER_SCALE))
    vv = lee_filter(recent.select("VV"))
    vh = lee_filter(recent.select("VH"))
    base_vv = lee_filter(base.select("VV"))

    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").unmask(0)
    permanent_water = occurrence.gte(JRC_PERMANENT_OCCURRENCE)

    flooded = (vv.subtract(base_vv).lt(DIFF_THRESHOLD_DB)
               .And(vv.lt(WATER_VV_DB))
               .And(vh.lt(WATER_VH_DB))
               .And(base_vv.gt(WATER_VV_DB))            # was land in the dry season
               .And(slope.lte(MAX_FLOOD_SLOPE_DEG))     # radar-shadow / steep terrain guard
               .And(permanent_water.Not()))
    flooded = flooded.updateMask(land).rename("flood").reproject(crs=crs, scale=FILTER_SCALE)

    if FLOOD_SCALE != FILTER_SCALE:
        flooded = (flooded.reduceResolution(ee.Reducer.mean(), bestEffort=False, maxPixels=256)
                   .reproject(crs=crs, scale=FLOOD_SCALE).gte(0.5).rename("flood"))
    flooded = flooded.selfMask()
    pixel_count = flooded.connectedPixelCount(maxSize=max(MIN_FLOOD_PIXELS + 1, 2), eightConnected=True)
    return flooded.updateMask(pixel_count.gte(MIN_FLOOD_PIXELS)).rename("flood")


def select_rain_source(now: datetime) -> dict[str, Any]:
    """Pick the first rainfall product whose newest image is recent enough."""
    best: Optional[dict[str, Any]] = None
    for source in RAIN_SOURCES:
        try:
            collection = ee.ImageCollection(source["collection"]).filterDate(
                iso(now - timedelta(days=60)), iso(now + timedelta(days=1)))
            latest_ms = collection.aggregate_max("system:time_start").getInfo()
        except Exception as exc:
            LOG.warning("Rain source %s unavailable: %s", source["id"], str(exc)[:200])
            continue
        if latest_ms is None:
            LOG.warning("Rain source %s has no images in the last 60 days", source["id"])
            continue
        age_days = (now - from_ms(latest_ms)).total_seconds() / 86400.0
        candidate = {**source, "latest_ms": int(latest_ms), "age_days": age_days}
        LOG.info("Rain source %s: newest image %s (%.1f days old)",
                 source["id"], iso(from_ms(latest_ms)), age_days)
        if age_days <= RAIN_MAX_LATENCY_DAYS:
            return {**candidate, "stale": False}
        if best is None or age_days < best["age_days"]:
            best = candidate
    if best is None:
        raise PipelineError("No rainfall dataset is available in Earth Engine right now.")
    LOG.warning("All rainfall sources are older than %.1f days; using %s", RAIN_MAX_LATENCY_DAYS, best["id"])
    return {**best, "stale": True}


def rain_accumulation(selection: dict[str, Any]) -> Any:
    end_ms = selection["latest_ms"] + selection["step_ms"]
    start_ms = end_ms - RAIN_WINDOW_DAYS * 24 * 3600 * 1000
    collection = (ee.ImageCollection(selection["collection"])
                  .filterDate(ee.Date(start_ms), ee.Date(end_ms))
                  .select(selection["band"]))
    return collection.sum().multiply(selection["factor"]).rename("rain_mm")


def _rule_image(rain: Any, slope: Any, rules: list[tuple[float, float]]) -> Any:
    result = None
    for min_rain, min_slope in rules:
        test = rain.gte(min_rain).And(slope.gte(min_slope))
        result = test if result is None else result.Or(test)
    return result


def build_landslide_image(rain: Any, land: Any) -> Any:
    crs = "EPSG:4326"
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    # Aggregate the 30 m slope to the 250 m hazard grid (mean slope of the cell)
    slope_c = (slope.reduceResolution(ee.Reducer.mean(), bestEffort=False, maxPixels=1024)
               .reproject(crs=crs, scale=LS_SCALE))
    code = (ee.Image(0)
            .where(_rule_image(rain, slope_c, LS_RULES["low"]), 1)
            .where(_rule_image(rain, slope_c, LS_RULES["moderate"]), 2)
            .where(_rule_image(rain, slope_c, LS_RULES["high"]), 3))
    code = code.updateMask(slope_c.gte(LS_SLOPE_MIN_DEG)).updateMask(code.gt(0)).updateMask(land)
    return code.rename("code").toInt()


def build_susceptibility_image(land: Any) -> Any:
    """Static terrain susceptibility from mean SRTM slope: 1 = steep, 2 = very steep, 3 = extreme."""
    crs = "EPSG:4326"
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    slope_c = (slope.reduceResolution(ee.Reducer.mean(), bestEffort=False, maxPixels=1024)
               .reproject(crs=crs, scale=SUSC_SCALE))
    code = (ee.Image(0)
            .where(slope_c.gte(SUSC_LOW_DEG), 1)
            .where(slope_c.gte(SUSC_MOD_DEG), 2)
            .where(slope_c.gte(SUSC_HIGH_DEG), 3))
    return code.updateMask(code.gt(0)).updateMask(land).rename("code").toInt()


# --------------------------------------------------------------------------------------
# Tiled raster -> vector extraction
# --------------------------------------------------------------------------------------

_SPLIT_HINTS = (
    "aborted after accumulating", "too many", "timed out", "timeout", "memory limit",
    "too large", "exceeded", "deadline", "internal error", "computation",
)


@dataclass
class TileStats:
    total_area: float = 0.0
    failed_area: float = 0.0
    failed_cells: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def failed_fraction(self) -> float:
        return self.failed_area / self.total_area if self.total_area else 0.0


def make_tiles(bbox: tuple[float, float, float, float], size: float) -> list[tuple[float, float, float, float]]:
    min_x, min_y, max_x, max_y = bbox
    tiles = []
    y = min_y
    while y < max_y - 1e-9:
        x = min_x
        while x < max_x - 1e-9:
            tiles.append((x, y, min(x + size, max_x), min(y + size, max_y)))
            x += size
        y += size
    return tiles


def _bounds_area(bounds: tuple[float, float, float, float]) -> float:
    return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])


def _fetch_tile(make_fc: Callable[[Any], Any], bounds: tuple[float, float, float, float],
                min_cell: float, stats: TileStats) -> list[dict[str, Any]]:
    geometry = ee.Geometry.Rectangle(list(bounds), proj="EPSG:4326", geodesic=False)
    last_error: Optional[Exception] = None
    for attempt in range(EE_RETRIES):
        try:
            data = make_fc(geometry).getInfo()
            return list(data.get("features", []))
        except Exception as exc:  # ee.EEException, HTTP errors, socket errors
            last_error = exc
            message = str(exc).lower()
            if any(hint in message for hint in _SPLIT_HINTS):
                break  # retrying the identical request will not help; split instead
            time.sleep(2 ** attempt * 2)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    if max(width, height) / 2.0 >= min_cell - 1e-9:
        mid_x, mid_y = bounds[0] + width / 2.0, bounds[1] + height / 2.0
        quadrants = [
            (bounds[0], bounds[1], mid_x, mid_y), (mid_x, bounds[1], bounds[2], mid_y),
            (bounds[0], mid_y, mid_x, bounds[3]), (mid_x, mid_y, bounds[2], bounds[3]),
        ]
        features: list[dict[str, Any]] = []
        for quadrant in quadrants:
            features.extend(_fetch_tile(make_fc, quadrant, min_cell, stats))
        return features
    with stats.lock:
        stats.failed_area += _bounds_area(bounds)
        stats.failed_cells += 1
    LOG.error("Tile %s failed permanently: %s", bounds, str(last_error)[:300])
    return []


def vectorise(image: Any, label: str, scale: int, tile_deg: float, min_cell: float,
              admin: Optional[AdminIndex]) -> tuple[list[dict[str, Any]], TileStats]:
    def make_fc(geometry: Any) -> Any:
        return image.reduceToVectors(
            geometry=geometry, scale=scale, crs="EPSG:4326", geometryType="polygon",
            eightConnected=True, labelProperty=label, maxPixels=int(1e9), tileScale=4)

    tiles = make_tiles(BBOX, tile_deg)
    if admin is not None:
        tiles = [t for t in tiles if admin.intersects_box(t)]
    stats = TileStats(total_area=sum(_bounds_area(t) for t in tiles))
    LOG.info("Vectorising %d tiles of %.2f deg (scale %d m)", len(tiles), tile_deg, scale)
    features: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=max(1, EE_WORKERS)) as pool:
        futures = [pool.submit(_fetch_tile, make_fc, tile, min_cell, stats) for tile in tiles]
        for future in cf.as_completed(futures):
            features.extend(future.result())
    LOG.info("Received %d raw polygons (%d failed cells)", len(features), stats.failed_cells)
    return features, stats


# --------------------------------------------------------------------------------------
# Geometry post-processing
# --------------------------------------------------------------------------------------

_AREA_TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)


def area_ha(geom: Any) -> float:
    """Equal-area (EPSG:6933) area in hectares."""
    return shp_transform(_AREA_TRANSFORMER.transform, geom).area / 10_000.0


def merge_and_simplify(geoms: list[Any], tolerance: float) -> list[Polygon]:
    """Union tile seams, then Douglas-Peucker simplify and explode to single polygons."""
    clean = []
    for geom in geoms:
        if geom is None or geom.is_empty:
            continue
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        clean.append(geom)
    if not clean:
        return []
    merged = unary_union(clean)
    out: list[Polygon] = []
    for poly in polygon_parts(merged):
        simple = poly.simplify(tolerance, preserve_topology=True)
        if not simple.is_valid:
            simple = shapely.make_valid(simple)
        out.extend(p for p in polygon_parts(simple) if not p.is_empty)
    return out


def build_pieces(polygons: list[Polygon], admin: Optional[AdminIndex], base_props: dict[str, Any],
                 min_piece_ha: float) -> list[dict[str, Any]]:
    """Split polygons by township and attach name / area properties."""
    pieces: list[dict[str, Any]] = []
    for poly in polygons:
        splits = admin.split(poly) if admin is not None else [(poly, None)]
        for geom, unit in splits:
            ha = area_ha(geom)
            if ha < min_piece_ha:
                continue
            props = dict(base_props)
            props.update({
                "township": unit.name if unit else "Unknown",
                "township_my": unit.name_my if unit else "",
                "state_region": unit.state if unit else "",
                "state_region_my": unit.state_my if unit else "",
                "area_ha": round(ha, 1),
            })
            pieces.append({"geom": geom, "props": props, "area": ha})
    return pieces


def _round_coords(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (int, float)):
            return [round(float(v), COORD_DECIMALS) for v in value]
        return [_round_coords(v) for v in value]
    return value


def serialise_features(pieces: list[dict[str, Any]], tolerance: Optional[float]) -> list[str]:
    out: list[str] = []
    grid = 10 ** -COORD_DECIMALS
    for index, piece in enumerate(pieces, start=1):
        geom = piece["geom"]
        if tolerance is not None:
            geom = geom.simplify(tolerance, preserve_topology=True)
        try:
            geom = shapely.set_precision(geom, grid)
        except shapely.errors.GEOSException:
            pass
        if geom.is_empty or not polygon_parts(geom):
            continue
        parts = polygon_parts(geom)
        geom = parts[0] if len(parts) == 1 else MultiPolygon(parts)
        shape_dict = mapping(geom)
        feature = {
            "type": "Feature",
            "id": index,
            "properties": piece["props"],
            "geometry": {"type": shape_dict["type"], "coordinates": _round_coords(shape_dict["coordinates"])},
        }
        out.append(json.dumps(feature, separators=(",", ":"), ensure_ascii=False))
    return out


def assemble_collection(feature_json: list[str], extra: dict[str, Any]) -> bytes:
    head = json.dumps({"type": "FeatureCollection", **extra}, separators=(",", ":"), ensure_ascii=False)
    body = ",".join(feature_json)
    return (head[:-1] + ',"features":[' + body + "]}\n").encode("utf-8")


def fit_to_size(pieces: list[dict[str, Any]], max_bytes: int,
                extra: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Serialise, escalating simplification and finally dropping the smallest polygons to fit max_bytes."""
    info: dict[str, Any] = {"simplify_tolerance": SIMPLIFY_TOLERANCE, "dropped_features": 0, "truncated": False}
    working = pieces
    tolerance = SIMPLIFY_TOLERANCE
    for step in range(7):
        if step:
            tolerance = SIMPLIFY_TOLERANCE * (1.6 ** step)
        feats = serialise_features(working, tolerance if step else None)
        payload = assemble_collection(feats, {**extra, "simplify_tolerance": round(tolerance, 5)})
        if len(payload) <= max_bytes:
            info.update(simplify_tolerance=round(tolerance, 5), feature_count=len(feats))
            return payload, info
        LOG.warning("Layer is %.2f MB at tolerance %.4f; simplifying further", len(payload) / 1e6, tolerance)
    ordered = sorted(working, key=lambda p: p["area"], reverse=True)
    keep = len(ordered)
    while keep > 1:
        keep = int(keep * 0.85)
        feats = serialise_features(ordered[:keep], tolerance)
        payload = assemble_collection(feats, {**extra, "simplify_tolerance": round(tolerance, 5)})
        if len(payload) <= max_bytes:
            info.update(simplify_tolerance=round(tolerance, 5), feature_count=len(feats),
                        dropped_features=len(ordered) - keep, truncated=True)
            LOG.warning("Dropped %d smallest polygons to respect the size limit", len(ordered) - keep)
            return payload, info
    raise PipelineError("Could not fit the layer inside the size limit")


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------


def _township_totals(pieces: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    for piece in pieces:
        props = piece["props"]
        key = (props["township"], props["state_region"])
        entry = totals.setdefault(key, {"township": key[0], "township_my": props.get("township_my", ""),
                                        "state_region": key[1],
                                        "state_region_my": props.get("state_region_my", ""), "area_ha": 0.0})
        entry["area_ha"] += piece["area"]
    return totals


def flood_summary(pieces: list[dict[str, Any]], updated: str) -> dict[str, Any]:
    totals = _township_totals(pieces)
    ranked = sorted(totals.values(), key=lambda e: e["area_ha"], reverse=True)
    by_state: dict[str, dict[str, Any]] = {}
    for entry in totals.values():
        state = by_state.setdefault(entry["state_region"], {
            "state_region": entry["state_region"], "state_region_my": entry["state_region_my"], "area_ha": 0.0})
        state["area_ha"] += entry["area_ha"]
    return {
        "updated_utc": updated,
        "total_area_ha": round(sum(p["area"] for p in pieces), 1),
        "polygon_count": len(pieces),
        "townships_affected": sum(1 for e in totals.values() if e["area_ha"] >= MIN_FLOOD_PIECE_HA),
        "top_townships": [{**e, "area_ha": round(e["area_ha"], 1)} for e in ranked[:10]],
        "by_state_region": [{**e, "area_ha": round(e["area_ha"], 1)}
                            for e in sorted(by_state.values(), key=lambda e: e["area_ha"], reverse=True)],
    }


def landslide_summary(pieces: list[dict[str, Any]], updated: str) -> dict[str, Any]:
    area_by_class = {1: 0.0, 2: 0.0, 3: 0.0}
    per_township: dict[int, dict[tuple[str, str], dict[str, Any]]] = {1: {}, 2: {}, 3: {}}
    for piece in pieces:
        code = int(piece["props"]["hazard_code"])
        area_by_class[code] += piece["area"]
        props = piece["props"]
        key = (props["township"], props["state_region"])
        entry = per_township[code].setdefault(key, {"township": key[0], "township_my": props.get("township_my", ""),
                                                    "state_region": key[1],
                                                    "state_region_my": props.get("state_region_my", ""),
                                                    "area_ha": 0.0})
        entry["area_ha"] += piece["area"]

    def count(code: int) -> int:
        return sum(1 for e in per_township[code].values() if e["area_ha"] >= MIN_TOWNSHIP_WARNING_HA)

    warned: dict[tuple[str, str], dict[str, Any]] = {}
    for code in (2, 3):
        for key, entry in per_township[code].items():
            slot = warned.setdefault(key, {**entry, "area_ha": 0.0, "high_ha": 0.0})
            slot["area_ha"] += entry["area_ha"]
            if code == 3:
                slot["high_ha"] += entry["area_ha"]
    warned = {k: v for k, v in warned.items() if v["area_ha"] >= MIN_TOWNSHIP_WARNING_HA}
    ranked = sorted(warned.values(), key=lambda e: (e["high_ha"], e["area_ha"]), reverse=True)
    return {
        "updated_utc": updated,
        "high_ha": round(area_by_class[3], 1),
        "moderate_ha": round(area_by_class[2], 1),
        "low_ha": round(area_by_class[1], 1),
        "polygon_count": len(pieces),
        "townships_warned": len(warned),
        "townships_high": count(3),
        "townships_moderate": count(2),
        "townships_low": count(1),
        "top_townships": [{**e, "area_ha": round(e["area_ha"], 1), "high_ha": round(e["high_ha"], 1)}
                          for e in ranked[:10]],
    }


# --------------------------------------------------------------------------------------
# Layer runners
# --------------------------------------------------------------------------------------


@dataclass
class LayerResult:
    status: str                      # updated | unchanged | no_new_data | error
    message: str
    meta: dict[str, Any] = field(default_factory=dict)
    summary: Optional[dict[str, Any]] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    now: datetime
    force: bool
    prev_meta: dict[str, Any]
    prev_summary: dict[str, Any]
    land: Any = None
    _admin: Any = None
    _admin_loaded: bool = False

    def admin(self) -> Optional[AdminIndex]:
        if not self._admin_loaded:
            self._admin = load_admin()
            self._admin_loaded = True
        return self._admin


def _prev_layer(ctx: Context, name: str) -> dict[str, Any]:
    return (ctx.prev_meta.get("layers") or {}).get(name) or {}


def _finalise_layer(path: Path, pieces: list[dict[str, Any]], stats: TileStats, label: str,
                    updated: str, extra_header: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, info = fit_to_size(pieces, MAX_FILE_BYTES, {"generated_utc": updated, **extra_header})
    atomic_write_bytes(path, payload)
    meta = {
        "updated_utc": updated,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "feature_count": info.get("feature_count", 0),
        "dropped_features": info["dropped_features"],
        "truncated": info["truncated"],
        "simplify_tolerance": info["simplify_tolerance"],
        "failed_area_fraction": round(stats.failed_fraction, 4),
        "failed_cells": stats.failed_cells,
    }
    LOG.info("%s layer written: %.2f MB, %d features", label, len(payload) / 1e6, meta["feature_count"])
    return meta, info


def run_flood(ctx: Context) -> LayerResult:
    now = ctx.now
    window_start = now - timedelta(days=S1_LOOKBACK_DAYS)
    scenes = (s1_collection().filterBounds(bbox_geometry())
              .filterDate(iso(window_start), iso(now + timedelta(days=1))))
    count = int(scenes.size().getInfo())
    if count == 0:
        return LayerResult("no_new_data",
                           f"No Sentinel-1 scenes in the last {S1_LOOKBACK_DAYS} days; previous flood layer kept.")
    latest_ms = scenes.aggregate_max("system:time_start").getInfo()
    latest_iso = iso(from_ms(latest_ms))
    prev = _prev_layer(ctx, "flood")
    satellite = {"latest_scene_utc": latest_iso, "scene_count": count,
                 "window_start_utc": iso(window_start), "window_end_utc": iso(now)}
    if (not ctx.force and prev.get("latest_scene_utc") == latest_iso and prev.get("sha256")
            and FLOOD_FILE.exists()):
        return LayerResult("unchanged", f"No Sentinel-1 scene newer than {latest_iso}; previous flood layer kept.",
                           meta={"latest_scene_utc": latest_iso}, extra={"satellite": satellite})

    year = now.year if now.month > BASELINE_END_MONTH else now.year - 1
    baseline_start = datetime(year, BASELINE_START_MONTH, 1, tzinfo=timezone.utc)
    baseline_end = datetime(year, BASELINE_END_MONTH + 1, 1, tzinfo=timezone.utc)
    satellite["baseline_period"] = f"{baseline_start:%Y-%m-%d}/{(baseline_end - timedelta(days=1)):%Y-%m-%d}"
    LOG.info("Flood: %d scenes, newest %s, baseline %s", count, latest_iso, satellite["baseline_period"])

    image = build_flood_image((iso(window_start), iso(now + timedelta(days=1))),
                              (iso(baseline_start), iso(baseline_end)), ctx.land)
    admin = ctx.admin()
    features, stats = vectorise(image, "flood", FLOOD_SCALE, FLOOD_TILE_DEG, FLOOD_MIN_TILE_DEG, admin)
    if stats.failed_fraction > MAX_FAILED_AREA_FRACTION:
        return LayerResult("error", f"{stats.failed_fraction:.0%} of the country failed to process; "
                                    "previous flood layer kept.",
                           meta={"failed_area_fraction": round(stats.failed_fraction, 4)})
    geoms = [shape(f["geometry"]) for f in features if f.get("geometry")]
    polygons = merge_and_simplify(geoms, SIMPLIFY_TOLERANCE)
    pieces = build_pieces(polygons, admin, {"layer": "flood"}, MIN_FLOOD_PIECE_HA)
    pieces.sort(key=lambda p: p["area"], reverse=True)
    updated = iso(now)
    meta, _ = _finalise_layer(FLOOD_FILE, pieces, stats, "Flood", updated,
                              {"layer": "flood", "latest_scene_utc": latest_iso})
    meta["latest_scene_utc"] = latest_iso
    message = "Flood layer updated."
    if stats.failed_cells:
        message += f" {stats.failed_cells} cells could not be processed."
    return LayerResult("updated", message, meta=meta, summary=flood_summary(pieces, updated),
                       extra={"satellite": satellite})


def run_landslide(ctx: Context) -> LayerResult:
    now = ctx.now
    selection = select_rain_source(now)
    rain_end_iso = iso(from_ms(selection["latest_ms"] + selection["step_ms"]))
    rain_start_iso = iso(from_ms(selection["latest_ms"] + selection["step_ms"]
                                 - RAIN_WINDOW_DAYS * 24 * 3600 * 1000))
    rainfall = {"source": selection["id"], "window_start_utc": rain_start_iso, "window_end_utc": rain_end_iso,
                "data_age_days": round(selection["age_days"], 2), "stale": bool(selection["stale"])}
    prev = _prev_layer(ctx, "landslide")
    signature = f"{selection['id']}@{rain_end_iso}"
    if (not ctx.force and prev.get("rain_signature") == signature and prev.get("sha256")
            and LANDSLIDE_FILE.exists()):
        return LayerResult("unchanged", f"No newer rainfall data than {rain_end_iso}; previous landslide layer kept.",
                           meta={"rain_signature": signature}, extra={"rainfall": rainfall})

    rain = rain_accumulation(selection)
    try:
        peak = rain.updateMask(ctx.land).reduceRegion(
            reducer=ee.Reducer.max(), geometry=bbox_geometry(), scale=10000,
            maxPixels=int(1e9), bestEffort=True).getInfo()
        rainfall["max_7d_mm"] = round(float(peak.get("rain_mm")), 1) if peak.get("rain_mm") is not None else None
    except Exception as exc:
        LOG.warning("Could not compute peak rainfall: %s", str(exc)[:200])
        rainfall["max_7d_mm"] = None

    image = build_landslide_image(rain, ctx.land)
    admin = ctx.admin()
    features, stats = vectorise(image, "code", LS_SCALE, LS_TILE_DEG, LS_MIN_TILE_DEG, admin)
    if stats.failed_fraction > MAX_FAILED_AREA_FRACTION:
        return LayerResult("error", f"{stats.failed_fraction:.0%} of the country failed to process; "
                                    "previous landslide layer kept.",
                           meta={"failed_area_fraction": round(stats.failed_fraction, 4)})
    by_class: dict[int, list[Any]] = {1: [], 2: [], 3: []}
    for feature in features:
        code = int(round(float((feature.get("properties") or {}).get("code", 0))))
        if code in by_class and feature.get("geometry"):
            by_class[code].append(shape(feature["geometry"]))
    pieces: list[dict[str, Any]] = []
    for code in (1, 2, 3):  # low first so that high is drawn last (on top)
        polygons = merge_and_simplify(by_class[code], SIMPLIFY_TOLERANCE)
        class_pieces = build_pieces(
            polygons, admin,
            {"layer": "landslide", "hazard": HAZARD_NAMES[code], "hazard_code": code},
            MIN_LANDSLIDE_PIECE_HA)
        class_pieces.sort(key=lambda p: p["area"], reverse=True)
        pieces.extend(class_pieces)
    updated = iso(now)
    meta, _ = _finalise_layer(LANDSLIDE_FILE, pieces, stats, "Landslide", updated,
                              {"layer": "landslide", "rain_source": selection["id"], "rain_window_end_utc": rain_end_iso})
    meta["rain_signature"] = signature
    message = "Landslide layer updated."
    if selection["stale"]:
        message += f" Rainfall data is {selection['age_days']:.1f} days old."
    return LayerResult("updated", message, meta=meta, summary=landslide_summary(pieces, updated),
                       extra={"rainfall": rainfall})


def run_susceptibility(ctx: Context) -> LayerResult:
    """Slope never changes, so this layer is built once (or when forced) and then kept."""
    prev = _prev_layer(ctx, "susceptibility")
    if not ctx.force and prev.get("sha256") and SUSCEPTIBILITY_FILE.exists():
        return LayerResult("unchanged", "Static susceptibility layer already built; kept.")
    image = build_susceptibility_image(ctx.land)
    admin = ctx.admin()
    features, stats = vectorise(image, "code", SUSC_SCALE, SUSC_TILE_DEG, LS_MIN_TILE_DEG, admin)
    if stats.failed_fraction > MAX_FAILED_AREA_FRACTION:
        return LayerResult("error", f"{stats.failed_fraction:.0%} of the country failed to process; "
                                    "susceptibility layer not updated.",
                           meta={"failed_area_fraction": round(stats.failed_fraction, 4)})
    by_class: dict[int, list[Any]] = {1: [], 2: [], 3: []}
    for feature in features:
        code = int(round(float((feature.get("properties") or {}).get("code", 0))))
        if code in by_class and feature.get("geometry"):
            by_class[code].append(shape(feature["geometry"]))
    pieces: list[dict[str, Any]] = []
    for code in (1, 2, 3):
        polygons = merge_and_simplify(by_class[code], SIMPLIFY_TOLERANCE)
        class_pieces = build_pieces(
            polygons, admin,
            {"layer": "susceptibility", "hazard": HAZARD_NAMES[code], "hazard_code": code},
            MIN_LANDSLIDE_PIECE_HA)
        class_pieces.sort(key=lambda p: p["area"], reverse=True)
        pieces.extend(class_pieces)
    updated = iso(ctx.now)
    meta, _ = _finalise_layer(SUSCEPTIBILITY_FILE, pieces, stats, "Susceptibility", updated,
                              {"layer": "susceptibility", "method": "mean SRTM slope"})
    return LayerResult("updated", "Static susceptibility layer built.", meta=meta)


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


def write_step_summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


def package_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0], "shapely": shapely.__version__}
    if ee is not None:
        versions["earthengine-api"] = getattr(ee, "__version__", "unknown")
    return versions


def parameters_snapshot() -> dict[str, Any]:
    return {
        "bbox": list(BBOX), "s1_lookback_days": S1_LOOKBACK_DAYS, "diff_threshold_db": DIFF_THRESHOLD_DB,
        "water_vv_db": WATER_VV_DB, "water_vh_db": WATER_VH_DB, "max_flood_slope_deg": MAX_FLOOD_SLOPE_DEG,
        "jrc_permanent_occurrence": JRC_PERMANENT_OCCURRENCE, "flood_scale_m": FLOOD_SCALE,
        "filter_scale_m": FILTER_SCALE, "lee_enl": LEE_ENL, "ls_slope_min_deg": LS_SLOPE_MIN_DEG,
        "ls_scale_m": LS_SCALE, "rain_window_days": RAIN_WINDOW_DAYS, "ls_rules": LS_RULES,
        "simplify_tolerance": SIMPLIFY_TOLERANCE, "max_file_bytes": MAX_FILE_BYTES,
    }


def run_pipeline(force: bool) -> int:
    now = utcnow()
    prev_meta = read_json(METADATA_FILE, {}) or {}
    prev_summary = read_json(SUMMARY_FILE, {}) or {}
    ctx = Context(now=now, force=force, prev_meta=prev_meta, prev_summary=prev_summary)

    meta = dict(prev_meta)
    meta.setdefault("schema_version", 1)
    meta.setdefault("layers", {})
    summary = dict(prev_summary) if prev_summary else read_json(SUMMARY_FILE, {}) or {}
    summary.setdefault("schema_version", 1)
    for key in ("satellite", "rainfall", "flood", "landslide"):
        summary.setdefault(key, {})
    meta["last_run_utc"] = iso(now)
    meta["versions"] = package_versions()
    meta["parameters"] = parameters_snapshot()

    results: dict[str, LayerResult] = {}
    try:
        init_earth_engine()
        ctx.land = myanmar_mask()
        for name, runner in (("flood", run_flood), ("landslide", run_landslide),
                             ("susceptibility", run_susceptibility)):
            try:
                results[name] = runner(ctx)
            except Exception as exc:
                LOG.exception("%s layer failed", name)
                results[name] = LayerResult("error", f"{type(exc).__name__}: {str(exc)[:300]}")
    except Exception as exc:
        LOG.exception("Pipeline could not start")
        message = f"{type(exc).__name__}: {str(exc)[:300]}"
        for name in ("flood", "landslide", "susceptibility"):
            results[name] = LayerResult("error", message)

    for name, result in results.items():
        layer_meta = dict(meta["layers"].get(name) or {})
        layer_meta.update(result.meta)
        layer_meta["status"] = result.status
        layer_meta["message"] = result.message
        layer_meta["last_checked_utc"] = iso(now)
        meta["layers"][name] = layer_meta
        if result.summary is not None:
            summary[name] = result.summary
        if "satellite" in result.extra:
            summary["satellite"] = {**summary.get("satellite", {}), **result.extra["satellite"]}
        if "rainfall" in result.extra:
            summary["rainfall"] = {**summary.get("rainfall", {}), **result.extra["rainfall"]}
    if "satellite" in summary:
        summary["satellite"]["sensor"] = "Sentinel-1 IW GRD (VV+VH)"
        summary["satellite"]["last_checked_utc"] = iso(now)
    admin = ctx._admin if ctx._admin_loaded else None
    if admin is not None:
        meta["admin_level"] = admin.level
        summary["admin_level"] = admin.level
    summary["generated_utc"] = iso(now)

    statuses = [r.status for r in results.values()]
    if "error" in statuses:
        meta["run_status"] = "error"
    elif any(m.get("failed_cells") for m in meta["layers"].values()):
        meta["run_status"] = "partial"
    else:
        meta["run_status"] = "ok"

    write_json(SUMMARY_FILE, summary)
    write_json(METADATA_FILE, meta)

    lines = ["### Hazard pipeline", "", "| Layer | Status | Message |", "|---|---|---|"]
    for name, result in results.items():
        lines.append(f"| {name} | {result.status} | {result.message} |")
    write_step_summary(lines)
    for name, result in results.items():
        LOG.info("%s: %s - %s", name, result.status, result.message)
    return 1 if "error" in statuses else 0


# --------------------------------------------------------------------------------------
# Self-test (no Earth Engine needed)
# --------------------------------------------------------------------------------------


def selftest() -> int:
    import random

    LOG.info("Running self-test")
    random.seed(7)
    units = [
        AdminUnit("Alpha", "Bago", "ပဲခူး", box(94.0, 17.0, 95.0, 18.0)),
        AdminUnit("Beta", "Mandalay", "မန္တလေး", box(95.0, 17.0, 96.0, 18.0)),
    ]
    admin = AdminIndex(units, "township")
    # Two raster-like blocks that touch at a tile seam (x = 94.5), one crossing the township border
    seam_a = box(94.2, 17.2, 94.5, 17.4)
    seam_b = box(94.5, 17.2, 94.8, 17.4)
    crossing = box(94.9, 17.5, 95.1, 17.6)
    outside = box(97.0, 20.0, 97.1, 20.1)  # not in any township -> dropped
    noisy = [Polygon([(94.1 + i * 0.002 + random.random() * 1e-4, 17.7 + random.random() * 1e-4)
                      for i in range(60)] + [(94.2, 17.9), (94.1, 17.9)]) for _ in range(3)]
    polygons = merge_and_simplify([seam_a, seam_b, crossing, outside] + noisy, SIMPLIFY_TOLERANCE)
    pieces = build_pieces(polygons, admin, {"layer": "flood"}, MIN_FLOOD_PIECE_HA)
    assert pieces, "no pieces produced"
    names = sorted({p["props"]["township"] for p in pieces})
    assert names == ["Alpha", "Beta"], names
    assert all(p["props"]["area_ha"] > 0 for p in pieces)
    merged_blocks = [p for p in pieces if p["props"]["township"] == "Alpha" and p["area"] > 1000]
    assert merged_blocks, "seam polygons were not merged"
    summary = flood_summary(pieces, iso(utcnow()))
    assert summary["townships_affected"] == 2 and summary["total_area_ha"] > 0
    payload, info = fit_to_size(pieces, MAX_FILE_BYTES, {"layer": "flood"})
    json.loads(payload)
    tiny_payload, tiny_info = fit_to_size(pieces, 1100, {"layer": "flood"})
    assert len(tiny_payload) <= 1100 and tiny_info["truncated"], "size fitting failed"
    ls_pieces = build_pieces(merge_and_simplify([box(94.3, 17.3, 94.6, 17.6)], SIMPLIFY_TOLERANCE), admin,
                             {"layer": "landslide", "hazard": "High", "hazard_code": 3}, MIN_LANDSLIDE_PIECE_HA)
    ls = landslide_summary(ls_pieces, iso(utcnow()))
    assert ls["townships_high"] == 1 and ls["townships_warned"] == 1, ls
    assert normalise_region("Rakhine State") == ("Rakhine", "ရခိုင်")
    assert normalise_region("Naypyitaw")[0] == "Nay Pyi Taw"
    assert len(make_tiles(BBOX, 2.0)) == 5 * 10
    LOG.info("Self-test passed: %d pieces, full file %d bytes, truncated file %d bytes",
             len(pieces), len(payload), len(tiny_payload))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Myanmar NRT flood & landslide hazard pipeline")
    parser.add_argument("--selftest", action="store_true", help="run offline post-processing tests and exit")
    parser.add_argument("--force", action="store_true", help="re-process even when no new data was found")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", stream=sys.stdout)
    if args.selftest:
        return selftest()
    force = args.force or os.environ.get("FORCE_REPROCESS", "0") == "1"
    return run_pipeline(force)


if __name__ == "__main__":
    sys.exit(main())
