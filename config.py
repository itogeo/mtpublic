"""
Configuration for Montana Public Land Access Analysis Pipeline.

IMPORTANT: Run 01_inspect_data.py first, then update the field name 
constants below to match your actual data.
"""
from pathlib import Path

# =============================================================================
# DIRECTORY PATHS
# =============================================================================
PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"

# Input data paths — update these to match your downloaded files
# These can be .shp, .geojson, .gdb, etc.
PUBLIC_LANDS_PATH = DATA_DIR / "public_lands"  # directory or file
ROADS_PATH = DATA_DIR / "roads"                # directory or file
PLSS_PATH = DATA_DIR / "plss"                  # directory or file
GALLATIN_ROADS_PATH = DATA_DIR / "gallatin" / "roads" / "roads.shp"
GALLATIN_PARCELS_PATH = DATA_DIR / "gallatin" / "parcels" / "parcels.shp"

# Intermediate/output paths
PREPPED_DIR = OUTPUT_DIR / "prepped"
RESULTS_DIR = OUTPUT_DIR / "results"

# =============================================================================
# COORDINATE REFERENCE SYSTEM
# =============================================================================
# Montana State Plane NAD83 (meters) — good for statewide analysis
TARGET_CRS = "EPSG:32100"

# =============================================================================
# BUFFER PARAMETERS
# =============================================================================
# MCA 7-14-2112: 60-foot statutory width = 30 feet each side of centerline
BUFFER_DISTANCE_FT = 30
BUFFER_DISTANCE_M = BUFFER_DISTANCE_FT * 0.3048  # 9.144 meters

# Maximum gap (in feet) to flag as a near-miss opportunity
NEAR_MISS_THRESHOLD_FT = 100
NEAR_MISS_THRESHOLD_M = NEAR_MISS_THRESHOLD_FT * 0.3048  # 30.48 meters

# =============================================================================
# FIELD NAME MAPPING
# =============================================================================
# These will vary depending on your data source.
# Run 01_inspect_data.py to see available fields, then update here.

# --- MSDI Transportation Framework fields ---
# Field names confirmed from 01_inspect_data.py (EPSG:6514 source CRS)
ROAD_NAME_FIELD = "St_Name"        # Primary street name
ROAD_CLASS_FIELD = "RoadClass"     # Local, Secondary, Primary, Private, etc.
ROAD_OWNER_FIELD = "Ownership"     # County, Public, State, City, Private, Federal, Tribal (often NULL)
ROAD_COUNTY_FIELD = "County_L"     # County name (left side), e.g. "Gallatin County"

# Values that indicate a county road in the Ownership field
# NOTE: Ownership is NULL for ~83% of records. We use both Ownership AND RoadClass
# to catch county roads. The prep script will combine these filters.
COUNTY_ROAD_VALUES = [
    "County",   # Explicit county ownership (2,799 in 50k sample)
    "Public",   # Public roads likely include county (2,392 in 50k sample)
]

# Also filter by RoadClass when Ownership is NULL
# "Local" roads are overwhelmingly county-maintained in Montana
COUNTY_ROAD_CLASSES = ["Local", "Secondary"]

# --- Public Lands fields ---
# Confirmed from 01_inspect_data.py (31,088 features, EPSG:6514 source CRS)
# Only fields: OWNER, Acreage, Shape_Length, Shape_Area, geometry
LAND_OWNER_FIELD = "OWNER"         # Full text: "US Bureau of Land Management", etc.
LAND_NAME_FIELD = "OWNER"          # No separate name field; reuse OWNER for display
LAND_TYPE_FIELD = "OWNER"          # No separate type field; classify from OWNER

# Values indicating public land ownership — exact strings from MSDI data
PUBLIC_LAND_OWNERS = {
    "BLM": ["US Bureau of Land Management"],
    "USFS": ["US Forest Service"],
    "STATE": ["Montana State Trust Lands", "State of Montana",
              "Montana Department of Natural Resources and Conservation"],
    "FWP": ["Montana Fish, Wildlife, and Parks"],
    "USFWS": ["US Fish and Wildlife Service"],
    "BOR": ["US Bureau of Reclamation"],
    "NPS": ["National Park Service"],
    "DOD": ["US Department of Defense"],
    "USACE": ["US Army Corps of Engineers"],
    "USDA": ["US Department of Agriculture"],
    "OTHER_FEDERAL": ["US Government"],
    "MDT": ["Montana Department of Transportation"],
    "UNIVERSITY": ["Montana University System"],
    "CORRECTIONS": ["Montana Department of Corrections"],
    "LOCAL": ["County Government", "City Government", "Local Government"],
}

# Priority scoring for land types (higher = more valuable to flag)
# BLM and State Trust are highest because they're often isolated/inaccessible
LAND_PRIORITY = {
    "BLM": 10,       # Often isolated/inaccessible — highest value
    "STATE": 9,       # State trust lands frequently landlocked
    "FWP": 7,         # Wildlife mgmt areas
    "USFWS": 6,       # Refuges
    "USFS": 5,        # Often already accessible via forest roads
    "DOD": 4,
    "USACE": 4,
    "BOR": 4,
    "USDA": 4,
    "OTHER_FEDERAL": 4,
    "NPS": 3,         # Usually well-managed access
    "MDT": 2,         # Transportation corridors, not hunting/rec land
    "UNIVERSITY": 2,
    "CORRECTIONS": 1,
    "LOCAL": 1,        # City/county land — usually already accessible
    "UNKNOWN": 2,
}

# =============================================================================
# PROCESSING PARAMETERS
# =============================================================================
# Process in chunks to manage memory for statewide analysis
CHUNK_SIZE = 50000  # rows per chunk for large datasets

# Simplify geometries for faster processing (tolerance in meters)
# Set to None to skip simplification
SIMPLIFY_TOLERANCE = 1.0  # 1 meter — negligible impact on 30ft buffer accuracy

# Number of parallel workers (set to 1 for debugging)
N_WORKERS = 1

# =============================================================================
# OUTPUT OPTIONS
# =============================================================================
# Minimum gap distance to include in output (filters out obvious adjacencies)
MIN_GAP_FT = -30   # Negative = buffer overlaps (definite access)
MAX_GAP_FT = 100   # Only flag gaps up to this distance

# Include road segments that already touch public land (gap <= 0)?
INCLUDE_CONFIRMED_ACCESS = True

# Export formats
EXPORT_CSV = True
EXPORT_GEOJSON = True
EXPORT_GPKG = True  # GeoPackage — good for QGIS
