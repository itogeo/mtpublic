#!/usr/bin/env python3
"""
Step 6: Convert analysis results to WGS84 GeoJSON for Mapbox web map.

Exports three layers:
  1. opportunities.geojson — Point features (access opportunity locations)
  2. roads.geojson — Line features (county road segments near public land)
  3. lands.geojson — ALL public land parcels statewide (polygon features)
"""
import json
import geopandas as gpd
from pathlib import Path

import config
from utils import print_header

CATEGORY_MAP = {
    'US Bureau of Land Management': 'BLM',
    'Montana State Trust Lands': 'STATE',
    'Montana DNRC': 'STATE',
    'US Forest Service': 'USFS',
    'Montana Fish, Wildlife & Parks': 'FWP',
    'US Fish and Wildlife Service': 'USFWS',
    'National Park Service': 'NPS',
    'US Bureau of Reclamation': 'BOR',
    'US Army Corps of Engineers': 'USACE',
    'US Department of Defense': 'DOD',
}


def write_geojson(gdf, output_path, label):
    """Write a GeoDataFrame as compact GeoJSON."""
    geojson = json.loads(gdf.to_json())
    with open(output_path, 'w') as f:
        json.dump(geojson, f, separators=(',', ':'))
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"    {label}: {output_path.name} ({size_mb:.1f} MB, {len(gdf):,} features)")


def export_opportunities(output_dir):
    """Export opportunity points."""
    print("\n  [1/3] Opportunities (points)...")
    input_path = config.RESULTS_DIR / "ranked_opportunities.gpkg"
    if not input_path.exists():
        print(f"    Error: {input_path} not found.")
        return None

    gdf = gpd.read_file(input_path)
    road_idxs = set(gdf['road_idx'].unique())

    gdf = gdf.to_crs(epsg=4326)

    for col in ['score', 'gap_score', 'land_score', 'size_score', 'isolation_score',
                'gap_ft', 'dist_centerline_ft', 'land_area_acres', 'road_length_ft']:
        if col in gdf.columns:
            gdf[col] = gdf[col].round(1)
    for col in ['latitude', 'longitude']:
        if col in gdf.columns:
            gdf[col] = gdf[col].round(6)

    gdf.geometry = gdf.geometry.apply(
        lambda g: type(g)([round(c, 6) for c in g.coords[0]]) if g else g
    )

    write_geojson(gdf, output_dir / "opportunities.geojson", "Points")
    return road_idxs


def export_roads(output_dir, road_idxs):
    """Export matching county road segments as lines."""
    print("\n  [2/3] County roads (lines)...")
    roads_path = config.PREPPED_DIR / "county_roads.gpkg"
    if not roads_path.exists():
        print(f"    Error: {roads_path} not found.")
        return

    roads = gpd.read_file(roads_path)
    matched = roads.loc[roads.index.isin(road_idxs)].copy()
    print(f"    Matched {len(matched):,} of {len(roads):,} road segments")

    matched = matched.to_crs(epsg=4326)
    matched['geometry'] = matched.geometry.simplify(0.0005)
    matched['road_idx'] = matched.index

    write_geojson(matched, output_dir / "roads.geojson", "Roads")


def export_all_lands(output_dir):
    """Export ALL public land parcels statewide."""
    print("\n  [3/3] ALL public lands statewide (polygons)...")
    lands_path = config.PREPPED_DIR / "public_lands.gpkg"
    if not lands_path.exists():
        print(f"    Error: {lands_path} not found.")
        return

    lands = gpd.read_file(lands_path)
    print(f"    Total parcels: {len(lands):,}")

    lands = lands.to_crs(epsg=4326)
    # Simplify for web (~200m tolerance) — keeps shapes recognizable
    lands['geometry'] = lands.geometry.simplify(0.002)
    # Add index for linking to opportunities
    lands['land_idx'] = lands.index

    # Category breakdown
    for cat in sorted(lands['land_category'].unique()):
        count = len(lands[lands['land_category'] == cat])
        print(f"      {cat}: {count:,}")

    write_geojson(lands, output_dir / "lands.geojson", "All Lands")


def main():
    print_header("CONVERTING RESULTS FOR WEB MAP")

    output_dir = Path(__file__).parent / "webapp" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = export_opportunities(output_dir)
    if result is None:
        return
    road_idxs = result

    export_roads(output_dir, road_idxs)
    export_all_lands(output_dir)

    total_size = sum(
        f.stat().st_size for f in output_dir.glob("*.geojson")
    ) / (1024 * 1024)
    print(f"\n  Total: {total_size:.1f} MB in {output_dir}")
    print(f"\n  Test locally:")
    print(f"    cd webapp && python -m http.server 8888")


if __name__ == "__main__":
    main()
