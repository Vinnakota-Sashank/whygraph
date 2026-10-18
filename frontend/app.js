/**
 * WhyGraph — Frontend Application Logic
 * Interactive PR Guardrail, Dynamic Expertise, Living Graph Canvas, AI Guardrail, and Executive Audit
 */

const API_BASE = '/api';

// ── State ───────────────────────────────────────────────────────────────────
let currentService = 'checkout-service';
let currentViolationResult = null;
let graphData = { nodes: [], edges: [] };
let canvasInitialized = false;
let canvasAnimId = null;

// ── DOM Elements ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPresets();
  initViolationForm();
  initChatForm();
  initExpertiseSelector();
  initInventoryTabs();
  initReingestButton();
  initCanvasVisualizer();
  initGuardrailSimulator();
  initLivingIngestModal();

  // Initial data fetches
  fetchGraphStats();
  loadExperts(currentService);
  loadInventoryData();
});

// ── Tab Navigation ──────────────────────────────────────────────────────────
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const targetSection = document.getElementById(targetId);
      if (targetSection) {
        targetSection.classList.add('active');
      }

      // Handle specific tab activations
      if (targetId === 'section-canvas') {
        resizeCanvas();
        if (!canvasInitialized) {
          loadGraphVisualization();
        }
      } else if (targetId === 'section-experts') {
        loadExperts(document.getElementById('select-expert-service').value);
      } else if (targetId === 'section-explorer') {
        loadInventoryData();
      }
    });
  });
}

function initInventoryTabs() {
  const subtabBtns = document.querySelectorAll('.subtab-btn');
  const subtabContents = document.querySelectorAll('.subtab-content');

  subtabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      subtabBtns.forEach(b => b.classList.remove('active'));
      subtabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-subtab');
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add('active');
      }

      if (targetId === 'subtab-compliance') {
        loadComplianceAudit();
      }
    });
  });
}

// ── Header Stats & Re-ingest ────────────────────────────────────────────────
async function fetchGraphStats() {
  try {
    const res = await fetch(`${API_BASE}/graph/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    const data = await res.json();

    document.getElementById('stat-nodes-count').textContent = data.total_nodes || '0';
    document.getElementById('stat-edges-count').textContent = data.total_relationships || '0';
  } catch (err) {
    console.warn('Could not load graph stats:', err);
  }
}

function initReingestButton() {
  const btn = document.getElementById('btn-reingest');
  btn.addEventListener('click', async () => {
    btn.classList.add('loading');
    showToast('Rebuilding graph and re-indexing in FalkorDB Cloud...');
    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: 'POST' });
      if (!res.ok) throw new Error('Rebuild failed');
      await res.json();
      showToast('✅ Graph rebuild complete!');
      await fetchGraphStats();
      loadExperts(document.getElementById('select-expert-service').value);
      loadInventoryData();
      loadGraphVisualization();
    } catch (err) {
      showToast(`⚠️ Rebuild error: ${err.message}`);
    } finally {
      btn.classList.remove('loading');
    }
  });
}

// ── Presets for PR Radar ────────────────────────────────────────────────────
function initPresets() {
  const presetMemcached = document.getElementById('preset-memcached');
  const presetSyncPayment = document.getElementById('preset-sync-payment');
  const presetClean = document.getElementById('preset-clean');

  presetMemcached.addEventListener('click', () => {
    document.getElementById('select-service').value = 'checkout-service';
    document.getElementById('input-dependencies').value = 'pymemcache';
    document.getElementById('input-files').value = 'services/checkout/cache_client.py\nservices/checkout/requirements.txt';
    runViolationScan();
  });

  presetSyncPayment.addEventListener('click', () => {
    document.getElementById('select-service').value = 'checkout-service';
    document.getElementById('input-dependencies').value = 'httpx, requests';
    document.getElementById('input-files').value = 'services/checkout/payment_client.py\nservices/checkout/views.py';
    runViolationScan();
  });

  presetClean.addEventListener('click', () => {
    document.getElementById('select-service').value = 'checkout-service';
    document.getElementById('input-dependencies').value = 'redis, psycopg2-binary';
    document.getElementById('input-files').value = 'services/checkout/models.py\nservices/checkout/db.py';
    runViolationScan();
  });
}

// ── Violation Form & Scan Logic ─────────────────────────────────────────────
function initViolationForm() {
  const form = document.getElementById('form-violation');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    runViolationScan();
  });
}

async function runViolationScan() {
  const service = document.getElementById('select-service').value;
  const depsRaw = document.getElementById('input-dependencies').value;
  const filesRaw = document.getElementById('input-files').value;

  const newDeps = depsRaw.split(',').map(s => s.trim()).filter(Boolean);
  const changedFiles = filesRaw.split('\n').map(s => s.trim()).filter(Boolean);

  const statusPill = document.getElementById('violation-status-pill');
  const output = document.getElementById('violation-output');
  const scanBtn = document.getElementById('btn-check-violation');

  statusPill.className = 'status-pill idle';
  statusPill.textContent = 'Scanning FalkorDB...';
  scanBtn.disabled = true;

  output.innerHTML = `
    <div class="empty-state">
      <div class="pulse-indicator" style="width: 20px; height: 20px; margin-bottom: 1rem;"></div>
      <div class="empty-text">Traversing FalkorDB knowledge graph for active constraints, historical post-mortems, and incident patterns...</div>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/check-violation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        changed_services: [service],
        new_dependencies: newDeps,
        changed_files: changedFiles,
      }),
    });

    if (!res.ok) throw new Error('API error on check-violation');
    const result = await res.json();
    currentViolationResult = result;
    renderViolationResult(result, service);
  } catch (err) {
    console.error(err);
    output.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div class="empty-text">Could not complete scan: ${err.message}. Ensure the WhyGraph backend is running.</div>
      </div>
    `;
    statusPill.className = 'status-pill idle';
    statusPill.textContent = 'Scan Failed';
  } finally {
    scanBtn.disabled = false;
  }
}

function renderViolationResult(data, serviceName) {
  const statusPill = document.getElementById('violation-status-pill');
  const output = document.getElementById('violation-output');

  if (data.status === 'VIOLATIONS_FOUND' && data.violations && data.violations.length > 0) {
    statusPill.className = 'status-pill violation';
    statusPill.textContent = `🚨 ${data.violations.length} Violation(s) Found`;

    let html = `
      <div class="violation-banner">
        <div class="violation-banner-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Architectural Constraint Violation Detected!
        </div>
        <div class="violation-banner-desc">
          Proposed modifications to <strong>${escapeHtml(serviceName)}</strong> breach documented team decisions.
          WhyGraph verified <strong>${data.constraints_checked}</strong> active constraints in FalkorDB Cloud.
        </div>
      </div>
    `;

    // Render individual violations
    data.violations.forEach((v, index) => {
      const traversalSteps = (v.traversal_path || '').split(' → ');

      html += `
        <div class="violation-item">
          <div class="violation-item-header">
            <div class="violation-rule-text">${escapeHtml(v.description)}</div>
            <span class="badge-severity">${escapeHtml(v.severity || 'MUST')} &bull; ${escapeHtml(v.type || 'ARCHITECTURAL')}</span>
          </div>

          <div class="violation-meta-grid">
            <div class="meta-field">
              <div class="meta-field-label">Triggered By</div>
              <div class="meta-field-value" style="color: #fb7185;">${escapeHtml(v.trigger_reason || 'Package conflict')}</div>
            </div>
            <div class="meta-field">
              <div class="meta-field-label">Original Decision</div>
              <div class="meta-field-value">${escapeHtml(v.source_type || 'ADR')}: ${escapeHtml(v.source_id || 'ADR-001')} ("${escapeHtml(v.source_title || 'Application Caching')}")</div>
            </div>
            <div class="meta-field">
              <div class="meta-field-label">Decision Author</div>
              <div class="meta-field-value">${escapeHtml(v.author_name || 'Sarah Chen')}</div>
            </div>
            <div class="meta-field">
              <div class="meta-field-label">Service Enforced</div>
              <div class="meta-field-value"><code>${escapeHtml(v.service)}</code></div>
            </div>
          </div>

          <!-- FalkorDB Traversal Lineage -->
          <div class="traversal-box">
            <div class="traversal-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
              FalkorDB Sub-Millisecond Graph Traversal Path
            </div>
            <div class="traversal-path">
              ${traversalSteps.map((step, idx) => `
                <div class="traversal-node ${idx === 0 ? 'pr' : idx === traversalSteps.length - 1 ? 'dest' : ''}">
                  ${escapeHtml(step.trim())}
                </div>
                ${idx < traversalSteps.length - 1 ? '<div class="traversal-arrow">&rarr;</div>' : ''}
              `).join('')}
            </div>
          </div>

          <!-- Outage Proof Evidence -->
          ${v.evidence ? `
            <div class="evidence-box">
              <div class="evidence-header">
                <span class="evidence-tag">💥 HISTORICAL OUTAGE PROOF</span>
                <span class="evidence-incident">${escapeHtml(v.evidence.incident_id)} &bull; ${escapeHtml(v.evidence.incident_severity)}</span>
              </div>
              <div class="evidence-title">${escapeHtml(v.evidence.postmortem_title)}</div>
              <div class="evidence-body">
                This exact modification caused a severe production incident. The constraint was created directly from the post-mortem action items to prevent recurrence.
              </div>
            </div>
          ` : ''}
        </div>
      `;
    });

    // Required Reviewers / Experts
    if (data.recommended_experts && data.recommended_experts.length > 0) {
      html += `
        <div class="experts-recommend-card">
          <div class="card-title-sm">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
            </svg>
            Required Architectural Reviewers (Multi-Signal Scoring)
          </div>
          <div class="expert-pills">
            ${data.recommended_experts.slice(0, 3).map(exp => `
              <div class="expert-pill">
                <div class="expert-avatar-sm">${escapeHtml(exp.name.charAt(0))}</div>
                <div class="expert-info-sm">
                  <div class="expert-name-sm">${escapeHtml(exp.name)}</div>
                  <div class="expert-meta-sm">${escapeHtml(exp.team)} &bull; Score: <strong>${exp.score}/100</strong></div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // Slack Alert Simulator Action Button
    html += `
      <div class="slack-preview-toggle-bar">
        <button id="btn-toggle-slack" class="btn-slack-toggle">
          <span>💬 Preview Enterprise Slack Webhook Alert</span>
        </button>
      </div>
      <div id="slack-preview-container" style="display: none;"></div>
    `;

    output.innerHTML = html;

    // Attach Slack toggle handler
    const slackBtn = document.getElementById('btn-toggle-slack');
    if (slackBtn) {
      slackBtn.addEventListener('click', () => toggleSlackPreview(serviceName, data));
    }

  } else {
    statusPill.className = 'status-pill clean';
    statusPill.textContent = '✅ All Constraints Passed';

    output.innerHTML = `
      <div class="clean-banner">
        <div class="clean-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <div class="clean-title">Pull Request is 100% Architecturally Compliant</div>
        <div class="clean-desc">
          No architectural constraints were violated. Verified against <strong>${data.constraints_checked} active rules</strong> in FalkorDB for <code>${escapeHtml(serviceName)}</code>.
        </div>
      </div>
    `;
  }
}

// ── Slack Alert Simulator ────────────────────────────────────────────────────
async function toggleSlackPreview(serviceName, data) {
  const container = document.getElementById('slack-preview-container');
  if (!container) return;

  if (container.style.display === 'block') {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';
  container.innerHTML = '<div style="padding: 1rem; color: var(--text-muted);">Generating Slack Block Kit webhook payload...</div>';

  try {
    const res = await fetch(`${API_BASE}/slack/simulate-alert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service_name: serviceName,
        violation_data: data
      })
    });

    if (!res.ok) throw new Error('Slack simulation failed');
    const slackData = await res.json();

    const firstV = data.violations[0] || {};
    const evidence = firstV.evidence || {};
    const topExp = data.recommended_experts ? data.recommended_experts[0] : { name: 'Sarah Chen', score: 85 };

    container.innerHTML = `
      <div class="slack-mock-card">
        <div class="slack-mock-header">
          <div class="slack-bot-avatar">WG</div>
          <div>
            <span class="slack-bot-name">WhyGraph Architectural Radar</span>
            <span class="slack-bot-app-tag">APP</span>
            <span style="font-size: 0.75rem; color: #9b9ea2; margin-left: 0.5rem;">${slackData.channel}</span>
          </div>
        </div>

        <div class="slack-mock-title">🚨 Architectural Constraint Violated on PR #142</div>
        <div style="font-size: 0.85rem; line-height: 1.4; margin-bottom: 0.5rem;">
          Pull Request proposes modifications to <strong><code>${escapeHtml(serviceName)}</code></strong> that violate corporate architecture.
        </div>

        <div class="slack-mock-fields">
          <div>
            <div class="slack-mock-field-label">Severity</div>
            <div class="slack-mock-field-val"><code>${escapeHtml(firstV.severity || 'MUST')}</code></div>
          </div>
          <div>
            <div class="slack-mock-field-label">Original Decision</div>
            <div class="slack-mock-field-val">${escapeHtml(firstV.source_type || 'ADR')}: ${escapeHtml(firstV.source_id || 'ADR-001')}</div>
          </div>
          <div style="grid-column: span 2;">
            <div class="slack-mock-field-label">Violated Rule</div>
            <div class="slack-mock-field-val">${escapeHtml(firstV.description || '')}</div>
          </div>
          ${evidence.incident_id ? `
            <div style="grid-column: span 2;">
              <div class="slack-mock-field-label">Historical Outage Proof</div>
              <div class="slack-mock-field-val" style="color: #fb7185;">💥 ${escapeHtml(evidence.incident_id)} (${escapeHtml(evidence.incident_severity)}): ${escapeHtml(evidence.postmortem_title)}</div>
            </div>
          ` : ''}
          <div style="grid-column: span 2;">
            <div class="slack-mock-field-label">Assigned Domain Reviewer</div>
            <div class="slack-mock-field-val">👤 <strong>@${escapeHtml(topExp.name)}</strong> (Signal Score: <strong>${topExp.score}/100</strong>)</div>
          </div>
        </div>

        <div class="slack-mock-actions">
          <button class="slack-btn slack-btn-primary" onclick="showToast('Review request dispatched to @${escapeHtml(topExp.name)}')">Request Review</button>
          <button class="slack-btn" onclick="document.getElementById('tab-canvas').click()">View WhyGraph Lineage</button>
          <button class="slack-btn slack-btn-danger" onclick="showToast('Exception request forwarded to Platform Tech Lead')">Request Exception</button>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose); font-size: 0.8rem;">Could not simulate Slack alert: ${err.message}</div>`;
  }
}

// ── Interactive HTML5 Canvas Graph Visualizer ───────────────────────────────
let canvas, ctx;
let nodes = [];
let edges = [];
let activeFilter = 'all';
let hoveredNode = null;
let draggedNode = null;
let dragOffset = { x: 0, y: 0 };
let transform = { x: 0, y: 0, scale: 1 };
let isPanning = false;
let startPan = { x: 0, y: 0 };
let highlightViolationActive = false;

function initCanvasVisualizer() {
  canvas = document.getElementById('graph-canvas');
  if (!canvas) return;
  ctx = canvas.getContext('2d');

  // Filter chips
  const chips = document.querySelectorAll('.canvas-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeFilter = chip.getAttribute('data-filter');
      simulationAlpha = 0.3;
    });
  });

  // Controls
  const resetBtn = document.getElementById('btn-canvas-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      centerGraph();
    });
  }

  const highlightBtn = document.getElementById('btn-canvas-highlight-violation');
  if (highlightBtn) {
    highlightBtn.addEventListener('click', () => {
      highlightViolationActive = !highlightViolationActive;
      highlightBtn.textContent = highlightViolationActive ? 'Disable Violation Pulse' : 'Highlight Violation Path';
      if (highlightViolationActive) {
        showToast('Tracing PR violation path: checkout-service → C-001 → ADR-001 → INC-089');
      }
    });
  }

  const closeInspector = document.getElementById('btn-close-inspector');
  if (closeInspector) {
    closeInspector.addEventListener('click', () => {
      document.getElementById('canvas-inspector').classList.add('hidden');
    });
  }

  // Mouse interaction
  canvas.addEventListener('mousedown', onCanvasMouseDown);
  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('mouseup', onCanvasMouseUp);
  canvas.addEventListener('wheel', onCanvasWheel);

  window.addEventListener('resize', resizeCanvas);
}

function resizeCanvas() {
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
}

async function loadGraphVisualization() {
  try {
    const res = await fetch(`${API_BASE}/graph/visualization`);
    if (!res.ok) throw new Error('Failed to load graph visualization');
    const data = await res.json();
    graphData = data;

    // Update filter counts
    document.getElementById('chip-count-all').textContent = data.nodes.length;
    document.getElementById('chip-count-svc').textContent = data.nodes.filter(n => n.type === 'Service').length;
    document.getElementById('chip-count-c').textContent = data.nodes.filter(n => n.type === 'Constraint').length;
    document.getElementById('chip-count-adr').textContent = data.nodes.filter(n => n.type === 'ADR').length;
    document.getElementById('chip-count-inc').textContent = data.nodes.filter(n => n.type === 'Incident' || n.type === 'PostMortem').length;
    document.getElementById('chip-count-person').textContent = data.nodes.filter(n => n.type === 'Person').length;

    // Initialize layout positions
    initNodePositions(data.nodes, data.edges);
    canvasInitialized = true;
    centerGraph();
    startAnimationLoop();
  } catch (err) {
    console.error('Visualization error:', err);
  }
}

let simulationAlpha = 1.0;

function initNodePositions(rawNodes, rawEdges) {
  const width = canvas.parentElement.clientWidth || 900;
  const height = canvas.parentElement.clientHeight || 620;
  const centerX = width / 2;
  const centerY = height / 2;

  // Group nodes by type for clustered positioning
  const services = rawNodes.filter(n => n.type === 'Service');
  const constraints = rawNodes.filter(n => n.type === 'Constraint');
  const adrs = rawNodes.filter(n => n.type === 'ADR');
  const incidents = rawNodes.filter(n => n.type === 'Incident' || n.type === 'PostMortem');
  const people = rawNodes.filter(n => n.type === 'Person' || n.type === 'Team');
  const others = rawNodes.filter(n => !['Service', 'Constraint', 'ADR', 'Incident', 'PostMortem', 'Person', 'Team'].includes(n.type));

  const nodeMap = {};

  // 1. Center Ring: Services (Inner core)
  services.forEach((s, idx) => {
    const angle = (idx / (services.length || 1)) * 2 * Math.PI;
    s.x = centerX + 150 * Math.cos(angle);
    s.y = centerY + 150 * Math.sin(angle);
    s.vx = 0; s.vy = 0;
    nodeMap[s.id] = s;
  });

  // 2. Middle Ring: Constraints (Arranged around services)
  constraints.forEach((c, idx) => {
    const angle = (idx / (constraints.length || 1)) * 2 * Math.PI + 0.2;
    c.x = centerX + 230 * Math.cos(angle) + (idx % 2 === 0 ? 25 : -25);
    c.y = centerY + 230 * Math.sin(angle) + (idx % 2 === 0 ? 25 : -25);
    c.vx = 0; c.vy = 0;
    nodeMap[c.id] = c;
  });

  // 3. Outer Ring A: ADRs & PostMortems
  adrs.forEach((a, idx) => {
    const angle = (idx / (adrs.length || 1)) * 2 * Math.PI;
    a.x = centerX + 310 * Math.cos(angle);
    a.y = centerY + 310 * Math.sin(angle);
    a.vx = 0; a.vy = 0;
    nodeMap[a.id] = a;
  });

  // 4. Outer Ring B: Incidents & Outages
  incidents.forEach((inc, idx) => {
    const angle = (idx / (incidents.length || 1)) * 2 * Math.PI + 0.5;
    inc.x = centerX + 370 * Math.cos(angle);
    inc.y = centerY + 370 * Math.sin(angle);
    inc.vx = 0; inc.vy = 0;
    nodeMap[inc.id] = inc;
  });

  // 5. Perimeter Ring: Engineers & Teams
  people.forEach((p, idx) => {
    const angle = (idx / (people.length || 1)) * 2 * Math.PI + 0.8;
    p.x = centerX + 430 * Math.cos(angle);
    p.y = centerY + 430 * Math.sin(angle);
    p.vx = 0; p.vy = 0;
    nodeMap[p.id] = p;
  });

  // 6. Any other nodes
  others.forEach((o, idx) => {
    const angle = (idx / (others.length || 1)) * 2 * Math.PI;
    o.x = centerX + 480 * Math.cos(angle);
    o.y = centerY + 480 * Math.sin(angle);
    o.vx = 0; o.vy = 0;
    nodeMap[o.id] = o;
  });

  nodes = rawNodes.map(n => nodeMap[n.id] || n);

  edges = rawEdges.map(e => ({
    ...e,
    sourceNode: nodes.find(n => n.id === e.source),
    targetNode: nodes.find(n => n.id === e.target)
  })).filter(e => e.sourceNode && e.targetNode);

  simulationAlpha = 1.0;
}

function centerGraph() {
  transform = { x: 0, y: 0, scale: 0.95 };
  simulationAlpha = 0.25;
}

function startAnimationLoop() {
  if (canvasAnimId) cancelAnimationFrame(canvasAnimId);

  function tick() {
    updatePhysics();
    drawGraph();
    canvasAnimId = requestAnimationFrame(tick);
  }
  tick();
}

function updatePhysics() {
  // If simulation has cooled down and no node is being dragged, STOP computing physics
  if (simulationAlpha < 0.004 && !draggedNode) {
    return;
  }

  const width = canvas.parentElement.clientWidth || 900;
  const height = canvas.parentElement.clientHeight || 620;
  const centerX = width / 2;
  const centerY = height / 2;

  const kRepulsion = 800 * simulationAlpha;
  const kSpring = 0.03 * simulationAlpha;
  const idealLength = 95;

  // 1. Node Repulsion & Hard Collision Avoidance
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[j].x - nodes[i].x;
      const dy = nodes[j].y - nodes[i].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;

      // Hard Collision push-apart so nodes never overlap each other
      const minDist = nodes[i].radius + nodes[j].radius + 18;
      if (dist < minDist) {
        const overlap = (minDist - dist) * 0.5;
        const pushX = (dx / dist) * overlap;
        const pushY = (dy / dist) * overlap;
        if (nodes[i] !== draggedNode) {
          nodes[i].x -= pushX;
          nodes[i].y -= pushY;
        }
        if (nodes[j] !== draggedNode) {
          nodes[j].x += pushX;
          nodes[j].y += pushY;
        }
      } else if (dist < 260) {
        const force = kRepulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (nodes[i] !== draggedNode) {
          nodes[i].vx -= fx;
          nodes[i].vy -= fy;
        }
        if (nodes[j] !== draggedNode) {
          nodes[j].vx += fx;
          nodes[j].vy += fy;
        }
      }
    }
  }

  // 2. Edge Springs
  edges.forEach(e => {
    const s = e.sourceNode;
    const t = e.targetNode;
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const force = (dist - idealLength) * kSpring;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    if (s !== draggedNode) {
      s.vx += fx;
      s.vy += fy;
    }
    if (t !== draggedNode) {
      t.vx -= fx;
      t.vy -= fy;
    }
  });

  // 3. Center Gravity pull & Damping
  nodes.forEach(n => {
    if (n === draggedNode) return;
    n.vx += (centerX - n.x) * 0.001 * simulationAlpha;
    n.vy += (centerY - n.y) * 0.001 * simulationAlpha;

    n.vx *= 0.82; // Strong damping
    n.vy *= 0.82;

    n.x += n.vx;
    n.y += n.vy;
  });

  // 4. Exponential Cooling (settles smoothly within ~2 seconds)
  simulationAlpha *= 0.94;
}

function drawGraph() {
  const width = canvas.parentElement.clientWidth;
  const height = canvas.parentElement.clientHeight;

  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.scale, transform.scale);

  const time = Date.now() * 0.004;

  // Draw edges
  edges.forEach(e => {
    const s = e.sourceNode;
    const t = e.targetNode;

    const sVisible = activeFilter === 'all' || s.type === activeFilter || (activeFilter === 'Incident' && (s.type === 'Incident' || s.type === 'PostMortem'));
    const tVisible = activeFilter === 'all' || t.type === activeFilter || (activeFilter === 'Incident' && (t.type === 'Incident' || t.type === 'PostMortem'));
    if (!sVisible && !tVisible) return;

    // Check if violation edge
    const isViolationPath = highlightViolationActive && (
      (s.key.includes('checkout') && t.key.includes('C-')) ||
      (s.key.includes('C-') && t.key.includes('ADR')) ||
      (s.key.includes('ADR') && t.key.includes('INC')) ||
      (s.key.includes('PM-') && t.key.includes('INC'))
    );

    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);

    if (isViolationPath) {
      const pulseAlpha = 0.5 + 0.5 * Math.sin(time * 3);
      ctx.strokeStyle = `rgba(244, 63, 94, ${pulseAlpha})`;
      ctx.lineWidth = 3;
    } else if (hoveredNode && (s === hoveredNode || t === hoveredNode)) {
      ctx.strokeStyle = 'rgba(139, 92, 246, 0.7)';
      ctx.lineWidth = 2;
    } else {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
    }
    ctx.stroke();
  });

  // Draw nodes
  nodes.forEach(n => {
    const isVisible = activeFilter === 'all' || n.type === activeFilter || (activeFilter === 'Incident' && (n.type === 'Incident' || n.type === 'PostMortem'));
    if (!isVisible) return;

    const isHovered = n === hoveredNode;
    const isViolationNode = highlightViolationActive && (
      n.key.includes('checkout') || n.key.includes('C-001') || n.key.includes('ADR-001') || n.key.includes('INC-089')
    );

    // Outer glow ring
    if (isViolationNode) {
      const pulseR = n.radius + 6 + 4 * Math.sin(time * 4);
      ctx.beginPath();
      ctx.arc(n.x, n.y, pulseR, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(244, 63, 94, 0.6)';
      ctx.lineWidth = 3;
      ctx.stroke();
    } else if (isHovered) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius + 6, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(139, 92, 246, 0.6)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Node body
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    ctx.fillStyle = n.color;
    ctx.shadowColor = n.color;
    ctx.shadowBlur = isHovered ? 15 : 6;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Node label
    ctx.fillStyle = '#ffffff';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(n.label.length > 18 ? n.label.substring(0, 16) + '...' : n.label, n.x, n.y + n.radius + 12);
  });

  ctx.restore();
}

function getNodeAt(x, y) {
  const scaledX = (x - transform.x) / transform.scale;
  const scaledY = (y - transform.y) / transform.scale;

  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    const dx = n.x - scaledX;
    const dy = n.y - scaledY;
    if (Math.sqrt(dx * dx + dy * dy) <= n.radius + 4) {
      return n;
    }
  }
  return null;
}

function onCanvasMouseDown(e) {
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  const node = getNodeAt(mouseX, mouseY);
  if (node) {
    draggedNode = node;
    simulationAlpha = 0.25;
    openInspector(node);
  } else {
    isPanning = true;
    startPan = { x: mouseX - transform.x, y: mouseY - transform.y };
  }
}

function onCanvasMouseMove(e) {
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  if (draggedNode) {
    draggedNode.x = (mouseX - transform.x) / transform.scale;
    draggedNode.y = (mouseY - transform.y) / transform.scale;
    draggedNode.vx = 0;
    draggedNode.vy = 0;
  } else if (isPanning) {
    transform.x = mouseX - startPan.x;
    transform.y = mouseY - startPan.y;
  } else {
    hoveredNode = getNodeAt(mouseX, mouseY);
    canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
  }
}

function onCanvasMouseUp() {
  draggedNode = null;
  isPanning = false;
  canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
}

function onCanvasWheel(e) {
  e.preventDefault();
  const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
  transform.scale = Math.max(0.4, Math.min(2.5, transform.scale * zoomFactor));
}

function openInspector(node) {
  const inspector = document.getElementById('canvas-inspector');
  if (!inspector) return;

  inspector.classList.remove('hidden');
  document.getElementById('inspector-badge').textContent = node.type;
  document.getElementById('inspector-title').textContent = node.label;
  document.getElementById('inspector-desc').textContent = node.subtitle || `Entity node stored in FalkorDB graph 'whygraph'.`;

  const metaBox = document.getElementById('inspector-meta');
  let metaHtml = `
    <div class="inspector-meta-row">
      <span class="inspector-meta-label">Node Type:</span>
      <span class="inspector-meta-val">${escapeHtml(node.type)}</span>
    </div>
    <div class="inspector-meta-row">
      <span class="inspector-meta-label">Internal ID:</span>
      <span class="inspector-meta-val">${escapeHtml(node.id)}</span>
    </div>
  `;

  if (node.properties) {
    for (const [k, v] of Object.entries(node.properties)) {
      if (k !== 'id' && k !== 'name' && k !== 'title') {
        metaHtml += `
          <div class="inspector-meta-row">
            <span class="inspector-meta-label">${escapeHtml(k)}:</span>
            <span class="inspector-meta-val">${escapeHtml(v)}</span>
          </div>
        `;
      }
    }
  }

  metaBox.innerHTML = metaHtml;
}

// ── AI Coding Agent Guardrail Simulator ─────────────────────────────────────
function initGuardrailSimulator() {
  const btnCache = document.getElementById('preset-ai-cache');
  const btnPayment = document.getElementById('preset-ai-payment');
  const promptInput = document.getElementById('ai-prompt-input');
  const simulateBtn = document.getElementById('btn-simulate-ai');

  if (btnCache) {
    btnCache.addEventListener('click', () => {
      btnCache.classList.add('active');
      if (btnPayment) btnPayment.classList.remove('active');
      promptInput.value = 'Write a caching utility for checkout-service to store cart items.';
      runAiGuardrailSimulation('checkout-service', promptInput.value);
    });
  }

  if (btnPayment) {
    btnPayment.addEventListener('click', () => {
      btnPayment.classList.add('active');
      if (btnCache) btnCache.classList.remove('active');
      promptInput.value = 'Call payment-service directly via HTTP to process immediate charge during checkout.';
      runAiGuardrailSimulation('checkout-service', promptInput.value);
    });
  }

  if (simulateBtn) {
    simulateBtn.addEventListener('click', () => {
      const targetServiceInput = document.getElementById('ai-target-service');
      const service = (targetServiceInput && targetServiceInput.value.trim()) || 'checkout-service';
      runAiGuardrailSimulation(service, promptInput.value);
    });
  }
}

async function runAiGuardrailSimulation(service, prompt) {
  const simulateBtn = document.getElementById('btn-simulate-ai');
  simulateBtn.disabled = true;
  simulateBtn.textContent = 'Simulating...';

  try {
    const res = await fetch(`${API_BASE}/ai-guardrail/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, target_service: service })
    });

    if (!res.ok) throw new Error('AI simulation error');
    const data = await res.json();

    document.getElementById('unguarded-code-box').innerHTML = `<code>${escapeHtml(data.unguarded.code)}</code>`;
    const violList = document.getElementById('unguarded-violations-list');
    violList.innerHTML = data.unguarded.violations.map(v => `<li>${escapeHtml(v)}</li>`).join('') +
      (data.unguarded.incident_risk ? `<li style="color: #fb7185; font-weight: 600;">${escapeHtml(data.unguarded.incident_risk)}</li>` : '');

    document.getElementById('guarded-code-box').innerHTML = `<code>${escapeHtml(data.guarded.code)}</code>`;
    const rulesList = document.getElementById('guarded-rules-list');
    rulesList.innerHTML = data.guarded.rules_injected.map(r => `<li>${escapeHtml(r)}</li>`).join('') +
      `<li style="color: #6ee7b7; font-weight: 600;">Verified via ${escapeHtml(data.guarded.verified_by)}</li>`;

  } catch (err) {
    showToast(`Simulation error: ${err.message}`);
  } finally {
    simulateBtn.disabled = false;
    simulateBtn.textContent = 'Simulate AI Generation';
  }
}

// ── Living Knowledge Ingestion Modal ────────────────────────────────────────
function initLivingIngestModal() {
  const modal = document.getElementById('modal-ingest');
  const openBtn = document.getElementById('btn-open-ingest-modal');
  const closeBtn = document.getElementById('btn-close-ingest-modal');
  const cancelBtn = document.getElementById('btn-cancel-ingest');
  const form = document.getElementById('form-unstructured-ingest');
  const textArea = document.getElementById('input-unstructured-text');
  const resultContainer = document.getElementById('ingest-result-container');

  const presetKafka = document.getElementById('preset-ingest-kafka');
  const presetQueue = document.getElementById('preset-ingest-queue');

  if (openBtn) openBtn.addEventListener('click', () => modal.classList.add('open'));
  if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.remove('open'));
  if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.remove('open'));

  if (presetKafka) {
    presetKafka.addEventListener('click', () => {
      textArea.value = `INCIDENT POST-MORTEM INC-105: Kafka Consumer Hang in analytics-service.\nIncident Lead: Alex Morgan.\nRoot cause: Consumer was reading unbatched offsets during peak spike.\nAction Item: analytics-service MUST use batch consumer with max.poll.records=500 and autocommit disabled.`;
    });
  }

  if (presetQueue) {
    presetQueue.addEventListener('click', () => {
      textArea.value = `ADR-004: Mandatory Asynchronous Order Processing Queues.\nAuthor: David Kumar.\nDate: 2026-10-17.\nStatus: ACCEPTED.\nTarget Services: order-service, checkout-service.\nDecision: Order submission must publish events to 'orders.v1' RabbitMQ topic. Direct synchronous calls to order-service from frontend gateways are PROHIBITED.`;
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = textArea.value.trim();
      if (!text) return;

      const submitBtn = document.getElementById('btn-submit-ingest');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Extracting via Gemini & FalkorDB...';
      resultContainer.style.display = 'none';

      try {
        const res = await fetch(`${API_BASE}/ingest/unstructured`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text, source_label: 'living_memory_modal' })
        });

        if (!res.ok) throw new Error('Ingestion failed');
        const data = await res.json();

        resultContainer.style.display = 'block';
        resultContainer.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 0.4rem;">✅ Successfully Ingested into FalkorDB Cloud!</div>
          <div><strong>Document:</strong> ${escapeHtml(data.doc_type)} (${escapeHtml(data.doc_id)}) — <em>${escapeHtml(data.title)}</em></div>
          <div><strong>Author:</strong> ${escapeHtml(data.author)} &bull; <strong>Target Services:</strong> ${escapeHtml(data.services.join(', '))}</div>
          <div><strong>Nodes Added:</strong> ${data.nodes_added.length} &bull; <strong>Relationships Linked:</strong> ${data.relationships_added.length}</div>
        `;

        showToast('🎉 Living knowledge ingested and linked into FalkorDB Cloud!');
        await fetchGraphStats();
        loadGraphVisualization();
        loadInventoryData();
      } catch (err) {
        resultContainer.style.display = 'block';
        resultContainer.style.borderColor = 'rgba(244, 63, 94, 0.4)';
        resultContainer.style.background = 'rgba(244, 63, 94, 0.1)';
        resultContainer.style.color = '#fecdd3';
        resultContainer.innerHTML = `⚠️ Ingestion Error: ${err.message}`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Extract & Link into FalkorDB';
      }
    });
  }
}

// ── Executive Compliance & Bus Factor Audit ─────────────────────────────────
async function loadComplianceAudit() {
  const container = document.getElementById('compliance-table-container');
  const badge = document.getElementById('compliance-health-badge');
  const exportBtn = document.getElementById('btn-export-audit');

  container.innerHTML = '<div class="empty-state"><div class="empty-text">Auditing organizational architecture across all services in FalkorDB...</div></div>';

  try {
    const res = await fetch(`${API_BASE}/compliance/report`);
    if (!res.ok) throw new Error('Failed to load compliance report');
    const data = await res.json();

    badge.textContent = `Overall Health Score: ${data.overall_health_score}%`;

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Service</th>
            <th>Active Rules</th>
            <th>Historical Outages</th>
            <th>Bus Factor (Experts)</th>
            <th>Top Signal Score</th>
            <th>Risk Level</th>
            <th>Governance Assessment</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.services.forEach(s => {
      const riskBadge = s.risk_level === 'HIGH'
        ? '<span class="badge-risk-high">HIGH RISK</span>'
        : s.risk_level === 'MEDIUM'
        ? '<span class="badge-risk-medium">MEDIUM</span>'
        : '<span class="badge-risk-low">LOW RISK</span>';

      html += `
        <tr>
          <td><strong><code>${escapeHtml(s.service)}</code></strong></td>
          <td>${s.active_constraints}</td>
          <td>${s.historical_incidents}</td>
          <td>${s.bus_factor} engineer(s)</td>
          <td>${s.top_expert_score}/100</td>
          <td>${riskBadge}</td>
          <td style="font-size: 0.78rem; color: var(--text-secondary);">${escapeHtml(s.risk_reason)}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;

    if (exportBtn) {
      exportBtn.onclick = () => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `whygraph-architectural-audit-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        showToast('📥 Architectural audit exported.');
      };
    }

  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-text">Failed loading audit: ${err.message}</div></div>`;
  }
}

// ── Chat Form & Messaging ───────────────────────────────────────────────────
function initChatForm() {
  const form = document.getElementById('form-chat');
  const input = document.getElementById('input-chat');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    appendChatMessage(query, 'user');
    input.value = '';

    const typingBubble = appendTypingIndicator();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query }),
      });

      typingBubble.remove();

      if (!res.ok) throw new Error('Chat failed');
      const data = await res.json();
      appendChatMessage(data.reply, 'bot');
    } catch (err) {
      typingBubble.remove();
      appendChatMessage(`I encountered an error querying the decision graph: ${err.message}`, 'bot');
    }
  });

  // Suggestion chips
  const suggestionChips = document.querySelectorAll('.suggestion-chip');
  suggestionChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.getAttribute('data-query');
      input.value = query;
      form.dispatchEvent(new Event('submit'));
    });
  });
}

function appendChatMessage(text, sender) {
  const container = document.getElementById('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;

  let avatarSvg = '';
  if (sender === 'bot') {
    avatarSvg = `
      <div class="bubble-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="18" cy="5" r="3"></circle>
          <circle cx="6" cy="12" r="3"></circle>
          <circle cx="18" cy="19" r="3"></circle>
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
        </svg>
      </div>
    `;
  } else {
    avatarSvg = `
      <div class="bubble-avatar user">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      </div>
    `;
  }

  bubble.innerHTML = `
    ${avatarSvg}
    <div class="bubble-content">
      ${formatMarkdown(text)}
    </div>
  `;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function appendTypingIndicator() {
  const container = document.getElementById('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble bot';
  bubble.innerHTML = `
    <div class="bubble-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="18" cy="5" r="3"></circle>
        <circle cx="6" cy="12" r="3"></circle>
        <circle cx="18" cy="19" r="3"></circle>
      </svg>
    </div>
    <div class="bubble-content">
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

// ── Expertise Selector & Loader ─────────────────────────────────────────────
function initExpertiseSelector() {
  const select = document.getElementById('select-expert-service');
  select.addEventListener('change', (e) => {
    loadExperts(e.target.value);
  });
}

async function loadExperts(serviceName) {
  const container = document.getElementById('experts-container');
  container.innerHTML = `
    <div class="empty-state">
      <div class="pulse-indicator" style="width: 20px; height: 20px; margin-bottom: 1rem;"></div>
      <div class="empty-text">Calculating multi-signal domain expertise for ${escapeHtml(serviceName)}...</div>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/experts/${serviceName}`);
    if (!res.ok) throw new Error('Expert query failed');
    const data = await res.json();

    if (!data.experts || data.experts.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">👤</div>
          <div class="empty-text">No active domain experts cataloged for ${escapeHtml(serviceName)}.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = data.experts.map(exp => `
      <div class="card glass-card expert-card">
        <div class="expert-card-header">
          <div class="expert-avatar">${escapeHtml(exp.name.charAt(0))}</div>
          <div class="expert-header-info">
            <div class="expert-name">${escapeHtml(exp.name)}</div>
            <div class="expert-role">${escapeHtml(exp.role)} &bull; <code>${escapeHtml(exp.team)}</code></div>
          </div>
          <div class="score-badge">
            <span class="score-value">${exp.score}</span>
            <span class="score-max">/100</span>
          </div>
        </div>

        <div class="signal-breakdown">
          <div class="signal-row">
            <span class="signal-label">Git Commits (1x)</span>
            <div class="signal-bar-track">
              <div class="signal-bar-fill" style="width: ${Math.min(100, exp.signals.commits * 1.5)}%;"></div>
            </div>
            <span class="signal-val">${exp.signals.commits}</span>
          </div>

          <div class="signal-row">
            <span class="signal-label">PR Reviews (0.5x)</span>
            <div class="signal-bar-track">
              <div class="signal-bar-fill" style="width: ${Math.min(100, exp.signals.reviews * 2)}%;"></div>
            </div>
            <span class="signal-val">${exp.signals.reviews}</span>
          </div>

          <div class="signal-row">
            <span class="signal-label">Outages Resolved (10x)</span>
            <div class="signal-bar-track">
              <div class="signal-bar-fill highlight" style="width: ${Math.min(100, exp.signals.incidents_resolved * 33)}%;"></div>
            </div>
            <span class="signal-val">${exp.signals.incidents_resolved}</span>
          </div>

          <div class="signal-row">
            <span class="signal-label">ADRs & Docs (3x)</span>
            <div class="signal-bar-track">
              <div class="signal-bar-fill" style="width: ${Math.min(100, exp.signals.docs_authored * 25)}%;"></div>
            </div>
            <span class="signal-val">${exp.signals.docs_authored}</span>
          </div>
        </div>

        ${exp.related_incidents && exp.related_incidents.length > 0 ? `
          <div class="expert-incident-badge">
            🚨 Authored post-mortem for ${escapeHtml(exp.related_incidents[0].id)} (${escapeHtml(exp.related_incidents[0].severity)})
          </div>
        ` : ''}
      </div>
    `).join('');

  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <div class="empty-text">Failed loading experts: ${err.message}</div>
      </div>
    `;
  }
}

// ── Inventory Data Loaders ──────────────────────────────────────────────────
async function loadInventoryData() {
  loadConstraintsTable();
  loadIncidentsTable();
  loadServicesTable();
}

async function loadConstraintsTable() {
  const container = document.getElementById('constraints-list');
  try {
    const res = await fetch(`${API_BASE}/constraints`);
    if (!res.ok) throw new Error('Constraints load error');
    const data = await res.json();

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Severity</th>
            <th>Type</th>
            <th>Constraint Description</th>
            <th>Applies To</th>
            <th>Originating Decision</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.constraints.forEach(c => {
      html += `
        <tr>
          <td><code>${escapeHtml(c.id)}</code></td>
          <td><span class="badge-severity ${c.severity.toLowerCase()}">${escapeHtml(c.severity)}</span></td>
          <td><span class="badge-type">${escapeHtml(c.type)}</span></td>
          <td class="table-desc">${escapeHtml(c.description)}</td>
          <td>${(c.applies_to || []).map(s => `<code>${escapeHtml(s)}</code>`).join(' ')}</td>
          <td>${escapeHtml(c.adr_id || c.postmortem_id || c.source)}</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-text">Failed loading constraints: ${err.message}</div></div>`;
  }
}

async function loadIncidentsTable() {
  const container = document.getElementById('incidents-list');
  try {
    const res = await fetch(`${API_BASE}/incidents`);
    if (!res.ok) throw new Error('Incidents load error');
    const data = await res.json();

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Incident ID</th>
            <th>Severity</th>
            <th>Date</th>
            <th>Duration</th>
            <th>Title</th>
            <th>Affected Services</th>
            <th>Recurring Pattern</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.incidents.forEach(inc => {
      html += `
        <tr>
          <td><code>${escapeHtml(inc.id)}</code></td>
          <td><span class="badge-severity danger">${escapeHtml(inc.severity)}</span></td>
          <td>${escapeHtml(inc.date)}</td>
          <td>${inc.duration_minutes} min</td>
          <td class="table-desc"><strong>${escapeHtml(inc.title)}</strong></td>
          <td>${(inc.affected_services || []).map(s => `<code>${escapeHtml(s)}</code>`).join(' ')}</td>
          <td><span class="badge-pattern">${escapeHtml(inc.pattern || 'Unclassified')}</span></td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-text">Failed loading incidents: ${err.message}</div></div>`;
  }
}

async function loadServicesTable() {
  const container = document.getElementById('services-list');
  try {
    const res = await fetch(`${API_BASE}/services`);
    if (!res.ok) throw new Error('Services load error');
    const data = await res.json();

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Service Name</th>
            <th>Owning Team</th>
            <th>Downstream Dependencies</th>
            <th>Active Graph Constraints</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.services.forEach(s => {
      html += `
        <tr>
          <td><strong><code>${escapeHtml(s.service)}</code></strong></td>
          <td><code>${escapeHtml(s.team)}</code></td>
          <td>${(s.dependencies || []).map(d => `<code>${escapeHtml(d)}</code>`).join(' ') || '<span style="color: var(--text-muted);">None</span>'}</td>
          <td><strong>${s.active_constraints_count}</strong> active rules</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty-state"><div class="empty-text">Failed loading services: ${err.message}</div></div>`;
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';

  let html = escapeHtml(text);

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');

  // Blockquotes
  html = html.replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Bullet points
  html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  // Line breaks to paragraphs
  html = html.split('\n\n').map(p => {
    p = p.trim();
    if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<blockquote')) {
      return p;
    }
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('');

  return html;
}
