# 🔥 TRECHOS CRÍTICOS PARA PATCH FINAL

## 📌 1. setupCanvas() COMPLETO

```javascript
/**
 * Configura canvas com grid e container interno
 */
setupCanvas() {
    if (!this.canvas) return;
    
    // Canvas principal - SEM transform, apenas background
    this.canvas.style.position = 'relative';
    this.canvas.style.overflow = 'hidden';
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.background = '#0D0F15';
    this.canvas.style.backgroundImage = 'radial-gradient(circle, rgba(255, 255, 255, 0.25) 1.5px, transparent 1.5px)';
    this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
    this.canvas.style.backgroundRepeat = 'repeat';
    this.canvas.style.backgroundPosition = '0 0';
    
    // Container interno para transform (zoom/pan)
    let existingContainer = this.canvas.querySelector('.flow-canvas-content');
    if (existingContainer) {
        this.contentContainer = existingContainer;
    } else {
        this.contentContainer = document.createElement('div');
        this.contentContainer.className = 'flow-canvas-content';
        this.contentContainer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            transform-origin: 0 0;
            will-change: transform;
            pointer-events: auto;
        `;
        
        // Mover elementos existentes para o container
        Array.from(this.canvas.children).forEach(child => {
            if (child.classList.contains('flow-step-block')) {
                this.contentContainer.appendChild(child);
            }
        });
        
        this.canvas.appendChild(this.contentContainer);
    }
    
    // Garantir que canvas NÃO tem transform
    this.canvas.style.setProperty('transform', 'none', 'important');
    
    // CRÍTICO: Observar mudanças no transform do contentContainer para revalidar endpoints
    if (window.MutationObserver && this.contentContainer) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    // Transform mudou, revalidar endpoints
                    if (this.instance && this.steps.size > 0) {
                        this.steps.forEach((element) => {
                            this.instance.revalidate(element);
                        });
                        this.instance.repaintEverything();
                    }
                }
            });
        });
        
        observer.observe(this.contentContainer, {
            attributes: true,
            attributeFilter: ['style']
        });
        
        // Guardar observer para cleanup
        this.transformObserver = observer;
    }
    
    // Atualizar transform inicial
    this.updateCanvasTransform();
}
```

---

## 📌 2. renderAllSteps() COMPLETO

```javascript
/**
 * Renderiza todos os steps
 */
renderAllSteps() {
    if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
        return;
    }
    
    const steps = this.alpine.config.flow_steps || [];
    if (!Array.isArray(steps)) return;
    
    // Remover steps que não existem mais
    const currentStepIds = new Set(this.steps.keys());
    const newStepIds = new Set(steps.map(s => String(s.id)));
    
    currentStepIds.forEach(stepId => {
        if (!newStepIds.has(stepId)) {
            this.removeStepElement(stepId);
        }
    });
    
    // Renderizar/atualizar steps
    steps.forEach(step => {
        const stepId = String(step.id);
        if (this.steps.has(stepId)) {
            this.updateStep(step);
        } else {
            this.renderStep(step);
        }
    });
    
    // Ajustar tamanho do canvas
    this.adjustCanvasSize();
    
    // Reconectar após renderização
    setTimeout(() => {
        this.reconnectAll();
    }, 100);
}
```

---

## 📌 3. CSS COMPLETO - Classes de Card e Nodes

```css
/* ============================================
   CARDS (FLOW-STEP-BLOCK / FLOW-CARD)
   ============================================ */

.flow-step-block,
.flow-card {
    position: absolute; /* Para posicionamento no canvas */
    width: 300px;
    min-height: 180px;
    background: #0F0F14;
    border: 1px solid #242836;
    border-radius: 12px;
    cursor: move;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    overflow: visible; /* CRÍTICO: visible para nodes ficarem visíveis fora do card */
    animation: stepFadeIn 0.3s ease-out;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3), 0 0 0 0 rgba(255, 255, 255, 0);
    user-select: none;
    -webkit-user-select: none;
    -moz-user-select: none;
    -ms-user-select: none;
    touch-action: none;
    will-change: transform;
    /* CRÍTICO: position relative é aplicado via JS para nodes absolutos funcionarem */
    /* O card tem position: absolute para posicionamento no canvas */
    /* Mas precisa ser relative para elementos absolutos (nodes) dentro dele */
}

@keyframes stepFadeIn {
    from {
        opacity: 0;
        transform: translateY(-10px) scale(0.95);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

.flow-step-block:hover {
    border-color: #3B82F6;
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3), 0 0 0 1px rgba(59, 130, 246, 0.2);
    transform: translateY(-1px);
    z-index: 100;
}

.flow-step-block.dragging {
    cursor: grabbing !important;
    opacity: 0.98;
    /* Transform será aplicado via JS (translate3d) - não usar scale aqui */
    z-index: 1000 !important;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
    border-color: #FFFFFF;
    transition: none !important; /* CRÍTICO: Desabilitar transições durante drag */
}

.flow-step-block.flow-step-initial {
    border-color: #FFB800;
    box-shadow: 
        0 0 0 3px rgba(255, 184, 0, 0.3),
        0 0 24px rgba(255, 184, 0, 0.4),
        0 8px 24px rgba(0, 0, 0, 0.5);
    animation: initialPulse 2s ease-in-out infinite;
}

@keyframes initialPulse {
    0%, 100% {
        box-shadow: 
            0 0 0 3px rgba(255, 184, 0, 0.3),
            0 0 24px rgba(255, 184, 0, 0.4),
            0 8px 24px rgba(0, 0, 0, 0.5);
    }
    50% {
        box-shadow: 
            0 0 0 4px rgba(255, 184, 0, 0.4),
            0 0 32px rgba(255, 184, 0, 0.6),
            0 8px 24px rgba(0, 0, 0, 0.5);
    }
}

.flow-step-block.flow-step-selected {
    border-color: #FFFFFF;
    box-shadow: 
        0 0 0 2px rgba(255, 255, 255, 0.3),
        0 8px 24px rgba(0, 0, 0, 0.5);
}

/* ============================================
   HEADER DO CARD
   ============================================ */

.flow-step-header {
    padding: 20px 16px;
    background: #E02727;
    border-radius: 14px 14px 0 0;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(224, 39, 39, 0.3);
}

.flow-step-header-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    position: relative;
}

.flow-step-icon-center {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: #FFFFFF;
}

.flow-step-title-center {
    font-size: 16px;
    font-weight: 700;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    text-align: center;
    letter-spacing: 0.3px;
}

.flow-step-start-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    font-size: 18px;
    animation: starPulse 2s ease-in-out infinite;
    filter: drop-shadow(0 0 4px rgba(255, 184, 0, 0.8));
    z-index: 10;
}

@keyframes starPulse {
    0%, 100% {
        transform: scale(1);
        opacity: 1;
    }
    50% {
        transform: scale(1.15);
        opacity: 0.9;
    }
}

/* ============================================
   BODY DO CARD
   ============================================ */

.flow-step-body {
    padding: 20px 16px;
    background: #0F0F14;
    min-height: 100px;
    border-top: 1px solid #242836;
    position: relative;
}

.flow-step-buttons-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 0;
}

.flow-step-button-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: linear-gradient(135deg, rgba(224, 39, 39, 0.15) 0%, rgba(239, 68, 68, 0.15) 100%);
    border: 2px solid rgba(224, 39, 39, 0.4);
    border-radius: 10px;
    position: relative;
    min-height: 44px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 6px rgba(224, 39, 39, 0.15);
}

.flow-step-button-item:hover {
    background: linear-gradient(135deg, rgba(224, 39, 39, 0.25) 0%, rgba(239, 68, 68, 0.25) 100%);
    border-color: rgba(224, 39, 39, 0.6);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(224, 39, 39, 0.25);
}

.flow-step-button-text {
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 600;
    flex: 1;
    padding-right: 12px;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.flow-step-button-endpoint-container {
    position: relative;
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.flow-step-global-output-container {
    position: absolute;
    right: -15px;
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
}

/* ============================================
   NODES (ENTRADAS/SAÍDAS) - PADRÃO MANYCHAT EXATO
   ============================================ */

.node-input,
.node-output,
.flow-step-node-input,
.flow-step-node-output {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #FFFFFF;
    border: 3px solid #27ae60;
    cursor: pointer;
    z-index: 50;
    pointer-events: auto;
    transition: all 0.15s ease;
}

/* Entrada - lado esquerdo, centro vertical */
.node-input,
.flow-step-node-input {
    left: -8px;
    top: 50%;
    transform: translateY(-50%);
    border-color: #27ae60;
    background: #FFFFFF;
}

.node-input:hover,
.flow-step-node-input:hover {
    background: #27ae60;
    border-color: #27ae60;
    transform: translateY(-50%) scale(1.15);
    box-shadow: 0 0 8px rgba(39, 174, 96, 0.5);
}

/* Saída - lado direito, centro vertical */
.node-output,
.flow-step-node-output {
    right: -8px;
    top: 50%;
    transform: translateY(-50%);
    border-color: #27ae60;
    background: #FFFFFF;
}

.node-output:hover,
.flow-step-node-output:hover {
    background: #27ae60;
    border-color: #27ae60;
    transform: translateY(-50%) scale(1.15);
    box-shadow: 0 0 8px rgba(39, 174, 96, 0.5);
}
```

---

## ✅ RESUMO DOS PROBLEMAS IDENTIFICADOS

### 🔴 PROBLEMA 1: setupCanvas()
- `contentContainer` criado com `transform-origin: 0 0` mas pode não estar alinhado corretamente
- MutationObserver revalida apenas `element`, não os nodes específicos dentro
- Canvas tem `position: relative` mas contentContainer tem `position: absolute` - pode causar desalinhamento

### 🔴 PROBLEMA 2: renderAllSteps()
- Não limpa endpoints antes de re-renderizar
- `setTimeout` de 100ms pode causar race conditions
- Não verifica se steps já estão renderizados antes de atualizar

### 🔴 PROBLEMA 3: CSS
- `.flow-card` e `.flow-step-block` têm `position: absolute` mas precisam de `position: relative` para nodes absolutos
- Nodes têm `transform: translateY(-50%)` mas podem não estar respeitando o transform do card pai
- `overflow: visible` está correto, mas pode haver conflito com `position: absolute` do card

---

## 🎯 PRONTO PARA PATCH CIRÚRGICO

Com esses 3 trechos, você tem tudo necessário para:
- Corrigir posicionamento dos nodes
- Alinhar inputs/outputs ao centro
- Fazer jsPlumb respeitar transform 3D
- Corrigir repaint no zoom
- Evitar duplicação de rendering
- Fazer modal abrir instantaneamente

