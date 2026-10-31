'use strict';
/**
 * EventGenie AI - Main Application
 * All API calls go through the Flask backend.
 * No API keys are present in this file.
 */

const API_BASE = '/api';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  currentPage: 'landing',
  events: [],
  currentEvent: null,
  currentPlan: null,
  budgetChart: null,
};

// ── Utility: API Fetch ──────────────────────────────────────────────────────
async function apiFetch(endpoint, options = {}) {
  const defaultOptions = {
    headers: { 'Content-Type': 'application/json' },
  };
  const merged = { ...defaultOptions, ...options };
  if (merged.body && typeof merged.body !== 'string') {
    merged.body = JSON.stringify(merged.body);
  }
  const resp = await fetch(`${API_BASE}${endpoint}`, merged);
  const json = await resp.json();
  if (!json.success && resp.status >= 400) {
    throw new Error(json.error || 'An error occurred');
  }
  return json;
}

// ── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ── Navigation ──────────────────────────────────────────────────────────────
function navigateTo(page, params = {}) {
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  // Show requested page
  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add('active');

  // Update nav items
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navItem = document.querySelector(`[data-page="${page}"]`);
  if (navItem) navItem.classList.add('active');

  state.currentPage = page;

  // Handle sidebar on mobile
  closeMobileSidebar();

  // Update topbar title
  const titles = {
    dashboard: 'Dashboard',
    events: 'My Events',
    'create-event': 'Create Event',
    'event-detail': state.currentEvent ? state.currentEvent.name : 'Event Details',
    chat: 'AI Planning Assistant',
    budget: 'Budget Planner',
    tasks: 'Timeline & Tasks',
    settings: 'Settings',
  };
  document.getElementById('topbarTitle').textContent = titles[page] || 'EventGenie AI';

  // Load page data
  if (page === 'dashboard') loadDashboard();
  else if (page === 'events') loadEventsPage();
  else if (page === 'event-detail' && params.eventId) loadEventDetail(params.eventId);
  else if (page === 'chat' && state.currentEvent) loadChatPage();
  else if (page === 'budget' && state.currentEvent) loadBudgetPage();
  else if (page === 'tasks' && state.currentEvent) loadTasksPage();
}

function showAppShell() {
  document.getElementById('landingSection').style.display = 'none';
  document.getElementById('appShell').style.display = 'flex';
  navigateTo('dashboard');
}

function showLanding() {
  document.getElementById('landingSection').style.display = 'block';
  document.getElementById('appShell').style.display = 'none';
}

// ── Mobile Sidebar ──────────────────────────────────────────────────────────
function toggleMobileSidebar() {
  document.getElementById('sidebar').classList.toggle('mobile-open');
}
function closeMobileSidebar() {
  document.getElementById('sidebar').classList.remove('mobile-open');
}

// ── API Health Check ────────────────────────────────────────────────────────
async function checkApiHealth() {
  try {
    const data = await apiFetch('/health');
    const dot = document.getElementById('apiStatusDot');
    const text = document.getElementById('apiStatusText');
    if (data.api_configured) {
      dot.className = 'api-status-dot connected';
      text.textContent = 'Gemini AI Connected';
    } else {
      dot.className = 'api-status-dot error';
      text.textContent = 'API Key Not Set';
    }
  } catch (e) {
    document.getElementById('apiStatusDot').className = 'api-status-dot error';
    document.getElementById('apiStatusText').textContent = 'Server Error';
  }
}

// ── Dashboard ───────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const data = await apiFetch('/events');
    state.events = data.data;
    renderDashboard(state.events);
  } catch (e) {
    showToast('Failed to load dashboard: ' + e.message, 'error');
  }
}

function renderDashboard(events) {
  const now = new Date();
  const upcoming = events.filter(e => e.event_date && new Date(e.event_date) >= now);
  const totalBudget = events.reduce((s, e) => s + (e.budget || 0), 0);
  const allTasks = events.reduce((s, e) => s + (e.total_tasks || 0), 0);
  const completedTasks = events.reduce((s, e) => s + (e.completed_tasks || 0), 0);

  setEl('statTotalEvents', events.length);
  setEl('statUpcoming', upcoming.length);
  setEl('statTotalBudget', formatCurrency(totalBudget));
  setEl('statTasksProgress', allTasks > 0 ? `${completedTasks}/${allTasks}` : '0/0');

  // Recent events
  const recentEl = document.getElementById('recentEventsGrid');
  if (events.length === 0) {
    recentEl.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-state-icon">🎉</div>
        <h3>No Events Yet</h3>
        <p>Create your first event to get started with AI-powered planning.</p>
        <button class="btn btn-primary" onclick="navigateTo('create-event')">
          ${icon('plus')} Create Event
        </button>
      </div>`;
  } else {
    recentEl.innerHTML = events.slice(0, 6).map(eventCardHTML).join('');
  }

  // Upcoming events list
  const upcomingEl = document.getElementById('upcomingEventsList');
  if (upcoming.length === 0) {
    upcomingEl.innerHTML = `<div class="text-center text-muted" style="padding:24px;font-size:.875rem">No upcoming events</div>`;
  } else {
    upcomingEl.innerHTML = upcoming.slice(0, 5).map(e => `
      <div class="flex items-center gap-12 mb-16" style="cursor:pointer" onclick="openEvent(${e.id})">
        <div class="stat-icon ${eventTypeColor(e.event_type)}" style="width:40px;height:40px;border-radius:10px;font-size:18px">
          ${eventEmoji(e.event_type)}
        </div>
        <div style="flex:1">
          <div style="font-weight:600;font-size:.875rem">${escHtml(e.name)}</div>
          <div style="font-size:.78rem;color:var(--text-muted)">${formatDate(e.event_date)}</div>
        </div>
        <div style="font-size:.78rem;color:var(--primary);font-weight:600">${daysUntil(e.event_date)}</div>
      </div>
    `).join('');
  }
}

// ── Events Page ─────────────────────────────────────────────────────────────
async function loadEventsPage() {
  try {
    const data = await apiFetch('/events');
    state.events = data.data;
    renderEventsGrid(state.events);
  } catch (e) {
    showToast('Failed to load events: ' + e.message, 'error');
  }
}

function renderEventsGrid(events) {
  const grid = document.getElementById('eventsGrid');
  if (!grid) return;
  if (events.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-state-icon">📋</div>
        <h3>No Events Found</h3>
        <p>Start planning your first event with AI-powered assistance.</p>
        <button class="btn btn-primary" onclick="navigateTo('create-event')">
          ${icon('plus')} Create Your First Event
        </button>
      </div>`;
  } else {
    grid.innerHTML = events.map(eventCardHTML).join('');
  }
}

function eventCardHTML(e) {
  return `
    <div class="event-card" onclick="openEvent(${e.id})">
      <div class="event-card-header">
        <div class="flex gap-12 items-center">
          <div class="event-card-icon ${eventTypeColor(e.event_type)}">${eventEmoji(e.event_type)}</div>
          <div>
            <div class="event-card-name">${escHtml(e.name)}</div>
            <span class="badge badge-${e.event_type}">${e.event_type}</span>
          </div>
        </div>
        <span class="badge badge-${e.status}">${e.status}</span>
      </div>
      <div class="event-card-body">
        ${e.event_date ? `<div class="event-card-detail">${icon('calendar')} ${formatDate(e.event_date)} ${daysUntilTag(e.event_date)}</div>` : ''}
        ${e.location ? `<div class="event-card-detail">${icon('map-pin')} ${escHtml(e.location)}</div>` : ''}
        ${e.guest_count ? `<div class="event-card-detail">${icon('users')} ${e.guest_count} guests</div>` : ''}
        ${e.budget ? `<div class="event-card-detail">${icon('indian-rupee')} ${formatCurrency(e.budget)}</div>` : ''}
      </div>
      <div class="event-card-footer">
        <div class="progress-bar-wrap">
          <div class="progress-label">${e.completed_tasks}/${e.total_tasks} tasks done</div>
          <div class="progress-bar"><div class="progress-fill" style="width:${e.task_progress}%"></div></div>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); openEvent(${e.id})">
          ${icon('arrow-right')} View
        </button>
      </div>
    </div>`;
}

// ── Event Detail Page ────────────────────────────────────────────────────────
async function openEvent(eventId) {
  try {
    const data = await apiFetch(`/events/${eventId}`);
    state.currentEvent = data.data;
    navigateTo('event-detail', { eventId });
  } catch (e) {
    showToast('Failed to load event: ' + e.message, 'error');
  }
}

async function loadEventDetail(eventId) {
  try {
    const data = await apiFetch(`/events/${eventId}`);
    state.currentEvent = data.data;
    renderEventDetail(state.currentEvent);
  } catch (e) {
    showToast('Failed to load event: ' + e.message, 'error');
  }
}

function renderEventDetail(event) {
  document.getElementById('topbarTitle').textContent = event.name;

  const container = document.getElementById('eventDetailContainer');
  const planSections = (event.plans || []).reduce((acc, p) => { acc[p.plan_type] = p; return acc; }, {});

  container.innerHTML = `
    <div class="page-header">
      <div class="page-header-text">
        <div class="flex items-center gap-12 mb-8">
          <span style="font-size:2rem">${eventEmoji(event.event_type)}</span>
          <div>
            <h2>${escHtml(event.name)}</h2>
            <span class="badge badge-${event.event_type}">${event.event_type}</span>
            <span class="badge badge-${event.status}" style="margin-left:6px">${event.status}</span>
          </div>
        </div>
      </div>
      <div class="flex gap-12">
        <button class="btn btn-secondary btn-sm" onclick="openEditEventModal(${event.id})">
          ${icon('edit')} Edit
        </button>
        <button class="btn btn-danger btn-sm" onclick="confirmDeleteEvent(${event.id})">
          ${icon('trash')} Delete
        </button>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="stats-grid" style="margin-bottom:24px">
      <div class="stat-card">
        <div class="stat-icon purple">${icon('calendar')}</div>
        <div class="stat-info">
          <div class="stat-value">${event.event_date ? formatDate(event.event_date) : 'TBD'}</div>
          <div class="stat-label">Event Date ${event.event_date ? daysUntilTag(event.event_date) : ''}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon cyan">${icon('users')}</div>
        <div class="stat-info">
          <div class="stat-value">${event.guest_count || '—'}</div>
          <div class="stat-label">Guests Expected</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon green">${icon('indian-rupee')}</div>
        <div class="stat-info">
          <div class="stat-value">${event.budget ? formatCurrency(event.budget) : '—'}</div>
          <div class="stat-label">Total Budget</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon orange">${icon('check-circle')}</div>
        <div class="stat-info">
          <div class="stat-value">${event.task_progress}%</div>
          <div class="stat-label">Tasks Complete (${event.completed_tasks}/${event.total_tasks})</div>
        </div>
      </div>
    </div>

    <!-- Info Grid -->
    <div class="grid-2 mb-24">
      <div class="card">
        <div class="card-header"><span class="card-title">Event Details</span></div>
        <div class="card-body">
          ${event.location ? `<div class="flex gap-8 mb-8"><span class="text-muted text-sm" style="min-width:80px">Location</span><span class="text-sm font-bold">${escHtml(event.location)}</span></div>` : ''}
          ${event.theme ? `<div class="flex gap-8 mb-8"><span class="text-muted text-sm" style="min-width:80px">Theme</span><span class="text-sm font-bold">${escHtml(event.theme)}</span></div>` : ''}
          ${event.preferences ? `<div class="flex gap-8 mb-8"><span class="text-muted text-sm" style="min-width:80px">Notes</span><span class="text-sm">${escHtml(event.preferences)}</span></div>` : ''}
          ${event.description ? `<div class="flex gap-8 mb-8"><span class="text-muted text-sm" style="min-width:80px">Description</span><span class="text-sm">${escHtml(event.description)}</span></div>` : ''}
          <div class="divider"></div>
          <div class="flex gap-8"><span class="text-muted text-sm" style="min-width:80px">Created</span><span class="text-sm">${formatDateTime(event.created_at)}</span></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Quick Actions</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:10px">
          <button class="btn btn-primary w-full" onclick="generatePlan(${event.id})" id="generatePlanBtn">
            ${icon('sparkles')} Generate AI Plan
          </button>
          <button class="btn btn-secondary w-full" onclick="navigateTo('chat')">
            ${icon('message-circle')} Open AI Assistant
          </button>
          <button class="btn btn-secondary w-full" onclick="navigateTo('budget')">
            ${icon('pie-chart')} View Budget Planner
          </button>
          <button class="btn btn-secondary w-full" onclick="navigateTo('tasks')">
            ${icon('check-square')} Manage Tasks
          </button>
          <div class="flex gap-8 mt-8">
            <button class="btn btn-secondary flex-1 btn-sm" onclick="printEventPlan()" aria-label="Print event plan">
              ${icon('sparkles')} Print Plan
            </button>
            <button class="btn btn-secondary flex-1 btn-sm" onclick="exportEventPlan(${event.id})" aria-label="Export event plan as JSON">
              ${icon('arrow-right')} Export JSON
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- AI Plan (if generated) -->
    ${planSections['overview'] ? renderPlanOverview(planSections) : `
      <div class="card">
        <div class="card-body">
          <div class="empty-state">
            <div class="empty-state-icon">✨</div>
            <h3>No AI Plan Generated Yet</h3>
            <p>Click "Generate AI Plan" to create a personalized event plan with budget, timeline, and vendor checklist.</p>
            <button class="btn btn-primary" onclick="generatePlan(${event.id})">
              ${icon('sparkles')} Generate AI Plan
            </button>
          </div>
        </div>
      </div>
    `}
  `;
}

function printEventPlan() {
  window.print();
}

async function exportEventPlan(eventId) {
  try {
    const res = await apiFetch(`/events/${eventId}/export`);
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res.data, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    const safeName = (state.currentEvent?.name || 'event').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    downloadAnchor.setAttribute("download", `${safeName}_plan.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast('Event plan exported as JSON!');
  } catch (e) {
    showToast('Failed to export: ' + e.message, 'error');
  }
}

function renderPlanOverview(planSections) {
  const overview = planSections['overview']?.content;
  const ideas = planSections['ideas']?.content;

  return `
    <div class="tab-nav" id="planTabNav" role="tablist" aria-label="Event Plan Sections">
      <button class="tab-btn active" role="tab" aria-selected="true" aria-controls="planTabOverview" onclick="switchPlanTab('overview', this)">Overview</button>
      <button class="tab-btn" role="tab" aria-selected="false" aria-controls="planTabTimeline" onclick="switchPlanTab('timeline', this)">Timeline</button>
      <button class="tab-btn" role="tab" aria-selected="false" aria-controls="planTabSchedule" onclick="switchPlanTab('schedule', this)">Day Schedule</button>
      <button class="tab-btn" role="tab" aria-selected="false" aria-controls="planTabVendors" onclick="switchPlanTab('vendors', this)">Vendors</button>
      <button class="tab-btn" role="tab" aria-selected="false" aria-controls="planTabIdeas-tab" onclick="switchPlanTab('ideas-tab', this)">Ideas</button>
    </div>

    <div id="planTabOverview" class="plan-tab">
      <div class="card">
        <div class="card-header">
          <span class="card-title">${icon('star')} Plan Overview</span>
          <button class="btn btn-sm btn-secondary" onclick="generatePlan(${state.currentEvent.id})">
            ${icon('refresh-cw')} Regenerate
          </button>
        </div>
        <div class="card-body">
          ${overview ? `
            <p style="font-size:.95rem;color:var(--text-primary);margin-bottom:16px">${escHtml(overview.summary || '')}</p>
            ${overview.key_highlights ? `
              <div class="plan-section-title">${icon('zap')} Key Highlights</div>
              <div class="ideas-grid">
                ${overview.key_highlights.map(h => `<div class="idea-chip">✨ ${escHtml(h)}</div>`).join('')}
              </div>
            ` : ''}
            <div class="grid-2 mt-16">
              ${overview.estimated_duration ? `<div class="stat-card" style="padding:14px">
                <div class="stat-icon purple" style="width:36px;height:36px;font-size:16px">${icon('clock')}</div>
                <div><div class="stat-value" style="font-size:1.1rem">${escHtml(overview.estimated_duration)}</div><div class="stat-label">Duration</div></div>
              </div>` : ''}
              ${overview.recommended_venue_type ? `<div class="stat-card" style="padding:14px">
                <div class="stat-icon cyan" style="width:36px;height:36px;font-size:16px">${icon('map-pin')}</div>
                <div><div class="stat-value" style="font-size:.9rem;font-weight:600">${escHtml(overview.recommended_venue_type)}</div><div class="stat-label">Venue Type</div></div>
              </div>` : ''}
            </div>
          ` : '<p class="text-muted">Overview data not available.</p>'}
        </div>
      </div>
    </div>

    <div id="planTabTimeline" class="plan-tab hidden">
      ${renderTimelineSection(planSections['preparation_timeline']?.content)}
    </div>

    <div id="planTabSchedule" class="plan-tab hidden">
      ${renderDayScheduleSection(planSections['event_day_schedule']?.content)}
    </div>

    <div id="planTabVendors" class="plan-tab hidden">
      ${renderVendorSection(planSections['vendor_checklist']?.content)}
    </div>

    <div id="planTabIdeas-tab" class="plan-tab hidden">
      ${renderIdeasSection(ideas)}
    </div>
  `;
}

function switchPlanTab(tab, btn) {
  document.querySelectorAll('.plan-tab').forEach(t => t.classList.add('hidden'));
  document.querySelectorAll('#planTabNav .tab-btn').forEach(b => {
    b.classList.remove('active');
    b.setAttribute('aria-selected', 'false');
  });
  const el = document.getElementById(`planTab${capitalize(tab)}`);
  if (el) el.classList.remove('hidden');
  btn.classList.add('active');
  btn.setAttribute('aria-selected', 'true');
}

function renderTimelineSection(timeline) {
  if (!Array.isArray(timeline) || timeline.length === 0) {
    return `<div class="card"><div class="card-body"><p class="text-muted text-center">No timeline data. Generate a plan first.</p></div></div>`;
  }
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">${icon('calendar')} Preparation Timeline</span></div>
      <div class="card-body">
        <div class="timeline">
          ${timeline.map(phase => `
            <div class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-phase">${escHtml(phase.phase || '')}</div>
              <div class="timeline-tasks">
                ${(phase.tasks || []).map(t => `
                  <div class="timeline-task">
                    <strong>${escHtml(t.title || '')}</strong>
                    ${t.description ? `<br><span style="color:var(--text-muted);font-size:.82rem">${escHtml(t.description)}</span>` : ''}
                    <span class="badge badge-${t.priority || 'medium'}" style="margin-left:8px;vertical-align:middle">${t.priority || 'medium'}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>`;
}

function renderDayScheduleSection(schedule) {
  if (!Array.isArray(schedule) || schedule.length === 0) {
    return `<div class="card"><div class="card-body"><p class="text-muted text-center">No day schedule available.</p></div></div>`;
  }
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">${icon('clock')} Event Day Schedule</span></div>
      <div class="card-body">
        ${schedule.map(item => `
          <div class="schedule-item">
            <div class="schedule-time">${escHtml(item.time || '')}</div>
            <div>
              <div class="schedule-activity font-bold">${escHtml(item.activity || '')}</div>
              ${item.duration_minutes ? `<div class="schedule-note">${icon('clock')} ${item.duration_minutes} min</div>` : ''}
              ${item.notes ? `<div class="schedule-note">${escHtml(item.notes)}</div>` : ''}
              ${item.responsible ? `<div class="schedule-note">${icon('user')} ${escHtml(item.responsible)}</div>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;
}

function renderVendorSection(checklist) {
  if (!Array.isArray(checklist) || checklist.length === 0) {
    return `<div class="card"><div class="card-body"><p class="text-muted text-center">No vendor checklist available.</p></div></div>`;
  }
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">${icon('list-checks')} Vendor Checklist</span></div>
      <div class="card-body">
        ${checklist.map(cat => `
          <div class="vendor-category">
            <div class="vendor-category-title">${icon('briefcase')} ${escHtml(cat.category || '')}</div>
            <div class="vendor-tasks">
              ${(cat.tasks || []).map(t => `
                <div class="vendor-task">
                  <span style="color:var(--primary)">${icon('check')}</span>
                  <div>
                    <div style="font-weight:600">${escHtml(t.title || '')}</div>
                    ${t.description ? `<div style="font-size:.8rem;color:var(--text-muted)">${escHtml(t.description)}</div>` : ''}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;
}

function renderIdeasSection(ideas) {
  if (!ideas) return `<div class="card"><div class="card-body"><p class="text-muted text-center">No ideas available.</p></div></div>`;
  return `
    <div class="card">
      <div class="card-header"><span class="card-title">${icon('lightbulb')} Creative Ideas & Suggestions</span></div>
      <div class="card-body">
        ${ideas.themes ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('palette')} Themes</div>
            <div class="ideas-grid">${ideas.themes.map(t => `<div class="idea-chip">🎨 ${escHtml(t)}</div>`).join('')}</div>
          </div>` : ''}
        ${ideas.color_combinations ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('droplet')} Color Palettes</div>
            <div style="display:flex;flex-direction:column;gap:10px">
              ${ideas.color_combinations.map(c => `
                <div class="flex items-center gap-12">
                  <span class="text-sm font-bold">${escHtml(c.name || '')}</span>
                  <div class="color-palette">
                    ${(c.colors || []).map(col => `<div class="color-swatch" style="background:${escHtml(col)}" title="${escHtml(col)}"></div>`).join('')}
                  </div>
                </div>`).join('')}
            </div>
          </div>` : ''}
        ${ideas.decoration_ideas ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('sparkles')} Decoration Ideas</div>
            <div class="ideas-grid">${ideas.decoration_ideas.map(d => `<div class="idea-chip">✨ ${escHtml(d)}</div>`).join('')}</div>
          </div>` : ''}
        ${ideas.menu_suggestions ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('utensils')} Menu Suggestions</div>
            <div class="ideas-grid">${ideas.menu_suggestions.map(m => `<div class="idea-chip">🍽️ ${escHtml(m)}</div>`).join('')}</div>
          </div>` : ''}
        ${ideas.entertainment ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('music')} Entertainment</div>
            <div class="ideas-grid">${ideas.entertainment.map(e => `<div class="idea-chip">🎵 ${escHtml(e)}</div>`).join('')}</div>
          </div>` : ''}
        ${ideas.budget_saving_tips ? `
          <div class="plan-section">
            <div class="plan-section-title">${icon('piggy-bank')} Budget-Saving Tips</div>
            <div style="display:flex;flex-direction:column;gap:8px">
              ${ideas.budget_saving_tips.map(t => `
                <div class="flex items-center gap-8">
                  <span style="color:var(--success)">${icon('check-circle')}</span>
                  <span class="text-sm">${escHtml(t)}</span>
                </div>`).join('')}
            </div>
          </div>` : ''}
      </div>
    </div>`;
}

// ── Generate Plan ────────────────────────────────────────────────────────────
async function generatePlan(eventId) {
  const btn = document.getElementById('generatePlanBtn') || document.querySelector(`[onclick="generatePlan(${eventId})"]`);
  const origText = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = `<div class="spinner" style="width:16px;height:16px;margin:0"></div> Generating…`; }

  showToast('Generating your personalized event plan… This may take 30-60 seconds.', 'info');

  try {
    const data = await apiFetch(`/events/${eventId}/generate-plan`, { method: 'POST' });
    showToast('Event plan generated successfully! 🎉', 'success');
    state.currentEvent = data.data;
    await loadEventDetail(eventId);
  } catch (e) {
    showToast('Failed to generate plan: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
  }
}

// ── Create Event Form ────────────────────────────────────────────────────────
function initCreateEventForm() {
  const form = document.getElementById('createEventForm');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('[type="submit"]');
    const origText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<div class="spinner" style="width:16px;height:16px;margin:0"></div> Creating…`;

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    // Clean empty strings
    Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k]; });
    if (payload.budget) payload.budget = parseFloat(payload.budget);
    if (payload.guest_count) payload.guest_count = parseInt(payload.guest_count);

    try {
      const data = await apiFetch('/events', { method: 'POST', body: payload });
      showToast(`Event "${data.data.name}" created!`, 'success');
      form.reset();
      state.currentEvent = data.data;
      navigateTo('event-detail', { eventId: data.data.id });
    } catch (e) {
      showToast('Failed to create event: ' + e.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = origText;
    }
  });
}

// ── Edit Event Modal ─────────────────────────────────────────────────────────
function openEditEventModal(eventId) {
  const event = state.currentEvent;
  if (!event) return;
  document.getElementById('editEventId').value = event.id;
  document.getElementById('editEventName').value = event.name;
  document.getElementById('editEventType').value = event.event_type;
  document.getElementById('editEventLocation').value = event.location || '';
  document.getElementById('editEventDate').value = event.event_date || '';
  document.getElementById('editEventGuests').value = event.guest_count || '';
  document.getElementById('editEventBudget').value = event.budget || '';
  document.getElementById('editEventTheme').value = event.theme || '';
  document.getElementById('editEventPreferences').value = event.preferences || '';
  openModal('editEventModal');
}

async function saveEditEvent() {
  const eventId = document.getElementById('editEventId').value;
  const payload = {
    name: document.getElementById('editEventName').value.trim(),
    event_type: document.getElementById('editEventType').value,
    location: document.getElementById('editEventLocation').value.trim(),
    event_date: document.getElementById('editEventDate').value,
    guest_count: document.getElementById('editEventGuests').value ? parseInt(document.getElementById('editEventGuests').value) : null,
    budget: document.getElementById('editEventBudget').value ? parseFloat(document.getElementById('editEventBudget').value) : null,
    theme: document.getElementById('editEventTheme').value.trim(),
    preferences: document.getElementById('editEventPreferences').value.trim(),
  };
  try {
    const data = await apiFetch(`/events/${eventId}`, { method: 'PUT', body: payload });
    state.currentEvent = data.data;
    closeModal('editEventModal');
    showToast('Event updated!', 'success');
    loadEventDetail(parseInt(eventId));
  } catch (e) {
    showToast('Failed to update event: ' + e.message, 'error');
  }
}

// ── Delete Event ─────────────────────────────────────────────────────────────
function confirmDeleteEvent(eventId) {
  if (confirm('Are you sure you want to delete this event? This will remove all plans, tasks, and budget data.')) {
    deleteEvent(eventId);
  }
}

async function deleteEvent(eventId) {
  try {
    await apiFetch(`/events/${eventId}`, { method: 'DELETE' });
    showToast('Event deleted.', 'success');
    state.currentEvent = null;
    navigateTo('events');
  } catch (e) {
    showToast('Failed to delete event: ' + e.message, 'error');
  }
}

// ── Budget Page ──────────────────────────────────────────────────────────────
let budgetItemEdits = {};

async function loadBudgetPage() {
  if (!state.currentEvent) return;
  document.getElementById('budgetEventName').textContent = state.currentEvent.name;

  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/budget`);
    renderBudgetPage(data.data);
  } catch (e) {
    showToast('Failed to load budget: ' + e.message, 'error');
  }
}

function renderBudgetPage(budgetData) {
  const { items, summary, total_budget } = budgetData;
  budgetItemEdits = {};

  // Summary bar
  const pct = Math.min(summary.utilization_percent, 100);
  const fill = document.getElementById('budgetSummaryFill');
  fill.style.width = pct + '%';
  fill.classList.toggle('overrun', summary.is_overrun);

  setEl('budgetTotalBudget', formatCurrency(summary.total_budget));
  setEl('budgetAllocated', formatCurrency(summary.total_allocated));
  setEl('budgetRemaining', formatCurrency(Math.abs(summary.remaining)));
  setEl('budgetRemainingLabel', summary.is_overrun ? 'Over Budget' : 'Remaining');
  setEl('budgetUtilization', summary.utilization_percent.toFixed(1) + '%');

  const overrunAlert = document.getElementById('budgetOverrunAlert');
  if (summary.is_overrun) {
    overrunAlert.classList.remove('hidden');
    document.getElementById('budgetOverrunAmount').textContent = formatCurrency(summary.overrun_amount);
  } else {
    overrunAlert.classList.add('hidden');
  }

  // Render items
  const listEl = document.getElementById('budgetItemsList');
  const COLORS = ['#7c3aed','#06b6d4','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1'];

  if (items.length === 0) {
    listEl.innerHTML = `<div class="text-center text-muted" style="padding:40px">No budget items yet. Generate an AI plan to populate the budget.</div>`;
  } else {
    listEl.innerHTML = items.map((item, i) => {
      const color = COLORS[i % COLORS.length];
      return `
        <div class="budget-item" data-id="${item.id}">
          <div class="budget-color" style="background:${color}" aria-hidden="true"></div>
          <div class="budget-category">
            <div style="font-weight:700;font-size:.9rem">${escHtml(item.category)}</div>
            ${item.description ? `<div style="font-size:.75rem;color:var(--text-muted)">${escHtml(item.description)}</div>` : ''}
            ${!item.is_confirmed ? `<div style="font-size:.72rem;color:var(--warning)">Estimated — not confirmed</div>` : ''}
          </div>
          <input type="number" class="budget-amount-input" value="${item.amount}" 
            aria-label="Allocated amount for ${escHtml(item.category)}"
            onchange="onBudgetItemChange(${item.id}, this.value)"
            onblur="saveBudgetChanges()"
            min="0" step="100">
          <div class="budget-pct">${item.percentage?.toFixed(1) || 0}%</div>
          <button class="btn btn-icon btn-danger btn-sm" onclick="deleteBudgetItem(${item.id})" aria-label="Remove ${escHtml(item.category)} budget item" title="Remove">
            ${icon('trash')}
          </button>
        </div>`;
    }).join('');
  }

  // Chart
  if (items.length > 0) {
    renderBudgetChart(items, COLORS);
  }
}

function onBudgetItemChange(itemId, value) {
  budgetItemEdits[itemId] = Math.max(0, parseFloat(value) || 0);
}

async function saveBudgetChanges() {
  if (Object.keys(budgetItemEdits).length === 0) return;
  const items = Object.entries(budgetItemEdits).map(([id, amount]) => ({ id: parseInt(id), amount }));
  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/budget`, {
      method: 'PUT', body: { items },
    });
    budgetItemEdits = {};
    showToast('Budget updated successfully');
    renderBudgetPage(data.data);
  } catch (e) {
    showToast('Failed to save budget: ' + e.message, 'error');
  }
}

async function addNewBudgetItemRow() {
  const category = prompt('Enter budget category name (e.g. Photography, Catering, DJ & Music):');
  if (!category || !category.trim()) return;
  const amountStr = prompt('Enter estimated amount (₹ INR):', '10000');
  const amount = Math.max(0, parseFloat(amountStr) || 0);
  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/budget`, {
      method: 'PUT',
      body: { items: [{ category: category.trim(), amount: amount, estimated_amount: amount }] },
    });
    showToast('Category added to budget');
    renderBudgetPage(data.data);
  } catch (e) {
    showToast('Failed to add category: ' + e.message, 'error');
  }
}

async function deleteBudgetItem(itemId) {
  if (!confirm('Remove this budget item?')) return;
  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/budget/${itemId}`, {
      method: 'DELETE',
    });
    showToast('Budget item removed');
    renderBudgetPage(data.data);
  } catch (e) {
    showToast('Failed to remove item: ' + e.message, 'error');
  }
}

function renderBudgetChart(items, colors) {
  const canvas = document.getElementById('budgetChart');
  if (!canvas) return;
  if (state.budgetChart) { state.budgetChart.destroy(); state.budgetChart = null; }

  state.budgetChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: items.map(i => i.category),
      datasets: [{
        data: items.map(i => i.amount),
        backgroundColor: items.map((_, i) => colors[i % colors.length]),
        borderWidth: 3,
        borderColor: '#ffffff',
        hoverBorderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom', labels: { font: { family: 'Inter', size: 12 }, padding: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.raw)} (${((ctx.raw / ctx.dataset.data.reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%)`,
          },
        },
      },
    },
  });
}

// ── Tasks Page ───────────────────────────────────────────────────────────────
async function loadTasksPage() {
  if (!state.currentEvent) return;
  document.getElementById('tasksEventName').textContent = state.currentEvent.name;

  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/tasks`);
    renderTasksPage(data.data);
  } catch (e) {
    showToast('Failed to load tasks: ' + e.message, 'error');
  }
}

function renderTasksPage(tasks) {
  const total = tasks.length;
  const completed = tasks.filter(t => t.status === 'completed').length;
  const pct = total > 0 ? Math.round(completed / total * 100) : 0;

  document.getElementById('tasksProgressFill').style.width = pct + '%';
  setEl('tasksProgressText', `${completed}/${total} tasks complete (${pct}%)`);

  const pending = tasks.filter(t => t.status === 'pending');
  const inProgress = tasks.filter(t => t.status === 'in_progress');
  const completedTasks = tasks.filter(t => t.status === 'completed');

  document.getElementById('tasksPendingList').innerHTML = renderTasksList(pending, true);
  document.getElementById('tasksInProgressList').innerHTML = renderTasksList(inProgress);
  document.getElementById('tasksCompletedList').innerHTML = renderTasksList(completedTasks);

  setEl('tasksPendingCount', pending.length);
  setEl('tasksInProgressCount', inProgress.length);
  setEl('tasksCompletedCount', completedTasks.length);
}

function renderTasksList(tasks, showEmpty = false) {
  if (tasks.length === 0) {
    return showEmpty ? '<p class="text-muted text-sm text-center" style="padding:16px">No pending tasks</p>' : '';
  }
  return `<div class="task-list">${tasks.map(t => taskItemHTML(t)).join('')}</div>`;
}

function taskItemHTML(task) {
  const isCompleted = task.status === 'completed';
  return `
    <div class="task-item ${isCompleted ? 'completed' : ''}" id="task-${task.id}" role="listitem">
      <button class="task-checkbox ${isCompleted ? 'checked' : ''}" role="checkbox" aria-checked="${isCompleted}" aria-label="Mark task ${escHtml(task.title)} as ${isCompleted ? 'incomplete' : 'complete'}" onclick="toggleTask(${task.id}, '${task.status}')"></button>
      <div class="task-info">
        <div class="task-title">${escHtml(task.title)}</div>
        <div class="task-meta">
          <div class="priority-dot ${task.priority}" aria-hidden="true"></div>
          <span>${task.priority}</span>
          ${task.category ? `<span>• ${escHtml(task.category)}</span>` : ''}
          ${task.due_date ? `<span>• Due: ${formatDate(task.due_date)}</span>` : ''}
          ${task.relative_deadline ? `<span>• ${escHtml(task.relative_deadline)}</span>` : ''}
          ${task.is_overdue ? `<span class="overdue-badge" role="status">⚠️ Overdue</span>` : ''}
        </div>
        ${task.description ? `<div style="font-size:.8rem;color:var(--text-muted);margin-top:4px">${escHtml(task.description)}</div>` : ''}
      </div>
      <div class="task-actions">
        <button class="btn btn-icon btn-secondary btn-sm" onclick="openEditTaskModal(${task.id})" aria-label="Edit task ${escHtml(task.title)}" title="Edit">
          ${icon('edit')}
        </button>
        <button class="btn btn-icon btn-danger btn-sm" onclick="deleteTask(${task.id})" aria-label="Delete task ${escHtml(task.title)}" title="Delete">
          ${icon('trash')}
        </button>
      </div>
    </div>`;
}

async function toggleTask(taskId, currentStatus) {
  const newStatus = currentStatus === 'completed' ? 'pending' : 'completed';
  try {
    await apiFetch(`/tasks/${taskId}`, { method: 'PUT', body: { status: newStatus } });
    loadTasksPage();
  } catch (e) {
    showToast('Failed to update task: ' + e.message, 'error');
  }
}

function openEditTaskModal(taskId) {
  const allTasks = [...document.querySelectorAll('[id^="task-"]')];
  // We'll reload tasks state from API by refetching
  apiFetch(`/events/${state.currentEvent.id}/tasks`).then(data => {
    const task = data.data.find(t => t.id === taskId);
    if (!task) return;
    document.getElementById('editTaskId').value = task.id;
    document.getElementById('editTaskTitle').value = task.title;
    document.getElementById('editTaskDesc').value = task.description || '';
    document.getElementById('editTaskPriority').value = task.priority;
    document.getElementById('editTaskStatus').value = task.status;
    document.getElementById('editTaskDueDate').value = task.due_date || '';
    openModal('editTaskModal');
  });
}

async function saveEditTask() {
  const taskId = document.getElementById('editTaskId').value;
  const payload = {
    title: document.getElementById('editTaskTitle').value.trim(),
    description: document.getElementById('editTaskDesc').value.trim(),
    priority: document.getElementById('editTaskPriority').value,
    status: document.getElementById('editTaskStatus').value,
    due_date: document.getElementById('editTaskDueDate').value || null,
  };
  try {
    await apiFetch(`/tasks/${taskId}`, { method: 'PUT', body: payload });
    closeModal('editTaskModal');
    showToast('Task updated!', 'success');
    loadTasksPage();
  } catch (e) {
    showToast('Failed to update task: ' + e.message, 'error');
  }
}

async function deleteTask(taskId) {
  if (!confirm('Delete this task?')) return;
  try {
    await apiFetch(`/tasks/${taskId}`, { method: 'DELETE' });
    showToast('Task deleted.', 'success');
    loadTasksPage();
  } catch (e) {
    showToast('Failed to delete task: ' + e.message, 'error');
  }
}

function openAddTaskModal() {
  document.getElementById('addTaskForm').reset();
  openModal('addTaskModal');
}

async function saveNewTask() {
  const title = document.getElementById('newTaskTitle').value.trim();
  if (!title) { showToast('Task title is required', 'warning'); return; }

  const payload = {
    title,
    description: document.getElementById('newTaskDesc').value.trim(),
    priority: document.getElementById('newTaskPriority').value,
    due_date: document.getElementById('newTaskDueDate').value || null,
    category: document.getElementById('newTaskCategory').value.trim(),
  };

  try {
    await apiFetch(`/events/${state.currentEvent.id}/tasks`, { method: 'POST', body: payload });
    closeModal('addTaskModal');
    showToast('Task added!', 'success');
    loadTasksPage();
  } catch (e) {
    showToast('Failed to add task: ' + e.message, 'error');
  }
}

// ── Chat Page ────────────────────────────────────────────────────────────────
async function loadChatPage() {
  if (!state.currentEvent) return;
  document.getElementById('chatEventName').textContent = state.currentEvent.name;
  document.getElementById('chatEventType').textContent = state.currentEvent.event_type;

  // Load existing messages
  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}`);
    const event = data.data;
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';

    // Show welcome if no messages
    const hasMessages = false; // we load from chat history separately
    addWelcomeMessage();
  } catch (e) {
    console.error('Failed to load chat:', e);
  }
}

function addWelcomeMessage() {
  if (!state.currentEvent) return;
  const chatMessages = document.getElementById('chatMessages');
  const welcomeText = `Hello! I'm EventGenie AI, your personal event planning assistant. I'm ready to help you plan the perfect **${state.currentEvent.event_type}** event — ${state.currentEvent.name}!

Here's what I can help you with:
• Generate creative theme ideas
• Refine your budget allocation
• Suggest vendors and services
• Create custom checklists
• Answer any event planning questions

What would you like to work on first?`;

  appendMessage('assistant', welcomeText);
}

function appendMessage(role, content) {
  const chatMessages = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  const avatar = role === 'user'
    ? `<div class="chat-avatar user-av">👤</div>`
    : `<div class="chat-avatar ai-av">✨</div>`;
  const bubble = `<div class="chat-bubble">${markdownToHtml(content)}</div>`;
  div.innerHTML = role === 'user' ? `${bubble}${avatar}` : `${avatar}${bubble}`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
  const chatMessages = document.getElementById('chatMessages');
  const typing = document.createElement('div');
  typing.id = 'typingIndicator';
  typing.className = 'chat-message assistant';
  typing.innerHTML = `
    <div class="chat-avatar ai-av">✨</div>
    <div class="chat-bubble" style="padding:14px 18px">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>`;
  chatMessages.appendChild(typing);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  document.getElementById('typingIndicator')?.remove();
}

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message || !state.currentEvent) return;

  input.value = '';
  input.style.height = 'auto';
  appendMessage('user', message);
  showTypingIndicator();

  const sendBtn = document.getElementById('chatSendBtn');
  sendBtn.disabled = true;

  try {
    const data = await apiFetch(`/events/${state.currentEvent.id}/chat`, {
      method: 'POST', body: { message },
    });
    removeTypingIndicator();
    appendMessage('assistant', data.data.message);
  } catch (e) {
    removeTypingIndicator();
    appendMessage('assistant', `I'm sorry, I encountered an error: ${e.message}. Please try again.`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// ── Modal Helpers (Accessible Focus Management) ─────────────────────────────
let lastFocusedElement = null;

function openModal(id) {
  lastFocusedElement = document.activeElement;
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  // Set focus to first input or interactive element inside modal
  setTimeout(() => {
    const focusable = modal.querySelectorAll('button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable.length > 0) {
      focusable[0].focus();
    }
  }, 50);
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove('open');
  document.body.style.overflow = '';
  if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
    lastFocusedElement.focus();
  }
}

// Global Escape key listener to dismiss open modals
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const openModals = document.querySelectorAll('.modal-overlay.open');
    if (openModals.length > 0) {
      openModals.forEach(m => m.classList.remove('open'));
      document.body.style.overflow = '';
      if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
        lastFocusedElement.focus();
      }
    }
  }
});

// ── Formatting Helpers ───────────────────────────────────────────────────────
function formatCurrency(amount) {
  if (!amount && amount !== 0) return '—';
  return '₹' + Number(amount).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function daysUntil(dateStr) {
  if (!dateStr) return '';
  const diff = Math.ceil((new Date(dateStr + 'T00:00:00') - new Date()) / 86400000);
  if (diff < 0) return 'Past';
  if (diff === 0) return 'Today!';
  if (diff === 1) return '1 day away';
  return `${diff} days away`;
}

function daysUntilTag(dateStr) {
  const text = daysUntil(dateStr);
  if (!text) return '';
  return `<span style="font-size:.72rem;color:var(--primary);font-weight:600;margin-left:4px">${text}</span>`;
}

function eventEmoji(type) {
  const emojis = { wedding: '💍', birthday: '🎂', college: '🎓', community: '🏘️', custom: '🎉' };
  return emojis[type] || '🎉';
}

function eventTypeColor(type) {
  const colors = { wedding: 'purple', birthday: 'orange', college: 'green', community: 'cyan', custom: 'purple' };
  return colors[type] || 'purple';
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;',
  };
  return String(str).replace(/[&<>"'/]/g, s => map[s]);
}

function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
}

function markdownToHtml(text) {
  if (!text) return '';
  return escHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code style="background:var(--gray-100);padding:2px 6px;border-radius:4px;font-size:.85em">$1</code>')
    .replace(/^• (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>')
    .replace(/\n/g, '<br>');
}

// ── SVG Icons (Lucide subset) ────────────────────────────────────────────────
function icon(name) {
  const icons = {
    'plus': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    'calendar': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    'users': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'indian-rupee': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12"/><path d="M6 8h12"/><path d="M6 13l8.5 8"/><path d="M6 13h3a4 4 0 0 0 0-8H6"/></svg>',
    'map-pin': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    'arrow-right': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    'sparkles': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L19.5 12l-5.6 1.9L12 21l-1.9-5.7L4.5 12l5.6-1.9L12 3z"/></svg>',
    'message-circle': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    'pie-chart': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>',
    'check-square': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    'check-circle': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    'check': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    'edit': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    'trash': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>',
    'refresh-cw': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    'clock': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    'star': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    'zap': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    'lightbulb': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="9" y1="18" x2="15" y2="18"/><line x1="10" y1="22" x2="14" y2="22"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>',
    'palette': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c1.85 0 3-1.15 3-3 0-1.15-.4-2.3-1.15-3.15-.3-.35-.15-.85.35-.85H18c2.75 0 4-1.25 4-4C22 6.48 17.52 2 12 2z"/></svg>',
    'droplet': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>',
    'utensils': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="2" x2="3" y2="22"/><path d="M7 2l0 8a5 5 0 0 1-4 5v5"/><path d="M21 15V2v0a5 5 0 0 0-5 5v6h4l-1 1.1a2 2 0 0 0-.5 1.3l.5 2.6"/></svg>',
    'music': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
    'piggy-bank': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2z"/><path d="M2 9v1a2 2 0 0 0 2 2h1"/><path d="M16 11h.01"/></svg>',
    'briefcase': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    'list-checks': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><polyline points="3 6 4 7 6 5"/><polyline points="3 12 4 13 6 11"/><polyline points="3 18 4 19 6 17"/></svg>',
    'user': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    'home': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    'settings': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    'send': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    'x': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    'menu': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
  };
  return icons[name] || '';
}

// ── Settings Page ────────────────────────────────────────────────────────────
async function saveSettings() {
  showToast('Settings saved! (Restart server to apply API key changes)', 'info');
}

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Check health
  checkApiHealth();

  // Init create event form
  initCreateEventForm();

  // Chat input enter key
  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });
  }

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('open');
        document.body.style.overflow = '';
      }
    });
  });

  // Mobile sidebar overlay close
  document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const menuBtn = document.querySelector('.menu-btn');
    if (sidebar && sidebar.classList.contains('mobile-open') &&
        !sidebar.contains(e.target) && (!menuBtn || !menuBtn.contains(e.target))) {
      closeMobileSidebar();
    }
  });

  // Periodic health check
  setInterval(checkApiHealth, 30000);
});
