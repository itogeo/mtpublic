#!/usr/bin/env python3
"""
Step 2: Prepare data for analysis.

- Reprojects all data to Montana State Plane (EPSG:32100)
- Filters roads to county roads only
- Filters land to public ownership only
- Standardizes field names
- Saves prepped data for fast loading in analysis step
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path

import config
from utils import (load_geodata, reproject, classify_land_owner, 
                   ensure_dirs, print_header, m_to_ft)


def prep_roads():
    """Load, filter, and standardize road data."""
    print_header("PREPARING ROADS DATA")
    
    gdf = load_geodata(config.ROADS_PATH)
    gdf = reproject(gdf)
    
    # Show available values in the ownership/class field to help filtering
    owner_field = config.ROAD_OWNER_FIELD
    if owner_field in gdf.columns:
        print(f"\n  Unique values in '{owner_field}':")
        for val, count in gdf[owner_field].value_counts().head(20).items():
            print(f"    {val}: {count:,}")
    else:
        print(f"\n  ⚠  Field '{owner_field}' not found!")
        print(f"  Available fields: {list(gdf.columns)}")
        print(f"  → Update ROAD_OWNER_FIELD in config.py")
        return None
    
    # Filter to county roads using TWO strategies:
    # 1. Ownership field (when populated): "County" or "Public"
    # 2. RoadClass field (when Ownership is NULL): "Local" or "Secondary"
    # NOTE: ~83% of MSDI Transportation records have NULL Ownership

    ownership_mask = gdf[owner_field].isin(config.COUNTY_ROAD_VALUES)

    # For records with NULL ownership, use RoadClass as fallback
    class_field = config.ROAD_CLASS_FIELD
    null_ownership = gdf[owner_field].isna() | (gdf[owner_field] == '')
    class_mask = null_ownership & gdf[class_field].isin(config.COUNTY_ROAD_CLASSES)

    # Exclude explicitly private roads even if RoadClass matches
    private_mask = gdf[owner_field].isin(['Private', 'Federal', 'State', 'City', 'Tribal'])

    county_mask = (ownership_mask | class_mask) & ~private_mask

    print(f"\n  Road filtering breakdown:")
    print(f"    Ownership='County'/'Public':  {ownership_mask.sum():,}")
    print(f"    RoadClass='Local'/'Secondary' (NULL ownership): {class_mask.sum():,}")
    print(f"    Excluded (Private/Federal/State/City/Tribal): {private_mask.sum():,}")

    county_roads = gdf[county_mask].copy()
    print(f"\n  Filtered to {len(county_roads):,} county road segments "
          f"(from {len(gdf):,} total)")
    
    if len(county_roads) == 0:
        print("  ⚠  No county roads found! Check COUNTY_ROAD_VALUES in config.py")
        return None
    
    # Standardize columns
    rename_map = {}
    if config.ROAD_NAME_FIELD in county_roads.columns:
        rename_map[config.ROAD_NAME_FIELD] = 'road_name'
    if config.ROAD_OWNER_FIELD in county_roads.columns:
        rename_map[config.ROAD_OWNER_FIELD] = 'road_owner'
    if config.ROAD_CLASS_FIELD in county_roads.columns:
        rename_map[config.ROAD_CLASS_FIELD] = 'road_class'
    if config.ROAD_COUNTY_FIELD in county_roads.columns:
        rename_map[config.ROAD_COUNTY_FIELD] = 'county'
    
    county_roads = county_roads.rename(columns=rename_map)
    
    # Keep only useful columns + geometry
    keep_cols = ['road_name', 'road_owner', 'road_class', 'county', 'geometry']
    keep_cols = [c for c in keep_cols if c in county_roads.columns]
    county_roads = county_roads[keep_cols]
    
    # Simplify geometry if configured
    if config.SIMPLIFY_TOLERANCE:
        print(f"  Simplifying geometries (tolerance={config.SIMPLIFY_TOLERANCE}m)...")
        county_roads['geometry'] = county_roads.geometry.simplify(
            config.SIMPLIFY_TOLERANCE, preserve_topology=True
        )
    
    # Add length in feet
    county_roads['length_ft'] = county_roads.geometry.length * 3.28084
    
    # Save
    outpath = config.PREPPED_DIR / "county_roads.gpkg"
    county_roads.to_file(outpath, driver="GPKG")
    print(f"  Saved: {outpath} ({len(county_roads):,} segments)")
    
    # Summary stats
    total_miles = county_roads['length_ft'].sum() / 5280
    print(f"  Total county road miles: {total_miles:,.0f}")
    if 'county' in county_roads.columns:
        print(f"\n  Roads by county (top 20):")
        for county, count in county_roads['county'].value_counts().head(20).items():
            miles = county_roads[county_roads['county'] == county]['length_ft'].sum() / 5280
            print(f"    {county}: {count:,} segments ({miles:,.0f} miles)")
    
    return county_roads


def prep_public_lands():
    """Load, filter, and standardize public lands data."""
    print_header("PREPARING PUBLIC LANDS DATA")
    
    gdf = load_geodata(config.PUBLIC_LANDS_PATH)
    gdf = reproject(gdf)
    
    # Show available values in ownership field
    owner_field = config.LAND_OWNER_FIELD
    if owner_field in gdf.columns:
        print(f"\n  Unique values in '{owner_field}':")
        for val, count in gdf[owner_field].value_counts().head(30).items():
            print(f"    {val}: {count:,}")
    else:
        print(f"\n  ⚠  Field '{owner_field}' not found!")
        print(f"  Available fields: {list(gdf.columns)}")
        print(f"  → Update LAND_OWNER_FIELD in config.py")
        return None
    
    # Classify ownership
    gdf['land_category'] = gdf[owner_field].apply(classify_land_owner)
    
    print(f"\n  Classified ownership:")
    for cat, count in gdf['land_category'].value_counts().items():
        print(f"    {cat}: {count:,}")
    
    # Filter to public lands only (exclude UNKNOWN which is likely private)
    public_mask = gdf['land_category'] != 'UNKNOWN'
    public_lands = gdf[public_mask].copy()
    print(f"\n  Filtered to {len(public_lands):,} public land parcels "
          f"(from {len(gdf):,} total)")
    
    # Standardize columns
    rename_map = {owner_field: 'land_owner'}
    if config.LAND_NAME_FIELD in public_lands.columns:
        rename_map[config.LAND_NAME_FIELD] = 'land_name'
    
    public_lands = public_lands.rename(columns=rename_map)
    
    keep_cols = ['land_owner', 'land_name', 'land_category', 'geometry']
    keep_cols = [c for c in keep_cols if c in public_lands.columns]
    public_lands = public_lands[keep_cols]
    
    # Add area in acres
    public_lands['area_acres'] = public_lands.geometry.area * 0.000247105
    
    # Simplify geometry if configured  
    if config.SIMPLIFY_TOLERANCE:
        print(f"  Simplifying geometries (tolerance={config.SIMPLIFY_TOLERANCE}m)...")
        public_lands['geometry'] = public_lands.geometry.simplify(
            config.SIMPLIFY_TOLERANCE, preserve_topology=True
        )
    
    # Save
    outpath = config.PREPPED_DIR / "public_lands.gpkg"
    public_lands.to_file(outpath, driver="GPKG")
    print(f"  Saved: {outpath} ({len(public_lands):,} parcels)")
    
    total_acres = public_lands['area_acres'].sum()
    print(f"  Total public land: {total_acres:,.0f} acres ({total_acres/1e6:.2f}M)")
    
    return public_lands


def prep_plss():
    """Load and standardize PLSS grid (optional, for enrichment)."""
    print_header("PREPARING PLSS GRID")

    if not config.PLSS_PATH.exists():
        print("  ⚠  PLSS data not found, skipping (not required for Phase 1)")
        return None

    try:
        gdf = load_geodata(config.PLSS_PATH)
    except Exception as e:
        print(f"  ⚠  Could not load PLSS data: {e}")
        print("  Skipping PLSS (not required for Phase 1)")
        return None
    gdf = reproject(gdf)
    
    outpath = config.PREPPED_DIR / "plss.gpkg"
    gdf.to_file(outpath, driver="GPKG")
    print(f"  Saved: {outpath} ({len(gdf):,} features)")
    
    return gdf


def main():
    ensure_dirs()
    
    print_header("MONTANA PUBLIC LAND ACCESS — DATA PREPARATION")
    
    roads = prep_roads()
    lands = prep_public_lands()
    plss = prep_plss()
    
    print_header("PREPARATION COMPLETE")
    if roads is not None and lands is not None:
        print(f"""
    ✓ County roads: {len(roads):,} segments
    ✓ Public lands:  {len(lands):,} parcels
    {'✓' if plss is not None else '⚠'} PLSS grid:    {'ready' if plss is not None else 'skipped'}
    
    Prepped data saved to: {config.PREPPED_DIR}
    
    Next: python 03_buffer_analysis.py
        """)
    else:
        print("""
    ⚠  Some datasets failed to prepare.
    Check the errors above and update config.py accordingly.
    Then re-run this script.
        """)


if __name__ == "__main__":
    main()
