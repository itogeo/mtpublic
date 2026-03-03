#!/usr/bin/env python3
"""
Step 3b: Public Land Unlock Analysis — Find roads that can open landlocked land.

Extends the connectivity graph from 03_state_access to ALL public land types
(BLM, USFS, STATE, FWP, etc.) and identifies strategic "unlock points" where
asserting a single county road could open access to entire blocks of connected
public land.

Each unlock opportunity = one point where a county road is closest to a
landlocked component. A single gap could unlock thousands of connected acres.

Algorithm:
  Phase 1: Build spatial adjacency graph of all public land parcels
  Phase 2: Flood-fill from county road buffer to find road-accessible components
  Phase 3: Classify ALL public land parcels (not just STATE)
  Phase 4: For each landlocked component, find the best unlock point
  Phase 5: Rank and export

Output: output/results/unlock_opportunities.gpkg
        output/results/all_public_access.gpkg
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import networkx as nx
from shapely import STRtree
from shapely.geometry import Point
from shapely.ops import nearest_points

import config
from utils import ensure_dirs, print_header, m_to_ft


# ---------------------------------------------------------------------------
# Phase 1: Build adjacency graph (shared with 03_state_access.py)
# ---------------------------------------------------------------------------
def build_adjacency_graph(lands):
    """
    Buffer all public land parcels by ADJACENCY_BUFFER_M, spatial self-join
    to find adjacent pairs, build NetworkX graph, find connected components.
    """
    print_header("PHASE 1: BUILDING ADJACENCY GRAPH")

    n = len(lands)
    print(f"  Parcels: {n:,}")
    print(f"  Adjacency buffer: {config.ADJACENCY_BUFFER_M}m")

    # Buffer geometries for adjacency testing
    print("  Buffering all parcels for adjacency detection...")
    buffered = lands[['geometry']].copy()
    buffered['geometry'] = lands.geometry.buffer(config.ADJACENCY_BUFFER_M)

    # Spatial self-join
    print("  Running spatial self-join (may take 1-3 minutes)...")
    joined = gpd.sjoin(buffered, buffered, how='inner', predicate='intersects')

    # Remove self-joins
    pairs = joined[joined.index != joined['index_right']]
    print(f"  Adjacency pairs: {len(pairs):,}")

    # Build NetworkX graph
    print("  Building graph...")
    G = nx.Graph()
    G.add_nodes_from(lands.index)
    G.add_edges_from(zip(pairs.index, pairs['index_right']))
    print(f"  Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    # Connected components
    components = list(nx.connected_components(G))
    print(f"  Connected components: {len(components):,}")

    # Map parcel index → component ID
    component_map = {}
    for comp_id, members in enumerate(components):
        for member in members:
            component_map[member] = comp_id

    lands['component_id'] = lands.index.map(component_map)

    # Stats
    sizes = [len(c) for c in components]
    print(f"  Largest component: {max(sizes):,} parcels")
    print(f"  Singletons: {sum(1 for s in sizes if s == 1):,}")

    return G, component_map, components


# ---------------------------------------------------------------------------
# Phase 2: Mark road-accessible components
# ---------------------------------------------------------------------------
def mark_road_accessible(lands, roads, component_map, components):
    """
    Buffer county roads by 30ft, spatial-join against public lands to find
    which parcels (and therefore which components) touch a county road.
    """
    print_header("PHASE 2: MARKING ROAD-ACCESSIBLE COMPONENTS")

    print(f"  Buffering {len(roads):,} road segments by {config.BUFFER_DISTANCE_FT}ft...")
    road_buffers = roads[['geometry']].copy()
    road_buffers['geometry'] = roads.geometry.buffer(config.BUFFER_DISTANCE_M)

    # Spatial join: which parcels intersect road buffers?
    print("  Spatial join: lands vs road buffers...")
    touching = gpd.sjoin(lands, road_buffers, how='inner', predicate='intersects')
    road_touching_idxs = touching.index.unique().tolist()
    print(f"  Parcels touching road buffer: {len(road_touching_idxs):,}")

    # Mark on lands
    lands['touches_road'] = lands.index.isin(road_touching_idxs)

    # Find accessible components
    accessible_components = set()
    for idx in road_touching_idxs:
        accessible_components.add(component_map[idx])

    # Stats
    accessible_parcels = sum(
        len(c) for i, c in enumerate(components) if i in accessible_components
    )
    print(f"  Road-accessible components: {len(accessible_components):,} "
          f"of {len(components):,}")
    print(f"  Parcels in accessible components: {accessible_parcels:,} "
          f"({accessible_parcels / len(lands) * 100:.1f}%)")

    return accessible_components


# ---------------------------------------------------------------------------
# Phase 3: Classify ALL public land parcels
# ---------------------------------------------------------------------------
def classify_all_parcels(lands, accessible_components, roads):
    """
    Classify every public land parcel as accessible / near_miss / landlocked.
    For landlocked parcels, measure gap to nearest accessible parcel.
    """
    print_header("PHASE 3: CLASSIFYING ALL PUBLIC LAND PARCELS")

    print(f"  Total public land parcels: {len(lands):,}")

    # Classify by component
    lands['access_status'] = lands['component_id'].apply(
        lambda cid: 'accessible' if cid in accessible_components else 'landlocked'
    )

    accessible_count = (lands['access_status'] == 'accessible').sum()
    landlocked_count = (lands['access_status'] == 'landlocked').sum()
    print(f"  Accessible: {accessible_count:,}")
    print(f"  Landlocked: {landlocked_count:,}")

    # Breakdown by land category
    print(f"\n  BREAKDOWN BY LAND TYPE:")
    for cat in sorted(lands['land_category'].unique()):
        cat_mask = lands['land_category'] == cat
        total = cat_mask.sum()
        acc = ((lands['access_status'] == 'accessible') & cat_mask).sum()
        locked = ((lands['access_status'] == 'landlocked') & cat_mask).sum()
        acres = lands.loc[cat_mask, 'area_acres'].sum() if 'area_acres' in lands.columns else 0
        locked_acres = lands.loc[(lands['access_status'] == 'landlocked') & cat_mask, 'area_acres'].sum() if 'area_acres' in lands.columns else 0
        print(f"    {cat:>15}: {total:>6,} parcels ({acc:>5,} accessible, "
              f"{locked:>5,} landlocked) — {locked_acres:>12,.0f} landlocked acres")

    # Measure gaps for landlocked parcels
    lands['gap_ft'] = 0.0

    landlocked = lands[lands['access_status'] == 'landlocked']
    if len(landlocked) > 0:
        print(f"\n  Measuring gaps for {len(landlocked):,} landlocked parcels...")

        # Build STRtree of all accessible parcels
        accessible_mask = lands['component_id'].isin(accessible_components)
        accessible_lands = lands[accessible_mask]
        tree = STRtree(accessible_lands.geometry.values)

        gaps = []
        for i, (idx, row) in enumerate(landlocked.iterrows()):
            nearest_idx = tree.nearest(row.geometry)
            dist_m = row.geometry.distance(accessible_lands.geometry.iloc[nearest_idx])
            gaps.append(m_to_ft(dist_m))
            if (i + 1) % 1000 == 0:
                print(f"    {i + 1}/{len(landlocked)}...")

        lands.loc[landlocked.index, 'gap_ft'] = gaps

        # Reclassify near-misses
        near_miss_mask = (
            (lands['access_status'] == 'landlocked') &
            (lands['gap_ft'] <= config.NEAR_MISS_THRESHOLD_FT)
        )
        lands.loc[near_miss_mask, 'access_status'] = 'near_miss'

        near_miss_count = near_miss_mask.sum()
        final_landlocked = (lands['access_status'] == 'landlocked').sum()
        print(f"  Near-miss (gap < {config.NEAR_MISS_THRESHOLD_FT}ft): {near_miss_count:,}")
        print(f"  Final landlocked: {final_landlocked:,}")

    return lands


# ---------------------------------------------------------------------------
# Phase 4: Find strategic unlock points for each landlocked component
# ---------------------------------------------------------------------------
def find_unlock_points(lands, roads):
    """
    For each landlocked connected component:
    - Find the closest county road segment
    - Create a point at the gap location
    - Calculate total acres and parcels in the component
    - Record the road name and gap distance
    """
    print_header("PHASE 4: FINDING STRATEGIC UNLOCK POINTS")

    # Get landlocked components (including near-miss)
    non_accessible = lands[lands['access_status'].isin(['landlocked', 'near_miss'])]
    landlocked_components = non_accessible['component_id'].unique()
    print(f"  Landlocked/near-miss components: {len(landlocked_components):,}")

    # Build spatial index for roads
    print("  Building road spatial index...")
    road_tree = STRtree(roads.geometry.values)

    unlock_points = []

    for i, comp_id in enumerate(landlocked_components):
        comp_parcels = lands[lands['component_id'] == comp_id]

        # Component stats
        total_acres = comp_parcels['area_acres'].sum() if 'area_acres' in comp_parcels.columns else 0
        num_parcels = len(comp_parcels)
        categories = comp_parcels['land_category'].value_counts()
        primary_category = categories.index[0]
        category_list = ', '.join(f"{cat}({n})" for cat, n in categories.items())
        owners = comp_parcels['land_name'].unique()

        # Find the nearest road to this entire component
        # Use the union of all parcel geometries in the component
        if num_parcels == 1:
            comp_geom = comp_parcels.geometry.iloc[0]
        else:
            comp_geom = comp_parcels.unary_union

        # Find nearest road segment
        nearest_road_idx = road_tree.nearest(comp_geom)
        road_row = roads.iloc[nearest_road_idx]
        road_geom = road_row.geometry

        # Buffer the road by 30ft statutory width
        road_buffered = road_geom.buffer(config.BUFFER_DISTANCE_M)

        # Measure gap from road buffer edge to component
        gap_m = comp_geom.distance(road_buffered)
        gap_ft = m_to_ft(gap_m)

        # Find the exact point on the component closest to the road
        p1, p2 = nearest_points(comp_geom, road_geom)
        # The unlock point is on the road side (where you'd assert access)
        unlock_point = p2

        # Get road name
        road_name = road_row.get('road_name', '') or road_row.get('St_Name', '')
        if not road_name:
            road_name = 'Unnamed Road'
        county = road_row.get('county', '') or road_row.get('County_L', '')

        # Road index for linking
        road_idx = roads.index[nearest_road_idx] if hasattr(nearest_road_idx, '__index__') else nearest_road_idx

        # Access status for the component
        statuses = comp_parcels['access_status'].value_counts()
        if 'near_miss' in statuses.index:
            comp_status = 'near_miss'
        else:
            comp_status = 'landlocked'

        # Acres by category
        cat_acres = {}
        for cat in comp_parcels['land_category'].unique():
            cat_acres[cat] = comp_parcels.loc[
                comp_parcels['land_category'] == cat, 'area_acres'
            ].sum() if 'area_acres' in comp_parcels.columns else 0

        unlock_points.append({
            'geometry': unlock_point,
            'component_id': int(comp_id),
            'gap_ft': round(gap_ft, 1),
            'total_acres': round(total_acres, 1),
            'num_parcels': num_parcels,
            'primary_category': primary_category,
            'categories': category_list,
            'road_name': road_name,
            'county': county,
            'road_idx': road_idx,
            'access_status': comp_status,
            # Breakdown
            'blm_acres': round(cat_acres.get('BLM', 0), 1),
            'usfs_acres': round(cat_acres.get('USFS', 0), 1),
            'state_acres': round(cat_acres.get('STATE', 0), 1),
            'fwp_acres': round(cat_acres.get('FWP', 0), 1),
            'other_acres': round(sum(v for k, v in cat_acres.items()
                                     if k not in ('BLM', 'USFS', 'STATE', 'FWP')), 1),
        })

        if (i + 1) % 500 == 0:
            print(f"    {i + 1}/{len(landlocked_components)}...")

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(unlock_points, crs=lands.crs)

    # Calculate unlock score: acres / max(gap, 1)
    # Higher score = more acres per foot of gap = better opportunity
    gdf['unlock_score'] = (gdf['total_acres'] / gdf['gap_ft'].clip(lower=1)).round(1)
    gdf = gdf.sort_values('unlock_score', ascending=False).reset_index(drop=True)

    print(f"\n  UNLOCK OPPORTUNITY SUMMARY")
    print(f"  {'=' * 60}")
    print(f"  Total unlock points: {len(gdf):,}")

    # Near-miss vs landlocked
    nm = gdf[gdf['access_status'] == 'near_miss']
    ll = gdf[gdf['access_status'] == 'landlocked']
    print(f"  Near-miss (< {config.NEAR_MISS_THRESHOLD_FT}ft gap): {len(nm):,} "
          f"({nm['total_acres'].sum():,.0f} acres)")
    print(f"  Landlocked (> {config.NEAR_MISS_THRESHOLD_FT}ft gap): {len(ll):,} "
          f"({ll['total_acres'].sum():,.0f} acres)")

    # Gap distribution
    print(f"\n  GAP DISTRIBUTION:")
    for threshold in [10, 25, 50, 100, 250, 500]:
        under = gdf[gdf['gap_ft'] <= threshold]
        print(f"    ≤ {threshold:>4}ft: {len(under):>5,} opportunities, "
              f"{under['total_acres'].sum():>12,.0f} acres")

    # Top 20 unlock opportunities
    print(f"\n  TOP 20 UNLOCK OPPORTUNITIES (by acres/gap ratio):")
    print(f"  {'Road':<30} {'Gap':>8} {'Acres':>10} {'Parcels':>8} {'Land Type':<15} {'County':<20}")
    print(f"  {'-'*95}")
    for _, row in gdf.head(20).iterrows():
        print(f"  {row['road_name']:<30} {row['gap_ft']:>7.1f}ft "
              f"{row['total_acres']:>9,.0f} {row['num_parcels']:>7,} "
              f"{row['primary_category']:<15} {row['county']:<20}")

    # Acres by primary land category
    print(f"\n  LANDLOCKED ACRES BY LAND TYPE:")
    cat_summary = gdf.groupby('primary_category').agg(
        count=('component_id', 'count'),
        acres=('total_acres', 'sum'),
    ).sort_values('acres', ascending=False)
    for cat, row in cat_summary.iterrows():
        print(f"    {cat:>15}: {int(row['count']):>5,} components, "
              f"{row['acres']:>12,.0f} acres")

    return gdf


# ---------------------------------------------------------------------------
# Phase 5: Export
# ---------------------------------------------------------------------------
def export_results(unlock_gdf, lands):
    """Export unlock opportunities and full public access classification."""
    print_header("PHASE 5: EXPORTING RESULTS")

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Unlock opportunities (point features)
    unlock_path = config.RESULTS_DIR / "unlock_opportunities.gpkg"
    unlock_gdf.to_file(unlock_path, driver="GPKG")
    print(f"  Saved: {unlock_path} ({len(unlock_gdf):,} unlock points)")

    # 2. Full public land access classification (polygon features)
    access_cols = [
        'access_status', 'gap_ft', 'area_acres', 'land_name',
        'land_category', 'component_id', 'geometry',
    ]
    access_cols = [c for c in access_cols if c in lands.columns]
    access_output = lands[access_cols].copy()
    access_path = config.RESULTS_DIR / "all_public_access.gpkg"
    access_output.to_file(access_path, driver="GPKG")
    print(f"  Saved: {access_path} ({len(access_output):,} parcels)")

    # 3. CSV of top unlock opportunities (easy to share)
    csv_cols = [c for c in unlock_gdf.columns if c != 'geometry']
    csv_path = config.RESULTS_DIR / "unlock_opportunities.csv"
    unlock_gdf[csv_cols].to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")

    # 4. Summary by county
    print(f"\n  TOP COUNTIES BY LANDLOCKED ACREAGE:")
    county_summary = unlock_gdf.groupby('county').agg(
        opportunities=('component_id', 'count'),
        total_acres=('total_acres', 'sum'),
        near_miss=('access_status', lambda x: (x == 'near_miss').sum()),
        avg_gap_ft=('gap_ft', 'mean'),
        min_gap_ft=('gap_ft', 'min'),
    ).sort_values('total_acres', ascending=False)
    county_summary.to_csv(config.RESULTS_DIR / "unlock_county_summary.csv")

    for county, row in county_summary.head(15).iterrows():
        print(f"    {county:<25} {int(row['opportunities']):>4} opps, "
              f"{row['total_acres']:>10,.0f} acres "
              f"({int(row['near_miss'])} near-miss, "
              f"min gap {row['min_gap_ft']:.0f}ft)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ensure_dirs()
    print_header("PUBLIC LAND UNLOCK ANALYSIS")
    print("  Finding ALL public land unlockable via county roads")
    print("  (BLM, USFS, STATE, FWP, and all other public land types)")

    # Load prepped data
    roads_path = config.PREPPED_DIR / "county_roads.gpkg"
    lands_path = config.PREPPED_DIR / "public_lands.gpkg"

    if not roads_path.exists() or not lands_path.exists():
        print("  ERROR: Prepped data not found. Run 02_prep_data.py first.")
        return

    print("  Loading prepped data...")
    roads = gpd.read_file(roads_path)
    lands = gpd.read_file(lands_path)
    print(f"  Roads: {len(roads):,} county road segments")
    print(f"  Public lands: {len(lands):,} parcels")

    # Phase 1 — Build adjacency graph
    G, component_map, components = build_adjacency_graph(lands)

    # Phase 2 — Mark road-accessible components
    accessible_components = mark_road_accessible(
        lands, roads, component_map, components
    )

    # Phase 3 — Classify ALL public parcels
    lands = classify_all_parcels(lands, accessible_components, roads)

    # Phase 4 — Find strategic unlock points
    unlock_gdf = find_unlock_points(lands, roads)

    # Phase 5 — Export
    export_results(unlock_gdf, lands)

    print_header("ANALYSIS COMPLETE")
    total_locked_acres = lands.loc[
        lands['access_status'].isin(['landlocked', 'near_miss']),
        'area_acres'
    ].sum() if 'area_acres' in lands.columns else 0
    print(f"  Total landlocked public land: {total_locked_acres:,.0f} acres")
    print(f"  Unlock opportunities: {len(unlock_gdf):,}")
    print(f"  Results: {config.RESULTS_DIR}")
    print(f"  Next: python 06_convert_for_web.py")


if __name__ == "__main__":
    main()
