document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-item');
    const mainContent = document.getElementById('main-content');

    const contentMap = {
        'tasks': `
            <h1>Aufgaben</h1>
            <div class="task-input-container">
                <input type="text" id="new-task-title" placeholder="Neue Aufgabe...">
                <button id="add-task-btn">Hinzufügen</button>
            </div>
            <ul id="task-list"></ul>
        `,
        'shopping': '<h1>Einkaufslisten</h1><p>Hier sind deine Einkaufslisten.</p>',
        'routines': '<h1>Routinen</h1><p>Hier sind deine Routinen.</p>',
        'chat': '<h1>Hermes Chat</h1><p>Sprich mit Hermes.</p>'
    };

    const apiBaseUrl = window.APP_CONFIG?.API_BASE_URL || "";

    async function loadTasks() {
        try {
            const response = await fetch(`${apiBaseUrl}/tasks/`);
            if (!response.ok) throw new Error('Failed to fetch tasks');
            const tasks = await response.json();
            renderTasks(tasks);
        } catch (error) {
            console.error('Error loading tasks:', error);
            const taskList = document.getElementById('task-list');
            if (taskList) {
                 taskList.innerHTML = '<li>Fehler beim Laden der Aufgaben.</li>';
            }
        }
    }

    async function addTask(title) {
        try {
            const response = await fetch(`${apiBaseUrl}/tasks/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title, completed: false })
            });
            if (!response.ok) throw new Error('Failed to add task');
            loadTasks();
        } catch (error) {
             console.error('Error adding task:', error);
        }
    }
    
    async function toggleTaskComplete(taskId, currentStatus) {
        try {
            const response = await fetch(`${apiBaseUrl}/tasks/${taskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ completed: !currentStatus })
            });
            if (!response.ok) throw new Error('Failed to update task');
            loadTasks();
        } catch(error) {
            console.error('Error updating task:', error);
        }
    }

    function renderTasks(tasks) {
        const taskList = document.getElementById('task-list');
        if (!taskList) return;
        
        taskList.innerHTML = '';
        tasks.forEach(task => {
            const li = document.createElement('li');
            li.innerHTML = `
                <label>
                    <input type="checkbox" ${task.completed ? 'checked' : ''} data-id="${task.id}" class="task-checkbox">
                    <span class="${task.completed ? 'completed' : ''}">${task.title}</span>
                </label>
            `;
            taskList.appendChild(li);
        });

        // Add event listeners for checkboxes
        document.querySelectorAll('.task-checkbox').forEach(checkbox => {
             checkbox.addEventListener('change', (e) => {
                  const taskId = e.target.getAttribute('data-id');
                  const currentStatus = !e.target.checked; // Since it just changed, previous status is opposite
                  toggleTaskComplete(taskId, currentStatus);
             });
        });
    }


    function attachTaskListeners() {
        const addBtn = document.getElementById('add-task-btn');
        const input = document.getElementById('new-task-title');
        
        if (addBtn && input) {
            addBtn.addEventListener('click', () => {
                const title = input.value.trim();
                if (title) {
                    addTask(title);
                    input.value = '';
                }
            });
            input.addEventListener('keypress', (e) => {
                 if (e.key === 'Enter') {
                      const title = input.value.trim();
                      if (title) {
                          addTask(title);
                          input.value = '';
                      }
                 }
            })
        }
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            
            // Add active class to clicked tab
            tab.classList.add('active');
            
            // Update content based on target
            const target = tab.getAttribute('data-target');
            if (contentMap[target]) {
                mainContent.innerHTML = contentMap[target];
                if (target === 'tasks') {
                    loadTasks();
                    attachTaskListeners();
                }
            }
        });
    });
    
    // Initial load for active tab
    const activeTab = document.querySelector('.tab-item.active');
    if (activeTab) {
         const target = activeTab.getAttribute('data-target');
         if (target === 'tasks') {
              mainContent.innerHTML = contentMap['tasks'];
              loadTasks();
              attachTaskListeners();
         }
    }

});