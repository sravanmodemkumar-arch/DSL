// STEM Video Generator - Client-side JS

// Auto-refresh processing pages
document.addEventListener('DOMContentLoaded', function() {
    // Tab key in JSON editor inserts spaces
    const editor = document.getElementById('json-editor');
    if (editor) {
        editor.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.selectionStart;
                const end = this.selectionEnd;
                this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
                this.selectionStart = this.selectionEnd = start + 2;
            }
        });
    }
});

// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const colors = {
        info: 'bg-cyan-500/20 border-cyan-500/30 text-cyan-400',
        success: 'bg-green-500/20 border-green-500/30 text-green-400',
        error: 'bg-red-500/20 border-red-500/30 text-red-400',
        warning: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
    };

    const toast = document.createElement('div');
    toast.className = `p-3 rounded-lg border text-sm fade-in ${colors[type] || colors.info}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// HTMX event listeners
document.body.addEventListener('htmx:responseError', function(e) {
    showToast('Request failed. Please try again.', 'error');
});
