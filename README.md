# Montana Public Land Access Analysis Pipeline

## Overview

This project identifies locations across Montana where county road legal easements 
(30 feet from centerline per MCA 7-14-2112) may provide unrecognized access to 
public lands (BLM, USFS, State Trust, DNRC).

The core analysis: buffer every county road by 30 feet and find where those buffers 
intersect or nearly intersect public land boundaries.

## Data Downloads Required

Before running the pipeline, download these free datasets:

### 1. MSDI Public Lands (Statewide)
- **URL**: https://msl.mt.gov/geoinfo/msdi/cadastral/
- **Direct download**: Go to Montana State Library GeoInfo → MSDI → Cadastral
- **Also try**: https://gis.data.mt.gov/ (Montana GIS Portal) — search "Public Lands"
- **What you need**: The statewide public/government lands layer showing BLM, USFS, 
  State Trust, DNRC, and other public ownership
- **Format**: Shapefile or GeoJSON
- **Place in**: `data/public_lands/`

### 2. MSDI Transportation Framework (Statewide Road Centerlines)
- **URL**: https://msl.mt.gov/geoinfo/msdi/transportation/
- **What you need**: Statewide road centerlines with road classification attributes
- **Key attributes to look for**: Road class, ownership/jurisdiction, road name
- **Format**: Shapefile or GDB
- **Place in**: `data/roads/`

### 3. CadNSDI - PLSS Grid (Township/Section boundaries)
- **URL**: https://navigator.blm.gov/home or https://gis.data.mt.gov/
- **Search**: "PLSS Montana" or "CadNSDI Montana"
- **What you need**: Township, Section, and Quarter-Section boundaries for Montana
- **Format**: Shapefile
- **Place in**: `data/plss/`

### 4. Gallatin County Data (for validation/comparison)
- **URL**: https://gis.gallatin.mt.gov/downloads/
- **Files**: roads.zip, parcels.zip
- **Place in**: `data/gallatin/`

### Alternative/Supplementary Sources
- **BLM MT Surface Management**: https://gbp-blm-egis.hub.arcgis.com/ 
  (search "Surface Management Agency" for Montana)
- **Montana Cadastral**: https://svc.mt.gov/msl/cadastral/
- **Individual County GIS**: Many counties publish road shapefiles — check county websites

## Directory Structure

```
mtpublic/
├── README.md
├── requirements.txt
├── config.py              # Paths, constants, buffer distances
├── 01_inspect_data.py     # Examine downloaded data, identify fields
├── 02_prep_data.py        # Standardize CRS, filter, clean
├── 03_buffer_analysis.py  # Core analysis — buffer roads, find intersections
├── 04_rank_results.py     # Score and prioritize opportunities
├── 05_export_results.py   # Export to GeoJSON, CSV, map-ready formats
├── utils.py               # Shared helper functions
├── data/                  # Downloaded data (not in git)
│   ├── public_lands/
│   ├── roads/
│   ├── plss/
│   └── gallatin/
└── output/                # Analysis results
    ├── opportunities.csv
    ├── opportunities.geojson
    └── county_summaries/
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download data into data/ subdirectories (see above)

# 3. Inspect your data to identify field names
python 01_inspect_data.py

# 4. Update config.py with correct field names from step 3

# 5. Prep data (standardize CRS, filter)
python 02_prep_data.py

# 6. Run buffer analysis
python 03_buffer_analysis.py

# 7. Rank results
python 04_rank_results.py

# 8. Export
python 05_export_results.py
```

## Configuration

Edit `config.py` after running `01_inspect_data.py` to set the correct field names 
for your data. The MSDI data field names may differ from what's expected — the 
inspect script will show you what's available.

## Key Parameters

- **BUFFER_DISTANCE_FT**: 30 (statutory half-width per MCA 7-14-2112)
- **NEAR_MISS_THRESHOLD_FT**: 100 (max gap to flag as opportunity)
- **TARGET_CRS**: EPSG:32100 (Montana State Plane NAD83, meters)

## Legal Basis

Montana Code Annotated 7-14-2112: County roads have a 60-foot statutory width 
(30 feet on each side of centerline) unless otherwise specified in the road 
petition or order establishing the road. This applies to roads established by 
petition through the county commission process.

## Phases

### Phase 1 (This Pipeline) — Statewide Screening
Identify every location where a county road buffer touches or nearly touches 
public land. Output ranked list of opportunities.

### Phase 2 — Validation & Enrichment  
- Cross-reference hits with PLSS to get legal descriptions
- Check which public parcels are otherwise inaccessible
- Add stream crossing analysis
- Identify corner-locked parcels

### Phase 3 — Road Petition Research
- For top opportunities, pull road petitions from county archives
- Georeference surveyed centerlines where formal surveys exist
- Compare legal vs physical road centerlines
