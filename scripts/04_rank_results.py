#!/usr/bin/env python3
"""
Step 4: Rank and prioritize opportunities.

Scoring factors:
- Gap distance (smaller = better)
- Land type priority (BLM/State > USFS)
- Land parcel size (larger isolated parcels = more valuable)
- Multiple road segments near same parcel (corridor opportunities)

Deduplicates to find unique access opportunities (not just segments).
"""
import geopandas as gpd
import pandas as pd
import numpy as np

import config
from utils import ensure_dirs, print_header


def load_raw_results():
    """Load raw analysis results."""
    path = config.RESULTS_DIR / "raw_opportunities.gpkg"
    if not path.exists():
        print("⚠  Raw results not found! Run 03_buffer_analysis.py first.")
        return None
    
    gdf = gpd.read_file(path)
    print(f"Loaded {len(gdf):,} raw opportunities")
    return gdf


def score_opportunities(gdf):
    """
    Score each opportunity based on multiple factors.
    Higher score = more valuable/actionable opportunity.
    """
    print_header("SCORING OPPORTUNITIES")
    
    scores = pd.DataFrame(index=gdf.index)
    
    # 1. Gap distance score (0-40 points)
    # Closer = better. Confirmed access (gap < 0) gets max points.
    max_gap = config.NEAR_MISS_THRESHOLD_FT
    scores['gap_score'] = np.clip(
        40 * (1 - gdf['gap_ft'].clip(lower=-30) / max_gap),
        0, 40
    )
    # Bonus for confirmed intersection
    scores.loc[gdf['buffer_intersects'] == True, 'gap_score'] = 40
    
    # 2. Land type priority score (0-20 points)
    scores['land_score'] = gdf['land_category'].map(config.LAND_PRIORITY).fillna(2)
    scores['land_score'] = scores['land_score'] * 2  # Scale to 0-20
    
    # 3. Parcel size score (0-20 points)
    # Larger parcels = more land potentially unlocked
    scores['size_score'] = np.clip(
        20 * np.log1p(gdf['land_area_acres']) / np.log1p(10000),
        0, 20
    )
    
    # 4. Isolation bonus (0-20 points)
    # Approximate: BLM and State parcels are more likely to be isolated
    # Full isolation analysis would need Phase 2
    isolation_bonus = {
        'BLM': 15, 'STATE': 15, 'FWP': 10, 'USFWS': 10,
        'USFS': 5, 'BOR': 5, 'NPS': 3, 'OTHER_FEDERAL': 5, 'UNKNOWN': 0
    }
    scores['isolation_score'] = gdf['land_category'].map(isolation_bonus).fillna(0)
    
    # Total score
    gdf['score'] = (scores['gap_score'] + scores['land_score'] + 
                    scores['size_score'] + scores['isolation_score'])
    
    # Add component scores for transparency
    gdf['gap_score'] = scores['gap_score'].round(1)
    gdf['land_score'] = scores['land_score'].round(1)
    gdf['size_score'] = scores['size_score'].round(1)
    gdf['isolation_score'] = scores['isolation_score'].round(1)
    
    gdf['score'] = gdf['score'].round(1)
    
    print(f"  Score range: {gdf['score'].min():.0f} — {gdf['score'].max():.0f}")
    print(f"  Mean score: {gdf['score'].mean():.1f}")
    
    return gdf


def deduplicate_opportunities(gdf):
    """
    Group nearby opportunities to avoid counting the same access point 
    multiple times from different road segments.
    
    Groups by: same land parcel + road segments within 500ft of each other.
    Keeps the highest-scoring opportunity from each group.
    """
    print_header("DEDUPLICATING OPPORTUNITIES")
    
    # Simple dedup: for each unique land parcel, keep the best opportunity
    # (More sophisticated spatial clustering could be added later)
    
    best_per_parcel = (
        gdf.sort_values('score', ascending=False)
        .groupby('land_idx')
        .first()
        .reset_index()
    )
    
    print(f"  {len(gdf):,} raw → {len(best_per_parcel):,} unique land parcels")
    
    # Also create a "per road" view — best land parcel for each road segment
    best_per_road = (
        gdf.sort_values('score', ascending=False)
        .groupby('road_idx')
        .first()
        .reset_index()
    )
    print(f"  {len(best_per_road):,} unique road segments with nearby public land")
    
    # Convert back to GeoDataFrame
    # Geometry column may be 'closest_point' (from analysis) or 'geometry' (from GPKG load)
    geom_col = 'closest_point' if 'closest_point' in best_per_parcel.columns else 'geometry'
    best_per_parcel = gpd.GeoDataFrame(
        best_per_parcel, geometry=geom_col, crs=config.TARGET_CRS
    )
    
    return best_per_parcel


def add_lat_lon(gdf):
    """Add lat/lon columns for easy reference."""
    gdf_4326 = gdf.to_crs("EPSG:4326")
    gdf['latitude'] = gdf_4326.geometry.y.round(6)
    gdf['longitude'] = gdf_4326.geometry.x.round(6)
    return gdf


def generate_summaries(gdf):
    """Generate summary statistics by county and land type."""
    print_header("GENERATING SUMMARIES")
    
    # Overall summary
    confirmed = gdf[gdf['buffer_intersects'] == True]
    near_miss = gdf[gdf['buffer_intersects'] == False]
    
    print(f"\n  STATEWIDE SUMMARY")
    print(f"  Total unique opportunities: {len(gdf):,}")
    print(f"  Confirmed access points: {len(confirmed):,}")
    print(f"  Near-miss opportunities: {len(near_miss):,}")
    print(f"  Average gap (near-miss): {near_miss['gap_ft'].mean():.0f} ft")
    
    # By land category
    print(f"\n  BY LAND TYPE:")
    for cat in sorted(gdf['land_category'].unique()):
        cat_data = gdf[gdf['land_category'] == cat]
        cat_conf = cat_data[cat_data['buffer_intersects'] == True]
        cat_near = cat_data[cat_data['buffer_intersects'] == False]
        print(f"    {cat}: {len(cat_conf)} confirmed, {len(cat_near)} near-miss "
              f"(avg gap: {cat_near['gap_ft'].mean():.0f}ft)" if len(cat_near) > 0 
              else f"    {cat}: {len(cat_conf)} confirmed, 0 near-miss")
    
    # By county
    if 'county' in gdf.columns:
        print(f"\n  TOP COUNTIES BY OPPORTUNITY COUNT:")
        county_summary = gdf.groupby('county').agg(
            total=('score', 'count'),
            confirmed=('buffer_intersects', 'sum'),
            avg_score=('score', 'mean'),
            min_gap=('gap_ft', 'min'),
            best_score=('score', 'max'),
        ).sort_values('total', ascending=False)
        
        for county, row in county_summary.head(30).iterrows():
            print(f"    {county}: {int(row['total'])} opportunities, "
                  f"{int(row['confirmed'])} confirmed, "
                  f"avg score: {row['avg_score']:.0f}, "
                  f"min gap: {row['min_gap']:.0f}ft")
        
        # Save county summaries
        outpath = config.RESULTS_DIR / "county_summaries" / "county_summary.csv"
        county_summary.to_csv(outpath)
        print(f"\n  Saved county summary: {outpath}")
    
    # Top 50 opportunities
    print(f"\n  TOP 50 OPPORTUNITIES:")
    top50 = gdf.nlargest(50, 'score')
    for i, (_, row) in enumerate(top50.iterrows(), 1):
        status = "✓ ACCESS" if row['buffer_intersects'] else f"gap: {row['gap_ft']:.0f}ft"
        county_str = f" ({row['county']})" if 'county' in row and row['county'] else ""
        print(f"    {i:2d}. [{row['score']:.0f}] {row['land_category']} "
              f"- {row.get('land_name', 'unnamed')}{county_str} "
              f"- {status} "
              f"- {row['land_area_acres']:,.0f}ac "
              f"- road: {row.get('road_name', 'unnamed')}")


def main():
    ensure_dirs()
    
    gdf = load_raw_results()
    if gdf is None:
        return
    
    gdf = score_opportunities(gdf)
    gdf = deduplicate_opportunities(gdf)
    gdf = add_lat_lon(gdf)
    
    # Sort by score
    gdf = gdf.sort_values('score', ascending=False).reset_index(drop=True)
    
    # Save ranked results
    outpath = config.RESULTS_DIR / "ranked_opportunities.gpkg"
    gdf.to_file(outpath, driver="GPKG")
    print(f"\n  Saved ranked results: {outpath}")
    
    generate_summaries(gdf)
    
    print_header("RANKING COMPLETE")
    print(f"""
    Ranked results: {config.RESULTS_DIR / 'ranked_opportunities.gpkg'}
    
    Next: python 05_export_results.py
    """)


if __name__ == "__main__":
    main()
