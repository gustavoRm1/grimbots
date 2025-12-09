/**
 * Flow Editor V4.0 - Rebuild Completo ManyChat-Level
 * Sistema profissional de edição visual de fluxos
 * 
 * ✅ CORREÇÕES IMPLEMENTADAS:
 * - Drag instantâneo sem delay
 * - Zoom suave com foco no mouse (scroll + Ctrl)
 * - Pan suave com botão direito (estilo Figma)
 * - Conexões perfeitas que acompanham cards
 * - Endpoints corretos: entrada à esquerda, saídas nos botões
 * - Preview completo: mídia, texto, botões
 * - Canvas responsivo sem estouro
 * - Performance otimizada com rAF
 * 
 * Dependências:
 * - jsPlumb 2.15.6 (CDN)
 * - Alpine.js 3.x (CDN)
 */

class FlowEditor {
    constructor(canvasId, alpineContext) {
        this.canvasId = canvasId;
        this.canvas = document.getElementById(canvasId);
        this.alpine = alpineContext;
        this.instance = null;
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
        
        // Cores e ícones
        this.stepIcons = {
            message: 'fa-comment',
            payment: 'fa-credit-card',
            access: 'fa-key',
            content: 'fa-file-alt',
            audio: 'fa-headphones',
            video: 'fa-video',
            buttons: 'fa-mouse-pointer'
        };
        
        this.init();
    }
    
    /**
     * Inicialização principal
     */
    init() {
        if (!this.canvas) {
            console.error('❌ Canvas não encontrado:', this.canvasId);
            return;
        }
        
        if (typeof jsPlumb === 'undefined') {
            console.error('❌ jsPlumb não está carregado');
            return;
        }
        
        this.setupJsPlumb();
        this.setupCanvas();
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
        
        // Renderizar steps após setup
        setTimeout(() => {
            this.renderAllSteps();
        }, 50);
    }
    
    /**
     * Configura jsPlumb com conexões brancas suaves
     */
    setupJsPlumb() {
        try {
            this.instance = jsPlumb.getInstance({
                Container: this.canvas
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
        
        // Atualizar transform inicial
        this.updateCanvasTransform();
    }
    
    /**
     * Atualiza transform do contentContainer (zoom + pan)
     */
    updateCanvasTransform() {
        if (!this.contentContainer) return;
        
        const transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoomLevel})`;
        this.contentContainer.style.transform = transform;
        
        // Repintar jsPlumb de forma otimizada
        if (this.repaintTimeout) {
            clearTimeout(this.repaintTimeout);
        }
        this.repaintTimeout = setTimeout(() => {
            if (this.instance) {
                this.instance.repaintEverything();
            }
        }, 16); // ~60fps
    }
    
    /**
     * Zoom suave com foco no mouse (scroll + Ctrl)
     */
    enableZoom() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('wheel', (e) => {
            // Zoom com Ctrl/Cmd ou scroll direto
            if (e.ctrlKey || e.metaKey || true) {
                e.preventDefault();
                
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                // Calcular zoom delta suave
                const zoomSpeed = e.ctrlKey || e.metaKey ? 0.001 : 0.0008;
                const zoomDelta = -e.deltaY * zoomSpeed;
                const newZoom = Math.max(
                    this.minZoom, 
                    Math.min(this.maxZoom, this.zoomLevel * (1 + zoomDelta))
                );
                
                // Zoom focado no mouse
                const worldX = (mouseX - this.pan.x) / this.zoomLevel;
                const worldY = (mouseY - this.pan.y) / this.zoomLevel;
                
                this.zoomLevel = newZoom;
                this.pan.x = mouseX - worldX * this.zoomLevel;
                this.pan.y = mouseY - worldY * this.zoomLevel;
                
                // Aplicar imediatamente
                this.updateCanvasTransform();
            }
        }, { passive: false });
    }
    
    /**
     * Pan suave com botão direito (estilo Figma)
     */
    enablePan() {
        if (!this.canvas) return;
        
        const startPan = (e) => {
            const isOverStep = e.target.closest('.flow-step-block');
            const isOverButton = e.target.closest('button');
            const isOverEndpoint = e.target.closest('.jtk-endpoint');
            
            // Pan apenas se não estiver sobre step/button/endpoint E for botão direito
            if (!isOverStep && !isOverButton && !isOverEndpoint && e.button === 2) {
                e.preventDefault();
                this.isPanning = true;
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
                this.canvas.style.cursor = 'grabbing';
                this.canvas.classList.add('panning');
                
                if (!this.panFrameId) {
                    const panLoop = () => {
                        if (this.isPanning) {
                            this.updateCanvasTransform();
                            this.panFrameId = requestAnimationFrame(panLoop);
                        } else {
                            this.panFrameId = null;
                        }
                    };
                    this.panFrameId = requestAnimationFrame(panLoop);
                }
            }
        };
        
        this.canvas.addEventListener('mousedown', startPan);
        
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isPanning) {
                e.preventDefault();
                const dx = e.clientX - this.lastPanPoint.x;
                const dy = e.clientY - this.lastPanPoint.y;
                
                this.pan.x += dx;
                this.pan.y += dy;
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isPanning = false;
            this.canvas.style.cursor = '';
            this.canvas.classList.remove('panning');
        });
        
        this.canvas.addEventListener('contextmenu', (e) => {
            const isOverStep = e.target.closest('.flow-step-block');
            if (!isOverStep && this.isPanning) {
                e.preventDefault();
            }
        });
    }
    
    /**
     * Habilita seleção de steps
     */
    enableSelection() {
        // Implementação básica - pode ser expandida
    }
    
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
    
    /**
     * Renderiza um step individual
     */
    renderStep(step) {
        if (!step || !step.id) return;
        
        const stepId = String(step.id);
        const stepType = step.type || 'message';
        const stepConfig = step.config || {};
        const position = step.position || { x: 100, y: 100 };
        const isStartStep = this.alpine?.config?.flow_start_step_id === stepId;
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Criar elemento
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block';
        stepElement.dataset.stepId = stepId;
        
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
        
        // HTML do card
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
            ${!hasButtons ? '<div class="flow-step-global-output-container"></div>' : ''}
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
        
        // Adicionar endpoints APÓS o DOM estar pronto
        // Usar setTimeout para garantir que o DOM foi renderizado
        setTimeout(() => {
            this.addEndpoints(stepElement, stepId, step);
            // Repintar após adicionar endpoints
            if (this.instance) {
                this.instance.repaintEverything();
            }
        }, 10);
        
        // Marcar como inicial se necessário
        if (isStartStep) {
            stepElement.classList.add('flow-step-initial');
        }
        
        this.steps.set(stepId, stepElement);
    }
    
    /**
     * Atualiza um step existente
     */
    updateStep(step) {
        const stepId = String(step.id);
        const element = this.steps.get(stepId);
        
        if (!element) {
            this.renderStep(step);
            return;
        }
        
        // Atualizar posição
        const position = step.position || { x: 100, y: 100 };
        element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
        this.stepTransforms.set(stepId, { x: position.x, y: position.y });
        
        // Remover endpoints antigos
        this.instance.removeAllEndpoints(element);
        
        // Re-renderizar conteúdo
        const stepType = step.type || 'message';
        const stepConfig = step.config || {};
        const isStartStep = this.alpine?.config?.flow_start_step_id === stepId;
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        const mediaUrl = stepConfig.media_url || '';
        const mediaType = stepConfig.media_type || 'video';
        const previewText = this.getStepPreview(step);
        const mediaHTML = mediaUrl ? this.getMediaPreviewHtml(stepConfig, mediaType) : '';
        const buttonsHTML = hasButtons ? this.getButtonPreviewHtml(customButtons) : '';
        
        // Atualizar header
        const headerEl = element.querySelector('.flow-step-header-content');
        if (headerEl) {
            headerEl.innerHTML = `
                <div class="flow-step-icon-center">
                    <i class="fas ${this.stepIcons[stepType] || 'fa-circle'}" style="color: #FFFFFF;"></i>
                </div>
                <div class="flow-step-title-center">
                    ${this.getStepTypeLabel(stepType)}
                </div>
                ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
            `;
        }
        
        // Atualizar body
        const bodyEl = element.querySelector('.flow-step-body');
        if (bodyEl) {
            bodyEl.innerHTML = `
                ${mediaHTML}
                ${previewText ? `<div class="flow-step-preview">${this.escapeHtml(previewText)}</div>` : ''}
                ${buttonsHTML}
            `;
        }
        
        // Atualizar container de saída global
        let globalOutputContainer = element.querySelector('.flow-step-global-output-container');
        if (!hasButtons) {
            if (!globalOutputContainer) {
                globalOutputContainer = document.createElement('div');
                globalOutputContainer.className = 'flow-step-global-output-container';
                element.appendChild(globalOutputContainer);
            }
        } else {
            if (globalOutputContainer) {
                globalOutputContainer.remove();
            }
        }
        
        // Re-adicionar endpoints APÓS o DOM estar pronto
        setTimeout(() => {
            this.addEndpoints(element, stepId, step);
            // Repintar após adicionar endpoints
            if (this.instance) {
                this.instance.repaintEverything();
            }
        }, 10);
        
        // Atualizar classe inicial
        if (isStartStep) {
            element.classList.add('flow-step-initial');
        } else {
            element.classList.remove('flow-step-initial');
        }
    }
    
    /**
     * Adiciona endpoints ao step
     * ESPECIFICAÇÃO:
     * - Entrada: LADO ESQUERDO, CENTRO VERTICAL
     * - Saídas com botões: UM endpoint por botão, LADO DIREITO do botão
     * - Saída sem botões: UM endpoint global, LADO DIREITO, CENTRO VERTICAL
     */
    addEndpoints(element, stepId, step) {
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // 1. ENTRADA - LADO ESQUERDO, CENTRO VERTICAL
        // Usar anchor fixo que se recalcula automaticamente
        this.instance.addEndpoint(element, {
            uuid: `endpoint-left-${stepId}`,
            anchor: 'LeftMiddle',
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
                        anchor: 'RightMiddle',
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
            // Sem botões: endpoint global
            let globalOutputContainer = element.querySelector('.flow-step-global-output-container');
            if (!globalOutputContainer) {
                globalOutputContainer = document.createElement('div');
                globalOutputContainer.className = 'flow-step-global-output-container';
                globalOutputContainer.style.cssText = `
                    position: absolute;
                    right: -7px;
                    top: 50%;
                    transform: translateY(-50%);
                    width: 14px;
                    height: 14px;
                `;
                element.appendChild(globalOutputContainer);
            }
            
            // Garantir que o container global tenha position relative
            if (!globalOutputContainer.style.position) {
                globalOutputContainer.style.position = 'relative';
            }
            this.instance.addEndpoint(globalOutputContainer, {
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
    
    /**
     * Callback quando step é arrastado (otimizado)
     */
    onStepDrag(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.add('dragging');
            
            // Cancelar frame anterior
            if (this.dragFrameId) {
                cancelAnimationFrame(this.dragFrameId);
            }
            
            // Atualizar conexões de forma otimizada
            this.dragFrameId = requestAnimationFrame(() => {
                if (this.instance) {
                    // Repintar todas as conexões (jsPlumb recalcula automaticamente)
                    this.instance.repaintEverything();
                }
                this.dragFrameId = null;
            });
        }
    }
    
    /**
     * Callback quando drag para
     */
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
            
            // Repintar conexões (jsPlumb recalcula endpoints automaticamente)
            if (this.instance) {
                // Repintar todas as conexões
                this.instance.repaintEverything();
            }
            
            // Ajustar canvas
            this.adjustCanvasSize();
        }
    }
    
    /**
     * Atualiza posição do step no Alpine
     */
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
    
    /**
     * Reconecta todas as conexões
     */
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
    
    /**
     * Cria conexão padrão (sem botões)
     */
    createConnection(sourceStepId, targetStepId, connectionType = 'next') {
        const sourceId = String(sourceStepId);
        const targetId = String(targetStepId);
        
        if (sourceId === targetId) return null;
        
        const sourceElement = this.steps.get(sourceId);
        const targetElement = this.steps.get(targetId);
        
        if (!sourceElement || !targetElement) return null;
        
        const connId = `${sourceId}-${targetId}-${connectionType}`;
        if (this.connections.has(connId)) {
            return this.connections.get(connId);
        }
        
        try {
            const connection = this.instance.connect({
                source: `endpoint-right-${sourceId}`,
                target: `endpoint-left-${targetId}`,
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
                overlays: [
                    ['Label', {
                        label: this.getConnectionLabel(connectionType),
                        location: 0.5,
                        cssClass: 'connection-label-white',
                        labelStyle: {
                            color: '#FFFFFF',
                            backgroundColor: '#0D0F15',
                            border: '1px solid #242836',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '10px',
                            fontWeight: '600'
                        }
                    }]
                ],
                data: {
                    sourceStepId: sourceId,
                    targetStepId: targetId,
                    connectionType: connectionType
                }
            });
            
            if (connection) {
                this.connections.set(connId, connection);
                
                // Atualizar Alpine
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceId);
                if (step && (!step.connections || !step.connections[connectionType])) {
                    if (!step.connections) step.connections = {};
                    step.connections[connectionType] = targetId;
                }
            }
            
            return connection;
        } catch (error) {
            console.error('❌ Erro ao criar conexão:', error);
            return null;
        }
    }
    
    /**
     * Cria conexão a partir de botão
     */
    createConnectionFromButton(sourceStepId, buttonIndex, targetStepId) {
        const sourceId = String(sourceStepId);
        const targetId = String(targetStepId);
        
        if (sourceId === targetId) return null;
        
        const sourceElement = this.steps.get(sourceId);
        const targetElement = this.steps.get(targetId);
        
        if (!sourceElement || !targetElement) return null;
        
        const connId = `button-${sourceId}-${buttonIndex}-${targetId}`;
        if (this.connections.has(connId)) {
            return this.connections.get(connId);
        }
        
        try {
            const connection = this.instance.connect({
                source: `endpoint-button-${sourceId}-${buttonIndex}`,
                target: `endpoint-left-${targetId}`,
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
                overlays: [
                    ['Label', {
                        label: 'Botão',
                        location: 0.5,
                        cssClass: 'connection-label-white',
                        labelStyle: {
                            color: '#FFFFFF',
                            backgroundColor: '#0D0F15',
                            border: '1px solid #242836',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '10px',
                            fontWeight: '600'
                        }
                    }]
                ],
                data: {
                    sourceStepId: sourceId,
                    targetStepId: targetId,
                    buttonIndex: buttonIndex,
                    connectionType: 'button'
                }
            });
            
            if (connection) {
                this.connections.set(connId, connection);
                
                // Atualizar Alpine
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceId);
                if (step && step.config && step.config.custom_buttons && step.config.custom_buttons[buttonIndex]) {
                    step.config.custom_buttons[buttonIndex].target_step = targetId;
                }
            }
            
            return connection;
        } catch (error) {
            console.error('❌ Erro ao criar conexão do botão:', error);
            return null;
        }
    }
    
    /**
     * Callback quando conexão é criada
     */
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
    
    /**
     * Callback quando conexão é removida
     */
    onConnectionDetached(info) {
        // Limpar do cache
        this.connections.forEach((conn, id) => {
            if (conn === info.connection) {
                this.connections.delete(id);
            }
        });
    }
    
    /**
     * Remove uma conexão
     */
    removeConnection(connection) {
        if (!connection) return;
        
        const data = connection.getData();
        if (data) {
            const { sourceStepId, targetStepId, connectionType, buttonIndex } = data;
            
            // Atualizar Alpine
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const sourceStep = steps.find(s => String(s.id) === String(sourceStepId));
                
                if (sourceStep) {
                    if (connectionType === 'button' && buttonIndex !== null && buttonIndex !== undefined) {
                        if (sourceStep.config && sourceStep.config.custom_buttons && sourceStep.config.custom_buttons[buttonIndex]) {
                            sourceStep.config.custom_buttons[buttonIndex].target_step = null;
                        }
                    } else if (sourceStep.connections) {
                        delete sourceStep.connections[connectionType];
                    }
                }
            }
        }
        
        try {
            this.instance.deleteConnection(connection);
        } catch (error) {
            console.error('❌ Erro ao remover conexão:', error);
        }
    }
    
    /**
     * Remove elemento de step
     */
    removeStepElement(stepId) {
        const element = this.steps.get(stepId);
        if (element) {
            // Remover conexões
            const connectionsToRemove = [];
            this.connections.forEach((conn) => {
                const data = conn.getData();
                if (data && (data.sourceStepId === stepId || data.targetStepId === stepId)) {
                    connectionsToRemove.push(conn);
                }
            });
            
            connectionsToRemove.forEach(conn => {
                this.removeConnection(conn);
            });
            
            // Remover do jsPlumb e DOM
            this.instance.remove(element);
            element.remove();
            this.steps.delete(stepId);
            this.stepTransforms.delete(stepId);
        }
    }
    
    /**
     * Remove um step
     */
    deleteStep(stepId) {
        if (!confirm('Tem certeza que deseja remover este step?')) {
            return;
        }
        
        this.removeStepElement(String(stepId));
        
        // Remover do Alpine
        if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
            const steps = this.alpine.config.flow_steps;
            const index = steps.findIndex(s => String(s.id) === String(stepId));
            if (index !== -1) {
                steps.splice(index, 1);
            }
            
            if (this.alpine.config.flow_start_step_id === String(stepId)) {
                this.alpine.config.flow_start_step_id = null;
            }
        }
        
        this.adjustCanvasSize();
    }
    
    /**
     * Define step como inicial
     */
    setStartStep(stepId) {
        if (this.alpine && this.alpine.config) {
            this.alpine.config.flow_start_step_id = String(stepId);
            this.renderAllSteps();
        }
    }
    
    /**
     * Abre modal de edição
     */
    editStep(stepId) {
        if (this.alpine && typeof this.alpine.openStepModal === 'function') {
            this.alpine.openStepModal(stepId);
        }
    }
    
    /**
     * Atualiza endpoints de um step
     */
    updateStepEndpoints(stepId) {
        const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === String(stepId));
        if (!step) return;
        
        const element = this.steps.get(String(stepId));
        if (!element) return;
        
        // Remover endpoints antigos
        this.instance.removeAllEndpoints(element);
        
        // Re-adicionar
        this.addEndpoints(element, String(stepId), step);
        
        // Reconectar
        setTimeout(() => {
            this.reconnectAll();
        }, 50);
    }
    
    /**
     * Ajusta tamanho do canvas automaticamente
     */
    adjustCanvasSize(padding = 400) {
        if (!this.canvas) return;
        
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.steps.forEach((element, stepId) => {
            const cached = this.stepTransforms.get(stepId);
            if (cached) {
                const x = cached.x;
                const y = cached.y;
                const w = element.offsetWidth || 300;
                const h = element.offsetHeight || 180;
                
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            }
        });
        
        if (minX === Infinity) {
            minX = 0;
            minY = 0;
            maxX = 1200;
            maxY = 800;
        }
        
        const parent = this.canvas.parentElement;
        if (!parent) return;
        
        const parentRect = parent.getBoundingClientRect();
        const contentWidth = maxX - minX + padding;
        const contentHeight = maxY - minY + padding;
        
        const width = Math.max(parentRect.width || 1200, contentWidth);
        const height = Math.max(parentRect.height || 600, contentHeight);
        
        // Aplicar dimensões
        this.canvas.style.setProperty('width', `${width}px`, 'important');
        this.canvas.style.setProperty('height', `${height}px`, 'important');
        
        if (this.contentContainer) {
            this.contentContainer.style.width = `${width}px`;
            this.contentContainer.style.height = `${height}px`;
        }
    }
    
    /**
     * Zoom in
     */
    zoomIn() {
        const targetZoom = Math.min(this.maxZoom, this.zoomLevel * 1.2);
        this.zoomToLevel(targetZoom);
    }
    
    /**
     * Zoom out
     */
    zoomOut() {
        const targetZoom = Math.max(this.minZoom, this.zoomLevel * 0.8);
        this.zoomToLevel(targetZoom);
    }
    
    /**
     * Zoom para nível específico
     */
    zoomToLevel(targetZoom) {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const worldX = (centerX - this.pan.x) / this.zoomLevel;
        const worldY = (centerY - this.pan.y) / this.zoomLevel;
        
        this.zoomLevel = Math.max(this.minZoom, Math.min(this.maxZoom, targetZoom));
        this.pan.x = centerX - worldX * this.zoomLevel;
        this.pan.y = centerY - worldY * this.zoomLevel;
        
        this.updateCanvasTransform();
    }
    
    /**
     * Reset zoom
     */
    zoomReset() {
        this.zoomLevel = 1;
        this.pan = { x: 0, y: 0 };
        this.updateCanvasTransform();
    }
    
    /**
     * Zoom para fit
     */
    zoomToFit() {
        if (!this.canvas || this.steps.size === 0) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const padding = 50;
        
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.steps.forEach((element) => {
            const cached = this.stepTransforms.get(element.dataset.stepId);
            if (cached) {
                const x = cached.x;
                const y = cached.y;
                const w = element.offsetWidth || 300;
                const h = element.offsetHeight || 180;
                
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            }
        });
        
        if (minX === Infinity) return;
        
        const contentWidth = maxX - minX + padding * 2;
        const contentHeight = maxY - minY + padding * 2;
        
        const scaleX = (rect.width - padding * 2) / contentWidth;
        const scaleY = (rect.height - padding * 2) / contentHeight;
        const newZoom = Math.min(scaleX, scaleY, 1);
        
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        this.zoomLevel = newZoom;
        this.pan.x = rect.width / 2 - centerX * newZoom;
        this.pan.y = rect.height / 2 - centerY * newZoom;
        
        this.updateCanvasTransform();
    }
    
    /**
     * Organiza steps verticalmente
     */
    organizeVertical() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        let currentY = 100;
        steps.forEach((step) => {
            const currentX = step.position?.x || 100;
            step.position = { x: currentX, y: currentY };
            currentY += 200;
            
            const element = this.steps.get(String(step.id));
            if (element) {
                element.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
                this.stepTransforms.set(String(step.id), { x: currentX, y: currentY });
            }
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.adjustCanvasSize();
        }, 50);
    }
    
    /**
     * Organiza steps horizontalmente
     */
    organizeHorizontal() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        let currentX = 100;
        steps.forEach((step) => {
            const currentY = step.position?.y || 100;
            step.position = { x: currentX, y: currentY };
            currentX += 320;
            
            const element = this.steps.get(String(step.id));
            if (element) {
                element.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
                this.stepTransforms.set(String(step.id), { x: currentX, y: currentY });
            }
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.adjustCanvasSize();
        }, 50);
    }
    
    /**
     * Organiza fluxo completo
     */
    organizeFlowComplete() {
        this.organizeVertical();
    }
    
    /**
     * Organiza por grupos
     */
    organizeByGroups() {
        this.organizeVertical();
    }
    
    /**
     * Utilitários
     */
    getStepTypeLabel(type) {
        const labels = {
            content: 'Conteúdo',
            message: 'Mensagem',
            audio: 'Áudio',
            video: 'Vídeo',
            buttons: 'Botões',
            payment: 'Pagamento',
            access: 'Acesso'
        };
        return labels[type] || type;
    }
    
    getStepPreview(step) {
        const config = step.config || {};
        const type = step.type || 'message';
        
        if (type === 'message' || type === 'content') {
            const text = config.message || config.text || '';
            if (!text) return '';
            
            // Clamp 3 linhas (~120 caracteres)
            const maxLength = 120;
            if (text.length <= maxLength) {
                return text;
            }
            
            const truncated = text.substring(0, maxLength);
            const lastSpace = truncated.lastIndexOf(' ');
            const lastNewline = truncated.lastIndexOf('\n');
            const breakPoint = Math.max(lastSpace, lastNewline);
            
            if (breakPoint > maxLength * 0.7) {
                return truncated.substring(0, breakPoint) + '...';
            }
            return truncated + '...';
        } else if (type === 'payment') {
            const price = config.price || '';
            const productName = config.product_name || '';
            if (price && productName) {
                return `${productName} - R$ ${price}`;
            }
            return price ? `R$ ${price}` : 'Pagamento';
        } else if (type === 'access') {
            return config.message || config.access_link || 'Acesso liberado';
        }
        
        return this.getStepTypeLabel(type);
    }
    
    getMediaPreviewHtml(stepConfig, mediaType) {
        const mediaUrl = stepConfig.media_url || '';
        if (!mediaUrl) return '';
        
        if (mediaType === 'photo' || mediaType === 'image') {
            return `
                <div class="flow-step-thumbnail-container" style="
                    margin-bottom: 12px;
                    border-radius: 8px;
                    overflow: hidden;
                    background: #13151C;
                    border: 1px solid #242836;
                    height: 120px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: relative;
                ">
                    <img src="${this.escapeHtml(mediaUrl)}" 
                         alt="Preview" 
                         style="width: 100%; height: 100%; object-fit: cover;"
                         onerror="this.style.display='none';"
                         loading="lazy" />
                </div>
            `;
        } else {
            return `
                <div class="flow-step-thumbnail-container" style="
                    margin-bottom: 12px;
                    border-radius: 8px;
                    overflow: hidden;
                    background: #13151C;
                    border: 1px solid #242836;
                    height: 120px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: relative;
                ">
                    <img src="${this.escapeHtml(mediaUrl)}" 
                         alt="Video thumbnail" 
                         style="width: 100%; height: 100%; object-fit: cover;"
                         onerror="this.style.display='none';"
                         loading="lazy" />
                    <div style="
                        position: absolute;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0, 0, 0, 0.4);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    ">
                        <i class="fas fa-play-circle" style="font-size: 48px; color: rgba(255, 255, 255, 0.9);"></i>
                    </div>
                </div>
            `;
        }
    }
    
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
    
    getConnectionLabel(type) {
        const labels = {
            next: 'Próximo',
            pending: 'Pendente',
            retry: 'Retry'
        };
        return labels[type] || type;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Limpa o canvas
     */
    clearCanvas() {
        const container = this.contentContainer || this.canvas;
        this.steps.forEach((element) => {
            this.instance.remove(element);
            element.remove();
        });
        this.steps.clear();
        this.connections.clear();
    }
    
    /**
     * Destruir instância
     */
    destroy() {
        if (this.dragFrameId) {
            cancelAnimationFrame(this.dragFrameId);
        }
        if (this.panFrameId) {
            cancelAnimationFrame(this.panFrameId);
        }
        if (this.zoomFrameId) {
            cancelAnimationFrame(this.zoomFrameId);
        }
        if (this.repaintTimeout) {
            clearTimeout(this.repaintTimeout);
        }
        
        this.clearCanvas();
        
        if (this.instance) {
            try {
                this.instance.destroy();
            } catch (e) {
                // Ignorar erros
            }
            this.instance = null;
        }
    }
}

// Exportar para uso global
window.FlowEditor = FlowEditor;
