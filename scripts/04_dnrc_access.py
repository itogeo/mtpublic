#!/usr/bin/env python3
"""
Step 4: DNRC Trust Land Access Analysis.

Downloads DNRC access designation data (No Public Access vs Public Access)
from the MT DNRC ArcGIS REST service, then cross-references with county roads
to find which "No Public Access" parcels could be unlocked by asserting
the 30ft statutory road easement (MCA 7-14-2112).

Data source:
  https://gis.dnrc.mt.gov/arcgis/rest/services/TLMD/AccessMap/MapServer/
  Layer 0 = No Public Access (3,428 parcels)
  Layer 1 = Public Access (8,697 parcels)

Output: output/results/dnrc_access.gpkg
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import requests
import json
import time
from shapely import STRtree
from shapely.ops import nearest_points

import config
from utils import ensure_dirs, print_header, m_to_ft

DNRC_BASE = "https://gis.dnrc.mt.gov/arcgis/rest/services/TLMD/AccessMap/MapServer"
MAX_RECORDS = 2000  # ArcGIS server limit per query

# Fields to download (skip the big geometry-stats fields)
OUT_FIELDS = (
    "OBJECTID,TractID,STRID,LegDescrip,Unit,GrantID,Acres,TLMSAcres,"
    "TractType,Access_Type,Access_Type_Spcl,AccessLoc,Lease_Status,"
    "Verified,TRS,Addl_Info"
)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def download_layer(layer_id, layer_name):
    """Download all features from a DNRC ArcGIS layer with pagination."""
    print(f"\n  Downloading Layer {layer_id}: {layer_name}...")

    # Get total count first
    count_url = f"{DNRC_BASE}/{layer_id}/query"
    count_params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    resp = requests.get(count_url, params=count_params, timeout=30)
    total = resp.json().get("count", 0)
    print(f"    Total features: {total:,}")

    all_features = []
    offset = 0
    while offset < total:
        query_params = {
            "where": "1=1",
            "outFields": OUT_FIELDS,
            "outSR": "32100",  # Montana State Plane
            "resultOffset": offset,
            "resultRecordCount": MAX_RECORDS,
            "f": "geojson",
        }
        resp = requests.get(f"{DNRC_BASE}/{layer_id}/query",
                            params=query_params, timeout=60)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        offset += len(features)
        print(f"    Downloaded {len(all_features):,} / {total:,}")
        time.sleep(0.3)  # Be polite to the server

    # Build GeoDataFrame
    fc = {"type": "FeatureCollection", "features": all_features}
    gdf = gpd.GeoDataFrame.from_features(fc, crs="EPSG:32100")
    print(f"    Got {len(gdf):,} features with {len(gdf.columns)} columns")
    return gdf


def download_all_dnrc():
    """Download both DNRC access layers."""
    print_header("DOWNLOADING DNRC ACCESS DATA")

    no_access = download_layer(0, "No Public Access")
    no_access["dnrc_status"] = "no_access"

    public_access = download_layer(1, "Public Access")
    public_access["dnrc_status"] = "public_access"

    # Combine
    combined = pd.concat([no_access, public_access], ignore_index=True)
    print(f"\n  Combined: {len(combined):,} DNRC parcels")
    print(f"    No Access:     {len(no_access):,}")
    print(f"    Public Access: {len(public_access):,}")

    return combined


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def analyze_road_access(dnrc, roads):
    """
    Find which DNRC 'No Public Access' parcels are near county roads.

    For each no-access parcel:
    - If road buffer (30ft) intersects → 'confirmed' (road easement provides access)
    - If gap < 100ft → 'near_miss'
    - Otherwise → 'landlocked'

    Public access parcels get status 'public_access' (already accessible).
    """
    print_header("ANALYZING ROAD ACCESS TO DNRC PARCELS")

    # Split into no-access vs public
    no_access = dnrc[dnrc["dnrc_status"] == "no_access"].copy()
    public = dnrc[dnrc["dnrc_status"] == "public_access"].copy()

    print(f"  No Access parcels to analyze: {len(no_access):,}")
    print(f"  Public Access parcels (pass-through): {len(public):,}")

    # --- Buffer county roads by statutory 30ft ---
    print(f"\n  Buffering {len(roads):,} county road segments by {config.BUFFER_DISTANCE_FT}ft...")
    road_buffer = roads.geometry.buffer(config.BUFFER_DISTANCE_M)
    road_union = road_buffer.union_all()
    print("    Road buffer union complete.")

    # --- Phase 1: Which no-access parcels are touched by road buffer? ---
    print("\n  Phase 1: Finding parcels touched by road buffer...")
    no_access["touches_road"] = no_access.geometry.intersects(road_union)
    confirmed = no_access[no_access["touches_road"]].copy()
    remaining = no_access[~no_access["touches_road"]].copy()
    print(f"    Confirmed (road buffer touches): {len(confirmed):,}")
    print(f"    Remaining to check: {len(remaining):,}")

    # --- Phase 2: Measure gap for remaining parcels ---
    print("\n  Phase 2: Measuring gap to nearest road for remaining parcels...")

    # Build STRtree of road geometries for fast nearest-neighbor
    road_geoms = roads.geometry.values
    road_tree = STRtree(road_geoms)
    road_names = roads["road_name"].values
    road_counties = roads["county"].values

    gaps = []
    nearest_roads = []
    nearest_counties = []

    for idx, row in remaining.iterrows():
        centroid = row.geometry.centroid
        nearest_idx = road_tree.nearest(centroid)
        nearest_road_geom = road_geoms[nearest_idx]
        # Distance from parcel boundary (not centroid) to road centerline
        gap_m = row.geometry.distance(nearest_road_geom)
        gap_ft = m_to_ft(gap_m) - config.BUFFER_DISTANCE_FT  # Subtract road buffer
        gaps.append(max(gap_ft, 0))
        nearest_roads.append(road_names[nearest_idx] if nearest_idx < len(road_names) else "Unknown")
        nearest_counties.append(road_counties[nearest_idx] if nearest_idx < len(road_counties) else "Unknown")

    remaining["gap_ft"] = gaps
    remaining["nearest_road"] = nearest_roads
    remaining["road_county"] = nearest_counties

    near_miss = remaining[remaining["gap_ft"] <= config.NEAR_MISS_THRESHOLD_FT].copy()
    landlocked = remaining[remaining["gap_ft"] > config.NEAR_MISS_THRESHOLD_FT].copy()

    print(f"    Near-miss (< {config.NEAR_MISS_THRESHOLD_FT}ft): {len(near_miss):,}")
    print(f"    Landlocked (> {config.NEAR_MISS_THRESHOLD_FT}ft): {len(landlocked):,}")

    # --- Phase 3: Enrich confirmed parcels with nearest road info ---
    print("\n  Phase 3: Enriching confirmed parcels with road info...")
    c_nearest_roads = []
    c_nearest_counties = []
    c_gaps = []

    for idx, row in confirmed.iterrows():
        centroid = row.geometry.centroid
        nearest_idx = road_tree.nearest(centroid)
        nearest_road_geom = road_geoms[nearest_idx]
        gap_m = row.geometry.distance(nearest_road_geom)
        gap_ft = m_to_ft(gap_m) - config.BUFFER_DISTANCE_FT
        c_gaps.append(max(gap_ft, 0))
        c_nearest_roads.append(road_names[nearest_idx] if nearest_idx < len(road_names) else "Unknown")
        c_nearest_counties.append(road_counties[nearest_idx] if nearest_idx < len(road_counties) else "Unknown")

    confirmed["gap_ft"] = c_gaps
    confirmed["nearest_road"] = c_nearest_roads
    confirmed["road_county"] = c_nearest_counties

    # --- Assign statuses ---
    confirmed["access_status"] = "confirmed"
    near_miss["access_status"] = "near_miss"
    landlocked["access_status"] = "landlocked"
    public["access_status"] = "public_access"
    public["gap_ft"] = 0
    public["nearest_road"] = ""
    public["road_county"] = ""

    # Enrich public parcels with nearest road too
    print("  Enriching public parcels with nearest road...")
    p_nearest_roads = []
    p_nearest_counties = []
    for idx, row in public.iterrows():
        centroid = row.geometry.centroid
        nearest_idx = road_tree.nearest(centroid)
        p_nearest_roads.append(road_names[nearest_idx] if nearest_idx < len(road_names) else "Unknown")
        p_nearest_counties.append(road_counties[nearest_idx] if nearest_idx < len(road_counties) else "Unknown")
    public["nearest_road"] = p_nearest_roads
    public["road_county"] = p_nearest_counties

    # Combine all
    result = pd.concat([confirmed, near_miss, landlocked, public], ignore_index=True)

    # Clean up columns
    drop_cols = ["touches_road"]
    result = result.drop(columns=[c for c in drop_cols if c in result.columns])

    return result


def main():
    ensure_dirs()

    # Download DNRC data
    dnrc = download_all_dnrc()

    # Remove empty geometries
    dnrc = dnrc[~dnrc.geometry.is_empty & dnrc.geometry.notna()].copy()
    print(f"\n  Valid geometries: {len(dnrc):,}")

    # Load county roads
    print_header("LOADING COUNTY ROADS")
    roads_path = config.PREPPED_DIR / "county_roads.gpkg"
    roads = gpd.read_file(roads_path)
    print(f"  County roads: {len(roads):,} segments")

    # Run analysis
    result = analyze_road_access(dnrc, roads)

    # Summary
    print_header("RESULTS SUMMARY")
    for status in ["confirmed", "near_miss", "landlocked", "public_access"]:
        subset = result[result["access_status"] == status]
        acres = subset["Acres"].sum() if "Acres" in subset.columns else 0
        print(f"  {status:15s}: {len(subset):>6,} parcels  ({acres:>12,.0f} acres)")

    total_no_access = result[result["dnrc_status"] == "no_access"]
    unlockable = result[result["access_status"].isin(["confirmed", "near_miss"])]
    unlockable_no = unlockable[unlockable["dnrc_status"] == "no_access"]
    print(f"\n  DNRC 'No Access' parcels: {len(total_no_access):,}")
    print(f"  Potentially unlockable via county roads: {len(unlockable_no):,}")
    if "Acres" in unlockable_no.columns:
        print(f"  Unlockable acres: {unlockable_no['Acres'].sum():,.0f}")

    # Top opportunities
    top = unlockable_no.nlargest(15, "Acres")
    print(f"\n  Top 15 unlock opportunities (by acres):")
    for _, row in top.iterrows():
        road = row.get("nearest_road", "Unknown")
        acres = row.get("Acres", 0)
        gap = row.get("gap_ft", 0)
        trs = row.get("TRS", "")
        status = row["access_status"]
        print(f"    {road:30s}  {acres:>8,.0f} ac  gap: {gap:>6.1f}ft  [{status}]  {trs}")

    # Export
    output_path = config.RESULTS_DIR / "dnrc_access.gpkg"
    result.to_file(output_path, driver="GPKG")
    print(f"\n  Saved: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
