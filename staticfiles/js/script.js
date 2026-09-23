/* ManagedTBI — Script */

document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const menuToggle = document.getElementById('menuToggle');

    if (menuToggle) {
        menuToggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // Close sidebar on Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        }
    });

    // Table row click highlight (optional)
    document.querySelectorAll('table tbody tr[data-href]').forEach(function (row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function () {
            window.location.href = this.dataset.href;
        });
    });
});
