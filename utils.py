"""
Shared utility functions for the Montana Public Land Access Pipeline.
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import Optional, Union
import config


def load_geodata(path: Union[str, Path], layer: Optional[str] = None) -> gpd.GeoDataFrame:
    """
    Load geospatial data from various formats (.shp, .geojson, .gdb, .gpkg).
    If path is a directory, attempts to find a shapefile or geodatabase inside.
    """
    path = Path(path)
    
    if path.is_dir():
        # Check for .gdb first (preferred for multi-layer data)
        gdbs = list(path.glob('*.gdb'))
        if gdbs:
            path = gdbs[0]
            print(f"  Found geodatabase: {path.name}")
        else:
            # Look for common geospatial files in the directory
            for ext in ['.shp', '.geojson', '.json', '.gpkg']:
                files = list(path.glob(f'*{ext}'))
                if files:
                    path = files[0]
                    print(f"  Found: {path.name}")
                    break
    
    if not path.exists():
        raise FileNotFoundError(f"Data not found at: {path}")
    
    print(f"  Loading: {path}")
    
    if str(path).endswith('.gdb'):
        if layer:
            gdf = gpd.read_file(path, layer=layer)
        else:
            import fiona
            layers = fiona.listlayers(str(path))
            print(f"  Available layers: {layers}")
            gdf = gpd.read_file(path, layer=layers[0])
    else:
        gdf = gpd.read_file(path)
    
    print(f"  Loaded {len(gdf):,} features")
    print(f"  CRS: {gdf.crs}")
    return gdf


def reproject(gdf: gpd.GeoDataFrame, target_crs: str = None) -> gpd.GeoDataFrame:
    """Reproject to target CRS (default: Montana State Plane)."""
    if target_crs is None:
        target_crs = config.TARGET_CRS
    if gdf.crs is None:
        print("  WARNING: No CRS set, assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    if str(gdf.crs) != target_crs:
        print(f"  Reprojecting from {gdf.crs} to {target_crs}")
        gdf = gdf.to_crs(target_crs)
    return gdf


def ft_to_m(feet: float) -> float:
    """Convert feet to meters."""
    return feet * 0.3048


def m_to_ft(meters: float) -> float:
    """Convert meters to feet."""
    return meters / 0.3048


def classify_land_owner(owner_value: str) -> str:
    """
    Classify a land ownership value into a standard category.
    Returns the category key (BLM, USFS, STATE, etc.) or 'UNKNOWN'.
    """
    if pd.isna(owner_value):
        return "UNKNOWN"
    
    owner_upper = str(owner_value).upper().strip()
    
    for category, values in config.PUBLIC_LAND_OWNERS.items():
        for v in values:
            if v.upper() in owner_upper or owner_upper in v.upper():
                return category
    
    return "UNKNOWN"


def get_county_from_geometry(gdf: gpd.GeoDataFrame, counties_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Spatial join to assign county names to features."""
    return gpd.sjoin(gdf, counties_gdf[['geometry', 'NAME']], how='left', predicate='intersects')


def ensure_dirs():
    """Create output directories if they don't exist."""
    for d in [config.OUTPUT_DIR, config.PREPPED_DIR, config.RESULTS_DIR,
              config.RESULTS_DIR / "county_summaries"]:
        d.mkdir(parents=True, exist_ok=True)


def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_fields(gdf: gpd.GeoDataFrame, name: str):
    """Print field names and sample values for inspection."""
    print(f"\n--- {name} ---")
    print(f"Fields ({len(gdf.columns)}): {list(gdf.columns)}")
    print(f"Shape: {len(gdf):,} rows")
    print(f"CRS: {gdf.crs}")
    print(f"Geometry type: {gdf.geometry.type.value_counts().to_dict()}")
    print(f"\nSample values (first 3 rows):")
    for col in gdf.columns:
        if col != 'geometry':
            vals = gdf[col].head(3).tolist()
            unique = gdf[col].nunique()
            print(f"  {col}: {vals}  ({unique} unique)")
