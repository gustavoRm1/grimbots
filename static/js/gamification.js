/**
 * Gamification V2 - Frontend JS
 * Sistema de notificações, popups e animações
 */

// ============================================================================
// CONEXÃO WEBSOCKET
// ============================================================================

let gamificationSocket = null;

function initGamification() {
    if (!window.socket) {
        return;
    }
    
    destroyGamification();
    
    gamificationSocket = window.socket;
    gamificationSocket.emit('subscribe_gamification');
    
    gamificationSocket.on('achievement_unlocked', handleAchievementUnlocked);
    gamificationSocket.on('league_promotion', handleLeaguePromotion);
    gamificationSocket.on('title_unlocked', handleTitleUnlocked);
    gamificationSocket.on('ranking_update', handleRankingUpdate);
    gamificationSocket.on('season_ending', handleSeasonEnding);
}

function destroyGamification() {
    if (gamificationSocket) {
        gamificationSocket.off('achievement_unlocked', handleAchievementUnlocked);
        gamificationSocket.off('league_promotion', handleLeaguePromotion);
        gamificationSocket.off('title_unlocked', handleTitleUnlocked);
        gamificationSocket.off('ranking_update', handleRankingUpdate);
        gamificationSocket.off('season_ending', handleSeasonEnding);
    }
    gamificationSocket = null;
}

// ============================================================================
// HANDLERS DE EVENTOS
// ============================================================================

function handleAchievementUnlocked(data) {
    playAchievementSound(data.sound);
    showAchievementPopup(data);
    if (data.animation === 'confetti' || data.animation === 'confetti_gold') {
        showConfetti(data.achievement.rarity);
    }
}

function handleLeaguePromotion(data) {
    playSound('level_up.mp3');
    showLeaguePromotionPopup(data);
}

function handleTitleUnlocked(data) {
    playSound('title_unlock.mp3');
    showTitlePopup(data);
}

function handleRankingUpdate(data) {
    if (data.direction === 'up' && data.delta >= 50) {
        showRankingNotification(data);
    }
}

function handleSeasonEnding(data) {
    if (data.days_left <= 7) {
        showSeasonEndingBanner(data);
    }
}

// ============================================================================
// POPUP DE CONQUISTA DESBLOQUEADA
// ============================================================================

function showAchievementPopup(data) {
    const achievement = data.achievement;
    
    // Cores por raridade
    const rarityColors = {
        'common': '#D1D5DB',
        'uncommon': '#34D399',
        'rare': '#3B82F6',
        'epic': '#A855F7',
        'legendary': '#F59E0B',
        'mythic': '#EF4444'
    };
    
    const color = rarityColors[achievement.rarity] || '#D1D5DB';
    
    // Criar popup
    const popup = document.createElement('div');
    popup.className = 'achievement-popup animate-bounceIn';
    popup.innerHTML = `
        <div class="achievement-popup-overlay"></div>
        <div class="achievement-popup-content ${achievement.rarity}">
            <!-- Header -->
            <div class="achievement-header" style="background: linear-gradient(135deg, ${color}, ${color}AA);">
                <i class="${achievement.icon} achievement-icon"></i>
                <h2 style="color: #1C1917; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">CONQUISTA DESBLOQUEADA!</h2>
            </div>
            
            <!-- Body -->
            <div class="achievement-body" style="background: #1F2937;">
                <h3 style="color: #FAFAFA; font-weight: 900;">${achievement.name}</h3>
                <p style="color: #D1D5DB;">${achievement.description}</p>
                
                <!-- Recompensas -->
                <div class="achievement-rewards">
                    <div class="reward-item">
                        <i class="fas fa-star" style="color: ${color};"></i>
                        <span style="color: ${color}; font-weight: 900;">+${achievement.points.toLocaleString()} pts</span>
                    </div>
                    ${achievement.reward_value.title ? `
                        <div class="reward-item">
                            <i class="fas fa-crown" style="color: ${color};"></i>
                            <span style="color: #FDE68A; font-weight: 900;">Título: ${achievement.reward_value.title}</span>
                        </div>
                    ` : ''}
                    ${achievement.reward_value.discount ? `
                        <div class="reward-item">
                            <i class="fas fa-percentage" style="color: ${color};"></i>
                            <span style="color: #6EE7B7; font-weight: 900;">${achievement.reward_value.discount}% OFF comissão (${achievement.reward_value.duration_days} dias)</span>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Raridade -->
                <div class="achievement-rarity ${achievement.rarity}" style="background: ${color}; color: #1C1917;">
                    ${achievement.rarity.toUpperCase()}
                </div>
            </div>
            
            <!-- Footer -->
            <button onclick="closeAchievementPopup()" class="achievement-close-btn" style="background: linear-gradient(135deg, ${color}, ${color}CC);">
                Continuar <i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(popup);
    
    // Auto-fechar após 10 segundos
    setTimeout(() => {
        closeAchievementPopup();
    }, 10000);
}

function closeAchievementPopup() {
    const popup = document.querySelector('.achievement-popup');
    if (popup) {
        popup.classList.add('animate-fadeOut');
        setTimeout(() => popup.remove(), 300);
    }
}

// ============================================================================
// CONFETES
// ============================================================================

function showConfetti(rarity) {
    const existingConfetti = document.querySelectorAll('.confetti-piece');
    if (existingConfetti.length > 50) {
        existingConfetti.forEach(el => el.remove());
    }
    
    const confettiColors = {
        'epic': ['#A855F7', '#EC4899', '#3B82F6'],
        'legendary': ['#F59E0B', '#FDE68A', '#FBBF24'],
        'mythic': ['#EF4444', '#F59E0B', '#EC4899', '#A855F7']
    };
    
    const colors = confettiColors[rarity] || ['#F59E0B', '#3B82F6', '#34D399'];
    
    const duration = rarity === 'mythic' ? 5000 : 3000;
    const count = rarity === 'mythic' ? 200 : 100;
    
    for (let i = 0; i < count; i++) {
        setTimeout(() => {
            createConfettiPiece(colors[Math.floor(Math.random() * colors.length)]);
        }, Math.random() * duration);
    }
}

function createConfettiPiece(color) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti-piece';
    confetti.style.left = Math.random() * 100 + 'vw';
    confetti.style.background = color;
    confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
    
    document.body.appendChild(confetti);
    
    setTimeout(() => confetti.remove(), 4000);
}

// ============================================================================
// SOM
// ============================================================================

function playAchievementSound(soundFile) {
    try {
        const audio = new Audio(`/static/sounds/${soundFile}`);
        audio.volume = 0.5;
        audio.play().catch(() => {});
    } catch (e) {
    }
}

function playSound(soundFile) {
    playAchievementSound(soundFile);
}

// ============================================================================
// POPUP DE PROMOÇÃO DE LIGA
// ============================================================================

function showLeaguePromotionPopup(data) {
    const newLeague = data.new_league;
    
    const popup = document.createElement('div');
    popup.className = 'league-promotion-popup animate-bounceIn';
    popup.innerHTML = `
        <div class="achievement-popup-overlay"></div>
        <div class="achievement-popup-content legendary">
            <div class="achievement-header" style="background: linear-gradient(135deg, ${newLeague.color}, ${newLeague.color}AA);">
                <i class="${newLeague.icon} text-5xl" style="color: #1C1917;"></i>
                <h2 style="color: #1C1917; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">PROMOÇÃO!</h2>
            </div>
            
            <div class="achievement-body" style="background: #1F2937;">
                <h3 style="color: #FAFAFA; font-weight: 900;">Você foi promovido para</h3>
                <h2 style="color: ${newLeague.color}; font-size: 2.5rem; font-weight: 900; text-shadow: 0 0 20px ${newLeague.color};">
                    ${newLeague.name.toUpperCase()}
                </h2>
                
                <div class="achievement-rewards">
                    <div class="reward-item">
                        <i class="fas fa-percentage" style="color: #6EE7B7;"></i>
                        <span style="color: #6EE7B7; font-weight: 900;">${newLeague.commission_discount}% de desconto na comissão!</span>
                    </div>
                </div>
            </div>
            
            <button onclick="closeLeaguePromotionPopup()" class="achievement-close-btn" style="background: linear-gradient(135deg, ${newLeague.color}, ${newLeague.color}CC);">
                Continuar <i class="fas fa-arrow-right ml-2"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(popup);
}

function closeLeaguePromotionPopup() {
    const popup = document.querySelector('.league-promotion-popup');
    if (popup) {
        popup.classList.add('animate-fadeOut');
        setTimeout(() => popup.remove(), 300);
    }
}

// ============================================================================
// NOTIFICAÇÃO DE TÍTULO
// ============================================================================

function showTitlePopup(data) {
    const title = data.title;
    
    showToast({
        title: '👑 Título Desbloqueado!',
        message: `Você ganhou o título: ${title.prefix} ${title.name}`,
        type: 'success',
        duration: 5000
    });
}

// ============================================================================
// NOTIFICAÇÃO DE RANKING
// ============================================================================

function showRankingNotification(data) {
    const icon = data.direction === 'up' ? '📈' : '📉';
    const color = data.direction === 'up' ? '#34D399' : '#EF4444';
    
    showToast({
        title: `${icon} Posição no Ranking`,
        message: `Você ${data.direction === 'up' ? 'subiu' : 'caiu'} ${data.delta} posições! (#${data.old_position} → #${data.new_position})`,
        type: data.direction === 'up' ? 'success' : 'warning',
        duration: 5000
    });
}

// ============================================================================
// BANNER DE FIM DE SEASON
// ============================================================================

function showSeasonEndingBanner(data) {
    // Verificar se já mostrou hoje
    const lastShown = localStorage.getItem('season_ending_banner_shown');
    const today = new Date().toDateString();
    
    if (lastShown === today) {
        return;  // Não mostrar novamente hoje
    }
    
    showToast({
        title: '⏰ Temporada Terminando!',
        message: `Faltam apenas ${data.days_left} dias para o fim da ${data.season.name}!`,
        type: 'warning',
        duration: 8000
    });
    
    localStorage.setItem('season_ending_banner_shown', today);
}

// ============================================================================
// TOAST NOTIFICATION (HELPER)
// ============================================================================

function showToast({title, message, type = 'info', duration = 5000}) {
    const colors = {
        'success': '#34D399',
        'error': '#EF4444',
        'warning': '#F59E0B',
        'info': '#3B82F6'
    };
    
    const color = colors[type] || colors.info;
    
    const toast = document.createElement('div');
    toast.className = 'gamification-toast animate-slideInRight';
    toast.innerHTML = `
        <div class="toast-content" style="border-left: 4px solid ${color};">
            <div class="toast-header" style="color: ${color}; font-weight: 900;">
                ${title}
            </div>
            <div class="toast-body" style="color: #E5E7EB;">
                ${message}
            </div>
        </div>
    `;
    
    const container = document.getElementById('gamification-toasts') || createToastContainer();
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('animate-slideOutRight');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'gamification-toasts';
    container.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
    `;
    document.body.appendChild(container);
    return container;
}

// ============================================================================
// API HELPERS
// ============================================================================

async function fetchGamificationProfile() {
    try {
        const response = await fetch('/api/v2/gamification/profile');
        const data = await response.json();
        
        if (data.success) {
            return data.profile;
        }
    } catch (e) {
    }
    return null;
}

async function fetchAchievements(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const response = await fetch(`/api/v2/gamification/achievements?${params}`);
        const data = await response.json();
        
        if (data.success) {
            return data.achievements;
        }
    } catch (e) {
    }
    return [];
}

async function fetchLeaderboard(filters = {}) {
    try {
        const params = new URLSearchParams(filters);
        const response = await fetch(`/api/v2/gamification/leaderboard?${params}`);
        const data = await response.json();
        
        if (data.success) {
            return data.leaderboard;
        }
    } catch (e) {
    }
    return [];
}

async function equipTitle(titleId) {
    try {
        const response = await fetch(`/api/v2/gamification/titles/${titleId}/equip`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showToast({
                title: '👑 Título Equipado!',
                message: data.message,
                type: 'success'
            });
            return true;
        }
    } catch (e) {
    }
    return false;
}

async function markNotificationRead(notificationId) {
    try {
        await fetch(`/api/v2/gamification/notifications/${notificationId}/read`, {
            method: 'POST'
        });
    } catch (e) {
    }
}

// ============================================================================
// INICIALIZAÇÃO
// ============================================================================

// Inicializar quando DOM carregar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGamification);
} else {
    initGamification();
}

document.addEventListener('beforeunload', destroyGamification);

// Expor funções globalmente
window.gamification = {
    init: initGamification,
    destroy: destroyGamification,
    fetchProfile: fetchGamificationProfile,
    fetchAchievements,
    fetchLeaderboard,
    equipTitle,
    markNotificationRead
};






