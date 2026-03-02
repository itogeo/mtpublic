#!/usr/bin/env python3
"""
Step 3: State Trust Land Connectivity Analysis.

Determines which State Trust / DNRC parcels are accessible from county
roads through a continuous chain of adjacent public land.

Algorithm:
  Phase 1: Build spatial adjacency graph of all public land parcels
  Phase 2: Flood-fill from county road buffer to find road-accessible components
  Phase 3: Classify each STATE parcel as accessible / landlocked / near_miss
  Phase 3b: Detect landlocked parcels enclosed by a single private owner
  Phase 4: Enrich with metadata and export

Output: output/results/state_access.gpkg
"""
import geopandas as gpd
import pandas as pd
import numpy as np
import networkx as nx
from shapely import STRtree
from shapely.ops import nearest_points

import config
from utils import ensure_dirs, print_header, m_to_ft


# ---------------------------------------------------------------------------
# Phase 1: Build adjacency graph
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
# Phase 3: Classify state parcels
# ---------------------------------------------------------------------------
def classify_state_parcels(lands, accessible_components, roads):
    """
    For each STATE parcel: accessible / near_miss / landlocked.
    For landlocked parcels, measure gap to nearest accessible parcel.
    """
    print_header("PHASE 3: CLASSIFYING STATE PARCELS")

    state_mask = lands['land_category'].isin(config.STATE_OWNER_CATEGORIES)
    state = lands[state_mask].copy()
    print(f"  State Trust / DNRC parcels: {len(state):,}")

    # Classify by component
    state['access_status'] = state['component_id'].apply(
        lambda cid: 'accessible' if cid in accessible_components else 'landlocked'
    )

    accessible_count = (state['access_status'] == 'accessible').sum()
    landlocked_count = (state['access_status'] == 'landlocked').sum()
    print(f"  Accessible: {accessible_count:,}")
    print(f"  Landlocked: {landlocked_count:,}")

    # Measure gaps for landlocked parcels
    state['gap_ft'] = 0.0

    landlocked = state[state['access_status'] == 'landlocked']
    if len(landlocked) > 0:
        print(f"  Measuring gaps for {len(landlocked):,} landlocked parcels...")

        # Build STRtree of all accessible parcels for nearest-neighbor queries
        accessible_mask = lands['component_id'].isin(accessible_components)
        accessible_lands = lands[accessible_mask]
        tree = STRtree(accessible_lands.geometry.values)

        gaps = []
        for i, (idx, row) in enumerate(landlocked.iterrows()):
            nearest_idx = tree.nearest(row.geometry)
            dist_m = row.geometry.distance(accessible_lands.geometry.iloc[nearest_idx])
            gaps.append(m_to_ft(dist_m))
            if (i + 1) % 500 == 0:
                print(f"    {i + 1}/{len(landlocked)}...")

        state.loc[landlocked.index, 'gap_ft'] = gaps

        # Reclassify near-misses
        near_miss_mask = (
            (state['access_status'] == 'landlocked') &
            (state['gap_ft'] <= config.NEAR_MISS_THRESHOLD_FT)
        )
        state.loc[near_miss_mask, 'access_status'] = 'near_miss'

        near_miss_count = near_miss_mask.sum()
        final_landlocked = (state['access_status'] == 'landlocked').sum()
        print(f"  Near-miss (gap < {config.NEAR_MISS_THRESHOLD_FT}ft): {near_miss_count:,}")
        print(f"  Final landlocked: {final_landlocked:,}")

    return state


# ---------------------------------------------------------------------------
# Phase 3b: Detect parcels enclosed by a single private owner
# ---------------------------------------------------------------------------
def detect_enclosed(state, cadastral_path):
    """
    For each landlocked/near_miss STATE parcel, check if all adjacent
    cadastral parcels belong to a single private owner.
    If so, mark as 'enclosed' and record the enclosing owner.
    """
    print_header("PHASE 3b: DETECTING SINGLE-OWNER ENCLOSURE")

    if not cadastral_path.exists():
        print(f"  Skipping: {cadastral_path} not found")
        print(f"  Run 07_process_parcels.py to download cadastral data")
        state['enclosed'] = False
        state['enclosing_owner'] = ''
        return state

    # Only analyze non-accessible parcels
    target_mask = state['access_status'].isin(['landlocked', 'near_miss'])
    target = state[target_mask]
    print(f"  Analyzing {len(target):,} landlocked/near-miss parcels")

    if len(target) == 0:
        state['enclosed'] = False
        state['enclosing_owner'] = ''
        return state

    # Load cadastral parcels — only need geometry + owner name
    print(f"  Loading cadastral data (this may take a minute)...")
    cadastral = gpd.read_file(
        cadastral_path,
        columns=['OwnerName', 'geometry'],
    )
    print(f"  Cadastral parcels loaded: {len(cadastral):,}")

    # Reproject to match state parcels
    if cadastral.crs != state.crs:
        print(f"  Reprojecting cadastral from {cadastral.crs} to {state.crs}")
        cadastral = cadastral.to_crs(state.crs)

    # Government/public owner patterns to exclude from enclosure detection
    # We only want to flag parcels enclosed by PRIVATE owners
    GOV_PATTERNS = [
        'STATE OF MONTANA', 'MONTANA STATE', 'MONTANA DEPARTMENT', 'MONTANA DNRC',
        'UNITED STATES', 'US GOVERNMENT', 'US BUREAU', 'US FOREST',
        'US FISH', 'NATIONAL PARK', 'BUREAU OF LAND',
        'DEPT OF NATURAL RESOURCES', 'FISH WILDLIFE',
        'COUNTY', 'CITY OF',
    ]

    def is_government_owner(name):
        upper = name.upper().strip()
        return any(pat in upper for pat in GOV_PATTERNS)

    # Build spatial index for cadastral parcels
    print(f"  Building spatial index...")
    cad_sindex = cadastral.sindex

    # For each target parcel, find all adjacent cadastral parcels
    print(f"  Checking enclosure for each parcel...")
    enclosed_flags = []
    enclosing_owners = []

    for i, (idx, row) in enumerate(target.iterrows()):
        # Buffer the state parcel slightly (50m) to catch adjacent owners
        buffered = row.geometry.buffer(50)

        # Find candidate cadastral parcels via spatial index
        candidate_idxs = list(cad_sindex.intersection(buffered.bounds))
        if not candidate_idxs:
            enclosed_flags.append(False)
            enclosing_owners.append('')
            continue

        candidates = cadastral.iloc[candidate_idxs]

        # Filter to parcels that actually intersect the buffer
        touching = candidates[candidates.geometry.intersects(buffered)]

        # Remove any with null owner
        touching = touching[touching['OwnerName'].notna() & (touching['OwnerName'] != '')]

        if len(touching) == 0:
            enclosed_flags.append(False)
            enclosing_owners.append('')
        else:
            unique_owners = touching['OwnerName'].str.upper().str.strip().unique()
            if len(unique_owners) == 1 and not is_government_owner(unique_owners[0]):
                enclosed_flags.append(True)
                enclosing_owners.append(touching['OwnerName'].iloc[0])
            else:
                enclosed_flags.append(False)
                enclosing_owners.append('')

        if (i + 1) % 500 == 0:
            enclosed_so_far = sum(enclosed_flags)
            print(f"    {i + 1}/{len(target)}... ({enclosed_so_far} enclosed)")

    state['enclosed'] = False
    state['enclosing_owner'] = ''
    state.loc[target.index, 'enclosed'] = enclosed_flags
    state.loc[target.index, 'enclosing_owner'] = enclosing_owners

    enclosed_count = sum(enclosed_flags)
    print(f"\n  Enclosed by single owner: {enclosed_count:,} of {len(target):,}")

    if enclosed_count > 0:
        enclosed_state = state[state['enclosed'] == True]
        total_enclosed_acres = enclosed_state['area_acres'].sum() if 'area_acres' in enclosed_state.columns else 0
        print(f"  Enclosed acres: {total_enclosed_acres:,.0f}")

        # Top enclosing owners
        print(f"\n  TOP ENCLOSING OWNERS:")
        owner_summary = enclosed_state.groupby('enclosing_owner').agg(
            count=('enclosed', 'count'),
            acres=('area_acres', 'sum') if 'area_acres' in enclosed_state.columns else ('enclosed', 'count'),
        ).sort_values('count', ascending=False).head(15)
        for owner, row in owner_summary.iterrows():
            acres_str = f", {row['acres']:,.0f} acres" if 'acres' in row.index else ""
            print(f"    {owner}: {int(row['count'])} parcels{acres_str}")

    return state


# ---------------------------------------------------------------------------
# Phase 4: Enrich with metadata and export
# ---------------------------------------------------------------------------
def enrich_and_export(state, lands, roads):
    """
    Add nearest road name, access_via chain info, county.
    Export to GeoPackage.
    """
    print_header("PHASE 4: ENRICHING & EXPORTING")

    # --- Nearest road ---
    print(f"  Finding nearest road for {len(state):,} state parcels...")
    road_tree = STRtree(roads.geometry.values)

    nearest_roads = []
    counties = []
    for i, (idx, row) in enumerate(state.iterrows()):
        nearest_idx = road_tree.nearest(row.geometry)
        road_row = roads.iloc[nearest_idx]
        name = road_row.get('road_name', '') or road_row.get('St_Name', '')
        nearest_roads.append(name if name else 'Unnamed Road')
        counties.append(road_row.get('county', '') or road_row.get('County_L', ''))
        if (i + 1) % 1000 == 0:
            print(f"    {i + 1}/{len(state)}...")

    state['nearest_road'] = nearest_roads
    state['county'] = counties

    # --- Access via ---
    print("  Determining access chain type...")

    def get_access_via(row):
        if row['access_status'] != 'accessible':
            return ''
        if row.get('touches_road', False):
            return 'direct'
        # Find adjacent non-state public land types in same component
        comp_members = lands[lands['component_id'] == row['component_id']]
        road_touchers = comp_members[comp_members.get('touches_road', pd.Series(dtype=bool)) == True]
        if len(road_touchers) > 0:
            categories = road_touchers['land_category'].unique()
            non_state = [c for c in categories if c not in config.STATE_OWNER_CATEGORIES]
            if non_state:
                return ', '.join(sorted(non_state))
            return 'other STATE'
        return 'chain'

    state['access_via'] = state.apply(get_access_via, axis=1)

    # --- Round values ---
    state['gap_ft'] = state['gap_ft'].round(1)
    if 'area_acres' in state.columns:
        state['area_acres'] = state['area_acres'].round(1)

    # --- Export ---
    output_cols = [
        'access_status', 'gap_ft', 'nearest_road', 'access_via',
        'county', 'area_acres', 'land_owner', 'land_category',
        'component_id', 'enclosed', 'enclosing_owner', 'geometry',
    ]
    output_cols = [c for c in output_cols if c in state.columns]
    output = state[output_cols].copy()

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    outpath = config.RESULTS_DIR / "state_access.gpkg"
    output.to_file(outpath, driver="GPKG")
    print(f"\n  Saved: {outpath} ({len(output):,} parcels)")

    # --- Summary ---
    print(f"\n  STATE TRUST LAND ACCESS SUMMARY")
    print(f"  {'=' * 50}")
    for status in ['accessible', 'near_miss', 'landlocked']:
        subset = output[output['access_status'] == status]
        acres = subset['area_acres'].sum() if 'area_acres' in subset.columns else 0
        print(f"  {status.upper():>12}: {len(subset):>6,} parcels "
              f"({acres:>12,.0f} acres)")

    if 'enclosed' in output.columns:
        enclosed = output[output['enclosed'] == True]
        enclosed_acres = enclosed['area_acres'].sum() if 'area_acres' in enclosed.columns else 0
        print(f"  {'ENCLOSED':>12}: {len(enclosed):>6,} parcels "
              f"({enclosed_acres:>12,.0f} acres)  [subset of landlocked/near-miss]")

    total_acres = output['area_acres'].sum() if 'area_acres' in output.columns else 0
    accessible_acres = output[output['access_status'] == 'accessible']['area_acres'].sum() \
        if 'area_acres' in output.columns else 0
    if total_acres > 0:
        print(f"\n  Total state land: {total_acres:,.0f} acres")
        print(f"  Accessible: {accessible_acres / total_acres * 100:.1f}%")

    # Top landlocked counties
    landlocked = output[output['access_status'].isin(['landlocked', 'near_miss'])]
    if len(landlocked) > 0 and 'county' in landlocked.columns:
        print(f"\n  TOP LANDLOCKED COUNTIES:")
        county_summary = landlocked.groupby('county').agg(
            count=('access_status', 'count'),
            acres=('area_acres', 'sum'),
        ).sort_values('acres', ascending=False).head(15)
        for county, row in county_summary.iterrows():
            print(f"    {county}: {int(row['count'])} parcels, "
                  f"{row['acres']:,.0f} acres")

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ensure_dirs()
    print_header("STATE TRUST LAND CONNECTIVITY ANALYSIS")

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

    # Phase 1
    G, component_map, components = build_adjacency_graph(lands)

    # Phase 2
    accessible_components = mark_road_accessible(
        lands, roads, component_map, components
    )

    # Phase 3
    state = classify_state_parcels(lands, accessible_components, roads)

    # Phase 3b — detect single-owner enclosure
    cadastral_path = config.DATA_DIR / "parcels" / "Montana_Parcels.gdb"
    state = detect_enclosed(state, cadastral_path)

    # Phase 4
    enrich_and_export(state, lands, roads)

    print_header("ANALYSIS COMPLETE")
    print(f"  Results: {config.RESULTS_DIR / 'state_access.gpkg'}")
    print(f"  Next: python 06_convert_for_web.py")


if __name__ == "__main__":
    main()
