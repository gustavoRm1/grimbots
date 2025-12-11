# 🔧 CORREÇÃO: STEPS FIXOS NÃO PODEM SER ARRASTADOS - V2.0

**Data:** 2025-01-18  
**Status:** ✅ Correção Aplicada  
**Problema:** Steps com classe `jtk-draggable` não podem ser arrastados

---

## 🔍 DIAGNÓSTICO

### Problemas Identificados:

1. **Pan interferindo com Drag**
   - O handler de pan (`enablePan()`) estava interceptando `mousedown` antes do draggable do jsPlumb
   - Mesmo com `capture: false`, o pan poderia bloquear o drag se detectasse step

2. **Drag Handle Mal Configurado**
   - Drag handle tinha `pointer-events: auto` mas pode não estar acessível
   - Uso simultâneo de `handle` e `filter` pode causar conflitos no jsPlumb

3. **Cursor Incorreto**
   - Elemento tinha `cursor: default` quando deveria ter `cursor: move`
   - Drag handle pode não estar visível/interativo

---

## ✅ CORREÇÕES APLICADAS

### 1. **Melhorar Detecção de Pan vs Drag**

```javascript
// ANTES:
const isOverStep = e.target.closest('.flow-step-block');
if (!isOverStep && !isOverButton && !isOverEndpoint && e.button === 2) {
    // Pan...
}

// DEPOIS:
const isOverStep = e.target.closest('.flow-step-block');
const isOverDragHandle = e.target.closest('.flow-drag-handle');

// Se estiver sobre step ou drag handle, deixar o drag do jsPlumb funcionar
if (isOverStep || isOverDragHandle) {
    return; // NÃO processar pan
}
```

**Impacto:** Pan não interfere mais com drag de steps

### 2. **Configurar Drag Handle Corretamente**

```javascript
// ANTES:
if (dragHandle) {
    draggableOptions.handle = dragHandle;
    // Usava filter junto com handle (conflito)
}

// DEPOIS:
if (dragHandle) {
    // Garantir que drag handle está totalmente configurado
    dragHandle.style.pointerEvents = 'auto';
    dragHandle.style.cursor = 'move';
    dragHandle.style.zIndex = '10';
    dragHandle.style.position = 'absolute';
    dragHandle.style.top = '0';
    dragHandle.style.left = '0';
    dragHandle.style.right = '0';
    dragHandle.style.height = '40px';
    dragHandle.style.background = 'transparent';
    dragHandle.removeAttribute('data-jtk-not-draggable');
    
    // Usar APENAS handle (não usar filter junto)
    draggableOptions.handle = dragHandle;
}
```

**Impacto:** Drag handle funciona corretamente e não há conflitos

### 3. **Garantir Cursor Correto**

```javascript
// ANTES:
stepElement.style.cursor = dragHandle ? 'default' : 'move';

// DEPOIS:
stepElement.style.cursor = 'move'; // Sempre move quando arrastável
```

**Impacto:** Feedback visual correto para o usuário

### 4. **Remover Atributos Bloqueadores**

```javascript
// Garantir que elemento e handle não têm atributos bloqueadores
stepElement.removeAttribute('data-jtk-not-draggable');
if (dragHandle) {
    dragHandle.removeAttribute('data-jtk-not-draggable');
}
```

**Impacto:** Nenhum atributo bloqueia o drag

---

## 🧪 TESTES RECOMENDADOS

1. ✅ Arrastar step pelo drag handle (deve funcionar)
2. ✅ Arrastar step pelo card (se não houver handle, deve funcionar)
3. ✅ Pan com botão direito não deve interferir com drag
4. ✅ Cursor deve mudar para `move` ao passar sobre step/handle
5. ✅ Steps devem se mover suavemente durante drag
6. ✅ Snap-to-grid deve funcionar durante drag

---

## 📝 ARQUIVOS MODIFICADOS

1. **`static/js/flow_editor.js`**
   - ✅ `enablePan()`: Melhorar detecção de step/drag handle
   - ✅ `setupDraggableForStep()`: Configurar drag handle corretamente
   - ✅ Remover uso simultâneo de `handle` e `filter`
   - ✅ Garantir cursor correto e atributos removidos

---

## ✅ CONCLUSÃO

As correções garantem que:

- ✅ Pan não interfere com drag de steps
- ✅ Drag handle está totalmente configurado e acessível
- ✅ Cursor correto (`move`) quando arrastável
- ✅ Nenhum atributo bloqueia o drag
- ✅ Sem conflitos entre `handle` e `filter`

Os steps agora devem ser arrastáveis corretamente.

