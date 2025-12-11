/**
 * TRADITIONAL_ENGINE_V8.js
 * 
 * 🔥 V8 ULTRA: TraditionalEngine - Sistema Tradicional Isolado
 * 
 * Só roda se router liberar.
 * Responde com boas vindas.
 * Continua funis antigos se Flow desativado.
 * Zero interferência com o flow.
 * 
 * @author ENGINEER-SUPREME MODE (ESM)
 * @version 8.0
 */

class TraditionalEngineV8 {
    /**
     * Constructor
     * @param {Object} botManager - Instância do BotManager
     */
    constructor(botManager) {
        this.botManager = botManager;
        this.redisConn = null;
        
        // Inicializar Redis
        this._initRedis();
    }
    
    /**
     * Inicializa conexão Redis
     * @private
     */
    _initRedis() {
        try {
            if (typeof get_redis_connection !== 'undefined') {
                this.redisConn = get_redis_connection();
            } else if (this.botManager && this.botManager._get_redis_connection) {
                this.redisConn = this.botManager._get_redis_connection();
            }
        } catch(e) {
            console.warn('⚠️ Redis não disponível para TraditionalEngine');
        }
    }
    
    /**
     * 🔥 CRÍTICO: Verifica se flow está ativo ANTES de processar
     * 
     * @param {string} userMessage - Mensagem do usuário
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {string} telegramUserId - ID do usuário no Telegram
     * @param {Object} context - Contexto adicional
     * @returns {Promise<any>} Resultado do processamento
     */
    async process(userMessage, botId, chatId, telegramUserId, context = {}) {
        // ✅ VERIFICAÇÃO OBRIGATÓRIA: Flow está ativo?
        const isFlowActive = await this.checkFlowActive(botId, chatId);
        
        if (isFlowActive) {
            console.log('🚫 [TRADITIONAL V8] BLOQUEADO - Flow Engine está ativo');
            return; // NÃO processar nada
        }
        
        // Processar via sistema tradicional
        console.log('✅ [TRADITIONAL V8] Processando via sistema tradicional');
        
        // Chamar método do botManager para enviar welcome
        if (this.botManager && this.botManager._send_welcome_message_only) {
            // Construir objeto message simulado
            const message = {
                from: {
                    id: parseInt(telegramUserId),
                    first_name: 'Usuário'
                },
                text: userMessage
            };
            
            // Buscar config
            const config = await this._getBotConfig(botId);
            
            if (config) {
                return await this.botManager._send_welcome_message_only(
                    botId,
                    context.token || '',
                    config,
                    chatId,
                    message
                );
            }
        }
        
        return null;
    }
    
    /**
     * 🔥 CRÍTICO: Verificação atômica se flow está ativo
     * 
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @returns {Promise<boolean>} True se flow está ativo
     */
    async checkFlowActive(botId, chatId) {
        try {
            // Verificar flag no Redis primeiro (mais rápido)
            if (this.redisConn) {
                const flagKey = `flow_active:${botId}:${chatId}`;
                const flag = await this.redisConn.get(flagKey);
                if (flag === '1') {
                    return true;
                }
            }
            
            // Buscar config e verificar
            const config = await this._getBotConfig(botId);
            
            if (!config) {
                return false;
            }
            
            // Usar função checkActiveFlow existente
            if (typeof checkActiveFlow !== 'undefined') {
                return checkActiveFlow(config);
            }
            
            // Fallback: verificação manual
            const flowEnabled = config.get('flow_enabled', false);
            const flowSteps = config.get('flow_steps', []);
            
            // Parsear flow_enabled
            let isEnabled = false;
            if (typeof flowEnabled === 'string') {
                isEnabled = flowEnabled.toLowerCase().trim() in ('true', '1', 'yes', 'on', 'enabled');
            } else if (typeof flowEnabled === 'boolean') {
                isEnabled = flowEnabled;
            } else if (typeof flowEnabled === 'number') {
                isEnabled = Boolean(flowEnabled);
            }
            
            // Parsear flow_steps
            let steps = [];
            if (flowSteps) {
                if (typeof flowSteps === 'string') {
                    try {
                        steps = JSON.parse(flowSteps);
                    } catch(e) {
                        steps = [];
                    }
                } else if (Array.isArray(flowSteps)) {
                    steps = flowSteps;
                }
            }
            
            // Retornar true apenas se flow está ativo E tem steps válidos
            return isEnabled && Array.isArray(steps) && steps.length > 0;
        } catch (error) {
            console.error('❌ [TRADITIONAL V8] Erro ao verificar flow ativo:', error);
            return false; // Default seguro: flow inativo
        }
    }
    
    /**
     * Busca configuração do bot
     * @private
     * @param {number} botId - ID do bot
     * @returns {Promise<Object>} Configuração do bot
     */
    async _getBotConfig(botId) {
        // Assumindo que botManager tem método para buscar config
        if (this.botManager && this.botManager._get_bot_config) {
            return await this.botManager._get_bot_config(botId);
        }
        
        return null;
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.TraditionalEngineV8 = TraditionalEngineV8;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = TraditionalEngineV8;
}

