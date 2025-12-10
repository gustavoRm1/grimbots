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
        
        // CRÍTICO: Setup canvas PRIMEIRO para criar contentContainer
        this.setupCanvas();
        
        // CRÍTICO: Setup jsPlumb DEPOIS, usando contentContainer como Container
        this.setupJsPlumb();
        
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
        
        // CRÍTICO: Configurar event delegation DEPOIS do contentContainer existir
        // Aguardar um pouco para garantir que o container está pronto
        setTimeout(() => {
            this.enableActionButtonsDelegation(); // Event delegation como fallback
        }, 100);
        
        // Renderizar steps após setup
        setTimeout(() => {
            this.renderAllSteps();
        }, 50);
    }
    
    /**
     * Event delegation para botões de ação (fallback)
     * CRÍTICO: Garante que cliques nos botões sejam capturados mesmo se attachActionButtons falhar
     */
    enableActionButtonsDelegation() {
        // CRÍTICO: Usar contentContainer onde os elementos realmente estão
        const container = this.contentContainer || this.canvas;
        if (!container) {
            console.warn('⚠️ enableActionButtonsDelegation: container não encontrado');
            return;
        }
        
        console.log('✅ Event delegation configurado no container:', container);
        
        // CRÍTICO: Interceptar ANTES do jsPlumb usando capture phase
        const handleButtonClick = (e) => {
            // Verificar se é um botão ou está dentro do footer
            const button = e.target.closest('.flow-step-btn-action[data-action]');
            const isInFooter = e.target.closest('.flow-step-footer');
            
            if (!button && !isInFooter) {
                // Verificar se é um ícone dentro de botão
                const icon = e.target.closest('i');
                if (icon) {
                    const parentButton = icon.closest('.flow-step-btn-action[data-action]');
                    if (parentButton) {
                        const action = parentButton.getAttribute('data-action');
                        const stepId = parentButton.getAttribute('data-step-id');
                        if (action && stepId) {
                            console.log('🔵 [Delegation CAPTURE] Ícone dentro de botão clicado:', { action, stepId, target: e.target });
                            e.stopImmediatePropagation(); // CRÍTICO: Primeiro, antes de tudo
                            e.stopPropagation();
                            e.preventDefault();
                            
                            // Desabilitar draggable temporariamente
                            const stepElement = parentButton.closest('.flow-step-block');
                            if (stepElement && this.instance) {
                                try {
                                    this.instance.setDraggable(stepElement, false);
                                    setTimeout(() => {
                                        if (this.instance && stepElement.parentNode) {
                                            this.instance.setDraggable(stepElement, true);
                                        }
                                    }, 200);
                                } catch (err) {
                                    console.warn('⚠️ Erro ao desabilitar draggable:', err);
                                }
                            }
                            
                            this.handleActionClick(action, stepId);
                            return;
                        }
                    }
                }
                return;
            }
            
            if (button) {
                const action = button.getAttribute('data-action');
                const stepId = button.getAttribute('data-step-id');
                if (!action || !stepId) {
                    return;
                }
                
                console.log('🔵 [Delegation CAPTURE] Botão clicado:', { action, stepId, target: e.target });
                e.stopImmediatePropagation(); // CRÍTICO: Primeiro, antes de tudo
                e.stopPropagation();
                e.preventDefault();
                
                // Desabilitar draggable temporariamente
                const stepElement = button.closest('.flow-step-block');
                if (stepElement && this.instance) {
                    try {
                        this.instance.setDraggable(stepElement, false);
                        setTimeout(() => {
                            if (this.instance && stepElement.parentNode) {
                                this.instance.setDraggable(stepElement, true);
                            }
                        }, 200);
                    } catch (err) {
                        console.warn('⚠️ Erro ao desabilitar draggable:', err);
                    }
                }
                
                this.handleActionClick(action, stepId);
            }
        };
        
        // CRÍTICO: Adicionar na fase de captura (true) para interceptar ANTES do jsPlumb
        container.addEventListener('mousedown', handleButtonClick, true);
        
        // CRÍTICO: Também adicionar listener de click como backup (capture phase)
        container.addEventListener('click', handleButtonClick, true);
    }
    
    /**
     * Handler centralizado para ações dos botões
     */
    handleActionClick(action, stepId) {
        console.log('🔵 handleActionClick chamado:', { action, stepId, hasThis: !!this, hasAlpine: !!this.alpine, hasWindowFlowEditor: !!window.flowEditor });
        switch (action) {
            case 'edit':
                console.log('🔵 [Handler] Chamando editStep para:', stepId);
                this.editStep(stepId);
                break;
            case 'remove':
                console.log('🔵 [Handler] Chamando deleteStep para:', stepId);
                this.deleteStep(stepId);
                break;
            case 'set-start':
                console.log('🔵 [Handler] Chamando setStartStep para:', stepId);
                this.setStartStep(stepId);
                break;
            default:
                console.warn('⚠️ Ação desconhecida:', action);
        }
    }
    
    /**
     * Configura jsPlumb com conexões brancas suaves
     */
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
                maxConnections: -1,
                // CRÍTICO: Habilitar conexões arrastáveis
                ConnectionsDetachable: true,
                ConnectionOverlays: [
                    ['Arrow', { width: 10, length: 12, location: 1 }]
                ]
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
     * PATCH V4.0 - ManyChat Perfect
     */
    setupCanvas() {
        if (!this.canvas) return;
        
        // Ensure we use the #flow-visual-canvas element
        // If flow-canvas-content already exists, reuse it
        let content = this.canvas.querySelector('.flow-canvas-content');
        if (!content) {
            content = document.createElement('div');
            content.className = 'flow-canvas-content';
            content.style.cssText = 'position:absolute; left:0; top:0; width:100%; height:100%; transform-origin:0 0; will-change:transform;';
            // Move any existing flow-step-block children into content
            Array.from(this.canvas.children).forEach(child => {
                if (child.classList && child.classList.contains('flow-step-block')) {
                    content.appendChild(child);
                }
            });
            this.canvas.appendChild(content);
        }
        this.contentContainer = content;
        
        // Ensure canvas base styles (grid)
        this.canvas.style.position = 'relative';
        this.canvas.style.overflow = 'hidden';
        this.canvas.style.background = '#0D0F15';
        this.canvas.style.backgroundImage = 'radial-gradient(circle, rgba(255,255,255,0.12) 1.5px, transparent 1.5px)';
        this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
        
        // Observe changes to contentContainer.style transform (zoom/pan)
        if (this.transformObserver) {
            this.transformObserver.disconnect();
            this.transformObserver = null;
        }
        if (window.MutationObserver) {
            this.transformObserver = new MutationObserver(() => {
                if (this.instance) {
                    // Revalidate nodes and cards
                    this.steps.forEach(el => {
                        try { this.instance.revalidate(el); } catch(e) {}
                    });
                    try { this.instance.repaintEverything(); } catch(e) {}
                }
            });
            this.transformObserver.observe(this.contentContainer, { attributes: true, attributeFilter: ['style'] });
        }
        
        // Apply initial transform
        this.updateCanvasTransform();
    }
    
    /**
     * Atualiza transform do contentContainer (zoom + pan)
     */
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
                // CRÍTICO: Revalidar todos os elementos E seus nodes (PATCH V4.0)
                this.steps.forEach((el, id) => {
                    this.instance.revalidate(el);
                    // Endpoints agora são gerenciados 100% pelo jsPlumb, não há mais nodes HTML
                    const inputs = [];
                    inputs.forEach(n => this.instance.revalidate(n));
                });
                this.instance.repaintEverything();
            }
        }, 16); // ~60fps
    }
    
    /**
     * Zoom suave com foco no mouse (padrão ManyChat)
     * CRÍTICO: Zoom sempre focado no ponto do cursor, não no centro
     */
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
    
    /**
     * Pan suave com botão direito (estilo Figma)
     */
    enablePan() {
        if (!this.canvas) return;
        
        const startPan = (e) => {
            // CRÍTICO: NUNCA processar pan se for clique em botão de ação
            const isOverActionButton = e.target.closest('.flow-step-btn-action[data-action]');
            if (isOverActionButton) {
                // Deixar o evento passar para os handlers dos botões
                return;
            }
            
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
        
        // CRÍTICO: Usar capture: false para não interceptar antes dos botões
        this.canvas.addEventListener('mousedown', startPan, false);
        
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
     * PATCH V4.0 - ManyChat Perfect
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
        
        // Remove existing element to avoid duplicates
        if (this.steps.has(stepId)) {
            this.removeStepElement(stepId);
        }
        
        // If element exists, update and return
        if (this.steps.has(stepId)) {
            this.updateStep(step);
            return;
        }
        
        // Create element
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block flow-card';
        stepElement.dataset.stepId = stepId;
        // Important: position absolute for canvas placement, relative children
        stepElement.style.position = 'absolute';
        stepElement.style.left = '0';
        stepElement.style.top = '0';
        stepElement.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
        stepElement.style.willChange = 'transform';
        
        // INNER wrapper (ensures nodes positioned relative to inner)
        const inner = document.createElement('div');
        inner.className = 'flow-step-block-inner';
        inner.style.position = 'relative';
        inner.style.width = '100%';
        inner.style.height = '100%';
        
        // Build inner HTML (media, text, buttons) — reuse existing helpers
        const mediaHtml = stepConfig.media_url ? this.getMediaPreviewHtml(stepConfig, stepConfig.media_type || 'video') : '';
        const previewText = this.getStepPreview(step) ? `<div class="flow-step-preview">${this.escapeHtml(this.getStepPreview(step))}</div>` : '';
        const buttonsHtml = hasButtons ? this.getButtonPreviewHtml(customButtons) : '';
        
        inner.innerHTML = `
            <div class="flow-step-header">
                <div class="flow-step-header-content">
                    <div class="flow-step-icon-center"><i class="fas ${this.stepIcons[stepType] || 'fa-circle'}"></i></div>
                    <div class="flow-step-title-center">${this.getStepTypeLabel(stepType)}</div>
                    ${isStartStep?'<div class="flow-step-start-badge">⭐</div>':''}
                </div>
            </div>
            <div class="flow-step-body">
                ${mediaHtml}
                ${previewText}
                ${buttonsHtml}
            </div>
            <div class="flow-step-footer" data-jtk-not-draggable="true" style="pointer-events: auto; z-index: 10000;">
                <button class="flow-step-btn-action" data-action="edit" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Editar" style="pointer-events: auto; cursor: pointer; z-index: 10001; position: relative;" onclick="console.log('🔵 [ONCLICK INLINE] editStep:', '${stepId}'); event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); if(window.flowEditor && window.flowEditor.handleActionClick) { window.flowEditor.handleActionClick('edit', '${stepId}'); } else if(window.flowEditorActions && window.flowEditorActions.editStep) { window.flowEditorActions.editStep('${stepId}'); } return false;"><i class="fas fa-edit"></i></button>
                <button class="flow-step-btn-action" data-action="remove" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Remover" style="pointer-events: auto; cursor: pointer; z-index: 10001; position: relative;" onclick="console.log('🔵 [ONCLICK INLINE] deleteStep:', '${stepId}'); event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); if(window.flowEditor && window.flowEditor.handleActionClick) { window.flowEditor.handleActionClick('remove', '${stepId}'); } else if(window.flowEditorActions && window.flowEditorActions.deleteStep) { window.flowEditorActions.deleteStep('${stepId}'); } return false;"><i class="fas fa-trash"></i></button>
                ${!isStartStep?`<button class="flow-step-btn-action" data-action="set-start" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Definir como inicial" style="pointer-events: auto; cursor: pointer; z-index: 10001; position: relative;" onclick="console.log('🔵 [ONCLICK INLINE] setStartStep:', '${stepId}'); event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); if(window.flowEditor && window.flowEditor.handleActionClick) { window.flowEditor.handleActionClick('set-start', '${stepId}'); } else if(window.flowEditorActions && window.flowEditorActions.setStartStep) { window.flowEditorActions.setStartStep('${stepId}'); } return false;">⭐</button>` : ''}
            </div>
        `;
        
        // Append inner to step and to contentContainer
        stepElement.appendChild(inner);
        const container = this.contentContainer || this.canvas;
        container.appendChild(stepElement);
        
        // CRÍTICO: Desabilitar draggable explicitamente no footer e botões ANTES de tornar o step draggable
        const footer = inner.querySelector('.flow-step-footer');
        if (footer) {
            footer.setAttribute('data-jtk-not-draggable', 'true');
            footer.style.pointerEvents = 'auto';
            const footerButtons = footer.querySelectorAll('.flow-step-btn-action');
            footerButtons.forEach(btn => {
                btn.setAttribute('data-jtk-not-draggable', 'true');
                btn.style.pointerEvents = 'auto';
                btn.style.cursor = 'pointer';
                btn.style.position = 'relative';
                btn.style.zIndex = '9999';
            });
        }
        
        // Make draggable (jsPlumb)
        this.instance.draggable(stepElement, {
            containment: container,
            drag: (params) => this.onStepDrag(params),
            stop: (params) => this.onStepDragStop(params),
            cursor: 'move',
            start: (params) => {
                // Ensure endpoints don't steal start events
                // no-op
            }
        });
        
        // Save
        this.steps.set(stepId, stepElement);
        
        // Add endpoints after DOM layout calculated
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.addEndpoints(stepElement, stepId, step);
                try { this.instance.revalidate(stepElement); this.instance.repaintEverything(); } catch(e) {}
            });
        });
    }
    
    /**
     * Anexa event listeners aos botões de ação do step
     */
    attachActionButtons(stepElement, stepId) {
        if (!stepElement) {
            console.warn('⚠️ attachActionButtons: stepElement não existe');
            return;
        }
        
        // Buscar dentro do stepElement (incluindo innerWrapper se existir)
        const innerWrapper = stepElement.querySelector('.flow-step-block-inner') || stepElement;
        const actionButtons = innerWrapper.querySelectorAll('.flow-step-btn-action[data-action]');
        
        console.log(`🔵 attachActionButtons: encontrados ${actionButtons.length} botões para step ${stepId}`, {
            stepElement: stepElement,
            innerWrapper: innerWrapper,
            buttons: actionButtons
        });
        
        if (actionButtons.length === 0) {
            console.warn('⚠️ attachActionButtons: nenhum botão encontrado no step', stepId, {
                stepElementHTML: stepElement.innerHTML.substring(0, 200)
            });
            return;
        }
        
        actionButtons.forEach((button, index) => {
            const action = button.getAttribute('data-action');
            const buttonStepId = button.getAttribute('data-step-id') || stepId;
            
            console.log(`🔵 Configurando listener para botão ${index}: action=${action}, stepId=${buttonStepId}`);
            
            // CRÍTICO: NÃO clonar o botão - isso remove o onclick inline!
            // Ao invés disso, apenas adicionar listeners adicionais
            // Garantir z-index alto para botões não serem bloqueados
            button.style.position = 'relative';
            button.style.zIndex = '9999';
            button.style.pointerEvents = 'auto';
            
            // CRÍTICO: Handler que funciona mesmo se outros interceptarem
            const handleButtonAction = (e) => {
                console.log(`🔵 [Direct Listener] Botão ${action} clicado: stepId=${buttonStepId}`, e);
                // CRÍTICO: Parar propagação IMEDIATAMENTE
                e.stopImmediatePropagation(); // Prevenir outros listeners (deve ser PRIMEIRO)
                e.stopPropagation(); // Prevenir propagação para o canvas
                e.preventDefault();
                
                // Forçar chamada mesmo se houver algum problema
                this.handleActionClick(action, buttonStepId);
            };
            
            // CRÍTICO: Adicionar listeners com capture:true para executar ANTES de tudo
            button.addEventListener('mousedown', handleButtonAction, true);
            button.addEventListener('click', handleButtonAction, true);
            
            // CRÍTICO: Backup usando onclick - será preservado se não clonarmos
            // O onclick inline já está no HTML, então não precisamos sobrescrever
        });
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
        
        // Atualizar posição - usar left/top ao invés de transform
        const position = step.position || { x: 100, y: 100 };
        element.style.left = `${position.x}px`;
        element.style.top = `${position.y}px`;
        this.stepTransforms.set(stepId, { x: position.x, y: position.y });
        
        // Remover endpoints antigos (todos os endpoints do card)
        // Endpoints agora são criados diretamente no elemento, não há mais nodes HTML
        this.instance.removeAllEndpoints(element);
        
        // CRÍTICO: Garantir que o card tenha position absolute e sem transform
        element.style.position = 'absolute';
        element.style.transform = 'none';
        
        // CRÍTICO: Buscar ou criar wrapper interno para referência correta dos nodes
        let innerWrapper = element.querySelector('.flow-step-block-inner');
        if (!innerWrapper) {
            // Se não existe, criar o wrapper e mover conteúdo existente
            innerWrapper = document.createElement('div');
            innerWrapper.className = 'flow-step-block-inner';
            const existingContent = element.innerHTML;
            innerWrapper.innerHTML = existingContent;
            element.innerHTML = '';
            element.appendChild(innerWrapper);
        }
        
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
        const headerEl = innerWrapper.querySelector('.flow-step-header-content');
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
        const bodyEl = innerWrapper.querySelector('.flow-step-body');
        if (bodyEl) {
            bodyEl.innerHTML = `
                ${mediaHTML}
                ${previewText ? `<div class="flow-step-preview">${this.escapeHtml(previewText)}</div>` : ''}
                ${buttonsHTML}
            `;
        }
        
        // Atualizar footer com botões de ação
        const footerEl = innerWrapper.querySelector('.flow-step-footer');
        if (footerEl) {
            footerEl.setAttribute('data-jtk-not-draggable', 'true');
            footerEl.innerHTML = `
                <button class="flow-step-btn-action" data-action="edit" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Editar" onclick="event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); (window.flowEditorActions && window.flowEditorActions.editStep) ? window.flowEditorActions.editStep('${stepId}') : (window.flowEditor && window.flowEditor.editStep('${stepId}')); return false;"><i class="fas fa-edit"></i></button>
                <button class="flow-step-btn-action" data-action="remove" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Remover" onclick="event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); (window.flowEditorActions && window.flowEditorActions.deleteStep) ? window.flowEditorActions.deleteStep('${stepId}') : (window.flowEditor && window.flowEditor.deleteStep('${stepId}')); return false;"><i class="fas fa-trash"></i></button>
                ${!isStartStep ? `<button class="flow-step-btn-action" data-action="set-start" data-step-id="${stepId}" data-jtk-not-draggable="true" title="Definir como inicial" onclick="event.stopImmediatePropagation(); event.stopPropagation(); event.preventDefault(); (window.flowEditorActions && window.flowEditorActions.setStartStep) ? window.flowEditorActions.setStartStep('${stepId}') : (window.flowEditor && window.flowEditor.setStartStep('${stepId}')); return false;">⭐</button>` : ''}
            `;
        }
        
        // CRÍTICO: Endpoints agora são gerenciados 100% pelo jsPlumb
        // Não há mais nodes HTML para criar/manter
        
        // CRÍTICO: Re-adicionar endpoints APÓS o DOM estar completamente renderizado
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Reanexar listeners dos botões de ação
                this.attachActionButtons(element, stepId);
                
                this.addEndpoints(element, stepId, step);
                // Revalidar e repintar após adicionar endpoints
                if (this.instance) {
                    this.instance.revalidate(element);
                    this.instance.repaintEverything();
                }
            });
        });
        
        // Atualizar classe inicial
        if (isStartStep) {
            element.classList.add('flow-step-initial');
        } else {
            element.classList.remove('flow-step-initial');
        }
    }
    
    /**
     * Adiciona endpoints ao step
     * PATCH V4.0 - ManyChat Perfect
     */
    addEndpoints(element, stepId, step) {
        if (!this.instance) return;
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Ensure element position relative for internal placement but endpoints will be outside by anchor offsets
        element.style.position = 'absolute';
        
        // Helper to check existing endpoints by uuid
        const hasEndpoint = (uuid) => {
            try {
                const eps = this.instance.getEndpoints(element);
                if (!eps) return false;
                for (let e of eps) {
                    if (e && e.getUuid && e.getUuid() === uuid) return true;
                }
            } catch(e) {}
            return false;
        };
        
        // 1) INPUT endpoint (left outside)
        const inputUuid = `endpoint-left-${stepId}`;
        // Create or revalidate
        if (!hasEndpoint(inputUuid)) {
            this.instance.addEndpoint(element, {
                uuid: inputUuid,
                anchor: [0, 0.5, -1, 0, -8, 0], // left outside
                isSource: false,
                isTarget: true,
                maxConnections: -1,
                endpoint: ['Dot', { radius: 7 }],
                paintStyle: { fill:'#FFFFFF', outlineStroke:'#0D0F15', outlineWidth:2 },
                hoverPaintStyle: { fill:'#FFB800' },
                data: { stepId, endpointType: 'input' }
            });
        } else {
            try { this.instance.revalidate(element); } catch(e){}
        }
        
        // 2) OUTPUT endpoints
        if (hasButtons) {
            // Remove global output if exists
            const globalUuid = `endpoint-right-${stepId}`;
            try {
                const ep = this.instance.getEndpoint(globalUuid);
                if (ep) { this.instance.deleteEndpoint(ep); }
            } catch(e){}
            
            // create one endpoint per button
            customButtons.forEach((btn, index) => {
                const btnSelector = element.querySelector(`[data-endpoint-button="${index}"]`);
                // attach endpoint to the card element but anchored to the right-middle with an offset computed per button vertical position
                const uuid = `endpoint-button-${stepId}-${index}`;
                if (this.instance.getEndpoint(uuid)) return;
                
                // compute relative Y of the button inside element for an accurate anchor (Middle + offset)
                let anchorY = 0.5;
                if (btnSelector) {
                    const btnRect = btnSelector.getBoundingClientRect();
                    const cardRect = element.getBoundingClientRect();
                    if (cardRect.height > 0) {
                        const centerY = (btnRect.top + btnRect.height/2) - cardRect.top;
                        anchorY = Math.max(0, Math.min(1, centerY / cardRect.height));
                    }
                }
                
                // anchor array: [x, y, dx, dy, offsetX, offsetY] where x=1 means right side
                const anchor = [1, anchorY, 1, 0, 8, 0];
                
                this.instance.addEndpoint(element, {
                    uuid,
                    anchor,
                    isSource: true,
                    isTarget: false,
                    maxConnections: 1,
                    endpoint: ['Dot', { radius: 6 }],
                    paintStyle: { fill:'#FFFFFF', outlineStroke:'#0D0F15', outlineWidth:2 },
                    hoverPaintStyle: { fill:'#FFB800' },
                    data: { stepId, buttonIndex: index, endpointType: 'button' }
                });
                
                // Prevent pointer events from bubbling to card when interacting with endpoint DOM
                // Use event capture on jsPlumb's overlay (if present)
                try {
                    const eps = this.instance.getEndpoints(element) || [];
                    const ep = eps.find(e => e.getUuid && e.getUuid() === uuid);
                    if (ep && ep.canvas) {
                        ep.canvas.addEventListener('mousedown', (ev) => ev.stopPropagation(), { capture: true });
                        ep.canvas.addEventListener('pointerdown', (ev) => ev.stopPropagation(), { capture: true });
                    }
                } catch(e){}
            });
        } else {
            // Without buttons: create a single global output on the right-middle
            const outUuid = `endpoint-right-${stepId}`;
            if (!hasEndpoint(outUuid)) {
                this.instance.addEndpoint(element, {
                    uuid: outUuid,
                    anchor: [1, 0.5, 1, 0, 8, 0], // right outside
                    isSource: true,
                    isTarget: false,
                    maxConnections: -1,
                    endpoint: ['Dot', { radius: 7 }],
                    paintStyle: { fill:'#FFFFFF', outlineStroke:'#0D0F15', outlineWidth:2 },
                    hoverPaintStyle: { fill:'#FFB800' },
                    data: { stepId, endpointType: 'global' }
                });
                try {
                    const ep = this.instance.getEndpoint(outUuid);
                    if (ep && ep.canvas) {
                        ep.canvas.addEventListener('mousedown', (ev) => ev.stopPropagation(), { capture: true });
                        ep.canvas.addEventListener('pointerdown', (ev) => ev.stopPropagation(), { capture: true });
                    }
                } catch(e){}
            }
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
            
            // CRÍTICO: Revalidar e repintar durante drag
            // Nota: revalidate já está sendo chamado no callback drag do jsPlumb
            // Este é um fallback adicional
            this.dragFrameId = requestAnimationFrame(() => {
                if (this.instance) {
                    // Revalidar o elemento arrastado
                    // Endpoints agora são gerenciados 100% pelo jsPlumb, não há mais nodes HTML
                    this.instance.revalidate(element);
                    // Repintar todas as conexões
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
            
            // Extrair posição do transform translate3d
            const transform = element.style.transform || '';
            const match = transform.match(/translate3d\(([^,]+)px,\s*([^,]+)px/);
            let x = 0, y = 0;
            if (match) {
                x = parseFloat(match[1]) || 0;
                y = parseFloat(match[2]) || 0;
            } else {
                // Fallback para left/top se transform não existir
                x = parseFloat(element.style.left) || 0;
                y = parseFloat(element.style.top) || 0;
            }
            
            // Snap to grid opcional
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
            
            // Atualizar posição usando translate3d
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
    /**
     * Reconecta todas as conexões
     * PATCH V4.0 - ManyChat Perfect
     */
    reconnectAll() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        if (!this.instance) {
            console.warn('⚠️ jsPlumb instance não disponível em reconnectAll()');
            return;
        }
        
        // remove existing connections but keep endpoints
        try {
            if (this.instance && typeof this.instance.deleteEveryConnection === 'function') {
                this.instance.deleteEveryConnection();
            }
        } catch (e) { 
            console.warn('⚠️ Erro ao deletar conexões:', e); 
        }
        this.connections.clear();
        
        const steps = this.alpine.config.flow_steps;
        if (!Array.isArray(steps)) return;
        
        // CRÍTICO: Aguardar um frame para garantir que endpoints foram criados
        requestAnimationFrame(() => {
            steps.forEach(step => {
                if (!step || !step.id) return;
                const stepId = String(step.id);
                const stepConfig = step.config || {};
                const customButtons = stepConfig.custom_buttons || [];
                const hasButtons = customButtons.length > 0;
                const connections = step.connections || {};
                
                // Buttons targets
                if (hasButtons) {
                    customButtons.forEach((btn, idx) => {
                        if (btn.target_step) {
                            const targetId = String(btn.target_step);
                            // endpoint-button-{stepId}-{idx} -> endpoint-left-{targetId}
                            const srcUuid = `endpoint-button-${stepId}-${idx}`;
                            const tgtUuid = `endpoint-left-${targetId}`;
                            try {
                                const srcEp = this.instance.getEndpoint(srcUuid);
                                const tgtEp = this.instance.getEndpoint(tgtUuid);
                                if (srcEp && tgtEp) {
                                    const conn = this.instance.connect({ 
                                        source: srcEp,
                                        target: tgtEp
                                    });
                                    if (conn) {
                                        const connId = `button-${stepId}-${idx}-${targetId}`;
                                        this.connections.set(connId, conn);
                                    }
                                } else {
                                    console.warn(`⚠️ Endpoints não encontrados: ${srcUuid} ou ${tgtUuid}`);
                                }
                            } catch (e) { 
                                console.warn(`⚠️ Erro ao conectar botão ${idx} do step ${stepId}:`, e); 
                            }
                        }
                    });
                } else {
                    // standard next/pending/retry connections using global output
                    ['next','pending','retry'].forEach(type => {
                        if (connections[type]) {
                            const targetId = String(connections[type]);
                            const srcUuid = `endpoint-right-${stepId}`;
                            const tgtUuid = `endpoint-left-${targetId}`;
                            try {
                                const srcEp = this.instance.getEndpoint(srcUuid);
                                const tgtEp = this.instance.getEndpoint(tgtUuid);
                                if (srcEp && tgtEp) {
                                    const conn = this.instance.connect({ 
                                        source: srcEp,
                                        target: tgtEp
                                    });
                                    if (conn) {
                                        const connId = `${stepId}-${targetId}-${type}`;
                                        this.connections.set(connId, conn);
                                    }
                                } else {
                                    console.warn(`⚠️ Endpoints não encontrados: ${srcUuid} ou ${tgtUuid}`);
                                }
                            } catch (e) {
                                console.warn(`⚠️ Erro ao conectar ${type} do step ${stepId}:`, e);
                            }
                        }
                    });
                }
            });
            
            // Final repaint
            this.instance.repaintEverything();
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
     * PATCH V4.0 - ManyChat Perfect
     */
    onConnectionCreated(info) {
        if (!info || !info.sourceEndpoint || !info.targetEndpoint) return;
        const sUuid = info.sourceEndpoint.getUuid ? info.sourceEndpoint.getUuid() : null;
        const tUuid = info.targetEndpoint.getUuid ? info.targetEndpoint.getUuid() : null;
        if (!sUuid || !tUuid) return;
        
        let sourceStep = null, buttonIndex = null, connType = 'next';
        const matchBtn = sUuid.match(/^endpoint-button-([^_]+)-(\d+)$/) || sUuid.match(/^endpoint-button-([^/]+)-(\d+)$/);
        if (matchBtn) {
            sourceStep = matchBtn[1];
            buttonIndex = parseInt(matchBtn[2], 10);
            connType = 'button';
        } else if (sUuid.startsWith('endpoint-right-')) {
            sourceStep = sUuid.replace('endpoint-right-','');
            connType = 'next';
        } else {
            // may be some other format; fallback to dataset
            const data = info.source.getParameters && info.source.getParameters() || {};
            sourceStep = data.stepId || null;
        }
        
        const matchTarget = tUuid.match(/^endpoint-left-([^_]+)$/) || tUuid.match(/^endpoint-left-([^/]+)$/);
        const targetStep = matchTarget ? matchTarget[1] : null;
        
        if (sourceStep && targetStep) {
            // store connection in this.connections with stable id
            const connId = connType === 'button' ? `button-${sourceStep}-${buttonIndex}-${targetStep}` : `${sourceStep}-${targetStep}-${connType}`;
            this.connections.set(connId, info.connection);
            
            // update alpine
            try {
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === String(sourceStep));
                if (connType === 'button' && step?.config?.custom_buttons?.[buttonIndex]) {
                    step.config.custom_buttons[buttonIndex].target_step = targetStep;
                } else if (step) {
                    if (!step.connections) step.connections = {};
                    step.connections[connType] = targetStep;
                }
            } catch(e){ console.warn('update alpine failed', e); }
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
        console.log('🔵 editStep chamado com stepId:', stepId, {
            hasThisAlpine: !!this.alpine,
            hasWindowAlpineFlowEditor: !!window.alpineFlowEditor,
            hasFlowEditor: !!window.flowEditor
        });
        
        // CRÍTICO: Abrir modal instantaneamente SEM setTimeout para resposta imediata
        // Estratégia 1: Usar this.alpine (passado no construtor)
        if (this.alpine && typeof this.alpine.openStepModal === 'function') {
            console.log('✅ Usando this.alpine.openStepModal');
            this.alpine.openStepModal(stepId);
            return;
        }
        
        // Estratégia 2: Usar window.alpineFlowEditor (exposto globalmente)
        if (window.alpineFlowEditor && typeof window.alpineFlowEditor.openStepModal === 'function') {
            console.log('✅ Usando window.alpineFlowEditor.openStepModal');
            window.alpineFlowEditor.openStepModal(stepId);
            return;
        }
        
        // Estratégia 3: Buscar contexto Alpine diretamente do DOM usando Alpine.$data()
        try {
            if (typeof Alpine !== 'undefined' && Alpine.$data) {
                const alpineElement = document.querySelector('[x-data*="botConfigApp"]');
                if (alpineElement) {
                    const alpineApp = Alpine.$data(alpineElement);
                    if (alpineApp && typeof alpineApp.openStepModal === 'function') {
                        console.log('✅ Usando Alpine.$data() para buscar botConfigApp');
                        alpineApp.openStepModal(stepId);
                        return;
                    }
                }
            }
        } catch (e) {
            console.warn('⚠️ Erro ao buscar contexto Alpine via DOM:', e);
        }
        
        // Estratégia 4: Fallback final - tentar abrir modal diretamente via DOM
        console.error('❌ Não foi possível encontrar contexto Alpine. Tentando fallback direto:', {
            hasThisAlpine: !!this.alpine,
            hasWindowAlpineFlowEditor: !!window.alpineFlowEditor,
            stepId: stepId
        });
        
        // Última tentativa: buscar qualquer elemento com x-data="botConfigApp" e tentar acessar
        try {
            const allAlpineElements = document.querySelectorAll('[x-data]');
            for (const el of allAlpineElements) {
                const xData = el.getAttribute('x-data');
                if (xData && xData.includes('botConfigApp')) {
                    if (typeof Alpine !== 'undefined' && Alpine.$data) {
                        const app = Alpine.$data(el);
                        if (app && typeof app.openStepModal === 'function') {
                            console.log('✅ Fallback: encontrado via querySelectorAll');
                            app.openStepModal(stepId);
                            return;
                        }
                    }
                }
            }
        } catch (e) {
            console.error('❌ Erro no fallback final:', e);
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
        
        // CRÍTICO: Ajustar tamanho do contentContainer dinamicamente (PATCH CIRÚRGICO)
        if (this.contentContainer) {
            // Usar tamanho calculado ou mínimo de 5000px para fluxos grandes
            const containerWidth = Math.max(width, 5000);
            const containerHeight = Math.max(height, 5000);
            this.contentContainer.style.width = `${containerWidth}px`;
            this.contentContainer.style.height = `${containerHeight}px`;
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
        let html = '<div class="flow-step-buttons-container" style="padding:0 12px 12px 12px; display:flex; flex-direction:column; gap:8px;">';
        customButtons.forEach((btn, index) => {
            const text = this.escapeHtml(btn.text || `Botão ${index+1}`);
            html += `
              <div class="flow-step-button-item" data-button-index="${index}" data-button-id="${btn.id || 'btn-'+index}" style="position:relative; min-height:44px; display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-radius:6px; background:#E02727;">
                <span class="flow-step-button-text">${text}</span>
                <div class="flow-step-button-endpoint-container" data-endpoint-button="${index}" style="width:20px; height:20px; position:relative;"></div>
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
        
        // Desconectar observer
        if (this.transformObserver) {
            this.transformObserver.disconnect();
            this.transformObserver = null;
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

// CRÍTICO: Expor métodos diretamente no window para uso em onclick inline
// Criar objeto global antes de qualquer coisa
if (!window.flowEditorActions) {
    window.flowEditorActions = {};
}

// Atualizar métodos quando necessário
window.flowEditorActions.editStep = function(stepId) {
    console.log('🔵 [Global Action] editStep chamado:', stepId, {
        hasFlowEditor: !!window.flowEditor,
        hasAlpineFlowEditor: !!window.alpineFlowEditor
    });
    
    // Estratégia 1: Usar window.flowEditor
    if (window.flowEditor && typeof window.flowEditor.editStep === 'function') {
        console.log('✅ Usando window.flowEditor.editStep');
        window.flowEditor.editStep(stepId);
        return;
    }
    
    // Estratégia 2: Usar window.alpineFlowEditor diretamente
    if (window.alpineFlowEditor && typeof window.alpineFlowEditor.openStepModal === 'function') {
        console.log('✅ Usando window.alpineFlowEditor.openStepModal diretamente');
        window.alpineFlowEditor.openStepModal(stepId);
        return;
    }
    
    // Estratégia 3: Buscar contexto Alpine diretamente do DOM usando Alpine.$data()
    try {
        if (typeof Alpine !== 'undefined' && Alpine.$data) {
            const alpineElement = document.querySelector('[x-data*="botConfigApp"]');
            if (alpineElement) {
                const alpineApp = Alpine.$data(alpineElement);
                if (alpineApp && typeof alpineApp.openStepModal === 'function') {
                    console.log('✅ [Global Action] Usando Alpine.$data() para buscar botConfigApp');
                    alpineApp.openStepModal(stepId);
                    return;
                }
            }
        }
    } catch (e) {
        console.warn('⚠️ [Global Action] Erro ao buscar contexto Alpine via DOM:', e);
    }
    
    // Estratégia 4: Fallback final - tentar abrir modal diretamente via DOM
    try {
        const allAlpineElements = document.querySelectorAll('[x-data]');
        for (const el of allAlpineElements) {
            const xData = el.getAttribute('x-data');
            if (xData && xData.includes('botConfigApp')) {
                if (typeof Alpine !== 'undefined' && Alpine.$data) {
                    const app = Alpine.$data(el);
                    if (app && typeof app.openStepModal === 'function') {
                        console.log('✅ [Global Action] Fallback: encontrado via querySelectorAll');
                        app.openStepModal(stepId);
                        return;
                    }
                }
            }
        }
    } catch (e) {
        console.error('❌ [Global Action] Erro no fallback final:', e);
    }
    
    console.error('❌ [Global Action] Nem flowEditor nem alpineFlowEditor disponíveis');
};

window.flowEditorActions.deleteStep = function(stepId) {
    console.log('🔵 [Global Action] deleteStep chamado:', stepId);
    if (window.flowEditor && typeof window.flowEditor.deleteStep === 'function') {
        window.flowEditor.deleteStep(stepId);
    }
};

window.flowEditorActions.setStartStep = function(stepId) {
    console.log('🔵 [Global Action] setStartStep chamado:', stepId);
    if (window.flowEditor && typeof window.flowEditor.setStartStep === 'function') {
        window.flowEditor.setStartStep(stepId);
    }
};

console.log('✅ window.flowEditorActions inicializado');

