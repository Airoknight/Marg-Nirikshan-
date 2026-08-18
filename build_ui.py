import re

html_template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MARG NIRIKSHAN &mdash; Municipal Transit Crowd Safety Authority</title>
<link rel="icon" type="image/png" href="/public/Black%20Gradient%20Bicycle%20Presentation.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=JetBrains+Mono:wght@400;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-dark: #090B10;
    --panel-bg: #11151E;
    --border-color: #2A3143;
    --text-main: #E2E8F0;
    --text-muted: #64748B;
    --accent-blue: #38BDF8;
    --accent-orange: #F97316;
    --danger: #EF4444;
    --font-mono: 'Share Tech Mono', 'JetBrains Mono', monospace;
    --font-sans: 'Inter', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  
  body {
    background: var(--bg-dark);
    color: var(--text-main);
    font-family: var(--font-mono);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-size: 11px;
    line-height: 1.4;
  }

  /* TOP NAV */
  .top-nav {
    display: flex;
    align-items: center;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-dark);
  }

  .logo-box {
    width: 24px;
    height: 24px;
    border: 1px solid var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    margin-right: 12px;
  }

  .brand-title {
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 1px;
    margin-right: auto;
    font-family: var(--font-sans);
    text-transform: uppercase;
  }
  .brand-title span {
    display: block;
    font-size: 9px;
    color: var(--text-muted);
    font-weight: 400;
    font-family: var(--font-mono);
  }

  .nav-links {
    display: flex;
    gap: 30px;
    margin-right: 40px;
  }
  .nav-links a {
    color: var(--text-muted);
    text-decoration: none;
    text-transform: uppercase;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-bottom: 4px;
    border-bottom: 2px solid transparent;
  }
  .nav-links a.active {
    color: var(--accent-blue);
    border-bottom-color: var(--accent-blue);
  }
  .nav-links a:hover {
    color: var(--text-main);
  }

  .time-display {
    color: var(--text-main);
    font-weight: 700;
    margin-right: 20px;
  }

  .light-mode-btn {
    color: var(--text-muted);
    cursor: pointer;
  }

  /* METRICS ROW */
  .metrics-row {
    display: flex;
    border-bottom: 1px solid var(--border-color);
  }
  .metric-col {
    flex: 1;
    padding: 16px 20px;
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .metric-col:last-child {
    border-right: none;
  }

  .metric-label {
    color: var(--text-muted);
    font-size: 9px;
    text-transform: uppercase;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
  }
  .metric-value {
    font-size: 24px;
    font-weight: 700;
    font-family: var(--font-sans);
    display: flex;
    align-items: baseline;
    gap: 6px;
  }
  .metric-unit {
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-weight: normal;
  }
  .metric-sub {
    font-size: 9px;
    color: var(--text-muted);
    margin-top: 6px;
  }

  /* HIGHLIGHT METRIC */
  .metric-highlight .metric-value {
    color: var(--text-main);
  }
  .progress-bar {
    margin-top: 8px;
    height: 4px;
    background: #2A3143;
    width: 100%;
  }
  .progress-fill {
    height: 100%;
    background: var(--danger);
    width: 80%;
  }

  /* ROUTING DIRECTIVE */
  .routing-directive {
    padding: 8px 20px;
    background: var(--panel-bg);
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    font-size: 10px;
    color: var(--text-main);
  }
  .routing-label {
    color: var(--text-muted);
    margin-right: 16px;
  }
  .live-badge {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-muted);
  }
  .pulse {
    width: 6px; height: 6px;
    background: var(--danger);
    border-radius: 50%;
    box-shadow: 0 0 6px var(--danger);
  }

  /* MAIN WORKSPACE */
  .main-workspace {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .left-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border-color);
  }

  /* STREAMS GRID */
  .streams-grid {
    display: flex;
    flex: 1;
    border-bottom: 1px solid var(--border-color);
  }
  .stream-box {
    flex: 1;
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    padding: 12px;
  }
  .stream-box:last-child {
    border-right: none;
  }
  .stream-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .stream-title {
    color: var(--text-main);
    font-weight: 700;
  }
  .stream-title span { color: var(--text-muted); margin-right: 8px; }
  .stream-badges {
    color: var(--text-muted);
    font-size: 9px;
  }

  .video-container {
    flex: 1;
    border: 1px dashed var(--border-color);
    position: relative;
    background-image: 
      linear-gradient(45deg, var(--bg-dark) 25%, transparent 25%, transparent 75%, var(--bg-dark) 75%, var(--bg-dark)),
      linear-gradient(45deg, var(--bg-dark) 25%, transparent 25%, transparent 75%, var(--bg-dark) 75%, var(--bg-dark));
    background-size: 4px 4px;
    background-position: 0 0, 2px 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .video-placeholder {
    color: var(--text-muted);
    text-align: center;
    font-size: 10px;
    z-index: 1;
  }
  .video-container img {
    position: absolute;
    top:0; left:0; width:100%; height:100%;
    object-fit: contain;
    z-index: 2;
  }
  .video-container canvas {
    position: absolute;
    top:0; left:0; width:100%; height:100%;
    z-index: 3;
    cursor: crosshair;
  }

  .stream-footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-top: 12px;
  }
  .stream-count {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-main);
  }
  .stream-count span {
    font-size: 9px;
    color: var(--text-muted);
    font-weight: normal;
  }
  .stream-status {
    text-align: right;
    color: var(--accent-orange);
    font-size: 10px;
  }
  .stream-controls {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    color: var(--text-muted);
    font-size: 9px;
  }

  /* TRENDS SECTION */
  .trends-section {
    height: 180px;
    padding: 12px 20px;
    display: flex;
    flex-direction: column;
  }
  .trends-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
  }
  .trends-title { color: var(--text-muted); }
  .trends-legend {
    display: flex;
    gap: 12px;
  }
  .legend-item { display: flex; align-items: center; gap: 6px; color: var(--text-main); font-size: 10px;}
  .legend-color { width: 8px; height: 2px; }

  .trend-bars {
    flex: 1;
    display: flex;
    align-items: flex-end;
    gap: 40px;
    padding-bottom: 10px;
    justify-content: center;
  }
  .bar-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    justify-content: flex-end;
    width: 20px;
  }
  .bar-pair {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 100%;
    width: 100%;
  }
  .bar-1 { background: var(--accent-blue); width: 8px; transition: height 0.3s;}
  .bar-2 { background: var(--accent-orange); width: 8px; transition: height 0.3s;}
  .bar-label {
    margin-top: 6px;
    font-size: 9px;
    color: var(--text-muted);
  }

  /* RIGHT SIDEBAR */
  .right-sidebar {
    width: 320px;
    background: var(--bg-dark);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .config-block {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
  }
  .config-title {
    color: var(--text-muted);
    font-size: 9px;
    margin-bottom: 12px;
    text-transform: uppercase;
  }

  label {
    display: block;
    color: var(--text-muted);
    font-size: 9px;
    margin-bottom: 4px;
    margin-top: 12px;
    text-transform: uppercase;
  }

  input[type="text"], input[type="number"], select {
    width: 100%;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-main);
    padding: 6px 8px;
    font-family: var(--font-mono);
    font-size: 10px;
    outline: none;
  }
  select option { background: var(--bg-dark); }

  .btn-group {
    display: flex;
    border: 1px solid var(--border-color);
  }
  .btn-group button {
    flex: 1;
    background: transparent;
    color: var(--text-muted);
    border: none;
    border-right: 1px solid var(--border-color);
    padding: 6px 0;
    font-family: var(--font-mono);
    font-size: 10px;
    cursor: pointer;
  }
  .btn-group button:last-child { border-right: none; }
  .btn-group button.active {
    background: var(--text-main);
    color: var(--bg-dark);
    font-weight: bold;
  }

  /* AUTOMATED DECISION SUPPORT */
  .decision-block {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
  }
  .decision-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .action-badge {
    background: var(--danger);
    color: #fff;
    padding: 2px 6px;
    font-size: 9px;
    font-weight: bold;
  }
  .decision-text {
    font-size: 10px;
    line-height: 1.5;
    margin-bottom: 16px;
  }
  .decision-actions {
    display: flex;
    gap: 8px;
  }
  .btn-primary {
    flex: 1;
    background: var(--text-main);
    color: var(--bg-dark);
    border: none;
    padding: 8px 0;
    font-weight: bold;
    font-family: var(--font-mono);
    cursor: pointer;
  }
  .btn-secondary {
    flex: 1;
    background: transparent;
    color: var(--text-main);
    border: 1px solid var(--border-color);
    padding: 8px 0;
    font-family: var(--font-mono);
    cursor: pointer;
  }

  /* EVENT LOG */
  .event-log {
    flex: 1;
    padding: 16px 20px;
  }
  .log-item {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    font-size: 9px;
  }
  .log-time {
    color: var(--text-muted);
  }
  .log-msg {
    color: var(--text-main);
  }
  .log-msg.alert { color: var(--danger); }
</style>
</head>
<body>

<div class="top-nav">
  <div class="logo-box">M</div>
  <div class="brand-title">MARG NIRIKSHAN <span>MUNICIPAL TRANSIT CROWD SAFETY AUTHORITY</span></div>
  <div class="nav-links">
    <a href="#" class="active" onclick="switchView('dash')">GOVERNMENT DASHBOARD</a>
    <a href="#" onclick="alert('Passenger App Opening...')">PASSENGER APP</a>
    <a href="#" onclick="switchView('settings')">SIMULATION CONTROL</a>
  </div>
  <div class="time-display" id="clockTop">23:38:49 IST</div>
  <div class="light-mode-btn">LIGHT MODE</div>
</div>

<div class="metrics-row">
  <div class="metric-col">
     <div class="metric-label">PLATFORM OVERFLOW FORECAST</div>
     <div class="metric-value"><span id="cmdOverflowCountdown">0.0</span> <span class="metric-unit">MIN TO CRITICAL</span></div>
     <div class="metric-sub">T = (Capacity - N_live) / (r_in - r_out)</div>
  </div>
  <div class="metric-col">
     <div class="metric-label">STRANDED PASSENGER INDEX</div>
     <div class="metric-value"><span id="cmdStrandedIndex">380</span> <span class="metric-unit">COMMUTERS</span></div>
     <div class="metric-sub">N = max(0, N_live - V_seats) - <span id="cmdReliefUnits">7 relief vehicles required</span></div>
  </div>
  <div class="metric-col">
     <div class="metric-label">CITY CCTV NETWORK</div>
     <div class="metric-value">04 <span class="metric-unit">EDGE NODES</span></div>
     <div class="metric-sub">100% operational - 2 ingesting</div>
  </div>
  <div class="metric-col metric-highlight">
     <div class="metric-label">NETWORK DENSITY STATE</div>
     <div class="metric-value" id="networkState">HIGH</div>
     <div class="progress-bar"><div class="progress-fill"></div></div>
  </div>
</div>

<div class="routing-directive">
  <span class="routing-label">ROUTING DIRECTIVE</span>
  <span id="alertMsg">Least crowded: Bus Terminal — Gate A at 55% effective congestion.</span>
  <div class="live-badge"><div class="pulse"></div> LIVE</div>
</div>

<div class="main-workspace" id="viewDash">
  <div class="left-area">
    <div class="streams-grid">
      
      <!-- STREAM 1 -->
      <div class="stream-box">
        <div class="stream-header">
          <div class="stream-title"><span>STREAM 01</span> <span id="s1Loc" style="color:#E2E8F0;">Bus Terminal — Gate A</span></div>
          <div class="stream-badges"><span id="s1ModelBadge">P2PNET</span> - CAM 01</div>
        </div>
        <div class="video-container">
          <div class="video-placeholder">CCTV FEED PLACEHOLDER<br/>drop cam 01 frame here</div>
          <img id="feed1" src="/stream1.mjpg" onerror="this.style.display='none'" onload="this.style.display='block'">
          <canvas id="zoneCanvas1"></canvas>
        </div>
        <div class="stream-footer">
          <div class="stream-count"><span id="s1OccVal">78</span> <span>/ <span id="s1CapVal">120</span> HEADS</span></div>
          <div class="stream-status" id="s1StatusExt">MODERATE - 55% EFF.<br/><span style="color:var(--text-muted);">live 65% + inbound transit 30%</span></div>
        </div>
        <div class="stream-controls">
          <span id="s1ZoneStateText">ZONE FILTER: pointPolygonTest - GATE 1</span>
          <a href="#" style="color:var(--text-muted); text-decoration:none;" onclick="startDrawingZone(1)">EDIT POLYGON</a>
          <button onclick="clearZone(1)" id="btnClearZone1" style="display:none; background:transparent; border:none; color:var(--danger); cursor:pointer;">CLEAR</button>
        </div>
      </div>

      <!-- STREAM 2 -->
      <div class="stream-box">
        <div class="stream-header">
          <div class="stream-title"><span>STREAM 02</span> <span id="s2Loc" style="color:#E2E8F0;">Railway Station — Platform 1</span></div>
          <div class="stream-badges"><span id="s2ModelBadge">P2PNET</span> - CAM 02</div>
        </div>
        <div class="video-container">
          <div class="video-placeholder">CCTV FEED PLACEHOLDER<br/>drop cam 02 frame here</div>
          <img id="feed2" src="/stream2.mjpg" onerror="this.style.display='none'" onload="this.style.display='block'">
          <canvas id="zoneCanvas2"></canvas>
        </div>
        <div class="stream-footer">
          <div class="stream-count"><span id="s2OccVal">800</span> <span>/ <span id="s2CapVal">800</span> HEADS</span></div>
          <div class="stream-status" id="s2StatusExt" style="color:var(--danger);">HIGH - 96% EFF.<br/><span style="color:var(--text-muted);">live 100% + inbound transit 85%</span></div>
        </div>
        <div class="stream-controls">
          <span id="s2ZoneStateText">ZONE FILTER: pointPolygonTest - PLATFORM EDGE</span>
          <a href="#" style="color:var(--text-muted); text-decoration:none;" onclick="startDrawingZone(2)">EDIT POLYGON</a>
          <button onclick="clearZone(2)" id="btnClearZone2" style="display:none; background:transparent; border:none; color:var(--danger); cursor:pointer;">CLEAR</button>
        </div>
      </div>

    </div>

    <!-- TRENDS SECTION -->
    <div class="trends-section">
      <div class="trends-header">
        <div class="trends-title">BUILDUP TREND &nbsp;&nbsp;&nbsp; Occupancy, last 5 minutes</div>
        <div class="trends-legend">
          <div class="legend-item"><div class="legend-color" style="background:var(--accent-blue);"></div> STREAM 01</div>
          <div class="legend-item"><div class="legend-color" style="background:var(--accent-orange);"></div> STREAM 02</div>
        </div>
      </div>
      <div class="trend-bars" id="trendBars">
        <!-- Rendered by JS -->
      </div>
    </div>
  </div>

  <div class="right-sidebar">
    <!-- CONFIG 1 -->
    <div class="config-block">
      <div class="config-title">STREAM 01 CONFIGURATION</div>
      <label>LOCATION NAME</label>
      <input type="text" id="locInput1" value="Bus Terminal - Gate A" onchange="postConfig(1, {location: this.value})">
      
      <label>INPUT FEED</label>
      <select id="cam1" onchange="postConfig(1, {source: this.value})"></select>
      
      <label>DETECTOR MODEL</label>
      <div class="btn-group">
        <button class="active" data-s1det="p2pnet" onclick="postConfig(1, {detector: 'p2pnet'})">P2PNET</button>
        <button data-s1det="yolo" onclick="postConfig(1, {detector: 'yolo'})">YOLO</button>
        <button data-s1det="kde" onclick="postConfig(1, {detector: 'kde'})">KDE</button>
      </div>

      <label>MAX CAPACITY</label>
      <input type="number" id="cap1" value="120" onchange="postConfig(1, {capacity: parseInt(this.value)})">
    </div>

    <!-- CONFIG 2 -->
    <div class="config-block">
      <div class="config-title">STREAM 02 CONFIGURATION</div>
      <label>LOCATION NAME</label>
      <input type="text" id="locInput2" value="Railway Station - Platform 1" onchange="postConfig(2, {location: this.value})">
      
      <label>INPUT FEED</label>
      <select id="cam2" onchange="postConfig(2, {source: this.value})"></select>
      
      <label>DETECTOR MODEL</label>
      <div class="btn-group">
        <button class="active" data-s2det="p2pnet" onclick="postConfig(2, {detector: 'p2pnet'})">P2PNET</button>
        <button data-s2det="yolo" onclick="postConfig(2, {detector: 'yolo'})">YOLO</button>
        <button data-s2det="kde" onclick="postConfig(2, {detector: 'kde'})">KDE</button>
      </div>

      <label>MAX CAPACITY</label>
      <input type="number" id="cap2" value="800" onchange="postConfig(2, {capacity: parseInt(this.value)})">
    </div>

    <div class="decision-block">
      <div class="decision-header">
        <span class="config-title" style="margin:0;">AUTOMATED DECISION SUPPORT</span>
        <span class="action-badge">ACTION</span>
      </div>
      <div class="decision-text">Critical density on Platform 1. Divert inbound commuters to Bus Terminal Gate A and hold platform intake until occupancy falls below 70%.</div>
      <div class="decision-actions">
        <button class="btn-primary" onclick="alert('Relief Dispatched')">DISPATCH RELIEF</button>
        <button class="btn-secondary" onclick="alert('Intake Held')">HOLD INTAKE</button>
      </div>
    </div>

    <div class="event-log" id="eventLog">
      <div class="config-title">EVENT LOG</div>
      <!-- Rendered by JS -->
      <div class="log-item"><span class="log-time">23:38</span><span class="log-msg">P2PNet headcount sync - 78 / 800</span></div>
      <div class="log-item"><span class="log-time">23:37</span><span class="log-msg">Overflow forecast recomputed - 0.0 min</span></div>
      <div class="log-item"><span class="log-time">23:35</span><span class="log-msg">ROI polygon updated on CAM 02 (platform edge)</span></div>
      <div class="log-item"><span class="log-time">23:32</span><span class="log-msg">Routing directive issued to passenger app</span></div>
      <div class="log-item"><span class="log-time">23:27</span><span class="log-msg alert">Stranded index breached 50 - relief staged</span></div>
      <div class="log-item"><span class="log-time">23:20</span><span class="log-msg">Edge node CAM 04 reconnected</span></div>
    </div>

  </div>
</div>

<!-- Hidden containers for compatibility with existing JS if they get called -->
<div id="viewMonitor" class="view-container" style="display:none;"></div>
<div id="viewReports" class="view-container" style="display:none;"></div>
<div id="viewSettings" class="view-container" style="display:none;">
  <div style="padding:20px;">
    <h2>Simulation Settings</h2>
    <div id="simBtnGroup"></div>
  </div>
</div>

<script>
"""

with open('static/old_script.js', 'r') as f:
    js_content = f.read()

# We need to monkey patch the javascript slightly so it writes to the correct new IDs for Stream 1/2.
js_content = js_content.replace("$('#s1Occ').innerHTML = `${count1} / ${s1.capacity || 1} (${eff1}% Eff.)`;", 
                                "$('#s1OccVal').textContent = count1; $('#s1CapVal').textContent = s1.capacity || 1; $('#s1StatusExt').innerHTML = `${s1.density_status || 'HIGH'} - ${eff1}% EFF.<br/><span style='color:var(--text-muted);'>live ${s1.occupancy_pct}%</span>`;")
js_content = js_content.replace("$('#s2Occ').innerHTML = `${count2} / ${s2.capacity || 1} (${eff2}% Eff.)`;", 
                                "$('#s2OccVal').textContent = count2; $('#s2CapVal').textContent = s2.capacity || 1; $('#s2StatusExt').innerHTML = `${s2.density_status || 'HIGH'} - ${eff2}% EFF.<br/><span style='color:var(--text-muted);'>live ${s2.occupancy_pct}%</span>`;")

# Trend chart rendering
trend_js = """
function renderTrendBars(history) {
  const container = $('#trendBars');
  if (!history || !history.length) return;
  const slice = history.slice(-5); // mockup shows last 5 minutes (5 bars)
  const labels = ['-5 MIN', '-4 MIN', '-3 MIN', '-2 MIN', 'LIVE'];
  container.innerHTML = slice.map((h, idx) => `
    <div class="bar-group" title="Stream 1: ${h.stream1_occ}%, Stream 2: ${h.stream2_occ}%">
      <div class="bar-pair">
        <div class="bar-1" style="height: ${Math.max(5, h.stream1_occ)}%;"></div>
        <div class="bar-2" style="height: ${Math.max(5, h.stream2_occ)}%;"></div>
      </div>
      <div class="bar-label">${labels[idx] || ''}</div>
    </div>
  `).join('');
}
"""
js_content = re.sub(r'function renderTrendBars\(history\) \{.*?\n\}', trend_js, js_content, flags=re.DOTALL)

# Overflow mapping
js_content = js_content.replace("$('#cmdOverflowCountdown').textContent = `OVERFLOW IN ${minOverflow} MINS`;", "$('#cmdOverflowCountdown').textContent = minOverflow.toFixed(1);")
js_content = js_content.replace("$('#cmdOverflowCountdown').textContent = `STABLE (No Overflow Forecasted)`;", "$('#cmdOverflowCountdown').textContent = '--';")

# Stranded mapping
js_content = js_content.replace("$('#cmdStrandedIndex').textContent = `${totalStranded} Commuters Stranded`;", "$('#cmdStrandedIndex').textContent = totalStranded;")

# Clock
js_content += """
setInterval(() => {
  const now = new Date();
  if ($('#clockTop')) $('#clockTop').textContent = now.toLocaleTimeString('en-GB') + ' IST';
}, 1000);
"""

with open('static/index.html', 'w') as f:
    f.write(html_template + js_content + "\\n</script>\\n</body>\\n</html>")

print("Generated new index.html")
