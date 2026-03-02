#!/usr/bin/env python3
"""
Step 1: Inspect downloaded data files.

Run this first to see what fields are available in your data,
then update config.py with the correct field names.
"""
import sys
from pathlib import Path
import geopandas as gpd

import config
from utils import load_geodata, print_header, print_fields


def inspect_directory(dir_path: Path, label: str):
    """List and inspect all geospatial files in a directory."""
    print_header(f"Inspecting: {label}")
    
    if not dir_path.exists():
        print(f"  ⚠  Directory not found: {dir_path}")
        print(f"  → Download this dataset and place it in: {dir_path}")
        return None
    
    # Find all geospatial files
    extensions = ['*.shp', '*.geojson', '*.json', '*.gpkg', '*.gdb']
    files = []
    for ext in extensions:
        files.extend(dir_path.rglob(ext))
    
    if not files:
        print(f"  ⚠  No geospatial files found in: {dir_path}")
        print(f"  Contents: {[f.name for f in dir_path.iterdir()]}")
        return None
    
    print(f"  Found {len(files)} geospatial file(s):")
    for f in files:
        print(f"    - {f.relative_to(dir_path)}")
    
    # Load and inspect the first/main file
    for f in files:
        try:
            if str(f).endswith('.gdb'):
                import fiona
                layers = fiona.listlayers(str(f))
                print(f"\n  Geodatabase layers: {layers}")
                for layer in layers[:5]:  # Inspect first 5 layers
                    print(f"\n  Loading layer: {layer}")
                    gdf = gpd.read_file(f, layer=layer, rows=100)
                    print_fields(gdf, f"{label} / {layer}")
            else:
                gdf = gpd.read_file(f, rows=100)  # Just load sample
                print_fields(gdf, label)
                return gdf
        except Exception as e:
            print(f"  ⚠  Error reading {f.name}: {e}")
    
    return None


def inspect_single_file(file_path: Path, label: str):
    """Inspect a single geospatial file."""
    print_header(f"Inspecting: {label}")
    
    if not file_path.exists():
        print(f"  ⚠  File not found: {file_path}")
        return None
    
    try:
        gdf = gpd.read_file(file_path, rows=100)
        print_fields(gdf, label)
        return gdf
    except Exception as e:
        print(f"  ⚠  Error: {e}")
        return None


def main():
    print_header("MONTANA PUBLIC LAND ACCESS — DATA INSPECTION")
    print(f"Looking for data in: {config.DATA_DIR}")
    print(f"Target CRS: {config.TARGET_CRS}")
    
    # Check what data directories exist
    print(f"\nData directory contents:")
    if config.DATA_DIR.exists():
        for item in sorted(config.DATA_DIR.iterdir()):
            marker = "📁" if item.is_dir() else "📄"
            print(f"  {marker} {item.name}")
    else:
        print(f"  ⚠  Data directory not found! Create: {config.DATA_DIR}")
        sys.exit(1)
    
    # Inspect each dataset
    roads_gdf = inspect_directory(config.ROADS_PATH, "MSDI Roads / Transportation")
    lands_gdf = inspect_directory(config.PUBLIC_LANDS_PATH, "Public Lands")
    plss_gdf = inspect_directory(config.PLSS_PATH, "PLSS Grid")
    
    # Gallatin county data (optional validation)
    if config.GALLATIN_ROADS_PATH.exists():
        inspect_single_file(config.GALLATIN_ROADS_PATH, "Gallatin County Roads")
    if config.GALLATIN_PARCELS_PATH.exists():
        inspect_single_file(config.GALLATIN_PARCELS_PATH, "Gallatin County Parcels")
    
    # Print guidance
    print_header("NEXT STEPS")
    print("""
    1. Review the field names printed above
    2. Update config.py with the correct field names:
       - ROAD_NAME_FIELD: the field containing road names
       - ROAD_OWNER_FIELD: the field indicating road jurisdiction/ownership
       - LAND_OWNER_FIELD: the field indicating land ownership agency
       
    3. Pay special attention to:
       - How county roads are identified (field name + values)
       - How public land ownership is categorized (BLM vs USFS vs State)
       - What CRS the data is in (will be reprojected to Montana State Plane)
       
    4. Then run: python 02_prep_data.py
    """)


if __name__ == "__main__":
    main()
