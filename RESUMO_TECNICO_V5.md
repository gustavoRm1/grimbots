# 📊 RESUMO TÉCNICO V5.0 - FLOW BUILDER

## 🎯 Objetivo

Implementar Flow Builder visual (ManyChat-level) com correções críticas de duplicação de endpoints, estrutura de nodes HTML, drag handle, reconcile de conexões e melhorias de performance.

## 🔧 Soluções Implementadas

### 1. **Sistema Anti-Duplicação Robusto**

**Problema**: Endpoints duplicados ao mover cards rapidamente ou re-renderizar.

**Solução**:
- **`ensureEndpoint()` wrapper**: Verifica existência antes de criar endpoint usando `getEndpoints()` e comparação de UUIDs
- **`dataset.endpointsInited` flag**: Flag booleana no elemento para evitar múltiplas criações
- **`endpointCreationLock`**: Set de UUIDs sendo criados para prevenir race conditions
- **`fixEndpoints()`**: Remove endpoints órfãos e duplicados antes de criar novos

**Por quê funciona**:
- Single-source of truth: `dataset.endpointsInited` garante que endpoints são criados apenas uma vez
- Verificação dupla: `ensureEndpoint()` + `preventEndpointDuplication()` interceptam criação
- Lock de criação previne concorrência

### 2. **Estrutura de Nodes HTML Separados**

**Problema**: Endpoints criados diretamente no card, difícil posicionamento preciso.

**Solução**:
- **`.flow-step-node-input`**: Node HTML separado à esquerda do card (position absolute, left: -8px, top: 50%)
- **`.flow-step-node-output-global`**: Node HTML separado à direita quando não há botões
- **`.flow-step-button-endpoint-container`**: Container dentro de cada botão para endpoints de botões

**Por quê funciona**:
- Nodes HTML fornecem referência estável para ancoragem de endpoints
- Position absolute permite posicionamento preciso independente do conteúdo do card
- Separação clara entre estrutura visual e lógica de conexão

### 3. **Drag Handle**

**Problema**: Card inteiro draggable, conflito com cliques em endpoints.

**Solução**:
- **`.flow-drag-handle`**: Elemento no header do card (height: 40px, cursor: move)
- **jsPlumb draggable com handle**: `instance.draggable(element, { handle: dragHandle })`
- **CSS**: Handle transparente com hover effect

**Por quê funciona**:
- Apenas área do header é responsável por drag
- Endpoints e botões não interferem no drag
- UX melhor: usuário sabe exatamente onde arrastar

### 4. **Reconcile de Conexões (reconnectAll)**

**Problema**: `deleteEveryConnection()` sempre deleta tudo, mesmo quando não necessário.

**Solução**:
- **Calcular conexões desejadas**: Mapear todas as conexões que devem existir baseado em Alpine state
- **Comparar com existentes**: Obter conexões atuais via `this.connections` e `getSource()/getTarget()`
- **Reconcile**: Remover apenas conexões que não devem existir, criar apenas as que faltam

**Por quê funciona**:
- Evita perda de conexões temporárias
- Performance melhor: não recria conexões que já existem
- Estado consistente: conexões sempre refletem Alpine state

### 5. **Melhorias de Performance**

**Soluções**:
- **Throttle de repaint**: `setTimeout(..., 16)` para ~60fps
- **requestAnimationFrame**: Para operações DOM assíncronas
- **Revalidate seletivo**: Apenas elementos que mudaram
- **Flag de inicialização**: Evita recriação desnecessária de endpoints

**Por quê funciona**:
- Throttle limita frequência de repaint
- rAF garante sincronização com frame do navegador
- Flags evitam trabalho redundante

## 📁 Arquivos Modificados

### `static/js/flow_editor.js`
- **Linha ~820-1093**: `ensureEndpoint()`, `addEndpoints()` com flag `dataset.endpointsInited`
- **Linha ~534-641**: `renderStep()` com nodes HTML separados e drag handle
- **Linha ~706-830**: `updateStep()` com garantia de nodes HTML e reset de flag
- **Linha ~1204-1320**: `reconnectAll()` refatorado para reconcile
- **Linha ~1603-1650**: `editStep()` melhorado com null-safety

### `templates/bot_config.html`
- **Linha ~110-130**: CSS para `.flow-step-node-output-global` e `.flow-drag-handle`

## 🔍 Padrões de Código

### Verificação de Endpoint Existente
```javascript
const existing = instance.getEndpoints(el).find(ep => {
    return ep && ep.getUuid && ep.getUuid() === uuid;
});
```

### Flag de Inicialização
```javascript
if (element.dataset.endpointsInited === 'true') {
    return; // Já inicializado
}
element.dataset.endpointsInited = 'true';
```

### Reconcile de Conexões
```javascript
// Calcular desejadas vs existentes
// Remover apenas as que não devem existir
// Criar apenas as que faltam
```

## ⚠️ Pontos de Atenção

1. **Flag `dataset.endpointsInited`**: Deve ser resetada quando estrutura muda (botões adicionados/removidos)
2. **Drag handle**: Se não encontrado, fallback para card inteiro (compatibilidade)
3. **Reconcile**: Pode falhar se endpoints não existirem ainda (aguardar requestAnimationFrame)
4. **Debug mode**: `window.FLOW_DEBUG = true` para logs detalhados

## 🎓 Lições Aprendidas

1. **Single-source of truth**: Flags dataset são mais confiáveis que verificações de DOM
2. **Reconcile > Delete All**: Sempre preferir reconcile ao invés de deletar tudo
3. **Nodes HTML separados**: Facilitam posicionamento e manutenção
4. **Drag handle**: Melhora UX e evita conflitos
5. **Throttle**: Essencial para performance em operações frequentes

