// Montana Public Land Access — Mapbox GL JS
// Public lands: Official MT State Library ArcGIS tile service
// Roads + opportunities: Local GeoJSON from analysis pipeline

const MT_LANDS_TILE_URL =
    'https://gisservicemt.gov/arcgis/rest/services/MSDI_Framework/PublicLands/MapServer/export' +
    '?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512' +
    '&format=png32&transparent=true&f=image';

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
let allRoads = null;

// ── Token ──
function initToken() {
    const saved = localStorage.getItem('mapbox_token');
    if (saved) { startMap(saved); return; }
    document.getElementById('token-modal').classList.remove('hidden');
    document.getElementById('token-submit').addEventListener('click', submitToken);
    document.getElementById('token-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitToken();
    });
}

function submitToken() {
    const token = document.getElementById('token-input').value.trim();
    if (token) {
        localStorage.setItem('mapbox_token', token);
        startMap(token);
    }
}

// ── Map ──
function startMap(token) {
    document.getElementById('token-modal').classList.add('hidden');
    document.getElementById('loading').classList.remove('hidden');
    updateLoadingText('Initializing map...');

    mapboxgl.accessToken = token;
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
        updateLoadingText('Loading county roads...');
        const roadsResp = await fetch('data/roads.geojson');
        allRoads = await roadsResp.json();

        updateLoadingText('Loading access opportunities...');
        const oppsResp = await fetch('data/opportunities.geojson');
        allOpportunities = await oppsResp.json();
        allOpportunities.features.forEach(f => {
            const cat = f.properties.land_category || 'UNKNOWN';
            f.properties._category = OPP_CATEGORY_MAP[cat] || 'OTHER';
        });

        addAllLayers();
        populateCountyFilter();
        updateStats();
        bindFilters();
        bindSidebar();
        bindBasemap();
        bindLandToggle();

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
    // === 1. OFFICIAL MT PUBLIC LANDS (raster tiles from state ArcGIS) ===
    map.addSource('mt-public-lands', {
        type: 'raster',
        tiles: [MT_LANDS_TILE_URL],
        tileSize: 512,
        attribution: 'MT State Library / MSDI',
    });

    map.addLayer({
        id: 'mt-lands-tiles',
        type: 'raster',
        source: 'mt-public-lands',
        paint: {
            'raster-opacity': 0.65,
        },
    });

    // === 2. COUNTY ROADS ===
    map.addSource('roads', { type: 'geojson', data: allRoads });

    map.addLayer({
        id: 'road-casing',
        type: 'line',
        source: 'roads',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
            'line-color': '#1e293b',
            'line-width': [
                'interpolate', ['linear'], ['zoom'],
                6, 0.8, 10, 3, 14, 7, 17, 12,
            ],
            'line-opacity': [
                'interpolate', ['linear'], ['zoom'],
                6, 0.15, 10, 0.4, 14, 0.5,
            ],
        },
    });

    map.addLayer({
        id: 'road-lines',
        type: 'line',
        source: 'roads',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
            'line-color': '#f8fafc',
            'line-width': [
                'interpolate', ['linear'], ['zoom'],
                6, 0.3, 10, 1.5, 14, 4, 17, 8,
            ],
            'line-opacity': [
                'interpolate', ['linear'], ['zoom'],
                6, 0.25, 10, 0.5, 14, 0.7,
            ],
        },
    });

    map.addLayer({
        id: 'road-labels',
        type: 'symbol',
        source: 'roads',
        minzoom: 12,
        layout: {
            'symbol-placement': 'line',
            'text-field': ['get', 'road_name'],
            'text-size': 11,
            'text-font': ['DIN Pro Regular', 'Arial Unicode MS Regular'],
            'text-allow-overlap': false,
        },
        paint: {
            'text-color': '#e2e8f0',
            'text-halo-color': 'rgba(15,23,42,0.8)',
            'text-halo-width': 1.5,
        },
    });

    // === 3. OPPORTUNITY POINTS ===
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
    map.on('click', 'road-lines', roadClick);

    ['points', 'clusters'].forEach(l => {
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
                        <div class="score-bar-bg"><div class="score-bar" style="width:${p.score}%"></div></div>
                        <div class="score-chips">
                            <span class="chip">Gap ${p.gap_score}</span>
                            <span class="chip">Land ${p.land_score}</span>
                            <span class="chip">Size ${p.size_score}</span>
                            <span class="chip">Iso ${p.isolation_score}</span>
                        </div>
                    </div>
                </div>
            </div>
        `)
        .addTo(map);
}

// ── Click: road line ──
function roadClick(e) {
    if (!e.features.length) return;
    if (map.queryRenderedFeatures(e.point, { layers: ['points'] }).length) return;

    const p = e.features[0].properties;
    const mi = p.length_ft ? (Number(p.length_ft) / 5280).toFixed(2) : '--';

    new mapboxgl.Popup({ maxWidth: '240px', offset: 10 })
        .setLngLat(e.lngLat)
        .setHTML(`
            <div class="popup">
                <div class="popup-top road">
                    <div class="popup-title">${p.road_name || 'Unnamed'}</div>
                    <div class="popup-county">${p.county || ''} — County Road</div>
                </div>
                <div class="popup-body">
                    <div class="popup-row"><span class="label">Length</span><span class="value">${mi} mi</span></div>
                    <div class="popup-row"><span class="label">Class</span><span class="value">${p.road_class || '--'}</span></div>
                </div>
            </div>
        `)
        .addTo(map);
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

    const activeRoadIdxs = new Set();
    filtered.features.forEach(f => {
        if (f.properties.road_idx != null) activeRoadIdxs.add(f.properties.road_idx);
    });
    map.getSource('roads').setData({
        type: 'FeatureCollection',
        features: allRoads.features.filter(f => activeRoadIdxs.has(f.properties.road_idx)),
    });

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

    document.getElementById('filter-county').addEventListener('change', applyFilters);

    document.getElementById('reset-filters').addEventListener('click', () => {
        document.querySelectorAll('#land-type-filters input, #filter-confirmed, #filter-nearmiss')
            .forEach(cb => cb.checked = true);
        scoreSlider.value = 0;
        document.getElementById('score-value').textContent = '0';
        gapSlider.value = 100;
        document.getElementById('gap-value').textContent = '100';
        document.getElementById('filter-county').value = '';
        map.getSource('opportunities').setData(allOpportunities);
        map.getSource('roads').setData(allRoads);
        updateVisibleCount(allOpportunities.features.length);
    });
}

// ── Land opacity toggle ──
function bindLandToggle() {
    const slider = document.getElementById('land-opacity');
    if (!slider) return;
    slider.addEventListener('input', () => {
        const val = Number(slider.value) / 100;
        document.getElementById('land-opacity-value').textContent = slider.value + '%';
        map.setPaintProperty('mt-lands-tiles', 'raster-opacity', val);
    });
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

document.addEventListener('DOMContentLoaded', initToken);
