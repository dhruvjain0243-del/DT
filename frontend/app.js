/* ============================================
   PARKWISE — app.js
   Connects to FastAPI backend at localhost:8000
   ============================================ */

const API = 'http://localhost:8000';

/* ─── State ─── */
let allLocations = [];
let lastRecommendations = [];
let lastFetchedAt = null;

/* ─── Helpers ─── */
const $ = id => document.getElementById(id);

function showToast(msg, duration = 3000) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), duration);
}

function minAgo(dt) {
  if (!dt) return '—';
  const diff = Math.round((Date.now() - dt) / 60000);
  return diff < 1 ? 'just now' : `${diff} min ago`;
}

function fitClass(pct) {
  if (pct >= 80) return 'fit-high';
  if (pct >= 50) return 'fit-med';
  return 'fit-low';
}

function fitLabel(pct) {
  if (pct >= 80) return `${Math.round(pct)}% fit`;
  if (pct >= 50) return `${Math.round(pct)}% fit`;
  return `${Math.round(pct)}% fit`;
}

function availClass(pct) {
  if (pct >= 60) return 'avail-high';
  if (pct >= 30) return 'avail-med';
  return 'avail-low';
}

function rankBgClass(rank) {
  return ['rank-1','rank-2','rank-3'][rank-1] || 'rank-1';
}

function markerClass(rank) {
  return ['marker-cyan','marker-purple','marker-amber','marker-gray'][rank-1] || 'marker-gray';
}

function parkingTypeIcon(type) {
  const icons = {
    Mall: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    Office: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="2" width="18" height="20" rx="1"/><line x1="9" y1="22" x2="9" y2="12"/><line x1="15" y1="22" x2="15" y2="12"/><rect x="9" y="12" width="6" height="10"/></svg>',
    Transit: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="1" width="18" height="16" rx="2"/><path d="M3 10h18"/><circle cx="7" cy="20" r="1"/><circle cx="17" cy="20" r="1"/><path d="M7 17h10"/></svg>',
    Campus: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    Street: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
  };
  return icons[type] || icons.Office;
}

/* ─── Tab Switching ─── */
function showTab(name, el) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  $(`tab-${name}`).classList.add('active');
  if (el) el.classList.add('active');

  if (name === 'livemap') renderMapLocations();
  if (name === 'recommendations') renderLocationsGrid();
}

/* ─── Health Check ─── */
async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    const ok = data.status === 'healthy';
    const pill = $('systemStatus');
    pill.classList.toggle('degraded', !ok);
    $('statusText').textContent = ok ? 'SYSTEM NOMINAL' : 'DEGRADED';
    $('kpiHealth').textContent = ok ? '99.9%' : '—';
    $('kpiHealthSub').textContent = ok ? 'All prediction services nominal' : data.model_status || 'Degraded';
    $('engineStatus').textContent = ok ? 'Forecast engine ready' : 'Engine degraded';
  } catch {
    $('statusText').textContent = 'OFFLINE';
    $('systemStatus').classList.add('degraded');
    $('kpiHealth').textContent = '—';
    $('kpiHealthSub').textContent = 'Cannot reach API';
    $('engineStatus').textContent = 'API unreachable';
  }
}

/* ─── Load Metrics ─── */
async function loadMetrics() {
  try {
    const res = await fetch(`${API}/metrics`);
    const data = await res.json();
    if (data.success) {
      const m = data.metrics;
      $('kpiMAE').textContent = `${m.model_mae?.toFixed(1)} spots`;
    }
  } catch { $('kpiMAE').textContent = '—'; }
}

/* ─── Load Locations ─── */
async function loadLocations() {
  try {
    const res = await fetch(`${API}/locations`);
    const data = await res.json();
    if (data.success) {
      allLocations = data.locations;
      $('kpiLocations').textContent = data.count;
      $('mapCount').textContent = `${data.count} monitored nodes`;
      populateFeedbackDropdown();
    }
  } catch { $('kpiLocations').textContent = '—'; }
}

function populateFeedbackDropdown() {
  const sel = $('fbParkingId');
  sel.innerHTML = '<option value="">Select location&hellip;</option>';
  allLocations.forEach(loc => {
    const opt = document.createElement('option');
    opt.value = loc.parking_id;
    opt.textContent = `${loc.parking_id} — ${loc.parking_name}`;
    sel.appendChild(opt);
  });
}

/* ─── Fetch Recommendations ─── */
async function fetchRecommendations() {
  const btn = $('findBtn');
  const btnText = $('findBtnText');
  btn.disabled = true;
  btnText.textContent = 'Fetching…';

  const arrival = $('arrivalTime').value;
  const preference = $('preference').value;
  const parkingType = $('parkingType').value;

  const body = { preference, parking_type: parkingType };
  if (arrival) {
    // Convert datetime-local to "YYYY-MM-DD HH:MM:SS"
    body.arrival_timestamp = arrival.replace('T', ' ') + ':00';
  }

  try {
    const res = await fetch(`${API}/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.success) {
      lastRecommendations = data.recommendations;
      lastFetchedAt = Date.now();
      renderRecCards(data.recommendations);
      updateKpiConfidence(data.recommendations);
      updateNetworkPulse(data.recommendations);
      updateSnapshotTime();
      showToast('Recommendations updated');
    } else {
      showToast('Error: ' + (data.detail || 'Unknown error'));
    }
  } catch (e) {
    showToast('Cannot reach API — is the backend running?');
    renderFallbackCards();
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Find parking availability';
  }
}

function updateSnapshotTime() {
  $('snapshotTime').textContent = `Live snapshot · ${minAgo(lastFetchedAt)}`;
  $('pulseSync').innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Last model sync · Live snapshot · ${minAgo(lastFetchedAt)}`;
}

function updateKpiConfidence(recs) {
  if (!recs || !recs.length) return;
  const highConf = recs.filter(r => r.confidence === 'High').length;
  const pct = Math.round((highConf / recs.length) * 100);
  $('kpiConfidence').textContent = pct + '%';
}

function updateNetworkPulse(recs) {
  if (!recs || !recs.length) return;
  const avgAvail = Math.round(recs.reduce((s, r) => s + r.availability_pct, 0) / recs.length);
  $('pulseAvail').textContent = avgAvail + '%';
  $('progressAvail').style.width = avgAvail + '%';

  const highConf = recs.filter(r => r.confidence === 'High').length;
  const confPct = Math.round((highConf / recs.length) * 100);
  $('pulseConf').textContent = confPct + '%';
  $('progressConf').style.width = confPct + '%';

  // Alert: find best mover
  const best = recs[0];
  if (best) {
    $('alertBody').textContent = `${best.parking_name} is ${best.availability_status}. ${best.explanation.split('.')[0]}.`;
  }
}

/* ─── Render Rec Cards ─── */
function renderRecCards(recs) {
  const container = $('recCards');
  container.innerHTML = '';
  recs.forEach(r => {
    container.appendChild(buildRecCard(r));
  });
  // also update recommendations tab
  renderLocationsGrid();
}

function buildRecCard(r) {
  const pct = r.availability_pct;
  const card = document.createElement('div');
  card.className = 'rec-card';
  card.onclick = () => { showTab('livemap', $('navLivemap')); };
  card.innerHTML = `
    <div class="rec-card-rank-badge ${rankBgClass(r.rank)}">#${r.rank}</div>
    <div class="rec-card-fit ${fitClass(pct)}">${fitLabel(pct)}</div>
    <div class="rec-card-name" title="${r.parking_name}">${r.parking_name}</div>
    <div class="rec-card-type">${parkingTypeIcon(r.parking_type)} ${r.parking_type} parking</div>
    <div class="rec-card-spots-label">PREDICTED OPEN SPOTS</div>
    <div class="rec-card-spots">${r.predicted_available_spaces}<span class="rec-card-spots-total"> / ${r.total_spaces}</span></div>
    <div class="rec-card-meta">
      <div class="rec-card-price"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> $${r.price_per_hour.toFixed(2)}</div>
      <div><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg> ${r.distance_km.toFixed(1)} km</div>
    </div>
    <div class="rec-avail-bar"><div class="rec-avail-fill ${availClass(pct)}" style="width:${pct}%"></div></div>
    <div class="rec-card-explanation">${r.explanation}</div>
    <div class="rec-card-actions">
      <button class="btn-action" onclick="event.stopPropagation();showTab('livemap',$('navLivemap'))">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
        Focus map
      </button>
      <button class="btn-action" onclick="event.stopPropagation();openFeedbackModalFor('${r.parking_id}')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      </button>
    </div>
  `;
  return card;
}

function renderFallbackCards() {
  const container = $('recCards');
  container.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><p style="color:#ef4444">Backend offline — start the FastAPI server on port 8000</p></div>';
}

/* ─── Recommendations Grid (full page) ─── */
let _filterData = [];

function renderLocationsGrid() {
  _filterData = [...lastRecommendations];
  filterLocations();
}

function filterLocations() {
  const q = ($('locationSearch')?.value || '').toLowerCase();
  const sort = $('locationSort')?.value || 'rank';
  const grid = $('locationsGrid');
  if (!grid) return;

  let data = _filterData.filter(r =>
    r.parking_name.toLowerCase().includes(q) ||
    r.parking_type.toLowerCase().includes(q)
  );

  data.sort((a, b) => {
    if (sort === 'availability') return b.availability_pct - a.availability_pct;
    if (sort === 'price') return a.price_per_hour - b.price_per_hour;
    if (sort === 'distance') return a.distance_km - b.distance_km;
    return a.rank - b.rank;
  });

  if (!data.length) {
    grid.innerHTML = '<div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#00e5ff" stroke-width="1"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><p>Run a query from the Overview tab to see ranked results here.</p></div>';
    return;
  }

  grid.innerHTML = '';
  data.forEach(r => {
    const card = document.createElement('div');
    card.className = 'location-card';
    const pct = r.availability_pct;
    card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <div style="display:flex;align-items:center;gap:8px">
          <span class="rec-card-rank-badge ${rankBgClass(r.rank)}" style="width:22px;height:22px;font-size:11px">#${r.rank}</span>
          <div>
            <div style="font-weight:700;font-size:14px">${r.parking_name}</div>
            <div style="font-size:11px;color:var(--text-muted)">${r.parking_type}</div>
          </div>
        </div>
        <span class="rec-card-fit ${fitClass(pct)}">${fitLabel(pct)}</span>
      </div>
      <div class="rec-avail-bar"><div class="rec-avail-fill ${availClass(pct)}" style="width:${pct}%"></div></div>
      <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--text-secondary)">
        <span><b style="color:var(--text-primary);font-size:20px">${r.predicted_available_spaces}</b> / ${r.total_spaces} spots</span>
        <span style="color:var(--cyan);font-weight:700">$${r.price_per_hour.toFixed(2)}/hr</span>
        <span>${r.distance_km.toFixed(1)} km</span>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--text-muted)">${r.explanation}</div>
      <div style="margin-top:6px;font-size:11px;font-family:var(--font-mono);color:var(--text-muted)">${r.availability_status} · Confidence: ${r.confidence}</div>
    `;
    grid.appendChild(card);
  });
}

/* ─── Map Markers ─── */
function renderMapLocations() {
  const list = $('mapLocationsList');
  const markers = $('mapMarkers');
  if (!list || !markers) return;

  list.innerHTML = '';
  markers.innerHTML = '';

  const data = lastRecommendations.length ? lastRecommendations : allLocations.map((l,i) => ({
    ...l,
    rank: i+1,
    predicted_available_spaces: Math.round(l.total_spaces * 0.65),
    availability_pct: 65,
    availability_status: 'Available',
    confidence: 'Medium',
    distance_km: l.distance_km || 1.0,
    price_per_hour: l.price_per_hour || 5.0,
    explanation: 'Run a query for live predictions.',
  }));

  // Map bounds: bbox=-74.02,40.69,-73.95,40.77
  const minLng = -74.02, maxLng = -73.95;
  const minLat = 40.69,  maxLat = 40.77;

  data.forEach((r, i) => {
    const lat = r.latitude || (minLat + Math.random() * (maxLat - minLat));
    const lng = r.longitude || (minLng + Math.random() * (maxLng - minLng));

    // Map to pixel % of iframe
    const xPct = ((lng - minLng) / (maxLng - minLng)) * 100;
    const yPct = (1 - (lat - minLat) / (maxLat - minLat)) * 100;

    const marker = document.createElement('div');
    marker.className = 'map-marker';
    marker.style.left = xPct + '%';
    marker.style.top  = yPct + '%';
    marker.innerHTML = `
      <div class="map-marker-inner ${markerClass(r.rank)}">
        <span>${r.rank || i+1}</span>
      </div>
      <div class="map-marker-tooltip">
        <b>${r.parking_name}</b><br/>
        ${r.predicted_available_spaces ?? '—'}/${r.total_spaces ?? '—'} spots · $${(r.price_per_hour||0).toFixed(2)}/hr
      </div>
    `;
    markers.appendChild(marker);

    // Sidebar list item
    const pct = r.availability_pct || 65;
    const item = document.createElement('div');
    item.className = 'map-loc-item';
    const dotColor = pct >= 60 ? 'var(--cyan)' : pct >= 30 ? 'var(--amber)' : '#ef4444';
    item.innerHTML = `
      <div class="map-loc-dot" style="background:${dotColor}"></div>
      <div class="map-loc-info">
        <div class="map-loc-name">${r.parking_name}</div>
        <div class="map-loc-meta">${r.parking_type} · ${(r.distance_km||0).toFixed(1)} km</div>
      </div>
      <div class="map-loc-avail" style="color:${dotColor}">${Math.round(pct)}%</div>
    `;
    list.appendChild(item);
  });
}

/* ─── Feedback Modal ─── */
function openFeedbackModal() {
  $('feedbackModal').classList.add('open');
}

function openFeedbackModalFor(parkingId) {
  $('fbParkingId').value = parkingId;
  openFeedbackModal();
}

function closeFeedbackModal(e) {
  if (!e || e.target === $('feedbackModal')) {
    $('feedbackModal').classList.remove('open');
    $('fbMsg').style.display = 'none';
    $('fbMsg').textContent = '';
  }
}

async function submitFeedback() {
  const parking_id = $('fbParkingId').value;
  const actual_status = $('fbStatus').value;
  const comment = $('fbComment').value;

  if (!parking_id) { showToast('Please select a parking location.'); return; }

  try {
    const res = await fetch(`${API}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parking_id, actual_status, comment }),
    });
    const data = await res.json();
    if (data.success) {
      $('fbMsg').textContent = data.message;
      $('fbMsg').style.display = 'block';
      showToast('Feedback submitted. Thank you!');
      setTimeout(() => closeFeedbackModal(), 1800);
    } else {
      showToast('Error: ' + (data.detail || 'Submission failed'));
    }
  } catch {
    showToast('Cannot reach API — is the backend running?');
  }
}

/* ─── Refresh All ─── */
function refreshAll() {
  checkHealth();
  loadMetrics();
  loadLocations();
  if (lastRecommendations.length) fetchRecommendations();
}

/* ─── Footer Clock ─── */
function updateFooter() {
  const now = new Date();
  $('footerTimestamp').textContent =
    `PREDICTION LAYER V.3 · ${now.toLocaleTimeString('en-US',{hour12:false})} LOCAL`;
}

/* ─── Snapshot Timer ─── */
setInterval(() => {
  if (lastFetchedAt) updateSnapshotTime();
}, 30000);

/* ─── Init ─── */
async function init() {
  await checkHealth();
  await loadMetrics();
  await loadLocations();
  // Auto-fetch default recommendations on load
  await fetchRecommendations();
  updateFooter();
  setInterval(updateFooter, 1000);
}

document.addEventListener('DOMContentLoaded', init);
