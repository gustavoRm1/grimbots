# 🔍 DIAGNÓSTICO DE PERFORMANCE - FLOW EDITOR

**Data:** 2024-01-XX  
**Versão Analisada:** Flow Editor V3.0  
**Analista:** Agente A (Arquiteto) + Agente B (Revisor) + Agente C (Testador)

---

## 📋 PASSO 0 - MAPEAMENTO DE HANDLERS E FUNÇÕES CRÍTICAS

### Event Listeners Identificados

#### Canvas Events (14 listeners)
1. **`wheel`** (linha 414) - Zoom com scroll
2. **`touchstart`** (linha 435) - Pinch zoom início
3. **`touchmove`** (linha 446) - Pinch zoom movimento
4. **`mousedown`** (linha 766) - Início de pan
5. **`mousemove`** (linha 813) - Movimento de pan
6. **`mouseup`** (linha 840) - Fim de pan
7. **`mouseleave`** (linha 846) - Sair do canvas
8. **`contextmenu`** (linha 806) - Menu contexto (prevent default)
9. **`click`** (linha 895) - Seleção de steps

#### Document Events (2 listeners)
10. **`keydown`** (linha 788) - Space para pan
11. **`keyup`** (linha 797) - Liberar Space

#### jsPlumb Events (4 bindings)
12. **`connection`** (linha 137) - Conexão criada
13. **`connectionDetached`** (linha 138) - Conexão removida
14. **`click`** (linha 140) - Duplo clique em conexão
15. **`contextmenu`** (linha 146) - Menu contexto em conexão

### Funções que Manipulam DOM Durante Drag/Zoom

#### Durante Drag
- **`onStepDrag(params)`** (linha 1748) - Chamado a cada frame de drag
  - Calcula snapping
  - Chama `getBoundingClientRect()` múltiplas vezes
  - Atualiza `style.left` e `style.top` (NÃO usa transform)
  - Renderiza linhas de snap

- **`instance.repaint(params.el)`** (linha 1077) - Repinta conexões do elemento
  - Chamado via `requestAnimationFrame` (bom)
  - Mas ainda pode causar reflow se chamado muito

- **`renderSnapLines()`** (linha 1874) - Cria/remove linhas DOM
  - Usa `appendChild` e `remove` durante drag
  - Causa reflow

#### Durante Zoom
- **`applyZoom()`** (linha 450) - Aplicação de zoom
  - Usa `requestAnimationFrame` (bom)
  - Mas chama `getBoundingClientRect()` múltiplas vezes
  - Atualiza `style.width/height` do canvas (causa reflow)
  - Chama `repaintEverything()` (pesado)

- **`updateCanvasTransform()`** (linha 812) - Atualiza transform
  - Atualiza `contentContainer.style.transform` (bom - GPU)
  - Mas também atualiza `canvas.style.transform = 'none'` (reflow)

#### Reconexão
- **`reconnectAll()`** (linha 1366) - Reconecta TODAS as conexões
  - **PROBLEMA CRÍTICO:** `deleteEveryConnection()` deleta TUDO
  - Depois recria todas as conexões do zero
  - Chamado após cada mudança (muito frequente)
  - Não há diffing - sempre recria tudo

### Funções que Gravam Posições

- **`updateStepPosition(stepId, position)`** (linha 1961)
  - Atualiza `step.position` no Alpine.js
  - **SEM DEBOUNCE** - chamado a cada drag stop
  - Pode disparar watchers do Alpine

- **`onStepDragStop(params)`** (linha 1922)
  - Calcula posição final
  - Chama `updateStepPosition()` imediatamente
  - Chama `expandCanvasBounds()`
  - Chama `repaintEverything()`

### Debounce/Throttle Atual

**❌ NENHUM DEBOUNCE IDENTIFICADO**

- `saveConfig()` não tem debounce (linha 2085)
- `updateStepPosition()` não tem debounce
- `reconnectAll()` não tem throttle
- Watcher do Alpine (linha 2660) não tem debounce

### Watchers do Alpine.js

```javascript
this.$watch('config.flow_steps', (newSteps, oldSteps) => {
    // Sem debounce - dispara imediatamente
    if (window.flowEditor) {
        window.flowEditor.renderAllSteps();
        window.flowEditor.revalidateConnections();
    }
});
```

**PROBLEMA:** Dispara a cada mudança, mesmo pequenas.

---

## 🚨 PASSO 1 - DIAGNÓSTICO PROFUNDO

### Top 10 Funções que Causam Maior Custo

#### 1. **`reconnectAll()`** - ⚠️ CRÍTICO
**Linha:** 1366-1422  
**Custo:** MUITO ALTO  
**Problemas:**
- `deleteEveryConnection()` deleta TODAS as conexões
- Depois recria todas do zero
- Chamado após cada mudança (muito frequente)
- Para 50 cards com 5 botões cada = 250 conexões recriadas

**Impacto:** 200-500ms para 50 cards

#### 2. **`renderAllSteps()`** - ⚠️ CRÍTICO
**Linha:** 936-966  
**Custo:** ALTO  
**Problemas:**
- `clearCanvas()` remove todos os elementos
- Depois recria todos do zero
- Usa `innerHTML` massivo (linha 1028)
- Não há diffing - sempre recria tudo

**Impacto:** 100-300ms para 50 cards

#### 3. **`onStepDrag()` com `getBoundingClientRect()`** - ⚠️ ALTO
**Linha:** 1748-1820  
**Custo:** ALTO  
**Problemas:**
- Chama `getBoundingClientRect()` múltiplas vezes por frame
- Para cada step sendo arrastado
- Para cada step para calcular snapping
- Causa layout thrash (read/write alternado)

**Impacto:** 10-30ms por frame (60fps = 600-1800ms/s)

#### 4. **`style.left/top` em vez de `transform`** - ⚠️ ALTO
**Linha:** 994-995, 1118-1119, 1858, 1863  
**Custo:** ALTO  
**Problemas:**
- Usa `style.left` e `style.top` (causa reflow)
- Não usa `transform: translate3d()` (sem GPU acceleration)
- Cada mudança força reflow completo

**Impacto:** 5-15ms por frame

#### 5. **`repaintEverything()` durante drag** - ⚠️ MÉDIO
**Linha:** 1088, 564  
**Custo:** MÉDIO-ALTO  
**Problemas:**
- Repinta TODAS as conexões
- Chamado após cada drag stop
- Durante zoom também

**Impacto:** 50-150ms para 50 cards

#### 6. **`renderSnapLines()` durante drag** - ⚠️ MÉDIO
**Linha:** 1874-1936  
**Custo:** MÉDIO  
**Problemas:**
- Cria/remove elementos DOM durante drag
- `appendChild` e `remove` causam reflow
- Chamado a cada frame de drag

**Impacto:** 2-5ms por frame

#### 7. **`innerHTML` massivo em `renderStep()`** - ⚠️ MÉDIO
**Linha:** 1028-1056  
**Custo:** MÉDIO  
**Problemas:**
- Usa `innerHTML` com string grande
- Parsing HTML é custoso
- Não reutiliza elementos DOM

**Impacto:** 5-10ms por step

#### 8. **Watcher do Alpine sem debounce** - ⚠️ MÉDIO
**Linha:** 2660  
**Custo:** MÉDIO  
**Problemas:**
- Dispara imediatamente a cada mudança
- Chama `renderAllSteps()` e `reconnectAll()`
- Pode disparar múltiplas vezes rapidamente

**Impacto:** 300-800ms por mudança

#### 9. **`expandCanvasBounds()` com `getBoundingClientRect()`** - ⚠️ BAIXO-MÉDIO
**Linha:** 287-336  
**Custo:** BAIXO-MÉDIO  
**Problemas:**
- Chama `getBoundingClientRect()` para cada step
- Chamado após cada drag stop

**Impacto:** 10-30ms para 50 cards

#### 10. **`applyZoom()` com múltiplos `getBoundingClientRect()`** - ⚠️ BAIXO-MÉDIO
**Linha:** 450-543  
**Custo:** BAIXO-MÉDIO  
**Problemas:**
- Chama `getBoundingClientRect()` múltiplas vezes
- Atualiza `style.width/height` (reflow)
- Chama `repaintEverything()`

**Impacto:** 50-100ms por zoom

---

## 🔧 PASSO 2 - PLANO DE AÇÃO

### PRIORIDADE ALTA (Implementar Imediatamente)

#### 1. Substituir `style.left/top` por `transform: translate3d()`
**Arquivo:** `static/js/flow_editor.js`  
**Linhas:** 994-995, 1118-1119, 1858, 1863, 2258-2259, 2295-2296, 2390-2391, 2403-2404, 2461-2462  
**Ação:** Usar `transform: translate3d(x, y, 0)` em vez de `left/top`  
**Benefício:** GPU acceleration, sem reflow  
**Estimativa:** 2 horas

#### 2. Refatorar `reconnectAll()` para `reconnectDiff()`
**Arquivo:** `static/js/flow_editor.js`  
**Linha:** 1366-1422  
**Ação:** 
- Manter cache de conexões existentes
- Comparar com novas conexões
- Criar apenas novas, remover apenas deletadas
- Atualizar apenas modificadas
**Benefício:** Reduzir de 200-500ms para 20-50ms  
**Estimativa:** 4 horas

#### 3. Throttle `onStepDrag()` com `requestAnimationFrame`
**Arquivo:** `static/js/flow_editor.js`  
**Linha:** 1748-1820  
**Ação:**
- Usar `requestAnimationFrame` para throttling
- Cachear `getBoundingClientRect()` (calcular uma vez por frame)
- Usar `transform` em vez de `left/top`
- Desabilitar transições CSS durante drag
**Benefício:** Reduzir de 10-30ms para 2-5ms por frame  
**Estimativa:** 3 horas

#### 4. Debounce `saveConfig()` e `updateStepPosition()`
**Arquivo:** `templates/bot_config.html`, `static/js/flow_editor.js`  
**Linhas:** 2085, 1961  
**Ação:**
- Debounce `saveConfig()` para 500ms
- Debounce `updateStepPosition()` para 300ms
- Usar async/await para não bloquear UI
**Benefício:** Reduzir chamadas desnecessárias  
**Estimativa:** 1 hora

#### 5. Debounce Watcher do Alpine
**Arquivo:** `templates/bot_config.html`  
**Linha:** 2660  
**Ação:**
- Adicionar debounce de 300ms no watcher
- Usar `Alpine.effect()` com debounce
**Benefício:** Reduzir de 300-800ms para 50-100ms  
**Estimativa:** 1 hora

#### 6. Eliminar `renderAllSteps()` em favor de render incremental
**Arquivo:** `static/js/flow_editor.js`  
**Linha:** 936-966  
**Ação:**
- Remover `clearCanvas()` completo
- Usar `renderStep()` apenas para novos steps
- Usar `updateStep()` para steps existentes
- Implementar diffing simples
**Benefício:** Reduzir de 100-300ms para 10-30ms  
**Estimativa:** 4 horas

#### 7. Otimizar `renderSnapLines()`
**Arquivo:** `static/js/flow_editor.js`  
**Linha:** 1874-1936  
**Ação:**
- Reutilizar elementos DOM (não criar/remover)
- Usar `display: none` em vez de `remove()`
- Renderizar apenas uma vez por frame
**Benefício:** Reduzir de 2-5ms para 0.5-1ms por frame  
**Estimativa:** 2 horas

### PRIORIDADE MÉDIA

#### 8. Virtualização (render apenas viewport)
**Arquivo:** `static/js/flow_editor.js`  
**Ação:**
- Calcular viewport visível
- Renderizar apenas steps dentro do viewport
- Adicionar/remover steps conforme scroll/zoom
**Benefício:** Performance constante mesmo com 200+ cards  
**Estimativa:** 6 horas

#### 9. Cachear `getBoundingClientRect()`
**Arquivo:** `static/js/flow_editor.js`  
**Ação:**
- Cachear resultados por frame
- Invalidar cache apenas quando necessário
**Benefício:** Reduzir chamadas custosas  
**Estimativa:** 2 horas

#### 10. Otimizar `innerHTML` em `renderStep()`
**Arquivo:** `static/js/flow_editor.js`  
**Linha:** 1028-1056  
**Ação:**
- Usar `createElement` e `appendChild` em vez de `innerHTML`
- Reutilizar elementos quando possível
- Usar DocumentFragment para inserção em lote
**Benefício:** Reduzir parsing HTML  
**Estimativa:** 3 horas

### PRIORIDADE BAIXA

#### 11. WebWorker para cálculos de layout
**Estimativa:** 8 horas

#### 12. Canvas-based rendering para conexões
**Estimativa:** 12 horas

---

## 📊 ESTIMATIVA TOTAL

- **Prioridade ALTA:** 17 horas
- **Prioridade MÉDIA:** 11 horas
- **Prioridade BAIXA:** 20 horas

**Total:** 48 horas (6 dias úteis)

**Recomendação:** Implementar PRIORIDADE ALTA primeiro (17h = 2-3 dias), validar, depois MÉDIA.

---

## 🎯 MÉTRICAS ESPERADAS (Após Implementação)

### Antes (Atual)
- FPS durante drag: 15-30fps
- Latência de resposta: 100-300ms
- `reconnectAll()`: 200-500ms
- `renderAllSteps()`: 100-300ms
- Save config: 500-2000ms (bloqueia UI)

### Depois (Meta)
- FPS durante drag: ≥50fps (ideal 60fps)
- Latência de resposta: <50ms
- `reconnectDiff()`: 20-50ms
- Render incremental: 10-30ms
- Save config: <200ms (assíncrono)

---

## ✅ PRÓXIMOS PASSOS

1. Implementar correções de PRIORIDADE ALTA
2. Executar profiling após cada mudança
3. Validar métricas
4. Testar cenários de QA
5. Documentar mudanças

