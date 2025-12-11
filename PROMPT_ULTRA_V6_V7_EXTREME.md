# 🚀 PROMPT ULTRA V6+V7 EXTREME - FLOW ENGINE INTEGRATION

**IDENTIDADE OBRIGATÓRIA:**
Você é um **ENGENHEIRO SÊNIOR ESPECIALISTA** em sistemas de automação, flow builders, integração de motores de execução, e arquitetura de software enterprise. Você tem **40 anos de experiência** e trabalha exclusivamente com padrões ManyChat, Typebot, e sistemas de chatbot profissionais.

**MODO DE TRABALHO:**
- ✅ Lê **TODOS** os arquivos antes de propor qualquer solução
- ✅ NUNCA assume - sempre verifica no código
- ✅ NUNCA faz soluções fáceis ou gambiarras
- ✅ Implementa arquitetura completa e robusta
- ✅ Garante 0 race conditions, 0 duplicações, 0 conflitos
- ✅ Entrega código production-ready, testado, documentado

---

## 🎯 MISSÃO PRINCIPAL

Implementar a **INTEGRAÇÃO TOTAL V6+V7** entre dois sistemas operacionais:

1. **Sistema Tradicional (Legacy)** - Fluxo linear ManyChat padrão
2. **Flow Engine Visual** - Flow Builder com jsPlumb

**OBJETIVO:** Criar um **MessageRouter** único que garante que apenas UM sistema responda por vez, eliminando 100% das duplicações, conflitos e mensagens duplicadas.

---

## 📋 FASE 1: LEITURA OBRIGATÓRIA (NÃO PULE ESTA ETAPA)

### **1.1 Arquivos Obrigatórios para Ler:**

```
✅ static/js/flow_editor.js (TODO o arquivo)
✅ templates/bot_config.html (TODO o arquivo, especialmente seção Flow)
✅ bot_manager.py (funções: _handle_start_command, _execute_flow, _send_welcome_message_only)
✅ RELATORIO_COMPLETO_ERROS_SENIOR_NIVEL.md (todos os 15 erros)
✅ Qualquer arquivo que contenha "flow", "welcome", "start", "message" no nome
```

### **1.2 O Que Você Deve Entender:**

1. **Como o sistema tradicional funciona:**
   - Onde `_handle_start_command()` é chamado
   - Como `_send_welcome_message_only()` funciona
   - Quais triggers/automações são executadas
   - Onde as mensagens são enviadas

2. **Como o Flow Engine funciona:**
   - Como `_execute_flow()` é chamado
   - Como `flow_steps` é estruturado
   - Como `flow_start_step_id` é usado
   - Como conexões entre steps funcionam

3. **Onde os dois sistemas conflitam:**
   - Identificar TODOS os pontos onde ambos podem responder
   - Identificar TODOS os pontos onde mensagens podem ser duplicadas
   - Identificar TODOS os pontos onde triggers podem entrar

4. **Os 15 erros do frontend:**
   - Ler `RELATORIO_COMPLETO_ERROS_SENIOR_NIVEL.md`
   - Entender cada erro e sua causa raiz
   - Mapear como cada erro afeta o sistema

---

## 🔥 FASE 2: ARQUITETURA V6+V7 (IMPLEMENTAÇÃO OBRIGATÓRIA)

### **2.1 MessageRouter - Source of Truth**

Criar um **MessageRouter** único que controla TODAS as mensagens:

```javascript
// FLOW_ENGINE_ROUTER_V7.js
class MessageRouter {
    constructor() {
        this.flowEngine = {
            isActive: false,
            currentStep: null,
            steps: {},
            connections: {},
            executeStep(stepId) { /* ... */ }
        };
        this.traditionalEngine = {
            isActive: false,
            process(message) { /* ... */ }
        };
    }
    
    /**
     * 🔥 CRÍTICO: Único ponto de entrada para processar mensagens
     * Garante que apenas UM motor responde
     */
    async processMessage(userMessage, botId, chatId, telegramUserId) {
        // ✅ VERIFICAÇÃO 1: Flow Engine está ativo?
        const flowConfig = await this.getFlowConfig(botId);
        const isFlowActive = flowConfig?.flow_enabled === true && 
                            flowConfig?.flow_steps?.length > 0 &&
                            flowConfig?.flow_start_step_id;
        
        if (isFlowActive) {
            // 🔥 FLOW ENGINE ATIVO: Bloquear sistema tradicional 100%
            console.log('🎯 FLOW ENGINE ATIVO - Processando via Flow Engine');
            return await this.flowEngine.process(userMessage, botId, chatId, telegramUserId);
        } else {
            // 🔥 TRADITIONAL ENGINE ATIVO: Usar sistema tradicional
            console.log('📋 TRADITIONAL ENGINE ATIVO - Processando via sistema tradicional');
            return await this.traditionalEngine.process(userMessage, botId, chatId, telegramUserId);
        }
    }
    
    /**
     * 🔥 CRÍTICO: Verifica configuração do flow de forma atômica
     */
    async getFlowConfig(botId) {
        // Buscar do banco/Redis de forma atômica
        // Garantir que não há race conditions
    }
}
```

### **2.2 Flow Engine - Implementação Completa**

```javascript
// FLOW_ENGINE_V6.js
class FlowEngine {
    constructor(botManager) {
        this.botManager = botManager;
        this.activeFlows = new Map(); // botId -> flowState
    }
    
    /**
     * 🔥 CRÍTICO: Processa mensagem APENAS se flow estiver ativo
     * Bloqueia 100% do sistema tradicional
     */
    async process(userMessage, botId, chatId, telegramUserId) {
        const flowState = await this.getFlowState(botId, chatId);
        
        if (!flowState || !flowState.isActive) {
            throw new Error('Flow Engine não está ativo');
        }
        
        // Processar mensagem via flow
        return await this.executeFlowStep(flowState, userMessage, botId, chatId, telegramUserId);
    }
    
    /**
     * 🔥 CRÍTICO: Executa step do flow
     * NÃO permite que sistema tradicional interfira
     */
    async executeFlowStep(flowState, userMessage, botId, chatId, telegramUserId) {
        // 1. Identificar step atual
        const currentStep = flowState.currentStep || flowState.startStep;
        
        // 2. Processar mensagem no contexto do step atual
        // 3. Identificar próximo step baseado em:
        //    - Botões clicados
        //    - Condições
        //    - Conexões do flow
        
        // 4. Executar próximo step
        // 5. Atualizar flowState
        
        // ✅ GARANTIA: Nenhuma mensagem tradicional é enviada
    }
    
    /**
     * 🔥 CRÍTICO: Bloqueia sistema tradicional quando flow está ativo
     */
    async activateFlow(botId, chatId, flowConfig) {
        const flowState = {
            isActive: true,
            startStep: flowConfig.flow_start_step_id,
            currentStep: flowConfig.flow_start_step_id,
            steps: flowConfig.flow_steps,
            connections: this.buildConnectionsMap(flowConfig.flow_steps)
        };
        
        this.activeFlows.set(`${botId}:${chatId}`, flowState);
        
        // ✅ GARANTIA: Marcar no Redis/DB que flow está ativo
        await this.setFlowActiveFlag(botId, chatId, true);
    }
}
```

### **2.3 Traditional Engine - Bloqueio Quando Flow Ativo**

```javascript
// TRADITIONAL_ENGINE_V7.js
class TraditionalEngine {
    constructor(botManager) {
        this.botManager = botManager;
    }
    
    /**
     * 🔥 CRÍTICO: Verifica se flow está ativo ANTES de processar
     */
    async process(userMessage, botId, chatId, telegramUserId) {
        // ✅ VERIFICAÇÃO OBRIGATÓRIA: Flow está ativo?
        const isFlowActive = await this.checkFlowActive(botId, chatId);
        
        if (isFlowActive) {
            console.log('🚫 TRADITIONAL ENGINE BLOQUEADO - Flow Engine está ativo');
            return; // NÃO processar nada
        }
        
        // Processar via sistema tradicional
        return await this.botManager._send_welcome_message_only(...);
    }
    
    /**
     * 🔥 CRÍTICO: Verificação atômica se flow está ativo
     */
    async checkFlowActive(botId, chatId) {
        // Buscar flag do Redis/DB de forma atômica
        // Retornar true se flow está ativo
    }
}
```

### **2.4 Integração no bot_manager.py**

```python
# bot_manager.py - Modificações obrigatórias

class BotManager:
    def __init__(self):
        # ✅ Importar MessageRouter
        from flow_engine_router_v7 import MessageRouter
        self.messageRouter = MessageRouter()
    
    def _handle_start_command(self, bot_id, token, config, chat_id, telegram_user_id):
        """
        🔥 CRÍTICO: Usar MessageRouter para processar
        Garante que apenas UM motor responde
        """
        # ✅ Usar MessageRouter ao invés de lógica direta
        return self.messageRouter.processMessage(
            user_message='/start',
            bot_id=bot_id,
            chat_id=chat_id,
            telegram_user_id=telegram_user_id
        )
    
    def _handle_callback_query(self, bot_id, token, config, chat_id, telegram_user_id, callback_data):
        """
        🔥 CRÍTICO: Verificar se flow está ativo antes de processar
        """
        # ✅ Verificar flow ativo
        is_flow_active = self._check_flow_active(bot_id, chat_id)
        
        if is_flow_active:
            # Processar via Flow Engine
            return self._execute_flow_button_click(...)
        else:
            # Processar via sistema tradicional
            return self._handle_traditional_button_click(...)
```

---

## 🔧 FASE 3: CORREÇÃO DOS 15 ERROS DO FRONTEND

### **3.1 Erro 1: HTML Limpa ContentContainer**

**Localização:** `templates/bot_config.html:3149-3150`

**Correção Obrigatória:**
```javascript
// ❌ REMOVER:
canvas.innerHTML = '';

// ✅ SUBSTITUIR POR:
const contentContainer = canvas.querySelector('.flow-canvas-content');
if (contentContainer) {
    // Remover apenas steps, preservar contentContainer
    Array.from(contentContainer.children).forEach(child => {
        if (child.classList?.contains('flow-step-block')) {
            child.remove();
        }
    });
} else {
    // Criar contentContainer se não existe
    const newContent = document.createElement('div');
    newContent.className = 'flow-canvas-content';
    newContent.style.cssText = 'position:absolute; left:0; top:0; width:100%; height:100%; transform-origin:0 0;';
    canvas.appendChild(newContent);
}
```

### **3.2 Erro 2: Race Condition na Inicialização**

**Localização:** `static/js/flow_editor.js:293-395`

**Correção Obrigatória:**
```javascript
// ✅ GARANTIR que init() completa antes de usar instância
constructor(canvasId, alpineContext) {
    this.canvasId = canvasId;
    this.canvas = document.getElementById(canvasId);
    this.contentContainer = null;
    this.instance = null;
    this.initPromise = this.init(); // ✅ Salvar promise
    this.ready = false; // ✅ Flag de ready
}

async init() {
    try {
        this.setupCanvas();
        await this.waitForElement(this.contentContainer, 2000);
        await this.setupJsPlumbAsync();
        this.ready = true; // ✅ Marcar como pronto
    } catch (error) {
        console.error('❌ Erro na inicialização:', error);
        throw error; // ✅ Propagar erro
    }
}

// ✅ No HTML, aguardar:
await window.flowEditor.initPromise;
if (window.flowEditor.ready) {
    window.flowEditor.renderAllSteps();
}
```

### **3.3 Erro 3: Container Incorreto Draggable**

**Localização:** `static/js/flow_editor.js:3097-3101`

**Correção Obrigatória:**
```javascript
setupDraggableForStep(stepElement, stepId, innerWrapper) {
    // ✅ VALIDAÇÃO ROBUSTA
    if (!this.instance || !stepElement) {
        console.error('❌ setupDraggableForStep: instance ou stepElement não existe');
        return;
    }
    
    // ✅ GARANTIR contentContainer existe
    if (!this.contentContainer) {
        console.warn('⚠️ contentContainer não existe, criando...');
        this.setupCanvas();
        if (!this.contentContainer) {
            console.error('❌ Não foi possível criar contentContainer');
            return;
        }
    }
    
    // ✅ GARANTIR elemento está no container correto
    const container = this.contentContainer;
    if (!container.contains(stepElement)) {
        container.appendChild(stepElement);
    }
    
    // ✅ Verificar se elemento está realmente no DOM
    if (!stepElement.parentElement) {
        console.error('❌ stepElement não está no DOM');
        return;
    }
    
    // ... resto do código
}
```

### **3.4 Erro 4: Endpoints Não Aparecem**

**Localização:** `static/js/flow_editor.js:2641-2665`

**Correção Obrigatória:**
```javascript
addEndpoints(element, stepId, step) {
    // ✅ VALIDAÇÕES OBRIGATÓRIAS
    if (!this.instance || !element || !element.parentElement) {
        console.error('❌ addEndpoints: condições não atendidas');
        return;
    }
    
    // ✅ GARANTIR que nodes HTML existem e têm dimensões
    const inputNode = innerWrapper.querySelector('.flow-step-node-input');
    if (!inputNode) {
        console.error('❌ inputNode não encontrado');
        return;
    }
    
    const inputRect = inputNode.getBoundingClientRect();
    if (inputRect.width === 0 || inputRect.height === 0) {
        console.warn('⚠️ inputNode não tem dimensões, aguardando...');
        setTimeout(() => this.addEndpoints(element, stepId, step), 100);
        return;
    }
    
    // ✅ Criar endpoint
    const inputEndpoint = this.ensureEndpoint(this.instance, inputNode, inputUuid, options);
    
    // ✅ FORÇAR VISIBILIDADE IMEDIATAMENTE
    if (inputEndpoint && inputEndpoint.canvas) {
        inputEndpoint.canvas.style.cssText = `
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 10000 !important;
        `;
    }
    
    // ✅ FORÇAR SVG OVERLAY VISÍVEL
    const svgOverlay = this.canvas.querySelector('svg.jtk-overlay') || 
                       this.contentContainer.querySelector('svg.jtk-overlay') ||
                       this.canvas.querySelector('svg');
    if (svgOverlay) {
        svgOverlay.style.cssText = `
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            height: 100% !important;
            z-index: 10000 !important;
            pointer-events: none !important;
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        `;
    }
    
    // ✅ REPAINT IMEDIATO
    this.instance.revalidate(element);
    this.throttledRepaint();
}
```

### **3.5 Erros 5-15: Implementar Todas as Correções**

**Seguir exatamente as correções descritas em `RELATORIO_COMPLETO_ERROS_SENIOR_NIVEL.md` para cada erro.**

---

## 🎯 FASE 4: GARANTIAS OBRIGATÓRIAS

### **4.1 Zero Duplicações**

✅ **Garantir:**
- Nenhuma mensagem é enviada duas vezes
- Nenhum endpoint é criado duas vezes
- Nenhuma conexão é criada duas vezes
- Nenhum step é renderizado duas vezes

### **4.2 Zero Race Conditions**

✅ **Garantir:**
- Todas as operações assíncronas usam locks
- Todas as verificações de estado são atômicas
- Todas as inicializações aguardam completion
- Todas as renderizações são serializadas

### **4.3 Zero Conflitos Entre Modos**

✅ **Garantir:**
- Flow Engine ativo = Traditional Engine 100% bloqueado
- Traditional Engine ativo = Flow Engine 100% ignorado
- MessageRouter é único ponto de entrada
- Verificações são atômicas e consistentes

### **4.4 Drag Perfeito**

✅ **Garantir:**
- Cards se movem suavemente
- Endpoints acompanham cards
- Conexões se atualizam durante drag
- Snap-to-grid funciona corretamente
- Não há conflito com pan/zoom

### **4.5 Endpoints Sempre Visíveis**

✅ **Garantir:**
- Endpoints aparecem imediatamente após criação
- Endpoints permanecem visíveis após zoom/pan
- Endpoints permanecem visíveis após drag
- SVG overlay está sempre configurado corretamente

---

## 📦 ENTREGÁVEIS OBRIGATÓRIOS

### **1. FLOW_ENGINE_ROUTER_V7.js**
- MessageRouter completo
- Integração com Flow Engine e Traditional Engine
- Verificações atômicas
- Zero duplicações

### **2. FLOW_ENGINE_V6.js**
- Flow Engine completo
- Execução de steps
- Gerenciamento de estado
- Bloqueio de sistema tradicional

### **3. TRADITIONAL_ENGINE_V7.js**
- Traditional Engine com verificação de flow ativo
- Bloqueio quando flow está ativo
- Processamento tradicional quando flow inativo

### **4. FLOW_INIT_FIX.js**
- Correções dos 15 erros do frontend
- Inicialização robusta
- Zero race conditions

### **5. FLOW_EDITOR_FINAL.js**
- Versão final do flow_editor.js
- Sem duplicações
- Drag perfeito
- Endpoints sempre visíveis

### **6. bot_manager.py (modificações)**
- Integração com MessageRouter
- Verificações de flow ativo
- Bloqueio de sistema tradicional

### **7. templates/bot_config.html (modificações)**
- Correção do erro 1 (contentContainer)
- Integração com Flow Engine Router
- Inicialização correta

### **8. DOCUMENTACAO_V6_V7_COMPLETA.md**
- Arquitetura completa
- Fluxo de execução
- Garantias implementadas
- Testes realizados

---

## 🚨 REGRAS ABSOLUTAS (NÃO VIOLAR)

1. ✅ **NUNCA** assumir - sempre verificar no código
2. ✅ **NUNCA** fazer soluções fáceis ou gambiarras
3. ✅ **NUNCA** permitir que ambos os sistemas respondam
4. ✅ **NUNCA** criar endpoints duplicados
5. ✅ **NUNCA** permitir race conditions
6. ✅ **SEMPRE** usar MessageRouter como único ponto de entrada
7. ✅ **SEMPRE** verificar flow ativo antes de processar
8. ✅ **SEMPRE** garantir que contentContainer existe
9. ✅ **SEMPRE** forçar visibilidade de endpoints
10. ✅ **SEMPRE** testar antes de entregar

---

## ✅ CHECKLIST FINAL

Antes de entregar, verificar:

- [ ] Todos os arquivos foram lidos completamente
- [ ] MessageRouter implementado e funcionando
- [ ] Flow Engine implementado e funcionando
- [ ] Traditional Engine bloqueado quando flow ativo
- [ ] Todos os 15 erros corrigidos
- [ ] Zero duplicações de mensagens
- [ ] Zero duplicações de endpoints
- [ ] Zero race conditions
- [ ] Drag funciona perfeitamente
- [ ] Endpoints sempre visíveis
- [ ] Conexões funcionam corretamente
- [ ] Snap-to-grid funciona
- [ ] Zoom/Pan não quebra drag
- [ ] Sistema tradicional funciona quando flow inativo
- [ ] Flow Engine funciona quando ativo
- [ ] Documentação completa criada
- [ ] Testes realizados e passando

---

## 🎯 COMEÇAR AGORA

1. **Ler TODOS os arquivos listados na Fase 1**
2. **Implementar MessageRouter (Fase 2.1)**
3. **Implementar Flow Engine (Fase 2.2)**
4. **Implementar Traditional Engine (Fase 2.3)**
5. **Integrar no bot_manager.py (Fase 2.4)**
6. **Corrigir os 15 erros (Fase 3)**
7. **Garantir todas as garantias (Fase 4)**
8. **Entregar todos os entregáveis (Fase 5)**

**NÃO PULE ETAPAS. NÃO ASSUMA. IMPLEMENTE COMPLETO.**

---

**🚀 BOA SORTE. ENTREGUE UM SISTEMA PERFEITO.**

