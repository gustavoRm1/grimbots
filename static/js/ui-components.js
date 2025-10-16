/**
 * Componentes de UI Reutilizáveis
 * Sistema completo de UX melhorado
 */

// ========================================
// TOOLTIPS E AJUDA CONTEXTUAL
// ========================================

function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip-popup hidden';
        tooltip.innerHTML = el.getAttribute('data-tooltip');
        el.parentElement.style.position = 'relative';
        el.parentElement.appendChild(tooltip);
        
        el.addEventListener('mouseenter', () => tooltip.classList.remove('hidden'));
        el.addEventListener('mouseleave', () => tooltip.classList.add('hidden'));
    });
}

// ========================================
// LOADING STATES
// ========================================

function setButtonLoading(button, loading, loadingText = 'Carregando...') {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            ${loadingText}
        `;
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText;
    }
}

// ========================================
// CONFIRMAÇÕES DE AÇÕES DESTRUTIVAS
// ========================================

function confirmAction(config) {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 z-50 overflow-y-auto';
        modal.innerHTML = `
            <div class="flex items-center justify-center min-h-screen px-4">
                <div class="fixed inset-0 bg-black opacity-50"></div>
                <div class="relative bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
                    <div class="text-center">
                        <div class="text-6xl mb-4">${config.icon || '<i class="fas fa-exclamation-triangle text-yellow-500"></i>'}</div>
                        <h3 class="text-2xl font-bold text-gray-900 mb-2">${config.title}</h3>
                        <p class="text-gray-600 mb-6">${config.message}</p>
                        ${config.warning ? `
                            <div class="bg-red-50 border-2 border-red-300 rounded-xl p-4 mb-6">
                                <p class="text-red-800 font-bold text-sm"><i class="fas fa-exclamation-triangle mr-2"></i>${config.warning}</p>
                            </div>
                        ` : ''}
                        <div class="flex gap-3">
                            <button class="cancel-btn flex-1 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-all">
                                ${config.cancelText || 'Cancelar'}
                            </button>
                            <button class="confirm-btn flex-1 px-6 py-3 bg-red-600 text-white rounded-xl font-semibold hover:bg-red-700 transition-all">
                                ${config.confirmText || 'Confirmar'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('.cancel-btn').onclick = () => {
            modal.remove();
            resolve(false);
        };
        
        modal.querySelector('.confirm-btn').onclick = () => {
            modal.remove();
            resolve(true);
        };
    });
}

// ========================================
// MOBILE NAVIGATION
// ========================================

function enhanceMobileNav() {
    const nav = document.querySelector('nav');
    if (!nav) return;
    
    // Adicionar labels em mobile
    const mobileLinks = nav.querySelectorAll('a');
    mobileLinks.forEach(link => {
        const icon = link.querySelector('i');
        const text = link.textContent.trim();
        
        if (icon && window.innerWidth < 640) {
            link.innerHTML = `
                <div class="flex flex-col items-center gap-1">
                    ${icon.outerHTML}
                    <span class="text-xs">${text.split(' ')[0]}</span>
                </div>
            `;
        }
    });
}

// ========================================
// INIT
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    initTooltips();
    enhanceMobileNav();
    
    // Re-aplicar em resize
    window.addEventListener('resize', enhanceMobileNav);
});

// Exportar globalmente
window.setButtonLoading = setButtonLoading;
window.confirmAction = confirmAction;

