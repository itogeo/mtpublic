// Montana Public Land Access — Mapbox GL JS Application

const COLORS = {
    BLM:   '#F59E0B',
    USFS:  '#10B981',
    STATE: '#3B82F6',
    FWP:   '#8B5CF6',
    OTHER: '#6B7280',
};

const CATEGORY_MAP = {
    'BLM': 'BLM',
    'USFS': 'USFS',
    'STATE': 'STATE',
    'FWP': 'FWP',
    'USFWS': 'FWP',
    'NPS': 'OTHER',
    'BOR': 'OTHER',
    'DOD': 'OTHER',
    'USACE': 'OTHER',
    'TRIBAL': 'OTHER',
    'LOCAL': 'OTHER',
    'UNKNOWN': 'OTHER',
};

let map;
let allData = null;

// ── Token handling ──
function initToken() {
    const saved = localStorage.getItem('mapbox_token');
    if (saved) {
        startMap(saved);
        return;
    }
    document.getElementById('token-modal').classList.remove('hidden');
    document.getElementById('token-submit').addEventListener('click', () => {
        const token = document.getElementById('token-input').value.trim();
        if (token) {
            localStorage.setItem('mapbox_token', token);
            startMap(token);
        }
    });
    document.getElementById('token-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') document.getElementById('token-submit').click();
    });
}

// ── Map init ──
function startMap(token) {
    document.getElementById('token-modal').classList.add('hidden');
    document.getElementById('loading').classList.remove('hidden');

    mapboxgl.accessToken = token;
    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/outdoors-v12',
        center: [-109.5, 47.0],
        zoom: 5.5,
        maxBounds: [[-117, 44], [-103, 50]],
    });

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.ScaleControl(), 'bottom-right');

    map.on('load', loadData);
}

// ── Load GeoJSON ──
async function loadData() {
    try {
        const resp = await fetch('data/opportunities.geojson');
        allData = await resp.json();

        // Normalize categories
        allData.features.forEach(f => {
            const cat = f.properties.land_category || 'UNKNOWN';
            f.properties._category = CATEGORY_MAP[cat] || 'OTHER';
        });

        addLayers();
        populateCountyFilter();
        updateStats();
        bindFilters();
        bindSidebar();
        bindBasemap();

        document.getElementById('loading').classList.add('hidden');
    } catch (err) {
        document.getElementById('loading').querySelector('p').textContent =
            'Error loading data: ' + err.message;
    }
}

// ── Layers ──
function addLayers() {
    map.addSource('opportunities', {
        type: 'geojson',
        data: allData,
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 40,
    });

    // Cluster circles
    map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'opportunities',
        filter: ['has', 'point_count'],
        paint: {
            'circle-color': [
                'step', ['get', 'point_count'],
                '#3B82F6', 20,
                '#2563EB', 100,
                '#1D4ED8', 500,
                '#1E3A8A',
            ],
            'circle-radius': [
                'step', ['get', 'point_count'],
                16, 20, 20, 100, 26, 500, 32,
            ],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#fff',
            'circle-stroke-opacity': 0.3,
        },
    });

    // Cluster labels
    map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'opportunities',
        filter: ['has', 'point_count'],
        layout: {
            'text-field': '{point_count_abbreviated}',
            'text-size': 12,
            'text-font': ['DIN Pro Medium', 'Arial Unicode MS Bold'],
        },
        paint: { 'text-color': '#fff' },
    });

    // Individual points
    map.addLayer({
        id: 'points',
        type: 'circle',
        source: 'opportunities',
        filter: ['!', ['has', 'point_count']],
        paint: {
            'circle-color': [
                'match', ['get', '_category'],
                'BLM',   COLORS.BLM,
                'USFS',  COLORS.USFS,
                'STATE', COLORS.STATE,
                'FWP',   COLORS.FWP,
                COLORS.OTHER,
            ],
            'circle-radius': [
                'interpolate', ['linear'], ['get', 'score'],
                0, 4,
                50, 7,
                80, 10,
                100, 14,
            ],
            'circle-opacity': [
                'case',
                ['get', 'buffer_intersects'], 0.85,
                0.5,
            ],
            'circle-stroke-width': [
                'case',
                ['get', 'buffer_intersects'], 2,
                1,
            ],
            'circle-stroke-color': '#fff',
            'circle-stroke-opacity': 0.6,
        },
    });

    // Click: expand cluster
    map.on('click', 'clusters', (e) => {
        const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] });
        const clusterId = features[0].properties.cluster_id;
        map.getSource('opportunities').getClusterExpansionZoom(clusterId, (err, zoom) => {
            if (err) return;
            map.easeTo({ center: features[0].geometry.coordinates, zoom: zoom + 1 });
        });
    });

    // Click: popup on point
    map.on('click', 'points', (e) => {
        const f = e.features[0];
        const p = f.properties;
        const coords = f.geometry.coordinates.slice();

        const status = p.buffer_intersects
            ? '<span class="popup-badge confirmed">Confirmed</span>'
            : '<span class="popup-badge nearmiss">Near-Miss</span>';

        const gapText = p.gap_ft <= 0 ? 'Overlaps' : p.gap_ft + ' ft';
        const acres = p.land_area_acres ? Number(p.land_area_acres).toLocaleString() : '?';

        const html = `
            <div class="popup-header">
                <h4>${p.road_name || 'Unnamed Road'}</h4>
                <div class="popup-sub">${p.county || ''} ${status}</div>
            </div>
            <div class="popup-body">
                <div class="popup-row"><span class="label">Land</span><span class="value">${p.land_name || p.land_category}</span></div>
                <div class="popup-row"><span class="label">Category</span><span class="value">${p.land_category}</span></div>
                <div class="popup-row"><span class="label">Acreage</span><span class="value">${acres}</span></div>
                <div class="popup-row"><span class="label">Gap</span><span class="value">${gapText}</span></div>
                <div class="popup-row"><span class="label">Score</span><span class="value">${p.score}/100</span></div>
                <div class="popup-score">
                    <span class="chip">Gap: ${p.gap_score}</span>
                    <span class="chip">Land: ${p.land_score}</span>
                    <span class="chip">Size: ${p.size_score}</span>
                    <span class="chip">Isolation: ${p.isolation_score}</span>
                </div>
            </div>
        `;

        new mapboxgl.Popup({ maxWidth: '320px' })
            .setLngLat(coords)
            .setHTML(html)
            .addTo(map);
    });

    // Cursor changes
    map.on('mouseenter', 'points', () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', 'points', () => map.getCanvas().style.cursor = '');
    map.on('mouseenter', 'clusters', () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', 'clusters', () => map.getCanvas().style.cursor = '');
}

// ── Filters ──
function buildFilter() {
    const filters = ['all'];

    // Status
    const showConfirmed = document.getElementById('filter-confirmed').checked;
    const showNearmiss = document.getElementById('filter-nearmiss').checked;
    if (showConfirmed && !showNearmiss) {
        filters.push(['==', ['get', 'buffer_intersects'], true]);
    } else if (!showConfirmed && showNearmiss) {
        filters.push(['==', ['get', 'buffer_intersects'], false]);
    } else if (!showConfirmed && !showNearmiss) {
        filters.push(['==', ['get', 'buffer_intersects'], 'NONE']); // hide all
    }

    // Land type
    const activeCats = [];
    document.querySelectorAll('#land-type-filters input[type="checkbox"]').forEach(cb => {
        if (cb.checked) activeCats.push(cb.dataset.category);
    });
    if (activeCats.length < 5) {
        filters.push(['in', ['get', '_category'], ['literal', activeCats]]);
    }

    // Score
    const minScore = Number(document.getElementById('filter-score').value);
    if (minScore > 0) {
        filters.push(['>=', ['get', 'score'], minScore]);
    }

    // Gap
    const maxGap = Number(document.getElementById('filter-gap').value);
    if (maxGap < 100) {
        filters.push(['<=', ['get', 'gap_ft'], maxGap]);
    }

    // County
    const county = document.getElementById('filter-county').value;
    if (county) {
        filters.push(['==', ['get', 'county'], county]);
    }

    return filters;
}

function applyFilters() {
    const filter = buildFilter();
    // Apply to unclustered points
    map.setFilter('points', ['all', ['!', ['has', 'point_count']], ...filter.slice(1)]);

    // For clusters, we need to update the source data
    // Mapbox GL JS doesn't support filtering clusters directly,
    // so we filter the source data
    const filtered = {
        type: 'FeatureCollection',
        features: allData.features.filter(f => matchesFilter(f.properties)),
    };
    map.getSource('opportunities').setData(filtered);
    // Re-apply point filter since source changed
    map.setFilter('points', ['!', ['has', 'point_count']]);

    updateVisibleCount(filtered.features.length);
}

function matchesFilter(p) {
    const showConfirmed = document.getElementById('filter-confirmed').checked;
    const showNearmiss = document.getElementById('filter-nearmiss').checked;
    if (p.buffer_intersects && !showConfirmed) return false;
    if (!p.buffer_intersects && !showNearmiss) return false;

    const activeCats = [];
    document.querySelectorAll('#land-type-filters input[type="checkbox"]').forEach(cb => {
        if (cb.checked) activeCats.push(cb.dataset.category);
    });
    if (!activeCats.includes(p._category)) return false;

    const minScore = Number(document.getElementById('filter-score').value);
    if (p.score < minScore) return false;

    const maxGap = Number(document.getElementById('filter-gap').value);
    if (p.gap_ft > maxGap) return false;

    const county = document.getElementById('filter-county').value;
    if (county && p.county !== county) return false;

    return true;
}

function bindFilters() {
    // Checkboxes
    document.querySelectorAll('#land-type-filters input, #filter-confirmed, #filter-nearmiss')
        .forEach(el => el.addEventListener('change', applyFilters));

    // Score slider
    const scoreSlider = document.getElementById('filter-score');
    scoreSlider.addEventListener('input', () => {
        document.getElementById('score-value').textContent = scoreSlider.value;
    });
    scoreSlider.addEventListener('change', applyFilters);

    // Gap slider
    const gapSlider = document.getElementById('filter-gap');
    gapSlider.addEventListener('input', () => {
        document.getElementById('gap-value').textContent = gapSlider.value;
    });
    gapSlider.addEventListener('change', applyFilters);

    // County
    document.getElementById('filter-county').addEventListener('change', applyFilters);

    // Reset
    document.getElementById('reset-filters').addEventListener('click', () => {
        document.querySelectorAll('#land-type-filters input, #filter-confirmed, #filter-nearmiss')
            .forEach(cb => cb.checked = true);
        scoreSlider.value = 0;
        document.getElementById('score-value').textContent = '0';
        gapSlider.value = 100;
        document.getElementById('gap-value').textContent = '100';
        document.getElementById('filter-county').value = '';
        applyFilters();
    });
}

// ── County dropdown ──
function populateCountyFilter() {
    const counties = new Set();
    allData.features.forEach(f => {
        if (f.properties.county) counties.add(f.properties.county);
    });
    const sorted = [...counties].sort();
    const select = document.getElementById('filter-county');
    sorted.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        select.appendChild(opt);
    });
}

// ── Stats ──
function updateStats() {
    const total = allData.features.length;
    const confirmed = allData.features.filter(f => f.properties.buffer_intersects).length;
    const nearmiss = total - confirmed;

    document.getElementById('stat-total').textContent = total.toLocaleString();
    document.getElementById('stat-confirmed').textContent = confirmed.toLocaleString();
    document.getElementById('stat-nearmiss').textContent = nearmiss.toLocaleString();
    document.getElementById('stat-visible').textContent = total.toLocaleString();
}

function updateVisibleCount(count) {
    document.getElementById('stat-visible').textContent = count.toLocaleString();
}

// ── Sidebar toggle ──
function bindSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const openBtn = document.getElementById('sidebar-open');

    toggleBtn.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        openBtn.style.display = 'flex';
    });

    openBtn.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        openBtn.style.display = 'none';
    });
}

// ── Base map toggle ──
function bindBasemap() {
    document.querySelectorAll('input[name="basemap"]').forEach(radio => {
        radio.addEventListener('change', () => {
            map.setStyle('mapbox://styles/mapbox/' + radio.value + '-v12');
            // Re-add data after style change
            map.once('style.load', () => {
                const filtered = {
                    type: 'FeatureCollection',
                    features: allData.features.filter(f => matchesFilter(f.properties)),
                };
                addLayers();
                map.getSource('opportunities').setData(filtered);
                map.setFilter('points', ['!', ['has', 'point_count']]);
            });
        });
    });
}

// ── Boot ──
document.addEventListener('DOMContentLoaded', initToken);
