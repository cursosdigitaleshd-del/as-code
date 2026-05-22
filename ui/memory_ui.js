/**
 * AS Code — Working Memory UI  (v1.0.0)
 *
 * Event-driven. NO polling — Working Memory changes infrequently.
 * Refresh triggers: drawer open, after any write/delete/reset.
 *
 * Public API (used by app.js):
 *   window.memoryUI.getSessionId()   → string
 *   window.memoryUI.setSessionId(id) → void
 *   window.memoryUI.addObservation(content, source) → Promise
 */

console.log('[MEMORY] module loaded ✓');

// ── Source config ─────────────────────────────────────────────
const SOURCE_COLORS = {
    user:       { bg: 'rgba(99,179,237,0.12)',  border: 'rgba(99,179,237,0.3)',  text: '#63b3ed' },
    system:     { bg: 'rgba(154,117,243,0.12)', border: 'rgba(154,117,243,0.3)', text: '#9a75f3' },
    rag:        { bg: 'rgba(72,187,120,0.12)',  border: 'rgba(72,187,120,0.3)',  text: '#48bb78' },
    capability: { bg: 'rgba(237,137,54,0.12)',  border: 'rgba(237,137,54,0.3)',  text: '#ed8936' },
};

const STATUS_CONFIG = {
    pending:     { icon: '○', class: 'task-pending',     label: 'Pending' },
    in_progress: { icon: '◑', class: 'task-in-progress', label: 'In Progress' },
    completed:   { icon: '●', class: 'task-completed',   label: 'Done' },
    failed:      { icon: '✕', class: 'task-failed',      label: 'Failed' },
};

const STATUS_CYCLE = ['pending', 'in_progress', 'completed', 'failed'];

// ─────────────────────────────────────────────────────────────
class MemoryUI {
    constructor() {
        this._sessionId = 'default_session';
        this._data = { variables: [], tasks: [], observations: [] };

        // DOM refs — resolved in init()
        this.drawer     = null;
        this.overlay    = null;
        this.toggleBtn  = null;
        this.closeBtn   = null;
        this.content    = null;

        console.log('[MEMORY] MemoryUI instance created');
    }

    // ── Initialization ──────────────────────────────────────────
    init() {
        console.log('[MEMORY] init() called — resolving DOM elements...');

        this.drawer    = document.getElementById('memoryDrawer');
        this.overlay   = document.getElementById('memoryOverlay');
        this.toggleBtn = document.getElementById('toggleMemory');
        this.closeBtn  = document.getElementById('closeMemory');
        this.content   = document.getElementById('memoryContent');

        if (!this.drawer || !this.toggleBtn) {
            console.error('[MEMORY] ❌ #memoryDrawer or #toggleMemory not found — init aborted');
            return;
        }

        this.toggleBtn.addEventListener('click', () => this.toggleDrawer());
        this.closeBtn?.addEventListener('click', () => this.closeDrawer());
        this.overlay?.addEventListener('click', () => this.closeDrawer());

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.drawer && !this.drawer.classList.contains('hidden')) {
                this.closeDrawer();
            }
        });

        console.log('[MEMORY] initialized ✓');
    }

    // ── Session ─────────────────────────────────────────────────
    getSessionId() { return this._sessionId; }
    setSessionId(id) {
        this._sessionId = id || 'default_session';
        if (this.drawer && !this.drawer.classList.contains('hidden')) {
            this.refresh(); // Reload for the new session
        }
    }

    // ── Drawer ──────────────────────────────────────────────────
    toggleDrawer() {
        const isOpen = this.drawer && !this.drawer.classList.contains('hidden');
        isOpen ? this.closeDrawer() : this.openDrawer();
    }

    openDrawer() {
        if (!this.drawer) return;
        this.drawer.classList.remove('hidden');
        this.toggleBtn?.classList.add('active');
        this.refresh(); // Single fetch on open — not repeated
    }

    closeDrawer() {
        if (!this.drawer) return;
        this.drawer.classList.add('hidden');
        this.toggleBtn?.classList.remove('active');
    }

    // ── Fetch ───────────────────────────────────────────────────
    async refresh() {
        if (!this.content) return;
        this.content.innerHTML = '<div class="loading-spinner">Loading memory...</div>';

        try {
            const res = await fetch(`/v1/memory?session_id=${encodeURIComponent(this._sessionId)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this._data = await res.json();
            this._render();
        } catch (err) {
            console.error('[MEMORY] fetch failed:', err);
            this.content.innerHTML = `
                <div style="padding:1.5rem;text-align:center;color:rgba(225,229,235,0.35);font-size:0.8rem;">
                    <div style="font-size:1.5rem;margin-bottom:0.5rem;">⚠️</div>
                    Failed to load working memory<br>
                    <span style="font-size:0.7rem;opacity:0.6;">${err.message}</span>
                </div>`;
        }
    }

    // ── Render ──────────────────────────────────────────────────
    _render() {
        if (!this.content) return;
        const { variables, tasks, observations } = this._data;

        this.content.innerHTML = '';
        
        // Render Workflow panel first
        const wfSection = this._buildWorkflowSection(variables);
        if (wfSection) {
            this.content.appendChild(wfSection);
        }

        // Filter out wf_* internal workflow variables from the user variables list
        const userVars = variables.filter(v => !v.key.startsWith('wf_'));

        this.content.appendChild(this._buildVariablesSection(userVars));
        this.content.appendChild(this._buildTasksSection(tasks));
        this.content.appendChild(this._buildObservationsSection(observations));
        this.content.appendChild(this._buildResetSection());
    }

    // ── Variables Section ───────────────────────────────────────
    _buildVariablesSection(variables) {
        const wrap = document.createElement('div');
        wrap.className = 'memory-section';

        const header = this._sectionHeader('Variables', `${variables.length}`);
        wrap.appendChild(header);

        if (variables.length > 0) {
            const list = document.createElement('div');
            list.className = 'memory-variable-list';
            variables.forEach(v => list.appendChild(this._variableChip(v)));
            wrap.appendChild(list);
        }

        // Add variable form
        const form = document.createElement('div');
        form.className = 'memory-add-row';
        form.innerHTML = `
            <input id="mem-var-key" class="memory-input" type="text" placeholder="key" style="flex:1;min-width:0;">
            <input id="mem-var-val" class="memory-input" type="text" placeholder="value" style="flex:2;min-width:0;">
            <button class="memory-add-btn" onclick="window.memoryUI._addVariable()">+ Set</button>`;
        wrap.appendChild(form);

        return wrap;
    }

    _variableChip(v) {
        const chip = document.createElement('div');
        chip.className = 'memory-variable-chip';
        chip.innerHTML = `
            <span class="mem-var-key">${this._esc(v.key)}</span>
            <span class="mem-var-sep">→</span>
            <span class="mem-var-val">${this._esc(v.value)}</span>
            <button class="mem-delete-btn" onclick="window.memoryUI._deleteVariable('${this._esc(v.key)}')" title="Remove">×</button>`;
        return chip;
    }

    async _addVariable() {
        const key = document.getElementById('mem-var-key')?.value.trim();
        const val = document.getElementById('mem-var-val')?.value.trim();
        if (!key) return;
        await this._post('/v1/memory/variables', {
            session_id: this._sessionId, key, value: val || ''
        });
        document.getElementById('mem-var-key').value = '';
        document.getElementById('mem-var-val').value = '';
        await this.refresh(); // Event-driven refresh
    }

    async _deleteVariable(key) {
        await fetch(
            `/v1/memory/variables/${encodeURIComponent(key)}?session_id=${encodeURIComponent(this._sessionId)}`,
            { method: 'DELETE' }
        );
        await this.refresh();
    }

    // ── Tasks Section ───────────────────────────────────────────
    _buildTasksSection(tasks) {
        const wrap = document.createElement('div');
        wrap.className = 'memory-section';

        const active = tasks.filter(t => t.status !== 'completed' && t.status !== 'failed');
        const done   = tasks.filter(t => t.status === 'completed' || t.status === 'failed');

        wrap.appendChild(this._sectionHeader('Tasks', `${active.length} active`));

        const list = document.createElement('div');
        list.className = 'memory-task-list';

        [...active, ...done].forEach(t => list.appendChild(this._taskRow(t)));
        wrap.appendChild(list);

        // Add task form
        const form = document.createElement('div');
        form.className = 'memory-add-row';
        form.innerHTML = `
            <input id="mem-task-title" class="memory-input" type="text" placeholder="New task..." style="flex:3;min-width:0;">
            <input id="mem-task-prio" class="memory-input" type="number" placeholder="P" min="0" value="0" style="flex:0 0 50px;text-align:center;">
            <button class="memory-add-btn" onclick="window.memoryUI._addTask()">+ Add</button>`;
        wrap.appendChild(form);

        return wrap;
    }

    _taskRow(t) {
        const cfg  = STATUS_CONFIG[t.status] || STATUS_CONFIG.pending;
        const prio = t.priority > 0 ? `<span class="mem-prio-badge">P${t.priority}</span>` : '';

        const row = document.createElement('div');
        row.className = `memory-task-row ${cfg.class}`;
        row.innerHTML = `
            <button class="mem-status-btn" title="Cycle status"
                onclick="window.memoryUI._cycleTaskStatus('${t.id}', '${t.status}')">
                ${cfg.icon}
            </button>
            <span class="mem-task-title">${this._esc(t.title)}</span>
            ${prio}
            <button class="mem-delete-btn" onclick="window.memoryUI._deleteTask('${t.id}')" title="Remove">×</button>`;
        return row;
    }

    async _addTask() {
        const title = document.getElementById('mem-task-title')?.value.trim();
        const prio  = parseInt(document.getElementById('mem-task-prio')?.value || '0', 10);
        if (!title) return;
        await this._post('/v1/memory/tasks', {
            session_id: this._sessionId, title, priority: prio
        });
        document.getElementById('mem-task-title').value = '';
        document.getElementById('mem-task-prio').value  = '0';
        await this.refresh();
    }

    async _cycleTaskStatus(taskId, currentStatus) {
        const idx  = STATUS_CYCLE.indexOf(currentStatus);
        const next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
        await fetch(`/v1/memory/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: next }),
        });
        await this.refresh();
    }

    async _deleteTask(taskId) {
        await fetch(`/v1/memory/tasks/${taskId}`, { method: 'DELETE' });
        await this.refresh();
    }

    // ── Observations Section ────────────────────────────────────
    _buildObservationsSection(observations) {
        const wrap = document.createElement('div');
        wrap.className = 'memory-section';
        wrap.appendChild(this._sectionHeader('Observations', `${observations.length}`));

        const list = document.createElement('div');
        list.className = 'memory-obs-list';
        observations.forEach(o => list.appendChild(this._obsRow(o)));
        wrap.appendChild(list);

        // Add observation form
        const form = document.createElement('div');
        form.className = 'memory-add-col';
        form.innerHTML = `
            <div class="memory-add-row">
                <input id="mem-obs-text" class="memory-input" type="text"
                    placeholder="Add observation..." style="flex:1;min-width:0;">
                <select id="mem-obs-src" class="memory-select">
                    <option value="user">user</option>
                    <option value="system">system</option>
                    <option value="rag">rag</option>
                    <option value="capability">capability</option>
                </select>
                <button class="memory-add-btn" onclick="window.memoryUI._addObservation()">+ Add</button>
            </div>`;
        wrap.appendChild(form);

        return wrap;
    }

    _obsRow(o) {
        const colors = SOURCE_COLORS[o.source] || SOURCE_COLORS.user;
        const row = document.createElement('div');
        row.className = 'memory-obs-row';
        row.style.cssText = `
            background:${colors.bg};border:1px solid ${colors.border};
            border-radius:6px;padding:0.4rem 0.6rem;margin-bottom:0.3rem;
            display:flex;align-items:flex-start;gap:0.5rem;`;
        row.innerHTML = `
            <span style="color:${colors.text};font-size:0.65rem;font-family:'JetBrains Mono',monospace;
                white-space:nowrap;padding-top:2px;">[${this._esc(o.source)}]</span>
            <span style="flex:1;font-size:0.75rem;color:rgba(225,229,235,0.8);
                line-height:1.4;">${this._esc(o.content)}</span>
            <button class="mem-delete-btn"
                onclick="window.memoryUI._deleteObservation('${o.id}')" title="Remove">×</button>`;
        return row;
    }

    async addObservation(content, source = 'user') {
        // Public API — called by app.js or other modules
        await this._post('/v1/memory/observations', {
            session_id: this._sessionId, content, source
        });
        if (this.drawer && !this.drawer.classList.contains('hidden')) {
            await this.refresh();
        }
    }

    async _addObservation() {
        const content = document.getElementById('mem-obs-text')?.value.trim();
        const source  = document.getElementById('mem-obs-src')?.value || 'user';
        if (!content) return;
        await this.addObservation(content, source);
        document.getElementById('mem-obs-text').value = '';
    }

    async _deleteObservation(obsId) {
        await fetch(`/v1/memory/observations/${obsId}`, { method: 'DELETE' });
        await this.refresh();
    }

    // ── Reset Section ───────────────────────────────────────────
    _buildResetSection() {
        const wrap = document.createElement('div');
        wrap.className = 'memory-section memory-section--reset';
        wrap.innerHTML = `
            <button class="memory-reset-btn"
                onclick="window.memoryUI._confirmReset()">
                🗑 Clear Memory (${this._sessionId})
            </button>`;
        return wrap;
    }

    async _confirmReset() {
        if (!confirm(`Clear all working memory for session "${this._sessionId}"?`)) return;
        await this._post('/v1/memory/reset', { session_id: this._sessionId });
        await this.refresh();
    }

    // ── Helpers ─────────────────────────────────────────────────
    _sectionHeader(title, badge) {
        const tooltips = {
            'Variables': 'Hechos importantes persistentes del proyecto o conversación.',
            'Tasks': 'Pasos activos del workflow que el runtime utiliza para dar continuidad.',
            'Observations': 'Señales o insights relevantes detectados durante la interacción.',
            'Workflow': 'Estado de progreso y fase del workflow actual del coordinador.'
        };
        const tooltip = tooltips[title] || '';
        const hdr = document.createElement('div');
        hdr.className = 'memory-section-header';
        if (tooltip) {
            hdr.setAttribute('title', tooltip);
            hdr.style.cursor = 'help';
        }
        hdr.innerHTML = `
            <span class="memory-section-title">${title}</span>
            <span class="memory-section-badge">${badge}</span>`;
        return hdr;
    }

    async _post(url, body) {
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                console.error(`[MEMORY] POST ${url} failed:`, err.detail);
            }
        } catch (err) {
            console.error(`[MEMORY] POST ${url} error:`, err);
        }
    }

    _esc(str) {
        return String(str ?? '')
            .replace(/&/g,'&amp;').replace(/</g,'&lt;')
            .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ── Workflow & Suggestions Panel (Phase 2 Coordinator) ──────
    _buildWorkflowSection(variables) {
        const vmap = {};
        variables.forEach(v => { vmap[v.key] = v.value; });

        const objective = vmap['wf_objective'];
        const phase = vmap['wf_phase'];
        const focus = vmap['wf_focus'];
        const suggestionsStr = vmap['wf_suggestions'] || '';

        if (!objective && !phase && !focus && !suggestionsStr) {
            return null;
        }

        const wrap = document.createElement('div');
        wrap.className = 'memory-section';
        wrap.style.cssText = `
            background: linear-gradient(135deg, rgba(110, 168, 254, 0.08) 0%, rgba(167, 139, 250, 0.08) 100%);
            border: 1px solid rgba(110, 168, 254, 0.18);
            border-radius: 8px;
            padding: 0.85rem;
            margin-bottom: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
        `;

        // 1. Workflow Objective & Phase Badge
        const titleText = objective ? `🧠 Workflow: ${this._esc(objective)}` : '🧠 Active Workflow';
        const phaseBadge = phase ? `<span style="background: rgba(167, 139, 250, 0.2); color: #c084fc; padding: 2px 7px; border-radius: 12px; font-size: 0.65rem; font-weight: 650; text-transform: uppercase; font-family: monospace;">${this._esc(phase)}</span>` : '';
        
        const header = document.createElement('div');
        header.style.cssText = 'display: flex; align-items: center; justify-content: space-between; font-weight: 600; color: #6ea8fe; font-size: 0.8rem;';
        header.innerHTML = `<span>${titleText}</span> ${phaseBadge}`;
        wrap.appendChild(header);

        // 2. Current Focus
        if (focus) {
            const focusDiv = document.createElement('div');
            focusDiv.style.cssText = 'font-size: 0.75rem; color: rgba(225, 229, 235, 0.8); line-height: 1.4;';
            focusDiv.innerHTML = `<span style="color: rgba(225, 229, 235, 0.45); font-weight: 500;">Current Focus:</span> ${this._esc(focus)}`;
            wrap.appendChild(focusDiv);
        }

        // 3. Suggested Skills
        if (suggestionsStr) {
            const suggestions = suggestionsStr.split(',').filter(Boolean);
            if (suggestions.length > 0) {
                const suggDiv = document.createElement('div');
                suggDiv.style.cssText = 'display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.2rem;';
                
                const skillEmojiMap = {
                    marketing: '📈 Marketing',
                    sales: '📞 Sales',
                    business: '💼 Business',
                    legal: '⚖️ Legal',
                    content_creator: '🎬 Content Creator'
                };

                const chipsHtml = suggestions.map(s => {
                    const label = skillEmojiMap[s] || `✨ ${s}`;
                    return `
                        <button class="skill-sugg-chip" 
                            style="background: rgba(110, 168, 254, 0.08); border: 1px solid rgba(110, 168, 254, 0.25); color: #9ec5fe; padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; cursor: pointer; transition: all 0.2s;"
                            onclick="window.memoryUI._activateSuggestedSkill('${this._esc(s)}')">
                            ${label}
                        </button>
                    `;
                }).join(' ');

                suggDiv.innerHTML = `
                    <div style="font-size: 0.65rem; color: rgba(225, 229, 235, 0.45); font-weight: 500;">Suggested Skills:</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">${chipsHtml}</div>
                `;
                wrap.appendChild(suggDiv);
            }
        }

        return wrap;
    }

    _activateSuggestedSkill(skillId) {
        if (window.skillsUI) {
            console.log('[MEMORY-COORDINATOR] Activating suggested skill:', skillId);
            window.skillsUI.activateSkill(skillId);
            this.refresh();
        } else {
            console.warn('[MEMORY-COORDINATOR] skillsUI module not available');
        }
    }
}

// ── Self-initialize ────────────────────────────────────────────
window.memoryUI = new MemoryUI();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('[MEMORY] DOMContentLoaded fired — calling init()');
        window.memoryUI.init();
    });
} else {
    console.log('[MEMORY] DOM already ready — calling init() immediately');
    window.memoryUI.init();
}
