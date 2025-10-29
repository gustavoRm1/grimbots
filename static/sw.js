// Service Worker para PWA - Grimbots
// Versão: 1.0.0

const CACHE_NAME = 'grimbots-v1';
const STATIC_CACHE = [
    '/',
    '/dashboard',
    '/static/css/brand-colors-v2.css',
    '/static/css/dark-theme.css',
    '/static/css/ui-components.css',
    '/static/js/dashboard.js'
];

// Instalação do Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker instalado');
    
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Cache aberto');
            return cache.addAll(STATIC_CACHE).catch((err) => {
                console.warn('[SW] Erro ao fazer cache inicial:', err);
            });
        })
    );
    
    // Forçar ativação imediata
    self.skipWaiting();
});

// Ativação do Service Worker
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker ativado');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => {
                        console.log('[SW] Removendo cache antigo:', name);
                        return caches.delete(name);
                    })
            );
        })
    );
    
    // Tomar controle imediato de todas as páginas
    return self.clients.claim();
});

// Interceptar requisições (Network First strategy)
self.addEventListener('fetch', (event) => {
    // Apenas cache GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Se resposta válida, cachear
                if (response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Se offline, buscar do cache
                return caches.match(event.request);
            })
    );
});

// ============================================================================
// PUSH NOTIFICATIONS
// ============================================================================

// Receber notificação push do servidor
self.addEventListener('push', (event) => {
    console.log('[SW] Push recebido:', event);
    
    // Cores padrão (será sobrescrito pelos dados do push)
    let bgColor = '#10B981'; // Verde (aprovada) - padrão
    
    let notificationData = {
        title: '💰 Nova Venda!',
        body: 'Você recebeu uma nova venda',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        tag: 'sale-notification',
        requireInteraction: false,
        vibrate: [200, 100, 200],
        data: {
            url: '/dashboard'
        }
    };
    
    // Se dados foram enviados no push
    if (event.data) {
        try {
            const pushData = event.data.json();
            
            notificationData.title = pushData.title || notificationData.title;
            notificationData.body = pushData.body || `Você recebeu: R$ ${(pushData.amount || 0).toFixed(2)}`;
            notificationData.data = {
                payment_id: pushData.payment_id,
                amount: pushData.amount,
                bot_id: pushData.bot_id,
                url: pushData.url || '/dashboard'
            };
            
            // ✅ CORES CONFORME TIPO (pendente = laranja, aprovada = verde)
            if (pushData.color === 'orange') {
                // Pendente: Amarelo/Laranja (#FFB800)
                bgColor = '#FFB800';
                notificationData.tag = 'pending-sale';
            } else {
                // Aprovada: Verde (#10B981)
                bgColor = '#10B981';
                notificationData.tag = 'approved-sale';
            }
            
            // ✅ ANDROID: Configurações específicas
            // Android requer image/icon no formato base64 ou URL válida
            // Som: Android suporta som customizado, mas precisa estar acessível
            // Vibrate: Android suporta padrões de vibração
            notificationData.actions = [];
            notificationData.requireInteraction = false; // Não bloquear até interação
            notificationData.renotify = true; // Permitir notificações repetidas
            
            // Log para debug
            console.log('[SW] Push data recebido:', pushData);
        } catch (e) {
            console.error('[SW] Erro ao parsear dados do push:', e);
        }
    }
    
    const notificationPromise = self.registration.showNotification(
        notificationData.title,
        notificationData
    );
    
    event.waitUntil(notificationPromise);
});

// Clique na notificação
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notificação clicada:', event);
    
    event.notification.close();
    
    const urlToOpen = event.notification.data?.url || '/dashboard';
    
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then((clientList) => {
            // Se já existe uma janela aberta, focar nela
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.includes(urlToOpen) && 'focus' in client) {
                    return client.focus();
                }
            }
            
            // Se não existe, abrir nova janela
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

// Fechar notificação
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notificação fechada:', event);
});

// Mensagens do cliente (para debug/test)
self.addEventListener('message', (event) => {
    console.log('[SW] Mensagem recebida:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

