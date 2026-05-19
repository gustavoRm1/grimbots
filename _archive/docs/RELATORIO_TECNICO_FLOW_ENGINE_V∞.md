# 🔥 RELATÓRIO TÉCNICO COMPLETO - FLOW ENGINE V∞
## Auditoria Profunda e Plano Arquitetural

**Data:** 2025-01-XX  
**Versão:** V∞ (Infinity)  
**Status:** Auditoria Completa - Aguardando Aprovação para Implementação

---

## 📋 SUMÁRIO EXECUTIVO

Este documento apresenta uma auditoria completa do sistema atual de Flow Engine, identificando:
- Arquitetura atual detectada
- Pontos de integração existentes
- Conflitos entre modo tradicional e modo fluxo
- Gaps e problemas identificados
- Proposta de arquitetura final V∞

---

## 1. ARQUITETURA ATUAL DETECTADA

### 1.1 Frontend - Editor Visual

#### Arquivos Principais
- `templates/bot_config.html` (linhas 2674-2905)
- `static/js/flow_editor.js` (~5400 linhas)
- `static/js/FLOW_ENGINE_V8.js` (~540 linhas)
- `static/js/FLOW_ENGINE_ROUTER_V8.js` (~440 linhas)

#### Componentes Frontend

**1.1.1 Alpine.js Component (`botConfigApp`)**
```javascript
{
    config: {
        flow_enabled: boolean,
        flow_steps: Array<Step>,
        flow_start_step_id: string | null
    },
    activeTab: 'flow' | 'welcome' | 'settings',
    showStepModal: boolean,
    editingStep: Step | null
}
```

**Funções Principais:**
- `loadConfig()` - Carrega config da API
- `saveConfig()` - Salva config (debounce 600ms)
- `addFlowStep()` - Adiciona novo step
- `removeFlowStep(stepId)` - Remove step
- `editStep(stepId)` - Abre modal de edição
- `saveStep()` - Salva edição do step
- `initVisualFlowEditor()` - Inicializa FlowEditor

**1.1.2 FlowEditor Class (`flow_editor.js`)**

**Características:**
- ✅ jsPlumb 2.15.6 integrado
- ✅ Zoom com foco no mouse (Ctrl+Scroll)
- ✅ Pan com botão direito (estilo Figma)
- ✅ Drag & Drop de steps
- ✅ Conexões visuais entre steps
- ✅ Grid SVG dinâmico
- ✅ Sistema de seleção (única, múltipla, lasso)
- ✅ Undo/Redo (HistoryManager)
- ✅ Sistema anti-duplicação de endpoints
- ✅ Self-healing (FlowSelfHealer)
- ✅ Consistency Engine (FlowConsistencyEngine)

**Estrutura de Step:**
```javascript
{
    id: string,                    // "step_1234567890"
    type: 'message' | 'payment' | 'access' | 'content' | 'audio' | 'video',
    order: number,                  // Ordem sequencial
    config: {
        message?: string,
        media_url?: string,
        media_type?: 'video' | 'photo',
        audio_url?: string,
        price?: number,             // Para payment
        product_name?: string,      // Para payment
        button_text?: string,       // Para payment
        access_link?: string,       // Para access
        custom_buttons?: Array<{
            text: string,
            target_step: string    // ID do step destino
        }>
    },
    connections: {
        next?: string,              // ID do próximo step
        pending?: string,            // ID do step se payment pendente
        retry?: string               // ID do step para retry
    },
    conditions: Array<Condition>,
    delay_seconds: number,
    position: { x: number, y: number },
    title?: string
}
```

**1.1.3 Canvas e Renderização**

**Estrutura DOM:**
```html
<div id="flow-visual-canvas">
    <svg class="flow-background-svg"><!-- Grid SVG --></svg>
    <div class="flow-canvas-content"><!-- Transform container -->
        <div class="flow-step-block" data-step-id="step_123">
            <!-- Step card -->
        </div>
    </div>
</div>
```

**Zoom/Pan:**
- Zoom: `transform: scale(zoomLevel)` no `contentContainer`
- Pan: `transform: translate(pan.x, pan.y)` no `contentContainer`
- Foco no mouse: Calcula coordenadas do mundo antes/after zoom

**Endpoints:**
- Entrada: `endpoint-left-{stepId}` (esquerda)
- Saída padrão: `endpoint-right-{stepId}` (direita)
- Saída por botão: `endpoint-button-{stepId}-{index}` (por botão)
- Condition: `endpoint-true-{stepId}`, `endpoint-false-{stepId}`

---

### 1.2 Backend - Execução de Fluxo

#### Arquivos Principais
- `bot_manager.py` (linhas 3055-3439, 3197-3439)
- `models.py` (linhas 300-494)
- `flow_engine_router_v8.py` (~440 linhas)
- `app.py` (linhas 5565-5658, 11607-11624)

#### Modelos de Dados

**1.2.1 BotConfig Model**
```python
class BotConfig(db.Model):
    flow_enabled = db.Column(db.Boolean, default=False, index=True)
    flow_steps = db.Column(db.Text, nullable=True)  # JSON array
    flow_start_step_id = db.Column(db.String(50), nullable=True, index=True)
    
    def get_flow_steps(self) -> List[Dict]:
        # Parse JSON string para lista
    
    def set_flow_steps(self, steps: List[Dict]):
        # Serializa lista para JSON string
```

**1.2.2 Payment Model**
```python
class Payment(db.Model):
    flow_step_id = db.Column(db.String(50), nullable=True, index=True)
    # Rastreia qual step do fluxo gerou este payment
```

#### Funções de Execução

**1.2.1 `_execute_flow()` (bot_manager.py:3055)**
```python
def _execute_flow(bot_id, token, config, chat_id, telegram_user_id):
    """
    ✅ Executa fluxo visual configurado
    ✅ Fallback para welcome_message se fluxo inválido
    ✅ Híbrido: Síncrono até payment, assíncrono após callback
    ✅ Usa flow_start_step_id ou fallback automático
    ✅ Snapshot da config no início (evita mudanças durante execução)
    """
```

**Fluxo de Execução:**
1. Parse `flow_steps` (JSON string → lista)
2. Validação: verifica se fluxo não está vazio
3. Cria snapshot da config (Redis, expira em 24h)
4. Identifica step inicial:
   - Prioridade 1: `flow_start_step_id`
   - Prioridade 2: step com `order=1`
   - Prioridade 3: primeiro step (menor order)
5. Chama `_execute_flow_recursive()` com step inicial

**1.2.2 `_execute_flow_recursive()` (bot_manager.py:3197)**
```python
def _execute_flow_recursive(
    bot_id, token, config, chat_id, telegram_user_id, step_id,
    recursion_depth=0, visited_steps=set(), flow_snapshot=None
):
    """
    ✅ Executa step recursivamente
    ✅ Proteção contra loops (max 50 steps, visited_steps)
    ✅ Usa snapshot se disponível
    """
```

**Fluxo de Execução:**
1. Validação: profundidade máxima (50), detecção de loops
2. Busca step no snapshot ou config atual
3. Executa step baseado no tipo:
   - `message`: Envia mensagem + mídia + áudio
   - `payment`: Gera PIX, salva `payment.flow_step_id`, **PARA AQUI** (aguarda callback)
   - `access`: Envia link de acesso
4. Delay (`delay_seconds`)
5. Determina próximo step:
   - Se `payment`: para e aguarda callback `verify_`
   - Se `connections.next`: continua recursivamente
6. Recursão: chama `_execute_flow_recursive()` com próximo step

**1.2.3 `_handle_verify_payment()` (bot_manager.py:5341)**

**⚠️ PROBLEMA CRÍTICO IDENTIFICADO:**
Esta função **NÃO está integrada com o flow**. Ela apenas:
- Verifica status do pagamento
- Envia mensagem de acesso se pago
- Envia mensagem pendente se não pago
- Processa upsells

**FALTA:**
- ❌ Verificar se `payment.flow_step_id` existe
- ❌ Buscar step no fluxo
- ❌ Executar próximo step baseado em `connections.next` ou `connections.pending`
- ❌ Continuar fluxo após verificação

---

### 1.3 Integração com Sistema Tradicional

#### MessageRouter V8 (`flow_engine_router_v8.py`)

**Arquitetura:**
```python
class MessageRouterV8:
    def process_message(...):
        # 1. Adquire lock atômico (Redis)
        # 2. Verifica se flow está ativo
        # 3. Roteia para Flow Engine OU Traditional Engine
```

**Verificação de Flow Ativo:**
```python
def check_flow_active_atomic(bot_id, config) -> bool:
    flow_enabled = config.get('flow_enabled', False)
    flow_steps = config.get('flow_steps', [])
    return flow_enabled and flow_steps and len(flow_steps) > 0
```

**⚠️ PROBLEMA IDENTIFICADO:**
O MessageRouter V8 existe mas **NÃO está sendo usado** no `bot_manager.py`. O código atual em `_process_telegram_update()` (linha 1274) tem um try/except que tenta usar o router, mas se falhar, faz fallback para método tradicional diretamente.

**Integração Atual:**
```python
# bot_manager.py:1274
try:
    router = get_message_router(self)
    router.process_message(...)
except Exception as router_error:
    # Fallback: processa via tradicional
    self._handle_start_command(...)
```

---

### 1.4 Pontos de Entrada

#### 1.4.1 `/start` Command
**Localização:** `bot_manager.py:1274` → `_handle_start_command()`

**Fluxo Atual:**
1. Verifica se `flow_enabled` e `flow_steps` existem
2. Se sim: chama `_execute_flow()`
3. Se não: envia `welcome_message` tradicional

**Código:**
```python
# bot_manager.py:1683-1711
if is_flow_active:
    logger.info("🚫 Fluxo visual ativo - BLOQUEANDO welcome_message")
    try:
        self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
    except Exception as e:
        logger.error(f"❌ Erro ao executar fluxo: {e}")
    return  # ✅ SAIR SEM ENVIAR welcome_message
```

#### 1.4.2 Callback `verify_`
**Localização:** `bot_manager.py:4153` → `_handle_callback_query()` → `_handle_verify_payment()`

**Fluxo Atual:**
1. Busca payment no banco
2. Verifica status (paid/pending)
3. Se paid: envia acesso
4. Se pending: envia mensagem pendente
5. **❌ NÃO continua o fluxo**

**FALTA:**
- Verificar `payment.flow_step_id`
- Buscar step no fluxo
- Executar próximo step (`connections.next` se paid, `connections.pending` se pending)

#### 1.4.3 Callback de Botões Customizados
**Localização:** `bot_manager.py:4022` → `_handle_callback_query()`

**Fluxo Atual:**
- Processa callbacks tradicionais: `buy_`, `bump_yes_`, `rmkt_`
- **❌ NÃO processa callbacks de botões customizados do flow**

**FALTA:**
- Detectar callback de botão customizado (formato: `flow_{stepId}_{buttonIndex}`)
- Buscar step no fluxo
- Executar step destino (`config.custom_buttons[buttonIndex].target_step`)

---

## 2. CONFLITOS IDENTIFICADOS

### 2.1 Conflito: Duplicação de Mensagens

**Problema:**
- Sistema tradicional pode enviar `welcome_message` mesmo com flow ativo
- Flow pode executar steps que enviam mensagens duplicadas

**Localização:**
- `bot_manager.py:1683` - `_send_welcome_message_only()` verifica flow, mas pode haver race condition

**Solução Proposta:**
- ✅ Lock atômico já existe no MessageRouter V8
- ✅ Verificação de flow ativo antes de enviar welcome_message
- ⚠️ **FALTA:** Garantir que MessageRouter V8 está sendo usado corretamente

### 2.2 Conflito: Estado do Fluxo

**Problema:**
- Flow não mantém estado de qual step o usuário está
- Após payment, não sabe qual step executar depois

**Solução Atual (Parcial):**
- ✅ `payment.flow_step_id` rastreia qual step gerou o payment
- ❌ `_handle_verify_payment()` não usa `payment.flow_step_id` para continuar fluxo

**Solução Proposta:**
- Usar `payment.flow_step_id` em `_handle_verify_payment()`
- Buscar step no fluxo
- Executar próximo step baseado em `connections.next` ou `connections.pending`

### 2.3 Conflito: Callbacks de Botões

**Problema:**
- Botões customizados do flow não têm callbacks implementados
- Sistema tradicional processa apenas callbacks hardcoded (`buy_`, `bump_yes_`, etc.)

**Solução Proposta:**
- Criar formato de callback para botões customizados: `flow_{stepId}_{buttonIndex}`
- Adicionar handler em `_handle_callback_query()`
- Executar step destino do botão

---

## 3. GAPS E PROBLEMAS CRÍTICOS

### 3.1 ❌ CRÍTICO: `_handle_verify_payment()` Não Continua Flow

**Problema:**
Após verificar pagamento, o sistema não continua o fluxo. Ele apenas envia mensagem de acesso ou pendente, mas não executa o próximo step do fluxo.

**Impacto:**
- Fluxos com steps após payment não funcionam
- Usuário fica "preso" após pagamento

**Solução Necessária:**
```python
def _handle_verify_payment(...):
    # ... código existente de verificação ...
    
    # ✅ NOVO: Verificar se payment tem flow_step_id
    if payment.flow_step_id:
        bot = payment.bot
        config = bot.config.to_dict()
        
        if config.get('flow_enabled') and config.get('flow_steps'):
            # Buscar step no fluxo
            step = self._find_step_by_id(config['flow_steps'], payment.flow_step_id)
            
            if step:
                # Determinar próximo step baseado em status
                if payment.status == 'paid':
                    next_step_id = step.get('connections', {}).get('next')
                else:
                    next_step_id = step.get('connections', {}).get('pending')
                
                if next_step_id:
                    # Continuar fluxo
                    self._execute_flow_recursive(
                        bot_id, token, config, chat_id, telegram_user_id,
                        next_step_id, recursion_depth=0, visited_steps=set()
                    )
                    return  # ✅ Sair sem executar código tradicional
    
    # ✅ FALLBACK: Comportamento tradicional (não quebra nada)
    if payment.status == 'paid':
        self._send_access(...)
    else:
        self._send_pending_message(...)
```

### 3.2 ❌ CRÍTICO: Botões Customizados Não Funcionam

**Problema:**
Botões customizados criados no flow não têm callbacks implementados. Quando usuário clica, nada acontece.

**Solução Necessária:**
1. Modificar geração de botões em `_execute_flow_recursive()`:
```python
# Para steps com custom_buttons
buttons = []
for idx, btn in enumerate(step.config.get('custom_buttons', [])):
    buttons.append({
        'text': btn['text'],
        'callback_data': f'flow_{step_id}_{idx}'  # ✅ NOVO formato
    })
```

2. Adicionar handler em `_handle_callback_query()`:
```python
if callback_data.startswith('flow_'):
    # Parse: flow_{stepId}_{buttonIndex}
    parts = callback_data.split('_')
    if len(parts) == 3:
        step_id = parts[1]
        button_index = int(parts[2])
        
        # Buscar step no fluxo
        config = bot.config.to_dict()
        step = self._find_step_by_id(config['flow_steps'], step_id)
        
        if step and step.config.get('custom_buttons'):
            target_step_id = step.config['custom_buttons'][button_index].get('target_step')
            
            if target_step_id:
                # Executar step destino
                self._execute_flow_recursive(
                    bot_id, token, config, chat_id, telegram_user_id,
                    target_step_id, recursion_depth=0, visited_steps=set()
                )
                return
```

### 3.3 ⚠️ MÉDIO: MessageRouter V8 Não Está Sendo Usado

**Problema:**
O MessageRouter V8 existe mas não está sendo usado corretamente. O código atual tem try/except que faz fallback para método tradicional.

**Solução Necessária:**
- Garantir que MessageRouter V8 está sendo usado em todos os pontos de entrada
- Remover fallback direto para método tradicional
- Usar router como único ponto de entrada

### 3.4 ⚠️ MÉDIO: Estado do Fluxo Não É Persistido

**Problema:**
O fluxo não mantém estado de qual step o usuário está. Se usuário enviar mensagem de texto durante o fluxo, o sistema não sabe qual step processar.

**Solução Atual (Parcial):**
- Redis: `flow_current_step:{bot_id}:{telegram_user_id}` (mencionado no FLOW_ENGINE_V8.js)
- **❌ NÃO está sendo usado no backend Python**

**Solução Proposta:**
- Salvar step atual no Redis após cada execução de step
- Em mensagens de texto, buscar step atual e processar no contexto

---

## 4. PONTOS QUE NÃO PODEM SER MEXIDOS

### 4.1 Sistema Tradicional (Modo Welcome)
- ✅ **NÃO alterar** lógica de `welcome_message`
- ✅ **NÃO alterar** lógica de `main_buttons`, `downsells`, `upsells`
- ✅ **NÃO alterar** callbacks existentes: `buy_`, `bump_yes_`, `rmkt_`
- ✅ **NÃO alterar** estrutura de `BotConfig` (apenas adicionar campos se necessário)

### 4.2 API de Configuração
- ✅ **NÃO alterar** endpoints `/api/bots/<id>/config` (GET/PUT)
- ✅ **NÃO alterar** estrutura de resposta JSON
- ✅ **NÃO alterar** validações existentes

### 4.3 Modelos de Dados
- ✅ **NÃO alterar** estrutura de `BotConfig` (apenas adicionar campos)
- ✅ **NÃO alterar** estrutura de `Payment` (apenas usar `flow_step_id` existente)
- ✅ **NÃO alterar** estrutura de `BotUser`

---

## 5. PROPOSTA DE ARQUITETURA FINAL V∞

### 5.1 Princípios Arquiteturais

1. **Separação Total:** Flow e Traditional são mutuamente exclusivos
2. **Fallback Seguro:** Se flow falhar, usa traditional (não quebra nada)
3. **Estado Stateless:** Usa `payment.flow_step_id` para rastrear progresso
4. **Atomicidade:** Locks Redis para prevenir race conditions
5. **Backward Compatible:** Não quebra bots existentes

### 5.2 Fluxo de Execução Proposto

#### 5.2.1 Comando `/start`
```
1. MessageRouter V8 verifica flow ativo
2. Se flow ativo:
   a. _execute_flow() → _execute_flow_recursive()
   b. Executa steps até encontrar payment
   c. Para e aguarda callback verify_
3. Se flow inativo:
   a. _handle_start_command() tradicional
   b. Envia welcome_message
```

#### 5.2.2 Callback `verify_`
```
1. _handle_verify_payment() verifica payment
2. Se payment.flow_step_id existe:
   a. Busca step no fluxo
   b. Determina próximo step (next se paid, pending se não)
   c. _execute_flow_recursive() com próximo step
   d. Retorna (não executa código tradicional)
3. Se payment.flow_step_id não existe:
   a. Comportamento tradicional (fallback)
```

#### 5.2.3 Callback de Botão Customizado
```
1. _handle_callback_query() detecta callback "flow_{stepId}_{buttonIndex}"
2. Busca step no fluxo
3. Busca target_step do botão
4. _execute_flow_recursive() com target_step
```

#### 5.2.4 Mensagem de Texto Durante Flow
```
1. MessageRouter V8 verifica flow ativo
2. Busca step atual no Redis: flow_current_step:{bot_id}:{telegram_user_id}
3. Se step atual existe:
   a. Processa mensagem no contexto do step
   b. Avalia condições (se step é condition)
   c. Executa próximo step baseado em resultado
4. Se step atual não existe:
   a. Reinicia fluxo do início (_execute_flow())
```

### 5.3 Estrutura de Dados Final

#### 5.3.1 Step Structure (Final)
```javascript
{
    id: string,
    type: 'message' | 'payment' | 'access' | 'content' | 'audio' | 'video' | 'condition',
    order: number,
    config: {
        // ... campos existentes ...
        custom_buttons: Array<{
            text: string,
            target_step: string
        }>
    },
    connections: {
        next?: string,           // Próximo step (sequencial)
        pending?: string,         // Step se payment pendente
        retry?: string,           // Step para retry
        true?: string,            // Step se condition true
        false?: string            // Step se condition false
    },
    conditions: Array<{
        type: 'text_validation' | 'payment_status' | 'user_attribute',
        validation: 'any' | 'exact' | 'contains',
        value?: string,
        target_step: string
    }>,
    delay_seconds: number,
    position: { x: number, y: number },
    title?: string
}
```

### 5.4 Integrações Necessárias

#### 5.4.1 Backend - `bot_manager.py`

**Modificações Necessárias:**
1. ✅ Integrar `_handle_verify_payment()` com flow
2. ✅ Adicionar handler para callbacks de botões customizados
3. ✅ Garantir que MessageRouter V8 está sendo usado
4. ✅ Salvar step atual no Redis após cada execução
5. ✅ Processar mensagens de texto no contexto do step atual

#### 5.4.2 Frontend - `flow_editor.js`

**Melhorias Necessárias:**
1. ✅ Adicionar suporte para step tipo `condition`
2. ✅ Melhorar preview de steps (mostrar mais informações)
3. ✅ Adicionar validação de conexões (evitar loops)
4. ✅ Adicionar botão "Testar Fluxo" (simulação)

#### 5.4.3 API - `app.py`

**Modificações Necessárias:**
1. ✅ Validar fluxo antes de salvar (verificar loops, steps órfãos)
2. ✅ Endpoint para testar fluxo (simulação)
3. ✅ Endpoint para obter estado atual do fluxo de um usuário

---

## 6. CHECKLIST DE IMPLEMENTAÇÃO

### 6.1 Backend (Python)

- [ ] Integrar `_handle_verify_payment()` com flow
- [ ] Adicionar handler para callbacks `flow_{stepId}_{buttonIndex}`
- [ ] Garantir uso do MessageRouter V8
- [ ] Salvar step atual no Redis
- [ ] Processar mensagens de texto no contexto do step
- [ ] Adicionar suporte para step tipo `condition`
- [ ] Validação de fluxo (detectar loops, steps órfãos)

### 6.2 Frontend (JavaScript)

- [ ] Adicionar step tipo `condition` no editor
- [ ] Melhorar preview de steps
- [ ] Validação de conexões (evitar loops)
- [ ] Botão "Testar Fluxo"
- [ ] Melhorar feedback visual de erros

### 6.3 API (Flask)

- [ ] Validar fluxo antes de salvar
- [ ] Endpoint `/api/bots/<id>/flow/test` (simulação)
- [ ] Endpoint `/api/bots/<id>/flow/state/<user_id>` (estado atual)

### 6.4 Testes

- [ ] Teste: Fluxo simples (message → payment → access)
- [ ] Teste: Fluxo com condições
- [ ] Teste: Fluxo com botões customizados
- [ ] Teste: Fluxo com loops (deve detectar e prevenir)
- [ ] Teste: Fallback para traditional se flow falhar
- [ ] Teste: Race conditions (múltiplas mensagens simultâneas)

---

## 7. PRÓXIMOS PASSOS

1. **Aprovação:** Revisar este relatório e aprovar arquitetura proposta
2. **Implementação Backend:** Começar por `_handle_verify_payment()` e callbacks
3. **Implementação Frontend:** Adicionar step `condition` e melhorias
4. **Testes:** Testar cada funcionalidade isoladamente
5. **Integração:** Integrar tudo e testar fluxos completos
6. **Documentação:** Documentar uso do Flow Engine para usuários finais

---

## 8. REFERÊNCIAS

- jsPlumb Chatbot Demo: https://github.com/jsplumb-demonstrations/chatbot
- jsPlumb Documentation: https://docs.jsplumbtoolkit.com/
- Alpine.js Documentation: https://alpinejs.dev/
- Flask Documentation: https://flask.palletsprojects.com/

---

**FIM DO RELATÓRIO TÉCNICO**


