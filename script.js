const $ = s => document.querySelector(s);
let state = {};

function switchPortal(pName) {
  document.querySelectorAll('.portal-view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.portal-btn').forEach(b => b.classList.remove('active'));

  if (pName === 'govt') {
    $('#portalGovt').classList.add('active');
    $('#pNavGovt').classList.add('active');
  } else if (pName === 'pass') {
    $('#portalPass').classList.add('active');
    $('#pNavPass').classList.add('active');
    updatePassengerView();
  } else if (pName === 'sim') {
    $('#portalSim').classList.add('active');
    $('#pNavSim').classList.add('active');
  }
}

async function postConfig(streamNum, cfg) {
  try {
    const r = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({stream: streamNum, ...cfg})
    });
    const j = await r.json();
    if (j.ok) apply(j);
  } catch(e) {}
}

function apply(s) {
  state = s;

  if (s.recommendation) {
    $('#dualRecommendation').innerHTML = `<span>${s.recommendation}</span><span style="font-size: 10.5px; font-weight: 700; padding: 3px 8px; background: rgba(106,126,252,0.15); border-radius: 4px; color: #6A7EFC;">LIVE REAL-TIME</span>`;
  }

  if (s.stream1) {
    const s1 = s.stream1;
    $('#s1Loc').textContent = (s1.location || 'Stream 1').replace('Stream 1: ', '').replace('Stream 2: ', '');
    const eff1 = s1.effective_occ_pct || s1.occupancy_pct || 0;
    $('#s1Occ').innerHTML = `${s1.count || 0} / ${s1.capacity || 1} <strong style="color: ${eff1 > 65 ? '#FF5656' : 'var(--text-main)'};">(${eff1}% Eff.)</strong><div style="font-size: 9px; color: var(--text-muted); font-weight: 400; margin-top: 2px;">ⓘ ${s1.explanation || 'Includes camera + incoming load'}</div>`;
    $('#s1Status').textContent = `${s1.density_status || 'LOW'}`;
    $('#s1Status').style.color = eff1 > 65 ? '#FF5656' : (eff1 > 35 ? '#f59e0b' : '#6A7EFC');
    $('#s1ModelBadge').textContent = (s1.detector || 'P2PNET').toUpperCase();
    if ($('#simLocHead1')) $('#simLocHead1').textContent = `Stream 1 Simulation (${s1.location || 'Stream 1'})`;

    // Breakdown & Zone State
    const hasZone1 = s1.zones && s1.zones.length > 0;
    if ($('#s1ZoneBadge')) $('#s1ZoneBadge').style.display = hasZone1 ? 'inline-block' : 'none';
    if ($('#btnClearZone1')) $('#btnClearZone1').style.display = hasZone1 ? 'inline-block' : 'none';
    if ($('#s1Breakdown')) {
      if (hasZone1) {
        let activeZones = [];
        let breakdownStr = `Total: ${s1.total_count || s1.count}`;
        if (s1.zone_counts) {
            s1.zone_counts.forEach(z => {
                breakdownStr += ` | ${z.name}: ${z.count}`;
                activeZones.push(z.name);
            });
        }
        $('#s1Breakdown').textContent = breakdownStr;
        $('#s1ZoneStateText').textContent = `📍 Zones Active: ${activeZones.join(', ')}`;
        $('#s1ZoneStateText').style.color = '#10B981';
      } else {
        $('#s1Breakdown').textContent = `Total: ${s1.count} | Zone: N/A`;
        $('#s1ZoneStateText').textContent = `No Zone Active (Full Frame)`;
        $('#s1ZoneStateText').style.color = '#64748B';
      }
    }

    if (document.activeElement !== $('#locInput1')) $('#locInput1').value = s1.location || '';
    if (document.activeElement !== $('#cap1')) $('#cap1').value = s1.capacity || 120;
    if (document.activeElement !== $('#cam1') && s1.source) $('#cam1').value = s1.source;

    document.querySelectorAll('[data-s1det]').forEach(b =>
      b.classList.toggle('on', b.dataset.s1det === s1.detector));
  }

  if (s.stream2) {
    const s2 = s.stream2;
    $('#s2Loc').textContent = (s2.location || 'Stream 2').replace('Stream 1: ', '').replace('Stream 2: ', '');
    const eff2 = s2.effective_occ_pct || s2.occupancy_pct || 0;
    $('#s2Occ').innerHTML = `${s2.count || 0} / ${s2.capacity || 1} <strong style="color: ${eff2 > 65 ? '#FF5656' : 'var(--text-main)'};">(${eff2}% Eff.)</strong><div style="font-size: 9px; color: var(--text-muted); font-weight: 400; margin-top: 2px;">ⓘ ${s2.explanation || 'Includes camera + incoming load'}</div>`;
    $('#s2Status').textContent = `${s2.density_status || 'LOW'}`;
    $('#s2Status').style.color = eff2 > 65 ? '#FF5656' : (eff2 > 35 ? '#f59e0b' : '#6A7EFC');
    $('#s2ModelBadge').textContent = (s2.detector || 'P2PNET').toUpperCase();
    if ($('#simLocHead2')) $('#simLocHead2').textContent = `Stream 2 Simulation (${s2.location || 'Stream 2'})`;

    // Breakdown & Zone State
    const hasZone2 = s2.zones && s2.zones.length > 0;
    if ($('#s2ZoneBadge')) $('#s2ZoneBadge').style.display = hasZone2 ? 'inline-block' : 'none';
    if ($('#btnClearZone2')) $('#btnClearZone2').style.display = hasZone2 ? 'inline-block' : 'none';
    if ($('#s2Breakdown')) {
      if (hasZone2) {
        let activeZones = [];
        let breakdownStr = `Total: ${s2.total_count || s2.count}`;
        if (s2.zone_counts) {
            s2.zone_counts.forEach(z => {
                breakdownStr += ` | ${z.name}: ${z.count}`;
                activeZones.push(z.name);
            });
        }
        $('#s2Breakdown').textContent = breakdownStr;
        $('#s2ZoneStateText').textContent = `📍 Zones Active: ${activeZones.join(', ')}`;
        $('#s2ZoneStateText').style.color = '#10B981';
      } else {
        $('#s2Breakdown').textContent = `Total: ${s2.count} | Zone: N/A`;
        $('#s2ZoneStateText').textContent = `No Zone Active (Full Frame)`;
        $('#s2ZoneStateText').style.color = '#64748B';
      }
    }

    if (document.activeElement !== $('#locInput2')) $('#locInput2').value = s2.location || '';
    if (document.activeElement !== $('#cap2')) $('#cap2').value = s2.capacity || 800;
    if (document.activeElement !== $('#cam2') && s2.source) $('#cam2').value = s2.source;

    document.querySelectorAll('[data-s2det]').forEach(b =>
      b.classList.toggle('on', b.dataset.s2det === s2.detector));
  }

  // Update Predictive Command Analytics Bar
  const a1 = s.stream1?.analytics || {};
  const a2 = s.stream2?.analytics || {};
  const minOverflow = Math.min(a1.overflow_countdown_min !== undefined ? a1.overflow_countdown_min : 999, a2.overflow_countdown_min !== undefined ? a2.overflow_countdown_min : 999);
  
  if ($('#cmdOverflowCountdown')) {
    if (minOverflow <= 15) {
      $('#cmdOverflowCountdown').textContent = `⏳ OVERFLOW FORECASTED IN ${minOverflow} MINS`;
      $('#cmdOverflowCountdown').style.color = '#FF5656';
    } else {
      $('#cmdOverflowCountdown').textContent = `🟢 STABLE (No Overflow Forecasted)`;
      $('#cmdOverflowCountdown').style.color = '#10B981';
    }
  }

  const totalStranded = (a1.stranded_count || 0) + (a2.stranded_count || 0);
  const totalRelief = (a1.relief_buses_needed || 0) + (a2.relief_buses_needed || 0);
  if ($('#cmdStrandedIndex')) {
    $('#cmdStrandedIndex').textContent = `${totalStranded} Commuters Stranded`;
    $('#cmdStrandedIndex').style.color = totalStranded > 0 ? '#FF5656' : '#6A7EFC';
  }
  if ($('#cmdReliefUnits')) {
    $('#cmdReliefUnits').textContent = totalStranded > 0 ? `🚨 ${totalRelief} Emergency Relief Shuttles Suggested` : `0 Relief Buses Required`;
  }

  // Update Government Alert protocol & Threshold Breach Alert state
  const eff1 = s.stream1?.effective_occ_pct || s.stream1?.occupancy_pct || 0;
  const eff2 = s.stream2?.effective_occ_pct || s.stream2?.occupancy_pct || 0;
  const maxOcc = Math.max(eff1, eff2);
  const alertCard = $('#alertCard');
  const alertMsg = $('#alertMsg');
  if (maxOcc > 65) {
    alertCard.style.borderColor = '#FF5656';
    alertCard.style.background = 'rgba(255,86,86,0.18)';
    alertCard.style.boxShadow = '0 0 16px rgba(255,86,86,0.3)';
    alertMsg.innerHTML = `<div style="font-size: 13px; font-weight: 800; color:#FF5656; margin-bottom: 2px;">🚨 THRESHOLD BREACHED (CRITICAL OVERFLOW)!</div>
      <div style="font-size: 11.5px; color:var(--text-main);">Effective congestion reached <strong style="color:#FF5656;">${maxOcc}%</strong> (combining camera density + incoming transit load). Standard Operating Procedure: <strong>Open auxiliary exit gates</strong> and <strong>dispatch emergency feeder buses</strong> to relieve platform pressure immediately.</div>`;
  } else {
    alertCard.style.borderColor = 'rgba(106,126,252,0.4)';
    alertCard.style.background = 'rgba(106,126,252,0.06)';
    alertCard.style.boxShadow = 'none';
    alertMsg.innerHTML = `Normal crowd flow. All platform capacities within safety thresholds.`;
  }

  fetchTrends();
  updatePassengerView();
}

async function fetchTrends() {
  try {
    const res = await fetch('/api/trends');
    const data = await res.json();
    if (data.history) renderTrendBars(data.history);
  } catch(e) {}
}

function renderTrendBars(history) {
  const container = $('#trendBars');
  if (!history || !history.length) {
    container.innerHTML = `<div style="font-size: 11px; color: var(--text-muted); padding: 20px;">Gathering live trend data...</div>`;
    return;
  }
  const slice = history.slice(-14);
  container.innerHTML = slice.map((h, idx) => {
    let s1Title = `Stream 1: ${h.stream1_occ}% (Total: ${h.stream1_count})`;
    if (h.stream1_zones && h.stream1_zones.length > 0) {
      s1Title += ` | ` + h.stream1_zones.map(z => `${z.name}: ${z.count}`).join(', ');
    }
    let s2Title = `Stream 2: ${h.stream2_occ}% (Total: ${h.stream2_count})`;
    if (h.stream2_zones && h.stream2_zones.length > 0) {
      s2Title += ` | ` + h.stream2_zones.map(z => `${z.name}: ${z.count}`).join(', ');
    }
    return `
    <div class="trend-bar-group" title="${h.timestamp}\n${s1Title}\n${s2Title}">
      <div class="trend-bars-pair">
        <div style="display:flex; gap:2px; height:100%; align-items:flex-end; flex:1; justify-content:center;">
          <div class="bar-s1" style="height: ${Math.max(3, h.stream1_occ)}%; width: 10px;"></div>
          ${(h.stream1_zones || []).map((z, i) => `<div style="height: ${Math.max(3, (z.count / (h.stream1_cap || 100))*100)}%; width: 6px; background: ${i%2===0 ? '#00F2FE' : '#FF6464'}; opacity: 0.9; border-radius: 2px 2px 0 0;"></div>`).join('')}
        </div>
        <div style="display:flex; gap:2px; height:100%; align-items:flex-end; flex:1; justify-content:center;">
          <div class="bar-s2" style="height: ${Math.max(3, h.stream2_occ)}%; width: 10px;"></div>
          ${(h.stream2_zones || []).map((z, i) => `<div style="height: ${Math.max(3, (z.count / (h.stream2_cap || 100))*100)}%; width: 6px; background: ${i%2===0 ? '#00F2FE' : '#FF6464'}; opacity: 0.9; border-radius: 2px 2px 0 0;"></div>`).join('')}
        </div>
      </div>
      <div style="font-size: 10px; font-weight: 700; color: #475569; margin-top: 6px; text-align: center; font-family: 'JetBrains Mono', monospace;">${idx}</div>
    </div>
    `;
  }).join('');
}

let currentPassengerData = null;
let mapAnimInterval = null;
let mapPos = 0;

function switchPassScreen(screenName) {
  const screens = ['Search', 'Options', 'Crowd', 'Map'];
  screens.forEach(s => {
    const el = $(`#screen${s}`);
    const nav = $(`#navBtn${s}`);
    if (el) el.style.display = (s === screenName) ? 'block' : 'none';
    if (nav) nav.style.color = (s === screenName) ? '#6A7EFC' : '#94A3B8';
  });

  const titleMap = {
    'Search': 'Search Journey',
    'Options': 'Best Options',
    'Crowd': 'Live Crowd Detail',
    'Map': 'Route Map & Tracker'
  };
  if ($('#passAppTitle')) $('#passAppTitle').textContent = titleMap[screenName] || 'Commuter Guide';

  if (screenName === 'Map') {
    startVehicleMapAnimation();
  } else if (mapAnimInterval) {
    clearInterval(mapAnimInterval);
    mapAnimInterval = null;
  }
}

async function executeSearchJourney() {
  await updatePassengerView();
  switchPassScreen('Options');
}

async function updatePassengerView() {
  try {
    const selectedStream = $('#pSelectOrigin').value === 'stream1' ? 1 : 2;
    const dest = $('#pSelectDest').value;
    const res = await fetch(`/api/passenger/status?selected_stream=${selectedStream}&destination=${dest}`);
    const data = await res.json();
    currentPassengerData = data;

    if (data.recommended_best) {
      const b = data.recommended_best;
      if ($('#pBestName')) $('#pBestName').textContent = b.name;
      if ($('#pBestReason')) $('#pBestReason').textContent = b.reason;
    }

    if (data.options) {
      const container = $('#pRouteMatrixContainer');
      if (container) {
        container.innerHTML = data.options.map((opt, idx) => `
          <div class="card" onclick="inspectRouteOption(${idx})" style="border-color: ${opt.occupancy_pct > 75 ? 'rgba(255,86,86,0.4)' : 'rgba(106,126,252,0.3)'}; background: var(--panel-bg); cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.03); transition: transform 0.15s; margin-bottom: 0;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">${opt.mode === 'bus' ? '🚍' : '🚆'}</span>
                <div>
                  <div style="font-size: 13px; font-weight: 800; color: var(--text-main);">${opt.mode === 'bus' ? 'Bus Transit' : 'Train Line'}</div>
                  <div style="font-size: 10px; color: var(--text-muted);">${opt.location}</div>
                </div>
              </div>
              <div style="text-align: right;">
                ${idx === 0 ? '<span class="status-badge" style="background: #10B981; color: #fff; font-weight: 800; padding: 2px 6px; font-size: 9px;">BEST</span>' : ''}
                <div style="font-size: 13px; font-weight: 800; color: var(--text-main); margin-top: 2px;">${opt.total_time} min</div>
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10.5px; margin-top: 4px; background: #F8FAFC; padding: 5px 8px; border-radius: 6px; border: 1px solid #E2E8F0;">
              <span style="color: var(--text-muted);">Crowd Occupancy:</span>
              <strong style="color: ${opt.occupancy_pct > 75 ? '#FF5656' : (opt.occupancy_pct > 35 ? '#f59e0b' : '#10B981')}; font-size: 11px;">
                ${opt.status} (${opt.occupancy_pct}%)
              </strong>
            </div>
          </div>
        `).join('');
      }

      // Auto inspect best route for screen 3 & 4 setup
      if (data.options.length > 0) inspectRouteOption(0, false);
    }
  } catch(e) {}
}

let isSatelliteMode = false;
let currentJourneyTotalMin = 14;

function toggleMapStyle() {
  isSatelliteMode = !isSatelliteMode;
  const btn = $('#btnMapStyle');
  const container = $('#mapCanvasContainer');
  const vectorGrid = $('#mapVectorGrid');
  const satGrid = $('#mapSatelliteGrid');
  const pathLine = $('#mapPathLine');
  const gpsBadge = $('#mapGpsBadge');
  const originText = $('#mapOriginText');
  const hubText = $('#mapHubText');
  const destText = $('#mapDestNodeLabel');

  if (isSatelliteMode) {
    btn.innerHTML = '🗺️ Vector View';
    btn.style.background = 'rgba(255,255,255,0.9)';
    btn.style.color = '#0F172A';
    btn.style.borderColor = '#CBD5E1';
    container.style.background = '#090F1E';

    if (vectorGrid) vectorGrid.style.display = 'none';
    if (satGrid) satGrid.style.display = 'block';

    if (pathLine) pathLine.setAttribute('stroke', '#00F2FE');
    if (gpsBadge) {
      gpsBadge.style.background = 'rgba(15,23,42,0.85)';
      gpsBadge.style.color = '#38BDF8';
      gpsBadge.style.borderColor = 'rgba(56,189,248,0.4)';
    }

    if (originText) originText.setAttribute('fill', '#E2E8F0');
    if (hubText) hubText.setAttribute('fill', '#94A3B8');
    if (destText) destText.setAttribute('fill', '#E2E8F0');
  } else {
    btn.innerHTML = '🛰️ Satellite View';
    btn.style.background = 'rgba(15,23,42,0.85)';
    btn.style.color = '#38BDF8';
    btn.style.borderColor = 'rgba(56,189,248,0.4)';
    container.style.background = '#F1F5F9';

    if (vectorGrid) vectorGrid.style.display = 'block';
    if (satGrid) satGrid.style.display = 'none';

    if (pathLine) pathLine.setAttribute('stroke', '#6A7EFC');
    if (gpsBadge) {
      gpsBadge.style.background = 'rgba(255,255,255,0.9)';
      gpsBadge.style.color = 'var(--text-main)';
      gpsBadge.style.borderColor = '#CBD5E1';
    }

    if (originText) originText.setAttribute('fill', 'var(--text-main)');
    if (hubText) hubText.setAttribute('fill', '#475569');
    if (destText) destText.setAttribute('fill', 'var(--text-main)');
  }
}

function inspectRouteOption(idx, autoSwitch = true) {
  if (!currentPassengerData || !currentPassengerData.options || !currentPassengerData.options[idx]) return;
  const opt = currentPassengerData.options[idx];
  currentJourneyTotalMin = opt.total_time || 14;
  
  if ($('#cSelectedLocTitle')) $('#cSelectedLocTitle').textContent = `${opt.name} - Live Crowd`;
  if ($('#crowdRingPct')) {
    $('#crowdRingPct').textContent = `${opt.occupancy_pct}%`;
    $('#crowdRingPct').style.color = opt.occupancy_pct > 75 ? '#FF5656' : (opt.occupancy_pct > 35 ? '#f59e0b' : '#10B981');
  }
  if ($('#crowdRingPath')) {
    const strokeColor = opt.occupancy_pct > 75 ? '#FF5656' : (opt.occupancy_pct > 35 ? '#f59e0b' : '#10B981');
    $('#crowdRingPath').setAttribute('stroke', strokeColor);
    $('#crowdRingPath').setAttribute('stroke-dasharray', `${opt.occupancy_pct}, 100`);
  }
  if ($('#crowdBadgeLevel')) {
    $('#crowdBadgeLevel').textContent = `${opt.status} (${opt.occupancy_pct}% OCCUPANCY)`;
    $('#crowdBadgeLevel').style.color = opt.occupancy_pct > 75 ? '#FF5656' : (opt.occupancy_pct > 35 ? '#f59e0b' : '#10B981');
    $('#crowdBadgeLevel').style.background = opt.occupancy_pct > 75 ? 'rgba(255,86,86,0.15)' : 'rgba(16,185,129,0.15)';
  }
  if ($('#crowdTrendBadge')) $('#crowdTrendBadge').textContent = opt.trend;
  if ($('#crowdInboundStatus')) $('#crowdInboundStatus').textContent = `${opt.vehicle_eta} min ETA (${opt.vehicle_occ}% Full)`;

  // Update Map metadata
  if ($('#mapDestNodeLabel')) $('#mapDestNodeLabel').textContent = currentPassengerData.destination_label || 'Destination';
  if ($('#mapTimelineOrigin')) $('#mapTimelineOrigin').textContent = opt.location;
  if ($('#mapTimelineDest')) $('#mapTimelineDest').textContent = currentPassengerData.destination_label || 'Destination';
  if ($('#mapArrivalEta')) $('#mapArrivalEta').textContent = `${opt.total_time} mins`;
  if ($('#mapVehicleLoad')) $('#mapVehicleLoad').textContent = `${opt.vehicle_occ}% Full`;

  if (autoSwitch) switchPassScreen('Crowd');
}

function startVehicleMapAnimation() {
  if (mapAnimInterval) clearInterval(mapAnimInterval);
  const icon = $('#mapMovingVehicle');
  if (!icon) return;

  // Very slow, realistic vehicle speed progression
  mapAnimInterval = setInterval(() => {
    mapPos += 0.0006;
    if (mapPos >= 1.0) mapPos = 0.0;

    // Quadratic bezier curve math M 30 130 Q 110 20 230 130
    const t = mapPos;
    const x = Math.pow(1-t, 2) * 30 + 2 * (1-t) * t * 110 + Math.pow(t, 2) * 230;
    const y = Math.pow(1-t, 2) * 130 + 2 * (1-t) * t * 20 + Math.pow(t, 2) * 130;
    icon.setAttribute('transform', `translate(${x}, ${y})`);

    // Realistic fluctuating vehicle speed
    const speed = 38 + Math.floor(Math.abs(Math.sin(mapPos * 20)) * 8);
    if ($('#mapTelemetrySpeed')) $('#mapTelemetrySpeed').textContent = `${speed} km/h`;

    // Dynamic decreasing ETA countdown
    const totalMin = currentJourneyTotalMin || 14;
    const remainingMin = Math.max(1, Math.round(totalMin * (1 - mapPos)));
    if ($('#mapArrivalEta')) $('#mapArrivalEta').textContent = `${remainingMin} mins`;
  }, 100);
}

function triggerGpsAutoDetect() {
  const btn = $('#btnGps');
  if (!btn) return;
  btn.textContent = '🔄 Locating GPS...';
  setTimeout(() => {
    btn.textContent = '📍 GPS LOCKED: Railway Platform 1';
    btn.style.background = 'rgba(16,185,129,0.15)';
    btn.style.color = '#10b981';
    $('#pSelectOrigin').value = 'stream2';
    updatePassengerView();
  }, 500);
}

function selectPassengerRoute(mode, name) {
  alert(`✅ Route Confirmed: ${name}\n\nLive GPS turn-by-turn navigation started. Enjoy your commute!`);
}

async function updateSim(streamNum) {
  const s = streamNum || 1;
  const occ = parseInt($(`#simS${s}Occ`).value);
  const eta = parseInt($(`#simS${s}Eta`).value);
  const boarding = parseInt($(`#simS${s}Boarding`).value);
  const alighting = parseInt($(`#simS${s}Alighting`).value);

  $(`#valS${s}Occ`).textContent = occ + '%';
  $(`#valS${s}Eta`).textContent = eta + ' mins';
  $(`#valS${s}Boarding`).textContent = '+' + boarding;
  $(`#valS${s}Alighting`).textContent = '-' + alighting;

  try {
    await fetch('/api/simulation/update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        stream: s,
        vehicle_occupancy: occ,
        vehicle_eta: eta,
        boarding_rate: boarding,
        alighting_rate: alighting
      })
    });
    const stateRes = await fetch('/api/state');
    apply(await stateRes.json());
  } catch(e) {}
}

function setScenario(s1Occ, s1Eta, s1B, s1A, s2Occ, s2Eta, s2B, s2A, name) {
  $('#simS1Occ').value = s1Occ;
  $('#simS1Eta').value = s1Eta;
  $('#simS1Boarding').value = s1B;
  $('#simS1Alighting').value = s1A;
  updateSim(1);

  $('#simS2Occ').value = s2Occ;
  $('#simS2Eta').value = s2Eta;
  $('#simS2Boarding').value = s2B;
  $('#simS2Alighting').value = s2A;
  updateSim(2);
}

async function loadSources() {
  try {
    const res = await fetch('/api/sources');
    const data = await res.json();
    let html = '';
    if (data.virtual_cameras && data.virtual_cameras.length > 0) {
      html += `<optgroup label="Virtual CCTV Feeds">` +
        data.virtual_cameras.map(c => `<option value="${c.value}">${c.label}</option>`).join('') +
        `</optgroup>`;
    }
    if (data.videos && data.videos.length > 0) {
      html += `<optgroup label="Video Files">` +
        data.videos.map(v => `<option value="${v.value}">${v.label}</option>`).join('') +
        `</optgroup>`;
    }
    $('#cam1').innerHTML = html || '<option value="">No sources found</option>';
    $('#cam2').innerHTML = html || '<option value="">No sources found</option>';
    if (state.stream1 && state.stream1.source) $('#cam1').value = state.stream1.source;
    if (state.stream2 && state.stream2.source) $('#cam2').value = state.stream2.source;
  } catch (err) {}
}

let drawingStream = null;
let currentPoints = [];
let currentZoneName = "";

function startDrawingZone(s) {
  drawingStream = s;
  const defName = s === 1 ? "Bus Waiting Area" : "Platform 1 Area";
  currentZoneName = prompt(`Enter a custom name for this Zone (e.g. "${defName}"):`, defName) || defName;
  currentPoints = [];
  
  const canvas = $(`#zoneCanvas${s}`);
  const img = $(`#feed${s}`);
  if (!canvas || !img) return;

  canvas.width = img.clientWidth || 640;
  canvas.height = img.clientHeight || 360;
  canvas.style.display = 'block';

  const btnGroup = $(`#s${s}ZoneBtnGroup`);
  if (btnGroup) {
    btnGroup.innerHTML = `
      <button onclick="saveZone(${s})" style="font-size: 9.5px; font-weight: 800; padding: 3px 8px; background: #10B981; color: #fff; border: none; border-radius: 4px; cursor: pointer;">✅ Apply "${currentZoneName}"</button>
      <button onclick="cancelDrawingZone(${s})" style="font-size: 9.5px; font-weight: 700; padding: 3px 8px; background: #F1F5F9; color: #64748B; border: 1px solid #CBD5E1; border-radius: 4px; cursor: pointer;">✖ Cancel</button>
    `;
  }

  if ($(`#s${s}ZoneStateText`)) {
    $(`#s${s}ZoneStateText`).textContent = `👆 Click points on the video above to draw "${currentZoneName}".`;
    $(`#s${s}ZoneStateText`).style.color = '#6A7EFC';
  }

  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const normX = (e.clientX - rect.left) / rect.width;
    const normY = (e.clientY - rect.top) / rect.height;

    currentPoints.push({x: normX, y: normY});
    redrawCanvas(s);
  };
}

function redrawCanvas(s) {
  const canvas = $(`#zoneCanvas${s}`);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  if (currentPoints.length === 0) return;

  ctx.beginPath();
  currentPoints.forEach((pt, idx) => {
    const px = pt.x * w;
    const py = pt.y * h;
    if (idx === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });

  if (currentPoints.length >= 3) {
    ctx.closePath();
    ctx.fillStyle = 'rgba(0, 242, 255, 0.25)';
    ctx.fill();
  }

  ctx.strokeStyle = '#00F2FE';
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Draw Vertex Handles
  currentPoints.forEach((pt) => {
    const px = pt.x * w;
    const py = pt.y * h;
    ctx.beginPath();
    ctx.arc(px, py, 4.5, 0, 2 * Math.PI);
    ctx.fillStyle = '#00F2FE';
    ctx.fill();
    ctx.strokeStyle = document.documentElement.classList.contains('dark-mode') ? '#1e293b' : '#FFFFFF';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });
}

function cancelDrawingZone(s) {
  drawingStream = null;
  currentPoints = [];
  const canvas = $(`#zoneCanvas${s}`);
  if (canvas) canvas.style.display = 'none';

  restoreZoneBtnGroup(s);
}

function restoreZoneBtnGroup(s) {
  const btnGroup = $(`#s${s}ZoneBtnGroup`);
  if (!btnGroup) return;
  
  const st = s === 1 ? state.stream1 : state.stream2;
  const hasZone = st && st.zones && st.zones.length > 0;

  btnGroup.innerHTML = `
    <button onclick="startDrawingZone(${s})" style="font-size: 9.5px; font-weight: 800; padding: 3px 8px; background: #6A7EFC; color: #fff; border: none; border-radius: 4px; cursor: pointer;">✏️ Draw Zone</button>
    <button onclick="clearZone(${s})" id="btnClearZone${s}" style="${hasZone ? '' : 'display:none;'} font-size: 9.5px; font-weight: 700; padding: 3px 8px; background: rgba(255,86,86,0.12); color: #FF5656; border: 1px solid rgba(255,86,86,0.3); border-radius: 4px; cursor: pointer;">🗑️ Clear Zone</button>
  `;
}

async function saveZone(s) {
  if (currentPoints.length < 3) {
    alert("⚠️ Click at least 3 points on the video feed to define a valid polygon zone shape!");
    return;
  }
  const polyArray = currentPoints.map(p => [p.x, p.y]);
  const canvas = $(`#zoneCanvas${s}`);
  if (canvas) canvas.style.display = 'none';

  // Get current zones for this stream to append
  const st = s === 1 ? state.stream1 : state.stream2;
  const currentZones = (st && st.zones) ? [...st.zones] : [];
  currentZones.push({
    name: currentZoneName || `Zone ${currentZones.length + 1}`,
    polygon: polyArray
  });

  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        stream: s,
        zones: currentZones
      })
    });
    restoreZoneBtnGroup(s);
    const stateRes = await fetch('/api/state');
    apply(await stateRes.json());
  } catch(e) {}
}

async function clearZone(s) {
  const canvas = $(`#zoneCanvas${s}`);
  if (canvas) canvas.style.display = 'none';

  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        stream: s,
        zones: []
      })
    });
    restoreZoneBtnGroup(s);
    const stateRes = await fetch('/api/state');
    apply(await stateRes.json());
  } catch(e) {}
}

(async () => {
  try {
    if (window.innerWidth <= 768) {
      switchPortal('pass');
    }
    const s = await (await fetch('/api/state')).json();
    apply(s);
    await loadSources();
    setInterval(async () => {
      try {
        const stateRes = await fetch('/api/state');
        apply(await stateRes.json());
      } catch (e) {}
    }, 500);
  } catch(err) {}
})();

function toggleTheme() {
  const root = document.documentElement;
  root.classList.toggle('dark-mode');
  const btn = document.getElementById('themeToggleBtn');
  if (root.classList.contains('dark-mode')) {
    btn.innerHTML = '☀️ Light Mode';
  } else {
    btn.innerHTML = '🌙 Dark Mode';
  }
}

