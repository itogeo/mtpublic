#!/usr/bin/env python3
"""
Step 3: Core buffer analysis.

For every county road segment:
1. Buffer by 30 feet (statutory half-width)
2. Find nearest public land parcel
3. Calculate gap distance
4. Record where buffer intersects public land (confirmed access)
5. Record near-misses (gap < 100 feet)

Outputs a GeoDataFrame of all opportunities with gap distances and metadata.
"""
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, MultiPoint
from shapely.ops import nearest_points
from tqdm import tqdm
from pathlib import Path

import config
from utils import ensure_dirs, print_header, m_to_ft, ft_to_m


def load_prepped_data():
    """Load prepped data from Step 2."""
    roads_path = config.PREPPED_DIR / "county_roads.gpkg"
    lands_path = config.PREPPED_DIR / "public_lands.gpkg"
    
    if not roads_path.exists() or not lands_path.exists():
        print("⚠  Prepped data not found! Run 02_prep_data.py first.")
        return None, None
    
    print("Loading prepped data...")
    roads = gpd.read_file(roads_path)
    print(f"  Roads: {len(roads):,} county road segments")
    
    lands = gpd.read_file(lands_path)
    print(f"  Public lands: {len(lands):,} parcels")
    
    return roads, lands


def build_spatial_index(gdf: gpd.GeoDataFrame):
    """Build spatial index for fast nearest-neighbor queries."""
    print("  Building spatial index...")
    return gdf.sindex


def analyze_segment(road_geom, road_idx, lands_gdf, lands_sindex, 
                    buffer_dist_m, search_dist_m):
    """
    Analyze a single road segment against public lands.
    
    Returns a list of opportunity dicts for this segment.
    """
    results = []
    
    # Search area: buffer the road by the maximum search distance
    search_area = road_geom.buffer(search_dist_m)
    
    # Find candidate public land parcels using spatial index
    candidate_idxs = list(lands_sindex.intersection(search_area.bounds))
    
    if not candidate_idxs:
        return results
    
    candidates = lands_gdf.iloc[candidate_idxs]
    
    # Calculate distance from road to each candidate parcel
    for land_idx, land_row in candidates.iterrows():
        land_geom = land_row.geometry
        
        # Distance from road centerline to land boundary
        dist_m = road_geom.distance(land_geom)
        dist_ft = m_to_ft(dist_m)
        
        # Gap = distance minus buffer (negative means buffer overlaps)
        gap_ft = dist_ft - config.BUFFER_DISTANCE_FT
        
        if gap_ft <= config.MAX_GAP_FT:
            # Find the closest points between road and land
            try:
                p1, p2 = nearest_points(road_geom, land_geom)
                closest_pt = Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
            except Exception:
                closest_pt = road_geom.interpolate(0.5, normalized=True)
            
            # Check if buffer actually intersects
            road_buffer = road_geom.buffer(config.BUFFER_DISTANCE_M)
            buffer_intersects = road_buffer.intersects(land_geom)
            
            result = {
                'road_idx': road_idx,
                'land_idx': land_idx,
                'dist_centerline_ft': round(dist_ft, 1),
                'gap_ft': round(gap_ft, 1),
                'buffer_intersects': buffer_intersects,
                'land_category': land_row.get('land_category', 'UNKNOWN'),
                'land_owner': land_row.get('land_owner', ''),
                'land_name': land_row.get('land_name', ''),
                'land_area_acres': round(land_row.get('area_acres', 0), 1),
                'closest_point': closest_pt,
            }
            results.append(result)
    
    return results


def run_analysis(roads, lands):
    """Run the buffer analysis across all county road segments."""
    print_header("RUNNING BUFFER ANALYSIS")
    
    search_dist_m = ft_to_m(config.NEAR_MISS_THRESHOLD_FT + config.BUFFER_DISTANCE_FT)
    
    print(f"  Buffer distance: {config.BUFFER_DISTANCE_FT} ft ({config.BUFFER_DISTANCE_M:.2f} m)")
    print(f"  Near-miss threshold: {config.NEAR_MISS_THRESHOLD_FT} ft")
    print(f"  Search radius: {m_to_ft(search_dist_m):.0f} ft")
    print(f"  Road segments to process: {len(roads):,}")
    
    # Build spatial index on public lands
    lands_sindex = build_spatial_index(lands)
    
    # Process each road segment
    all_results = []
    
    for idx, road_row in tqdm(roads.iterrows(), total=len(roads), 
                               desc="  Analyzing roads"):
        results = analyze_segment(
            road_geom=road_row.geometry,
            road_idx=idx,
            lands_gdf=lands,
            lands_sindex=lands_sindex,
            buffer_dist_m=config.BUFFER_DISTANCE_M,
            search_dist_m=search_dist_m,
        )
        
        # Attach road metadata to each result
        for r in results:
            r['road_name'] = road_row.get('road_name', '')
            r['road_owner'] = road_row.get('road_owner', '')
            r['county'] = road_row.get('county', '')
            r['road_length_ft'] = round(road_row.get('length_ft', 0), 0)
        
        all_results.extend(results)
    
    print(f"\n  Found {len(all_results):,} road-to-land proximities")
    
    if not all_results:
        print("  ⚠  No opportunities found! Check your data and config.")
        return None
    
    # Convert to GeoDataFrame
    results_df = pd.DataFrame(all_results)
    results_gdf = gpd.GeoDataFrame(
        results_df,
        geometry='closest_point',
        crs=config.TARGET_CRS
    )
    
    # Summary
    confirmed = results_gdf[results_gdf['buffer_intersects'] == True]
    near_miss = results_gdf[
        (results_gdf['buffer_intersects'] == False) & 
        (results_gdf['gap_ft'] <= config.NEAR_MISS_THRESHOLD_FT)
    ]
    
    print(f"\n  RESULTS SUMMARY:")
    print(f"  ✓ Confirmed access (buffer intersects): {len(confirmed):,}")
    print(f"  → Near-misses (gap ≤ {config.NEAR_MISS_THRESHOLD_FT}ft): {len(near_miss):,}")
    
    print(f"\n  By land category:")
    for cat in results_gdf['land_category'].unique():
        cat_data = results_gdf[results_gdf['land_category'] == cat]
        cat_confirmed = cat_data[cat_data['buffer_intersects'] == True]
        cat_near = cat_data[cat_data['buffer_intersects'] == False]
        print(f"    {cat}: {len(cat_confirmed):,} confirmed, {len(cat_near):,} near-miss")
    
    if 'county' in results_gdf.columns:
        print(f"\n  By county (top 20):")
        county_counts = results_gdf.groupby('county').agg(
            total=('gap_ft', 'count'),
            confirmed=('buffer_intersects', 'sum'),
            min_gap=('gap_ft', 'min'),
        ).sort_values('total', ascending=False).head(20)
        for county, row in county_counts.iterrows():
            print(f"    {county}: {int(row['total'])} total, "
                  f"{int(row['confirmed'])} confirmed, "
                  f"min gap: {row['min_gap']:.0f}ft")
    
    # Save raw results
    outpath = config.RESULTS_DIR / "raw_opportunities.gpkg"
    results_gdf.to_file(outpath, driver="GPKG")
    print(f"\n  Saved raw results: {outpath}")
    
    return results_gdf


def main():
    ensure_dirs()
    
    roads, lands = load_prepped_data()
    if roads is None or lands is None:
        return
    
    results = run_analysis(roads, lands)
    
    if results is not None:
        print_header("ANALYSIS COMPLETE")
        print(f"""
    Raw results saved to: {config.RESULTS_DIR / 'raw_opportunities.gpkg'}
    
    Next: python 04_rank_results.py
        """)


if __name__ == "__main__":
    main()
