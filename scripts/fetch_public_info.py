#!/usr/bin/env python3
"""Refresh weather-risk screening and verified public-source links for Myanmar.

This script never creates official warnings. It stores forecast-derived screening,
links/headlines from authoritative sources, and a recent-earthquake feed separately.
If a source fails, its last successful data is retained with its original update time
and the source check is marked failed.

Usage: python scripts/fetch_public_info.py [--selftest]
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "public_info.json"
USER_AGENT = "MyanmarHazardMonitor/2.0 (+https://github.com)"
TIMEOUT = 25

WEATHER_API = "https://api.open-meteo.com/v1/forecast"
CITY_POINTS = [
    ("Yangon", "ရန်ကုန်", 16.8661, 96.1951),
    ("Mandalay", "မန္တလေး", 21.9588, 96.0891),
    ("Nay Pyi Taw", "နေပြည်တော်", 19.7633, 96.0785),
    ("Taunggyi", "တောင်ကြီး", 20.7892, 97.0378),
    ("Mawlamyine", "မော်လမြိုင်", 16.4905, 97.6283),
    ("Sittwe", "စစ်တွေ", 20.1500, 92.9000),
    ("Pathein", "ပုသိမ်", 16.7792, 94.7321),
    ("Monywa", "မုံရွာ", 22.1086, 95.1358),
    ("Myitkyina", "မြစ်ကြီးနား", 25.3833, 97.4000),
    ("Hpa-An", "ဘားအံ", 16.8890, 97.6340),
    ("Dawei", "ထားဝယ်", 14.0823, 98.1959),
    ("Bago", "ပဲခူး", 17.3367, 96.4797),
    ("Lashio", "လားရှိုး", 22.9359, 97.7498),
    ("Hakha", "ဟားခါး", 22.6500, 93.6167),
    ("Kyaing Tong", "ကျိုင်းတုံ", 21.3000, 99.6000),
]

SOURCES = {
    "weather": {"name": "Open-Meteo Forecast API", "url": "https://open-meteo.com/en/docs", "kind": "forecast"},
    "dmh": {"name": "Myanmar Department of Meteorology and Hydrology (DMH)", "url": "https://www.moezala.gov.mm/index.php/en", "kind": "official_bulletins"},
    "enso": {"name": "NOAA Climate Prediction Center ENSO Diagnostic Discussion", "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml", "kind": "climate_outlook"},
    "health": {"name": "WHO South-East Asia: outbreaks and emergencies", "url": "https://www.who.int/southeastasia/outbreaks-and-emergencies", "kind": "health_source"},
    "earthquakes": {"name": "USGS Earthquake Hazards Program", "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson", "kind": "earthquake_feed"},
}
LOG = logging.getLogger("public-info")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_utc": None,
        "source_checks": {},
        "sources": SOURCES,
        "weather": {"status": "unavailable", "updated_utc": None, "cities": []},
        "enso": {"status": "unavailable", "updated_utc": None, "title": "ENSO update not yet retrieved", "url": SOURCES["enso"]["url"]},
        "dmh": {"status": "unavailable", "updated_utc": None, "items": [], "url": SOURCES["dmh"]["url"]},
        "health": {"status": "unavailable", "updated_utc": None, "items": [], "url": SOURCES["health"]["url"]},
        "earthquakes": {"status": "unavailable", "updated_utc": None, "items": [], "url": SOURCES["earthquakes"]["url"]},
        "disclaimer": "Forecast-based risk screening and third-party source summaries; not official warnings or a substitute for local authorities.",
    }


class HTMLExtract(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._href: Optional[str] = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.text_parts.append(text)
            if self._href is not None:
                self._anchor_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            title = " ".join(" ".join(self._anchor_text).split())
            if title and self._href:
                self.links.append({"title": title, "href": self._href})
            self._href = None
            self._anchor_text = []


def parse_html(content: str) -> tuple[str, list[dict[str, str]]]:
    parser = HTMLExtract()
    parser.feed(content)
    return " ".join(parser.text_parts), parser.links


def request_json(url: str, params: Optional[dict[str, Any]] = None) -> Any:
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def request_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def allowed_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def classify_daily(day: dict[str, Any]) -> list[dict[str, str]]:
    """Transparent threshold screening; never label results as official warnings."""
    out: list[dict[str, str]] = []
    temp = day.get("temp_max_c")
    rain = day.get("precipitation_mm")
    probability = day.get("precipitation_probability_max")
    uv = day.get("uv_index_max")
    wind = day.get("wind_max_kmh")

    if isinstance(temp, (int, float)):
        if temp >= 40:
            out.append({"type": "heat", "level": "severe"})
        elif temp >= 35:
            out.append({"type": "heat", "level": "high"})
        elif temp >= 33:
            out.append({"type": "heat", "level": "moderate"})
    if isinstance(uv, (int, float)):
        if uv >= 11:
            out.append({"type": "uv", "level": "severe"})
        elif uv >= 8:
            out.append({"type": "uv", "level": "high"})
        elif uv >= 6:
            out.append({"type": "uv", "level": "moderate"})
    if isinstance(rain, (int, float)):
        if rain >= 100:
            out.append({"type": "heavy_rain", "level": "severe"})
        elif rain >= 50:
            out.append({"type": "heavy_rain", "level": "high"})
        elif rain >= 25 and (probability is None or probability >= 50):
            out.append({"type": "heavy_rain", "level": "moderate"})
    if isinstance(wind, (int, float)):
        if wind >= 70:
            out.append({"type": "wind", "level": "high"})
        elif wind >= 50:
            out.append({"type": "wind", "level": "moderate"})
    return out


def fetch_weather() -> dict[str, Any]:
    coords = CITY_POINTS
    params = {
        "latitude": ",".join(f"{item[2]:.4f}" for item in coords),
        "longitude": ",".join(f"{item[3]:.4f}" for item in coords),
        "daily": "temperature_2m_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,uv_index_max,weather_code",
        "forecast_days": 7,
        "timezone": "Asia/Yangon",
    }
    result = request_json(WEATHER_API, params)
    locations = result if isinstance(result, list) else [result]
    if len(locations) != len(coords):
        raise ValueError(f"Expected {len(coords)} weather locations, received {len(locations)}")
    cities = []
    for identity, payload in zip(coords, locations):
        name, name_my, lat, lon = identity
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        keys = {
            "temp_max_c": daily.get("temperature_2m_max") or [],
            "precipitation_mm": daily.get("precipitation_sum") or [],
            "precipitation_probability_max": daily.get("precipitation_probability_max") or [],
            "wind_max_kmh": daily.get("wind_speed_10m_max") or [],
            "uv_index_max": daily.get("uv_index_max") or [],
            "weather_code": daily.get("weather_code") or [],
        }
        forecast = []
        for i, date in enumerate(dates):
            day: dict[str, Any] = {"date": date}
            for key, values in keys.items():
                value = values[i] if i < len(values) else None
                if isinstance(value, float) and not math.isfinite(value):
                    value = None
                day[key] = value
            day["risks"] = classify_daily(day)
            forecast.append(day)
        if not forecast:
            continue
        cities.append({"name": name, "name_my": name_my, "latitude": lat, "longitude": lon,
                       "timezone": payload.get("timezone", "Asia/Yangon"), "forecast": forecast})
    if not cities:
        raise ValueError("Weather API returned no daily forecasts")
    return {"status": "ok", "updated_utc": now_iso(), "source": SOURCES["weather"]["name"], "cities": cities,
            "method_note": "Threshold-based weather-risk screening, not an official warning; see source for model and uncertainty."}


def fetch_dmh() -> dict[str, Any]:
    url = SOURCES["dmh"]["url"]
    text, links = parse_html(request_html(url))
    pattern = re.compile(r"warning|flood|heavy rain|rainfall|cyclone|storm|river|water level|flash flood|weather forecast|low pressure|bulletin", re.I)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in links:
        title = re.sub(r"\s+", " ", link["title"]).strip()
        href = urljoin(url, link["href"])
        if not pattern.search(title) or not allowed_http_url(href) or urlparse(href).netloc.lower() not in {"www.moezala.gov.mm", "moezala.gov.mm"}:
            continue
        if href in seen or len(title) < 5:
            continue
        seen.add(href)
        items.append({"title": title[:220], "url": href, "source": "DMH"})
        if len(items) >= 8:
            break
    return {"status": "ok", "updated_utc": now_iso(), "items": items, "url": url,
            "page_text_checked": bool(text), "note": "Headlines/links collected from the official DMH page; check the bulletin itself for issue time and location."}


def fetch_enso() -> dict[str, Any]:
    url = SOURCES["enso"]["url"]
    text, _ = parse_html(request_html(url))
    status_match = re.search(r"ENSO\s+Alert\s+System\s+Status\s*:\s*(.{2,100}?)(?:\s+Synopsis\s*:|\s+Synopsis\b)", text, re.I)
    # Some pages flatten status and synopsis without the expected whitespace.
    if not status_match:
        status_match = re.search(r"ENSO Alert System Status\s*:\s*(El Niño Advisory|El Niño Watch|La Niña Advisory|La Niña Watch|Final La Niña Advisory|Neutral)", text, re.I)
    synopsis_match = re.search(r"Synopsis\s*:\s*(.*?)(?:\s+The CPC Official ENSO outlook|\s+In summary,|$)", text, re.I)
    date_match = re.search(r"(?:issued|issued on)\s+(\d{1,2}\s+[A-Za-z]+\s+20\d{2})", text, re.I)
    status = status_match.group(1).strip(" .:") if status_match else "See latest NOAA bulletin"
    synopsis = re.sub(r"\s+", " ", synopsis_match.group(1)).strip() if synopsis_match else "The current NOAA discussion could not be extracted into a short synopsis; open the original bulletin."
    return {"status": "ok", "updated_utc": now_iso(), "title": "NOAA ENSO Diagnostic Discussion",
            "alert_status": status[:100], "issued_date": date_match.group(1) if date_match else None,
            "synopsis": synopsis[:900], "url": url, "source": SOURCES["enso"]["name"]}


def fetch_health() -> dict[str, Any]:
    url = SOURCES["health"]["url"]
    text, links = parse_html(request_html(url))
    pattern = re.compile(r"Myanmar|outbreak|epidemic|dengue|malaria|cholera|disease|epidemiological|health emergency|health alert", re.I)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in links:
        title = re.sub(r"\s+", " ", link["title"]).strip()
        href = urljoin(url, link["href"])
        if not pattern.search(title) or not allowed_http_url(href):
            continue
        host = (urlparse(href).hostname or "").lower()
        if not (host == "who.int" or host.endswith(".who.int")):
            continue
        if href in seen or len(title) < 8:
            continue
        seen.add(href)
        items.append({"title": title[:220], "url": href, "source": "WHO"})
        if len(items) >= 8:
            break
    return {"status": "ok", "updated_utc": now_iso(), "items": items, "url": url,
            "note": "These are source-page links, not automatically confirmed local outbreak alerts. Verify the original WHO bulletin."}


def fetch_earthquakes() -> dict[str, Any]:
    url = SOURCES["earthquakes"]["url"]
    payload = request_json(url)
    features = filter_usgs_features(payload)
    items = []
    for feature in features:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        lon, lat = float(coords[0]), float(coords[1])
        mag = float(props["mag"])
        stamp = props.get("time")
        time_utc = datetime.fromtimestamp(stamp / 1000, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stamp else None
        event_url = props.get("url") or url
        if not allowed_http_url(event_url):
            event_url = url
        items.append({"title": str(props.get("title") or f"Magnitude {mag:g} earthquake"), "magnitude": round(mag, 1),
                      "latitude": lat, "longitude": lon, "time_utc": time_utc, "url": event_url,
                      "place": str(props.get("place") or "Myanmar region")})
    items.sort(key=lambda item: item.get("time_utc") or "", reverse=True)
    return {"status": "ok", "updated_utc": now_iso(), "items": items[:12], "url": url,
            "note": "USGS feed filtered to a broad Myanmar bounding box and magnitude 2.5+; completeness varies by catalog."}


def load_previous() -> dict[str, Any]:
    try:
        obj = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except (OSError, json.JSONDecodeError):
        pass
    return empty_payload()


def run() -> int:
    data = load_previous()
    defaults = empty_payload()
    for key, value in defaults.items():
        data.setdefault(key, value)
    data["sources"] = SOURCES
    now = now_iso()
    checks: dict[str, Any] = dict(data.get("source_checks") or {})
    tasks = [("weather", fetch_weather), ("dmh", fetch_dmh), ("enso", fetch_enso),
             ("health", fetch_health), ("earthquakes", fetch_earthquakes)]
    successes = 0
    for name, fetcher in tasks:
        try:
            fresh = fetcher()
            data[name] = fresh
            checks[name] = {"status": "ok", "checked_utc": now, "message": "Source fetched successfully."}
            successes += 1
            LOG.info("%s source refreshed", name)
        except Exception as exc:
            checks[name] = {"status": "error", "checked_utc": now, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            if not data.get(name) or data[name].get("status") == "unavailable":
                data[name] = defaults[name]
                data[name]["status"] = "unavailable"
            LOG.warning("%s refresh failed: %s", name, str(exc)[:180])
    data["source_checks"] = checks
    data["generated_utc"] = now
    data["disclaimer"] = defaults["disclaimer"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    LOG.info("Saved %s (%d/5 sources refreshed)", OUTPUT, successes)
    return 0 if successes else 1


def selftest() -> int:
    assert classify_daily({"temp_max_c": 40, "precipitation_mm": 101, "uv_index_max": 12, "wind_max_kmh": 71}) == [
        {"type": "heat", "level": "severe"}, {"type": "uv", "level": "severe"},
        {"type": "heavy_rain", "level": "severe"}, {"type": "wind", "level": "high"}]
    assert classify_daily({"temp_max_c": 24, "precipitation_mm": 0, "uv_index_max": 2, "wind_max_kmh": 3}) == []
    text, links = parse_html('<html><body><a href="/x">Flood Bulletin</a><p>ENSO Alert System Status: El Niño Advisory</p></body></html>')
    assert "ENSO Alert System Status" in text and links == [{"title": "Flood Bulletin", "href": "/x"}]
    assert not allowed_http_url("javascript:alert(1)") and allowed_http_url("https://www.moezala.gov.mm/x")
    sample = {"features": [{"properties": {"mag": 3.2, "time": 1800000000000, "url": "https://earthquake.usgs.gov/test", "place": "near Sagaing"},
                            "geometry": {"coordinates": [95.9, 22.0, 10]}},
                           {"properties": {"mag": 6.0, "time": 1800000000000}, "geometry": {"coordinates": [110.0, 22.0, 10]}}]}
    assert len(filter_usgs_features(sample)) == 1
    print("public-info self-test passed")
    return 0


def filter_usgs_features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure helper tested offline and shared by fetch_earthquakes validation."""
    result = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2 or props.get("mag") is None:
            continue
        lon, lat, mag = float(coords[0]), float(coords[1]), float(props["mag"])
        if 92 <= lon <= 102 and 9 <= lat <= 29 and mag >= 2.5:
            result.append(feature)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run offline tests without network")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return selftest() if args.selftest else run()


if __name__ == "__main__":
    sys.exit(main())
