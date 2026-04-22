"""
NRW UV Hazard Index
===================
Daily UV index forecast for all municipalities in North Rhine-Westphalia (NRW),
classified according to the WHO UV index scale.

Data source : DWD OpenData – Health Forecasts (ICON-EU-Nest, GRIB2)
Classification: WHO UV index scale (1–11+)
"""

import json
import logging
import re
import sys
import datetime
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xarray as xr
from scipy.spatial import cKDTree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT      = Path(__file__).parent
CSV_PATH       = REPO_ROOT / "data" / "municipality_nrw.csv"
OUTPUT_JSON    = REPO_ROOT / "output" / "uvi_forecast_nrw.json"
OUTPUT_GEOJSON = REPO_ROOT / "output" / "uvi_forecast_nrw.geojson"
GEOJSON_SRC    = REPO_ROOT / "municipality_nrw.geojson"
README_FILE    = REPO_ROOT / "README.md"
TEMPLATE_FILE  = REPO_ROOT / "README_template.md"

BASE_URL = "https://opendata.dwd.de/climate_environment/health/forecasts/"
TOP_N    = 10

# ---------------------------------------------------------------------------
# UV Index classification (WHO scale)
# ---------------------------------------------------------------------------
# (upper bound inclusive, label, risk, hex colour)
UV_CLASSES = [
    ( 2, "Low",      "Low",      "#339C23"),
    ( 3, "Moderate", "Moderate", "#9CC401"),
    ( 4, "Moderate", "Moderate", "#FFF200"),
    ( 5, "Moderate", "Moderate", "#FED300"),
    ( 6, "Moderate", "Moderate", "#F7AF00"),
    ( 7, "High",     "High",     "#EF8300"),
    ( 8, "High",     "High",     "#EA6003"),
    ( 9, "Very high","Very high","#D90017"),
    (10, "Very high","Very high","#FF009A"),
    (11, "Very high","Very high","#B64BFF"),
    (99, "Extreme",  "Extreme",  "#9A8DFF"),
]

# Compact legend for README (one row per risk group)
LEGEND_GROUPS = [
    # (uvi_range, label, risk, hex)
    ("1–2",  "Low",      "Low",      "#339C23"),
    ("3–5",  "Moderate", "Moderate", "#FED300"),
    ("6–7",  "High",     "High",     "#EF8300"),
    ("8–10", "Very high","Very high","#D90017"),
    ("11+",  "Extreme",  "Extreme",  "#9A8DFF"),
]


def classify(uvi: float) -> dict:
    """Return label, risk and hex colour for a UV index value."""
    val = round(float(uvi))
    for upper, label, risk, hex_c in UV_CLASSES:
        if val <= upper:
            return {"uvi_class": label, "risk": risk, "bg_color": hex_c}
    return {"uvi_class": "Extreme", "risk": "Extreme", "bg_color": "#9A8DFF"}


def badge(hex_c: str) -> str:
    c = hex_c.lstrip("#")
    return f"![](https://placehold.co/14x14/{c}/{c}.png)"


def uvi_icon(uvi: float) -> str:
    v = round(float(uvi))
    if v <= 2:  return "🟢"
    if v <= 5:  return "🟡"
    if v <= 7:  return "🟠"
    if v <= 10: return "🔴"
    return "🟣"

# ---------------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------------
def get_latest_uvi_url() -> str:
    log.info("Scanning DWD directory: %s", BASE_URL)
    r = requests.get(BASE_URL, timeout=30)
    r.raise_for_status()
    files = re.findall(r'href="([^"]*icreu_uvi[^"]*\.(?:bin|grib2))"', r.text)
    if not files:
        raise RuntimeError("No UVI files found in DWD directory.")
    files.sort()
    url = BASE_URL + files[-1]
    log.info("Latest file: %s", files[-1])
    return url


def parse_filename(url: str):
    fname = url.split("/")[-1]
    run_dt = valid_dt = None
    m = re.search(r"EDZW_(\d{14})", fname)
    if m:
        run_dt = datetime.datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(
            tzinfo=datetime.timezone.utc)
    m = re.search(r"_(\d{10})_HPC", fname)
    if m:
        valid_dt = datetime.datetime.strptime("20" + m.group(1), "%Y%m%d%H%M").replace(
            tzinfo=datetime.timezone.utc)
    return run_dt, valid_dt

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def download(url: str, dest: Path) -> None:
    log.info("Downloading …")
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        dest.write_bytes(b"".join(r.iter_content(65536)))
    log.info("  → %.1f MB saved", dest.stat().st_size / 1e6)

# ---------------------------------------------------------------------------
# GRIB2
# ---------------------------------------------------------------------------
def open_grib(path: Path) -> xr.Dataset:
    try:
        return xr.open_dataset(str(path), engine="cfgrib",
                               backend_kwargs={"indexpath": ""})
    except Exception as e:
        log.warning("open_dataset failed (%s) – trying open_datasets", e)
    import cfgrib
    datasets = cfgrib.open_datasets(str(path), backend_kwargs={"indexpath": ""})
    if not datasets:
        raise RuntimeError("Cannot read GRIB2 file.")
    log.info("open_datasets: %d message(s)", len(datasets))
    return datasets[0]


def find_var(ds: xr.Dataset) -> str:
    # Known DWD variable names for UV index
    for c in ("DUVRS", "UVI", "uvi", "duvrs", "unknown"):
        if c in ds.data_vars:
            return c
    first = list(ds.data_vars)[0]
    log.warning("Unknown variable name – using '%s'. Available: %s",
                first, list(ds.data_vars))
    return first

# ---------------------------------------------------------------------------
# Vectorised processing via KD-Tree
# ---------------------------------------------------------------------------
def process(ds: xr.Dataset, df: pd.DataFrame,
            dates: dict[str, datetime.date]) -> list[dict]:
    var = find_var(ds)
    log.info("Using variable '%s'", var)

    # Build KD-Tree
    lat_v = ds.latitude.values
    lon_v = ds.longitude.values
    if lat_v.ndim == 1 and lon_v.ndim == 1:
        lon_2d, lat_2d = np.meshgrid(lon_v, lat_v)
        grid_lat = lat_2d.ravel()
        grid_lon = lon_2d.ravel()
    else:
        grid_lat = lat_v.ravel()
        grid_lon = lon_v.ravel()

    tree = cKDTree(np.column_stack([grid_lat, grid_lon]))
    _, nn_idx = tree.query(df[["lat", "lon"]].values)
    log.info("KD-Tree: %d grid points, %d municipalities", len(grid_lat), len(df))

    # Time axis
    tc = next((c for c in ("valid_time", "time") if c in ds.coords), None)
    if tc is None:
        log.error("No time coordinate found.")
        sys.exit(1)
    times = pd.to_datetime(ds[tc].values)
    is_scalar = times.ndim == 0

    # Flatten to (time × grid)
    raw = ds[var].values
    if is_scalar:
        flat  = raw.ravel()[np.newaxis, :]
        times = np.array([times])
    elif raw.ndim == 3:
        flat = raw.reshape(raw.shape[0], -1)
    elif raw.ndim == 2:
        flat = raw if raw.shape[0] == len(times) else raw.T
    else:
        flat = raw.reshape(1, -1)
    log.info("Data shape: %s", flat.shape)

    # For UV index: use daily MAXIMUM (peak UV at solar noon)
    date_masks = {k: np.array([t.date() == d for t in times])
                  for k, d in dates.items()}

    out = []
    for i, row in df.iterrows():
        gi = nn_idx[i]
        forecasts = {}
        for key, mask in date_masks.items():
            if not mask.any():
                forecasts[key] = None
                continue
            vals = flat[mask, gi]
            vals = vals[~np.isnan(vals)]
            if len(vals) == 0:
                forecasts[key] = None
                continue
            peak = float(np.max(vals))
            forecasts[key] = {"uvi_max": round(peak, 1), **classify(peak)}
        out.append({"name": row["name"], "lat": row["lat"],
                    "lon": row["lon"], "forecasts": forecasts})

    log.info("%d municipalities processed", len(out))
    return out

# ---------------------------------------------------------------------------
# GeoJSON export (spatial join)
# ---------------------------------------------------------------------------
def export_geojson(results: list[dict], dates: dict) -> None:
    import geopandas as gpd
    from shapely.geometry import Point

    if not GEOJSON_SRC.exists():
        log.warning("municipality_nrw.geojson not found – skipping GeoJSON export")
        return

    poly_gdf = gpd.read_file(str(GEOJSON_SRC))
    if poly_gdf.crs is None:
        poly_gdf = poly_gdf.set_crs("EPSG:4326")
    else:
        poly_gdf = poly_gdf.to_crs("EPSG:4326")
    log.info("GeoJSON properties: %s", list(poly_gdf.columns))

    rows = []
    for r in results:
        today = (r["forecasts"].get("today") or {})
        rows.append({
            "csv_name":  r["name"],
            "uvi_max":   today.get("uvi_max"),
            "uvi_class": today.get("uvi_class"),
            "risk":      today.get("risk"),
            "bg_color":  today.get("bg_color"),
            "forecast_today":        json.dumps(r["forecasts"].get("today"),
                                                ensure_ascii=False),
            "forecast_tomorrow":     json.dumps(r["forecasts"].get("tomorrow"),
                                                ensure_ascii=False),
            "forecast_day_after":    json.dumps(r["forecasts"].get("day_after_tomorrow"),
                                                ensure_ascii=False),
            "geometry": Point(r["lon"], r["lat"]),
        })
    pts_gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")

    joined = gpd.sjoin(poly_gdf, pts_gdf, how="left", predicate="contains")
    matched = joined["uvi_max"].notna().sum()
    log.info("Spatial join: %d/%d matched", matched, len(joined))

    if matched == 0:
        log.warning("No 'contains' matches – trying nearest join")
        joined = gpd.sjoin_nearest(poly_gdf, pts_gdf, how="left", max_distance=5000)
        matched = joined["uvi_max"].notna().sum()
        log.info("Nearest join: %d/%d matched", matched, len(joined))

    for drop_col in ("index_right", "index_left"):
        if drop_col in joined.columns:
            joined = joined.drop(columns=[drop_col])

    OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    joined.to_file(str(OUTPUT_GEOJSON), driver="GeoJSON")
    log.info("GeoJSON saved: %s  (%d features, %d with data)",
             OUTPUT_GEOJSON, len(joined), matched)

# ---------------------------------------------------------------------------
# README table
# ---------------------------------------------------------------------------
def build_table(results: list[dict], dates: dict,
                run_dt: datetime.datetime) -> str:
    import time
    top = sorted(
        results,
        key=lambda r: -(r["forecasts"].get("today") or {}).get("uvi_max", -1)
    )[:TOP_N]

    def cell(d):
        if d is None: return "–"
        return f"{badge(d['bg_color'])} **{d['uvi_max']:.0f}** · {d['uvi_class']}"

    cache_bust = int(time.time())
    repo_url   = "https://github.com/umweltinformationssysteme/NRW-uv-hazard-index"
    map_url    = f"{repo_url}/raw/main/output/uvi-map-nrw-today.jpg?{cache_bust}"
    map_link   = f"{repo_url}/blob/main/output/uvi-map-nrw-today.jpg"

    run_str  = run_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = dates["today"].strftime("%Y-%m-%d")
    d_h = dates["today"].strftime("%Y-%m-%d")
    d_m = dates["tomorrow"].strftime("%Y-%m-%d")
    d_u = dates["day_after_tomorrow"].strftime("%Y-%m-%d")

    lines = [
        "<!-- UVI_TABLE_START -->",
        "",
        f"[![NRW UV Hazard Map]({map_url})]({map_link})",
        "",
        "---",
        "",
        f"## Top 10 — Highest UV Index Today ({date_str})",
        "",
        f"*Forecast base: {run_dt.strftime('%Y-%m-%d %H:%M')} UTC · Generated: {run_str}*",
        "",
        f"|   | Municipality | Today ({d_h}) | Tomorrow ({d_m}) | Day after ({d_u}) | Risk |",
        "|:---:|:---|:---|:---|:---|:---|",
    ]
    for i, r in enumerate(top, 1):
        fh = r["forecasts"].get("today")
        fm = r["forecasts"].get("tomorrow")
        fu = r["forecasts"].get("day_after_tomorrow")
        b_today = badge(fh["bg_color"]) if fh else ""
        risk    = fh["risk"] if fh else "–"
        lines.append(
            f"| {b_today} | **{r['name']}** | {cell(fh)} | {cell(fm)} | {cell(fu)} | {risk} |"
        )

    lines += [
        "",
        "### Colour scale",
        "",
        "| Colour | UV Index | Classification | Risk |",
        "|:------:|:--------:|----------------|------|",
    ]
    for uvi_range, label, risk, hex_c in LEGEND_GROUPS:
        lines.append(f"| {badge(hex_c)} | {uvi_range} | {label} | {risk} |")

    lines += ["", "<!-- UVI_TABLE_END -->"]
    return "\n".join(lines)


def update_readme(table: str) -> None:
    START = "<!-- UVI_TABLE_START -->"
    END   = "<!-- UVI_TABLE_END -->"
    src   = TEMPLATE_FILE if TEMPLATE_FILE.exists() else README_FILE
    base  = src.read_text("utf-8") if src.exists() else "# NRW UV Hazard Index\n\n"
    if START in base and END in base:
        content = base[:base.index(START)] + table + base[base.index(END) + len(END):]
    else:
        content = base.rstrip("\n") + "\n\n" + table + "\n"
    README_FILE.write_text(content, "utf-8")
    log.info("README.md updated")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    try:
        url = get_latest_uvi_url()
    except Exception as e:
        log.error("URL discovery failed: %s", e)
        sys.exit(1)

    run_dt, valid_dt = parse_filename(url)
    log.info("Model run:      %s UTC", run_dt)
    log.info("Validity start: %s UTC", valid_dt)

    ref = (run_dt or datetime.datetime.now(datetime.timezone.utc)).date()
    dates = {
        "today":               ref,
        "tomorrow":            ref + datetime.timedelta(days=1),
        "day_after_tomorrow":  ref + datetime.timedelta(days=2),
    }
    log.info("Forecast dates: %s", dates)

    tmp = Path(tempfile.mktemp(suffix=".grib2"))
    try:
        download(url, tmp)

        log.info("Opening GRIB2 …")
        ds = open_grib(tmp)
        log.info("Variables: %s  |  Coordinates: %s",
                 list(ds.data_vars), list(ds.coords))

        if not CSV_PATH.exists():
            log.error("CSV not found: %s", CSV_PATH)
            sys.exit(1)
        df = pd.read_csv(CSV_PATH)
        log.info("%d municipalities loaded", len(df))

        results = process(ds, df, dates)

        # JSON
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps({
            "generated_at_utc":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model_run_utc":     run_dt.isoformat() if run_dt else None,
            "valid_start_utc":   valid_dt.isoformat() if valid_dt else None,
            "forecast_dates":    {k: v.isoformat() for k, v in dates.items()},
            "data_source":       "DWD OpenData – Health Forecasts (ICON-EU-Nest, GRIB2)",
            "classification":    "WHO UV Index scale",
            "municipalities":    results,
        }, indent=2, ensure_ascii=False), "utf-8")
        log.info("JSON saved: %s", OUTPUT_JSON)

        # GeoJSON
        export_geojson(results, dates)

        # Map
        try:
            from generate_map import render_map
            render_map(dates["today"].strftime("%Y-%m-%d"),
                       (run_dt or datetime.datetime.now(datetime.timezone.utc)).isoformat())
        except Exception:
            import traceback
            log.error("Map rendering failed:\n%s", traceback.format_exc())
            sys.exit(1)

        # README
        update_readme(build_table(
            results, dates,
            run_dt or datetime.datetime.now(datetime.timezone.utc)))

    finally:
        tmp.unlink(missing_ok=True)

    log.info("Done — %d municipalities updated", len(results))


if __name__ == "__main__":
    main()
