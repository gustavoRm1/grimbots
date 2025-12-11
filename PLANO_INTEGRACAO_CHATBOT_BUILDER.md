# 🚀 PLANO DE INTEGRAÇÃO: Chatbot Builder jsPlumb

**Fonte:** [jsplumb-demonstrations/chatbot](https://github.com/jsplumb-demonstrations/chatbot)  
**Objetivo:** Integrar padrões e funcionalidades do chatbot builder oficial do jsPlumb ao nosso Flow Builder

---

## 📊 ANÁLISE DO CHATBOT BUILDER

### Funcionalidades Identificadas

1. **Drag & Drop de Nodes**
   - Diferentes tipos de nós (decisions, actions)
   - Arrastar do palette para o canvas
   - Posicionamento livre no canvas

2. **Sistema de Conexões**
   - Conexões visuais entre nós
   - Validação de conexões permitidas
   - Visual feedback durante conexão

3. **Tipos de Nodes**
   - Decision nodes (decisões/condições)
   - Action nodes (ações/mensagens)
   - Custom nodes (extensíveis)

4. **Palette de Componentes**
   - Sidebar com componentes disponíveis
   - Drag para adicionar ao canvas
   - Preview de componentes

---

## 🎯 INTEGRAÇÃO COM NOSSO SISTEMA

### 1. **PALETTE DE STEPS**

#### Implementação
Adicionar uma sidebar com tipos de steps disponíveis:

```javascript
// Tipos de steps disponíveis
const stepTypes = [
    { type: 'message', icon: 'fa-comment', label: 'Mensagem', color: '#3B82F6' },
    { type: 'content', icon: 'fa-file-alt', label: 'Conteúdo', color: '#10B981' },
    { type: 'payment', icon: 'fa-credit-card', label: 'Pagamento', color: '#F59E0B' },
    { type: 'access', icon: 'fa-key', label: 'Acesso', color: '#8B5CF6' },
    { type: 'audio', icon: 'fa-headphones', label: 'Áudio', color: '#EC4899' },
    { type: 'video', icon: 'fa-video', label: 'Vídeo', color: '#EF4444' },
    { type: 'buttons', icon: 'fa-mouse-pointer', label: 'Botões', color: '#14B8A6' },
    { type: 'condition', icon: 'fa-code-branch', label: 'Condição', color: '#F97316' }
];
```

#### Funcionalidade
- Drag & drop do palette para o canvas
- Criação automática de step ao soltar
- Posicionamento no ponto de drop

### 2. **SISTEMA DE VALIDAÇÃO DE CONEXÕES**

#### Implementação
Validar quais conexões são permitidas:

```javascript
// Regras de conexão
const connectionRules = {
    'message': ['content', 'payment', 'access', 'buttons', 'condition'],
    'payment': ['access', 'message', 'condition'],
    'condition': ['message', 'payment', 'access'],
    'access': [] // Fim do fluxo
};
```

#### Funcionalidade
- Bloquear conexões inválidas
- Feedback visual (endpoint vermelho se inválido)
- Tooltip explicando por que não pode conectar

### 3. **NOVO TIPO: CONDITION NODE**

#### Implementação
Adicionar step tipo `condition` para decisões:

```javascript
{
    id: 'step_xxx',
    type: 'condition',
    config: {
        condition_type: 'text_validation' | 'button_click' | 'payment_status' | 'time_elapsed',
        condition_value: '...',
        true_step_id: 'step_yyy',  // Se condição verdadeira
        false_step_id: 'step_zzz'  // Se condição falsa
    },
    position: { x: 100, y: 100 }
}
```

#### Visual
- Node com formato de losango (diamond)
- Dois outputs: `true` e `false`
- Cores diferentes para cada branch

### 4. **PALETTE SIDEBAR**

#### HTML
```html
<div class="flow-palette" x-show="config.flow_enabled">
    <div class="flow-palette-header">
        <h3>Componentes</h3>
    </div>
    <div class="flow-palette-items">
        <div 
            class="flow-palette-item" 
            draggable="true"
            data-step-type="message"
            @dragstart="handlePaletteDrag($event, 'message')"
        >
            <i class="fas fa-comment"></i>
            <span>Mensagem</span>
        </div>
        <!-- Mais itens... -->
    </div>
</div>
```

#### CSS
```css
.flow-palette {
    position: fixed;
    left: 0;
    top: 0;
    width: 250px;
    height: 100vh;
    background: #1A1D29;
    border-right: 1px solid #242836;
    padding: 20px;
    overflow-y: auto;
    z-index: 1000;
}

.flow-palette-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    background: #242836;
    border-radius: 8px;
    cursor: grab;
    transition: all 0.2s;
}

.flow-palette-item:hover {
    background: #2D3142;
    transform: translateX(4px);
}

.flow-palette-item:active {
    cursor: grabbing;
}
```

### 5. **DRAG & DROP DO PALETTE**

#### JavaScript
```javascript
handlePaletteDrag(event, stepType) {
    event.dataTransfer.setData('application/step-type', stepType);
    event.dataTransfer.effectAllowed = 'copy';
}

// No canvas
handleCanvasDrop(event) {
    event.preventDefault();
    const stepType = event.dataTransfer.getData('application/step-type');
    if (!stepType) return;
    
    // Obter posição do drop relativa ao canvas
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left - this.pan.x;
    const y = event.clientY - rect.top - this.pan.y;
    
    // Criar novo step
    this.addFlowStepFromPalette(stepType, x / this.zoomLevel, y / this.zoomLevel);
}

addFlowStepFromPalette(stepType, x, y) {
    const stepId = `step_${Date.now()}`;
    const newStep = {
        id: stepId,
        type: stepType,
        order: this.alpine.config.flow_steps.length,
        config: this.getDefaultConfigForType(stepType),
        connections: {},
        conditions: [],
        delay_seconds: 0,
        position: { x, y }
    };
    
    this.alpine.config.flow_steps.push(newStep);
    this.renderAllSteps();
}
```

---

## 🔧 IMPLEMENTAÇÃO TÉCNICA

### Arquivos a Modificar

1. **`templates/bot_config.html`**
   - Adicionar sidebar de palette
   - Adicionar handlers de drag & drop

2. **`static/js/flow_editor.js`**
   - Adicionar `handlePaletteDrag()`
   - Adicionar `handleCanvasDrop()`
   - Adicionar `addFlowStepFromPalette()`
   - Adicionar `validateConnection()`
   - Adicionar suporte para `condition` node type

3. **CSS (em `bot_config.html`)**
   - Estilos para palette sidebar
   - Estilos para palette items
   - Estilos para condition nodes (diamond shape)

---

## 🎨 MELHORIAS VISUAIS

### 1. **Condition Node (Losango)**
```css
.flow-step-block[data-step-type="condition"] {
    width: 200px;
    height: 120px;
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
    border-radius: 0;
}

.flow-step-block[data-step-type="condition"] .flow-step-header {
    border-radius: 0;
}
```

### 2. **Palette Items com Preview**
- Ícone colorido
- Nome do tipo
- Descrição curta
- Badge de "novo" se tipo não usado

### 3. **Feedback Visual de Drag**
- Ghost image durante drag
- Highlight no canvas quando sobre área válida
- Cursor apropriado (grab/grabbing)

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Criar sidebar de palette
- [ ] Implementar drag & drop do palette
- [ ] Adicionar tipo `condition` node
- [ ] Implementar validação de conexões
- [ ] Adicionar feedback visual de conexões inválidas
- [ ] Criar estilos para condition nodes (diamond)
- [ ] Testar drag & drop em diferentes zoom levels
- [ ] Garantir que novos steps aparecem corretamente
- [ ] Validar que conexões funcionam com novos tipos

---

## 🚀 PRÓXIMOS PASSOS

1. **Fase 1:** Implementar palette sidebar básica
2. **Fase 2:** Adicionar drag & drop funcional
3. **Fase 3:** Implementar condition nodes
4. **Fase 4:** Adicionar validação de conexões
5. **Fase 5:** Melhorias visuais e UX

---

## 📚 REFERÊNCIAS

- [jsplumb-demonstrations/chatbot](https://github.com/jsplumb-demonstrations/chatbot)
- [jsPlumb Toolkit Documentation](https://docs.jsplumbtoolkit.com/)
- [jsPlumb Community Edition](https://jsplumb.github.io/jsplumb/)

