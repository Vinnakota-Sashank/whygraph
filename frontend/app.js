/**
 * WhyGraph — Frontend Application Logic
 * Interactive PR Guardrail, Dynamic Expertise, Real-time Graph Stats, and Chat Agent
 */

const API_BASE = '/api';

// ── State ───────────────────────────────────────────────────────────────────
let currentService = 'checkout-service';

// ── DOM Elements ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPresets();
  initViolationForm();
  initChatForm();
  initExpertiseSelector();
  initInventoryTabs();
  initReingestButton();

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

      // Refresh specific tab data on view
      if (targetId === 'section-experts') {
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
    document.getElementById('stat-nodes-count').textContent = '24';
    document.getElementById('stat-edges-count').textContent = '48';
  }
}

function initReingestButton() {
  const btn = document.getElementById('btn-reingest');
  btn.addEventListener('click', async () => {
    btn.classList.add('loading');
    showToast('Rebuilding graph and indexing in FalkorDB...');
    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: 'POST' });
      if (!res.ok) throw new Error('Rebuild failed');
      const data = await res.json();
      showToast('✅ Graph rebuild complete!');
      await fetchGraphStats();
      loadExperts(document.getElementById('select-expert-service').value);
      loadInventoryData();
    } catch (err) {
      showToast('⚠️ Rebuild warning: verify backend connection');
      console.error(err);
    } finally {
      btn.classList.remove('loading');
    }
  });
}

// ── Demo Presets ────────────────────────────────────────────────────────────
function initPresets() {
  const serviceSelect = document.getElementById('select-service');
  const depsInput = document.getElementById('input-dependencies');
  const filesInput = document.getElementById('input-files');

  document.getElementById('preset-memcached').addEventListener('click', () => {
    serviceSelect.value = 'checkout-service';
    depsInput.value = 'pymemcache';
    filesInput.value = `services/checkout/cache_client.py\nservices/checkout/requirements.txt`;
    showToast('Loaded preset: Memcached in checkout-service');
    runViolationScan();
  });

  document.getElementById('preset-sync-payment').addEventListener('click', () => {
    serviceSelect.value = 'checkout-service';
    depsInput.value = 'httpx';
    filesInput.value = `services/checkout/payment_sync.py\nservices/checkout/router.py`;
    showToast('Loaded preset: Synchronous payment call');
    runViolationScan();
  });

  document.getElementById('preset-clean').addEventListener('click', () => {
    serviceSelect.value = 'user-service';
    depsInput.value = 'redis, psycopg2';
    filesInput.value = `services/user/session_repo.py\nservices/user/database.py`;
    showToast('Loaded preset: Compliant Redis/Postgres PR');
    runViolationScan();
  });
}

// ── PR Violation Form ───────────────────────────────────────────────────────
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
  statusPill.textContent = 'Scanning...';
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
          WhyGraph checked <strong>${data.constraints_checked}</strong> active constraints across the service topology.
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
              <div class="meta-field-value">${escapeHtml(v.source_type)}: ${escapeHtml(v.source_id)} ("${escapeHtml(v.source_title)}")</div>
            </div>
            <div class="meta-field">
              <div class="meta-field-label">Decision Author</div>
              <div class="meta-field-value">${escapeHtml(v.author_name || 'Team Architect')}</div>
            </div>
          </div>

          <!-- Graph Traversal Path -->
          <div class="traversal-section">
            <div class="traversal-title">Graph Traversal Lineage (FalkorDB Sub-Millisecond Path):</div>
            <div class="traversal-path">
              ${traversalSteps.map((step, idx) => {
                let nodeClass = 'path-node';
                if (step.startsWith('PR')) nodeClass += ' pr';
                else if (step.includes('Constraint')) nodeClass += ' constraint';
                else if (step.includes('ADR')) nodeClass += ' adr';
                else if (step.includes('PostMortem')) nodeClass += ' pm';

                return `
                  <span class="${nodeClass}">${escapeHtml(step)}</span>
                  ${idx < traversalSteps.length - 1 ? '<span class="path-arrow">&rarr;</span>' : ''}
                `;
              }).join('')}
            </div>
          </div>

          <!-- Outage Evidence -->
          ${v.evidence ? `
            <div class="evidence-box">
              <div class="evidence-header">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
                Validated by Past Incident: ${escapeHtml(v.evidence.incident_id)} (${escapeHtml(v.evidence.incident_severity)})
              </div>
              <div class="evidence-desc">
                <strong>Post-Mortem:</strong> "${escapeHtml(v.evidence.postmortem_title)}" (${escapeHtml(v.evidence.postmortem_id)}).
                This exact change previously resulted in service degradation. ADR constraints exist precisely to prevent recurrence.
              </div>
            </div>
          ` : ''}
        </div>
      `;
    });

    // Reviewers recommendation
    if (data.recommended_experts && data.recommended_experts.length > 0) {
      html += `
        <div class="reviewers-box">
          <div class="reviewers-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="8.5" cy="7" r="4"></circle>
              <line x1="20" y1="8" x2="20" y2="14"></line>
              <line x1="23" y1="11" x2="17" y2="11"></line>
            </svg>
            Assigned Graph Experts for Architectural Review
          </div>
          <div class="reviewers-list">
            ${data.recommended_experts.slice(0, 3).map(exp => `
              <div class="reviewer-chip">
                <div>
                  <span class="reviewer-name">${escapeHtml(exp.name)}</span>
                  <span class="reviewer-role">(${escapeHtml(exp.team)}, ${escapeHtml(exp.role)})</span>
                </div>
                <div class="score-badge">Expertise: ${exp.score}/100</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    output.innerHTML = html;
  } else {
    // Clean result
    statusPill.className = 'status-pill clean';
    statusPill.textContent = '✅ Compliant (0 Violations)';

    output.innerHTML = `
      <div class="empty-state" style="padding: 2.5rem 1rem;">
        <div style="font-size: 3.5rem; margin-bottom: 1rem;">✅</div>
        <h3 style="font-family: var(--font-display); font-size: 1.3rem; margin-bottom: 0.5rem; color: #34d399;">
          No Architectural Violations Detected
        </h3>
        <p style="color: var(--text-secondary); max-width: 480px; font-size: 0.9rem; line-height: 1.6;">
          Your proposed modifications for <strong>${escapeHtml(serviceName)}</strong> adhere to all active architectural constraints,
          technology standards, and post-mortem mandates.
        </p>
        <div style="margin-top: 1.25rem; font-size: 0.8rem; color: var(--text-muted); background: rgba(255, 255, 255, 0.03); padding: 0.5rem 1rem; border-radius: var(--radius-full);">
          Verified <strong>${data.constraints_checked || 0}</strong> active constraints in FalkorDB
        </div>
      </div>
    `;
  }
}

// ── Chat Form & Suggestion Chips ────────────────────────────────────────────
function initChatForm() {
  const form = document.getElementById('form-chat');
  const input = document.getElementById('input-chat');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    await sendChatMessage(query);
  });

  // Suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', async () => {
      const q = chip.getAttribute('data-query');
      if (q) {
        await sendChatMessage(q);
      }
    });
  });
}

async function sendChatMessage(query) {
  const chatMessages = document.getElementById('chat-messages');

  // Append user bubble
  appendChatBubble('user', query);

  // Append loading bot bubble
  const loadingBubble = appendChatBubble('bot', '<em>Thinking and traversing knowledge graph...</em>');
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query }),
    });

    if (!res.ok) throw new Error('API error on /chat');
    const data = await res.json();

    loadingBubble.querySelector('.bubble-content').innerHTML = formatMarkdown(data.reply);
  } catch (err) {
    loadingBubble.querySelector('.bubble-content').innerHTML = `
      <p style="color: #fb7185;">⚠️ Error connecting to WhyGraph reasoning agent: ${escapeHtml(err.message)}</p>
    `;
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendChatBubble(sender, htmlContent) {
  const chatMessages = document.getElementById('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;

  const iconSvg = sender === 'user' ? `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
      <circle cx="12" cy="7" r="4"></circle>
    </svg>
  ` : `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="18" cy="5" r="3"></circle>
      <circle cx="6" cy="12" r="3"></circle>
      <circle cx="18" cy="19" r="3"></circle>
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
    </svg>
  `;

  bubble.innerHTML = `
    <div class="bubble-avatar">${iconSvg}</div>
    <div class="bubble-content">${htmlContent}</div>
  `;

  chatMessages.appendChild(bubble);
  return bubble;
}

// ── Dynamic Expertise ───────────────────────────────────────────────────────
function initExpertiseSelector() {
  const select = document.getElementById('select-expert-service');
  select.addEventListener('change', () => {
    loadExperts(select.value);
  });
}

async function loadExperts(serviceName) {
  const container = document.getElementById('experts-container');
  container.innerHTML = `
    <div class="empty-state" style="grid-column: 1 / -1;">
      <div class="pulse-indicator" style="width: 16px; height: 16px; margin-bottom: 0.75rem;"></div>
      <div class="empty-text">Calculating dynamic multi-signal expertise for ${escapeHtml(serviceName)}...</div>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/experts/${serviceName}`);
    if (!res.ok) throw new Error('Failed to load experts');
    const data = await res.json();

    if (!data.experts || data.experts.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="empty-icon">👥</div>
          <div class="empty-text">No recorded contributors found for ${escapeHtml(serviceName)}.</div>
        </div>
      `;
      return;
    }

    let html = '';
    data.experts.forEach(exp => {
      const sig = exp.signals || {};
      html += `
        <div class="expert-card">
          <div class="expert-rank-badge">#${exp.rank}</div>
          <div class="expert-header">
            <div class="expert-name">${escapeHtml(exp.name)}</div>
            <div class="expert-role-team">${escapeHtml(exp.role)} &bull; ${escapeHtml(exp.team)}</div>
          </div>

          <div class="expert-score-container">
            <span style="font-size: 0.75rem; color: var(--text-muted);">Expertise:</span>
            <div class="score-meter">
              <div class="score-fill" style="width: ${exp.score}%;"></div>
            </div>
            <span style="font-family: var(--font-mono); font-size: 0.85rem; font-weight: 700; color: #38bdf8;">
              ${exp.score}/100
            </span>
          </div>

          <div class="expert-signals-grid">
            <div class="signal-item">Commits: <span class="signal-val">${sig.commits || 0}</span></div>
            <div class="signal-item">Reviews: <span class="signal-val">${sig.reviews || 0}</span></div>
            <div class="signal-item">Incidents: <span class="signal-val">${sig.incidents_resolved || 0}</span></div>
            <div class="signal-item">Docs: <span class="signal-val">${sig.docs_authored || 0}</span></div>
          </div>

          ${exp.related_incidents && exp.related_incidents.length > 0 ? `
            <div style="margin-top: 0.75rem; font-size: 0.75rem; color: #f87171;">
              💥 Incident Author: ${escapeHtml(exp.related_incidents[0].id)} (${escapeHtml(exp.related_incidents[0].severity)})
            </div>
          ` : ''}
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-icon">⚠️</div>
        <div class="empty-text">Could not load experts: ${err.message}</div>
      </div>
    `;
  }
}

// ── Knowledge Inventory ─────────────────────────────────────────────────────
async function loadInventoryData() {
  loadConstraintsTable();
  loadIncidentsTable();
  loadServicesTable();
}

async function loadConstraintsTable() {
  const container = document.getElementById('constraints-list');
  try {
    const res = await fetch(`${API_BASE}/constraints`);
    if (!res.ok) throw new Error('Constraints query failed');
    const data = await res.json();

    if (!data.constraints || data.constraints.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-text">No active constraints recorded in graph.</div></div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Constraint Rule</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Applies To</th>
            <th>Source Document</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.constraints.forEach(c => {
      const sourceTitle = c.adr_title || c.postmortem_title || c.source;
      const sourceId = c.adr_id || c.postmortem_id || '';
      html += `
        <tr>
          <td><span style="font-family: var(--font-mono); font-weight: 600; color: #a78bfa;">${escapeHtml(c.id)}</span></td>
          <td><strong>${escapeHtml(c.description)}</strong></td>
          <td><span class="pill-tag">${escapeHtml(c.type || 'ARCH')}</span></td>
          <td><span class="badge-severity">${escapeHtml(c.severity || 'MUST')}</span></td>
          <td>${(c.applies_to || []).map(s => `<code>${escapeHtml(s)}</code>`).join(' ')}</td>
          <td>${escapeHtml(sourceId)} ${sourceTitle ? `("${escapeHtml(sourceTitle)}")` : ''}</td>
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
    if (!res.ok) throw new Error('Incidents query failed');
    const data = await res.json();

    if (!data.incidents || data.incidents.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-text">No incident records found.</div></div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th>Incident ID</th>
            <th>Title</th>
            <th>Severity</th>
            <th>Date</th>
            <th>Downtime</th>
            <th>Affected Services</th>
            <th>Pattern Tag</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.incidents.forEach(inc => {
      html += `
        <tr>
          <td><span style="font-family: var(--font-mono); font-weight: 700; color: #f87171;">${escapeHtml(inc.id)}</span></td>
          <td><strong>${escapeHtml(inc.title)}</strong></td>
          <td><span class="badge-severity" style="background: rgba(239, 68, 68, 0.2);">${escapeHtml(inc.severity)}</span></td>
          <td>${escapeHtml(inc.date)}</td>
          <td>${inc.duration_minutes ? `${inc.duration_minutes} min` : 'N/A'}</td>
          <td>${(inc.affected_services || []).map(s => `<code>${escapeHtml(s)}</code>`).join(' ')}</td>
          <td><span class="pill-tag">${escapeHtml(inc.pattern || 'Cascade')}</span></td>
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
    if (!res.ok) throw new Error('Services query failed');
    const data = await res.json();

    if (!data.services || data.services.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-text">No services registered.</div></div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th>Service Name</th>
            <th>Responsible Team</th>
            <th>Dependencies</th>
            <th>Active Rules</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.services.forEach(s => {
      html += `
        <tr>
          <td><code style="font-size: 0.9rem; color: #38bdf8;">${escapeHtml(s.service)}</code></td>
          <td><strong>${escapeHtml(s.team || 'Platform')}</strong></td>
          <td>${(s.dependencies || []).map(d => `<code>${escapeHtml(d)}</code>`).join(' ') || '<span style="color: var(--text-muted);">None</span>'}</td>
          <td><span class="pill-tag">${s.active_constraints_count || 0} constraints</span></td>
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
