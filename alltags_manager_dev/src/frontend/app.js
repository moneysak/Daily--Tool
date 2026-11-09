document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-item');
    const mainContent = document.getElementById('main-content');

    // Dynamischer Ingress- & API-Pfad
    function getApiBaseUrl() {
        if (window.APP_CONFIG && typeof window.APP_CONFIG.API_BASE_URL === 'string') {
            return window.APP_CONFIG.API_BASE_URL.replace(/\/+$/, '');
        }
        // Fallback: Ermittlung über aktuellen Pfad (wenn z.B. /api/hassio_ingress/<token>/...)
        const path = window.location.pathname;
        if (path.includes('/api/hassio_ingress/')) {
            const parts = path.split('/api/hassio_ingress/');
            const sub = parts[1].split('/')[0];
            return `/api/hassio_ingress/${sub}`;
        }
        return '';
    }

    const apiBaseUrl = getApiBaseUrl();
    let authToken = sessionStorage.getItem('alltags_manager_token') || "";

    function getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
            headers['X-Auth-Token'] = authToken;
        }
        return headers;
    }

    // --- Tab Contents (HTML Templates) ---
    const contentMap = {
        'today': `
            <div class="content-header">
                <h1 class="greeting" id="today-greeting">Willkommen</h1>
                <p class="subtitle" id="today-date"></p>
            </div>
            <div class="progress-card glass-panel">
                <div class="progress-head">
                    <span>Fortschritt heute</span>
                    <span id="progress-text">0 von 0 erledigt</span>
                </div>
                <div class="progress-track" id="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-label="Tagesfortschritt">
                    <div class="progress-fill" id="progress-fill" style="width: 0%;"></div>
                </div>
            </div>
            <div id="today-sections" class="today-sections"></div>
            <div id="shopping-card-slot"></div>
        `,
        'tasks': `
            <div class="content-header">
                <h1>✓ Aufgaben</h1>
                <p class="subtitle">Persönliche To-Dos verwalten</p>
            </div>
            <div class="input-card glass-panel flex-row">
                <input type="text" id="new-task-title" placeholder="Neue Aufgabe hinzufügen..." class="app-input flex-2">
                <input type="date" id="new-task-due" class="app-input flex-1" title="Fälligkeitsdatum (optional)">
                <button id="add-task-btn" class="app-btn-accent">Hinzufügen</button>
            </div>
            <div class="list-wrapper">
                <ul id="task-list" class="app-list"></ul>
            </div>
        `,
        'shopping': `
            <div class="content-header">
                <h1>🛒 Einkaufsliste</h1>
                <p class="subtitle">Artikel und Mengen planen</p>
            </div>
            <div class="input-card glass-panel flex-row">
                <input type="text" id="new-shop-item" placeholder="Artikel (z. B. Hafermilch)..." class="app-input flex-2">
                <input type="text" id="new-shop-qty" placeholder="Menge (z. B. 2x)" class="app-input flex-1">
                <button id="add-shop-btn" class="app-btn-accent">Hinzufügen</button>
            </div>
            <div class="list-controls">
                <button id="clear-checked-shop-btn" class="app-btn-secondary">Erledigte entfernen</button>
            </div>
            <div class="list-wrapper">
                <ul id="shopping-list" class="app-list"></ul>
            </div>
        `,
        'routines': `
            <div class="content-header">
                <h1>↻ Routinen</h1>
                <p class="subtitle">Wiederkehrende Gewohnheiten</p>
            </div>
            <div class="input-card glass-panel flex-row">
                <input type="text" id="new-routine-title" placeholder="Routine (z. B. Morgen-Meditation)..." class="app-input flex-2">
                <select id="new-routine-frequency" class="app-input flex-1" title="Häufigkeit">
                    <option value="daily">Täglich</option>
                    <option value="weekly">Wöchentlich</option>
                </select>
                <button id="add-routine-btn" class="app-btn-accent">Anlegen</button>
            </div>
            <div id="weekday-chips" class="weekday-chips" style="display: none;"></div>
            <div class="list-wrapper">
                <ul id="routines-list" class="app-list"></ul>
            </div>
        `,
        'chat': `
            <div class="content-header">
                <h1>💬 Hermes Assistent</h1>
                <p class="subtitle">Direkter KI-Dialog im Alltag</p>
            </div>
            <div id="chat-container" class="glass-panel chat-box">
                <div id="chat-messages" class="chat-messages-area">
                    <div class="chat-bubble hermes">Hallo! Wie kann ich dich heute bei Aufgaben, Einkäufen oder Routinen unterstützen?</div>
                </div>
                <div class="chat-input-row">
                    <input type="text" id="chat-input" placeholder="Nachricht an Hermes..." class="app-input chat-input-field">
                    <button id="send-chat-btn" class="app-btn-accent">Senden</button>
                </div>
            </div>
        `
    };

    // --- Authentifizierung ---
    function setLogoutVisible(visible) {
        const btn = document.getElementById('logout-btn');
        if (btn) btn.style.display = visible ? 'block' : 'none';
    }

    // Bei 401: Token verwerfen und Login-Maske zeigen (statt leerer Seite).
    function handleUnauthorized() {
        authToken = "";
        try { sessionStorage.removeItem('alltags_manager_token'); } catch (e) {}
        setLogoutVisible(false);
        showAuthModal();
        return false;
    }

    async function checkAuth() {
        try {
            const response = await fetch(`${apiBaseUrl}/api/auth/status`, {
                headers: getAuthHeaders()
            });
            if (response.status === 401) {
                return handleUnauthorized();
            }
            hideAuthModal();
            setLogoutVisible(!!authToken);
            return true;
        } catch (e) {
            console.error("Auth check failed:", e);
            return true;
        }
    }

    function showAuthModal() {
        const modal = document.getElementById('auth-modal');
        if (modal) modal.style.display = 'flex';
    }

    function hideAuthModal() {
        const modal = document.getElementById('auth-modal');
        if (modal) modal.style.display = 'none';
    }

    const loginBtn = document.getElementById('auth-login-btn');
    const pwInput = document.getElementById('auth-password-input');
    const errorMsg = document.getElementById('auth-error-msg');

    if (loginBtn && pwInput) {
        async function doLogin() {
            const password = pwInput.value.trim();
            if (!password) return;
            try {
                const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password })
                });
                if (!response.ok) {
                    if (errorMsg) errorMsg.style.display = 'block';
                    return;
                }
                const data = await response.json();
                authToken = data.token;
                sessionStorage.setItem('alltags_manager_token', authToken);
                hideAuthModal();
                setLogoutVisible(!!authToken);
                if (errorMsg) errorMsg.style.display = 'none';
                renderActiveTab();
            } catch (err) {
                if (errorMsg) {
                    errorMsg.textContent = "Verbindungsfehler";
                    errorMsg.style.display = 'block';
                }
            }
        }
        loginBtn.addEventListener('click', doLogin);
        pwInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') doLogin();
        });
    }

    // Logout: Token am Server widerrufen, lokal verwerfen, Login-Maske zeigen.
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                if (authToken) {
                    await fetch(`${apiBaseUrl}/api/auth/logout`, {
                        method: 'POST',
                        headers: getAuthHeaders()
                    });
                }
            } catch (err) {
                console.error('Logout failed:', err);
            }
            handleUnauthorized();
        });
    }

    // ==========================================
    // 1. TASKS LOGIC
    // ==========================================
    async function loadTasks() {
        try {
            const response = await fetch(`${apiBaseUrl}/tasks/`, { headers: getAuthHeaders() });
            if (response.status === 401) return handleUnauthorized();
            if (!response.ok) throw new Error('Tasks load failed');
            const tasks = await response.json();
            renderTasks(tasks);
        } catch (error) {
            console.error('Error loading tasks:', error);
            const list = document.getElementById('task-list');
            if (list) list.innerHTML = '<li class="list-msg">Konnte Aufgaben nicht laden.</li>';
        }
    }

    async function addTask(title, dueDate) {
        try {
            const payload = { title, completed: false };
            if (dueDate) payload.due_date = dueDate;
            const response = await fetch(`${apiBaseUrl}/tasks/`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            if (response.status === 401) return handleUnauthorized();
            loadTasks();
        } catch (error) {
            console.error('Error adding task:', error);
        }
    }

    async function toggleTask(id, currentStatus) {
        try {
            await fetch(`${apiBaseUrl}/tasks/${id}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ completed: !currentStatus })
            });
            loadTasks();
        } catch (error) {
            console.error('Error updating task:', error);
        }
    }

    async function deleteTask(id) {
        try {
            await fetch(`${apiBaseUrl}/tasks/${id}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            loadTasks();
        } catch (error) {
            console.error('Error deleting task:', error);
        }
    }

    function renderTasks(tasks) {
        const list = document.getElementById('task-list');
        if (!list) return;
        list.innerHTML = '';
        if (tasks.length === 0) {
            list.innerHTML = '<li class="list-msg empty">Keine offenen Aufgaben. Gut gemacht! ✨</li>';
            return;
        }
        tasks.forEach(task => {
            const li = document.createElement('li');
            li.className = `list-item ${task.completed ? 'is-completed' : ''}`;
            const dueBadge = task.due_date
                ? `<span class="badge ${isOverdue(task.due_date) ? 'overdue-badge' : ''}">${escapeHtml(formatDueLabel(task.due_date))}</span>`
                : '';
            li.innerHTML = `
                <label class="item-left">
                    <input type="checkbox" class="task-checkbox" data-id="${task.id}" ${task.completed ? 'checked' : ''}>
                    <span class="item-text">${escapeHtml(task.title)}</span>
                    ${dueBadge}
                </label>
                <button class="delete-btn" data-id="${task.id}" title="Löschen">✕</button>
            `;
            list.appendChild(li);
        });

        list.querySelectorAll('.task-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                const completed = !e.target.checked;
                toggleTask(id, completed);
            });
        });

        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                deleteTask(id);
            });
        });
    }

    function attachTaskListeners() {
        const addBtn = document.getElementById('add-task-btn');
        const input = document.getElementById('new-task-title');
        const dueInput = document.getElementById('new-task-due');
        if (addBtn && input) {
            const handleAdd = () => {
                const val = input.value.trim();
                if (val) {
                    addTask(val, dueInput ? dueInput.value : '');
                    input.value = '';
                    if (dueInput) dueInput.value = '';
                }
            };
            addBtn.addEventListener('click', handleAdd);
            input.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleAdd(); });
        }
    }

    // ==========================================
    // 2. SHOPPING LIST LOGIC
    // ==========================================
    async function loadShopping() {
        try {
            const response = await fetch(`${apiBaseUrl}/api/shopping/`, { headers: getAuthHeaders() });
            if (response.status === 401) return handleUnauthorized();
            if (!response.ok) throw new Error('Shopping load failed');
            const items = await response.json();
            renderShopping(items);
        } catch (error) {
            console.error('Error loading shopping items:', error);
            const list = document.getElementById('shopping-list');
            if (list) list.innerHTML = '<li class="list-msg">Konnte Einkaufsliste nicht laden.</li>';
        }
    }

    async function addShoppingItem(name, quantity) {
        try {
            await fetch(`${apiBaseUrl}/api/shopping/`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ name, quantity: quantity || "1", checked: false })
            });
            loadShopping();
        } catch (error) {
            console.error('Error adding shopping item:', error);
        }
    }

    async function toggleShoppingItem(id, currentStatus) {
        try {
            await fetch(`${apiBaseUrl}/api/shopping/${id}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ checked: !currentStatus })
            });
            loadShopping();
        } catch (error) {
            console.error('Error updating item:', error);
        }
    }

    async function deleteShoppingItem(id) {
        try {
            await fetch(`${apiBaseUrl}/api/shopping/${id}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            loadShopping();
        } catch (error) {
            console.error('Error deleting item:', error);
        }
    }

    async function clearCheckedShopping() {
        try {
            await fetch(`${apiBaseUrl}/api/shopping/clear-checked`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            loadShopping();
        } catch (error) {
            console.error('Error clearing checked:', error);
        }
    }

    function renderShopping(items) {
        const list = document.getElementById('shopping-list');
        if (!list) return;
        list.innerHTML = '';
        if (items.length === 0) {
            list.innerHTML = '<li class="list-msg empty">Einkaufsliste ist leer. 🍏</li>';
            return;
        }
        items.forEach(item => {
            const li = document.createElement('li');
            li.className = `list-item ${item.checked ? 'is-completed' : ''}`;
            li.innerHTML = `
                <label class="item-left">
                    <input type="checkbox" class="shop-checkbox" data-id="${item.id}" ${item.checked ? 'checked' : ''}>
                    <span class="item-text">${escapeHtml(item.name)}</span>
                    ${item.quantity ? `<span class="item-badge">${escapeHtml(item.quantity)}</span>` : ''}
                </label>
                <button class="delete-btn" data-id="${item.id}" title="Löschen">✕</button>
            `;
            list.appendChild(li);
        });

        list.querySelectorAll('.shop-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                const checked = !e.target.checked;
                toggleShoppingItem(id, checked);
            });
        });

        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                deleteShoppingItem(id);
            });
        });
    }

    function attachShoppingListeners() {
        const addBtn = document.getElementById('add-shop-btn');
        const nameInput = document.getElementById('new-shop-item');
        const qtyInput = document.getElementById('new-shop-qty');
        const clearBtn = document.getElementById('clear-checked-shop-btn');

        if (addBtn && nameInput) {
            const handleAdd = () => {
                const name = nameInput.value.trim();
                const qty = qtyInput ? qtyInput.value.trim() : "1";
                if (name) {
                    addShoppingItem(name, qty);
                    nameInput.value = '';
                    if (qtyInput) qtyInput.value = '';
                }
            };
            addBtn.addEventListener('click', handleAdd);
            nameInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleAdd(); });
            if (qtyInput) qtyInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleAdd(); });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', clearCheckedShopping);
        }
    }

    // ==========================================
    // 3. ROUTINES LOGIC
    // ==========================================
    async function loadRoutines() {
        try {
            const response = await fetch(`${apiBaseUrl}/api/routines/`, { headers: getAuthHeaders() });
            if (response.status === 401) return handleUnauthorized();
            if (!response.ok) throw new Error('Routines load failed');
            const routines = await response.json();
            renderRoutines(routines);
        } catch (error) {
            console.error('Error loading routines:', error);
            const list = document.getElementById('routines-list');
            if (list) list.innerHTML = '<li class="list-msg">Konnte Routinen nicht laden.</li>';
        }
    }

    async function addRoutine(title, frequency, weekdays) {
        try {
            const payload = { title, frequency: frequency || "daily", active: true, completed_today: false };
            if (payload.frequency === "weekly" && weekdays && weekdays.length) {
                payload.weekdays = weekdays;
            }
            await fetch(`${apiBaseUrl}/api/routines/`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            loadRoutines();
        } catch (error) {
            console.error('Error adding routine:', error);
        }
    }

    async function toggleRoutine(id, currentStatus) {
        try {
            await fetch(`${apiBaseUrl}/api/routines/${id}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ completed_today: !currentStatus })
            });
            loadRoutines();
        } catch (error) {
            console.error('Error updating routine:', error);
        }
    }

    async function deleteRoutine(id) {
        try {
            await fetch(`${apiBaseUrl}/api/routines/${id}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            loadRoutines();
        } catch (error) {
            console.error('Error deleting routine:', error);
        }
    }

    function renderRoutines(routines) {
        const list = document.getElementById('routines-list');
        if (!list) return;
        list.innerHTML = '';
        if (routines.length === 0) {
            list.innerHTML = '<li class="list-msg empty">Noch keine Routinen eingetragen. ☕</li>';
            return;
        }
        routines.forEach(rt => {
            const li = document.createElement('li');
            li.className = `list-item ${rt.completed_today ? 'is-completed' : ''}`;
            li.innerHTML = `
                <label class="item-left">
                    <input type="checkbox" class="routine-checkbox" data-id="${rt.id}" ${rt.completed_today ? 'checked' : ''}>
                    <span class="item-text">${escapeHtml(rt.title)}</span>
                    <span class="item-badge">${escapeHtml(routineScheduleLabel(rt))}</span>
                </label>
                <button class="delete-btn" data-id="${rt.id}" title="Löschen">✕</button>
            `;
            list.appendChild(li);
        });

        list.querySelectorAll('.routine-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                const done = !e.target.checked;
                toggleRoutine(id, done);
            });
        });

        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                deleteRoutine(id);
            });
        });
    }

    const WEEKDAY_LABELS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

    function buildWeekdayChips() {
        const container = document.getElementById('weekday-chips');
        if (!container) return;
        container.innerHTML = WEEKDAY_LABELS.map((label, day) =>
            `<button type="button" class="weekday-chip" data-day="${day}">${label}</button>`
        ).join('');
        container.querySelectorAll('.weekday-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                chip.classList.toggle('selected');
            });
        });
    }

    function attachRoutinesListeners() {
        const addBtn = document.getElementById('add-routine-btn');
        const input = document.getElementById('new-routine-title');
        const freqSelect = document.getElementById('new-routine-frequency');
        const chips = document.getElementById('weekday-chips');

        buildWeekdayChips();

        const syncChipsVisibility = () => {
            if (!chips || !freqSelect) return;
            chips.style.display = freqSelect.value === 'weekly' ? 'flex' : 'none';
        };
        if (freqSelect) {
            freqSelect.addEventListener('change', syncChipsVisibility);
            syncChipsVisibility();
        }

        if (addBtn && input) {
            const handleAdd = () => {
                const val = input.value.trim();
                if (!val) return;
                const frequency = freqSelect ? freqSelect.value : 'daily';
                let weekdays = [];
                if (frequency === 'weekly' && chips) {
                    weekdays = Array.from(chips.querySelectorAll('.weekday-chip.selected'))
                        .map(chip => parseInt(chip.getAttribute('data-day'), 10));
                }
                addRoutine(val, frequency, weekdays);
                input.value = '';
                if (chips) {
                    chips.querySelectorAll('.weekday-chip.selected').forEach(c => c.classList.remove('selected'));
                }
            };
            addBtn.addEventListener('click', handleAdd);
            input.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleAdd(); });
        }
    }

    // ==========================================
    // 4. HERMES CHAT LOGIC
    // ==========================================
    function attachChatListeners() {
        const sendBtn = document.getElementById('send-chat-btn');
        const input = document.getElementById('chat-input');
        const messagesDiv = document.getElementById('chat-messages');

        if (sendBtn && input && messagesDiv) {
            async function sendMessage() {
                const message = input.value.trim();
                if (!message) return;

                // User Nachricht anzeigen
                const userMsg = document.createElement('div');
                userMsg.className = 'chat-bubble user';
                userMsg.textContent = message;
                messagesDiv.appendChild(userMsg);

                input.value = '';
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                // Typing Indicator
                const typingMsg = document.createElement('div');
                typingMsg.className = 'chat-bubble hermes typing';
                typingMsg.textContent = 'Hermes tippt...';
                messagesDiv.appendChild(typingMsg);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                try {
                    const response = await fetch(`${apiBaseUrl}/api/hermes/chat`, {
                        method: 'POST',
                        headers: getAuthHeaders(),
                        body: JSON.stringify({ message: message })
                    });

                    typingMsg.remove();

                    if (response.status === 401) {
                        handleUnauthorized();
                        return;
                    }

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Fehler bei der Kommunikation mit Hermes.');
                    }

                    const data = await response.json();
                    const hermesMsg = document.createElement('div');
                    hermesMsg.className = 'chat-bubble hermes';
                    hermesMsg.textContent = data.message || "Antwort erhalten.";
                    messagesDiv.appendChild(hermesMsg);

                } catch (error) {
                    if (typingMsg) typingMsg.remove();
                    const errorBubble = document.createElement('div');
                    errorBubble.className = 'chat-bubble system-error';
                    errorBubble.textContent = `Fehler: ${error.message}`;
                    messagesDiv.appendChild(errorBubble);
                }
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }

            sendBtn.addEventListener('click', sendMessage);
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') sendMessage();
            });
        }
    }

    // ==========================================
    // 5. TODAY OVERVIEW LOGIC ("Heute")
    // ==========================================
    function localDateString(d = new Date()) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function formatLocalDate(d) {
        try {
            return d.toLocaleDateString('de-DE', {
                weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
            });
        } catch (e) {
            return localDateString(d);
        }
    }

    function isOverdue(dueDate) {
        return !!dueDate && dueDate < localDateString();
    }

    function formatDueLabel(dueDate) {
        if (!dueDate) return '';
        if (dueDate === localDateString()) return 'heute';
        return 'fällig ' + dueDate;
    }

    function routineScheduleLabel(routine) {
        const frequency = (routine.frequency || 'daily').toLowerCase();
        if (frequency === 'weekly') {
            const days = Array.isArray(routine.weekdays) ? routine.weekdays : [];
            if (days.length) {
                return days.map(d => WEEKDAY_LABELS[d] || '').filter(Boolean).join('/');
            }
            return 'wöchentlich';
        }
        return 'täglich';
    }

    // Reine Funktion: Begrüßung aus lokaler Stunde + optionalem Namen.
    function greetingFor(hour, name) {
        let base;
        if (hour >= 5 && hour <= 10) {
            base = 'Guten Morgen';
        } else if (hour >= 11 && hour <= 17) {
            base = 'Guten Tag';
        } else {
            base = 'Guten Abend';
        }
        const cleanName = (name || '').trim();
        return cleanName ? `${base}, ${cleanName}` : base;
    }

    async function loadOverview() {
        const today = localDateString();
        try {
            const response = await fetch(`${apiBaseUrl}/api/overview?today=${today}`, {
                headers: getAuthHeaders()
            });
            if (response.status === 401) return handleUnauthorized();
            if (!response.ok) throw new Error('Overview load failed');
            const overview = await response.json();
            renderTodaySections(overview);
            attachTodayListeners();
        } catch (error) {
            console.error('Error loading overview:', error);
            const sections = document.getElementById('today-sections');
            if (sections) sections.innerHTML = '<div class="list-msg">Konnte die Übersicht nicht laden.</div>';
        }
    }

    function renderTodaySections(overview) {
        const now = new Date();
        const tasks = overview.tasks || {};
        const routines = overview.routines || [];
        const progress = overview.progress || { done: 0, total: 0, percent: 0 };

        const greetingEl = document.getElementById('today-greeting');
        if (greetingEl) greetingEl.textContent = greetingFor(now.getHours(), overview.user_name);
        const dateEl = document.getElementById('today-date');
        if (dateEl) dateEl.textContent = formatLocalDate(now);

        const progressText = document.getElementById('progress-text');
        if (progressText) progressText.textContent = `${progress.done} von ${progress.total} erledigt`;
        const fill = document.getElementById('progress-fill');
        if (fill) fill.style.width = `${progress.percent}%`;
        const track = document.getElementById('progress-track');
        if (track) track.setAttribute('aria-valuenow', String(progress.percent));

        const sections = document.getElementById('today-sections');
        if (!sections) return;

        const taskRow = (task, cls) => `
            <li class="list-item ${task.completed ? 'is-completed' : ''} ${cls || ''}">
                <label class="item-left">
                    <input type="checkbox" class="overview-task-checkbox" data-id="${task.id}" ${task.completed ? 'checked' : ''}>
                    <span class="item-text">${escapeHtml(task.title)}</span>
                    ${task.is_overdue ? '<span class="badge overdue-badge">überfällig</span>' : ''}
                </label>
            </li>`;

        const taskSection = (title, items, cls) => {
            if (!items || items.length === 0) return '';
            return `
                <div class="today-block ${cls || ''}">
                    <h2 class="section-title">${escapeHtml(title)}</h2>
                    <ul class="app-list">${items.map(t => taskRow(t, cls)).join('')}</ul>
                </div>`;
        };

        const routineSection = (items) => {
            if (!items || items.length === 0) return '';
            const rows = items.map(r => `
                <li class="list-item ${r.completed_today ? 'is-completed' : ''}">
                    <label class="item-left">
                        <input type="checkbox" class="overview-routine-checkbox" data-id="${r.id}" ${r.completed_today ? 'checked' : ''}>
                        <span class="item-text">${escapeHtml(r.title)}</span>
                    </label>
                </li>`).join('');
            return `
                <div class="today-block routines-block">
                    <h2 class="section-title">Routinen</h2>
                    <ul class="app-list">${rows}</ul>
                </div>`;
        };

        const blocks = [
            taskSection('Überfällig', tasks.overdue, 'overdue'),
            taskSection('Heute', tasks.due_today, 'due'),
            routineSection(routines),
            taskSection('Irgendwann', tasks.someday, 'someday'),
            taskSection('Heute erledigt', tasks.done_today, 'done')
        ].filter(Boolean);

        sections.innerHTML = blocks.length > 0
            ? blocks.join('')
            : '<div class="list-msg empty">Heute ist nichts zu tun. Genieß den Tag! ☀</div>';

        renderTodayShoppingCard(overview.shopping || { open_count: 0 });
    }

    function renderTodayShoppingCard(shopping) {
        const slot = document.getElementById('shopping-card-slot');
        if (!slot) return;
        const count = shopping.open_count || 0;
        let text;
        if (count === 0) {
            text = 'Nichts zu kaufen 🎉';
        } else if (count === 1) {
            text = 'Heute einkaufen: 1 Artikel';
        } else {
            text = `Heute einkaufen: ${count} Artikel`;
        }
        slot.innerHTML = `
            <button type="button" class="shopping-card glass-panel" id="overview-shopping-card">
                <span class="shopping-card-icon">🛒</span>
                <span class="shopping-card-text">${escapeHtml(text)}</span>
            </button>`;
        const card = document.getElementById('overview-shopping-card');
        if (card) card.addEventListener('click', () => activateTab('shopping'));
    }

    async function toggleOverviewTask(id, done) {
        const response = await fetch(`${apiBaseUrl}/tasks/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ completed: done })
        });
        if (response.status === 401) return handleUnauthorized();
        loadOverview();
    }

    async function toggleOverviewRoutine(id, done) {
        const response = await fetch(`${apiBaseUrl}/api/routines/${id}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
            body: JSON.stringify({ completed_today: done })
        });
        if (response.status === 401) return handleUnauthorized();
        loadOverview();
    }

    function attachTodayListeners() {
        document.querySelectorAll('.overview-task-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                toggleOverviewTask(id, e.target.checked);
            });
        });
        document.querySelectorAll('.overview-routine-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                toggleOverviewRoutine(id, e.target.checked);
            });
        });
    }

    // ==========================================
    // Tab Navigation & Rendering
    // ==========================================
    function renderActiveTab() {
        const activeTab = document.querySelector('.tab-item.active');
        if (!activeTab) return;
        const target = activeTab.getAttribute('data-target');
        if (contentMap[target]) {
            mainContent.innerHTML = contentMap[target];
            if (target === 'today') {
                loadOverview();
            } else if (target === 'tasks') {
                loadTasks();
                attachTaskListeners();
            } else if (target === 'shopping') {
                loadShopping();
                attachShoppingListeners();
            } else if (target === 'routines') {
                loadRoutines();
                attachRoutinesListeners();
            } else if (target === 'chat') {
                attachChatListeners();
            }
        }
    }

    // Zentrale Tab-Aktivierung (Klick + programmatisch, z.B. Einkaufs-Karte).
    function activateTab(name) {
        let found = false;
        tabs.forEach(t => {
            const isTarget = t.getAttribute('data-target') === name;
            t.classList.toggle('active', isTarget);
            if (isTarget) found = true;
        });
        if (found) renderActiveTab();
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            activateTab(tab.getAttribute('data-target'));
        });
    });

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initialisierung
    checkAuth().then(isAuth => {
        if (isAuth) {
            renderActiveTab();
        }
    });
});
