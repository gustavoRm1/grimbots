# 📋 TRECHOS PARA ANÁLISE CIRÚRGICA - FLOW EDITOR

## 1️⃣ static/js/flow_editor.js - TRECHOS CRÍTICOS

### A) Constructor e Inicialização
```javascript
class FlowEditor {
    constructor(canvasId, alpineContext) {
        this.canvasId = canvasId;
        this.canvas = document.getElementById(canvasId);
        this.alpine = alpineContext;
        this.instance = null;  // jsPlumb instance
        this.steps = new Map();
        this.connections = new Map();
        this.selectedStep = null;
        this.contentContainer = null;
        
        // Zoom e Pan
        this.zoomLevel = 1;
        this.pan = { x: 0, y: 0 };
        this.isPanning = false;
        this.lastPanPoint = { x: 0, y: 0 };
        this.panFrameId = null;
        this.zoomFrameId = null;
        
        // Performance
        this.dragFrameId = null;
        this.repaintTimeout = null;
        this.stepTransforms = new Map();
        
        // Configurações
        this.gridSize = 20;
        this.minZoom = 0.2;
        this.maxZoom = 4.0;
        
        this.init();
    }
    
    init() {
        if (!this.canvas) {
            console.error('❌ Canvas não encontrado:', this.canvasId);
            return;
        }
        
        if (typeof jsPlumb === 'undefined') {
            console.error('❌ jsPlumb não está carregado');
            return;
        }
        
        // CRÍTICO: Setup canvas PRIMEIRO para criar contentContainer
        this.setupCanvas();
        
        // CRÍTICO: Setup jsPlumb DEPOIS, usando contentContainer como Container
        this.setupJsPlumb();
        
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
        
        // Renderizar steps após setup
        setTimeout(() => {
            this.renderAllSteps();
        }, 50);
    }
```

### B) Configuração do jsPlumb
```javascript
    setupJsPlumb() {
        try {
            // CRÍTICO: Container deve ser o contentContainer (onde os elementos estão)
            // Não usar this.canvas porque os elementos estão dentro de contentContainer
            const container = this.contentContainer || this.canvas;
            
            this.instance = jsPlumb.getInstance({
                Container: container
            });
            
            // Defaults: conexões brancas suaves estilo ManyChat
            this.instance.importDefaults({
                paintStyle: { 
                    stroke: '#FFFFFF', 
                    strokeWidth: 2.5,
                    strokeOpacity: 0.9
                },
                hoverPaintStyle: { 
                    stroke: '#FFFFFF', 
                    strokeWidth: 3.5,
                    strokeOpacity: 1
                },
                connector: ['Bezier', { 
                    curviness: 80,
                    stub: [15, 20],
                    gap: 8,
                    cornerRadius: 5
                }],
                endpoint: ['Dot', { radius: 7 }],
                endpointStyle: { 
                    fill: '#FFFFFF', 
                    outlineStroke: '#0D0F15', 
                    outlineWidth: 2
                },
                endpointHoverStyle: { 
                    fill: '#FFB800', 
                    outlineStroke: '#0D0F15', 
                    outlineWidth: 3
                },
                maxConnections: -1
            });
            
            // Eventos
            this.instance.bind('connection', (info) => this.onConnectionCreated(info));
            this.instance.bind('connectionDetached', (info) => this.onConnectionDetached(info));
            this.instance.bind('click', (conn, e) => {
                if (e && e.detail === 2) {
                    this.removeConnection(conn);
                }
            });
            
            console.log('✅ jsPlumb inicializado');
        } catch (error) {
            console.error('❌ Erro ao inicializar jsPlumb:', error);
        }
    }
```

### C) renderStep() - HTML do Card
```javascript
    renderStep(step) {
        if (!step || !step.id) return;
        
        const stepId = String(step.id);
        const stepType = step.type || 'message';
        const stepConfig = step.config || {};
        const position = step.position || { x: 100, y: 100 };
        const isStartStep = this.alpine?.config?.flow_start_step_id === stepId;
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Criar elemento - CRÍTICO: usar flow-card com position relative
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block flow-card';
        stepElement.dataset.stepId = stepId;
        
        // CRÍTICO: position relative para nodes absolutos funcionarem
        stepElement.style.position = 'relative';
        
        // Posição usando transform (GPU acceleration)
        stepElement.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
        stepElement.style.left = '0';
        stepElement.style.top = '0';
        stepElement.style.willChange = 'transform';
        
        // Cache de transform
        this.stepTransforms.set(stepId, { x: position.x, y: position.y });
        
        // Preview completo
        const mediaUrl = stepConfig.media_url || '';
        const mediaType = stepConfig.media_type || 'video';
        const previewText = this.getStepPreview(step);
        const mediaHTML = mediaUrl ? this.getMediaPreviewHtml(stepConfig, mediaType) : '';
        const buttonsHTML = hasButtons ? this.getButtonPreviewHtml(customButtons) : '';
        
        // HTML do card - CRÍTICO: Nodes DEVEM estar literalmente dentro do card
        stepElement.innerHTML = `
            <div class="flow-step-header">
                <div class="flow-step-header-content">
                    <div class="flow-step-icon-center">
                        <i class="fas ${this.stepIcons[stepType] || 'fa-circle'}" style="color: #FFFFFF;"></i>
                    </div>
                    <div class="flow-step-title-center">
                        ${this.getStepTypeLabel(stepType)}
                    </div>
                    ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
                </div>
            </div>
            <div class="flow-step-body">
                ${mediaHTML}
                ${previewText ? `<div class="flow-step-preview">${this.escapeHtml(previewText)}</div>` : ''}
                ${buttonsHTML}
            </div>
            <div class="flow-step-footer">
                <button class="flow-step-btn-action" onclick="window.flowEditor?.editStep('${stepId}')" title="Editar">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="flow-step-btn-action" onclick="window.flowEditor?.deleteStep('${stepId}')" title="Remover">
                    <i class="fas fa-trash"></i>
                </button>
                ${!isStartStep ? `<button class="flow-step-btn-action" onclick="window.flowEditor?.setStartStep('${stepId}')" title="Definir como inicial">⭐</button>` : ''}
            </div>
            <!-- CRÍTICO: Nodes DENTRO do card (padrão ManyChat) -->
            <div class="node-input flow-step-node-input" data-node-type="input" data-step-id="${stepId}"></div>
            ${!hasButtons ? '<div class="node-output flow-step-node-output" data-node-type="output" data-step-id="' + stepId + '"></div>' : ''}
        `;
        
        // Adicionar ao container
        const container = this.contentContainer || this.canvas;
        container.appendChild(stepElement);
        
        // Tornar arrastável (otimizado)
        this.instance.draggable(stepElement, {
            containment: 'parent',
            grid: false,
            drag: (params) => {
                this.onStepDrag(params);
            },
            stop: (params) => {
                this.onStepDragStop(params);
            },
            cursor: 'move',
            zIndex: 1000
        });
        
        // CRÍTICO: Adicionar endpoints APÓS o DOM estar completamente renderizado
        // Usar requestAnimationFrame para garantir que o layout foi calculado
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.addEndpoints(stepElement, stepId, step);
                // Revalidar e repintar após adicionar endpoints
                if (this.instance) {
                    this.instance.revalidate(stepElement);
                    this.instance.repaintEverything();
                }
            });
        });
        
        // Marcar como inicial se necessário
        if (isStartStep) {
            stepElement.classList.add('flow-step-initial');
        }
        
        this.steps.set(stepId, stepElement);
    }
```

### D) addEndpoints() - Criação de Endpoints
```javascript
    addEndpoints(element, stepId, step) {
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // CRÍTICO: Garantir que o card tenha position relative
        if (!element.style.position || element.style.position === 'absolute') {
            element.style.position = 'relative';
        }
        
        // 1. ENTRADA - LADO ESQUERDO, CENTRO VERTICAL
        // Usar o elemento HTML dentro do card (não o card inteiro)
        const inputNode = element.querySelector('.flow-step-node-input');
        if (inputNode) {
            this.instance.addEndpoint(inputNode, {
                uuid: `endpoint-left-${stepId}`,
                anchor: 'Center',
                maxConnections: -1,
                isSource: false,
                isTarget: true,
                endpoint: ['Dot', { radius: 7 }],
                paintStyle: { 
                    fill: '#10B981', 
                    outlineStroke: '#FFFFFF', 
                    outlineWidth: 2
                },
                hoverPaintStyle: { 
                    fill: '#FFB800', 
                    outlineStroke: '#FFFFFF', 
                    outlineWidth: 3
                },
                data: {
                    stepId: stepId,
                    endpointType: 'input'
                }
            });
        }
        
        // 2. SAÍDAS
        if (hasButtons) {
            // Com botões: endpoint individual por botão
            customButtons.forEach((btn, index) => {
                const buttonContainer = element.querySelector(`[data-endpoint-button="${index}"]`);
                if (buttonContainer) {
                    // Garantir que o container do botão tenha position relative
                    if (!buttonContainer.style.position) {
                        buttonContainer.style.position = 'relative';
                    }
                    this.instance.addEndpoint(buttonContainer, {
                        uuid: `endpoint-button-${stepId}-${index}`,
                        anchor: ['RightMiddle', { dx: 7 }],
                        maxConnections: 1,
                        isSource: true,
                        isTarget: false,
                        endpoint: ['Dot', { radius: 6 }],
                        paintStyle: { 
                            fill: '#FFFFFF', 
                            outlineStroke: '#0D0F15', 
                            outlineWidth: 2
                        },
                        hoverPaintStyle: { 
                            fill: '#FFB800', 
                            outlineStroke: '#FFFFFF', 
                            outlineWidth: 3
                        },
                        data: {
                            stepId: stepId,
                            buttonIndex: index,
                            endpointType: 'button'
                        }
                    });
                }
            });
        } else {
            // Sem botões: endpoint global - usar elemento HTML dentro do card
            const outputNode = element.querySelector('.flow-step-node-output');
            if (outputNode) {
                this.instance.addEndpoint(outputNode, {
                    uuid: `endpoint-right-${stepId}`,
                    anchor: 'Center',
                    maxConnections: -1,
                    isSource: true,
                    isTarget: false,
                    endpoint: ['Dot', { radius: 7 }],
                    paintStyle: { 
                        fill: '#FFFFFF', 
                        outlineStroke: '#0D0F15', 
                        outlineWidth: 2
                    },
                    hoverPaintStyle: { 
                        fill: '#FFB800', 
                        outlineStroke: '#FFFFFF', 
                        outlineWidth: 3
                    },
                    data: {
                        stepId: stepId,
                        endpointType: 'global'
                    }
                });
            }
        }
    }
```

### E) Drag Handlers
```javascript
    onStepDrag(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.add('dragging');
            
            // Cancelar frame anterior
            if (this.dragFrameId) {
                cancelAnimationFrame(this.dragFrameId);
            }
            
            // CRÍTICO: Revalidar e repintar durante drag
            this.dragFrameId = requestAnimationFrame(() => {
                if (this.instance) {
                    // Revalidar o elemento arrastado para recalcular endpoints
                    this.instance.revalidate(element);
                    // Repintar todas as conexões
                    this.instance.repaintEverything();
                }
                this.dragFrameId = null;
            });
        }
    }
    
    onStepDragStop(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.remove('dragging');
            
            // Extrair posição do transform
            const transform = element.style.transform || '';
            let x = 0, y = 0;
            
            if (transform && transform.includes('translate3d')) {
                const match = transform.match(/translate3d\(([^,]+)px,\s*([^,]+)px/);
                if (match) {
                    x = parseFloat(match[1]) || 0;
                    y = parseFloat(match[2]) || 0;
                }
            }
            
            // Snap to grid opcional
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
            
            // Atualizar posição
            element.style.transform = `translate3d(${x}px, ${y}px, 0)`;
            this.stepTransforms.set(stepId, { x, y });
            
            // Atualizar no Alpine
            this.updateStepPosition(stepId, { x, y });
            
            // CRÍTICO: Revalidar e repintar após drag parar
            if (this.instance) {
                // Revalidar o elemento para recalcular endpoints na nova posição
                this.instance.revalidate(element);
                // Repintar todas as conexões
                this.instance.repaintEverything();
            }
            
            // Ajustar canvas
            this.adjustCanvasSize();
        }
    }
    
    updateStepPosition(stepId, position) {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        const steps = this.alpine.config.flow_steps;
        const step = steps.find(s => String(s.id) === String(stepId));
        
        if (step) {
            if (!step.position) {
                step.position = {};
            }
            step.position.x = position.x;
            step.position.y = position.y;
        }
    }
```

### F) Zoom/Transform
```javascript
    updateCanvasTransform() {
        if (!this.contentContainer) return;
        
        const transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoomLevel})`;
        this.contentContainer.style.transform = transform;
        
        // CRÍTICO: Revalidar e repintar jsPlumb após transform
        // Revalidar recalcula as posições dos endpoints considerando o transform
        if (this.repaintTimeout) {
            clearTimeout(this.repaintTimeout);
        }
        this.repaintTimeout = setTimeout(() => {
            if (this.instance) {
                // CRÍTICO: Revalidar todos os elementos E seus nodes
                // Os nodes dentro dos cards acompanham o transform via CSS
                // Mas jsPlumb precisa recalcular as posições das conexões
                this.steps.forEach((element) => {
                    this.instance.revalidate(element);
                    // Revalidar nodes específicos dentro do card
                    const inputNode = element.querySelector('.flow-step-node-input');
                    const outputNode = element.querySelector('.flow-step-node-output');
                    if (inputNode) this.instance.revalidate(inputNode);
                    if (outputNode) this.instance.revalidate(outputNode);
                });
                // Repintar todas as conexões
                this.instance.repaintEverything();
            }
        }, 16); // ~60fps
    }
    
    enableZoom() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('wheel', (e) => {
            // Zoom com Ctrl/Cmd ou scroll direto (padrão ManyChat)
            if (e.ctrlKey || e.metaKey || true) {
                e.preventDefault();
                
                // Obter posição do mouse relativa ao canvas
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                // Calcular zoom delta suave (ManyChat style)
                const zoomSpeed = e.ctrlKey || e.metaKey ? 0.0015 : 0.001;
                const zoomDelta = -e.deltaY * zoomSpeed;
                const newZoom = Math.max(
                    this.minZoom, 
                    Math.min(this.maxZoom, this.zoomLevel * (1 + zoomDelta))
                );
                
                // CRÍTICO: Zoom focado no ponto do cursor (não no centro)
                // Converter coordenadas do mouse para coordenadas do mundo (antes do zoom)
                const worldX = (mouseX - this.pan.x) / this.zoomLevel;
                const worldY = (mouseY - this.pan.y) / this.zoomLevel;
                
                // Aplicar novo zoom
                this.zoomLevel = newZoom;
                
                // Ajustar pan para manter o ponto do cursor fixo
                this.pan.x = mouseX - worldX * this.zoomLevel;
                this.pan.y = mouseY - worldY * this.zoomLevel;
                
                // Aplicar imediatamente (já inclui revalidate de todos os nodes)
                this.updateCanvasTransform();
            }
        }, { passive: false });
    }
```

### G) Reconexão e Restauração
```javascript
    reconnectAll() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        // Limpar conexões antigas
        this.instance.deleteEveryConnection();
        this.connections.clear();
        
        const steps = this.alpine.config.flow_steps;
        if (!Array.isArray(steps)) return;
        
        steps.forEach(step => {
            if (!step || !step.id) return;
            
            const stepId = String(step.id);
            const stepConfig = step.config || {};
            const customButtons = stepConfig.custom_buttons || [];
            const hasButtons = customButtons.length > 0;
            const connections = step.connections || {};
            
            if (!this.steps.has(stepId)) return;
            
            // Conexões de botões
            if (hasButtons) {
                customButtons.forEach((btn, index) => {
                    if (btn.target_step) {
                        const targetId = String(btn.target_step);
                        if (this.steps.has(targetId)) {
                            this.createConnectionFromButton(stepId, index, targetId);
                        }
                    }
                });
            } else {
                // Conexões padrão (next, pending, retry)
                ['next', 'pending', 'retry'].forEach(connType => {
                    if (connections[connType]) {
                        const targetId = String(connections[connType]);
                        if (this.steps.has(targetId)) {
                            this.createConnection(stepId, targetId, connType);
                        }
                    }
                });
            }
        });
    }
```

### H) Handlers de Conexão
```javascript
    onConnectionCreated(info) {
        const sourceUuid = info.sourceEndpoint.getUuid();
        const targetUuid = info.targetEndpoint.getUuid();
        
        // Determinar tipo de conexão
        let sourceStepId = null;
        let buttonIndex = null;
        let connectionType = 'next';
        
        if (sourceUuid.includes('endpoint-button-')) {
            const match = sourceUuid.match(/endpoint-button-([^-]+)-(\d+)/);
            if (match) {
                sourceStepId = match[1];
                buttonIndex = parseInt(match[2]);
                connectionType = 'button';
            }
        } else if (sourceUuid.includes('endpoint-right-')) {
            sourceStepId = sourceUuid.replace('endpoint-right-', '');
            connectionType = 'next';
        }
        
        const targetStepId = targetUuid.includes('endpoint-left-') 
            ? targetUuid.replace('endpoint-left-', '') 
            : null;
        
        if (sourceStepId && targetStepId) {
            const connId = connectionType === 'button' && buttonIndex !== null
                ? `button-${sourceStepId}-${buttonIndex}-${targetStepId}`
                : `${sourceStepId}-${targetStepId}-${connectionType}`;
            
            this.connections.set(connId, info.connection);
            
            // Atualizar Alpine
            if (connectionType === 'button' && buttonIndex !== null) {
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceStepId);
                if (step && step.config && step.config.custom_buttons && step.config.custom_buttons[buttonIndex]) {
                    step.config.custom_buttons[buttonIndex].target_step = targetStepId;
                }
            } else {
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceStepId);
                if (step) {
                    if (!step.connections) step.connections = {};
                    step.connections[connectionType] = targetStepId;
                }
            }
        }
    }
    
    onConnectionDetached(info) {
        // Limpar do cache
        this.connections.forEach((conn, id) => {
            if (conn === info.connection) {
                this.connections.delete(id);
            }
        });
    }
```

---

## 2️⃣ HTML DO FLUXO (templates/bot_config.html)

### A) Container do Canvas
```html
<div x-show="config.flow_enabled" class="flow-canvas-container" style="width: 100%; height: 600px; border: 1px solid #242836; border-radius: 8px; overflow: hidden; position: relative; margin-top: 16px;">
    <div 
        id="flow-visual-canvas" 
        style="width: 100%; height: 100%; position: relative;"
        x-init="
            if (config.flow_enabled && activeTab === 'flow') {
                setTimeout(() => {
                    if (typeof FlowEditor !== 'undefined' && typeof jsPlumb !== 'undefined') {
                        initVisualFlowEditor();
                    } else if (window.flowEditor) {
                        window.flowEditor.renderAllSteps();
                    }
                }, 400);
            }
        "
    ></div>
</div>
```

### B) Botão Adicionar Step
```html
<button @click="addFlowStep()" class="btn btn-primary" :disabled="!config.flow_enabled">
    <i class="fas fa-plus"></i> Adicionar Step
</button>
```

### C) Handler addFlowStep()
```javascript
addFlowStep() {
    console.log('🔵 addFlowStep() chamado');
    
    if (!this.config.flow_steps) {
        this.config.flow_steps = [];
    }
    
    if (!this.config.flow_enabled) {
        this.config.flow_enabled = true;
        console.log('✅ Flow habilitado automaticamente');
        // Garantir que estamos na tab flow
        if (this.activeTab !== 'flow') {
            this.activeTab = 'flow';
            console.log('✅ Tab Flow ativada automaticamente');
        }
    }
    
    const stepId = `step_${Date.now()}`;
    
    const existingSteps = this.config.flow_steps.length;
    const cols = Math.ceil(Math.sqrt(existingSteps + 1));
    const row = Math.floor(existingSteps / cols);
    const col = existingSteps % cols;
    
    const newStep = {
        id: stepId,
        type: 'message',
        order: existingSteps,
        config: {
            message: '',
            media_url: '',
            audio_url: '',
            media_type: 'video',
            custom_buttons: []
        },
        connections: {},
        conditions: [],
        delay_seconds: 0,
        position: {
            x: 100 + (col * 280),
            y: 100 + (row * 180)
        }
    };
    
    this.config.flow_steps.push(newStep);
    console.log('✅ Step adicionado ao Alpine:', stepId, 'Total:', this.config.flow_steps.length);
    
    // Garantir que o editor está inicializado e renderizar
    this.$nextTick(() => {
        // Função para tentar renderizar
        const tryRender = () => {
            if (window.flowEditor && typeof window.flowEditor.renderAllSteps === 'function') {
                window.flowEditor.renderAllSteps();
                console.log('✅ Steps re-renderizados (jsPlumb)');
                return true;
            }
            return false;
        };
        
        // Tentar renderizar imediatamente
        if (tryRender()) {
            return;
        }
        
        // Se não funcionou, tentar inicializar o editor
        console.log('🆕 Editor não inicializado. Inicializando agora...');
        
        // Verificar se FlowEditor e jsPlumb estão disponíveis
        if (typeof window.FlowEditor === 'undefined' || typeof jsPlumb === 'undefined') {
            console.warn('⚠️ FlowEditor ou jsPlumb não está disponível. Aguardando carregamento...');
            // Aguardar até FlowEditor e jsPlumb estarem disponíveis
            let attempts = 0;
            const checkInterval = setInterval(() => {
                attempts++;
                if (typeof window.FlowEditor !== 'undefined' && typeof jsPlumb !== 'undefined') {
                    clearInterval(checkInterval);
                    this.initVisualFlowEditor();
                    setTimeout(() => tryRender(), 500);
                } else if (attempts > 20) {
                    clearInterval(checkInterval);
                    console.error('❌ FlowEditor ou jsPlumb não carregou após 4 segundos');
                }
            }, 200);
        } else {
            // FlowEditor está disponível, inicializar
            this.initVisualFlowEditor();
            // Aguardar um pouco e tentar renderizar
            setTimeout(() => {
                if (!tryRender()) {
                    console.warn('⚠️ Editor inicializado mas renderAllSteps ainda não está disponível. Tentando novamente...');
                    setTimeout(() => tryRender(), 500);
                }
            }, 500);
        }
    });
}
```

---

## 3️⃣ CSS RELEVANTE

### A) Canvas e Container
```css
.flow-canvas-container {
    position: relative;
    overflow: hidden; /* Impede o grid de escapar da div */
    width: 100%;
    height: 100%;
    border-radius: 8px;
}

#flow-visual-canvas {
    background: #0D0F15 !important;
    background-image: 
        radial-gradient(circle, rgba(255, 255, 255, 0.25) 1.5px, transparent 1.5px) !important;
    background-size: 20px 20px !important;
    background-repeat: repeat !important;
    background-position: 0 0 !important;
    font-family: 'Inter', sans-serif;
    user-select: none;
    -webkit-user-select: none;
    cursor: default;
    position: absolute; /* Canvas interno que pode ser maior que container (virtual) */
    left: 0;
    top: 0;
    transform-origin: 0 0; /* Para zoom via transform */
    will-change: transform;
    /* CRÍTICO: Canvas NUNCA deve ter transform - apenas o contentContainer */
    transform: none !important;
    /* Canvas pode ser maior que container (virtual canvas) */
    min-width: 1200px;
    min-height: 800px;
}

.flow-canvas-content {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    transform-origin: top left;
    will-change: transform;
    pointer-events: auto;
    z-index: 1;
}
```

### B) Cards
```css
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
```

### C) Nodes (ManyChat Style)
```css
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

## 4️⃣ VERSÕES E INCLUDES

```html
<!-- jsPlumb 2.15.6 -->
<script src="https://cdn.jsdelivr.net/npm/jsplumb@2.15.6/dist/js/jsplumb.min.js"></script>

<!-- Flow Editor (jsPlumb) -->
<script src="{{ url_for('static', filename='js/flow_editor.js') }}?v=4.0.0"></script>
```

No `base.html`:
```html
<!-- jsPlumb Community Edition - Editor Visual de Fluxo -->
<!-- CDN confiável do jsPlumb 2.x (carregar ANTES do Alpine.js) -->
<script src="https://cdn.jsdelivr.net/npm/jsplumb@2.15.6/dist/js/jsplumb.min.js"></script>

<!-- Alpine.js -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

---

## 5️⃣ PERSISTÊNCIA E RESTAURAÇÃO

### A) Salvar Posição (updateStepPosition)
```javascript
updateStepPosition(stepId, position) {
    if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
        return;
    }
    
    const steps = this.alpine.config.flow_steps;
    const step = steps.find(s => String(s.id) === String(stepId));
    
    if (step) {
        if (!step.position) {
            step.position = {};
        }
        step.position.x = position.x;
        step.position.y = position.y;
    }
}
```

### B) Restaurar Conexões (reconnectAll)
```javascript
reconnectAll() {
    // Limpar conexões antigas
    this.instance.deleteEveryConnection();
    this.connections.clear();
    
    const steps = this.alpine.config.flow_steps;
    if (!Array.isArray(steps)) return;
    
    steps.forEach(step => {
        const stepId = String(step.id);
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        const connections = step.connections || {};
        
        if (!this.steps.has(stepId)) return;
        
        // Conexões de botões
        if (hasButtons) {
            customButtons.forEach((btn, index) => {
                if (btn.target_step) {
                    const targetId = String(btn.target_step);
                    if (this.steps.has(targetId)) {
                        this.createConnectionFromButton(stepId, index, targetId);
                    }
                }
            });
        } else {
            // Conexões padrão (next, pending, retry)
            ['next', 'pending', 'retry'].forEach(connType => {
                if (connections[connType]) {
                    const targetId = String(connections[connType]);
                    if (this.steps.has(targetId)) {
                        this.createConnection(stepId, targetId, connType);
                    }
                }
            });
        }
    });
}
```

### C) Estrutura de Dados no Alpine
```javascript
// Ao adicionar step:
const newStep = {
    id: stepId,
    type: 'message',
    order: existingSteps,
    config: {
        message: '',
        media_url: '',
        audio_url: '',
        media_type: 'video',
        custom_buttons: []
    },
    connections: {},  // ← Conexões salvas aqui
    conditions: [],
    delay_seconds: 0,
    position: {  // ← Posição salva aqui
        x: 100 + (col * 280),
        y: 100 + (row * 180)
    }
};
```

---

## 6️⃣ getButtonPreviewHtml() - Estrutura dos Botões

```javascript
getButtonPreviewHtml(customButtons) {
    if (!customButtons || customButtons.length === 0) return '';
    
    let html = '<div class="flow-step-buttons-container" style="padding: 0 12px 12px 12px; display: flex; flex-direction: column; gap: 8px;">';
    
    customButtons.forEach((btn, index) => {
        const btnText = btn.text || `Botão ${index + 1}`;
        const btnColor = btn.color || '#E02727';
        
        html += `
            <div class="flow-step-button-item" 
                 data-button-index="${index}" 
                 data-button-id="${btn.id || `btn-${index}`}"
                 style="
                     background: ${btnColor};
                     border-radius: 6px;
                     padding: 10px 14px;
                     display: flex;
                     align-items: center;
                     justify-content: space-between;
                     position: relative;
                     min-height: 44px;
                 ">
                <span style="
                    color: #FFFFFF;
                    font-weight: 600;
                    font-size: 13px;
                    flex: 1;
                    padding-right: 12px;
                ">${this.escapeHtml(btnText)}</span>
                <div class="flow-step-button-endpoint-container" 
                     data-endpoint-button="${index}" 
                     style="
                         width: 14px;
                         height: 14px;
                         flex-shrink: 0;
                         position: relative;
                     "></div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}
```

---

## ✅ RESUMO DO PROBLEMA IDENTIFICADO

**CAUSA RAIZ:**
1. Cards têm `position: absolute` no CSS, mas precisam de `position: relative` para nodes absolutos funcionarem
2. JS aplica `position: relative` via `style.position`, mas pode ser sobrescrito
3. Nodes estão dentro do card, mas jsPlumb pode não estar recalculando corretamente após transform
4. `contentContainer` tem `transform: translate() scale()`, mas revalidação pode não estar capturando todos os nodes

**SOLUÇÃO NECESSÁRIA:**
- Garantir que `position: relative` seja aplicado via CSS (não apenas JS)
- Melhorar revalidação para incluir nodes específicos
- Verificar se `transform-origin` está correto
- Garantir que nodes acompanhem o card durante drag/zoom

