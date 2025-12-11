# 🎯 ANÁLISE: Implementação de Events System para V2.0

**Data:** 2025-12-11  
**Versão Atual:** V7 (70% implementado)  
**Meta V2.0:** 95% (Nível Typebot/ManyChat)

---

## 🔍 SITUAÇÃO ATUAL

### **Documentação Fornecida:**
- ✅ **jsPlumb Toolkit Events** (Model Events + UI Events)
- ✅ **Event Binding Methods** (`bind()`, declarative binding)
- ✅ **Lista completa de eventos**

### **Nosso Projeto:**
- ✅ **jsPlumb Community Edition 2.15.6** (não Toolkit)
- ✅ **Alguns eventos já implementados** (`connection`, `connectionDetached`, `click`)
- ❌ **Muitos eventos faltando** (`endpoint:click`, `canvas:click`, `drag:start`, etc.)

---

## ⚠️ LIMITAÇÃO

### **jsPlumb Toolkit Events NÃO estão disponíveis**

**Por quê?**
- `toolkit.bind(EVENT_NODE_ADDED, ...)` são métodos do **Toolkit**
- Estamos usando **Community Edition** (não tem Toolkit)
- Precisamos usar **jsPlumb Community Edition events** + implementar manualmente

**Consequência:**
- ❌ **NÃO podemos usar** eventos do Toolkit diretamente
- ✅ **PODEMOS usar** eventos do Community Edition
- ✅ **PODEMOS implementar** eventos customizados manualmente

---

## ✅ EVENTOS DISPONÍVEIS NO COMMUNITY EDITION

### **Eventos jsPlumb Community Edition 2.15.6:**

```javascript
// Conexões
instance.bind('connection', (info) => { ... });           // ✅ JÁ IMPLEMENTADO
instance.bind('connectionDetached', (info) => { ... });   // ✅ JÁ IMPLEMENTADO
instance.bind('click', (conn, e) => { ... });             // ✅ JÁ IMPLEMENTADO

// Endpoints
instance.bind('endpointClick', (endpoint, e) => { ... });  // ❌ FALTA
instance.bind('endpointDblClick', (endpoint, e) => { ... }); // ❌ FALTA

// Drag
instance.bind('drag', (params) => { ... });               // ❌ FALTA (parcial)
instance.bind('dragStart', (params) => { ... });          // ❌ FALTA
instance.bind('dragStop', (params) => { ... });          // ❌ FALTA

// Canvas
// Não há evento nativo - precisamos implementar manualmente
```

---

## 📊 COMPARAÇÃO: Toolkit vs. Community Edition

| Evento Toolkit | Community Edition | Status |
|----------------|-------------------|--------|
| `node:added` | ❌ Não existe | ⚠️ **Implementar manualmente** |
| `node:removed` | ❌ Não existe | ⚠️ **Implementar manualmente** |
| `node:updated` | ❌ Não existe | ⚠️ **Implementar manualmente** |
| `edge:added` | ✅ `connection` | ✅ **JÁ IMPLEMENTADO** |
| `edge:removed` | ✅ `connectionDetached` | ✅ **JÁ IMPLEMENTADO** |
| `endpoint:click` | ⚠️ `endpointClick` (nome diferente) | ❌ **FALTA** |
| `canvas:click` | ❌ Não existe | ⚠️ **Implementar manualmente** |
| `drag:start` | ⚠️ `dragStart` (nome diferente) | ❌ **FALTA** |
| `drag:move` | ⚠️ `drag` (nome diferente) | ⚠️ **PARCIAL** |
| `drag:stop` | ⚠️ `dragStop` (nome diferente) | ❌ **FALTA** |

---

## ✅ IMPLEMENTAÇÃO COMPLETA PARA V2.0

### **Arquivo:** `static/js/flow_editor.js`

#### **1. Eventos jsPlumb Community Edition (Adicionar em `setupJsPlumbAsync()`):**

```javascript
setupJsPlumbAsync() {
    // ... código existente ...
    
    // ✅ JÁ IMPLEMENTADO
    this.instance.bind('connection', (info) => this.onConnectionCreated(info));
    this.instance.bind('connectionDetached', (info) => this.onConnectionDetached(info));
    this.instance.bind('click', (conn, e) => {
        if (e.detail === 2) {
            this.removeConnection(conn);
        }
    });
    
    // ❌ ADICIONAR - Endpoint Events
    this.instance.bind('endpointClick', (endpoint, e) => {
        this.onEndpointClick(endpoint, e);
    });
    
    this.instance.bind('endpointDblClick', (endpoint, e) => {
        this.onEndpointDblClick(endpoint, e);
    });
    
    // ❌ ADICIONAR - Drag Events
    this.instance.bind('dragStart', (params) => {
        this.onDragStart(params);
    });
    
    this.instance.bind('drag', (params) => {
        this.onDragMove(params);
    });
    
    this.instance.bind('dragStop', (params) => {
        this.onDragStop(params);
    });
}
```

#### **2. Eventos Customizados (Implementar Manualmente):**

```javascript
// Canvas Click - Implementar manualmente
enableCanvasEvents() {
    this.canvas.addEventListener('click', (e) => {
        // Apenas se clicou no canvas (não em step ou endpoint)
        if (e.target === this.canvas || e.target === this.contentContainer) {
            this.onCanvasClick(e);
        }
    }, true);
}

// Node Events - Implementar manualmente
enableNodeEvents() {
    // node:added - Disparar quando renderStep() é chamado
    // node:removed - Disparar quando deleteStep() é chamado
    // node:updated - Disparar quando updateStep() é chamado
}

// Edge Events - Já temos connection/connectionDetached
// Mas podemos adicionar edge:moved, edge:pathEdited
```

#### **3. Handlers de Eventos:**

```javascript
// Endpoint Click Handler
onEndpointClick(endpoint, e) {
    e.stopPropagation();
    const stepId = endpoint.data?.stepId;
    const endpointType = endpoint.data?.endpointType;
    
    console.log('🔵 Endpoint clicked:', { stepId, endpointType });
    
    // Disparar evento customizado
    this.emit('endpoint:click', {
        endpoint,
        stepId,
        endpointType,
        originalEvent: e
    });
}

// Endpoint Double Click Handler
onEndpointDblClick(endpoint, e) {
    e.stopPropagation();
    const stepId = endpoint.data?.stepId;
    const endpointType = endpoint.data?.endpointType;
    
    console.log('🔵 Endpoint double clicked:', { stepId, endpointType });
    
    // Disparar evento customizado
    this.emit('endpoint:dblclick', {
        endpoint,
        stepId,
        endpointType,
        originalEvent: e
    });
}

// Canvas Click Handler
onCanvasClick(e) {
    console.log('🔵 Canvas clicked');
    
    // Disparar evento customizado
    this.emit('canvas:click', {
        x: e.clientX,
        y: e.clientY,
        originalEvent: e
    });
}

// Drag Start Handler
onDragStart(params) {
    const stepId = params.el?.dataset?.stepId;
    
    console.log('🔵 Drag started:', { stepId });
    
    // Adicionar classe CSS
    if (params.el) {
        params.el.classList.add('jtk-surface-element-dragging');
    }
    
    // Disparar evento customizado
    this.emit('drag:start', {
        stepId,
        element: params.el,
        position: params.pos,
        originalParams: params
    });
}

// Drag Move Handler
onDragMove(params) {
    const stepId = params.el?.dataset?.stepId;
    
    // Disparar evento customizado
    this.emit('drag:move', {
        stepId,
        element: params.el,
        position: params.pos,
        originalParams: params
    });
}

// Drag Stop Handler
onDragStop(params) {
    const stepId = params.el?.dataset?.stepId;
    
    console.log('🔵 Drag stopped:', { stepId });
    
    // Remover classe CSS
    if (params.el) {
        params.el.classList.remove('jtk-surface-element-dragging');
        params.el.classList.add('jtk-most-recently-dragged');
        setTimeout(() => {
            params.el.classList.remove('jtk-most-recently-dragged');
        }, 1000);
    }
    
    // Disparar evento customizado
    this.emit('drag:stop', {
        stepId,
        element: params.el,
        position: params.pos,
        originalParams: params
    });
}
```

#### **4. Sistema de Eventos Customizado (Event Emitter):**

```javascript
// Adicionar ao constructor
constructor(canvasId, alpineContext) {
    // ... código existente ...
    
    // Event System
    this.eventListeners = new Map(); // eventName -> Set<listeners>
}

// Emitir evento customizado
emit(eventName, data) {
    const listeners = this.eventListeners.get(eventName);
    if (listeners) {
        listeners.forEach(listener => {
            try {
                listener(data);
            } catch (e) {
                console.error(`❌ Erro em listener de ${eventName}:`, e);
            }
        });
    }
}

// Registrar listener
on(eventName, listener) {
    if (!this.eventListeners.has(eventName)) {
        this.eventListeners.set(eventName, new Set());
    }
    this.eventListeners.get(eventName).add(listener);
    
    // Retornar função para remover listener
    return () => {
        this.off(eventName, listener);
    };
}

// Remover listener
off(eventName, listener) {
    const listeners = this.eventListeners.get(eventName);
    if (listeners) {
        listeners.delete(listener);
    }
}

// Remover todos os listeners de um evento
removeAllListeners(eventName) {
    if (eventName) {
        this.eventListeners.delete(eventName);
    } else {
        this.eventListeners.clear();
    }
}
```

#### **5. Node Events (Implementar Manualmente):**

```javascript
// Em renderStep() - Disparar node:added
renderStep(step) {
    // ... código existente ...
    
    // Disparar evento node:added
    this.emit('node:added', {
        stepId: step.id,
        step: step,
        element: stepElement
    });
}

// Em deleteStep() - Disparar node:removed
deleteStep(stepId) {
    // ... código existente ...
    
    // Disparar evento node:removed
    this.emit('node:removed', {
        stepId: stepId
    });
}

// Em updateStep() - Disparar node:updated
updateStep(stepId, updates) {
    // ... código existente ...
    
    // Disparar evento node:updated
    this.emit('node:updated', {
        stepId: stepId,
        updates: updates,
        step: this.alpine?.config?.flow_steps?.find(s => s.id === stepId)
    });
}
```

---

## 📋 LISTA COMPLETA DE EVENTOS PARA V2.0

### **✅ JÁ IMPLEMENTADOS:**
- ✅ `connection` - Conexão criada
- ✅ `connectionDetached` - Conexão removida
- ✅ `click` (connection) - Clique em conexão

### **❌ FALTANDO (Implementar):**

#### **Endpoint Events:**
- ❌ `endpoint:click` - Clique em endpoint
- ❌ `endpoint:dblclick` - Duplo clique em endpoint

#### **Canvas Events:**
- ❌ `canvas:click` - Clique no canvas

#### **Drag Events:**
- ❌ `drag:start` - Início do drag
- ❌ `drag:move` - Movimento durante drag
- ❌ `drag:stop` - Fim do drag

#### **Node Events:**
- ❌ `node:added` - Node adicionado
- ❌ `node:removed` - Node removido
- ❌ `node:updated` - Node atualizado

#### **Edge Events:**
- ❌ `edge:moved` - Conexão movida
- ❌ `edge:pathEdited` - Caminho da conexão editado

---

## 🎯 IMPLEMENTAÇÃO COMPLETA

### **Ordem de Implementação:**

1. **Sistema de Eventos Customizado** (30min)
   - `emit()`, `on()`, `off()`, `removeAllListeners()`

2. **Endpoint Events** (1h)
   - `endpointClick`, `endpointDblClick`
   - Handlers: `onEndpointClick()`, `onEndpointDblClick()`

3. **Canvas Events** (30min)
   - `canvas:click`
   - Handler: `onCanvasClick()`

4. **Drag Events** (1h)
   - `dragStart`, `drag`, `dragStop`
   - Handlers: `onDragStart()`, `onDragMove()`, `onDragStop()`

5. **Node Events** (1h)
   - `node:added`, `node:removed`, `node:updated`
   - Disparar em `renderStep()`, `deleteStep()`, `updateStep()`

6. **Edge Events** (30min)
   - `edge:moved`, `edge:pathEdited`
   - Handlers customizados

**Total: 4-5 horas**

---

## ✅ CONCLUSÃO

### **Podemos implementar Events System completo manualmente**

**Vantagens:**
- ✅ Funciona com Community Edition
- ✅ Controle total sobre eventos
- ✅ Sistema customizado de event emitter
- ✅ Compatível com padrão Toolkit (mesmos nomes de eventos)

**Desvantagens:**
- ❌ Mais trabalho manual
- ❌ Não temos eventos prontos do Toolkit

### **Tempo Estimado:**
- **Events System Completo**: **3-4 horas** (conforme análise anterior)

---

## 🚀 PRÓXIMOS PASSOS

1. ✅ Implementar sistema de eventos customizado (`emit()`, `on()`, `off()`)
2. ✅ Adicionar eventos jsPlumb Community Edition (`endpointClick`, `dragStart`, etc.)
3. ✅ Implementar eventos customizados (`canvas:click`, `node:added`, etc.)
4. ✅ Adicionar handlers para todos os eventos
5. ✅ Integrar com código existente

**Após implementar, teremos Events System completo para V2.0.**

---

**Última Atualização**: 2025-12-11  
**Status**: ✅ **PODEMOS IMPLEMENTAR MANUALMENTE**  
**Tempo Estimado**: 3-4 horas

