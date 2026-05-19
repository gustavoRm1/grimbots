# 📐 MANUAL DE ARQUITETURA - FLOW EDITOR V7 PROFISSIONAL

**Data:** 2025-01-11  
**Versão:** V7 PROFISSIONAL  
**Status:** ✅ DOCUMENTAÇÃO COMPLETA

---

## 🏗️ ARQUITETURA GERAL

### Componentes Principais

1. **FlowEditor Class** (`static/js/flow_editor.js`)
   - Classe principal que gerencia todo o editor visual
   - Integra jsPlumb para conexões
   - Gerencia zoom, pan, drag, endpoints

2. **Alpine.js Context** (`templates/bot_config.html`)
   - Gerencia estado do fluxo (steps, connections)
   - Integra com backend via API
   - Controla modal de edição

3. **jsPlumb Instance**
   - Biblioteca externa para conexões visuais
   - Gerencia SVG overlay e endpoints
   - Renderiza conexões entre elementos

---

## 🔄 FLUXO DE INICIALIZAÇÃO

### Sequência de Inicialização (V7)

```
1. initVisualFlowEditor() [Alpine]
   ↓
2. new FlowEditor('flow-visual-canvas', alpineContext)
   ↓
3. FlowEditor.init() [async]
   ├─ setupCanvas()
   │  └─ Cria contentContainer
   ├─ waitForElement(contentContainer)
   │  └─ Aguarda estar no DOM
   ├─ setupJsPlumbAsync() [async]
   │  ├─ jsPlumb.newInstance({ Container: this.canvas })
   │  ├─ instance.setContainer(this.canvas)
   │  ├─ configureSVGOverlayWithRetry()
   │  └─ Retorna Promise
   └─ continueInit()
      ├─ enableZoom()
      ├─ enablePan()
      ├─ enableSelection()
      └─ renderAllSteps()
         └─ renderStep() para cada step
            └─ addEndpoints()
               └─ forceEndpointVisibility()
```

**Mudança Crítica V7:** Inicialização agora é **async/await**, eliminando race conditions.

---

## 🎯 CONTAINER JSPLUMB

### Estrutura de Containers

```
#flow-visual-canvas (this.canvas)
├─ Container do jsPlumb (SVG overlay criado aqui)
└─ .flow-canvas-content (this.contentContainer)
   ├─ Tem transform CSS (zoom/pan)
   └─ Contém .flow-step-block elements
```

**Regra Crítica V7:** 
- **jsPlumb Container:** `this.canvas` (SEM transform)
- **Content Container:** `this.contentContainer` (COM transform)

**Por quê?**
- SVG overlay do jsPlumb deve ser criado em container sem transform
- Se usar `contentContainer`, SVG pode não aparecer corretamente
- Sistema de coordenadas do jsPlumb fica distorcido

---

## 🔌 ENDPOINTS

### Tipos de Endpoints

1. **Input Endpoint** (Entrada)
   - UUID: `endpoint-left-{stepId}`
   - Cor: Verde (#10B981)
   - Posição: Esquerda do card
   - Tipo: `isTarget: true, isSource: false`

2. **Output Endpoint** (Saída Global)
   - UUID: `endpoint-right-{stepId}`
   - Cor: Branco (#FFFFFF)
   - Posição: Direita do card
   - Tipo: `isSource: true, isTarget: false`
   - **Apenas se não há botões**

3. **Button Endpoint** (Saída de Botão)
   - UUID: `endpoint-button-{stepId}-{index}`
   - Cor: Branco (#FFFFFF)
   - Posição: Direita de cada botão
   - Tipo: `isSource: true, isTarget: false`
   - **Apenas se há botões**

### Sistema Anti-Duplicação

```javascript
// Registry de endpoints por step
this.endpointRegistry = new Map(); // stepId -> Set<UUID>

// Lock de criação (previne race conditions)
this.endpointCreationLock = new Set(); // UUIDs sendo criados

// ensureEndpoint() verifica existência antes de criar
// preventEndpointDuplication() intercepta addEndpoint()
```

---

## 🎨 VISUAL E CSS

### Hierarquia de z-index

```
SVG Overlay: z-index: 10000
Endpoints: z-index: 10000
Cards: z-index: auto
Footer buttons: z-index: 10000
```

### CSS Crítico

```css
/* Canvas não deve ter transform */
#flow-visual-canvas {
    transform: none !important;
}

/* SVG overlay sempre visível */
#flow-visual-canvas svg {
    z-index: 10001 !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}

/* Endpoints sempre visíveis */
.jtk-endpoint {
    z-index: 10000 !important;
    pointer-events: auto !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}
```

---

## 🔄 EVENTOS E CALLBACKS

### Eventos jsPlumb

```javascript
// Conexão criada
instance.bind('connection', (info) => {
    // Salvar conexão no Map
    // Atualizar Alpine state
});

// Conexão removida
instance.bind('connectionDetached', (info) => {
    // Remover do Map
    // Atualizar Alpine state
});

// Duplo clique para remover
instance.bind('click', (conn, e) => {
    if (e.detail === 2) {
        removeConnection(conn);
    }
});
```

### Eventos Drag

```javascript
// Drag iniciado
draggableOptions.start = (params) => {
    // Garantir SVG overlay visível
};

// Durante drag
draggableOptions.drag = (params) => {
    // Revalidar endpoints
    // Repintar conexões
};

// Drag parado
draggableOptions.stop = (params) => {
    // Salvar posição
    // Revalidar tudo
    // Repintar tudo
};
```

---

## 🎯 ZOOM E PAN

### Zoom

- **Trigger:** Scroll + Ctrl (ou scroll direto)
- **Foco:** Ponto do cursor (não centro)
- **Range:** 0.2x a 4.0x
- **Transform:** Aplicado em `contentContainer`

### Pan

- **Trigger:** Botão direito do mouse
- **Estilo:** Figma-like
- **Transform:** Aplicado em `contentContainer`

### MutationObserver

- **Observa:** Mudanças em `contentContainer.style.transform`
- **Debounce:** 16ms (~60fps)
- **Flag:** `isRepainting` previne loops infinitos

---

## 🔗 CONEXÕES

### Estrutura de Conexões

```javascript
// Map de conexões
this.connections = new Map(); // connId -> Connection

// Formato connId:
// - Sem botões: `{stepId}-{targetId}-{type}`
// - Com botões: `button-{stepId}-{index}-{targetId}`

// Tipos de conexão:
// - 'next': Próximo passo
// - 'pending': Pendente
// - 'retry': Retry
```

### reconnectAll()

```javascript
// 1. Calcular conexões desejadas (do Alpine state)
// 2. Obter conexões existentes (do jsPlumb)
// 3. Remover conexões que não devem existir
// 4. Criar conexões que faltam
// 5. Retry automático para endpoints não prontos
```

---

## 🛡️ PROTEÇÕES E VALIDAÇÕES

### Race Conditions

- ✅ Inicialização async/await
- ✅ `waitForElement()` garante DOM pronto
- ✅ `endpointCreationLock` previne duplicação
- ✅ `isRepainting` previne loops

### Validações

- ✅ Verificar `this.instance` antes de usar
- ✅ Verificar `this.contentContainer` antes de usar
- ✅ Verificar elemento no DOM antes de criar endpoints
- ✅ Verificar endpoints existentes antes de criar

---

## 📊 PERFORMANCE

### Otimizações

1. **Debounce/Throttle**
   - MutationObserver: 16ms debounce
   - Repaint: requestAnimationFrame
   - Drag: requestAnimationFrame

2. **Lazy Loading**
   - Endpoints criados apenas quando necessário
   - Conexões criadas apenas quando necessário

3. **Caching**
   - `this.steps` Map para acesso rápido
   - `this.connections` Map para acesso rápido
   - `this.endpointRegistry` para verificação rápida

---

## 🔧 FUNÇÕES CRÍTICAS

### `forceEndpointVisibility()`

Garante que endpoint e círculo SVG estão visíveis e interativos.

**Fluxo:**
1. Verificar canvas existe
2. Buscar círculo SVG (canvas ou SVG pai)
3. Configurar atributos SVG (fill, stroke, r)
4. Garantir SVG pai visível
5. Forçar repaint
6. Verificar visibilidade após configuração

### `setupJsPlumbAsync()`

Inicializa jsPlumb de forma assíncrona e robusta.

**Fluxo:**
1. Verificar contentContainer existe
2. Criar instância jsPlumb com `this.canvas` como container
3. Configurar defaults
4. Configurar eventos
5. Configurar SVG overlay com retry
6. Retornar Promise

### `waitForElement()`

Aguarda elemento estar no DOM.

**Fluxo:**
1. Verificar elemento existe
2. Verificar já está no DOM
3. Polling a cada 50ms até timeout
4. Retornar Promise

---

## 🎯 INTEGRAÇÃO COM ALPINE.JS

### Estado Gerenciado pelo Alpine

```javascript
config.flow_enabled        // Boolean
config.flow_steps         // Array<Step>
config.flow_start_step_id // String
```

### Métodos Expostos

```javascript
// No Alpine context
initVisualFlowEditor()    // Inicializa editor
addFlowStep()            // Adiciona novo step
openStepModal(stepId)    // Abre modal de edição
closeStepModal()         // Fecha modal
```

### Comunicação FlowEditor ↔ Alpine

```javascript
// FlowEditor → Alpine
this.alpine.config.flow_steps = [...];
this.updateStepPosition(stepId, position);

// Alpine → FlowEditor
window.flowEditor.renderAllSteps();
window.flowEditor.reconnectAll();
```

---

## 📝 NOTAS TÉCNICAS

### jsPlumb Version
- **Versão:** 2.15.6 (CDN)
- **Documentação:** https://jsplumbtoolkit.com/

### Alpine.js Version
- **Versão:** 3.x (CDN)
- **Documentação:** https://alpinejs.dev/

### Browser Compatibility
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ⚠️ Safari (testar se necessário)

---

## 🚨 REGRAS CRÍTICAS

1. **Container jsPlumb:** SEMPRE `this.canvas`, NUNCA `contentContainer`
2. **Inicialização:** SEMPRE async/await, NUNCA setTimeout fixos
3. **Endpoints:** SEMPRE usar `forceEndpointVisibility()` após criar
4. **Draggable:** SEMPRE usar `this.canvas` como containment
5. **SVG Overlay:** SEMPRE buscar em `this.canvas`, NUNCA em `contentContainer`

---

**Documento gerado em:** 2025-01-11  
**Última atualização:** 2025-01-11

