#!/usr/bin/env python3
"""
Step 5: Export results to various formats.

- CSV (for spreadsheet analysis)
- GeoJSON (for web mapping / Mapbox)
- GeoPackage (for QGIS)
- Per-county GeoJSON files
"""
import geopandas as gpd
import pandas as pd
import json

import config
from utils import ensure_dirs, print_header


def load_ranked_results():
    """Load ranked results from Step 4."""
    path = config.RESULTS_DIR / "ranked_opportunities.gpkg"
    if not path.exists():
        print("⚠  Ranked results not found! Run 04_rank_results.py first.")
        return None
    return gpd.read_file(path)


def export_csv(gdf):
    """Export to CSV (no geometry, just coordinates and attributes)."""
    print("  Exporting CSV...")
    
    # Drop geometry column, use lat/lon instead
    df = gdf.drop(columns=['geometry']).copy()
    
    # Reorder columns for readability
    priority_cols = [
        'score', 'gap_ft', 'buffer_intersects', 'dist_centerline_ft',
        'land_category', 'land_owner', 'land_name', 'land_area_acres',
        'road_name', 'county', 'latitude', 'longitude',
        'gap_score', 'land_score', 'size_score', 'isolation_score',
    ]
    other_cols = [c for c in df.columns if c not in priority_cols]
    col_order = [c for c in priority_cols if c in df.columns] + other_cols
    df = df[col_order]
    
    outpath = config.RESULTS_DIR / "opportunities.csv"
    df.to_csv(outpath, index=False)
    print(f"    Saved: {outpath} ({len(df):,} rows)")


def export_geojson(gdf):
    """Export to GeoJSON for web mapping."""
    print("  Exporting GeoJSON...")
    
    # Full statewide file
    outpath = config.RESULTS_DIR / "opportunities.geojson"
    gdf.to_file(outpath, driver="GeoJSON")
    print(f"    Saved: {outpath}")
    
    # Top opportunities only (lighter file for quick viewing)
    top200 = gdf.head(200)
    outpath_top = config.RESULTS_DIR / "top_200_opportunities.geojson"
    top200.to_file(outpath_top, driver="GeoJSON")
    print(f"    Saved: {outpath_top}")
    
    # Near-misses only (the actionable ones)
    near_miss = gdf[
        (gdf['buffer_intersects'] == False) & 
        (gdf['gap_ft'] <= config.NEAR_MISS_THRESHOLD_FT)
    ]
    if len(near_miss) > 0:
        outpath_near = config.RESULTS_DIR / "near_misses.geojson"
        near_miss.to_file(outpath_near, driver="GeoJSON")
        print(f"    Saved: {outpath_near} ({len(near_miss):,} near-misses)")
    
    # Confirmed access points
    confirmed = gdf[gdf['buffer_intersects'] == True]
    if len(confirmed) > 0:
        outpath_conf = config.RESULTS_DIR / "confirmed_access.geojson"
        confirmed.to_file(outpath_conf, driver="GeoJSON")
        print(f"    Saved: {outpath_conf} ({len(confirmed):,} confirmed)")


def export_by_county(gdf):
    """Export per-county GeoJSON files."""
    print("  Exporting by county...")
    
    if 'county' not in gdf.columns:
        print("    ⚠  No county field, skipping per-county export")
        return
    
    county_dir = config.RESULTS_DIR / "county_summaries"
    county_dir.mkdir(exist_ok=True)
    
    for county in gdf['county'].dropna().unique():
        county_data = gdf[gdf['county'] == county]
        if len(county_data) > 0:
            safe_name = county.replace(' ', '_').replace('/', '_').lower()
            outpath = county_dir / f"{safe_name}.geojson"
            county_data.to_file(outpath, driver="GeoJSON")
    
    n_counties = gdf['county'].nunique()
    print(f"    Saved {n_counties} county files to: {county_dir}")


def export_gpkg(gdf):
    """Export to GeoPackage (native QGIS format)."""
    print("  Exporting GeoPackage...")
    outpath = config.RESULTS_DIR / "opportunities.gpkg"
    gdf.to_file(outpath, driver="GPKG")
    print(f"    Saved: {outpath}")


def print_final_summary(gdf):
    """Print final summary for the user."""
    confirmed = gdf[gdf['buffer_intersects'] == True]
    near_miss = gdf[
        (gdf['buffer_intersects'] == False) & 
        (gdf['gap_ft'] <= config.NEAR_MISS_THRESHOLD_FT)
    ]
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║          MONTANA PUBLIC LAND ACCESS ANALYSIS            ║
║                    FINAL RESULTS                        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Total opportunities found:  {len(gdf):>6,}                   ║
║  Confirmed access points:    {len(confirmed):>6,}                   ║
║  Near-miss opportunities:    {len(near_miss):>6,}                   ║
║                                                          ║
║  Gap < 10 ft:  {len(gdf[gdf['gap_ft'] < 10]):>6,}  (strong cases)               ║
║  Gap < 25 ft:  {len(gdf[gdf['gap_ft'] < 25]):>6,}  (petition research)          ║
║  Gap < 50 ft:  {len(gdf[gdf['gap_ft'] < 50]):>6,}  (easement purchase)          ║
║  Gap < 100 ft: {len(gdf[gdf['gap_ft'] < 100]):>6,}  (advocacy targets)           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

Output files in: {config.RESULTS_DIR}
  - opportunities.csv        (spreadsheet analysis)
  - opportunities.geojson    (web mapping)
  - opportunities.gpkg       (QGIS)
  - top_200_opportunities.geojson
  - near_misses.geojson
  - confirmed_access.geojson
  - county_summaries/        (per-county files)

NEXT STEPS:
  1. Open opportunities.gpkg in QGIS to visualize
  2. Review top-scoring near-misses for road petition research
  3. For gaps < 25ft, investigate whether the surveyed road 
     centerline differs from the physical road
  4. For BLM/State parcels with high scores, check if they're
     truly isolated (no other access routes)
    """)


def main():
    ensure_dirs()
    
    print_header("EXPORTING RESULTS")
    
    gdf = load_ranked_results()
    if gdf is None:
        return
    
    print(f"  Exporting {len(gdf):,} opportunities...\n")
    
    if config.EXPORT_CSV:
        export_csv(gdf)
    
    if config.EXPORT_GEOJSON:
        export_geojson(gdf)
    
    if config.EXPORT_GPKG:
        export_gpkg(gdf)
    
    export_by_county(gdf)
    
    print_final_summary(gdf)


if __name__ == "__main__":
    main()
