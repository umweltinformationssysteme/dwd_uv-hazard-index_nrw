"""
NRW UV Hazard Index – Map Generator
=====================================
Renders a choropleth map of daily peak UV index by municipality for NRW.
Analogous to dwd_heat-health-warning-map_nrw/generate_map.py.

Input:  output/uvi_forecast_nrw.geojson  (written by fetch_uvi.py)
        background.tiff                  (Sentinel-2, same as thermal project)
Output: output/uvi-map-nrw-today.jpg     (1280 × 720 px)
"""

import io
import logging
import os
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image

log = logging.getLogger(__name__)

REPO_ROOT       = Path(__file__).parent
GEOJSON_PATH    = REPO_ROOT / "output" / "uvi_forecast_nrw.geojson"
BACKGROUND_TIFF = REPO_ROOT / "background.tiff"
OUTPUT_MAP      = REPO_ROOT / "output" / "uvi-map-nrw-today.jpg"

IMG_W_PX   = 1280
IMG_H_PX   = 720
NRW_H_FRAC = 680 / 720
DPI        = 100
POLY_ALPHA = 0.78

# ---------------------------------------------------------------------------
# UV Index colour scale (WHO)
# ---------------------------------------------------------------------------
# Same dict-based lookup as fetch_uvi.py – round float to int first
UV_MAP: dict[int, str] = {
    1: "#339C23", 2: "#9CC401", 3: "#FFF200", 4: "#FED300",
    5: "#F7AF00", 6: "#EF8300", 7: "#EA6003", 8: "#D90017",
    9: "#FF009A", 10: "#B64BFF",
}
UV_EXTREME_HEX = "#9A8DFF"  # UVI ≥ 11

LEGEND_GROUPS = [
    ("1–2",  "Low",       "#339C23"),
    ("3–5",  "Moderate",  "#FED300"),
    ("6–7",  "High",      "#EF8300"),
    ("8–10", "Very high", "#D90017"),
    ("11+",  "Extreme",   "#9A8DFF"),
]


def classify_colour(uvi) -> str:
    """Map UV index float → hex colour. Rounds to nearest integer (like fetch_uvi.py)."""
    try:
        if uvi is None: return "#CCCCCC"
        v = float(uvi)
        if np.isnan(v): return "#CCCCCC"
        vi = max(1, int(round(v)))          # 2.9 → 3, 3.4 → 3, 4.5 → 5
        return UV_MAP.get(vi, UV_EXTREME_HEX)
    except (TypeError, ValueError):
        return "#CCCCCC"


def hex_to_rgba(hex_c: str, alpha: float) -> tuple:
    h = hex_c.lstrip("#")
    return int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255, alpha


def compute_map_extent(gdf: gpd.GeoDataFrame):
    b     = gdf.total_bounds
    map_h = (b[3] - b[1]) / NRW_H_FRAC
    map_w = map_h * (IMG_W_PX / IMG_H_PX)
    cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
    return (cx - map_w/2, cx + map_w/2), (cy - map_h/2, cy + map_h/2)


def render_map(date_str: str, run_str: str) -> None:
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"GeoJSON not found: {GEOJSON_PATH}\n"
            "Run fetch_uvi.py first.")
    if not BACKGROUND_TIFF.exists():
        raise FileNotFoundError(f"background.tiff not found: {BACKGROUND_TIFF}")

    # Load GeoJSON
    log.info("Loading GeoJSON: %s", GEOJSON_PATH)
    gdf = gpd.read_file(str(GEOJSON_PATH))
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    if "uvi_max" not in gdf.columns:
        raise ValueError("'uvi_max' column missing – run fetch_uvi.py first.")

    missing = gdf["uvi_max"].isna().sum()
    if missing == len(gdf):
        raise ValueError(f"All {missing} municipalities have uvi_max=null.")
    elif missing:
        log.warning("%d/%d municipalities have no UV data (grey)", missing, len(gdf))
    else:
        log.info("All %d municipalities have UV data", len(gdf))

    gdf["fill_hex"] = gdf["uvi_max"].apply(classify_colour)

    # Open TIFF – reproject GDF to TIFF CRS
    os.environ["GTIFF_SRS_SOURCE"] = "EPSG"
    with rasterio.open(str(BACKGROUND_TIFF)) as src:
        tiff_crs    = src.crs
        tiff_bounds = src.bounds
        tiff_data   = src.read()
        log.info("TIFF: CRS=%s  size=%dx%d", tiff_crs, src.width, src.height)

    gdf_proj = gdf.to_crs(tiff_crs)
    xlim, ylim = compute_map_extent(gdf_proj)

    # Build RGB
    n   = tiff_data.shape[0]
    rgb = np.stack([tiff_data[i] for i in range(min(3,n))]
                   if n >= 3 else [tiff_data[0]]*3, axis=-1)
    if   rgb.dtype == np.uint16: rgb = (rgb/65535.0).clip(0,1)
    elif rgb.dtype == np.uint8:  rgb = (rgb/255.0  ).clip(0,1)
    else:
        lo,hi = rgb.min(), rgb.max()
        rgb = ((rgb-lo)/(hi-lo+1e-9)).clip(0,1)

    # Figure
    fig, ax = plt.subplots(figsize=(IMG_W_PX/DPI, IMG_H_PX/DPI), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_axis_off()

    ax.imshow(rgb,
              extent=[tiff_bounds.left, tiff_bounds.right,
                      tiff_bounds.bottom, tiff_bounds.top],
              origin="upper", aspect="auto", interpolation="bilinear")

    log.info("Drawing %d polygons …", len(gdf_proj))
    for _, row in gdf_proj.iterrows():
        color = hex_to_rgba(row["fill_hex"], POLY_ALPHA)
        gpd.GeoDataFrame([row], crs=gdf_proj.crs).plot(
            ax=ax, color=[color], edgecolor="#44444455", linewidth=0.25)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    # Legend
    handles = []
    for uvi_range, label, hex_c in LEGEND_GROUPS:
        cnt = sum(1 for h in gdf_proj["fill_hex"]
                  if classify_colour(
                      next((u for u,(up,hc) in enumerate(UV_STEPS) if hc==h), None)
                  ) == hex_c) if False else ""  # count omitted for simplicity
        rgba = hex_to_rgba(hex_c, 1.0)
        handles.append(mpatches.Patch(
            facecolor=rgba[:3], edgecolor="#888",
            label=f"UVI {uvi_range}  –  {label}"
        ))

    leg = ax.legend(
        handles=handles,
        loc="lower right",
        bbox_to_anchor=(1260/IMG_W_PX, 10/IMG_H_PX),
        bbox_transform=ax.transAxes,
        fontsize=6.5,
        framealpha=0.88, edgecolor="#bbbbbb", facecolor="#ffffff",
        handlelength=1.2, handleheight=1.0,
        borderpad=0.6, labelspacing=0.35,
        title=f"UV Index · NRW\n{date_str}",
        title_fontsize=7.0,
    )
    leg.get_title().set_fontweight("bold")

    ax.text(0.01, 0.01,
            "Data: Deutscher Wetterdienst (DWD), CC BY 4.0  |  "
            "Background: Sentinel-2  |  Boundaries: BKG",
            transform=ax.transAxes, fontsize=5, color="white", alpha=0.9,
            va="bottom", ha="left",
            bbox=dict(facecolor="black", alpha=0.35, pad=2, edgecolor="none"))

    ax.text(0.015, 0.985, "NRW UV Hazard Index",
            transform=ax.transAxes, fontsize=11, fontweight="bold",
            color="white", va="top", ha="left", zorder=7,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#000000",
                      alpha=0.55, edgecolor="none"))
    ax.text(0.015, 0.915,
            f"Daily peak UV index · {date_str}\n"
            "Source: DWD OpenData · ICON-EU-Nest",
            transform=ax.transAxes, fontsize=5.5, color="#eeeeee",
            va="top", ha="left", zorder=7)

    # Save
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    img = img.resize((IMG_W_PX, IMG_H_PX), Image.LANCZOS)
    OUTPUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUTPUT_MAP), format="JPEG", quality=88, optimize=True)
    log.info("Map saved: %s  (%dx%d px,  %.0f KB)",
             OUTPUT_MAP, img.size[0], img.size[1],
             OUTPUT_MAP.stat().st_size / 1024)


if __name__ == "__main__":
    import datetime
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-8s  %(message)s",
                        datefmt="%H:%M:%S")
    render_map(datetime.date.today().strftime("%Y-%m-%d"),
               datetime.datetime.now(datetime.timezone.utc).isoformat())
