# NRW UV Hazard Index

Daily 3-day UV index forecast for all municipalities in North Rhine-Westphalia (NRW), Germany.  
Data source: [DWD OpenData – Health Forecasts](https://opendata.dwd.de/climate_environment/health/forecasts/) — ICON-EU-Nest, variable `DUVRS` (UV index).

---

<!-- UVI_TABLE_START -->

[![NRW UV Hazard Map](https://github.com/umweltinformationssysteme/NRW-uv-hazard-index/raw/main/output/uvi-map-nrw-today.jpg?1776861549)](https://github.com/umweltinformationssysteme/NRW-uv-hazard-index/blob/main/output/uvi-map-nrw-today.jpg)

---

## Top 10 — Highest UV Index Today (2026-04-22)

*Forecast base: 2026-04-22 04:30 UTC · Generated: 2026-04-22T04:30:12Z*

|   | Municipality | Today (2026-04-22) | Tomorrow (2026-04-23) | Day after (2026-04-24) | Risk |
|:---:|:---|:---|:---|:---|:---|
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Dahlem** | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Monschau** | ![](https://placehold.co/14x14/FED300/FED300.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Simmerath** | ![](https://placehold.co/14x14/FED300/FED300.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Blankenheim** | ![](https://placehold.co/14x14/FED300/FED300.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FFF200/FFF200.png) | **Hellenthal** | ![](https://placehold.co/14x14/FFF200/FFF200.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FFF200/FFF200.png) | **Mechernich** | ![](https://placehold.co/14x14/FFF200/FFF200.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Nettersheim** | ![](https://placehold.co/14x14/FED300/FED300.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FED300/FED300.png) | **Schleiden** | ![](https://placehold.co/14x14/FED300/FED300.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FFF200/FFF200.png) | **Alsdorf** | ![](https://placehold.co/14x14/FFF200/FFF200.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |
| ![](https://placehold.co/14x14/FFF200/FFF200.png) | **Baesweiler** | ![](https://placehold.co/14x14/FFF200/FFF200.png) **4** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | ![](https://placehold.co/14x14/FED300/FED300.png) **5** · Moderate | Moderate |

### Colour scale

| Colour | UV Index | Classification | Risk |
|:------:|:--------:|----------------|------|
| ![](https://placehold.co/14x14/339C23/339C23.png) | 1–2 | Low | Low |
| ![](https://placehold.co/14x14/FED300/FED300.png) | 3–5 | Moderate | Moderate |
| ![](https://placehold.co/14x14/EF8300/EF8300.png) | 6–7 | High | High |
| ![](https://placehold.co/14x14/D90017/D90017.png) | 8–10 | Very high | Very high |
| ![](https://placehold.co/14x14/9A8DFF/9A8DFF.png) | 11+ | Extreme | Extreme |

<!-- UVI_TABLE_END -->

---

## What it does

A GitHub Actions workflow runs every morning at **09:00 UTC**. You can trigger a run at any time via **Actions → NRW UV Hazard Index → Run workflow**. It:

1. Scans the DWD OpenData directory and downloads the latest UV index GRIB2 forecast file (ICON-EU-Nest, `icreu_uvi`).
2. Builds a KD-Tree over the ~905,000 grid points and maps each of the 396 municipality centroids to the nearest grid point.
3. Extracts the **daily peak UV index** for today, tomorrow and the day after tomorrow.
4. Classifies each value according to the WHO UV index scale.
5. Exports a GeoJSON file with forecast attributes attached to each municipality polygon.
6. Renders a choropleth map (`output/uvi-map-nrw-today.jpg`) using the municipality polygons coloured by UV index, overlaid on a Sentinel-2 background.
7. Updates the Top-10 table and the map in this README.
8. Writes full results to `output/uvi_forecast_nrw.json` and pushes everything back to this repository.

---

## Output format

`output/uvi_forecast_nrw.json`

```json
{
  "generated_at_utc": "2026-04-22T09:12:34Z",
  "model_run_utc": "2026-04-22T04:30:12Z",
  "forecast_dates": {
    "today": "2026-04-22",
    "tomorrow": "2026-04-23",
    "day_after_tomorrow": "2026-04-24"
  },
  "data_source": "DWD OpenData – Health Forecasts (ICON-EU-Nest, GRIB2)",
  "classification": "WHO UV Index scale",
  "municipalities": [
    {
      "name": "Köln",
      "lat": 50.938107,
      "lon": 6.957068,
      "forecasts": {
        "today":     { "uvi_max": 6.2, "uvi_class": "High",     "risk": "High",     "bg_color": "#EF8300" },
        "tomorrow":  { "uvi_max": 4.8, "uvi_class": "Moderate", "risk": "Moderate", "bg_color": "#FED300" },
        "day_after_tomorrow": null
      }
    }
  ]
}
```

`output/uvi_forecast_nrw.geojson` — same data merged into municipality polygon geometries.

---

## Repository structure

```
NRW-uv-hazard-index/
├── .github/
│   └── workflows/
│       └── update_uvi.yml               ← GitHub Actions (daily 09:00 UTC)
├── data/
│   └── municipality_nrw.csv            ← municipality centroids (396 entries)
├── output/
│   ├── uvi_forecast_nrw.json           ← forecast data (auto-committed daily)
│   ├── uvi_forecast_nrw.geojson        ← polygon forecast (auto-committed daily)
│   └── uvi-map-nrw-today.jpg           ← choropleth map (auto-committed daily)
├── fetch_uvi.py                        ← GRIB2 download, processing, README update
├── generate_map.py                     ← map rendering (matplotlib + rasterio)
├── municipality_nrw.geojson            ← NRW municipality polygon boundaries (BKG)
├── background.tiff                     ← Sentinel-2 georeferenced background
├── requirements.txt
├── README_template.md                  ← static sections
└── README.md                           ← auto-generated daily
```

---

## Licenses and Data Sources

### 1. UV Index Data
- **Data source:** [DWD OpenData – Health Forecasts](https://opendata.dwd.de/climate_environment/health/forecasts/)
- **Model:** ICON-EU-Nest · Variable: `DUVRS` / `UVI`
- **License:** [DWD Open Data License](https://www.dwd.de/EN/service/copyright/copyright_node.html)
- **Attribution:** *Contains data from Deutscher Wetterdienst (DWD), OpenData.*

### 2. Classification
The UV index classification follows the **WHO UV index scale**. The UV index describes the level of solar UV radiation reaching the Earth's surface. Values above 3 require sun protection measures.

| UV Index | Classification | Recommended protection |
|:--------:|---------------|------------------------|
| 1–2      | Low           | No protection needed |
| 3–5      | Moderate      | Sun protection recommended |
| 6–7      | High          | Sun protection required |
| 8–10     | Very high     | Extra protection required |
| 11+      | Extreme       | Maximum protection, avoid midday sun |

### 3. Administrative Boundaries
- **Data source:** © GeoBasis-DE / BKG (data modified).

### 4. Satellite Background
- **Data source:** Sentinel-2 Quarterly Mosaics True Color Cloudless, via Sentinel Hub
- **License:** [Copernicus Data License](https://scihub.copernicus.eu/twiki/do/view/SciHubWebPortal/TermsConditions)

---

## Notes

- The DWD GRIB2 file is updated once per day (model run ~04:00–05:00 UTC).
- All timestamps are in **UTC**.
- The ICON-EU-Nest grid resolution is approximately **2 × 2 km**.
- `uvi_max` is `null` when no forecast data is available for that day.
- UV index values represent the **daily peak** (around solar noon).
