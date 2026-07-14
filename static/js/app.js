/**
 * Quora Reply Automation - Shared JavaScript
 */

// ─── Utility Functions ───────────────────────────────────

function formatDate(iso) {
    if (!iso) return '';
    try {
        return new Date(iso).toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch(e) { return iso; }
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}

function setVal(id, value) {
    const el = document.getElementById(id);
    if (el && value !== undefined && value !== null) {
        el.value = value;
    }
}

// ─── API Helpers ─────────────────────────────────────────

async function apiGet(path) {
    const res = await fetch(path);
    return res.json();
}

async function apiPost(path, data = {}) {
    const res = await fetch(path, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    return res.json();
}

async function apiPut(path, data = {}) {
    const res = await fetch(path, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    return res.json();
}

async function apiDelete(path) {
    const res = await fetch(path, { method: 'DELETE' });
    return res.json();
}

// ─── Language Switcher ───────────────────────────────────

function toggleLangMenu() {
    const menu = document.getElementById('langMenu');
    if (menu) menu.classList.toggle('show');
}

// Close language menu when clicking outside
document.addEventListener('click', (e) => {
    const menu = document.getElementById('langMenu');
    if (menu && !e.target.closest('.lang-switcher')) {
        menu.classList.remove('show');
    }
});

async function switchLang(code) {
    try {
        await fetch('/api/lang/set', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lang: code})
        });
        window.location.reload();
    } catch(e) {
        console.error('Language switch error:', e);
    }
}

// ─── Notification Toast ─────────────────────────────────

function showToast(message, type = 'info') {
    // Remove existing toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.cssText = `
        position: fixed; bottom: 20px; right: 20px; z-index: 9999;
        padding: 12px 20px; border-radius: 8px; font-size: 13px;
        max-width: 400px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        animation: slideIn 0.3s ease;
        ${type === 'success' ? 'background: #1b5e20; color: #a5d6a7;' : ''}
        ${type === 'error' ? 'background: #b71c1c; color: #ef9a9a;' : ''}
        ${type === 'info' ? 'background: #1a237e; color: #9fa8da;' : ''}
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Inject toast animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style);

// ─── Screenshot Lightbox (click thumbnail to enlarge) ──
function openScreenshotLightbox(src) {
    if (!src) return;
    let box = document.getElementById('screenshotLightbox');
    if (!box) {
        box = document.createElement('div');
        box.id = 'screenshotLightbox';
        box.className = 'screenshot-lightbox';
        box.innerHTML = '<div class="sl-backdrop"></div>'
            + '<img class="sl-img" alt="Screenshot preview">'
            + '<button class="sl-close" aria-label="Close">✕</button>';
        document.body.appendChild(box);
        box.addEventListener('click', (e) => {
            if (e.target === box
                || e.target.classList.contains('sl-backdrop')
                || e.target.classList.contains('sl-close')) {
                box.style.display = 'none';
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') box.style.display = 'none';
        });
    }
    box.querySelector('.sl-img').src = src;
    box.style.display = 'flex';
}

// Event delegation: clicking any screenshot thumbnail enlarges it
document.addEventListener('click', (e) => {
    const cell = e.target.closest('.screenshot-thumb, .shot-item');
    if (!cell) return;
    const img = cell.querySelector('img');
    if (img && img.getAttribute('src')) {
        openScreenshotLightbox(img.src);
    }
});

console.log('📱 Quora Reply Automation JS loaded');
