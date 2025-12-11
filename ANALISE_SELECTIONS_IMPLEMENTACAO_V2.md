# 🎯 ANÁLISE: Implementação de Selections para V2.0

**Data:** 2025-12-11  
**Versão Atual:** V7 (70% implementado)  
**Meta V2.0:** 95% (Nível Typebot/ManyChat)

---

## 🔍 SITUAÇÃO ATUAL

### **Documentação Fornecida:**
- ✅ **jsPlumb Toolkit Selections** (métodos prontos)
- ✅ **Lasso Selection** (seleção por área)
- ✅ **Selection Modes** (mixed, isolated, nodesOnly, etc.)

### **Nosso Projeto:**
- ✅ **jsPlumb Community Edition 2.15.6** (não Toolkit)
- ❌ **`enableSelection()` está VAZIO**
- ✅ **`selectedStep` existe** mas não é usado

---

## ⚠️ LIMITAÇÃO

### **jsPlumb Toolkit Selection Methods NÃO estão disponíveis**

**Por quê?**
- `toolkit.setSelection()`, `toolkit.addToSelection()`, etc. são métodos do **Toolkit**
- Estamos usando **Community Edition** (não tem Toolkit)
- Precisamos implementar **manualmente**

**Consequência:**
- ❌ **NÃO podemos usar** métodos prontos do Toolkit
- ✅ **PODEMOS implementar** manualmente usando Vanilla JS

---

## ✅ O QUE PODEMOS IMPLEMENTAR MANUALMENTE

### **1. Selection System Básico**

#### **Estrutura de Dados:**
```javascript
// No constructor do FlowEditor
this.selectedSteps = new Set(); // IDs dos steps selecionados
this.selectionMode = 'mixed'; // 'mixed', 'single', 'multiple'
this.isLassoSelecting = false;
this.lassoStartPoint = null;
this.lassoElement = null;
```

#### **Métodos Principais:**
```javascript
// setSelection(stepId) - Definir seleção única
setSelection(stepId) {
    this.clearSelection();
    if (stepId) {
        this.selectedSteps.add(stepId);
        this.updateSelectionVisual();
    }
}

// addToSelection(stepId) - Adicionar à seleção
addToSelection(stepId) {
    if (this.selectionMode === 'single') {
        this.setSelection(stepId);
    } else {
        this.selectedSteps.add(stepId);
        this.updateSelectionVisual();
    }
}

// removeFromSelection(stepId) - Remover da seleção
removeFromSelection(stepId) {
    this.selectedSteps.delete(stepId);
    this.updateSelectionVisual();
}

// clearSelection() - Limpar seleção
clearSelection() {
    this.selectedSteps.clear();
    this.updateSelectionVisual();
}

// getSelection() - Obter seleção atual
getSelection() {
    return Array.from(this.selectedSteps);
}
```

---

### **2. Visual Feedback (CSS Classes)**

#### **CSS Classes:**
```css
/* Step selecionado */
.flow-step-block.jtk-surface-selected-element {
    border: 2px solid #FFB800 !important;
    box-shadow: 0 0 0 4px rgba(255, 184, 0, 0.2) !important;
    transform: scale(1.02);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Múltiplos steps selecionados */
.flow-step-block.jtk-surface-selected-element.multiple-selection {
    border-color: #10B981 !important;
}
```

#### **Método updateSelectionVisual():**
```javascript
updateSelectionVisual() {
    // Remover classe de todos os steps
    this.steps.forEach((element, stepId) => {
        element.classList.remove('jtk-surface-selected-element', 'multiple-selection');
    });
    
    // Adicionar classe aos selecionados
    this.selectedSteps.forEach(stepId => {
        const element = this.steps.get(stepId);
        if (element) {
            element.classList.add('jtk-surface-selected-element');
            if (this.selectedSteps.size > 1) {
                element.classList.add('multiple-selection');
            }
        }
    });
}
```

---

### **3. Seleção por Clique**

#### **Implementação:**
```javascript
enableSelection() {
    // Clique no step - selecionar
    this.contentContainer.addEventListener('click', (e) => {
        const stepElement = e.target.closest('.flow-step-block');
        if (!stepElement) {
            // Clique no canvas - deselecionar
            if (e.target === this.canvas || e.target === this.contentContainer) {
                this.clearSelection();
            }
            return;
        }
        
        const stepId = stepElement.dataset.stepId;
        if (!stepId) return;
        
        // Prevenir seleção se clicou em botão de ação
        if (e.target.closest('.flow-step-btn-action')) {
            return;
        }
        
        // Prevenir seleção se clicou em endpoint
        if (e.target.closest('.jtk-endpoint')) {
            return;
        }
        
        e.stopPropagation();
        
        // Ctrl/Cmd + Click = adicionar à seleção
        if (e.ctrlKey || e.metaKey) {
            if (this.selectedSteps.has(stepId)) {
                this.removeFromSelection(stepId);
            } else {
                this.addToSelection(stepId);
            }
        } else {
            // Click normal = seleção única
            this.setSelection(stepId);
        }
    }, true);
}
```

---

### **4. Seleção por Área (Lasso Selection)**

#### **Implementação:**
```javascript
enableLassoSelection() {
    let isLassoActive = false;
    let lassoStart = null;
    let lassoElement = null;
    
    // Mousedown no canvas
    this.canvas.addEventListener('mousedown', (e) => {
        // Apenas se clicou no canvas (não em step)
        if (e.target === this.canvas || e.target === this.contentContainer) {
            // Shift + Drag = lasso selection
            if (e.shiftKey) {
                isLassoActive = true;
                lassoStart = { x: e.clientX, y: e.clientY };
                
                // Criar elemento lasso
                lassoElement = document.createElement('div');
                lassoElement.className = 'flow-lasso';
                lassoElement.style.cssText = `
                    position: absolute;
                    border: 2px dashed #FFB800;
                    background: rgba(255, 184, 0, 0.1);
                    pointer-events: none;
                    z-index: 10000;
                `;
                this.canvas.appendChild(lassoElement);
            }
        }
    });
    
    // Mousemove - atualizar lasso
    this.canvas.addEventListener('mousemove', (e) => {
        if (isLassoActive && lassoStart && lassoElement) {
            const rect = this.canvas.getBoundingClientRect();
            const left = Math.min(lassoStart.x - rect.left, e.clientX - rect.left);
            const top = Math.min(lassoStart.y - rect.top, e.clientY - rect.top);
            const width = Math.abs(e.clientX - lassoStart.x);
            const height = Math.abs(e.clientY - lassoStart.y);
            
            lassoElement.style.left = left + 'px';
            lassoElement.style.top = top + 'px';
            lassoElement.style.width = width + 'px';
            lassoElement.style.height = height + 'px';
            
            // Selecionar steps dentro do lasso
            this.selectStepsInLasso(left, top, width, height);
        }
    });
    
    // Mouseup - finalizar lasso
    this.canvas.addEventListener('mouseup', () => {
        if (isLassoActive) {
            isLassoActive = false;
            if (lassoElement) {
                lassoElement.remove();
                lassoElement = null;
            }
            lassoStart = null;
        }
    });
}

selectStepsInLasso(left, top, width, height) {
    const lassoRect = { left, top, width, height };
    
    this.steps.forEach((element, stepId) => {
        const rect = element.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();
        const stepRect = {
            left: rect.left - canvasRect.left,
            top: rect.top - canvasRect.top,
            width: rect.width,
            height: rect.height
        };
        
        // Verificar se step está dentro do lasso
        const isInside = this.isRectInside(stepRect, lassoRect);
        
        if (isInside) {
            this.addToSelection(stepId);
        }
    });
}

isRectInside(inner, outer) {
    return inner.left >= outer.left &&
           inner.top >= outer.top &&
           (inner.left + inner.width) <= (outer.left + outer.width) &&
           (inner.top + inner.height) <= (outer.top + outer.height);
}
```

---

### **5. Keyboard Shortcuts para Seleção**

#### **Implementação:**
```javascript
enableKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // ESC - Deselecionar
        if (e.key === 'Escape') {
            this.clearSelection();
            return;
        }
        
        // Ctrl+A - Selecionar todos
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
            e.preventDefault();
            this.selectAll();
            return;
        }
        
        // Delete/Backspace - Remover selecionados
        if ((e.key === 'Delete' || e.key === 'Backspace') && this.selectedSteps.size > 0) {
            e.preventDefault();
            this.deleteSelected();
            return;
        }
        
        // Ctrl+C - Copiar selecionados
        if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
            e.preventDefault();
            this.copySelected();
            return;
        }
        
        // Ctrl+V - Colar
        if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
            e.preventDefault();
            this.pasteSelected();
            return;
        }
    });
}

selectAll() {
    this.steps.forEach((element, stepId) => {
        this.selectedSteps.add(stepId);
    });
    this.updateSelectionVisual();
}

deleteSelected() {
    const selected = Array.from(this.selectedSteps);
    selected.forEach(stepId => {
        this.deleteStep(stepId);
    });
    this.clearSelection();
}
```

---

## 📊 COMPARAÇÃO: Toolkit vs. Implementação Manual

| Funcionalidade | Toolkit (Pronto) | Manual (A Implementar) |
|----------------|------------------|------------------------|
| `setSelection()` | ✅ `toolkit.setSelection()` | ✅ `this.setSelection()` |
| `addToSelection()` | ✅ `toolkit.addToSelection()` | ✅ `this.addToSelection()` |
| `removeFromSelection()` | ✅ `toolkit.removeFromSelection()` | ✅ `this.removeFromSelection()` |
| `clearSelection()` | ✅ `toolkit.clearSelection()` | ✅ `this.clearSelection()` |
| `getSelection()` | ✅ `toolkit.getSelection()` | ✅ `this.getSelection()` |
| **Lasso Selection** | ✅ Plugin pronto | ✅ **Implementar manualmente** |
| **Visual Feedback** | ✅ Automático | ✅ **Implementar CSS + updateSelectionVisual()** |
| **Keyboard Shortcuts** | ❌ Não incluído | ✅ **Implementar manualmente** |

---

## 🎯 IMPLEMENTAÇÃO COMPLETA PARA V2.0

### **Arquivo:** `static/js/flow_editor.js`

#### **1. Adicionar ao Constructor:**
```javascript
constructor(canvasId, alpineContext) {
    // ... código existente ...
    
    // Selection System
    this.selectedSteps = new Set();
    this.selectionMode = 'mixed'; // 'mixed', 'single', 'multiple'
    this.isLassoSelecting = false;
    this.lassoStartPoint = null;
    this.lassoElement = null;
}
```

#### **2. Implementar enableSelection():**
```javascript
enableSelection() {
    // Seleção por clique
    this.contentContainer.addEventListener('click', (e) => {
        // ... código acima ...
    }, true);
    
    // Lasso selection
    this.enableLassoSelection();
    
    // Keyboard shortcuts
    this.enableKeyboardShortcuts();
}
```

#### **3. Adicionar Métodos de Seleção:**
```javascript
setSelection(stepId) { ... }
addToSelection(stepId) { ... }
removeFromSelection(stepId) { ... }
clearSelection() { ... }
getSelection() { ... }
updateSelectionVisual() { ... }
enableLassoSelection() { ... }
selectStepsInLasso(left, top, width, height) { ... }
isRectInside(inner, outer) { ... }
enableKeyboardShortcuts() { ... }
selectAll() { ... }
deleteSelected() { ... }
```

---

## ✅ CONCLUSÃO

### **Podemos implementar Selection System completo manualmente**

**Vantagens:**
- ✅ Funciona com Community Edition
- ✅ Controle total sobre comportamento
- ✅ Customização completa

**Desvantagens:**
- ❌ Mais trabalho manual
- ❌ Não temos métodos prontos do Toolkit

### **Tempo Estimado:**
- **Selection System Básico**: 2-3 horas
- **Lasso Selection**: 1-2 horas
- **Keyboard Shortcuts**: 1 hora
- **Total**: **4-6 horas** (conforme análise anterior)

---

## 🚀 PRÓXIMOS PASSOS

1. ✅ Implementar `enableSelection()` completo
2. ✅ Adicionar métodos de seleção
3. ✅ Implementar lasso selection
4. ✅ Adicionar keyboard shortcuts
5. ✅ Adicionar CSS para feedback visual

**Após implementar, teremos Selection System completo para V2.0.**

---

**Última Atualização**: 2025-12-11  
**Status**: ✅ **PODEMOS IMPLEMENTAR MANUALMENTE**  
**Tempo Estimado**: 4-6 horas

