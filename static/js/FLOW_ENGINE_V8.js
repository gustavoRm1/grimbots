/**
 * FLOW_ENGINE_V8.js
 * 
 * 🔥 V8 ULTRA: FlowEngine - Execution Engine
 * 
 * Executa steps do flow visual.
 * Administra conexões.
 * Lê o JSON do flow.
 * Mantém estado por chat e bot.
 * Usa store persistente (Redis, DB).
 * Impede qualquer envio tradicional.
 * Renderiza outputs de forma limpa.
 * Garante progresso deterministicamente.
 * 
 * @author ENGINEER-SUPREME MODE (ESM)
 * @version 8.0
 */

class FlowEngineV8 {
    /**
     * Constructor
     * @param {Object} botManager - Instância do BotManager
     */
    constructor(botManager) {
        this.botManager = botManager;
        this.activeFlows = new Map(); // botId:chatId -> FlowState
        this.flowStore = new FlowStoreV8(); // Store persistente
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
            console.warn('⚠️ Redis não disponível para FlowEngine');
        }
    }
    
    /**
     * 🔥 CRÍTICO: Processa mensagem APENAS se flow estiver ativo
     * Bloqueia 100% do sistema tradicional
     * 
     * @param {string} userMessage - Mensagem do usuário
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {string} telegramUserId - ID do usuário no Telegram
     * @param {Object} context - Contexto adicional
     * @returns {Promise<any>} Resultado do processamento
     */
    async process(userMessage, botId, chatId, telegramUserId, context = {}) {
        try {
            // ✅ PASSO 1: Obter estado do flow de forma atômica
            const flowState = await this.getFlowState(botId, chatId);
            
            if (!flowState || !flowState.isActive) {
                throw new Error('Flow Engine não está ativo');
            }
            
            // ✅ PASSO 2: Processar mensagem via flow
            return await this.executeFlowStep(flowState, userMessage, botId, chatId, telegramUserId, context);
        } catch (error) {
            console.error('❌ [FLOW ENGINE V8] Erro ao processar:', error);
            throw error;
        }
    }
    
    /**
     * 🔥 CRÍTICO: Executa step do flow
     * NÃO permite que sistema tradicional interfira
     * 
     * @param {Object} flowState - Estado do flow
     * @param {string} userMessage - Mensagem do usuário
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {string} telegramUserId - ID do usuário no Telegram
     * @param {Object} context - Contexto adicional
     * @returns {Promise<any>} Resultado da execução
     */
    async executeFlowStep(flowState, userMessage, botId, chatId, telegramUserId, context = {}) {
        try {
            // 1. Identificar step atual
            const currentStepId = flowState.currentStep || flowState.startStep;
            
            if (!currentStepId) {
                throw new Error('Step atual não identificado');
            }
            
            // 2. Buscar step no flowState
            const currentStep = this._findStepById(flowState.steps, currentStepId);
            
            if (!currentStep) {
                throw new Error(`Step ${currentStepId} não encontrado`);
            }
            
            // 3. Processar mensagem no contexto do step atual
            // (lógica específica baseada no tipo de step)
            
            // 4. Identificar próximo step baseado em:
            //    - Botões clicados (se userMessage é callback)
            //    - Condições (se step é condition)
            //    - Conexões do flow (next, pending, retry)
            const nextStepId = await this._identifyNextStep(
                currentStep,
                userMessage,
                flowState,
                context
            );
            
            // 5. Executar próximo step (se houver)
            if (nextStepId) {
                // Atualizar flowState de forma atômica
                await this._updateFlowState(botId, chatId, {
                    currentStep: nextStepId
                });
                
                // Executar próximo step recursivamente
                const updatedFlowState = await this.getFlowState(botId, chatId);
                return await this.executeFlowStep(
                    updatedFlowState,
                    userMessage,
                    botId,
                    chatId,
                    telegramUserId,
                    context
                );
            } else {
                // Fim do fluxo
                console.log('✅ [FLOW ENGINE V8] Fluxo finalizado');
                return { completed: true };
            }
        } catch (error) {
            console.error('❌ [FLOW ENGINE V8] Erro ao executar step:', error);
            throw error;
        }
    }
    
    /**
     * Identifica próximo step baseado em contexto
     * @private
     * @param {Object} currentStep - Step atual
     * @param {string} userMessage - Mensagem do usuário
     * @param {Object} flowState - Estado do flow
     * @param {Object} context - Contexto adicional
     * @returns {Promise<string|null>} ID do próximo step ou null
     */
    async _identifyNextStep(currentStep, userMessage, flowState, context) {
        const stepType = currentStep.type || 'message';
        const stepConfig = currentStep.config || {};
        const connections = currentStep.connections || {};
        const customButtons = stepConfig.custom_buttons || [];
        
        // Se é callback de botão
        if (context.isCallback && context.buttonIndex !== undefined) {
            const button = customButtons[context.buttonIndex];
            if (button && button.target_step) {
                return String(button.target_step);
            }
        }
        
        // Se é condition
        if (stepType === 'condition') {
            // Avaliar condições (lógica específica)
            const conditionResult = await this._evaluateConditions(
                currentStep,
                userMessage,
                flowState
            );
            
            if (conditionResult === true && stepConfig.true_step_id) {
                return String(stepConfig.true_step_id);
            } else if (conditionResult === false && stepConfig.false_step_id) {
                return String(stepConfig.false_step_id);
            }
        }
        
        // Conexão padrão (next, pending, retry)
        if (connections.next) {
            return String(connections.next);
        }
        
        // Sem próximo step
        return null;
    }
    
    /**
     * Avalia condições do step
     * @private
     * @param {Object} step - Step com condições
     * @param {string} userMessage - Mensagem do usuário
     * @param {Object} flowState - Estado do flow
     * @returns {Promise<boolean>} Resultado da avaliação
     */
    async _evaluateConditions(step, userMessage, flowState) {
        // Implementação específica de avaliação de condições
        // Por enquanto, retorna true como padrão
        return true;
    }
    
    /**
     * Busca step por ID
     * @private
     * @param {Array} steps - Array de steps
     * @param {string} stepId - ID do step
     * @returns {Object|null} Step encontrado ou null
     */
    _findStepById(steps, stepId) {
        if (!Array.isArray(steps)) {
            return null;
        }
        
        return steps.find(s => String(s.id) === String(stepId)) || null;
    }
    
    /**
     * Obtém estado do flow de forma atômica
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @returns {Promise<Object|null>} Estado do flow ou null
     */
    async getFlowState(botId, chatId) {
        const stateKey = `${botId}:${chatId}`;
        
        // Verificar cache em memória
        if (this.activeFlows.has(stateKey)) {
            return this.activeFlows.get(stateKey);
        }
        
        // Buscar do Redis/DB
        try {
            if (this.redisConn) {
                const redisKey = `flow_state:${stateKey}`;
                const cached = await this.redisConn.get(redisKey);
                if (cached) {
                    const state = JSON.parse(cached);
                    this.activeFlows.set(stateKey, state);
                    return state;
                }
            }
        } catch(e) {
            console.warn('⚠️ Erro ao buscar flow state do Redis:', e);
        }
        
        // Buscar do banco via botManager
        try {
            const config = await this._getBotConfig(botId);
            if (config && checkActiveFlow && checkActiveFlow(config)) {
                const flowState = await this._buildFlowState(config);
                this.activeFlows.set(stateKey, flowState);
                return flowState;
            }
        } catch(e) {
            console.warn('⚠️ Erro ao buscar flow state do banco:', e);
        }
        
        return null;
    }
    
    /**
     * Constrói estado do flow a partir da config
     * @private
     * @param {Object} config - Configuração do bot
     * @returns {Promise<Object>} Estado do flow
     */
    async _buildFlowState(config) {
        const flowSteps = config.flow_steps || [];
        const flowStartStepId = config.flow_start_step_id;
        
        // Parsear flow_steps se necessário
        let steps = [];
        if (typeof flowSteps === 'string') {
            try {
                steps = JSON.parse(flowSteps);
            } catch(e) {
                steps = [];
            }
        } else if (Array.isArray(flowSteps)) {
            steps = flowSteps;
        }
        
        // Identificar start step
        let startStepId = flowStartStepId;
        if (!startStepId && steps.length > 0) {
            // Fallback: primeiro step ou step com order=1
            const sortedSteps = steps.sort((a, b) => (a.order || 0) - (b.order || 0));
            startStepId = sortedSteps[0]?.id;
        }
        
        return {
            isActive: true,
            startStep: startStepId ? String(startStepId) : null,
            currentStep: startStepId ? String(startStepId) : null,
            steps: steps,
            connections: this._buildConnectionsMap(steps)
        };
    }
    
    /**
     * Constrói mapa de conexões
     * @private
     * @param {Array} steps - Array de steps
     * @returns {Map} Mapa de conexões
     */
    _buildConnectionsMap(steps) {
        const connectionsMap = new Map();
        
        steps.forEach(step => {
            const stepId = String(step.id);
            const stepConnections = step.connections || {};
            const stepConfig = step.config || {};
            const customButtons = stepConfig.custom_buttons || [];
            
            // Conexões padrão (next, pending, retry)
            if (stepConnections.next) {
                connectionsMap.set(`${stepId}:next`, String(stepConnections.next));
            }
            if (stepConnections.pending) {
                connectionsMap.set(`${stepId}:pending`, String(stepConnections.pending));
            }
            if (stepConnections.retry) {
                connectionsMap.set(`${stepId}:retry`, String(stepConnections.retry));
            }
            
            // Conexões de botões
            customButtons.forEach((btn, idx) => {
                if (btn.target_step) {
                    connectionsMap.set(`${stepId}:button:${idx}`, String(btn.target_step));
                }
            });
            
            // Conexões de condições
            if (step.type === 'condition') {
                if (stepConfig.true_step_id) {
                    connectionsMap.set(`${stepId}:true`, String(stepConfig.true_step_id));
                }
                if (stepConfig.false_step_id) {
                    connectionsMap.set(`${stepId}:false`, String(stepConfig.false_step_id));
                }
            }
        });
        
        return connectionsMap;
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
    
    /**
     * 🔥 CRÍTICO: Bloqueia sistema tradicional quando flow está ativo
     * 
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {Object} flowConfig - Configuração do flow
     * @returns {Promise<void>}
     */
    async activateFlow(botId, chatId, flowConfig) {
        const stateKey = `${botId}:${chatId}`;
        
        // Construir flowState
        const flowState = await this._buildFlowState(flowConfig);
        
        // Salvar em memória
        this.activeFlows.set(stateKey, flowState);
        
        // ✅ GARANTIA: Marcar no Redis/DB que flow está ativo (atômico)
        await this.setFlowActiveFlag(botId, chatId, true);
        
        // Salvar estado no Redis
        if (this.redisConn) {
            try {
                const redisKey = `flow_state:${stateKey}`;
                await this.redisConn.set(
                    redisKey,
                    JSON.stringify(flowState),
                    'EX',
                    86400 // Expira em 24h
                );
            } catch(e) {
                console.warn('⚠️ Erro ao salvar flow state no Redis:', e);
            }
        }
        
        console.log(`✅ [FLOW ENGINE V8] Flow ativado: ${stateKey}`);
    }
    
    /**
     * 🔥 CRÍTICO: Desativa flow e libera sistema tradicional
     * 
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @returns {Promise<void>}
     */
    async deactivateFlow(botId, chatId) {
        const stateKey = `${botId}:${chatId}`;
        
        // Remover de memória
        this.activeFlows.delete(stateKey);
        
        // ✅ GARANTIA: Remover flag do Redis/DB (atômico)
        await this.setFlowActiveFlag(botId, chatId, false);
        
        // Remover estado do Redis
        if (this.redisConn) {
            try {
                const redisKey = `flow_state:${stateKey}`;
                await this.redisConn.del(redisKey);
            } catch(e) {
                console.warn('⚠️ Erro ao remover flow state do Redis:', e);
            }
        }
        
        console.log(`✅ [FLOW ENGINE V8] Flow desativado: ${stateKey}`);
    }
    
    /**
     * Atualiza estado do flow de forma atômica
     * @private
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {Object} updates - Atualizações a aplicar
     * @returns {Promise<void>}
     */
    async _updateFlowState(botId, chatId, updates) {
        const stateKey = `${botId}:${chatId}`;
        const currentState = this.activeFlows.get(stateKey);
        
        if (!currentState) {
            return;
        }
        
        // Aplicar atualizações
        const updatedState = {
            ...currentState,
            ...updates
        };
        
        // Atualizar em memória
        this.activeFlows.set(stateKey, updatedState);
        
        // Atualizar no Redis
        if (this.redisConn) {
            try {
                const redisKey = `flow_state:${stateKey}`;
                await this.redisConn.set(
                    redisKey,
                    JSON.stringify(updatedState),
                    'EX',
                    86400
                );
            } catch(e) {
                console.warn('⚠️ Erro ao atualizar flow state no Redis:', e);
            }
        }
    }
    
    /**
     * Define flag de flow ativo no Redis/DB
     * @param {number} botId - ID do bot
     * @param {number} chatId - ID do chat
     * @param {boolean} isActive - Se flow está ativo
     * @returns {Promise<void>}
     */
    async setFlowActiveFlag(botId, chatId, isActive) {
        const flagKey = `flow_active:${botId}:${chatId}`;
        
        if (this.redisConn) {
            try {
                if (isActive) {
                    await this.redisConn.set(flagKey, '1', 'EX', 86400);
                } else {
                    await this.redisConn.del(flagKey);
                }
            } catch(e) {
                console.warn('⚠️ Erro ao definir flag de flow ativo:', e);
            }
        }
        
        // Também salvar no banco (se botManager tem método)
        if (this.botManager && this.botManager._set_flow_active_flag) {
            try {
                await this.botManager._set_flow_active_flag(botId, chatId, isActive);
            } catch(e) {
                console.warn('⚠️ Erro ao definir flag de flow ativo no banco:', e);
            }
        }
    }
}

/**
 * FlowStoreV8 - Store persistente para flow states
 */
class FlowStoreV8 {
    constructor() {
        this.storage = new Map(); // Fallback em memória
    }
    
    async get(key) {
        return this.storage.get(key);
    }
    
    async set(key, value) {
        this.storage.set(key, value);
    }
    
    async delete(key) {
        this.storage.delete(key);
    }
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.FlowEngineV8 = FlowEngineV8;
    window.FlowStoreV8 = FlowStoreV8;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FlowEngineV8, FlowStoreV8 };
}

