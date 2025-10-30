// Service Worker para PWA - Grimbots
// Versão: 2.0.0 - Debug aprimorado

const CACHE_NAME = 'grimbots-v2';
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
    console.log('[SW] Service Worker instalado (v2.0.0)');
    
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
// PUSH NOTIFICATIONS - DEBUG APRIMORADO
// ============================================================================

// Receber notificação push do servidor
self.addEventListener('push', (event) => {
    console.log('[SW] ========================================');
    console.log('[SW] 🔔 PUSH EVENT RECEBIDO!');
    console.log('[SW] ========================================');
    console.log('[SW] Timestamp:', new Date().toISOString());
    console.log('[SW] Has data:', !!event.data);
    
    // ✅ IMPORTANTE: pywebpush envia dados como texto JSON
    // Usar event.waitUntil() para garantir que a Promise seja aguardada
    const promiseChain = Promise.resolve().then(() => {
        if (!event.data) {
            console.warn('[SW] ⚠️ Push event sem dados! Mostrando notificação padrão.');
            return showDefaultNotification();
        }
        
        try {
            // Tentar diferentes métodos de parsing
            if (typeof event.data.json === 'function') {
                // Método padrão para PushMessageData (síncrono)
                const pushData = event.data.json();
                console.log('[SW] ✅ Dados parseados via .json():', JSON.stringify(pushData, null, 2));
                return processPushNotification(pushData);
            } else if (typeof event.data.text === 'function') {
                // Se .json() não funcionar, tentar como texto (assíncrono)
                return event.data.text().then((text) => {
                    console.log('[SW] 📝 Dados recebidos como texto:', text);
                    const pushData = JSON.parse(text);
                    console.log('[SW] ✅ Dados parseados via .text() + JSON.parse():', JSON.stringify(pushData, null, 2));
                    return processPushNotification(pushData);
                }).catch((e) => {
                    console.error('[SW] ❌ Erro ao ler/parsear texto:', e);
                    return showDefaultNotification();
                });
            } else {
                // Tentar acessar diretamente
                const pushData = event.data;
                console.log('[SW] ⚠️ Dados acessados diretamente:', pushData);
                return processPushNotification(pushData);
            }
        } catch (e) {
            console.error('[SW] ❌ ERRO ao parsear dados do push:', e);
            console.error('[SW] Tipo do event.data:', typeof event.data);
            return showDefaultNotification();
        }
    });
    
    // ✅ CRÍTICO: Usar event.waitUntil() para garantir que o Service Worker não seja encerrado
    event.waitUntil(promiseChain);
});

function processPushNotification(pushData) {
    console.log('[SW] 📦 Processando dados do push:', JSON.stringify(pushData, null, 2));
    
    // Extrair dados (pode estar em pushData diretamente ou aninhado)
    const title = pushData.title || (pushData.data && pushData.data.title);
    const body = pushData.body || (pushData.data && pushData.data.body);
    const amount = pushData.amount || (pushData.data && pushData.data.amount);
    const color = pushData.color || (pushData.data && pushData.data.color) || 'green';
    const paymentId = pushData.payment_id || (pushData.data && pushData.data.payment_id);
    const botId = pushData.bot_id || (pushData.data && pushData.data.bot_id);
    const url = pushData.url || (pushData.data && pushData.data.url) || '/dashboard';
    
    // Dados da notificação
    let notificationData = {
        title: title || '💰 Nova Venda!',
        body: body || (amount ? `Você recebeu: R$ ${parseFloat(amount).toFixed(2)}` : 'Você recebeu uma nova venda'),
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        tag: 'sale-notification',
        requireInteraction: false,
        vibrate: [200, 100, 200],
        silent: false,
        renotify: true,
        data: {
            payment_id: paymentId,
            amount: amount,
            bot_id: botId,
            url: url
        }
    };
    
    // ✅ CORES CONFORME TIPO
    if (color === 'orange') {
        notificationData.tag = 'pending-sale';
        console.log('[SW] 🟠 Notificação PENDENTE (laranja)');
    } else {
        notificationData.tag = 'approved-sale';
        console.log('[SW] 🟢 Notificação APROVADA (verde)');
    }
    
    console.log('[SW] 📝 Notificação configurada:', JSON.stringify(notificationData, null, 2));
    
    // Mostrar notificação
    showNotification(notificationData);
}

function showDefaultNotification() {
    const notificationData = {
        title: '💰 Nova Venda!',
        body: 'Você recebeu uma nova venda',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="%23FFB800"/><text x="50" y="70" font-size="60" text-anchor="middle" fill="%23111827">🤖</text></svg>',
        tag: 'sale-notification',
        requireInteraction: false,
        vibrate: [200, 100, 200],
        data: { url: '/dashboard' }
    };
    showNotification(notificationData);
}

function showNotification(notificationData) {
    console.log('[SW] 🎯 Mostrando notificação...');
    
    const notificationPromise = self.registration.showNotification(
        notificationData.title,
        notificationData
    ).then(() => {
        console.log('[SW] ✅ Notificação exibida com sucesso!');
        return Promise.resolve();
    }).catch((error) => {
        console.error('[SW] ❌ ERRO ao exibir notificação:', error);
        console.error('[SW] Erro completo:', JSON.stringify(error, Object.getOwnPropertyNames(error)));
        return Promise.reject(error);
    });
    
    return notificationPromise;
}

// Clique na notificação
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] 🖱️ Notificação clicada:', event);
    
    event.notification.close();
    
    const urlToOpen = event.notification.data?.url || '/dashboard';
    console.log('[SW] Abrindo URL:', urlToOpen);
    
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then((clientList) => {
            // Se já existe uma janela aberta, focar nela
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.includes(urlToOpen) && 'focus' in client) {
                    console.log('[SW] Focando janela existente:', client.url);
                    return client.focus();
                }
            }
            
            // Se não existe, abrir nova janela
            if (clients.openWindow) {
                console.log('[SW] Abrindo nova janela:', urlToOpen);
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

// Fechar notificação
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] 📭 Notificação fechada');
});

// Mensagens do cliente (para debug/test)
self.addEventListener('message', (event) => {
    console.log('[SW] 📨 Mensagem recebida:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
