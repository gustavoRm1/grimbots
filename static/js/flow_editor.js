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
        this.enableActionButtonsDelegation(); // Event delegation como fallback
        
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
        if (!this.canvas) return;
        
        // Usar event delegation no canvas para capturar cliques nos botões
        this.canvas.addEventListener('click', (e) => {
            // Verificar se o clique foi em um botão de ação
            const button = e.target.closest('.flow-step-btn-action[data-action]');
            if (!button) return;
            
            const action = button.getAttribute('data-action');
            const stepId = button.getAttribute('data-step-id');
            
            if (!action || !stepId) return;
            
            console.log('🔵 [Delegation] Botão clicado:', { action, stepId, target: e.target });
            
            e.stopPropagation();
            e.preventDefault();
            e.stopImmediatePropagation();
            
            switch (action) {
                case 'edit':
                    console.log('🔵 [Delegation] Chamando editStep para:', stepId);
                    this.editStep(stepId);
                    break;
                case 'remove':
                    this.deleteStep(stepId);
                    break;
                case 'set-start':
                    this.setStartStep(stepId);
                    break;
            }
        }, true); // Capture phase para garantir que seja executado primeiro
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
        
        // Canvas principal - SEM transform, apenas background
        this.canvas.style.position = 'relative';
        this.canvas.style.overflow = 'hidden';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.background = '#0D0F15';
        this.canvas.style.backgroundImage = `radial-gradient(circle, rgba(255,255,255,0.12) 1.5px, transparent 1.5px)`;
        this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
        this.canvas.style.backgroundRepeat = 'repeat';
        this.canvas.style.backgroundPosition = '0 0';
        this.canvas.style.transform = 'none';
        
        // Container interno para transform (zoom/pan)
        let existingContainer = this.canvas.querySelector('.flow-canvas-content');
        if (existingContainer) {
            this.contentContainer = existingContainer;
        } else {
            this.contentContainer = document.createElement('div');
            this.contentContainer.className = 'flow-canvas-content';
            Object.assign(this.contentContainer.style, {
                position: 'absolute',
                top: '0',
                left: '0',
                width: '2000px',     // espaço virtual grande por padrão
                height: '2000px',
                transformOrigin: '0 0',
                willChange: 'transform',
                pointerEvents: 'auto'
            });
            
            // Mover apenas elementos de step existentes para o container
            Array.from(this.canvas.children).forEach(child => {
                if (child.classList && child.classList.contains('flow-step-block')) {
                    this.contentContainer.appendChild(child);
                }
            });
            
            this.canvas.appendChild(this.contentContainer);
        }
        
        // Observer para revalidate quando contentContainer transform mudar
        if (window.MutationObserver && this.contentContainer) {
            if (this.transformObserver) this.transformObserver.disconnect();
            const observer = new MutationObserver((mutations) => {
                let changed = false;
                mutations.forEach(m => {
                    if (m.type === 'attributes' && m.attributeName === 'style') changed = true;
                });
                if (changed && this.instance) {
                    // Revalidate cards and their nodes
                    this.steps.forEach((el, id) => {
                        this.instance.revalidate(el);
                        const inputs = el.querySelectorAll('.flow-step-node-input, .flow-step-node-output, .flow-step-button-endpoint-container');
                        inputs.forEach(n => this.instance.revalidate(n));
                    });
                    this.instance.repaintEverything();
                }
            });
            observer.observe(this.contentContainer, { attributes: true, attributeFilter: ['style'] });
            this.transformObserver = observer;
        }
        
        // Ensure canvas transform is none
        this.canvas.style.setProperty('transform', 'none', 'important');
        
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
                    const inputs = el.querySelectorAll('.flow-step-node-input, .flow-step-node-output, .flow-step-button-endpoint-container');
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
        
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block';
        // CRÍTICO: position absolute para posicionamento no canvas
        // Usar APENAS left/top, NUNCA transform (jsPlumb não acompanha transform)
        stepElement.style.position = 'absolute';
        stepElement.style.left = `${position.x}px`;
        stepElement.style.top = `${position.y}px`;
        stepElement.style.transform = 'none'; // Garantir que não há transform
        stepElement.dataset.stepId = stepId;
        stepElement.style.willChange = 'left, top';
        
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
            <div class="flow-step-footer">
                <button class="flow-step-btn-action" data-action="edit" data-step-id="${stepId}" title="Editar"><i class="fas fa-edit"></i></button>
                <button class="flow-step-btn-action" data-action="remove" data-step-id="${stepId}" title="Remover"><i class="fas fa-trash"></i></button>
                ${!isStartStep?`<button class="flow-step-btn-action" data-action="set-start" data-step-id="${stepId}" title="Definir como inicial">⭐</button>` : ''}
            </div>
            <!-- Nodes INSIDE the card -->
            <div class="flow-step-node-input" data-node-type="input" data-step-id="${stepId}" title="Entrada" style="width: 14px; height: 14px;"></div>
            ${!hasButtons ? `<div class="flow-step-node-output" data-node-type="output" data-step-id="${stepId}" title="Saída" style="width: 14px; height: 14px;"></div>` : ''}
        `;
        
        // Append inner to step and to contentContainer
        stepElement.appendChild(inner);
        const container = this.contentContainer || this.canvas;
        container.appendChild(stepElement);
        
        // Make draggable via jsPlumb (pass DOM element)
        // CRÍTICO: jsPlumb usa left/top automaticamente, não transform
        this.instance.draggable(stepElement, {
            containment: false,
            grid: [this.gridSize, this.gridSize],
            filter: '.flow-step-btn-action, .flow-step-btn-action *', // CRÍTICO: Não arrastar quando clicar nos botões
            start: (params) => {
                // Verificar se o clique foi em um botão de ação
                if (params.e && params.e.target && params.e.target.closest('.flow-step-btn-action')) {
                    return false; // Cancelar drag se for um botão
                }
                stepElement.classList.add('dragging');
                // Garantir que não há transform
                stepElement.style.transform = 'none';
            },
            drag: (params) => {
                // CRÍTICO: Garantir que não há transform durante drag
                stepElement.style.transform = 'none';
                // CRÍTICO: Revalidar durante drag para endpoints acompanharem
                this.instance.revalidate(stepElement);
                const inner = stepElement.querySelector('.flow-step-block-inner');
                if (inner) {
                    const nodes = inner.querySelectorAll('.flow-step-node-input, .flow-step-node-output, .flow-step-button-endpoint-container');
                    nodes.forEach(n => this.instance.revalidate(n));
                }
                this.instance.repaintEverything();
                this.onStepDrag(params);
            },
            stop: (params) => {
                // Garantir que não há transform após drag
                stepElement.style.transform = 'none';
                this.onStepDragStop(params);
            },
            cursor: 'move',
            zIndex: 1000
        });
        
        // After DOM painted, add endpoints to inner nodes and per-button containers
        // CRÍTICO: Usar double rAF para garantir DOM completamente renderizado
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // CRÍTICO: Configurar event listeners para botões de ação APÓS DOM estar pronto
                this.attachActionButtons(stepElement, stepId);
                
                // add endpoints and ensure deduplication
                this.addEndpoints(stepElement, stepId, step);
                this.instance.revalidate(stepElement);
                this.instance.repaintEverything();
            });
        });
        
        // cache
        this.steps.set(stepId, stepElement);
        if (isStartStep) stepElement.classList.add('flow-step-initial');
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
            
            // Remover listeners anteriores clonando o botão (remove todos os listeners)
            const newButton = button.cloneNode(true);
            if (button.parentNode) {
                button.parentNode.replaceChild(newButton, button);
            } else {
                console.error('❌ Botão não tem parentNode:', button);
                return;
            }
            
            // Garantir z-index alto para botões não serem bloqueados
            newButton.style.position = 'relative';
            newButton.style.zIndex = '9999';
            newButton.style.pointerEvents = 'auto';
            
            // Adicionar novo listener com capture phase
            newButton.addEventListener('click', (e) => {
                console.log(`🔵 Botão clicado: action=${action}, stepId=${buttonStepId}`, e);
                e.stopPropagation(); // Prevenir propagação para o canvas
                e.stopImmediatePropagation(); // Prevenir outros listeners
                e.preventDefault();
                
                // Forçar chamada mesmo se houver algum problema
                switch (action) {
                    case 'edit':
                        console.log('🔵 Chamando editStep para:', buttonStepId);
                        // Tentar múltiplas vezes para garantir
                        if (typeof this.editStep === 'function') {
                            this.editStep(buttonStepId);
                        } else {
                            console.error('❌ this.editStep não é uma função');
                            // Fallback direto
                            if (window.alpineFlowEditor && window.alpineFlowEditor.openStepModal) {
                                window.alpineFlowEditor.openStepModal(buttonStepId);
                            }
                        }
                        break;
                    case 'remove':
                        this.deleteStep(buttonStepId);
                        break;
                    case 'set-start':
                        this.setStartStep(buttonStepId);
                        break;
                    default:
                        console.warn('⚠️ Ação desconhecida:', action);
                }
            }, true); // Usar capture phase para garantir que seja executado primeiro
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
        
        // Remover endpoints antigos (todos os elementos do card)
        this.instance.removeAllEndpoints(element);
        const inputNodeOld = element.querySelector('.flow-step-node-input');
        const outputNodeOld = element.querySelector('.flow-step-node-output');
        if (inputNodeOld) this.instance.removeAllEndpoints(inputNodeOld);
        if (outputNodeOld) this.instance.removeAllEndpoints(outputNodeOld);
        
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
            footerEl.innerHTML = `
                <button class="flow-step-btn-action" data-action="edit" data-step-id="${stepId}" title="Editar"><i class="fas fa-edit"></i></button>
                <button class="flow-step-btn-action" data-action="remove" data-step-id="${stepId}" title="Remover"><i class="fas fa-trash"></i></button>
                ${!isStartStep ? `<button class="flow-step-btn-action" data-action="set-start" data-step-id="${stepId}" title="Definir como inicial">⭐</button>` : ''}
            `;
        }
        
        // CRÍTICO: Garantir que os nodes estejam no HTML (dentro do wrapper)
        let inputNode = innerWrapper.querySelector('.flow-step-node-input');
        if (!inputNode) {
            inputNode = document.createElement('div');
            inputNode.className = 'node-input flow-step-node-input';
            inputNode.setAttribute('data-node-type', 'input');
            inputNode.setAttribute('data-step-id', stepId);
            innerWrapper.appendChild(inputNode);
        }
        
        // Remover ou adicionar node de saída global conforme necessário
        let outputNode = innerWrapper.querySelector('.flow-step-node-output:not([data-button-index])');
        if (!hasButtons) {
            if (!outputNode) {
                outputNode = document.createElement('div');
                outputNode.className = 'node-output flow-step-node-output';
                outputNode.setAttribute('data-node-type', 'output');
                outputNode.setAttribute('data-step-id', stepId);
                innerWrapper.appendChild(outputNode);
            }
        } else {
            if (outputNode) {
                outputNode.remove();
            }
        }
        
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
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // CRÍTICO: Garantir position absolute e sem transform
        element.style.position = 'absolute';
        element.style.transform = 'none';
        const inner = element.querySelector('.flow-step-block-inner') || element;
        
        // Helper to safely remove endpoint by uuid
        const safeRemoveEndpoint = (uuid) => {
            try {
                const ep = this.instance.getEndpoint(uuid);
                if (ep) {
                    this.instance.deleteEndpoint(ep);
                }
            } catch (e) {}
        };
        
        // INPUT - LEFT CENTER (one per card)
        // CRÍTICO: Anchor fixo à esquerda, centro vertical
        const inputUuid = `endpoint-left-${stepId}`;
        safeRemoveEndpoint(inputUuid);
        const inputNode = inner.querySelector('.flow-step-node-input');
        if (inputNode) {
            // Garantir dimensões do node
            if (!inputNode.style.width) inputNode.style.width = '14px';
            if (!inputNode.style.height) inputNode.style.height = '14px';
            try {
                const ep = this.instance.addEndpoint(inputNode, {
                    uuid: inputUuid,
                    anchor: 'LeftMiddle', // Anchor simples - jsPlumb calcula automaticamente
                    maxConnections: -1,
                    isSource: false,
                    isTarget: true,
                    endpoint: ['Dot', { radius: 7 }],
                    paintStyle: { fill: '#10B981', outlineStroke: '#FFFFFF', outlineWidth: 2 },
                    hoverPaintStyle: { fill: '#FFB800', outlineStroke: '#FFFFFF', outlineWidth: 3 },
                    data: { stepId, endpointType: 'input' }
                });
                console.log(`✅ Endpoint input criado: ${inputUuid}`, ep);
            } catch (e) {
                console.error(`❌ Erro ao criar endpoint input ${inputUuid}:`, e);
            }
        } else {
            console.warn(`⚠️ Input node não encontrado para step ${stepId}`);
        }
        
        // Remove any global output if will create button endpoints
        const globalUuid = `endpoint-right-${stepId}`;
        if (hasButtons) {
            safeRemoveEndpoint(globalUuid);
        }
        
        // OUTPUTS
        if (hasButtons) {
            // One endpoint per button - anchor RightMiddle aligned to button endpoint container
            // CRÍTICO: Anchor fixo à direita do botão, centro vertical
            customButtons.forEach((btn, idx) => {
                const buttonContainer = inner.querySelector(`[data-endpoint-button="${idx}"]`);
                const btnUuid = `endpoint-button-${stepId}-${idx}`;
                safeRemoveEndpoint(btnUuid);
                if (buttonContainer) {
                    // Ensure buttonContainer is positioned relative inside card
                    if (!buttonContainer.style.position) buttonContainer.style.position = 'relative';
                    // Garantir dimensões do container
                    if (!buttonContainer.style.width) buttonContainer.style.width = '14px';
                    if (!buttonContainer.style.height) buttonContainer.style.height = '14px';
                    try {
                        const ep = this.instance.addEndpoint(buttonContainer, {
                            uuid: btnUuid,
                            anchor: 'RightMiddle', // Anchor simples - jsPlumb calcula automaticamente
                            maxConnections: 1,
                            isSource: true,
                            isTarget: false,
                            endpoint: ['Dot', { radius: 6 }],
                            paintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 2 },
                            hoverPaintStyle: { fill: '#FFB800', outlineStroke: '#FFFFFF', outlineWidth: 3 },
                            data: { stepId, buttonIndex: idx, endpointType: 'button' }
                        });
                        console.log(`✅ Endpoint botão criado: ${btnUuid}`, ep);
                    } catch (e) {
                        console.error(`❌ Erro ao criar endpoint botão ${btnUuid}:`, e);
                    }
                }
            });
        } else {
            // Global output present
            // CRÍTICO: Anchor fixo à direita, centro vertical
            const outputNode = inner.querySelector('.flow-step-node-output');
            safeRemoveEndpoint(globalUuid);
            if (outputNode) {
                // Garantir dimensões do node
                if (!outputNode.style.width) outputNode.style.width = '14px';
                if (!outputNode.style.height) outputNode.style.height = '14px';
                try {
                    const ep = this.instance.addEndpoint(outputNode, {
                        uuid: globalUuid,
                        anchor: 'RightMiddle', // Anchor simples - jsPlumb calcula automaticamente
                        maxConnections: -1,
                        isSource: true,
                        isTarget: false,
                        endpoint: ['Dot', { radius: 7 }],
                        paintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 2 },
                        hoverPaintStyle: { fill: '#FFB800', outlineStroke: '#FFFFFF', outlineWidth: 3 },
                        data: { stepId, endpointType: 'global' }
                    });
                    console.log(`✅ Endpoint output global criado: ${globalUuid}`, ep);
                } catch (e) {
                    console.error(`❌ Erro ao criar endpoint output global ${globalUuid}:`, e);
                }
            } else {
                console.warn(`⚠️ Output node não encontrado para step ${stepId}`);
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
                    // Revalidar o elemento arrastado e seus nodes internos
                    this.instance.revalidate(element);
                    const inner = element.querySelector('.flow-step-block-inner');
                    if (inner) {
                        const nodes = inner.querySelectorAll('.flow-step-node-input, .flow-step-node-output, .flow-step-button-endpoint-container');
                        nodes.forEach(n => this.instance.revalidate(n));
                    }
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
            
            // Extrair posição de left/top (jsPlumb usa left/top, não transform)
            let x = parseFloat(element.style.left) || 0;
            let y = parseFloat(element.style.top) || 0;
            
            // Snap to grid opcional
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
            
            // Atualizar posição usando left/top e garantir que não há transform
            element.style.left = `${x}px`;
            element.style.top = `${y}px`;
            element.style.transform = 'none'; // CRÍTICO: remover qualquer transform
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
        try {
            const srcEndpoint = info.sourceEndpoint;
            const tgtEndpoint = info.targetEndpoint;
            
            // CRÍTICO: Múltiplos métodos para obter UUID (compatibilidade)
            let sourceUuid = '';
            let targetUuid = '';
            
            if (srcEndpoint.getUuid) {
                sourceUuid = srcEndpoint.getUuid();
            } else if (srcEndpoint.uuid) {
                sourceUuid = srcEndpoint.uuid;
            } else if (srcEndpoint.id) {
                sourceUuid = srcEndpoint.id;
            } else if (srcEndpoint.canvas && srcEndpoint.canvas.getAttribute) {
                sourceUuid = srcEndpoint.canvas.getAttribute('data-uuid') || '';
            }
            
            if (tgtEndpoint.getUuid) {
                targetUuid = tgtEndpoint.getUuid();
            } else if (tgtEndpoint.uuid) {
                targetUuid = tgtEndpoint.uuid;
            } else if (tgtEndpoint.id) {
                targetUuid = tgtEndpoint.id;
            } else if (tgtEndpoint.canvas && tgtEndpoint.canvas.getAttribute) {
                targetUuid = tgtEndpoint.canvas.getAttribute('data-uuid') || '';
            }
            
            if (!sourceUuid || !targetUuid) {
                console.warn('⚠️ UUIDs não encontrados:', { sourceUuid, targetUuid, srcEndpoint, tgtEndpoint });
                return;
            }
            
            let sourceStepId=null, buttonIndex=null, connectionType='next';
            if (sourceUuid.startsWith('endpoint-button-')) {
                const m = sourceUuid.match(/^endpoint-button-([^-\s]+)-(\d+)$/);
                if (m) { 
                    sourceStepId = m[1]; 
                    buttonIndex = parseInt(m[2]); 
                    connectionType = 'button'; 
                }
            } else if (sourceUuid.startsWith('endpoint-right-')) {
                sourceStepId = sourceUuid.replace('endpoint-right-','');
                connectionType = 'next';
            }
            
            const targetMatch = targetUuid.startsWith('endpoint-left-') ? targetUuid.replace('endpoint-left-','') : null;
            const targetStepId = targetMatch;
            
            if (!sourceStepId || !targetStepId) {
                console.warn('⚠️ Step IDs não encontrados:', { sourceUuid, targetUuid, sourceStepId, targetStepId });
                return;
            }
            
            const connId = connectionType === 'button' && buttonIndex !== null
                ? `button-${sourceStepId}-${buttonIndex}-${targetStepId}`
                : `${sourceStepId}-${targetStepId}-${connectionType}`;
            
            // Prevent duplicates
            if (this.connections.has(connId)) {
                // If duplicate created, immediately detach the new connection
                if (info.connection && info.connection.detach) {
                    info.connection.detach();
                }
                return;
            }
            
            this.connections.set(connId, info.connection);
            
            // Persist to Alpine state
            const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === String(sourceStepId));
            if (!step) {
                console.warn('⚠️ Step não encontrado no Alpine:', sourceStepId);
                return;
            }
            
            if (connectionType === 'button' && buttonIndex !== null) {
                if (!step.config) step.config = {};
                if (!step.config.custom_buttons) step.config.custom_buttons = [];
                if (!step.config.custom_buttons[buttonIndex]) step.config.custom_buttons[buttonIndex] = {};
                step.config.custom_buttons[buttonIndex].target_step = targetStepId;
            } else {
                if (!step.connections) step.connections = {};
                step.connections[connectionType] = targetStepId;
            }
            
            console.log('✅ Conexão criada:', connId);
        } catch (e) {
            console.error('❌ onConnectionCreated error', e);
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
        console.log('🔵 editStep chamado com stepId:', stepId);
        
        // CRÍTICO: Abrir modal instantaneamente sem delay (PATCH CIRÚRGICO)
        // Usar setTimeout 0 para garantir que não há conflito com drag
        setTimeout(() => {
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
            
            // Estratégia 3: Tentar buscar pelo contexto Alpine diretamente
            console.error('❌ Não foi possível encontrar contexto Alpine:', {
                hasThisAlpine: !!this.alpine,
                hasWindowAlpineFlowEditor: !!window.alpineFlowEditor,
                stepId: stepId
            });
        }, 0);
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

