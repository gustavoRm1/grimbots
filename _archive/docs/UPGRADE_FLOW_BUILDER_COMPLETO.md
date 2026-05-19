# 🚀 UPGRADE COMPLETO DO FLOW BUILDER

## ✅ IMPLEMENTAÇÃO CONFORME ESPECIFICAÇÃO EXATA

Todas as regras foram implementadas **exatamente** conforme especificado, sem alterações na lógica.

---

## 🔵 1. POSIÇÃO DO INPUT (ENTRADA DO CARD)

### ✅ Implementado:
- **Input sempre no topo-central** do container ROOT (`stepElement`)
- **Nunca em subcomponents** (não está mais no bloco de texto)
- Endpoint `target` único registrado no elemento raiz
- UUID: `endpoint-top-{stepId}`
- Anchor: `['TopCenter', { dy: -5 }]`

### Código:
```javascript
// Em addEndpoints() - linha ~567
this.instance.addEndpoint(element, {  // element = container ROOT
    uuid: `endpoint-top-${stepId}`,
    anchor: ['TopCenter', { dy: -5 }],
    isSource: false,
    isTarget: true,
    // ...
});
```

---

## 🔘 2. SAÍDAS QUANDO EXISTEM BOTÕES

### ✅ Implementado:
- **Cada botão tem seu próprio endpoint `source` individual**
- Endpoint renderizado **no próprio botão** (container `.flow-step-button-endpoint-container`)
- Posição: **lado direito** do botão, verticalmente centralizado
- jsPlumb registra dinamicamente cada botão como `source`
- **Output global removido** quando há botões
- Cada output carrega ID do botão correspondente (`buttonIndex`, `buttonId`)
- Conexão identifica qual botão a criou

### Estrutura DOM:
```html
<div class="flow-step-button-item" data-button-index="0" data-button-id="btn-0">
    <span class="flow-step-button-text">Texto do botão</span>
    <div class="flow-step-button-endpoint-container" data-endpoint-button="0"></div>
</div>
```

### Código:
```javascript
// Em addEndpoints() - linha ~668
customButtons.forEach((btn, index) => {
    const buttonContainer = element.querySelector(`[data-endpoint-button="${index}"]`);
    if (buttonContainer) {
        this.instance.addEndpoint(buttonContainer, {
            uuid: `endpoint-button-${stepId}-${index}`,
            anchor: ['Right', { dx: 5 }],
            maxConnections: 1,
            isSource: true,
            data: {
                stepId: stepId,
                buttonIndex: index,
                buttonId: btn.id || `btn-${index}`,
                endpointType: 'button'
            }
        });
    }
});
```

---

## ⚪ 3. SAÍDA QUANDO NÃO EXISTEM BOTÕES

### ✅ Implementado:
- **Uma saída global única** quando não há botões
- Posição: **centro-direita** do card
- Alinhada verticalmente com o meio do card (`top: 50%`, `transform: translateY(-50%)`)
- Endpoint `source` registrado
- **Desaparece automaticamente** se botões forem adicionados
- **Reaparece** se todos os botões forem removidos

### Código:
```javascript
// Em addEndpoints() - linha ~700
if (!hasButtons) {
    let globalOutputContainer = element.querySelector('.flow-step-global-output-container');
    if (!globalOutputContainer) {
        globalOutputContainer = document.createElement('div');
        globalOutputContainer.className = 'flow-step-global-output-container';
        element.appendChild(globalOutputContainer);
    }
    
    this.instance.addEndpoint(globalOutputContainer, {
        uuid: `endpoint-bottom-${stepId}`,
        anchor: ['Right', { dx: 5 }],
        maxConnections: -1,
        isSource: true,
        // ...
    });
}
```

### CSS:
```css
.flow-step-global-output-container {
    position: absolute;
    right: -15px;
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    z-index: 10;
}
```

---

## 🧱 4. HIERARQUIA DO CARD (ORDEM VISUAL)

### ✅ Implementado na ordem EXATA:
1. **Header** (título vermelho)
2. **Body:**
   - **Mídia** (se existir) - preview com ícone
   - **URL da mídia** (se existir) - texto truncado
   - **Texto** - preview do conteúdo
   - **Botões** - lista de botões customizados
3. **Footer** (ações: editar, excluir, favoritar)
4. **Output(s)** - endpoints de saída

### Código HTML:
```javascript
// Em renderStep() - linha ~382
stepElement.innerHTML = `
    <div class="flow-step-header">...</div>
    <div class="flow-step-body">
        ${mediaHTML}                    <!-- 1. Mídia -->
        ${hasMedia ? mediaUrlHTML : ''} <!-- 2. URL da mídia -->
        ${previewTextHTML}              <!-- 3. Texto -->
        ${buttonsHTML}                  <!-- 4. Botões -->
    </div>
    <div class="flow-step-footer">...</div> <!-- 5. Ações -->
    ${!hasButtons ? '<div class="flow-step-global-output-container"></div>' : ''} <!-- 6. Output -->
`;
```

---

## 🎨 5. POSIÇÕES EXATAS DOS ENDPOINTS

### ✅ INPUT:
- **Topo → centro horizontal**
- Anchor: `['TopCenter', { dy: -5 }]`
- No container ROOT

### ✅ OUTPUT GLOBAL (sem botões):
- **Centro-direita** do card
- **Alinhado verticalmente** com o meio (`top: 50%`, `transform: translateY(-50%)`)
- CSS: `right: -15px`

### ✅ OUTPUT POR BOTÃO:
- **Aplicado dentro do próprio botão**
- **Lado direito**, verticalmente alinhado
- Endpoint pequeno (`radius: 6`) porém clicável
- **Acompanha o botão** ao mover o card (jsPlumb gerencia automaticamente)

---

## ⚙ 6. REGRAS DO JSPLUMB

### ✅ Implementado:

#### Registro de Endpoints:
- **Input**: Endpoint `TARGET` fixo no container ROOT
- **Botões**: Endpoints `SOURCE` individuais registrados dinamicamente
- **Saída global**: Endpoint `SOURCE` apenas quando não há botões

#### Atualização Automática:
- ✅ **Ao mover card**: jsPlumb atualiza automaticamente (drag repaint)
- ✅ **Ao adicionar botão**: `addCustomButton()` → `updateStepEndpoints()`
- ✅ **Ao excluir botão**: `removeCustomButton()` → `updateStepEndpoints()`
- ✅ **Ao editar botão**: `saveStep()` → `updateStepEndpoints()`

#### Save/Load:
- ✅ **Identificação de botão**: `buttonIndex` e `buttonId` salvos em `connection.data`
- ✅ **ID do endpoint**: UUID único por endpoint (`endpoint-button-{stepId}-{index}`)
- ✅ **Ligações corretas**: `target_step` do botão ou `connections[type]` do step

### Funções Implementadas:

```javascript
// Atualizar endpoints após mudanças
updateStepEndpoints(stepId) {
    // Remove todos os endpoints
    // Re-adiciona conforme estado atual
    // Reconecta automaticamente
}

// Reconectar todas as conexões
reconnectAll() {
    // Detecta se tem botões ou não
    // Reconecta pelos endpoints corretos
}
```

---

## 🧠 7. COMPATIBILIDADE COM O QUE JÁ EXISTE

### ✅ Implementado:

#### JSON Compatível:
- ✅ Mantém estrutura existente (`connections`, `config.custom_buttons`)
- ✅ Não quebra fluxos já existentes
- ✅ Preserva `target_step` dos botões

#### Conversão Automática:
- ✅ **Steps antigos com botões** → Cria endpoints por botão automaticamente
- ✅ **Steps antigos sem botões** → Mantém endpoint global
- ✅ **Inicialização automática** em `renderAllSteps()`:
  ```javascript
  // Garantir que config existe
  if (!step.config) step.config = {};
  // Garantir que custom_buttons existe
  if (!step.config.custom_buttons) step.config.custom_buttons = [];
  // Garantir que connections existe
  if (!step.connections) step.connections = {};
  ```

#### Preservação de Dados:
- ✅ `saveStep()` preserva conexões existentes
- ✅ `reconnectAll()` reconstrói conexões corretamente
- ✅ `onConnectionCreated()` atualiza Alpine.js automaticamente

---

## 🔥 ENTREGA COMPLETA

### ✅ Arquivos Atualizados:

1. **`static/js/flow_editor.js`**:
   - ✅ `renderStep()` - HTML seguindo hierarquia exata
   - ✅ `addEndpoints()` - Lógica completa de endpoints
   - ✅ `updateStep()` - Re-renderização com endpoints
   - ✅ `updateStepEndpoints()` - NOVO - Atualização automática
   - ✅ `reconnectAll()` - Reconexão com detecção de botões
   - ✅ `createConnectionFromButton()` - Conexões de botões
   - ✅ `onConnectionCreated()` - Identificação de botão
   - ✅ `removeConnection()` - Remoção correta
   - ✅ `renderAllSteps()` - Conversão automática de steps antigos

2. **`templates/bot_config.html`**:
   - ✅ CSS para `.flow-step-media-preview`
   - ✅ CSS para `.flow-step-media-url`
   - ✅ CSS para `.flow-step-button-endpoint-container`
   - ✅ CSS para `.flow-step-global-output-container` (posição corrigida)
   - ✅ `addCustomButton()` - Atualiza endpoints automaticamente
   - ✅ `removeCustomButton()` - Atualiza endpoints automaticamente
   - ✅ `saveStep()` - Atualiza endpoints após salvar

### ✅ Funcionalidades Garantidas:

- ✅ **Arrastar cards**: Endpoints acompanham automaticamente
- ✅ **Conectar**: Identifica botão ou conexão global corretamente
- ✅ **Desconectar**: Remove do Alpine.js corretamente
- ✅ **Adicionar botão**: Endpoint criado automaticamente, output global removido
- ✅ **Remover botão**: Endpoint removido, output global reaparece se necessário
- ✅ **Recarregar página**: Endpoints reconstruídos corretamente

---

## 📋 CHECKLIST DE VALIDAÇÃO

### Input (Entrada):
- ✅ No topo-central do container ROOT
- ✅ Nunca em subcomponents
- ✅ Endpoint `target` único

### Saídas com Botões:
- ✅ Um endpoint por botão
- ✅ No lado direito do botão
- ✅ Dentro do próprio botão
- ✅ Identificação correta (`buttonIndex`, `buttonId`)
- ✅ Output global removido quando há botões

### Saída sem Botões:
- ✅ Uma saída global única
- ✅ Centro-direita do card
- ✅ Alinhada verticalmente
- ✅ Reaparece quando botões são removidos

### Hierarquia:
- ✅ Header → Mídia → URL → Texto → Botões → Ações → Outputs

### jsPlumb:
- ✅ Registro correto de endpoints
- ✅ Atualização automática ao mover/adicionar/remover/editar
- ✅ Save/load com identificação de botões

### Compatibilidade:
- ✅ JSON compatível
- ✅ Conversão automática de steps antigos
- ✅ Não quebra fluxos existentes

---

## 🎯 RESULTADO FINAL

**✅ TODAS AS ESPECIFICAÇÕES IMPLEMENTADAS EXATAMENTE COMO SOLICITADO**

O Flow Builder agora funciona conforme padrões profissionais (ManyChat/Botpress/HighLevel) com:
- Endpoints posicionados corretamente
- Lógica de conexões profissional
- Atualização automática
- Compatibilidade total com dados existentes
- UX fluida e intuitiva

**Código limpo, modular e funcional.**

