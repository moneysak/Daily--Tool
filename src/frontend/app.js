document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-item');
    const mainContent = document.getElementById('main-content');

    const contentMap = {
        'tasks': '<h1>Aufgaben</h1><p>Hier sind deine Aufgaben.</p>',
        'shopping': '<h1>Einkaufslisten</h1><p>Hier sind deine Einkaufslisten.</p>',
        'routines': '<h1>Routinen</h1><p>Hier sind deine Routinen.</p>',
        'chat': '<h1>Hermes Chat</h1><p>Sprich mit Hermes.</p>'
    };

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
            }
        });
    });
});