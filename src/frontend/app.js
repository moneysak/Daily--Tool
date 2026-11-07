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
        'chat': `
            <h1>Hermes Chat</h1>
            <div id="chat-container">
                <div id="chat-messages" style="height: 300px; overflow-y: scroll; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; background-color: #f9f9f9;"></div>
                <div class="chat-input-container">
                    <input type="text" id="chat-input" placeholder="Nachricht an Hermes..." style="width: 70%;">
                    <button id="send-chat-btn">Senden</button>
                </div>
            </div>
        `
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

    function attachChatListeners() {
        const sendBtn = document.getElementById('send-chat-btn');
        const input = document.getElementById('chat-input');
        const messagesDiv = document.getElementById('chat-messages');

        if (sendBtn && input && messagesDiv) {
            async function sendMessage() {
                const message = input.value.trim();
                if (!message) return;

                // User message
                const userMsg = document.createElement('div');
                userMsg.style.textAlign = 'right';
                userMsg.style.marginBottom = '5px';
                userMsg.innerHTML = `<strong>Du:</strong> ${message}`;
                messagesDiv.appendChild(userMsg);
                
                input.value = '';
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

                try {
                    const response = await fetch(`${apiBaseUrl}/api/hermes/chat`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ message: message })
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || 'Fehler bei der Kommunikation mit Hermes.');
                    }
                    
                    const data = await response.json();
                    
                    // Hermes message
                    const hermesMsg = document.createElement('div');
                    hermesMsg.style.textAlign = 'left';
                    hermesMsg.style.marginBottom = '5px';
                    hermesMsg.innerHTML = `<strong>Hermes:</strong> ${data.message || data.response || JSON.stringify(data)}`;
                    messagesDiv.appendChild(hermesMsg);
                    
                } catch (error) {
                    console.error('Chat error:', error);
                    const errorMsg = document.createElement('div');
                    errorMsg.style.textAlign = 'left';
                    errorMsg.style.marginBottom = '5px';
                    errorMsg.style.color = 'red';
                    errorMsg.innerHTML = `<strong>System:</strong> ${error.message}`;
                    messagesDiv.appendChild(errorMsg);
                }
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }

            sendBtn.addEventListener('click', sendMessage);
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
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
                } else if (target === 'chat') {
                    attachChatListeners();
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
         } else if (target === 'chat') {
              mainContent.innerHTML = contentMap['chat'];
              attachChatListeners();
         }
    }

});