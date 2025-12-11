# 📝 CHANGELOG V7 - FLUXO VISUAL PROFISSIONAL

**Data:** 2025-01-11  
**Versão:** V7 PROFISSIONAL

---

## 🔴 BREAKING CHANGES

### Inicialização Assíncrona

**ANTES (V6):**
```javascript
init() {
    setTimeout(() => {
        this.setupJsPlumb();
        setTimeout(() => {
            this.continueInit();
        }, 200);
    }, 100);
}
```

**DEPOIS (V7):**
```javascript
async init() {
    this.setupCanvas();
    await this.waitForElement(this.contentContainer, 2000);
    await this.setupJsPlumbAsync();
    this.continueInit();
}
```

**Impacto:** Código que chama `init()` deve aguardar Promise ou usar `await`.

---

## ✅ NOVAS FUNCIONALIDADES

### 1. `forceEndpointVisibility()`

Nova função profissional que garante visibilidade completa de endpoints.

```javascript
forceEndpointVisibility(endpoint, stepId, endpointType)
```

**Uso:**
```javascript
const endpoint = this.ensureEndpoint(...);
if (endpoint) {
    this.forceEndpointVisibility(endpoint, stepId, 'input');
}
```

---

### 2. `waitForElement()`

Nova função auxiliar para aguardar elemento estar no DOM.

```javascript
await this.waitForElement(element, timeout)
```

**Uso:**
```javascript
await this.waitForElement(this.contentContainer, 2000);
```

---

### 3. `setupJsPlumbAsync()`

Nova função assíncrona para inicializar jsPlumb.

```javascript
await this.setupJsPlumbAsync()
```

**Uso:**
```javascript
await this.setupJsPlumbAsync();
if (!this.instance) {
    console.error('Instance não criado');
    return;
}
```

---

### 4. `configureSVGOverlayWithRetry()`

Nova função com retry robusto para configurar SVG overlay.

```javascript
await this.configureSVGOverlayWithRetry(maxAttempts)
```

**Uso:**
```javascript
await this.configureSVGOverlayWithRetry(10);
```

---

## 🔧 MELHORIAS

### Container jsPlumb

**ANTES (V6):**
```javascript
const container = this.contentContainer;
const canvasParent = container.parentElement || this.canvas;
this.instance = jsPlumb.newInstance({ Container: canvasParent });
```

**DEPOIS (V7):**
```javascript
const container = this.canvas; // SEMPRE canvas pai
this.instance = jsPlumb.newInstance({ Container: container });
this.instance.setContainer(container);
```

**Benefício:** SVG overlay renderizado corretamente, endpoints sempre visíveis.

---

### MutationObserver com Debounce

**ANTES (V6):**
```javascript
this.transformObserver = new MutationObserver(() => {
    // Sem debounce - pode causar loops
    this.instance.repaintEverything();
});
```

**DEPOIS (V7):**
```javascript
let debounceTimeout = null;
let isRepainting = false;

this.transformObserver = new MutationObserver(() => {
    if (isRepainting || !this.instance) return;
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
        isRepainting = true;
        // ... processar ...
        isRepainting = false;
    }, 16);
});
```

**Benefício:** Elimina loops infinitos, melhora performance.

---

### reconnectAll() com Retry

**ANTES (V6):**
```javascript
if (srcEp && tgtEp) {
    // criar conexão
} else {
    console.warn('Endpoints não encontrados');
    // Não cria conexão
}
```

**DEPOIS (V7):**
```javascript
if (srcEp && tgtEp) {
    // criar conexão
} else {
    // Adicionar à fila de retry
    pendingConnections.push({ connId, desired });
}

// Retry automático até 5 vezes
const retryInterval = setInterval(() => {
    // Tentar criar conexões pendentes
}, 200);
```

**Benefício:** Conexões são criadas mesmo se endpoints não estão prontos imediatamente.

---

### Draggable Containment

**ANTES (V6):**
```javascript
containment: container || this.contentContainer || this.canvas
```

**DEPOIS (V7):**
```javascript
containment: this.canvas // SEMPRE canvas pai
```

**Benefício:** Drag funciona corretamente, containment correto.

---

## 🐛 BUGS CORRIGIDOS

1. ✅ Endpoints não apareciam visualmente
2. ✅ Cards não podiam ser arrastados
3. ✅ Conexões não funcionavam
4. ✅ Race conditions na inicialização
5. ✅ Duplicação de endpoints durante drag
6. ✅ Loops infinitos no MutationObserver
7. ✅ reconnectAll falhando silenciosamente
8. ✅ CSS ocultando elementos

---

## 📊 PERFORMANCE

### Melhorias

- ✅ Debounce no MutationObserver (16ms)
- ✅ requestAnimationFrame para repaint
- ✅ Retry inteligente em reconnectAll
- ✅ Lazy loading de endpoints

### Métricas

- **Antes:** Lag durante drag/zoom frequente
- **Depois:** Performance suave, sem lag

---

## 🎨 VISUAL

### Melhorias CSS

- ✅ CSS profissional ManyChat-level
- ✅ Endpoints com cores corretas
- ✅ Hover states melhorados
- ✅ SVG overlay sempre visível

---

## 📚 DOCUMENTAÇÃO

### Novos Documentos

1. ✅ `RELATORIO_AUDITORIA_V6_V7.md`
2. ✅ `CHECKLIST_QA_V6_V7.md`
3. ✅ `MANUAL_ARQUITETURA_FLOW_V7.md`
4. ✅ `ENTREGA_FINAL_V7.md`
5. ✅ `CHANGELOG_V7.md` (este arquivo)

---

## 🔄 MIGRAÇÃO DE V6 PARA V7

### Passos Necessários

1. **Backup**
   ```bash
   cp static/js/flow_editor.js static/js/flow_editor.js.v6
   ```

2. **Substituir Arquivos**
   - `static/js/flow_editor.js`
   - `templates/bot_config.html`

3. **Verificar Dependências**
   - jsPlumb 2.15.6 (CDN)
   - Alpine.js 3.x (CDN)

4. **Testar**
   - Endpoints aparecem
   - Cards arrastáveis
   - Conexões funcionam
   - Zoom/pan funcionam

5. **Rollback (se necessário)**
   ```bash
   cp static/js/flow_editor.js.v6 static/js/flow_editor.js
   ```

---

## 🎯 PRÓXIMAS VERSÕES

### V8 (Futuro)

- [ ] Suporte para condições visuais
- [ ] Suporte para loops/cycles
- [ ] Export/Import de fluxos
- [ ] Templates pré-configurados
- [ ] Validação de fluxo em tempo real

---

**Documento gerado em:** 2025-01-11  
**Última atualização:** 2025-01-11

