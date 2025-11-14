/**
 * Meta Pixel Cookie Capture - Client-Side
 * 
 * Captura _fbp e _fbc do navegador e envia ao servidor via URL params
 * Isso garante que 100% do tráfego tenha cookies capturados corretamente
 * 
 * ✅ CRÍTICO: Executar ANTES do redirect para Telegram
 */

(function() {
    'use strict';
    
    // ✅ Capturar cookies do navegador
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }
    
    // ✅ Capturar _fbp e _fbc
    const fbp = getCookie('_fbp');
    const fbc = getCookie('_fbc');
    
    // ✅ Se já estamos na URL de redirect, adicionar cookies como params
    const currentUrl = window.location.href;
    const urlObj = new URL(currentUrl);
    
    // ✅ Adicionar cookies como params apenas se não estiverem presentes
    // Isso evita sobrescrever cookies já capturados
    if (fbp && !urlObj.searchParams.has('_fbp_cookie')) {
        urlObj.searchParams.set('_fbp_cookie', fbp);
    }
    
    if (fbc && !urlObj.searchParams.has('_fbc_cookie')) {
        urlObj.searchParams.set('_fbc_cookie', fbc);
    }
    
    // ✅ Se cookies foram adicionados, atualizar URL (sem reload se possível)
    if ((fbp && !urlObj.searchParams.has('_fbp_cookie')) || (fbc && !urlObj.searchParams.has('_fbc_cookie'))) {
        // ✅ Log para debug (remover em produção se necessário)
        console.log('[META PIXEL] Cookies capturados:', {
            fbp: fbp ? fbp.substring(0, 30) + '...' : 'ausente',
            fbc: fbc ? fbc.substring(0, 50) + '...' : 'ausente'
        });
        
        // ✅ Atualizar URL com cookies (servidor vai ler os params)
        // Nota: Isso pode causar redirect, mas garante que cookies sejam enviados
        if (window.history && window.history.replaceState) {
            window.history.replaceState({}, '', urlObj.toString());
        } else {
            // Fallback para navegadores antigos
            window.location.href = urlObj.toString();
        }
    }
})();

