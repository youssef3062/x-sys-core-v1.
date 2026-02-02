/**
 * main.js — Brescan Frontend Logic
 * Handles Desktop Enhancements, UX interactions, and dynamic components.
 */

const DesktopApp = {
    notifications: [],
    contextMenu: null,
    searchData: [],

    init() {
        console.log('Initialize Desktop App');
        this.setupPageTransitions();
        this.setupNavbar();
        this.setupKeyboardShortcuts();
        this.setupContextMenu();
        this.setupNotifications();
        this.setupSearch();
        this.setupBreadcrumbs();
        this.setupTableSorting();
        this.setupResizablePanels();
        this.setupDragAndDrop();
        this.detectDesktopFeatures();
    },

    // Page transitions: Fade in content on load
    setupPageTransitions() {
        const pageContent = document.querySelector('.page-content');
        if (pageContent) {
            pageContent.style.opacity = '0';
            pageContent.style.transform = 'translateY(15px)';
            pageContent.style.transition = 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)';

            requestAnimationFrame(() => {
                pageContent.style.opacity = '1';
                pageContent.style.transform = 'translateY(0)';
            });
        }
    },

    // Navbar behavior: Hide on scroll down, show on scroll up
    setupNavbar() {
        const navbar = document.querySelector('.brescan-nav');
        let lastScrollTop = 0;

        window.addEventListener('scroll', () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            if (navbar) {
                if (scrollTop > lastScrollTop && scrollTop > 100) {
                    navbar.style.transform = 'translateY(-100%)';
                } else {
                    navbar.style.transform = 'translateY(0)';
                }
            }
            lastScrollTop = scrollTop;
        });
    },

    // Keyboard Shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Global search (Ctrl + K)
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.showSearch();
            }
            // Escape to close UX overlays
            if (e.key === 'Escape') {
                this.hideContextMenu();
                this.hideSearch();
            }
        });
    },

    // Context Menu System
    setupContextMenu() {
        this.contextMenu = document.getElementById('contextMenu');

        document.addEventListener('contextmenu', (e) => {
            const target = e.target.closest('.patient-row, .visit-row, .medical-record');
            if (target) {
                e.preventDefault();
                this.showContextMenu(e.clientX, e.clientY, target);
            }
        });

        document.addEventListener('click', () => {
            this.hideContextMenu();
        });

        if (this.contextMenu) {
            this.contextMenu.addEventListener('click', (e) => {
                const item = e.target.closest('.context-menu-item');
                if (item) {
                    this.handleContextAction(item.dataset.action);
                    this.hideContextMenu();
                }
            });
        }
    },

    showContextMenu(x, y, target) {
        if (!this.contextMenu) return;
        this.contextMenu.style.display = 'block';

        // Prevent menu from going off-screen
        let menuWidth = this.contextMenu.offsetWidth || 200;
        let menuHeight = this.contextMenu.offsetHeight || 150;

        let posX = x;
        let posY = y;

        if (x + menuWidth > window.innerWidth) posX = window.innerWidth - menuWidth - 10;
        if (y + menuHeight > window.innerHeight) posY = window.innerHeight - menuHeight - 10;

        this.contextMenu.style.left = posX + 'px';
        this.contextMenu.style.top = posY + 'px';
        this.contextMenu.dataset.targetId = target.dataset.id || '';
    },

    hideContextMenu() {
        if (this.contextMenu) this.contextMenu.style.display = 'none';
    },

    handleContextAction(action) {
        // Implement specific logic here
        this.showNotification(`Action triggered: ${action}`, 'info');
    },

    // Search System
    setupSearch() {
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value;
                if (query.length > 2) {
                    this.performSearch(query);
                } else {
                    this.hideSearchSuggestions();
                }
            });
        }
    },

    showSearch() {
        const searchBar = document.getElementById('advancedSearch');
        const searchInput = document.getElementById('searchInput');
        if (searchBar && searchInput) {
            searchBar.style.display = 'block';
            searchInput.focus();
        }
    },

    hideSearch() {
        const searchBar = document.getElementById('advancedSearch');
        if (searchBar) searchBar.style.display = 'none';
    },

    performSearch(query) {
        // Mock search logic for UI demonstration
        const mockResults = [
            { type: 'patient', name: 'John Doe', id: 'BRESCAN-0001' },
            { type: 'visit', label: 'Visit Jan 15', id: 'V-102' }
        ].filter(r => r.name?.toLowerCase().includes(query.toLowerCase()) || r.label?.toLowerCase().includes(query.toLowerCase()));

        this.displaySearchResults(mockResults);
    },

    displaySearchResults(results) {
        const suggestions = document.getElementById('searchSuggestions');
        if (results.length > 0 && suggestions) {
            suggestions.innerHTML = results.map(r => `
                <div class="search-suggestion">
                    <i class="fas fa-${r.type === 'patient' ? 'user' : 'file-medical'} me-2"></i>
                    <span>${r.name || r.label}</span>
                </div>
            `).join('');
            suggestions.style.display = 'block';
        } else if (suggestions) {
            suggestions.style.display = 'none';
        }
    },

    hideSearchSuggestions() {
        const suggestions = document.getElementById('searchSuggestions');
        if (suggestions) suggestions.style.display = 'none';
    },

    // Breadcrumbs
    setupBreadcrumbs() {
        const nav = document.getElementById('breadcrumbNav');
        const list = document.getElementById('breadcrumbList');
        if (nav && list) {
            const path = window.location.pathname.split('/').filter(p => p);
            if (path.length > 0) {
                let html = '<li><a href="/">Home</a></li>';
                let current = '';
                path.forEach((p, i) => {
                    current += `/${p}`;
                    const isLast = i === path.length - 1;
                    const name = p.charAt(0).toUpperCase() + p.slice(1);
                    html += isLast
                        ? `<li><span class="active">${name}</span></li>`
                        : `<li><a href="${current}">${name}</a></li>`;
                });
                list.innerHTML = html;
                nav.style.display = 'block';
            }
        }
    },

    // Notifications
    setupNotifications() {
        const container = document.getElementById('notifications');
        if (!container) return;
        this.notificationsContainer = container;
    },

    showNotification(message, type = 'info', duration = 3000) {
        const c = document.getElementById('notifications');
        if (!c) return;

        const notif = document.createElement('div');
        notif.className = `desktop-notification border-${type}`;
        notif.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'} text-${type}"></i>
            <span>${message}</span>
        `;
        c.appendChild(notif);

        setTimeout(() => {
            notif.style.opacity = '0';
            setTimeout(() => notif.remove(), 300);
        }, duration);
    },

    // Table Sorting (Basic client-side)
    setupTableSorting() {
        document.querySelectorAll('th.sortable').forEach(th => {
            th.addEventListener('click', () => {
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                const idx = Array.from(th.parentNode.children).indexOf(th);
                const asc = !th.classList.contains('asc');

                const rows = Array.from(tbody.querySelectorAll('tr')).sort((a, b) => {
                    const av = a.children[idx].innerText;
                    const bv = b.children[idx].innerText;
                    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
                });

                rows.forEach(r => tbody.appendChild(r));
                table.querySelectorAll('th').forEach(t => t.classList.remove('asc', 'desc'));
                th.classList.toggle('asc', asc);
                th.classList.toggle('desc', !asc);
            });
        });
    },

    setupResizablePanels() {
        // Placeholder for future resize logic
    },

    setupDragAndDrop() {
        // Placeholder for future drag and drop logic
    },

    detectDesktopFeatures() {
        if (window.innerWidth > 1024) {
            document.body.classList.add('is-desktop');
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    DesktopApp.init();
});
