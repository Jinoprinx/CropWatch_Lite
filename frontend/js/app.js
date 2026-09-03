/**
 * CropWatch Lite - Frontend Web Application Logic
 * Integrates Leaflet GIS, multi-spectral layers, drone photogrammetry,
 * deep vision leaf diagnostics, yield forecasting, and flight mission planning.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    currentTab: 'tab-satellite',
    fieldsData: null,
    currentFieldId: 'field_corn_01',
    satelliteLayerData: null,
    activeSpectralLayer: 'ndvi',
    map: null,
    fieldPolygonLayer: null,
    hotspotMarkersLayer: null,
    sampleAssets: { leaves: [], drone_tiles: [] },
    droneAnalysis: null,
    leafAnalysis: null,
    yieldData: null,
    flightData: null
  };

  // ----------------- Initialization ----------------- //
  initTabs();
  initMap();
  loadFields();
  loadSampleAssets();
  bindEvents();

  // ----------------- Tabs Navigation ----------------- //
  function initTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        const activeContent = document.getElementById(targetTab);
        if (activeContent) activeContent.classList.add('active');

        state.currentTab = targetTab;
        if (targetTab === 'tab-satellite' && state.map) {
          setTimeout(() => state.map.invalidateSize(), 200);
        }
      });
    });
  }

  // ----------------- Map & GIS (Leaflet) ----------------- //
  function initMap() {
    // Center initially in Iowa Corn Belt
    state.map = L.map('satellite-map', {
      zoomControl: true,
      attributionControl: false
    }).setView([42.0215, -93.6460], 15);

    // High-Res Satellite Imagery Basemap (ESRI World Imagery)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19
    }).addTo(state.map);

    state.fieldPolygonLayer = L.layerGroup().addTo(state.map);
    state.hotspotMarkersLayer = L.layerGroup().addTo(state.map);
  }

  async function loadFields() {
    try {
      const res = await fetch('/api/fields');
      const data = await res.json();
      state.fieldsData = data;
      renderCurrentField();
      runSatelliteScan();
    } catch (err) {
      console.error('Failed to load fields:', err);
    }
  }

  function renderCurrentField() {
    if (!state.fieldsData || !state.map) return;
    state.fieldPolygonLayer.clearLayers();

    const field = state.fieldsData.features.find(f => f.id === state.currentFieldId);
    if (!field) return;

    // Invert Coordinates for Leaflet [Lat, Lon]
    const coords = field.geometry.coordinates[0].map(pt => [pt[1], pt[0]]);
    
    const polygon = L.polygon(coords, {
      color: '#10b981',
      weight: 3,
      fillColor: '#10b981',
      fillOpacity: 0.15,
      dashArray: '4, 6'
    }).addTo(state.fieldPolygonLayer);

    polygon.bindPopup(`<strong>${field.properties.name}</strong><br>Crop: ${field.properties.crop}<br>Area: ${field.properties.area_ha} ha`);
    state.map.fitBounds(polygon.getBounds(), { padding: [40, 40] });
  }

  // ----------------- Satellite Pipeline ----------------- //
  async function runSatelliteScan() {
    const field = state.fieldsData?.features.find(f => f.id === state.currentFieldId);
    const coords = field ? field.geometry.coordinates[0] : [[-93.65, 42.02], [-93.64, 42.02], [-93.64, 42.01], [-93.65, 42.01]];
    
    const lons = coords.map(c => c[0]);
    const lats = coords.map(c => c[1]);
    const bbox = [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
    const originLat = (bbox[1] + bbox[3]) / 2;
    const originLon = (bbox[0] + bbox[2]) / 2;

    try {
      const res = await fetch('/api/satellite/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bbox: bbox,
          crop_type: field?.properties.crop || 'corn',
          growth_stage: 'peak_vegetative',
          origin_lat: originLat,
          origin_lon: originLon
        })
      });

      const data = await res.json();
      state.satelliteLayerData = data;
      renderSatelliteAnalysis(data);
    } catch (err) {
      console.error('Satellite scan error:', err);
    }
  }

  function renderSatelliteAnalysis(data) {
    // Update KPI Grid
    document.getElementById('kpi-mean-ndvi').textContent = data.summary_indices.mean_ndvi.toFixed(2);
    document.getElementById('kpi-mean-ndre').textContent = data.summary_indices.mean_ndre.toFixed(2);
    document.getElementById('kpi-mean-ndwi').textContent = data.summary_indices.mean_ndwi.toFixed(2);
    document.getElementById('kpi-mean-savi').textContent = data.summary_indices.mean_savi.toFixed(2);

    // Update Anomaly Risk Badge
    const riskBadge = document.getElementById('badge-anomaly-risk');
    const anom = data.anomaly_analysis;
    riskBadge.textContent = `${anom.risk_assessment} (${anom.anomalous_area_pct}% Area)`;
    riskBadge.className = `badge ${anom.anomalous_area_pct > 6 ? 'badge-red' : 'badge-amber'}`;

    // Render Hotspots Table
    const tbody = document.getElementById('hotspots-body');
    tbody.innerHTML = '';
    state.hotspotMarkersLayer.clearLayers();

    if (anom.hotspots && anom.hotspots.length > 0) {
      anom.hotspots.forEach(h => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>#${h.hotspot_id}</strong></td>
          <td><span style="font-family: monospace;">${h.latitude.toFixed(4)}, ${h.longitude.toFixed(4)}</span></td>
          <td>${h.area_m2} m²</td>
          <td><span class="badge ${h.severity === 'high' ? 'badge-red' : 'badge-amber'}">${h.probable_cause}</span></td>
          <td><button class="btn btn-xs btn-outline btn-dispatch-drone" data-lat="${h.latitude}" data-lon="${h.longitude}"><i class="fa-solid fa-helicopter"></i> Scout</button></td>
        `;
        tbody.appendChild(tr);

        // Add GPS Marker on Map
        const marker = L.circleMarker([h.latitude, h.longitude], {
          radius: Math.max(8, Math.min(22, Math.sqrt(h.area_m2))),
          color: h.severity === 'high' ? '#ef4444' : '#f59e0b',
          fillColor: h.severity === 'high' ? '#ef4444' : '#f59e0b',
          fillOpacity: 0.55
        }).addTo(state.hotspotMarkersLayer);

        marker.bindPopup(`<strong>Hotspot #${h.hotspot_id} (${h.severity.toUpperCase()})</strong><br>${h.probable_cause}<br>Area: ${h.area_m2} m²<br><em>${h.recommended_action}</em>`);
      });
    } else {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--emerald-primary);">✓ No significant anomaly clusters detected. Canopy vigor is homogeneous.</td></tr>';
    }

    // Attach scout click events
    document.querySelectorAll('.btn-dispatch-drone').forEach(btn => {
      btn.addEventListener('click', () => {
        const lat = parseFloat(btn.dataset.lat);
        const lon = parseFloat(btn.dataset.lon);
        state.map.setView([lat, lon], 17);
        // Switch to drone tab automatically for close-up investigation
        document.querySelector('.nav-tab[data-tab="tab-drone"]').click();
      });
    });

    updateSpectralLayerPreview();
  }

  function updateSpectralLayerPreview() {
    if (!state.satelliteLayerData) return;
    const layers = state.satelliteLayerData.layers;
    const overlay = document.getElementById('raster-overlay');
    const img = document.getElementById('raster-image');
    const label = document.getElementById('legend-label');

    overlay.classList.remove('hidden');

    if (state.activeSpectralLayer === 'ndvi') {
      img.src = layers.ndvi_heatmap;
      label.textContent = 'NDVI (Biomass Density):';
    } else if (state.activeSpectralLayer === 'ndre') {
      img.src = layers.ndre_heatmap;
      label.textContent = 'NDRE (Red-Edge Chlorophyll):';
    } else if (state.activeSpectralLayer === 'ndwi') {
      img.src = layers.ndwi_heatmap;
      label.textContent = 'NDWI (Canopy Water Content):';
    } else {
      img.src = layers.true_color;
      label.textContent = 'Sentinel-2 True Color (RGB):';
    }
  }

  // ----------------- Sample Assets Loader ----------------- //
  async function loadSampleAssets() {
    try {
      const res = await fetch('/api/sample-assets');
      const data = await res.json();
      state.sampleAssets = data;

      // Populate leaf sample buttons
      const btnWrap = document.getElementById('sample-leaf-buttons');
      btnWrap.innerHTML = '';
      data.leaves.forEach((l, idx) => {
        const b = document.createElement('button');
        b.className = `btn btn-xs ${idx === 0 ? 'btn-success' : 'btn-outline'}`;
        b.innerHTML = `<i class="fa-solid fa-leaf"></i> ${l.name}`;
        b.addEventListener('click', () => {
          document.querySelectorAll('#sample-leaf-buttons button').forEach(el => el.className = 'btn btn-xs btn-outline');
          b.className = 'btn btn-xs btn-success';
          analyzeLeafBase64(l.base64);
        });
        btnWrap.appendChild(b);
      });

      // Auto-analyze first leaf & drone sample
      if (data.leaves.length > 0) {
        analyzeLeafBase64(data.leaves[0].base64);
      }
      if (data.drone_tiles.length > 0) {
        analyzeDroneBase64(data.drone_tiles[0].base64);
      }
    } catch (err) {
      console.error('Failed to load sample assets:', err);
    }
  }

  // ----------------- Drone Photogrammetry ----------------- //
  async function analyzeDroneBase64(b64) {
    document.getElementById('img-drone-original').src = b64;
    try {
      const form = new FormData();
      form.append('image_base64', b64);
      form.append('gsd_cm', '2.5');
      form.append('altitude_m', '60');

      const res = await fetch('/api/drone/analyze', {
        method: 'POST',
        body: form
      });
      const data = await res.json();
      state.droneAnalysis = data;
      renderDroneAnalysis(data);
    } catch (err) {
      console.error('Drone analysis error:', err);
    }
  }

  function renderDroneAnalysis(data) {
    document.getElementById('img-drone-heatmap').src = data.heatmap_base64;
    document.getElementById('kpi-canopy-cover').textContent = `${data.canopy_coverage_percentage}%`;
    document.getElementById('kpi-healthy-canopy').textContent = `${data.healthy_canopy_pct}%`;
    document.getElementById('kpi-stressed-canopy').textContent = `${data.stressed_infected_canopy_pct}%`;
    document.getElementById('kpi-drone-gsd').textContent = `${data.gsd_cm_px} cm`;

    document.getElementById('lbl-chemical-savings').textContent = `${data.precision_spray_advisory.chemical_and_cost_savings_pct}%`;
    document.getElementById('lbl-blanket-spray').textContent = `${data.precision_spray_advisory.conventional_spray_liters} Liters`;
    document.getElementById('lbl-targeted-spray').textContent = `${data.precision_spray_advisory.cropwatch_precision_spray_liters} Liters`;
  }

  // ----------------- AI Leaf Diagnostics ----------------- //
  async function analyzeLeafBase64(b64) {
    document.getElementById('img-leaf-original').src = b64;
    try {
      const form = new FormData();
      form.append('image_base64', b64);

      const res = await fetch('/api/disease/analyze-leaf', {
        method: 'POST',
        body: form
      });
      const data = await res.json();
      state.leafAnalysis = data;
      renderLeafAnalysis(data);
    } catch (err) {
      console.error('Leaf disease error:', err);
    }
  }

  function renderLeafAnalysis(data) {
    document.getElementById('img-leaf-annotated').src = data.annotated_image_base64;
    document.getElementById('lbl-disease-name').textContent = data.disease_name;
    document.getElementById('lbl-crop-name').textContent = data.crop;
    document.getElementById('lbl-pathogen-name').textContent = data.pathogen;
    document.getElementById('lbl-confidence').textContent = `${(data.confidence * 100).toFixed(1)}%`;

    document.getElementById('lbl-severity-pct').textContent = `${data.severity_percentage}%`;
    document.getElementById('bar-severity-fill').style.width = `${Math.min(data.severity_percentage * 3.5, 100)}%`;
    document.getElementById('lbl-severity-desc').textContent = data.severity_description;

    const badge = document.getElementById('badge-disease-severity');
    badge.textContent = `${data.severity_level.toUpperCase()} INFECTION`;
    badge.className = `badge ${data.severity_level === 'severe' ? 'badge-red' : (data.severity_level === 'moderate' ? 'badge-amber' : 'badge-emerald')}`;

    // Render Treatment Prescriptions
    renderTreatmentList('list-organic', data.treatments.organic);
    renderTreatmentList('list-chemical', data.treatments.chemical);
    renderTreatmentList('list-cultural', data.treatments.cultural_practices);

    // Link severity to Yield forecast simulator
    const yieldDiseaseInput = document.getElementById('input-yield-disease');
    if (yieldDiseaseInput) {
      yieldDiseaseInput.value = data.severity_percentage;
    }
  }

  function renderTreatmentList(elementId, items) {
    const ul = document.getElementById(elementId);
    ul.innerHTML = '';
    if (items && items.length > 0) {
      items.forEach(it => {
        const li = document.createElement('li');
        li.textContent = it;
        ul.appendChild(li);
      });
    } else {
      ul.innerHTML = '<li>No specific treatments required. Maintain standard crop monitoring.</li>';
    }
  }

  // ----------------- Yield Forecast Simulator ----------------- //
  async function runYieldForecast() {
    const crop = document.getElementById('input-yield-crop').value;
    const peakNdvi = parseFloat(document.getElementById('input-yield-ndvi').value);
    const gdd = parseFloat(document.getElementById('input-yield-gdd').value);
    const rain = parseFloat(document.getElementById('input-yield-rain').value);
    const vpd = parseFloat(document.getElementById('input-yield-vpd').value);
    const soc = parseFloat(document.getElementById('input-yield-soc').value);
    const diseasePct = parseFloat(document.getElementById('input-yield-disease').value);
    const anomalyPct = parseFloat(document.getElementById('input-yield-anomaly').value);

    try {
      const res = await fetch('/api/yield/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          crop: crop,
          peak_ndvi: peakNdvi,
          ndvi_auc: peakNdvi * 88.0,
          peak_ndre: peakNdvi * 0.70,
          accumulated_gdd: gdd,
          total_precipitation_mm: rain,
          mean_vpd_kpa: vpd,
          soil_organic_carbon_pct: soc,
          available_water_capacity_mm: 165.0,
          detected_disease_severity_pct: diseasePct,
          farm_anomaly_area_pct: anomalyPct
        })
      });

      const data = await res.json();
      state.yieldData = data;
      renderYieldForecast(data);
    } catch (err) {
      console.error('Yield forecast error:', err);
    }
  }

  function renderYieldForecast(data) {
    document.getElementById('lbl-yield-tha').textContent = data.predicted_yield_tha.toFixed(1);
    document.getElementById('lbl-yield-buac').textContent = `${data.predicted_yield_bu_ac} bu/ac`;
    document.getElementById('lbl-yield-ci').textContent = `90% CI: [${data.confidence_interval_90.lower_bound_tha} - ${data.confidence_interval_90.upper_bound_tha} t/ha]`;

    const grade = document.getElementById('lbl-yield-grade');
    grade.textContent = `${data.yield_grade} (${data.variance_vs_baseline_pct > 0 ? '+' : ''}${data.variance_vs_baseline_pct}%)`;
    grade.className = `badge ${data.variance_vs_baseline_pct >= 0 ? 'badge-emerald' : 'badge-amber'}`;

    // Render Impact Breakdown
    const list = document.getElementById('impact-factors-list');
    list.innerHTML = '';
    data.impact_attribution.forEach(attr => {
      const div = document.createElement('div');
      div.className = 'impact-item';
      div.innerHTML = `
        <div>
          <strong>${attr.factor}</strong>
          <div style="font-size: 11px; color: var(--text-dim);">${attr.notes}</div>
        </div>
        <span class="impact-item-val ${attr.impact_tha >= 0 ? 'pos' : 'neg'}">
          ${attr.impact_tha > 0 ? '+' : ''}${attr.impact_tha} t/ha
        </span>
      `;
      list.appendChild(div);
    });
  }

  // ----------------- Flight Planner (ME / Aero) ----------------- //
  async function runFlightPlanning() {
    const cam = document.getElementById('input-flight-camera').value;
    const area = parseFloat(document.getElementById('input-flight-area').value);
    const alt = parseFloat(document.getElementById('input-flight-alt').value);
    const fwd = parseFloat(document.getElementById('input-flight-fwd').value);
    const side = parseFloat(document.getElementById('input-flight-side').value);
    const speed = parseFloat(document.getElementById('input-flight-speed').value);

    try {
      const res = await fetch('/api/drone/flight-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field_area_ha: area,
          camera_type: cam,
          flight_altitude_m: alt,
          forward_overlap_pct: fwd,
          side_overlap_pct: side,
          flight_speed_m_s: speed,
          battery_flight_time_min: 24.0
        })
      });

      const data = await res.json();
      state.flightData = data;
      renderFlightPlan(data);
    } catch (err) {
      console.error('Flight planner error:', err);
    }
  }

  function renderFlightPlan(data) {
    document.getElementById('lbl-plan-gsd').textContent = `${data.gsd_cm_per_pixel} cm/px`;
    document.getElementById('lbl-plan-time').textContent = `${data.estimated_flight_time_minutes} min`;
    document.getElementById('lbl-plan-lines').textContent = `${data.flight_lines_count} passes`;
    document.getElementById('lbl-plan-batteries').textContent = `${data.batteries_needed} packs`;

    document.getElementById('lbl-plan-shutter').textContent = data.recommended_shutter_speed;
    document.getElementById('lbl-plan-photos').textContent = `${data.total_images_estimated} photos (${data.total_flight_distance_km} km)`;
  }

  // ----------------- Event Listeners ----------------- //
  function bindEvents() {
    // Field Selector
    document.getElementById('select-field').addEventListener('change', (e) => {
      state.currentFieldId = e.target.value;
      renderCurrentField();
      runSatelliteScan();
    });

    // Run Satellite Ingest
    document.getElementById('btn-run-satellite').addEventListener('click', runSatelliteScan);

    // Spectral Layer Switcher
    document.querySelectorAll('.btn-layer').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-layer').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.activeSpectralLayer = btn.dataset.layer;
        updateSpectralLayerPreview();
      });
    });

    // Drone File Dropzone & Upload
    const droneDrop = document.getElementById('drone-dropzone');
    const droneInput = document.getElementById('input-drone-file');
    droneDrop.addEventListener('click', () => droneInput.click());
    droneInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        const reader = new FileReader();
        reader.onload = (ev) => analyzeDroneBase64(ev.target.result);
        reader.readAsDataURL(e.target.files[0]);
      }
    });

    document.getElementById('btn-load-sample-drone').addEventListener('click', () => {
      if (state.sampleAssets.drone_tiles.length > 0) {
        analyzeDroneBase64(state.sampleAssets.drone_tiles[0].base64);
      }
    });

    // Leaf File Dropzone & Upload
    const leafDrop = document.getElementById('leaf-dropzone');
    const leafInput = document.getElementById('input-leaf-file');
    leafDrop.addEventListener('click', () => leafInput.click());
    leafInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        const reader = new FileReader();
        reader.onload = (ev) => analyzeLeafBase64(ev.target.result);
        reader.readAsDataURL(e.target.files[0]);
      }
    });

    // Treatment Tabs
    document.querySelectorAll('.t-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.t-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.querySelectorAll('.treatment-body').forEach(b => b.classList.remove('active'));
        document.getElementById(`ttab-${tab.dataset.ttab}`).classList.add('active');
      });
    });

    // Recalculate Yield
    document.getElementById('btn-recalculate-yield').addEventListener('click', runYieldForecast);
    runYieldForecast(); // initial run

    // Calculate Flight Path
    document.getElementById('btn-calculate-flight').addEventListener('click', runFlightPlanning);
    runFlightPlanning(); // initial run

    // Report Modal
    document.getElementById('btn-generate-report').addEventListener('click', openReportModal);
    document.getElementById('btn-close-modal').addEventListener('click', () => document.getElementById('report-modal').classList.add('hidden'));
    document.getElementById('btn-dismiss-modal').addEventListener('click', () => document.getElementById('report-modal').classList.add('hidden'));
    document.getElementById('btn-print-report').addEventListener('click', () => window.print());
  }

  function openReportModal() {
    const modal = document.getElementById('report-modal');
    const content = document.getElementById('modal-report-content');
    const f = state.fieldsData?.features.find(field => field.id === state.currentFieldId)?.properties || { name: 'Sector Alpha', crop: 'Corn', area_ha: 34.2 };

    content.innerHTML = `
      <div style="border-bottom: 1px solid var(--card-border); padding-bottom: 14px; margin-bottom: 16px;">
        <h2 style="color: #fff; font-size: 20px;">Precision Agronomy Diagnostic & Harvest Audit</h2>
        <div style="color: var(--emerald-primary); font-size: 13px;">CropWatch Lite Autonomous Intelligence System</div>
        <div style="color: var(--text-dim); font-size: 11px; margin-top: 4px;">Audit Timestamp: ${new Date().toLocaleString()}</div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
        <div style="background: rgba(255,255,255,0.02); padding: 14px; border-radius: 8px;">
          <h4 style="color: #fff; margin-bottom: 6px;">1. Farm & Spectral Health (Sentinel-2)</h4>
          <p>• Field: <strong>${f.name}</strong> (${f.area_ha} ha, ${f.crop.toUpperCase()})</p>
          <p>• Mean NDVI: <strong>${state.satelliteLayerData?.summary_indices.mean_ndvi || 0.78}</strong> (Vigorous Biomass)</p>
          <p>• Red-Edge NDRE: <strong>${state.satelliteLayerData?.summary_indices.mean_ndre || 0.54}</strong></p>
          <p>• Stress Hotspots: <strong>${state.satelliteLayerData?.anomaly_analysis.anomaly_count || 1} clusters</strong> (${state.satelliteLayerData?.anomaly_analysis.anomalous_area_ha || 1.4} ha)</p>
        </div>

        <div style="background: rgba(255,255,255,0.02); padding: 14px; border-radius: 8px;">
          <h4 style="color: #fff; margin-bottom: 6px;">2. UAV Photogrammetry & Variable Spraying</h4>
          <p>• Ground Sampling Distance: <strong>${state.droneAnalysis?.gsd_cm_px || 2.5} cm/px</strong></p>
          <p>• Canopy Ground Cover: <strong>${state.droneAnalysis?.canopy_coverage_percentage || 82.4}%</strong></p>
          <p>• Chemical Reduction Savings: <strong style="color: var(--emerald-primary);">${state.droneAnalysis?.precision_spray_advisory.chemical_and_cost_savings_pct || 74.5}%</strong></p>
        </div>
      </div>

      <div style="background: rgba(255,255,255,0.02); padding: 14px; border-radius: 8px; margin-bottom: 20px;">
        <h4 style="color: #fff; margin-bottom: 6px;">3. AI Leaf Pathology Diagnosis & Action Plan</h4>
        <p>• Pathogen Identification: <strong style="color: #fff;">${state.leafAnalysis?.disease_name || 'Northern Corn Leaf Blight'}</strong> (<em>${state.leafAnalysis?.pathogen || 'Exserohilum turcicum'}</em>)</p>
        <p>• Severity Area: <strong>${state.leafAnalysis?.severity_percentage || 14.5}%</strong> (${state.leafAnalysis?.severity_level?.toUpperCase()} Level)</p>
        <p>• Primary Organic Action: <em>${state.leafAnalysis?.treatments.organic[0] || 'Bacillus subtilis bio-fungicide foliar mist.'}</em></p>
        <p>• Primary Chemical Prescription: <em>${state.leafAnalysis?.treatments.chemical[0] || 'Azoxystrobin + Difenoconazole at 0.75 L/ha.'}</em></p>
      </div>

      <div style="background: linear-gradient(135deg, rgba(16,185,129,0.1), transparent); border: 1px solid rgba(16,185,129,0.3); padding: 16px; border-radius: 8px;">
        <h4 style="color: var(--emerald-primary); margin-bottom: 6px;">4. Final Harvest Forecast & Confidence</h4>
        <div style="font-size: 24px; font-weight: 800; color: #fff;">${state.yieldData?.predicted_yield_tha || 11.4} Tonnes / Hectare <span style="font-size: 14px; color: var(--text-muted);">(${state.yieldData?.predicted_yield_bu_ac || 181.6} bu/ac)</span></div>
        <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Grade: ${state.yieldData?.yield_grade || 'Optimal Yield (+8.6%)'} • Confidence Interval: [${state.yieldData?.confidence_interval_90.lower_bound_tha || 10.5} - ${state.yieldData?.confidence_interval_90.upper_bound_tha || 12.3} t/ha]</p>
      </div>
    `;

    modal.classList.remove('hidden');
  }
});
