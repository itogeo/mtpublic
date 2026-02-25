#!/usr/bin/env python3
"""
Step 7: Download and process statewide cadastral parcels for vector tiles.

Downloads the Montana Parcels GDB from the State Library FTP, processes
individual parcels and dissolved ownership blocks, then converts to
PMTiles using tippecanoe for use in the web map.

Output: webapp/data/parcels.pmtiles (two layers: parcels + ownership_blocks)
"""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import geopandas as gpd
import pandas as pd

import config
from utils import print_header

# Source data
PARCELS_FTP = 'https://ftpgeoinfo.msl.mt.gov/Data/Spatial/MSDI/Cadastral/Parcels/Statewide/MTParcels_GDB.zip'
PARCELS_DIR = config.DATA_DIR / 'parcels'

# Output
WEBAPP_DATA = Path(__file__).parent / 'webapp' / 'data'

# Fields to keep (minimizes GeoJSON size)
KEEP_FIELDS = [
    'OwnerName', 'PropType', 'TotalAcres', 'TotalValue',
    'CountyName', 'AddressLine1', 'CityStateZip', 'GISAcres',
]


def download_parcels():
    """Download statewide parcels GDB from Montana FTP."""
    PARCELS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PARCELS_DIR / 'MTParcels_GDB.zip'

    if zip_path.exists():
        print(f"    Already downloaded: {zip_path.name} ({zip_path.stat().st_size / 1e6:.0f} MB)")
        return zip_path

    print(f"    Downloading from MT State Library FTP...")
    print(f"    URL: {PARCELS_FTP}")

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(downloaded / total_size * 100, 100) if total_size > 0 else 0
        mb = downloaded / 1e6
        print(f"\r    {mb:.0f} MB ({pct:.0f}%)", end='', flush=True)

    urlretrieve(PARCELS_FTP, zip_path, reporthook=progress)
    print(f"\n    Downloaded: {zip_path.stat().st_size / 1e6:.0f} MB")
    return zip_path


def extract_parcels(zip_path):
    """Extract the GDB from the zip file."""
    # Check if already extracted
    gdbs = list(PARCELS_DIR.glob('*.gdb'))
    if gdbs:
        print(f"    Already extracted: {gdbs[0].name}")
        return gdbs[0]

    print(f"    Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(PARCELS_DIR)

    gdbs = list(PARCELS_DIR.glob('*.gdb'))
    if not gdbs:
        # Check subdirectories
        gdbs = list(PARCELS_DIR.rglob('*.gdb'))
    if not gdbs:
        raise FileNotFoundError("No .gdb found after extraction")

    print(f"    Extracted: {gdbs[0].name}")
    return gdbs[0]


def owner_hash(name):
    """Create a short hash of owner name for fast client-side matching."""
    if pd.isna(name) or not name:
        return '0'
    return hashlib.md5(name.encode()).hexdigest()[:8]


def process_parcels(gdb_path):
    """Load parcels, export individual + dissolved ownership blocks."""
    print("\n  [1/3] Loading parcels from GDB...")
    gdf = gpd.read_file(gdb_path)
    print(f"    Loaded {len(gdf):,} parcels")
    print(f"    CRS: {gdf.crs}")

    # Keep only needed fields
    available = [f for f in KEEP_FIELDS if f in gdf.columns]
    missing = [f for f in KEEP_FIELDS if f not in gdf.columns]
    if missing:
        print(f"    Missing fields (skipped): {missing}")
    gdf = gdf[available + ['geometry']].copy()

    # Reproject to WGS84
    print("    Reprojecting to EPSG:4326...")
    gdf = gdf.to_crs(epsg=4326)

    # Remove invalid/empty geometries
    valid = gdf.geometry.is_valid & ~gdf.geometry.is_empty
    dropped = (~valid).sum()
    if dropped:
        print(f"    Dropped {dropped:,} invalid/empty geometries")
        gdf = gdf[valid].copy()

    # Simplify geometries (~5m tolerance at Montana latitudes)
    print("    Simplifying geometries...")
    gdf['geometry'] = gdf.geometry.simplify(0.00005)

    # Add owner hash for client-side matching
    gdf['owner_id'] = gdf['OwnerName'].apply(owner_hash)

    # Round numeric fields
    for col in ['TotalAcres', 'GISAcres']:
        if col in gdf.columns:
            gdf[col] = gdf[col].round(1)
    for col in ['TotalValue']:
        if col in gdf.columns:
            gdf[col] = gdf[col].fillna(0).astype(int)

    return gdf


def export_individual_parcels(gdf, output_path):
    """Export individual parcels as compact GeoJSON."""
    print("\n  [2/3] Exporting individual parcels...")
    geojson = json.loads(gdf.to_json())

    with open(output_path, 'w') as f:
        json.dump(geojson, f, separators=(',', ':'))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"    {output_path.name}: {size_mb:.1f} MB ({len(gdf):,} features)")
    return output_path


def export_ownership_blocks(gdf, output_path):
    """Dissolve parcels by owner within each county, export as GeoJSON."""
    print("\n  [3/3] Dissolving parcels by owner (per county)...")

    results = []
    counties = gdf['CountyName'].dropna().unique() if 'CountyName' in gdf.columns else ['ALL']

    for i, county in enumerate(sorted(counties)):
        if county == 'ALL':
            chunk = gdf
        else:
            chunk = gdf[gdf['CountyName'] == county]

        if len(chunk) == 0:
            continue

        try:
            dissolved = chunk.dissolve(
                by='owner_id',
                sort=False,
                aggfunc={
                    'OwnerName': 'first',
                    'TotalAcres': 'sum',
                    'CountyName': 'first',
                    **({'PropType': 'first'} if 'PropType' in chunk.columns else {}),
                },
            )
            dissolved['parcel_count'] = chunk.groupby('owner_id').size().values
            dissolved = dissolved.reset_index()
            results.append(dissolved)
        except Exception as e:
            print(f"    Warning: {county} dissolve failed: {e}")
            continue

        if (i + 1) % 10 == 0:
            print(f"    Processed {i + 1}/{len(counties)} counties...")

    all_dissolved = pd.concat(results, ignore_index=True)
    all_dissolved = gpd.GeoDataFrame(all_dissolved, geometry='geometry', crs='EPSG:4326')

    # Round acres
    if 'TotalAcres' in all_dissolved.columns:
        all_dissolved['TotalAcres'] = all_dissolved['TotalAcres'].round(1)

    print(f"    Dissolved: {len(gdf):,} parcels → {len(all_dissolved):,} ownership blocks")

    geojson = json.loads(all_dissolved.to_json())
    with open(output_path, 'w') as f:
        json.dump(geojson, f, separators=(',', ':'))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"    {output_path.name}: {size_mb:.1f} MB ({len(all_dissolved):,} features)")
    return output_path


def build_pmtiles(parcels_geojson, ownership_geojson, output_pmtiles):
    """Run tippecanoe to create PMTiles with both layers."""
    print("\n  Building PMTiles with tippecanoe...")

    if not shutil.which('tippecanoe'):
        print("    ERROR: tippecanoe not found. Install with: brew install tippecanoe")
        return False

    parcels_tmp = '/tmp/mt_parcels.pmtiles'
    ownership_tmp = '/tmp/mt_ownership.pmtiles'

    # Individual parcels (zoom 10-14)
    print("    Creating parcels layer (z10-14)...")
    subprocess.run([
        'tippecanoe',
        '-o', parcels_tmp,
        '-Z10', '-z14',
        '-l', 'parcels',
        '--drop-densest-as-needed',
        '--extend-zooms-if-still-dropping',
        '--no-feature-limit',
        '--force',
        str(parcels_geojson),
    ], check=True)

    # Ownership blocks (zoom 8-14)
    print("    Creating ownership_blocks layer (z8-14)...")
    subprocess.run([
        'tippecanoe',
        '-o', ownership_tmp,
        '-Z8', '-z14',
        '-l', 'ownership_blocks',
        '--coalesce-densest-as-needed',
        '--force',
        str(ownership_geojson),
    ], check=True)

    # Merge into one PMTiles file
    print("    Merging layers...")
    subprocess.run([
        'tile-join',
        '-o', str(output_pmtiles),
        '--no-tile-size-limit',
        '--force',
        parcels_tmp,
        ownership_tmp,
    ], check=True)

    # Cleanup
    Path(parcels_tmp).unlink(missing_ok=True)
    Path(ownership_tmp).unlink(missing_ok=True)

    size_mb = output_pmtiles.stat().st_size / (1024 * 1024)
    print(f"    PMTiles: {output_pmtiles.name} ({size_mb:.1f} MB)")
    return True


def main():
    print_header("PROCESSING STATEWIDE CADASTRAL PARCELS")

    WEBAPP_DATA.mkdir(parents=True, exist_ok=True)

    # Download
    print("\n  Downloading statewide parcels...")
    zip_path = download_parcels()

    # Extract
    gdb_path = extract_parcels(zip_path)

    # Process
    gdf = process_parcels(gdb_path)

    # Export individual parcels
    parcels_path = WEBAPP_DATA / 'parcels_individual.geojson'
    export_individual_parcels(gdf, parcels_path)

    # Export dissolved ownership blocks
    ownership_path = WEBAPP_DATA / 'ownership_blocks.geojson'
    export_ownership_blocks(gdf, ownership_path)

    # Build PMTiles
    pmtiles_path = WEBAPP_DATA / 'parcels.pmtiles'
    success = build_pmtiles(parcels_path, ownership_path, pmtiles_path)

    if success:
        # Clean up intermediate GeoJSON (large files)
        parcels_path.unlink(missing_ok=True)
        ownership_path.unlink(missing_ok=True)
        print(f"\n  Done! PMTiles at: {pmtiles_path}")
        print(f"  Test: cd webapp && python -m http.server 8888")
    else:
        print(f"\n  GeoJSON exported. Install tippecanoe to create PMTiles.")


if __name__ == '__main__':
    main()
