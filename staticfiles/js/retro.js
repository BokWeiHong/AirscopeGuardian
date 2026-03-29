document.addEventListener('DOMContentLoaded', () => {

    // Footer Clock
    const footerTime = document.getElementById('footer-time');
    function updateFooterTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        if (footerTime) footerTime.textContent = timeString;
    }
    setInterval(updateFooterTime, 1000);
    updateFooterTime();

    // Tab Switching Logic
    const tabs = document.querySelectorAll('.window-tabs .tab');
    if (tabs.length > 0) {
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                tabs.forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                const panel = document.getElementById(target);
                if (panel) panel.classList.add('active');
            });
        });
    }

    // Login Screen Toggle
    const loginScreen = document.getElementById('loginScreen');
    const gameTitle = document.querySelector(".game-title");
    const menuOptions = document.querySelector(".menu-options");

    window.showLogin = () => {
        if (gameTitle) gameTitle.style.display = "none";
        if (menuOptions) menuOptions.style.display = "none";
        if (loginScreen) loginScreen.style.display = "block";
    };

    window.closeLogin = () => {
        if (gameTitle) gameTitle.style.display = "block";
        if (menuOptions) menuOptions.style.display = "block";
        if (loginScreen) loginScreen.style.display = "none";
    };

    // Internet Connectivity Alert
    const alertBox = document.getElementById('alertMap');
    function showAlert(title, message) {
        if (!alertBox) return;
        const titleEl = alertBox.querySelector('.alert-title');
        const msgEl = alertBox.querySelector('.alert-message');
        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        alertBox.classList.remove('hidden');
    }

    function closeAlert() {
        if (alertBox) alertBox.classList.add('hidden');
    }

    function checkInternet() {
        if (!navigator.onLine) {
            showAlert("Connection Lost", "Internet connection required to load map tiles.");
        } else {
            closeAlert();
        }
    }

    window.addEventListener("online", checkInternet);
    window.addEventListener("offline", checkInternet);
    checkInternet();

});
