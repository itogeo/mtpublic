// Montana Public Land Access — Mapbox GL JS
// Public lands: Official MT State Library ArcGIS tile service
// Roads: Official MT MSDI Transportation tile service
// Parcels: PMTiles vector tiles from processed statewide data
// Opportunities: Local GeoJSON from analysis pipeline

// Register PMTiles protocol for Mapbox GL JS
try {
    const pmtilesProtocol = new pmtiles.Protocol();
    mapboxgl.addProtocol('pmtiles', pmtilesProtocol.tile);
} catch (e) {
    console.warn('PMTiles protocol not available:', e.message);
}

// ArcGIS tile export bases
const MSDI_LANDS_BASE = 'https://gisservicemt.gov/arcgis/rest/services/MSDI_Framework/PublicLands/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=png32&transparent=true&f=image';
const MSDI_ROADS_BASE = 'https://gisservicemt.gov/arcgis/rest/services/MSDI_Framework/MontanaTransportation/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=png32&transparent=true&f=image';
const DNRC_ACCESS_BASE = 'https://gis.dnrc.mt.gov/arcgis/rest/services/TLMD/AccessMap/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=png32&transparent=true&f=image';
const DNRC_TLMS_BASE = 'https://gis.dnrc.mt.gov/arcgis/rest/services/TLMD/TLMS/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=png32&transparent=true&f=image';
const MSDI_HYDRO_BASE = 'https://gisservicemt.gov/arcgis/rest/services/MSDI_Framework/Hydrography/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=png32&transparent=true&f=image';

function msdiFiltered(ownerValues) {
    const where = ownerValues.map(v => `OWNER='${v}'`).join(' OR ');
    return MSDI_LANDS_BASE + '&layerDefs=' + encodeURIComponent(JSON.stringify({"0": where}));
}

function roadFiltered(ownershipValues) {
    const where = ownershipValues.map(v => `Ownership='${v}'`).join(' OR ');
    return MSDI_ROADS_BASE + '&layerDefs=' + encodeURIComponent(JSON.stringify({"0": where}));
}

function roadClassFiltered(classValues) {
    const where = classValues.map(v => `RoadClass='${v}'`).join(' OR ');
    return MSDI_ROADS_BASE + '&layerDefs=' + encodeURIComponent(JSON.stringify({"0": where}));
}

const TILE_LAYERS = {
    // Individual MSDI land types (official MT colors)
    blm:   { label: 'BLM',                color: '#FEEA79', on: true,
             url: msdiFiltered(['US Bureau of Land Management']) },
    usfs:  { label: 'US Forest Service',   color: '#CCEBC5', on: true,
             url: msdiFiltered(['US Forest Service']) },
    state: { label: 'State Trust / DNRC',  color: '#6BCFE2', on: true,
             url: msdiFiltered(['Montana State Trust Lands','Montana Department of Natural Resources and Conservation','Montana Department of Corrections','Montana Department of Transportation','Montana Fish, Wildlife, and Parks','Montana University System','State of Montana']) },
    nps:   { label: 'National Parks',      color: '#CABDDC', on: true,
             url: msdiFiltered(['National Park Service']) },
    usfws: { label: 'US Fish & Wildlife',  color: '#7FCCA7', on: true,
             url: msdiFiltered(['US Fish and Wildlife Service']) },
    fed:   { label: 'Other Federal',       color: '#FBB4CE', on: false,
             url: msdiFiltered(['US Bureau of Reclamation','US Army Corps of Engineers','US Department of Defense','US Department of Agriculture','US Government']) },
    local: { label: 'Local Government',    color: '#9C9C9C', on: false,
             url: msdiFiltered(['City Government','County Government','Local Government']) },
    // DNRC Access overlays (split by access type)
    dnrc_public:  { label: 'DNRC Public Access',     color: '#005CE6', on: false,
             url: DNRC_ACCESS_BASE + '&layers=show:1' },
    dnrc_closed:  { label: 'DNRC No Public Access',  color: '#FF0000', on: false,
             url: DNRC_ACCESS_BASE + '&layers=show:0' },
    dnrc_special: { label: 'DNRC Special Scenario',  color: '#A900E6', on: false,
             url: DNRC_ACCESS_BASE + '&layers=show:2' },
    dnrc_rec:     { label: 'DNRC Non-Trust Rec Use',  color: '#00FFC5', on: false,
             url: DNRC_ACCESS_BASE + '&layers=show:3' },
    // DNRC Surface Tracts
    dnrc_tracts:  { label: 'DNRC Surface Tracts',    color: '#97DBF2', on: false,
             url: DNRC_TLMS_BASE + '&layers=show:0' },
};

const ROAD_LAYERS = {
    county:   { label: 'County Roads',   color: '#f8fafc', on: true,
                url: roadFiltered(['County','Public']) },
    highways: { label: 'Highways',       color: '#f97316', on: false,
                url: roadClassFiltered(['Primary','Secondary']) },
    federal:  { label: 'Federal Roads',  color: '#86efac', on: false,
                url: roadFiltered(['Federal']) },
    private:  { label: 'Private Roads',  color: '#fca5a5', on: false,
                url: roadFiltered(['Private']) },
    city:     { label: 'City Roads',     color: '#c4b5fd', on: false,
                url: roadFiltered(['City']) },
};

const WATER_LAYERS = {
    streams:     { label: 'Streams & Rivers',    color: '#38bdf8', on: false,
                   url: MSDI_HYDRO_BASE + '&layers=show:3' },
    waterbodies: { label: 'Lakes & Reservoirs',  color: '#0ea5e9', on: false,
                   url: MSDI_HYDRO_BASE + '&layers=show:5' },
};

const LAND_LABELS = {
    BLM:   'Bureau of Land Management',
    USFS:  'US Forest Service',
    STATE: 'State Trust / DNRC',
    FWP:   'Fish, Wildlife & Parks',
    USFWS: 'US Fish & Wildlife',
    NPS:   'National Park Service',
    BOR:   'Bureau of Reclamation',
    DOD:   'Dept. of Defense',
    LOCAL: 'Local Government',
};

const OPP_COLORS = {
    BLM:   '#F59E0B',
    USFS:  '#22C55E',
    STATE: '#3B82F6',
    FWP:   '#A855F7',
    USFWS: '#EC4899',
    NPS:   '#22C55E',
};

const OPP_CATEGORY_MAP = {
    'BLM': 'BLM', 'USFS': 'USFS', 'STATE': 'STATE',
    'FWP': 'FWP', 'USFWS': 'FWP', 'NPS': 'OTHER',
    'BOR': 'OTHER', 'DOD': 'OTHER', 'USACE': 'OTHER',
    'TRIBAL': 'OTHER', 'LOCAL': 'OTHER', 'UNKNOWN': 'OTHER',
    'MDT': 'OTHER', 'CORRECTIONS': 'OTHER', 'UNIVERSITY': 'OTHER',
    'USDA': 'OTHER', 'OTHER_FEDERAL': 'OTHER',
};

let map;
let allOpportunities = null;
let stateAccessData = null;
let unlockData = null;
let dnrcAccessData = null;

// ── Map init ──
// MAPBOX_TOKEN is loaded from token.js (gitignored)

function initMap() {
    document.getElementById('loading').classList.remove('hidden');
    updateLoadingText('Initializing map...');

    mapboxgl.accessToken = MAPBOX_TOKEN;
    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/outdoors-v12',
        center: [-109.5, 47.0],
        zoom: 5.8,
        maxBounds: [[-117, 43.5], [-103, 50]],
    });

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.ScaleControl({ unit: 'imperial' }), 'bottom-right');
    map.addControl(new mapboxgl.FullscreenControl(), 'top-right');

    map.on('load', loadAllData);
}

function updateLoadingText(msg) {
    const el = document.getElementById('loading-text');
    if (el) el.textContent = msg;
}

// ── Load data ──
async function loadAllData() {
    try {
        updateLoadingText('Loading access opportunities...');
        const oppsResp = await fetch('data/opportunities.geojson');
        allOpportunities = await oppsResp.json();
        allOpportunities.features.forEach(f => {
            const cat = f.properties.land_category || 'UNKNOWN';
            f.properties._category = OPP_CATEGORY_MAP[cat] || 'OTHER';
        });

        // Load state access data
        updateLoadingText('Loading state access data...');
        try {
            const stateResp = await fetch('data/state_access.geojson');
            stateAccessData = await stateResp.json();
        } catch (e) {
            console.warn('State access data not available:', e.message);
            stateAccessData = null;
        }

        // Load unlock opportunities
        updateLoadingText('Loading unlock opportunities...');
        try {
            const unlockResp = await fetch('data/unlock_opportunities.geojson');
            unlockData = await unlockResp.json();
        } catch (e) {
            console.warn('Unlock data not available:', e.message);
            unlockData = null;
        }

        // Load DNRC access data
        updateLoadingText('Loading DNRC access data...');
        try {
            const dnrcResp = await fetch('data/dnrc_access.geojson');
            dnrcAccessData = await dnrcResp.json();
        } catch (e) {
            console.warn('DNRC access data not available:', e.message);
            dnrcAccessData = null;
        }

        addAllLayers();
        populateCountyFilter();
        updateStats();
        bindFilters();
        bindSidebar();
        bindBasemap();
        bindLandToggle();
        bindRoadToggle();
        bindWaterToggle();
        bindParcelToggle();
        bindStateAccessToggle();
        bindDnrcAccessToggle();
        bindUnlockToggle();

        document.getElementById('loading').classList.add('hidden');
    } catch (err) {
        updateLoadingText('Error: ' + err.message);
    }
}

function oppColorExpr() {
    return [
        'match', ['get', 'land_category'],
        'BLM',   OPP_COLORS.BLM,
        'USFS',  OPP_COLORS.USFS,
        'STATE', OPP_COLORS.STATE,
        'FWP',   OPP_COLORS.FWP,
        'USFWS', OPP_COLORS.USFWS,
        'NPS',   OPP_COLORS.NPS,
        '#94a3b8',
    ];
}

// ── Layers ──
function addAllLayers() {
    // === 1. OFFICIAL MT TILE LAYERS (one per land type) ===
    for (const [key, layer] of Object.entries(TILE_LAYERS)) {
        map.addSource('tiles-' + key, {
            type: 'raster',
            tiles: [layer.url],
            tileSize: 512,
        });

        const tileLayerOpts = {
            id: 'tiles-' + key,
            type: 'raster',
            source: 'tiles-' + key,
            paint: { 'raster-opacity': 0.7 },
            layout: { visibility: layer.on ? 'visible' : 'none' },
        };
        if (layer.minzoom) tileLayerOpts.minzoom = layer.minzoom;
        map.addLayer(tileLayerOpts);
    }

    // === 2. ROAD TILE LAYERS ===
    for (const [key, layer] of Object.entries(ROAD_LAYERS)) {
        map.addSource('roads-' + key, {
            type: 'raster',
            tiles: [layer.url],
            tileSize: 512,
        });

        map.addLayer({
            id: 'roads-' + key,
            type: 'raster',
            source: 'roads-' + key,
            minzoom: 8,
            paint: { 'raster-opacity': 0.9 },
            layout: { visibility: layer.on ? 'visible' : 'none' },
        });
    }

    // === 2b. WATER TILE LAYERS ===
    for (const [key, layer] of Object.entries(WATER_LAYERS)) {
        map.addSource('water-' + key, {
            type: 'raster',
            tiles: [layer.url],
            tileSize: 512,
        });

        map.addLayer({
            id: 'water-' + key,
            type: 'raster',
            source: 'water-' + key,
            paint: { 'raster-opacity': 0.8 },
            layout: { visibility: layer.on ? 'visible' : 'none' },
        });
    }

    // === 3. CADASTRAL PARCELS (PMTiles vector tiles) ===
    map.addSource('parcels-vt', {
        type: 'vector',
        url: 'pmtiles://data/parcels.pmtiles',
    });

    // Ownership blocks — thick exterior borders (visible z8+)
    map.addLayer({
        id: 'ownership-borders',
        source: 'parcels-vt',
        'source-layer': 'ownership_blocks',
        type: 'line',
        minzoom: 8,
        paint: {
            'line-color': '#8B6914',
            'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.5, 12, 2.5, 14, 3],
            'line-opacity': 0.7,
        },
        layout: { visibility: 'none' },
    });

    // Individual parcels — thin interior borders (visible z10+)
    map.addLayer({
        id: 'parcel-borders',
        source: 'parcels-vt',
        'source-layer': 'parcels',
        type: 'line',
        minzoom: 10,
        paint: {
            'line-color': '#D4A574',
            'line-width': 0.5,
            'line-opacity': 0.6,
        },
        layout: { visibility: 'none' },
    });

    // Parcel fill — transparent, just for click targeting (z10+)
    map.addLayer({
        id: 'parcel-fill',
        source: 'parcels-vt',
        'source-layer': 'parcels',
        type: 'fill',
        minzoom: 10,
        paint: {
            'fill-color': '#D4A574',
            'fill-opacity': 0,
        },
        layout: { visibility: 'none' },
    });

    // Highlight layer — selected owner's parcels
    map.addLayer({
        id: 'parcel-highlight',
        source: 'parcels-vt',
        'source-layer': 'parcels',
        type: 'fill',
        minzoom: 10,
        paint: {
            'fill-color': '#F59E0B',
            'fill-opacity': 0.35,
        },
        filter: ['==', 'owner_id', ''],
        layout: { visibility: 'none' },
    });

    // Highlight border — selected owner's parcels thick outline
    map.addLayer({
        id: 'parcel-highlight-border',
        source: 'parcels-vt',
        'source-layer': 'parcels',
        type: 'line',
        minzoom: 10,
        paint: {
            'line-color': '#F59E0B',
            'line-width': 2.5,
            'line-opacity': 0.9,
        },
        filter: ['==', 'owner_id', ''],
        layout: { visibility: 'none' },
    });

    // === 4a. DNRC UNLOCKABLE PARCELS (only confirmed + near_miss) ===
    if (dnrcAccessData) {
        // Filter to only the unlockable parcels (closed + near a road)
        const unlockableDnrc = {
            type: 'FeatureCollection',
            features: dnrcAccessData.features.filter(f =>
                f.properties.access_status === 'confirmed' ||
                f.properties.access_status === 'near_miss'
            ),
        };

        map.addSource('dnrc-access', {
            type: 'geojson',
            data: unlockableDnrc,
        });

        // Color: confirmed=blue (road touches), near_miss=yellow
        const dnrcFillColor = [
            'match', ['get', 'access_status'],
            'confirmed',     '#3b82f6',
            'near_miss',     '#eab308',
            '#6b7280',
        ];
        const dnrcBorderColor = [
            'match', ['get', 'access_status'],
            'confirmed',     '#2563eb',
            'near_miss',     '#ca8a04',
            '#4b5563',
        ];

        map.addLayer({
            id: 'dnrc-access-fill',
            type: 'fill',
            source: 'dnrc-access',
            paint: {
                'fill-color': dnrcFillColor,
                'fill-opacity': 0.45,
            },
            layout: { visibility: 'none' },
        });

        map.addLayer({
            id: 'dnrc-access-border',
            type: 'line',
            source: 'dnrc-access',
            paint: {
                'line-color': dnrcBorderColor,
                'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.5, 12, 2],
                'line-opacity': 0.8,
            },
            layout: { visibility: 'none' },
        });

        // Click handler for DNRC parcels
        map.on('click', 'dnrc-access-fill', (e) => {
            const f = e.features[0];
            const p = f.properties;
            const isConfirmed = p.access_status === 'confirmed';
            const color = isConfirmed ? '#3b82f6' : '#eab308';
            const label = isConfirmed ? 'Road Unlockable' : 'Near-Miss';
            const acres = p.Acres ? Number(p.Acres).toLocaleString() : '--';
            const gapText = isConfirmed
                ? 'County road 30ft easement touches this parcel'
                : (p.gap_ft ? p.gap_ft + ' ft gap to nearest county road' : '--');

            new mapboxgl.Popup({ maxWidth: '340px', offset: 12 })
                .setLngLat(e.lngLat)
                .setHTML(`
                    <div class="popup">
                        <div class="popup-top dnrc">
                            <div class="popup-title">${p.TractID || 'DNRC Trust Land'}</div>
                            <div class="popup-county">${p.road_county || ''}</div>
                            <span class="badge" style="background:${color}22;color:${color}">${label}</span>
                        </div>
                        <div class="popup-body">
                            <div class="popup-section">
                                <div class="popup-row"><span class="label">Acres</span><span class="value">${acres}</span></div>
                                <div class="popup-row"><span class="label">TRS</span><span class="value">${p.TRS || '--'}</span></div>
                                <div class="popup-row"><span class="label">Unit</span><span class="value">${p.Unit || '--'}</span></div>
                                <div class="popup-row"><span class="label">Grant</span><span class="value">${p.GrantID || '--'}</span></div>
                            </div>
                            <div class="popup-section">
                                <div class="popup-section-title">Access Details</div>
                                <div class="popup-row"><span class="label">DNRC Status</span><span class="value">${p.Access_Type || '--'}</span></div>
                                <div class="popup-row"><span class="label">Analysis</span><span class="value">${gapText}</span></div>
                                ${p.nearest_road ? `<div class="popup-row"><span class="label">Nearest Road</span><span class="value">${p.nearest_road}</span></div>` : ''}
                            </div>
                            ${p.LegDescrip ? `<div class="popup-section"><div class="popup-section-title">Legal</div><div style="font-size:0.72rem;color:var(--text-muted);word-wrap:break-word">${p.LegDescrip}</div></div>` : ''}
                        </div>
                    </div>
                `)
                .addTo(map);
        });

        map.on('mouseenter', 'dnrc-access-fill', () => map.getCanvas().style.cursor = 'pointer');
        map.on('mouseleave', 'dnrc-access-fill', () => map.getCanvas().style.cursor = '');
    }

    // === 4b. STATE ACCESS LAYER ===
    if (stateAccessData) {
        map.addSource('state-access', {
            type: 'geojson',
            data: stateAccessData,
        });

        // Color: enclosed parcels get a distinct dark maroon
        const stateAccessColor = [
            'case',
            ['==', ['get', 'enclosed'], 'true'], '#991b1b',
            ['match', ['get', 'access_status'],
                'accessible', '#22c55e',
                'near_miss',  '#eab308',
                'landlocked', '#ef4444',
                '#6b7280'],
        ];
        const stateAccessBorderColor = [
            'case',
            ['==', ['get', 'enclosed'], 'true'], '#7f1d1d',
            ['match', ['get', 'access_status'],
                'accessible', '#16a34a',
                'near_miss',  '#ca8a04',
                'landlocked', '#dc2626',
                '#4b5563'],
        ];

        map.addLayer({
            id: 'state-access-fill',
            type: 'fill',
            source: 'state-access',
            paint: {
                'fill-color': stateAccessColor,
                'fill-opacity': 0.45,
            },
            layout: { visibility: 'none' },
        });

        map.addLayer({
            id: 'state-access-border',
            type: 'line',
            source: 'state-access',
            paint: {
                'line-color': stateAccessBorderColor,
                'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.5, 12, 2],
                'line-opacity': 0.8,
            },
            layout: { visibility: 'none' },
        });

        map.on('click', 'state-access-fill', (e) => {
            const f = e.features[0];
            const p = f.properties;
            const isEnclosed = p.enclosed === true || p.enclosed === 'true' || p.enclosed === 'True';
            const statusColor = {accessible: '#22c55e', near_miss: '#eab308', landlocked: '#ef4444'};
            const statusLabel = {accessible: 'Accessible', near_miss: 'Near-Miss', landlocked: 'Landlocked'};
            const displayColor = isEnclosed ? '#991b1b' : (statusColor[p.access_status] || '#6b7280');
            const displayLabel = isEnclosed ? 'Enclosed' : (statusLabel[p.access_status] || p.access_status);
            const acres = p.area_acres ? Number(p.area_acres).toLocaleString() : '--';
            const gapText = p.access_status === 'accessible'
                ? 'Connected via public land'
                : (p.gap_ft + ' ft gap');
            const enclosedRow = isEnclosed && p.enclosing_owner
                ? `<div class="popup-row"><span class="label">Enclosed By</span><span class="value" style="color:#fca5a5">${p.enclosing_owner}</span></div>`
                : '';

            new mapboxgl.Popup({ maxWidth: '320px', offset: 12 })
                .setLngLat(e.lngLat)
                .setHTML(`
                    <div class="popup">
                        <div class="popup-top state">
                            <div class="popup-title">${p.land_owner || 'State Trust Land'}</div>
                            <div class="popup-county">${p.county || ''}</div>
                            <span class="badge" style="background:${displayColor}22;color:${displayColor}">${displayLabel}</span>
                        </div>
                        <div class="popup-body">
                            <div class="popup-section">
                                <div class="popup-row"><span class="label">Acres</span><span class="value">${acres}</span></div>
                                <div class="popup-row"><span class="label">Status</span><span class="value">${gapText}</span></div>
                                <div class="popup-row"><span class="label">Nearest Road</span><span class="value">${p.nearest_road || '--'}</span></div>
                                ${p.access_via ? `<div class="popup-row"><span class="label">Access Via</span><span class="value">${p.access_via}</span></div>` : ''}
                                ${enclosedRow}
                            </div>
                        </div>
                    </div>
                `)
                .addTo(map);
        });

        map.on('mouseenter', 'state-access-fill', () => map.getCanvas().style.cursor = 'pointer');
        map.on('mouseleave', 'state-access-fill', () => map.getCanvas().style.cursor = '');
    }

    // === 5. UNLOCK OPPORTUNITIES (strategic points) ===
    if (unlockData) {
        map.addSource('unlock-opps', {
            type: 'geojson',
            data: unlockData,
        });

        // Color by primary land category
        const unlockColor = [
            'match', ['get', 'primary_category'],
            'BLM',   '#F59E0B',
            'STATE', '#3B82F6',
            'USFS',  '#22C55E',
            'FWP',   '#A855F7',
            'USFWS', '#EC4899',
            '#94a3b8',
        ];

        // Outer glow — sized by total acres
        map.addLayer({
            id: 'unlock-glow',
            type: 'circle',
            source: 'unlock-opps',
            paint: {
                'circle-color': unlockColor,
                'circle-radius': [
                    'interpolate', ['linear'], ['get', 'total_acres'],
                    10, 12, 500, 18, 5000, 28, 50000, 40,
                ],
                'circle-opacity': 0.15,
                'circle-blur': 0.6,
            },
            layout: { visibility: 'none' },
        });

        // Inner dot — shaped like a diamond via icon or distinct circle
        map.addLayer({
            id: 'unlock-points',
            type: 'circle',
            source: 'unlock-opps',
            paint: {
                'circle-color': unlockColor,
                'circle-radius': [
                    'interpolate', ['linear'], ['get', 'total_acres'],
                    10, 4, 500, 7, 5000, 11, 50000, 16,
                ],
                'circle-opacity': [
                    'case',
                    ['==', ['get', 'access_status'], 'near_miss'], 0.95,
                    0.7,
                ],
                'circle-stroke-width': 2.5,
                'circle-stroke-color': '#fff',
                'circle-stroke-opacity': 0.9,
            },
            layout: { visibility: 'none' },
        });

        // Acres label at higher zoom
        map.addLayer({
            id: 'unlock-labels',
            type: 'symbol',
            source: 'unlock-opps',
            minzoom: 9,
            layout: {
                'text-field': ['concat',
                    ['to-string', ['round', ['get', 'total_acres']]],
                    ' ac',
                ],
                'text-size': 10,
                'text-offset': [0, -1.8],
                'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
                visibility: 'none',
            },
            paint: {
                'text-color': '#fff',
                'text-halo-color': '#000',
                'text-halo-width': 1,
            },
        });

        // Click handler for unlock points
        map.on('click', 'unlock-points', (e) => {
            const f = e.features[0];
            const p = f.properties;
            const acres = Number(p.total_acres).toLocaleString();
            const gap = Number(p.gap_ft).toFixed(1);
            const isNearMiss = p.access_status === 'near_miss';
            const statusBadge = isNearMiss
                ? '<span class="badge nearmiss">Near-Miss</span>'
                : '<span class="badge" style="background:rgba(239,68,68,0.15);color:#fca5a5">Landlocked</span>';

            // Acre breakdown rows
            const catRows = [];
            if (Number(p.blm_acres) > 0) catRows.push(`<div class="popup-row"><span class="label"><span class="dot blm"></span> BLM</span><span class="value">${Number(p.blm_acres).toLocaleString()} ac</span></div>`);
            if (Number(p.usfs_acres) > 0) catRows.push(`<div class="popup-row"><span class="label"><span class="dot usfs"></span> USFS</span><span class="value">${Number(p.usfs_acres).toLocaleString()} ac</span></div>`);
            if (Number(p.state_acres) > 0) catRows.push(`<div class="popup-row"><span class="label"><span class="dot state"></span> State</span><span class="value">${Number(p.state_acres).toLocaleString()} ac</span></div>`);
            if (Number(p.fwp_acres) > 0) catRows.push(`<div class="popup-row"><span class="label"><span class="dot fwp"></span> FWP</span><span class="value">${Number(p.fwp_acres).toLocaleString()} ac</span></div>`);
            if (Number(p.other_acres) > 0) catRows.push(`<div class="popup-row"><span class="label">Other</span><span class="value">${Number(p.other_acres).toLocaleString()} ac</span></div>`);

            new mapboxgl.Popup({ maxWidth: '340px', offset: 12 })
                .setLngLat(e.lngLat)
                .setHTML(`
                    <div class="popup">
                        <div class="popup-top unlock">
                            <div class="popup-title">${p.road_name || 'Unnamed Road'}</div>
                            <div class="popup-county">${p.county || ''}</div>
                            ${statusBadge}
                        </div>
                        <div class="popup-body">
                            <div class="popup-section">
                                <div class="popup-section-title">Unlock Potential</div>
                                <div class="popup-row"><span class="label">Total Acres</span><span class="value" style="font-weight:600;color:#fbbf24">${acres}</span></div>
                                <div class="popup-row"><span class="label">Gap to Road</span><span class="value">${gap} ft</span></div>
                                <div class="popup-row"><span class="label">Parcels</span><span class="value">${p.num_parcels}</span></div>
                                <div class="popup-row"><span class="label">Score</span><span class="value">${Number(p.unlock_score).toLocaleString()}</span></div>
                            </div>
                            <div class="popup-section">
                                <div class="popup-section-title">Land Types</div>
                                ${catRows.join('')}
                            </div>
                            <div class="popup-section">
                                <div class="popup-section-title">MCA 7-14-2112</div>
                                <div style="font-size:0.75rem;color:var(--text-muted)">
                                    County roads have a 60ft statutory width. Asserting this road's easement could bridge the ${gap}ft gap and unlock ${acres} acres of public land.
                                </div>
                            </div>
                        </div>
                    </div>
                `)
                .addTo(map);
        });

        map.on('mouseenter', 'unlock-points', () => map.getCanvas().style.cursor = 'pointer');
        map.on('mouseleave', 'unlock-points', () => map.getCanvas().style.cursor = '');
    }

    // === 6. OPPORTUNITY POINTS ===
    map.addSource('opportunities', {
        type: 'geojson',
        data: allOpportunities,
        cluster: true,
        clusterMaxZoom: 11,
        clusterRadius: 40,
    });

    map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'opportunities',
        filter: ['has', 'point_count'],
        paint: {
            'circle-color': [
                'step', ['get', 'point_count'],
                '#60a5fa', 10, '#3b82f6', 50, '#2563eb', 200, '#1e40af',
            ],
            'circle-radius': [
                'step', ['get', 'point_count'],
                14, 10, 18, 50, 24, 200, 30,
            ],
            'circle-stroke-width': 2,
            'circle-stroke-color': 'rgba(255,255,255,0.5)',
        },
    });

    map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'opportunities',
        filter: ['has', 'point_count'],
        layout: {
            'text-field': '{point_count_abbreviated}',
            'text-size': 11,
            'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'],
        },
        paint: { 'text-color': '#fff' },
    });

    map.addLayer({
        id: 'point-glow',
        type: 'circle',
        source: 'opportunities',
        filter: ['!', ['has', 'point_count']],
        paint: {
            'circle-color': oppColorExpr(),
            'circle-radius': [
                'interpolate', ['linear'], ['get', 'score'],
                0, 10, 50, 14, 80, 18, 100, 24,
            ],
            'circle-opacity': 0.15,
            'circle-blur': 0.7,
        },
    });

    map.addLayer({
        id: 'points',
        type: 'circle',
        source: 'opportunities',
        filter: ['!', ['has', 'point_count']],
        paint: {
            'circle-color': oppColorExpr(),
            'circle-radius': [
                'interpolate', ['linear'], ['get', 'score'],
                0, 3, 50, 5, 80, 8, 100, 11,
            ],
            'circle-opacity': [
                'case', ['get', 'buffer_intersects'], 0.9, 0.55,
            ],
            'circle-stroke-width': [
                'interpolate', ['linear'], ['zoom'],
                5, 1, 12, 2.5,
            ],
            'circle-stroke-color': '#fff',
            'circle-stroke-opacity': [
                'case', ['get', 'buffer_intersects'], 0.9, 0.4,
            ],
        },
    });

    // ── Click handlers ──
    map.on('click', 'clusters', clusterClick);
    map.on('click', 'points', pointClick);
    map.on('click', mapClick);

    ['points', 'clusters', 'parcel-fill', 'dnrc-access-fill', 'state-access-fill'].forEach(l => {
        map.on('mouseenter', l, () => map.getCanvas().style.cursor = 'pointer');
        map.on('mouseleave', l, () => map.getCanvas().style.cursor = '');
    });
}

// ── Click: cluster ──
function clusterClick(e) {
    const f = e.features[0];
    map.getSource('opportunities').getClusterExpansionZoom(
        f.properties.cluster_id,
        (err, zoom) => {
            if (!err) map.easeTo({ center: f.geometry.coordinates, zoom: zoom + 1 });
        }
    );
}

// ── Click: opportunity point ──
function pointClick(e) {
    const f = e.features[0];
    const p = f.properties;
    const isConfirmed = p.buffer_intersects === true || p.buffer_intersects === 'true';
    const catClass = (p.land_category || 'other').toLowerCase();
    const gapText = p.gap_ft <= 0
        ? '<span class="value pos">Buffer overlaps land</span>'
        : `<span class="value">${p.gap_ft} ft</span>`;
    const acres = p.land_area_acres ? Number(p.land_area_acres).toLocaleString() : '--';
    const statusBadge = isConfirmed
        ? '<span class="badge confirmed">Confirmed Access</span>'
        : '<span class="badge nearmiss">Near-Miss</span>';
    const landLabel = LAND_LABELS[p.land_category] || p.land_name || p.land_category;

    new mapboxgl.Popup({ maxWidth: '320px', offset: 12 })
        .setLngLat(f.geometry.coordinates.slice())
        .setHTML(`
            <div class="popup">
                <div class="popup-top ${catClass}">
                    <div class="popup-title">${p.road_name || 'Unnamed Road'}</div>
                    <div class="popup-county">${p.county || ''}</div>
                    ${statusBadge}
                </div>
                <div class="popup-body">
                    <div class="popup-section">
                        <div class="popup-section-title">Public Land</div>
                        <div class="popup-row"><span class="label">Agency</span><span class="value">${landLabel}</span></div>
                        <div class="popup-row"><span class="label">Parcel</span><span class="value">${acres} acres</span></div>
                    </div>
                    <div class="popup-section">
                        <div class="popup-section-title">Access Analysis</div>
                        <div class="popup-row"><span class="label">Gap</span>${gapText}</div>
                        <div class="popup-row"><span class="label">Centerline</span><span class="value">${p.dist_centerline_ft} ft</span></div>
                        <div class="popup-row"><span class="label">Road Length</span><span class="value">${p.road_length_ft ? (Number(p.road_length_ft)/5280).toFixed(2) + ' mi' : '--'}</span></div>
                    </div>
                    <div class="popup-section">
                        <div class="popup-section-title">Score ${p.score}/100</div>
                        <div class="score-bar-container"><div class="score-bar" style="width:${p.score}%"></div></div>
                    </div>
                </div>
            </div>
        `)
        .addTo(map);
}

// ── Click: map background (parcel identify + owner highlight) ──
function mapClick(e) {
    // Skip if an opportunity point, cluster, or state access parcel was clicked
    const skipLayers = ['points', 'clusters'];
    if (map.getLayer('dnrc-access-fill')) skipLayers.push('dnrc-access-fill');
    if (map.getLayer('state-access-fill')) skipLayers.push('state-access-fill');
    const hits = map.queryRenderedFeatures(e.point, { layers: skipLayers });
    if (hits.length > 0) return;

    // Check for parcel click (vector tile features)
    const parcelHits = map.queryRenderedFeatures(e.point, { layers: ['parcel-fill'] });
    if (parcelHits.length === 0) {
        // Clear any existing highlight
        clearParcelHighlight();
        return;
    }

    const p = parcelHits[0].properties;
    const ownerId = p.owner_id || '';
    const acres = p.TotalAcres ? Number(p.TotalAcres).toLocaleString(undefined, {maximumFractionDigits: 1}) : (p.GISAcres ? Number(p.GISAcres).toLocaleString(undefined, {maximumFractionDigits: 1}) : '--');
    const value = p.TotalValue ? '$' + Number(p.TotalValue).toLocaleString() : '--';
    const landValue = p.TotalLandValue ? '$' + Number(p.TotalLandValue).toLocaleString() : '';

    // Owner type badge
    const ownerTypeColors = {
        corporate: { bg: 'rgba(239,68,68,0.15)', fg: '#fca5a5', label: 'Corporate' },
        trust:     { bg: 'rgba(168,85,247,0.15)', fg: '#c084fc', label: 'Trust' },
        government:{ bg: 'rgba(59,130,246,0.15)', fg: '#93c5fd', label: 'Government' },
        individual:{ bg: 'rgba(34,197,94,0.15)',  fg: '#86efac', label: 'Individual' },
    };
    const ot = ownerTypeColors[p.owner_type] || { bg: 'rgba(148,163,184,0.15)', fg: '#94a3b8', label: p.owner_type || 'Unknown' };
    const isOOS = p.out_of_state === true || p.out_of_state === 'true' || p.out_of_state === 'True';

    // Real owner (from CareOfTaxpayer or DbaName)
    const realOwner = p.real_owner && p.real_owner !== '' ? p.real_owner : '';
    const ownerLocation = [p.OwnerCity, p.OwnerState].filter(Boolean).join(', ');
    const legal = p.LegalDescriptionShort || '';
    const trs = [p.Township, p.Range, p.Section].filter(Boolean).join(' / ');

    // Highlight ALL parcels with same owner
    map.setFilter('parcel-highlight', ['==', 'owner_id', ownerId]);
    map.setFilter('parcel-highlight-border', ['==', 'owner_id', ownerId]);

    new mapboxgl.Popup({ maxWidth: '340px', offset: 12 })
        .setLngLat(e.lngLat)
        .setHTML(`
            <div class="popup">
                <div class="popup-top parcel">
                    <div class="popup-title">${p.OwnerName || 'Unknown Owner'}</div>
                    ${realOwner ? `<div class="popup-county" style="color:#fbbf24">Actual: ${realOwner}</div>` : ''}
                    <div class="popup-county">${p.CountyName || ''} County${ownerLocation ? ' &bull; ' + ownerLocation : ''}</div>
                    <span class="badge" style="background:${ot.bg};color:${ot.fg}">${ot.label}</span>
                    ${isOOS ? '<span class="badge" style="background:rgba(245,158,11,0.15);color:#fbbf24;margin-left:4px">Out-of-State</span>' : ''}
                </div>
                <div class="popup-body">
                    <div class="popup-section">
                        <div class="popup-section-title">Property</div>
                        <div class="popup-row"><span class="label">Acres</span><span class="value">${acres}</span></div>
                        <div class="popup-row"><span class="label">Type</span><span class="value">${p.PropType || '--'}</span></div>
                        <div class="popup-row"><span class="label">Address</span><span class="value">${p.AddressLine1 || '--'}</span></div>
                        ${trs ? `<div class="popup-row"><span class="label">Twp/Rng/Sec</span><span class="value">${trs}</span></div>` : ''}
                        ${legal ? `<div class="popup-row"><span class="label">Legal</span><span class="value" style="font-size:0.72rem;max-width:180px;word-wrap:break-word">${legal}</span></div>` : ''}
                    </div>
                    <div class="popup-section">
                        <div class="popup-section-title">Assessed Value</div>
                        <div class="popup-row"><span class="label">Total</span><span class="value">${value}</span></div>
                        ${landValue ? `<div class="popup-row"><span class="label">Land</span><span class="value">${landValue}</span></div>` : ''}
                    </div>
                    ${p.OwnerAddress1 ? `<div class="popup-section"><div class="popup-section-title">Owner Address</div><div style="font-size:0.78rem;color:var(--text-muted)">${p.OwnerAddress1}${p.OwnerCity ? '<br>' + p.OwnerCity + ', ' + (p.OwnerState || '') + ' ' + (p.OwnerZipCode || '') : ''}</div></div>` : ''}
                </div>
            </div>
        `)
        .on('close', clearParcelHighlight)
        .addTo(map);
}

function clearParcelHighlight() {
    if (map.getLayer('parcel-highlight')) {
        map.setFilter('parcel-highlight', ['==', 'owner_id', '']);
        map.setFilter('parcel-highlight-border', ['==', 'owner_id', '']);
    }
}

// ── Filtering ──
function matchesFilter(p) {
    const showConfirmed = document.getElementById('filter-confirmed').checked;
    const showNearmiss = document.getElementById('filter-nearmiss').checked;
    const isConfirmed = p.buffer_intersects === true || p.buffer_intersects === 'true';
    if (isConfirmed && !showConfirmed) return false;
    if (!isConfirmed && !showNearmiss) return false;

    const activeCats = [];
    document.querySelectorAll('#land-type-filters input[type="checkbox"]').forEach(cb => {
        if (cb.checked) activeCats.push(cb.dataset.category);
    });
    if (!activeCats.includes(p._category)) return false;

    if (p.score < Number(document.getElementById('filter-score').value)) return false;
    if (p.gap_ft > Number(document.getElementById('filter-gap').value)) return false;

    const minAcres = Number(document.getElementById('filter-acres').value);
    if (minAcres > 0 && (p.land_area_acres || 0) < minAcres) return false;

    const county = document.getElementById('filter-county').value;
    if (county && p.county !== county) return false;

    return true;
}

function applyFilters() {
    const filtered = {
        type: 'FeatureCollection',
        features: allOpportunities.features.filter(f => matchesFilter(f.properties)),
    };
    map.getSource('opportunities').setData(filtered);
    updateVisibleCount(filtered.features.length);
}

function bindFilters() {
    document.querySelectorAll('#land-type-filters input, #filter-confirmed, #filter-nearmiss')
        .forEach(el => el.addEventListener('change', applyFilters));

    const scoreSlider = document.getElementById('filter-score');
    scoreSlider.addEventListener('input', () => {
        document.getElementById('score-value').textContent = scoreSlider.value;
    });
    scoreSlider.addEventListener('change', applyFilters);

    const gapSlider = document.getElementById('filter-gap');
    gapSlider.addEventListener('input', () => {
        document.getElementById('gap-value').textContent = gapSlider.value;
    });
    gapSlider.addEventListener('change', applyFilters);

    const acresSlider = document.getElementById('filter-acres');
    acresSlider.addEventListener('input', () => {
        document.getElementById('acres-value').textContent = Number(acresSlider.value).toLocaleString();
    });
    acresSlider.addEventListener('change', applyFilters);

    document.getElementById('filter-county').addEventListener('change', applyFilters);

    document.getElementById('reset-filters').addEventListener('click', () => {
        document.querySelectorAll('#land-type-filters input, #filter-confirmed, #filter-nearmiss')
            .forEach(cb => cb.checked = true);
        scoreSlider.value = 0;
        document.getElementById('score-value').textContent = '0';
        gapSlider.value = 100;
        document.getElementById('gap-value').textContent = '100';
        acresSlider.value = 0;
        document.getElementById('acres-value').textContent = '0';
        document.getElementById('filter-county').value = '';
        map.getSource('opportunities').setData(allOpportunities);
        updateVisibleCount(allOpportunities.features.length);
    });
}

// ── Land layer toggles ──
function bindLandToggle() {
    const slider = document.getElementById('land-opacity');
    if (slider) {
        slider.addEventListener('input', () => {
            const val = Number(slider.value) / 100;
            document.getElementById('land-opacity-value').textContent = slider.value + '%';
            for (const key of Object.keys(TILE_LAYERS)) {
                if (map.getLayer('tiles-' + key)) {
                    map.setPaintProperty('tiles-' + key, 'raster-opacity', val);
                }
            }
        });
    }

    document.querySelectorAll('.layer-toggle').forEach(cb => {
        cb.addEventListener('change', () => {
            const layerId = 'tiles-' + cb.dataset.layer;
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', cb.checked ? 'visible' : 'none');
            }
        });
    });
}

// ── Road layer toggles ──
function bindRoadToggle() {
    document.querySelectorAll('.road-toggle').forEach(cb => {
        cb.addEventListener('change', () => {
            const layerId = 'roads-' + cb.dataset.layer;
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', cb.checked ? 'visible' : 'none');
            }
        });
    });
}

// ── Water layer toggles ──
function bindWaterToggle() {
    document.querySelectorAll('.water-toggle').forEach(cb => {
        cb.addEventListener('change', () => {
            const layerId = 'water-' + cb.dataset.layer;
            if (map.getLayer(layerId)) {
                map.setLayoutProperty(layerId, 'visibility', cb.checked ? 'visible' : 'none');
            }
        });
    });
}

// ── Parcel toggle ──
const PARCEL_LAYERS = ['ownership-borders', 'parcel-borders', 'parcel-fill', 'parcel-highlight', 'parcel-highlight-border'];

function bindParcelToggle() {
    const cb = document.getElementById('parcels-toggle');
    if (!cb) return;
    cb.addEventListener('change', () => {
        const vis = cb.checked ? 'visible' : 'none';
        PARCEL_LAYERS.forEach(id => {
            if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
        });
        if (!cb.checked) clearParcelHighlight();
    });
}

// ── DNRC access toggle ──
function bindDnrcAccessToggle() {
    const cb = document.getElementById('dnrc-access-toggle');
    if (!cb) return;
    cb.addEventListener('change', () => {
        const vis = cb.checked ? 'visible' : 'none';
        ['dnrc-access-fill', 'dnrc-access-border'].forEach(id => {
            if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
        });
    });

    // Show stats
    if (dnrcAccessData) {
        const statsEl = document.getElementById('dnrc-stats');
        if (statsEl) {
            const confirmed = dnrcAccessData.features.filter(f => f.properties.access_status === 'confirmed');
            const nearMiss = dnrcAccessData.features.filter(f => f.properties.access_status === 'near_miss');
            const sumAcres = arr => arr.reduce((s, f) => s + (Number(f.properties.Acres) || 0), 0);
            const totalParcels = confirmed.length + nearMiss.length;
            const totalAcres = sumAcres([...confirmed, ...nearMiss]);
            statsEl.innerHTML = `
                <strong>${totalParcels}</strong> closed parcels near roads &mdash; <strong>${totalAcres.toLocaleString()} acres</strong><br>
                ${confirmed.length} confirmed (road touches) + ${nearMiss.length} near-miss
            `;
        }
    }
}

// ── State access toggle ──
function bindStateAccessToggle() {
    const cb = document.getElementById('state-access-toggle');
    if (!cb) return;
    cb.addEventListener('change', () => {
        const vis = cb.checked ? 'visible' : 'none';
        ['state-access-fill', 'state-access-border'].forEach(id => {
            if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
        });
    });
}

// ── Unlock opportunities toggle ──
const UNLOCK_LAYERS = ['unlock-glow', 'unlock-points', 'unlock-labels'];

function bindUnlockToggle() {
    const cb = document.getElementById('unlock-toggle');
    if (!cb) return;

    // Filter controls
    const gapSlider = document.getElementById('unlock-gap-filter');
    const acresSlider = document.getElementById('unlock-acres-filter');

    cb.addEventListener('change', () => {
        const vis = cb.checked ? 'visible' : 'none';
        UNLOCK_LAYERS.forEach(id => {
            if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis);
        });
    });

    function applyUnlockFilters() {
        if (!unlockData) return;
        const maxGap = gapSlider ? Number(gapSlider.value) : 500;
        const minAcres = acresSlider ? Number(acresSlider.value) : 0;

        if (document.getElementById('unlock-gap-value')) {
            document.getElementById('unlock-gap-value').textContent = maxGap;
        }
        if (document.getElementById('unlock-acres-value')) {
            document.getElementById('unlock-acres-value').textContent = minAcres;
        }

        const filtered = {
            type: 'FeatureCollection',
            features: unlockData.features.filter(f => {
                const p = f.properties;
                return Number(p.gap_ft) <= maxGap && Number(p.total_acres) >= minAcres;
            }),
        };
        if (map.getSource('unlock-opps')) {
            map.getSource('unlock-opps').setData(filtered);
        }

        // Update count
        const countEl = document.getElementById('unlock-count');
        if (countEl) {
            const totalAcres = filtered.features.reduce((s, f) => s + Number(f.properties.total_acres), 0);
            countEl.textContent = `${filtered.features.length.toLocaleString()} opportunities — ${totalAcres.toLocaleString()} acres`;
        }
    }

    if (gapSlider) {
        gapSlider.addEventListener('input', applyUnlockFilters);
        gapSlider.addEventListener('change', applyUnlockFilters);
    }
    if (acresSlider) {
        acresSlider.addEventListener('input', applyUnlockFilters);
        acresSlider.addEventListener('change', applyUnlockFilters);
    }

    // Initialize count
    if (unlockData) {
        const countEl = document.getElementById('unlock-count');
        if (countEl) {
            const totalAcres = unlockData.features.reduce((s, f) => s + Number(f.properties.total_acres), 0);
            countEl.textContent = `${unlockData.features.length.toLocaleString()} opportunities — ${totalAcres.toLocaleString()} acres`;
        }
    }
}

// ── County dropdown ──
function populateCountyFilter() {
    const counties = new Set();
    allOpportunities.features.forEach(f => {
        if (f.properties.county) counties.add(f.properties.county);
    });
    const select = document.getElementById('filter-county');
    [...counties].sort().forEach(c => {
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        select.appendChild(opt);
    });
}

// ── Stats ──
function updateStats() {
    const total = allOpportunities.features.length;
    const confirmed = allOpportunities.features.filter(f => {
        const b = f.properties.buffer_intersects;
        return b === true || b === 'true';
    }).length;
    document.getElementById('stat-total').textContent = total.toLocaleString();
    document.getElementById('stat-confirmed').textContent = confirmed.toLocaleString();
    document.getElementById('stat-nearmiss').textContent = (total - confirmed).toLocaleString();
    document.getElementById('stat-visible').textContent = total.toLocaleString();
}

function updateVisibleCount(count) {
    document.getElementById('stat-visible').textContent = count.toLocaleString();
}

// ── Sidebar ──
function bindSidebar() {
    const sidebar = document.getElementById('sidebar');
    const openBtn = document.getElementById('sidebar-open');
    document.getElementById('sidebar-toggle').addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        openBtn.style.display = 'flex';
    });
    openBtn.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        openBtn.style.display = 'none';
    });
}

// ── Basemap ──
function bindBasemap() {
    document.querySelectorAll('input[name="basemap"]').forEach(radio => {
        radio.addEventListener('change', () => {
            map.setStyle('mapbox://styles/mapbox/' + radio.value + '-v12');
            map.once('style.load', () => {
                addAllLayers();
                applyFilters();
            });
        });
    });
}

document.addEventListener('DOMContentLoaded', initMap);
