# Myanmar NRT Flood & Landslide Monitor

A zero-cost, fully automated monitor for Myanmar that runs on the GitHub free tier.

* **GitHub Actions** runs the satellite flood/landslide pipeline twice a day (00:00 and 12:00 UTC) and on demand. A separate lightweight live-event workflow checks USGS/GDACS feeds and 3-day weather-risk screening for 20 Myanmar locations every 30 minutes, publishing only meaningful changes.
* The pipeline uses **Google Earth Engine** to detect newly flooded areas from **Sentinel-1 radar** and to compute a **rainfall × slope landslide hazard** layer.
* Results are saved as small GeoJSON files in `data/` and committed back to the repository.
* A static **Leaflet** web app on **GitHub Pages** reads those files and shows an interactive map with OpenStreetMap base maps (Myanmar + English interface).

> **Not an official warning system.** The layers are satellite-based estimates. Follow the Department of Meteorology and Hydrology (DMH) and local authorities.

## Repository layout

```
.github/workflows/update_data.yml   scheduled pipeline (cron + manual trigger)
.github/workflows/ci.yml            syntax checks + offline self-test on every push / pull request
.github/dependabot.yml              monthly update PRs for Actions and Python packages
scripts/generate_hazard_data.py     Earth Engine processing + GeoJSON/summary generation
scripts/fetch_river_forecast.py     GloFAS river-discharge forecast retrieval
scripts/fetch_disaster_events.py   USGS earthquakes, GDACS alerts, forecast-risk screening and optional NASA FIRMS detections
.github/workflows/refresh_live_events.yml  lightweight 30-minute event-feed refresh
scripts/fetch_public_info.py        city weather screening, official-source links, ENSO and earthquake feed
scripts/make_demo.py                builds demo.html (web app + made-up sample data)
scripts/requirements.txt            Python dependencies
data/                               hazard layers, summaries, reference boundaries and public_info.json
index.html, css/style.css, js/      responsive web app, CDN fallback and stale-service-worker repair
favicon.svg, manifest.webmanifest, icons/   browser tab icon and "Add to Home Screen" icons
START-HERE-MYANMAR.md             Burmese setup steps and honest data/credential limitations
demo.html                           single-file demo with sample data (not real events)
```

## Try it first (no Earth Engine needed)

`demo.html` is the web app with **made-up sample hazard polygons** embedded. Those sample floods/landslides are fake and only demonstrate the UI. It needs a browser and an internet connection for the map. Put it on GitHub Pages and open `https://<user>.github.io/<repo>/demo.html`. On a computer, VS Code + the **Live Server** extension is the non-Python local option. Regenerate it with `python scripts/make_demo.py` when editing the project; no local Python is needed to view the already-built demo.

## Setup

### 1. Create the repository and upload the files

1. Create a **public** GitHub repository (public repositories get unlimited Actions minutes; private ones have a monthly free quota).
2. Upload every file from this project, **keeping the folder structure and the hidden `.github` folder** (the seed files in `data/` let the map load before the first run).
   * **Computer, command line:**
     ```bash
     unzip myanmar-hazard-monitor.zip -d myanmar-hazard-monitor && cd myanmar-hazard-monitor
     git init -b main && git add -A && git commit -m "Initial commit"
     git remote add origin https://github.com/<user>/<repo>.git
     git push -u origin main
     ```
     When pushing over HTTPS, a personal access token needs the `workflow` scope, because the commit contains files under `.github/workflows/`.
   * **Computer, browser only:** unzip, open the new repository, **Add file → Upload files** and drag in the files and folders. Hidden folders are not shown by default in Finder (press `Cmd+Shift+.`) and Windows Explorer (View → Show → Hidden items).
   * **Phone:** the mobile browser can upload single files (**Add file → Upload files**), which is enough for `demo.html`. Uploading the whole project is easier from a computer.
3. Settings → **Actions → General → Workflow permissions** → choose **Read and write permissions** → Save.
4. Keep the key out of the repository: `EE_SERVICE_ACCOUNT_KEY` belongs only in repository secrets. `.gitignore` already excludes `ee-key.json`.

### 2. Earth Engine access (the `EE_SERVICE_ACCOUNT_KEY` secret)

1. In the [Google Cloud console](https://console.cloud.google.com/) create (or pick) a project and enable the **Earth Engine API**.
2. Register the project for Earth Engine at <https://code.earthengine.google.com/register>. Check the current Earth Engine terms and quotas for non-commercial use; this project is intended for humanitarian / research use.
3. Create a **service account** (IAM & Admin → Service Accounts) and grant it the roles **Earth Engine Resource Viewer** and **Service Usage Consumer** on the project.
4. Open the service account → **Keys → Add key → Create new key → JSON**. A key file downloads. Never commit it.
5. In the GitHub repository: Settings → **Secrets and variables → Actions → New repository secret**
   * Name: `EE_SERVICE_ACCOUNT_KEY`
   * Value: paste the **entire contents** of the JSON file (base64-encoded JSON also works).
6. Optional: under the **Variables** tab add `EE_PROJECT` with your Cloud project id. If omitted, the id inside the key file is used.

### 3. Run the pipeline once

Actions tab → **Update hazard data** → **Run workflow**. Tick *force* if you want to ignore the "no new data" shortcut. The first run can take a while (all of Myanmar is processed in tiles). Afterwards the workflow commits the new files in `data/`.

### 4. Activate GitHub Pages

Settings → **Pages** → *Build and deployment* → Source **Deploy from a branch** → Branch `main`, folder `/ (root)` → Save. The site appears at `https://<user>.github.io/<repo>/`.

The web app reads the data from `raw.githubusercontent.com` first (so it is fresh without waiting for a Pages rebuild) and falls back to the copy served by Pages. Large GeoJSON files are cached in the browser (IndexedDB) and only re-downloaded when their hash in `metadata.json` changes.

### Troubleshooting a blank page, oversized heading, or `app.js` loading error

1. In **Settings → Pages**, confirm **Deploy from a branch**, branch `main`, folder `/(root)`. If Pages is configured for `/docs`, another branch, or a separate Actions artifact, the site can display an older `index.html` while `js/app.js` is missing.
2. At the repository root, make sure `index.html`, `css/style.css`, and `js/app.js` are present at exactly those paths. Do not upload the ZIP itself as a file and do not leave the project nested one folder deep. Upload/extract the ZIP contents.
3. After committing the files, wait for the Pages deployment to finish, then hard-refresh Firefox with **Ctrl+Shift+R**. The local CSS and JavaScript links include a version query so the browser requests the refreshed files.
4. In DevTools → **Network**, reload and open `js/app.js`. It should return **200** with JavaScript content, not **404** or an HTML error page. If it still fails, the problem is the Pages source/path rather than JavaScript syntax.
5. The starting `data/` files intentionally contain no detected hazard polygons or live events. Real layers appear only after **Actions → Update hazard data → Run workflow** completes successfully; that workflow also requires the Earth Engine service-account secret described above.

## How it works

### Flood layer (Sentinel-1 SAR, VV + VH)

1. Sentinel-1 IW GRD from Earth Engine (already noise-corrected, calibrated and terrain-corrected, in dB); incidence-angle edges are masked.
2. Median composite of the last 12 days versus a median **dry-season baseline (January–March)** of the most recent completed dry season.
3. Adaptive **Lee** speckle filter on both composites.
4. A pixel is flooded when: VV dropped by 3 dB or more, VV and VH are low enough to be open water, the pixel was not water in the baseline, the terrain slope is 5° or less (SRTM 30 m, radar-shadow guard), and it is not permanent water (JRC Global Surface Water occurrence ≥ 75 %).
5. Tiny patches are removed, the mask is vectorised in tiles, merged, **Douglas-Peucker simplified (tolerance 0.001°)** and split by township. Files are kept under 5 MB: if needed, the pipeline simplifies more and finally drops the smallest polygons (recorded in `metadata.json`).

### Landslide layer

A dynamic index (not a trained model): **7-day antecedent rainfall** × **mean slope ≥ 20°** on a 250 m grid.

| Class | Rule (any one) |
|---|---|
| High | rain ≥ 150 mm and slope ≥ 30°; rain ≥ 250 mm and slope ≥ 20° |
| Moderate | rain ≥ 100 mm and slope ≥ 25°; rain ≥ 150 mm and slope ≥ 20°; rain ≥ 75 mm and slope ≥ 35° |
| Low | rain ≥ 50 mm and slope ≥ 20° |

Rainfall comes from **GPM IMERG V07**. If Earth Engine's copy is more than 6 days old, the pipeline falls back to CHIRPS, then ERA5-Land, and records the source and age in `summary.json`; the web app warns when the rainfall is stale. NASA LHASA 2.0 is **not** integrated, because this build uses the dynamic-index option the brief allows.

### Fault tolerance

* No new Sentinel-1 scene (or no new rainfall data): the previous GeoJSON is kept and only timestamps are updated in `metadata.json` / `summary.json`.
* Earth Engine errors on a tile are retried, then the tile is split into smaller ones. If more than 20 % of the country fails, the previous layer is kept and the run is marked as an error (the job turns red so you notice).
* The workflow commits only when files changed, never runs twice at once, and retries the push.

## Public information and weather-risk screening

The separate `Refresh live disaster events` workflow runs every 30 minutes: it retrieves the USGS earthquake catalog, GDACS event feed, and Open-Meteo 3-day forecast screening for 20 Myanmar locations; NASA FIRMS active-fire detections are enabled only if the optional `NASA_FIRMS_MAP_KEY` secret is configured. Weather screening markers are forecast-based and use transparent app thresholds; they are not official DMH warnings, calibrated township impact forecasts, or proof that flooding will occur. It commits only meaningful event/source-health changes, avoiding timestamp-only commits. Observed/reported events and forecast-screening notices appear as map markers and in the mobile-first Live Alerts panel. Forecast notices include the forecast date, source, screening level and threshold explanation. An empty event feed is never presented as proof of safety.

The scheduled workflow independently runs `scripts/fetch_public_info.py`, so this part can still refresh when Earth Engine is not configured or a satellite task fails. It writes `data/public_info.json` and keeps the last successful result for a source if that source temporarily fails.

* **Past rain radar:** RainViewer's past radar frames can be toggled on the map. The API currently exposes past radar only (not a future radar forecast), may have local coverage gaps, has a maximum native zoom of 7, and its free API is for personal/educational/small community use. Visible attribution is included.
* **7-day city forecasts:** Open-Meteo forecast data for 15 Myanmar cities. The interface shows daily maximum temperature, rainfall, UV index, and simple screening labels.
* **Weather/health precautions:** transparent threshold rules flag possible heat exposure (33/35/40 °C), UV exposure (6/8/11), heavy rainfall totals (25/50/100 mm/day), and strong wind (50/70 km/h). These are pragmatic screening thresholds chosen for this app, **not official Myanmar warning thresholds and not a clinical health forecast**. The site displays general safety advice, not a disease diagnosis.
* **DMH bulletins:** headline links are collected from the official Department of Meteorology and Hydrology homepage. Always open the original bulletin to confirm its issue time, affected locations and instructions.
* **El Niño / ENSO:** the latest available NOAA Climate Prediction Center discussion is parsed for the alert status, issue date and synopsis. ENSO status is global climate context; it is not a precise local forecast for a Myanmar township.
* **Health information:** recent health-emergency headlines are collected from the WHO South-East Asia source page. These are source links, **not automatically confirmed local outbreak alerts**. No disease outbreak should be inferred from the weather forecast.
* **Earthquakes:** the USGS monthly GeoJSON feed is filtered to a broad Myanmar bounding box and magnitude 2.5+. The feed is not guaranteed to include every small or locally reported event.

Sources: [Open-Meteo forecast documentation](https://open-meteo.com/en/docs), [Open-Meteo Flood API documentation](https://open-meteo.com/en/docs/flood-api), [Myanmar DMH](https://www.moezala.gov.mm/index.php/en), [NOAA CPC ENSO discussion](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml), [WHO South-East Asia emergencies](https://www.who.int/southeastasia/outbreaks-and-emergencies), and [USGS earthquake feed](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson). Review each provider's current terms before commercial use; this starter project does not grant rights to third-party data.

**Important:** before the scheduled workflow has run successfully, the starter `public_info.json` intentionally reports `unavailable` rather than pretending the data was fetched. A failed source check is shown in the UI and its last-successful timestamp is retained.

## Run the site without Python on your computer

For local browser testing, open the project folder in VS Code and use the **Live Server** extension (right-click `index.html` → **Open with Live Server**). Do not open `index.html` via `file://` when you want to fetch JSON data, and do not open a ZIP directly in the browser. The app tries three Leaflet CDNs with Subresource Integrity; an old same-origin `/sw.js` service worker from earlier versions is unregistered once so it cannot keep replaying blocked/empty CDN responses. Map tiles, fonts and live source refreshes still require a working internet connection.

## Data files

| File | Content |
|---|---|
| `flood_zones.geojson` | polygons with `township`, `state_region`, `state_region_my`, `area_ha` |
| `landslide_zones.geojson` | same, plus `hazard` (High / Moderate / Low) and `hazard_code` (3 / 2 / 1) |
| `summary.json` | totals, top townships, satellite and rainfall timestamps (feeds the metric cards) |
| `metadata.json` | run status per layer, timestamps, content hashes, parameters used |
| `river_forecast.json` | GloFAS discharge forecast points and threshold estimates; empty until a successful API run |
| `public_info.json` | city forecasts, DMH/WHO links, NOAA ENSO status, USGS earthquake links and source-check status |
| `disaster_events.json` | observed/reported events plus clearly labelled 3-day weather-risk screening notices; refreshes every 30 minutes when GitHub Actions is enabled |

Township names come from [geoBoundaries](https://www.geoboundaries.org/) (CC BY 4.0). If that is unreachable, FAO GAUL districts are used and the popups say "District". Names are in English; state/region names also have Myanmar labels.

## Tests

Before publishing, the GitHub Checks workflow runs Python syntax checks, offline self-tests for the flood/landslide geometry processing, river discharge threshold maths, and public-data parsing/risk thresholds, JavaScript syntax checks, local asset checks, JSON validation and a demo-page build. These tests do not authenticate to Earth Engine or prove that live APIs are reachable. A successful live data run still requires network access and the configured credentials described above.

Local offline tests (only if Python is already installed) are:

```bash
python scripts/generate_hazard_data.py --selftest
python scripts/fetch_river_forecast.py --selftest
python scripts/fetch_public_info.py --selftest
python scripts/fetch_disaster_events.py --selftest
```

## Optional: keep the repository small

Two commits a day of up to 10 MB of GeoJSON grow the Git history by gigabytes per year. To avoid that, add a repository **variable** `DATA_BRANCH` (for example `data`). The workflow then force-pushes each result as a single commit to that branch instead of committing to `main`. After that, in `js/app.js` set `branch: 'data'` and `dataPath: ''` in `CONFIG`. In this mode, GitHub Pages no longer serves the data, so the web app reads it from `raw.githubusercontent.com`.

## Tuning

Environment variables (set them in the workflow's `env:`) override the defaults in the script, for example `DIFF_THRESHOLD_DB`, `WATER_VV_DB`, `WATER_VH_DB`, `JRC_PERMANENT_OCCURRENCE`, `S1_LOOKBACK_DAYS`, `FLOOD_SCALE`, `FILTER_SCALE`, `EE_WORKERS`, `FLOOD_TILE_DEG`. The landslide thresholds are in `LS_RULES` in the script.

## Devices and browsers

The page is responsive (phone, tablet, desktop), works with touch gestures and with keyboard and mouse (Esc closes the layer panel), and follows the system light/dark setting. It targets current versions of Chrome, Edge, Firefox and Safari (iOS 15.4+ / macOS 12+ recommended). It can be added to a phone's home screen (the manifest and icons are included) but it is not an offline app: there is no service worker, so it needs a connection to show tiles and data. Myanmar text uses Pyidaungsu if installed, otherwise Noto Sans Myanmar from Google Fonts. If Google Fonts is blocked on a network, the system's Myanmar font is used.

## Checks on GitHub

`ci.yml` runs on every push and pull request: Python syntax, three offline self-tests, JavaScript syntax, local asset existence, JSON validity and the demo build. The data commits made by the pipeline do not trigger it.

## Local checks

The website itself does not require Python on your computer: use VS Code + Live Server as described above. Python is only needed if you personally want to run the data pipeline or offline tests outside GitHub Actions. Those tests do not require Earth Engine credentials.

## Known limitations

* **Calibrate before relying on it.** The 3 dB / −15 dB / −22 dB flood thresholds and the landslide rainfall/slope thresholds are literature-style defaults. Validate them against known 2024–2025 events and tune.
* Flooded hillside valleys steeper than 5° are excluded by design; flooded vegetation and urban flooding are under-detected by C-band SAR.
* Baseline and recent composites mix orbits, which adds some backscatter noise.
* The Earth Engine parts of the pipeline could not be run end-to-end where this code was written (no Earth Engine account there). Run the workflow manually once and read the log before trusting the output.
* The Burmese interface text should be reviewed by a native speaker.
* GitHub disables scheduled workflows in inactive public repositories after 60 days. The workflow re-enables itself on every run (best effort); if it stops, re-enable it in the Actions tab.

## Credits and licences

Copernicus Sentinel-1 data; JRC Global Surface Water; NASA/USGS SRTM; NASA GPM IMERG; CHIRPS; ERA5-Land; geoBoundaries; map data © OpenStreetMap contributors, HOT tiles by OSM France, imagery © Esri, labels © CARTO. Check each provider's usage terms, especially for the public tile servers.


## Added in the latest version

| What | Where | Notes |
|---|---|---|
| OpenStreetMap-only base map, everything outside Myanmar hidden | `js/app.js` (`addCountryMask`) | The mask uses `data/ref/myanmar_outline.geojson`. |
| Township names in Burmese | `data/ref/admin3_mmr.geojson` | Built from the boundary files you supplied (valid on 2024-02-15). The pipeline uses this file first and only falls back to geoBoundaries if it is missing. Check the licence and credit of those boundary files before you publish. |
| "Previously flooded areas" layer | `data/flood_prone.geojson`, `data/flood_prone_stats.json` | Built from `myanmar-admin1-flood.csv`. The CSV has no source or date, and repeated rows are read as the number of floods. That reading is an assumption. |
| River flood forecast (30 days) | `scripts/fetch_river_forecast.py` | GloFAS through Open-Meteo. Free tier is for non-commercial use. Needs no Earth Engine key. |
| Steep-terrain layer | `run_susceptibility` in `scripts/generate_hazard_data.py` | Mean SRTM slope only. Built once, then kept. |

Rebuild the reference data (only when your source files change):

```bash
pip install shapely numpy pandas rasterio
python scripts/build_reference_data.py --geojson-dir <folder with mmr_admin0.geojson and mmr_admin3.geojson> --flood-csv <myanmar-admin1-flood.csv>
```

### Opening the site from a local folder

Double-clicking `index.html` works: the data is read from `data/js/mapdata.js` (rebuild it with `python scripts/make_simple_map_data.py` after the data changes). The base map is OSM France "HOT" (OpenStreetMap data), which also loads from a local file. The layer panel only lists layers that have data, so the satellite, landslide and river layers appear once the pipeline has produced them. Your own data (flood-prone areas, state and township outlines) can be switched on and off right away.


## Troubleshooting: map/CDN loading errors

If the browser console shows `L is not defined`, Leaflet failed to load; this is usually a blocked CDN request or a stale Service Worker, not a problem with the GeoJSON data. This release includes a safer root `sw.js` that does not intercept third-party CDN requests.

For a local development server (`http://localhost:8000` or `http://127.0.0.1:8000`), if the old errors persist:
1. Open the site in Firefox and press **F12**.
2. Open **Storage** (or **Application** in Chromium) → **Service Workers**.
3. Unregister the old worker for that local origin, then clear that origin's site data/cache.
4. Stop and restart `python -m http.server 8000`, then hard-reload with **Ctrl+Shift+R**.
5. Make sure the browser can reach `https://unpkg.com` and `https://fonts.googleapis.com`. Myanmar and Latin system-font fallbacks remain available if Google Fonts cannot load.

The map still needs the Leaflet library and internet access for OpenStreetMap tiles. Do not treat a successful page load as confirmation that hazard data is current; check the data timestamp and official local alerts.
