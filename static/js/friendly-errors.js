/**
 * Sistema de Mensagens de Erro Amigáveis
 * Converte erros técnicos em linguagem simples
 */

const errorMessages = {
    // ========================================
    // ERROS DE BANCO DE DADOS
    // ========================================
    'UNIQUE constraint failed: bots.token': {
        title: '🤖 Este bot já foi cadastrado',
        message: 'Parece que você já adicionou este bot antes.',
        action: 'Cada bot só pode ser cadastrado uma vez. Tente usar um bot diferente ou verifique sua lista de bots.',
        type: 'warning'
    },
    
    'UNIQUE constraint failed: users.email': {
        title: '📧 Este email já está em uso',
        message: 'Já existe uma conta com este email.',
        action: 'Tente fazer login ou use outro email para criar uma nova conta.',
        type: 'warning'
    },
    
    'UNIQUE constraint failed: users.username': {
        title: '👤 Este nome de usuário já existe',
        message: 'Alguém já está usando este nome.',
        action: 'Escolha um nome de usuário diferente.',
        type: 'warning'
    },
    
    // ========================================
    // ERROS DE AUTENTICAÇÃO
    // ========================================
    'Invalid email or password': {
        title: '🔒 Email ou senha incorretos',
        message: 'Não conseguimos encontrar uma conta com esses dados.',
        action: 'Verifique se digitou corretamente. Esqueceu sua senha? Clique em "Recuperar Senha".',
        type: 'error'
    },
    
    'Email ou senha inválidos': {
        title: '🔒 Dados incorretos',
        message: 'Email ou senha não conferem.',
        action: 'Confira se digitou tudo certinho e tente novamente.',
        type: 'error'
    },
    
    'Você precisa estar logado': {
        title: '⚠️ Faça login primeiro',
        message: 'Esta página precisa que você esteja logado.',
        action: 'Entre na sua conta para continuar.',
        type: 'warning'
    },
    
    // ========================================
    // ERROS DO TELEGRAM
    // ========================================
    'Unauthorized: bot token is invalid': {
        title: '❌ Token do bot inválido',
        message: 'O token que você colou não funciona.',
        action: 'Copie novamente o token do @BotFather no Telegram e cole aqui. Certifique-se de copiar tudo.',
        type: 'error'
    },
    
    'bot token is invalid': {
        title: '❌ Token incorreto',
        message: 'Este token não é válido.',
        action: 'Verifique se copiou o token completo do @BotFather.',
        type: 'error'
    },
    
    'Not Found: bot not found': {
        title: '🔍 Bot não encontrado',
        message: 'Não conseguimos encontrar este bot no Telegram.',
        action: 'Certifique-se de que o bot foi criado no @BotFather.',
        type: 'error'
    },
    
    // ========================================
    // ERROS DE GATEWAY/PAGAMENTO
    // ========================================
    'Invalid gateway credentials': {
        title: '💳 Dados do método de pagamento incorretos',
        message: 'As informações que você forneceu não estão corretas.',
        action: 'Confira os dados do seu método de pagamento (SyncPay, Paradise, etc) e tente novamente.',
        type: 'error'
    },
    
    'Gateway not configured': {
        title: '⚠️ Método de pagamento não configurado',
        message: 'Você precisa configurar um método de pagamento primeiro.',
        action: 'Vá em Configurações e adicione um método de pagamento (PIX).',
        type: 'warning'
    },
    
    // ========================================
    // ERROS DE VALIDAÇÃO
    // ========================================
    'Campo obrigatório': {
        title: '📝 Preencha todos os campos',
        message: 'Alguns campos obrigatórios estão vazios.',
        action: 'Campos marcados com * são obrigatórios. Preencha todos eles.',
        type: 'warning'
    },
    
    'Email inválido': {
        title: '📧 Email no formato errado',
        message: 'Este não parece ser um email válido.',
        action: 'Exemplo de email correto: seu.nome@gmail.com',
        type: 'warning'
    },
    
    'Senha muito curta': {
        title: '🔐 Senha muito fraca',
        message: 'Sua senha precisa ter pelo menos 6 caracteres.',
        action: 'Crie uma senha mais forte com letras, números e símbolos.',
        type: 'warning'
    },
    
    // ========================================
    // ERROS DE CONEXÃO
    // ========================================
    'Network error': {
        title: '📡 Problema de conexão',
        message: 'Não conseguimos conectar com o servidor.',
        action: 'Verifique sua internet e tente novamente em alguns segundos.',
        type: 'error'
    },
    
    'Timeout': {
        title: '⏱️ Demorou muito',
        message: 'A operação está demorando mais que o esperado.',
        action: 'Tente novamente. Se persistir, entre em contato com o suporte.',
        type: 'warning'
    },
    
    // ========================================
    // ERROS GENÉRICOS
    // ========================================
    'Internal Server Error': {
        title: '😕 Ops! Algo deu errado',
        message: 'Tivemos um problema inesperado.',
        action: 'Tente novamente em alguns segundos. Se o erro continuar, entre em contato com o suporte.',
        type: 'error'
    },
    
    '500': {
        title: '🔧 Erro no servidor',
        message: 'Estamos com um problema técnico.',
        action: 'Já fomos notificados. Tente novamente em alguns minutos.',
        type: 'error'
    },
    
    '404': {
        title: '🔍 Página não encontrada',
        message: 'A página que você procura não existe.',
        action: 'Verifique se o endereço está correto ou volte para o início.',
        type: 'warning'
    },
    
    '403': {
        title: '🚫 Sem permissão',
        message: 'Você não tem permissão para acessar isso.',
        action: 'Se acha que deveria ter acesso, entre em contato com o suporte.',
        type: 'warning'
    }
};

/**
 * Converte um erro técnico em mensagem amigável
 * @param {string} technicalError - Erro técnico do backend
 * @returns {object} Objeto com dados da mensagem amigável
 */
function getFriendlyError(technicalError) {
    // Tentar encontrar mensagem exata
    if (errorMessages[technicalError]) {
        return errorMessages[technicalError];
    }
    
    // Tentar encontrar por palavra-chave
    for (const [key, value] of Object.entries(errorMessages)) {
        if (technicalError.includes(key)) {
            return value;
        }
    }
    
    // Mensagem padrão
    return {
        title: '😕 Algo não funcionou',
        message: 'Não conseguimos completar esta ação.',
        action: 'Tente novamente em alguns segundos ou entre em contato com o suporte se o problema persistir.',
        type: 'error'
    };
}

/**
 * Exibe mensagem de erro amigável na tela
 * @param {string} technicalError - Erro técnico do backend
 * @param {string} containerId - ID do container onde exibir (opcional)
 */
function showFriendlyError(technicalError, containerId = 'error-container') {
    const error = getFriendlyError(technicalError);
    
    const icons = {
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️',
        success: '✅'
    };
    
    const colors = {
        error: 'bg-red-50 border-red-300 text-red-800',
        warning: 'bg-yellow-50 border-yellow-300 text-yellow-800',
        info: 'bg-blue-50 border-blue-300 text-blue-800',
        success: 'bg-green-50 border-green-300 text-green-800'
    };
    
    const html = `
        <div class="rounded-xl p-5 border-2 ${colors[error.type]} animate-fadeInDown mb-4" 
             role="alert"
             x-data="{show: true}" 
             x-show="show"
             x-transition:enter="transition ease-out duration-300"
             x-transition:enter-start="opacity-0 transform scale-95"
             x-transition:enter-end="opacity-100 transform scale-100">
            <div class="flex items-start">
                <div class="flex-shrink-0 text-3xl">
                    ${icons[error.type]}
                </div>
                <div class="ml-4 flex-1">
                    <h3 class="text-lg font-bold mb-2">
                        ${error.title}
                    </h3>
                    <p class="text-sm mb-3">
                        ${error.message}
                    </p>
                    ${error.action ? `
                        <div class="mt-3 p-3 bg-white bg-opacity-40 rounded-lg">
                            <p class="text-sm font-medium">
                                💡 ${error.action}
                            </p>
                        </div>
                    ` : ''}
                </div>
                <button @click="show = false" 
                        class="ml-4 flex-shrink-0 text-xl hover:scale-110 transition-transform focus:outline-none"
                        aria-label="Fechar">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = html;
        
        // Auto-hide após 8 segundos (para não-críticos)
        if (error.type !== 'error') {
            setTimeout(() => {
                if (container.firstElementChild) {
                    container.firstElementChild.remove();
                }
            }, 8000);
        }
    } else {
        console.warn(`Container #${containerId} não encontrado`);
    }
    
    return error;
}

/**
 * Exibe mensagem de sucesso
 * @param {string} message - Mensagem de sucesso
 * @param {string} containerId - ID do container
 */
function showSuccess(message, containerId = 'error-container') {
    const html = `
        <div class="rounded-xl p-5 border-2 bg-green-50 border-green-300 text-green-800 animate-fadeInDown mb-4" 
             x-data="{show: true}" 
             x-show="show"
             x-init="setTimeout(() => show = false, 5000)">
            <div class="flex items-start">
                <div class="flex-shrink-0 text-3xl">
                    ✅
                </div>
                <div class="ml-4 flex-1">
                    <h3 class="text-lg font-bold">
                        Tudo certo!
                    </h3>
                    <p class="text-sm mt-1">
                        ${message}
                    </p>
                </div>
                <button @click="show = false" 
                        class="ml-4 flex-shrink-0 text-xl hover:scale-110 transition-transform">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = html;
    }
}

// Exportar para uso global
window.showFriendlyError = showFriendlyError;
window.getFriendlyError = getFriendlyError;
window.showSuccess = showSuccess;

