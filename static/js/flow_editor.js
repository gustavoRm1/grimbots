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
        this.repaintFrameId = null; // 🔥 FASE 1: Repaint throttling
        this.stepTransforms = new Map();
        
        // Endpoint management - V5.0 Anti-duplication system
        this.endpointRegistry = new Map(); // stepId -> Set of endpoint UUIDs
        this.endpointEventListeners = new WeakMap(); // endpoint -> Set of listeners
        this.endpointCreationLock = new Set(); // UUIDs being created (prevent race conditions)
        
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
     * Inicialização principal - V7 PROFISSIONAL
     * 🔥 REFATORADO: async/await para eliminar race conditions
     */
    async init() {
        if (!this.canvas) {
            console.error('❌ Canvas não encontrado:', this.canvasId);
            return;
        }
        
        if (typeof jsPlumb === 'undefined') {
            console.error('❌ jsPlumb não está carregado');
            return;
        }
        
        try {
            // CRÍTICO: Setup canvas PRIMEIRO para criar contentContainer
            this.setupCanvas();
            
            // Aguardar contentContainer estar no DOM
            await this.waitForElement(this.contentContainer, 2000);
            
            // Setup jsPlumb e aguardar completion
            await this.setupJsPlumbAsync();
            
            // Verificar se instance foi criado
            if (!this.instance) {
                console.error('❌ Instance não foi criado após setupJsPlumb!');
                return;
            }
            
            // Ativar sistema de proteção contra duplicação
            this.preventEndpointDuplication();
            
            // Continuar inicialização
            this.continueInit();
        } catch (error) {
            console.error('❌ Erro na inicialização:', error);
        }
    }
    
    /**
     * 🔥 V7: Aguarda elemento estar no DOM
     */
    waitForElement(element, timeout = 5000) {
        return new Promise((resolve, reject) => {
            if (!element) {
                reject(new Error('Element não fornecido'));
                return;
            }
            
            if (element.parentElement || element === document.body) {
                resolve(element);
                return;
            }
            
            const startTime = Date.now();
            const checkInterval = setInterval(() => {
                if (element.parentElement || element === document.body) {
                    clearInterval(checkInterval);
                    resolve(element);
                } else if (Date.now() - startTime > timeout) {
                    clearInterval(checkInterval);
                    reject(new Error(`Timeout aguardando elemento estar no DOM após ${timeout}ms`));
                }
            }, 50);
        });
    }
    
    /**
     * Continua inicialização após instance estar pronto
     */
    continueInit() {
        if (!this.instance) {
            console.error('❌ continueInit: instance não existe!');
            return;
        }
        
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
        
        // CRÍTICO: Configurar event delegation DEPOIS do contentContainer existir
        // Aguardar um pouco para garantir que o container está pronto
        setTimeout(() => {
            this.enableActionButtonsDelegation(); // Event delegation como fallback
        }, 100);
        
        // 🔥 V8 ULTRA: Renderizar steps após setup com delay maior para garantir que tudo está pronto
        setTimeout(() => {
            console.log('🔵 Renderizando steps...');
            this.renderAllSteps();
            console.log('✅ Steps renderizados');
        }, 200);
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
        // 🔥 V7 PROFISSIONAL: NÃO bloquear eventos no drag handle
        const handleButtonClick = (e) => {
            // 🔥 CRÍTICO: Se é o drag handle, deixar evento passar para jsPlumb
            const isDragHandle = e.target.closest('.flow-drag-handle');
            if (isDragHandle) {
                // Não interceptar - deixar jsPlumb gerenciar o drag
                return;
            }
            
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
                            e.stopImmediatePropagation();
                            e.stopPropagation();
                            e.preventDefault();
                            
                            // Desabilitar draggable temporariamente apenas para este elemento
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
                e.stopImmediatePropagation();
                e.stopPropagation();
                e.preventDefault();
                
                // Desabilitar draggable temporariamente apenas para este elemento
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
    /**
     * Setup jsPlumb - V7 PROFISSIONAL
     * 🔥 CORREÇÃO CRÍTICA: Sempre usar this.canvas como container (não contentContainer)
     * 🔥 REFATORADO: async/await para garantir completion
     */
    async setupJsPlumbAsync() {
        return new Promise((resolve, reject) => {
            try {
                // Garantir que contentContainer existe
                if (!this.contentContainer) {
                    this.setupCanvas();
                }
                
                if (!this.contentContainer) {
                    reject(new Error('contentContainer não existe após setupCanvas'));
                    return;
                }
                
                // 🔥 V7 CRÍTICO: Container SEMPRE deve ser this.canvas (não contentContainer)
                // O SVG overlay do jsPlumb é criado dentro do container especificado
                // Se usar contentContainer (que tem transform CSS), o SVG pode não aparecer corretamente
                const container = this.canvas;
                
                if (!container) {
                    reject(new Error('Canvas não encontrado'));
                    return;
                }
                
                console.log('🔵 [V7] Inicializando jsPlumb com canvas como container:', {
                    canvasId: container.id,
                    canvasClass: container.className,
                    hasContentContainer: !!this.contentContainer
                });
                
                // Criar instância jsPlumb com canvas como container
                try {
                    const existingInstance = jsPlumb.getInstance();
                    if (existingInstance && existingInstance.getContainer) {
                        const currentContainer = existingInstance.getContainer();
                        if (currentContainer === container) {
                            this.instance = existingInstance;
                            console.log('✅ [V7] Reutilizando instância jsPlumb existente');
                        } else {
                            this.instance = jsPlumb.newInstance({
                                Container: container
                            });
                            console.log('✅ [V7] Nova instância jsPlumb criada (container diferente)');
                        }
                    } else {
                        this.instance = jsPlumb.newInstance({
                            Container: container
                        });
                        console.log('✅ [V7] Nova instância jsPlumb criada');
                    }
                } catch(e) {
                    console.warn('⚠️ [V7] Erro ao criar newInstance, usando getInstance:', e);
                    this.instance = jsPlumb.getInstance({
                        Container: container
                    });
                }
                
                if (!this.instance) {
                    reject(new Error('jsPlumb.getInstance retornou null'));
                    return;
                }
                
                // CRÍTICO: Garantir que setContainer está correto
                this.instance.setContainer(container);
                
                // 🔥 V7 PROFISSIONAL: Defaults com Vertex Avoidance conforme documentação oficial
                // Grid de 20px (múltiplo de 10px conforme recomendação A*)
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
                    // 🔥 V7 PROFISSIONAL: Vertex Avoidance - Conexões evitam passar por cima de elementos
                    // NOTA: Para melhor vertex avoidance, recomenda-se usar Orthogonal ou Straight com constrain
                    // Bezier funciona mas não tem routing inteligente como Orthogonal
                    edgesAvoidVertices: true,        // Ativar vertex avoidance (A* algorithm)
                    // 🔥 V7 PROFISSIONAL: Bezier Connector conforme documentação oficial jsPlumb 2.15.6
                    // Opções válidas: curviness, stub, gap, scale, showLoopback, legacyPaint, cssClass, hoverClass
                    connector: ['Bezier', { 
                        curviness: 150,              // Curvatura padrão (documentação: default 150)
                        stub: 15,                   // Stub único em pixels (15px) - distância antes da curva começar
                        gap: 10,                    // Gap entre endpoint e conexão (10px)
                        scale: 0.45,                // Posição do control point (0.45 = 45% da distância source-target)
                        showLoopback: true,          // Mostrar conexões loopback (mesmo elemento)
                        legacyPaint: false,          // Usar estratégia moderna de pintura (padrão: false)
                        cssClass: 'flow-connector',  // Classe CSS para customização
                        hoverClass: 'flow-connector-hover' // Classe CSS aplicada no hover
                    }],
                    // 🔥 V7 PROFISSIONAL: Dot Endpoint padrão conforme documentação oficial
                    endpoint: ['Dot', { 
                        radius: 7,
                        cssClass: 'flow-endpoint-default',
                        hoverClass: 'flow-endpoint-default-hover'
                    }],
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
                    ConnectionsDetachable: true,
                    // 🔥 V7 PROFISSIONAL: Connection Overlays conforme documentação oficial
                    // Arrow overlay no final da conexão (location: 1 = 100% do caminho)
                    ConnectionOverlays: [
                        {
                            type: 'Arrow',
                            options: {
                                width: 12,              // Largura da base da seta (default: 20)
                                length: 15,             // Comprimento da seta (default: 20)
                                location: 1,            // No final da conexão (1 = 100%)
                                direction: 1,           // Direção: 1 = forward (padrão), -1 = backward
                                foldback: 0.623,        // Ponto de dobra (default: 0.623)
                                cssClass: 'flow-arrow-overlay',
                                paintStyle: {
                                    stroke: '#FFFFFF',
                                    strokeWidth: 2,
                                    fill: '#FFFFFF',
                                    fillStyle: 'solid'
                                }
                            }
                        }
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
                
                this.instance.setSuspendDrawing(false);
                
                // Configurar SVG overlay com retry
                this.configureSVGOverlayWithRetry(10).then(() => {
                    console.log('✅ [V7] jsPlumb inicializado completamente');
                    resolve();
                }).catch((e) => {
                    console.warn('⚠️ [V7] SVG overlay não configurado, mas continuando:', e);
                    resolve(); // Continuar mesmo se SVG overlay não foi configurado
                });
                
            } catch (error) {
                console.error('❌ [V7] Erro ao inicializar jsPlumb:', error);
                reject(error);
            }
        });
    }
    
    /**
     * 🔥 V7: Configura SVG overlay com retry robusto
     */
    configureSVGOverlayWithRetry(maxAttempts = 10) {
        return new Promise((resolve, reject) => {
            let attempt = 0;
            
            const tryConfigure = () => {
                attempt++;
                
                try {
                    // 🔥 V7 CRÍTICO: Buscar SVG overlay APENAS no container do jsPlumb (this.canvas)
                    const container = this.canvas;
                    const svgOverlay = container.querySelector('svg.jtk-overlay') || 
                                     container.querySelector('svg');
                    
                    if (svgOverlay) {
                        svgOverlay.style.position = 'absolute';
                        svgOverlay.style.left = '0';
                        svgOverlay.style.top = '0';
                        svgOverlay.style.width = '100%';
                        svgOverlay.style.height = '100%';
                        svgOverlay.style.zIndex = '10000';
                        svgOverlay.style.pointerEvents = 'none';
                        svgOverlay.style.display = 'block';
                        svgOverlay.style.visibility = 'visible';
                        svgOverlay.style.opacity = '1';
                        
                        console.log('✅ [V7] SVG overlay configurado');
                        resolve();
                    } else if (attempt < maxAttempts) {
                        setTimeout(tryConfigure, 100 * attempt);
                    } else {
                        reject(new Error(`SVG overlay não encontrado após ${maxAttempts} tentativas`));
                    }
                } catch(e) {
                    if (attempt < maxAttempts) {
                        setTimeout(tryConfigure, 100 * attempt);
                    } else {
                        reject(e);
                    }
                }
            };
            
            tryConfigure();
        });
    }
    
    /**
     * Método síncrono mantido para compatibilidade (deprecated)
     */
    setupJsPlumb() {
        console.warn('⚠️ setupJsPlumb() síncrono chamado - usar setupJsPlumbAsync()');
        // Fallback síncrono para compatibilidade
        if (!this.contentContainer) {
            this.setupCanvas();
        }
        if (!this.instance && this.canvas) {
            try {
                this.instance = jsPlumb.newInstance({
                    Container: this.canvas
                });
                this.instance.setContainer(this.canvas);
            } catch(e) {
                console.error('❌ Erro no fallback síncrono:', e);
            }
        }
    }
    
    /**
     * Configura canvas com grid e container interno
     * PATCH V4.0 - ManyChat Perfect
     */
    setupCanvas() {
        if (!this.canvas) {
            console.error('❌ setupCanvas: canvas não encontrado');
            return;
        }
        
        // 🔥 V8 ULTRA: Garantir que contentContainer existe e está correto
        // Se flow-canvas-content já existe no HTML, reutilizar
        let content = this.canvas.querySelector('.flow-canvas-content');
        if (!content) {
            console.log('🔵 Criando contentContainer...');
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
        } else {
            console.log('✅ contentContainer encontrado no HTML, reutilizando');
        }
        
        // CRÍTICO: Garantir que contentContainer tem os estilos corretos
        content.style.position = 'absolute';
        content.style.left = '0';
        content.style.top = '0';
        content.style.width = '100%';
        content.style.height = '100%';
        content.style.transformOrigin = '0 0';
        content.style.willChange = 'transform';
        content.style.pointerEvents = 'auto';
        
        this.contentContainer = content;
        console.log('✅ contentContainer configurado:', {
            exists: !!this.contentContainer,
            parent: this.contentContainer?.parentElement?.id,
            children: this.contentContainer?.children?.length || 0
        });
        
        // Ensure canvas base styles (grid)
        this.canvas.style.position = 'relative';
        this.canvas.style.overflow = 'hidden';
        this.canvas.style.background = '#0D0F15';
        this.canvas.style.backgroundImage = 'radial-gradient(circle, rgba(255,255,255,0.12) 1.5px, transparent 1.5px)';
        this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
        
        // 🔥 V7 PROFISSIONAL: MutationObserver com debounce para evitar loops infinitos
        if (this.transformObserver) {
            this.transformObserver.disconnect();
            this.transformObserver = null;
        }
        if (window.MutationObserver) {
            let debounceTimeout = null;
            let isRepainting = false; // Flag para evitar loops
            
            this.transformObserver = new MutationObserver(() => {
                if (isRepainting || !this.instance) return; // Evitar loops
                
                // Debounce: aguardar 16ms antes de processar
                if (debounceTimeout) {
                    clearTimeout(debounceTimeout);
                }
                
                debounceTimeout = setTimeout(() => {
                    if (isRepainting || !this.instance) return;
                    isRepainting = true;
                    
                    requestAnimationFrame(() => {
                        try {
                            // Revalidate nodes and cards
                            this.steps.forEach(el => {
                                try { 
                                    this.instance.revalidate(el);
                                    // Garantir que endpoints estão visíveis após revalidate
                                    const endpoints = this.instance.getEndpoints(el);
                                    endpoints.forEach(ep => {
                                        if (ep && ep.canvas) {
                                            ep.canvas.style.display = 'block';
                                            ep.canvas.style.visibility = 'visible';
                                            ep.canvas.style.opacity = '1';
                                        }
                                    });
                                } catch(e) {}
                            });
                            
                            // Repintar tudo
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                            
                            // Garantir que SVG overlay está visível (buscar no canvas)
                            const svgOverlay = this.canvas.querySelector('svg.jtk-overlay') || 
                                             this.canvas.querySelector('svg');
                            if (svgOverlay) {
                                svgOverlay.style.display = 'block';
                                svgOverlay.style.visibility = 'visible';
                                svgOverlay.style.opacity = '1';
                            }
                        } catch(e) {
                            console.error('❌ [V7] Erro ao revalidar após transform:', e);
                        } finally {
                            isRepainting = false;
                        }
                    });
                }, 16); // ~60fps
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
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
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
        console.log('🔵 renderAllSteps chamado', {
            hasInstance: !!this.instance,
            hasAlpine: !!this.alpine,
            hasConfig: !!this.alpine?.config,
            flowStepsCount: this.alpine?.config?.flow_steps?.length || 0
        });
        
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            console.warn('⚠️ renderAllSteps: Alpine ou config não disponível');
            return;
        }
        
        // 🔥 V8 ULTRA: Verificar se instance existe
        if (!this.instance) {
            console.error('❌ renderAllSteps: jsPlumb instance não existe! Tentando inicializar...');
            // Tentar inicializar jsPlumb novamente
            if (this.contentContainer) {
                try {
                    this.setupJsPlumb();
                } catch(e) {
                    console.error('❌ Erro ao tentar inicializar jsPlumb:', e);
                }
            } else {
                // Se não tem contentContainer, criar canvas primeiro
                this.setupCanvas();
                if (this.contentContainer) {
                    try {
                        this.setupJsPlumb();
                    } catch(e) {
                        console.error('❌ Erro ao tentar inicializar jsPlumb após criar canvas:', e);
                    }
                }
            }
            
            // Se ainda não tem instance, retornar
            if (!this.instance) {
                console.error('❌ renderAllSteps: Não foi possível inicializar instance');
                return;
            }
        }
        
        // 🔥 V8 ULTRA: Garantir que contentContainer existe
        if (!this.contentContainer) {
            console.error('❌ renderAllSteps: contentContainer não existe! Tentando criar...');
            this.setupCanvas();
            if (!this.contentContainer) {
                console.error('❌ renderAllSteps: Não foi possível criar contentContainer');
                return;
            }
        }
        
        const steps = this.alpine.config.flow_steps || [];
        if (!Array.isArray(steps)) {
            console.warn('⚠️ renderAllSteps: flow_steps não é array');
            return;
        }
        
        console.log(`🔵 renderAllSteps: renderizando ${steps.length} steps`);
        
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
            // 🔥 CRÍTICO: Forçar repaint final após tudo estar renderizado
            if (this.instance) {
                try {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                    console.log('✅ Repaint final executado após renderAllSteps');
                } catch(e) {
                    console.error('❌ Erro ao fazer repaint final:', e);
                }
            }
        }, 200);
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
        // 🔥 FASE 1: Adicionar classes oficiais jsPlumb
        stepElement.className = 'flow-step-block flow-card jtk-node';
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
                <!-- 🔥 V7 PROFISSIONAL: Drag handle no header - SEMPRE presente e interativo -->
                <div class="flow-drag-handle" style="position: absolute; top: 0; left: 0; right: 0; height: 40px; cursor: move; z-index: 1; pointer-events: auto; background: transparent;"></div>
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
            <!-- 🔥 V5.0: Nodes HTML separados para endpoints -->
            <div class="flow-step-node-input" style="position: absolute; left: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;"></div>
            ${!hasButtons ? '<div class="flow-step-node-output-global" style="position: absolute; right: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;"></div>' : ''}
        `;
        
        // 🔥 V8 ULTRA: Append inner to step and to contentContainer
        stepElement.appendChild(inner);
        
        // CRÍTICO: Garantir que contentContainer existe
        if (!this.contentContainer) {
            console.error('❌ renderStep: contentContainer não existe! Tentando criar...');
            this.setupCanvas();
        }
        
        const container = this.contentContainer || this.canvas;
        if (!container) {
            console.error('❌ renderStep: Nenhum container disponível!');
            return;
        }
        
        container.appendChild(stepElement);
        console.log('✅ Step adicionado ao container:', {
            stepId: stepId,
            container: container.className || container.id,
            containerChildren: container.children.length
        });
        
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
        
        // Save
        this.steps.set(stepId, stepElement);
        
        // 🔥 V5.0: Reset flag de endpoints antes de criar
        stepElement.dataset.endpointsInited = 'false';
        
        // 🔥 V7 PROFISSIONAL: Configurar draggable APÓS elemento estar no DOM e instance pronto
        // Aguardar DOM estar pronto
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Verificar se instance está pronto
                if (!this.instance) {
                    console.warn('⚠️ [V7] Instance não está pronto, aguardando...');
                    setTimeout(() => {
                        if (this.instance && stepElement.parentElement) {
                            this.setupDraggableForStep(stepElement, stepId, inner);
                        }
                    }, 300);
                } else if (stepElement.parentElement) {
                    // Instance pronto e elemento no DOM - configurar draggable
                    this.setupDraggableForStep(stepElement, stepId, inner);
                } else {
                    console.warn('⚠️ [V7] Elemento não está no DOM, aguardando...');
                    setTimeout(() => {
                        if (stepElement.parentElement && this.instance) {
                            this.setupDraggableForStep(stepElement, stepId, inner);
                        }
                    }, 300);
                }
                
                // Adicionar endpoints após configurar draggable
                setTimeout(() => {
                    console.log(`🔵 Adicionando endpoints para step ${stepId} após renderização`);
                    this.addEndpoints(stepElement, stepId, step);
                    
                    // 🔥 V8 ULTRA: Aguardar um pouco mais e forçar repaint
                    setTimeout(() => {
                        try { 
                            if (!this.instance) {
                                console.error('❌ Instance não existe ao revalidar step:', stepId);
                                return;
                            }
                            
                            this.instance.revalidate(stepElement); 
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint(); 
                            console.log('✅ Step renderizado e endpoints criados:', stepId);
                            
                            // Verificar se endpoints foram criados
                            const endpoints = this.instance.getEndpoints(stepElement);
                            console.log(`🔍 Verificação: ${endpoints.length} endpoints encontrados para step ${stepId}`);
                            endpoints.forEach((ep, idx) => {
                                try {
                                    const uuid = ep.getUuid();
                                    const canvas = ep.canvas;
                                    const computedStyle = canvas ? window.getComputedStyle(canvas) : null;
                                    console.log(`  Endpoint ${idx}:`, {
                                        uuid: uuid,
                                        hasCanvas: !!canvas,
                                        canvasVisible: computedStyle ? computedStyle.display !== 'none' : false,
                                        canvasZIndex: computedStyle ? computedStyle.zIndex : 'N/A',
                                        canvasPosition: canvas ? canvas.getBoundingClientRect() : null
                                    });
                                    
                                    // 🔥 CRÍTICO: Garantir que canvas está visível
                                    if (canvas) {
                                        canvas.style.display = 'block';
                                        canvas.style.visibility = 'visible';
                                        canvas.style.opacity = '1';
                                        canvas.style.pointerEvents = 'auto';
                                        canvas.style.zIndex = '10000';
                                    }
                                } catch(e) {
                                    console.error(`❌ Erro ao verificar endpoint ${idx}:`, e);
                                }
                            });
                            
                            // 🔥 CRÍTICO: Forçar repaint novamente após configurar estilos
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                        } catch(e) {
                            console.error('❌ Erro ao revalidar step:', e);
                        }
                    }, 150);
                }, 100);
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
        
        // 🔥 V7 PROFISSIONAL: Atualizar posição usando transform (compatível com draggable)
        const position = step.position || { x: 100, y: 100 };
        element.style.position = 'absolute';
        element.style.left = '0';
        element.style.top = '0';
        element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
        this.stepTransforms.set(stepId, { x: position.x, y: position.y });
        
        // 🔥 V5.0: Corrigir endpoints antes de remover (remove duplicados primeiro)
        this.fixEndpoints(element);
        
        // 🔥 V5.0: Reset flag de endpoints para permitir recriação
        element.dataset.endpointsInited = 'false';
        
        // Remover endpoints antigos apenas se necessário (não sempre)
        // Verificar se estrutura mudou (botões adicionados/removidos)
        const oldHasButtons = (step.config?.custom_buttons || []).length > 0;
        const newHasButtons = customButtons.length > 0;
        
        if (oldHasButtons !== newHasButtons) {
            // Estrutura mudou, corrigir endpoints primeiro (remove órfãos)
            this.fixEndpoints(element);
            // Depois remover todos e recriar
            try {
                this.instance.removeAllEndpoints(element);
            } catch(e) {
                console.warn('⚠️ Erro ao remover endpoints:', e);
            }
            this.endpointRegistry.delete(stepId);
            // Reset flag para permitir recriação
            element.dataset.endpointsInited = 'false';
        }
        
        // 🔥 V7 PROFISSIONAL: Garantir que o card tenha position absolute e transform correto
        element.style.position = 'absolute';
        element.style.left = '0';
        element.style.top = '0';
        // Manter transform se já existe, senão aplicar posição
        if (!element.style.transform || element.style.transform === 'none') {
            element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
        }
        
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
        const headerEl = innerWrapper.querySelector('.flow-step-header');
        if (headerEl) {
            const headerContent = headerEl.querySelector('.flow-step-header-content');
            if (headerContent) {
                headerContent.innerHTML = `
                    <div class="flow-step-icon-center">
                        <i class="fas ${this.stepIcons[stepType] || 'fa-circle'}" style="color: #FFFFFF;"></i>
                    </div>
                    <div class="flow-step-title-center">
                        ${this.getStepTypeLabel(stepType)}
                    </div>
                    ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
                `;
            }
            // 🔥 V5.0: Garantir que drag handle existe
            if (!headerEl.querySelector('.flow-drag-handle')) {
                const dragHandle = document.createElement('div');
                dragHandle.className = 'flow-drag-handle';
                dragHandle.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; height: 40px; cursor: move; z-index: 1;';
                headerEl.appendChild(dragHandle);
            }
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
        
        // 🔥 V5.0: Garantir que nodes HTML existam
        if (!innerWrapper.querySelector('.flow-step-node-input')) {
            const inputNode = document.createElement('div');
            inputNode.className = 'flow-step-node-input';
            inputNode.style.cssText = 'position: absolute; left: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;';
            innerWrapper.appendChild(inputNode);
        }
        
        if (!hasButtons && !innerWrapper.querySelector('.flow-step-node-output-global')) {
            const outputNode = document.createElement('div');
            outputNode.className = 'flow-step-node-output-global';
            outputNode.style.cssText = 'position: absolute; right: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;';
            innerWrapper.appendChild(outputNode);
        } else if (hasButtons && innerWrapper.querySelector('.flow-step-node-output-global')) {
            // Remover output global se botões existem
            const outputNode = innerWrapper.querySelector('.flow-step-node-output-global');
            if (outputNode) outputNode.remove();
        }
        
        // CRÍTICO: Re-adicionar endpoints APÓS o DOM estar completamente renderizado
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Reanexar listeners dos botões de ação
                this.attachActionButtons(element, stepId);
                
                // 🔥 V7 PROFISSIONAL: Reconfigurar draggable usando função dedicada
                if (this.instance && element.parentElement) {
                    this.setupDraggableForStep(element, stepId, innerWrapper);
                }
                
                this.addEndpoints(element, stepId, step);
                // Revalidar e repintar após adicionar endpoints
                if (this.instance) {
                    this.instance.revalidate(element);
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
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
     * 🔥 V5.0 - Sistema Anti-Duplicação de Endpoints
     * Remove endpoints duplicados e órfãos antes de criar novos
     */
    fixEndpoints(cardElement) {
        if (!cardElement || !this.instance) return;
        
        const stepId = cardElement.dataset.stepId;
        if (!stepId) return;
        
        try {
            // Obter todos os endpoints do elemento
            const allEndpoints = this.instance.getEndpoints(cardElement) || [];
            const expectedUuids = new Set();
            
            // Calcular UUIDs esperados
            const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === stepId);
            if (step) {
                expectedUuids.add(`endpoint-left-${stepId}`);
                const hasButtons = (step.config?.custom_buttons || []).length > 0;
                if (hasButtons) {
                    (step.config.custom_buttons || []).forEach((btn, idx) => {
                        expectedUuids.add(`endpoint-button-${stepId}-${idx}`);
                    });
                } else {
                    expectedUuids.add(`endpoint-right-${stepId}`);
                }
            }
            
            // Remover endpoints órfãos (que não estão na lista esperada)
            allEndpoints.forEach(ep => {
                try {
                    const uuid = ep.getUuid ? ep.getUuid() : null;
                    if (uuid && !expectedUuids.has(uuid)) {
                        console.log(`🧹 Removendo endpoint órfão: ${uuid}`);
                        this.instance.deleteEndpoint(ep);
                    }
                } catch(e) {}
            });
            
            // Verificar duplicação por UUID
            const uuidCounts = new Map();
            allEndpoints.forEach(ep => {
                try {
                    const uuid = ep.getUuid ? ep.getUuid() : null;
                    if (uuid) {
                        uuidCounts.set(uuid, (uuidCounts.get(uuid) || 0) + 1);
                    }
                } catch(e) {}
            });
            
            // Remover duplicados (manter apenas o primeiro)
            uuidCounts.forEach((count, uuid) => {
                if (count > 1) {
                    console.log(`🧹 Removendo ${count - 1} duplicado(s) do endpoint: ${uuid}`);
                    let foundFirst = false;
                    allEndpoints.forEach(ep => {
                        try {
                            const epUuid = ep.getUuid ? ep.getUuid() : null;
                            if (epUuid === uuid) {
                                if (!foundFirst) {
                                    foundFirst = true;
                                } else {
                                    this.instance.deleteEndpoint(ep);
                                }
                            }
                        } catch(e) {}
                    });
                }
            });
            
        } catch(e) {
            console.error('❌ Erro em fixEndpoints:', e);
        }
    }
    
    /**
     * 🔥 V5.0 - Sistema de Proteção Contra Duplicação
     * Monitora e previne criação duplicada de endpoints
     */
    preventEndpointDuplication() {
        if (!this.instance) return;
        
        // Interceptar addEndpoint para prevenir duplicação
        const originalAddEndpoint = this.instance.addEndpoint.bind(this.instance);
        this.instance.addEndpoint = (element, params) => {
            const uuid = params.uuid;
            if (!uuid) {
                return originalAddEndpoint(element, params);
            }
            
            // Verificar se já existe
            try {
                const existing = this.instance.getEndpoint(uuid);
                if (existing) {
                    console.warn(`⚠️ Endpoint ${uuid} já existe, ignorando criação duplicada`);
                    return existing;
                }
            } catch(e) {}
            
            // Verificar lock de criação
            if (this.endpointCreationLock.has(uuid)) {
                console.warn(`⚠️ Endpoint ${uuid} está sendo criado, ignorando duplicação`);
                return null;
            }
            
            // Adicionar lock
            this.endpointCreationLock.add(uuid);
            
            try {
                const endpoint = originalAddEndpoint(element, params);
                
                // Registrar endpoint
                const stepId = element.dataset.stepId;
                if (stepId) {
                    if (!this.endpointRegistry.has(stepId)) {
                        this.endpointRegistry.set(stepId, new Set());
                    }
                    this.endpointRegistry.get(stepId).add(uuid);
                }
                
                // Configurar event listeners uma única vez
                this.setupEndpointEventListeners(endpoint, uuid);
                
                return endpoint;
            } finally {
                // Remover lock após criação
                setTimeout(() => {
                    this.endpointCreationLock.delete(uuid);
                }, 100);
            }
        };
    }
    
    /**
     * 🔥 V5.0 - Configura event listeners nos endpoints (uma única vez)
     */
    setupEndpointEventListeners(endpoint, uuid) {
        if (!endpoint || !endpoint.canvas) return;
        
        // Verificar se já tem listeners configurados
        if (this.endpointEventListeners.has(endpoint)) {
            return; // Já configurado
        }
        
        const listeners = new Set();
        
        // Handler para prevenir drag do card
        const preventCardDrag = (ev) => {
            ev.stopPropagation();
            ev.stopImmediatePropagation();
        };
        
        // Adicionar listeners
        endpoint.canvas.addEventListener('mousedown', preventCardDrag, { capture: true });
        endpoint.canvas.addEventListener('pointerdown', preventCardDrag, { capture: true });
        endpoint.canvas.addEventListener('touchstart', preventCardDrag, { capture: true });
        
        listeners.add(preventCardDrag);
        this.endpointEventListeners.set(endpoint, listeners);
        
        // Garantir z-index e pointer-events
        if (endpoint.canvas) {
            endpoint.canvas.style.zIndex = '9999';
            endpoint.canvas.style.pointerEvents = 'auto';
        }
    }
    
    /**
     * 🔥 V5.0 - Wrapper ensureEndpoint: previne duplicação
     * Verifica existência antes de criar endpoint
     * CRÍTICO: Usa getEndpoint() primeiro (mais rápido), depois getEndpoints() como fallback
     */
    ensureEndpoint(instance, el, uuid, options) {
        if (!instance || !el || !uuid) return null;
        
        // ESTRATÉGIA 1: Verificar via getEndpoint() (mais rápido, busca global)
        try {
            const existingGlobal = instance.getEndpoint(uuid);
            if (existingGlobal) {
                if (window.FLOW_DEBUG) {
                    console.log(`✅ Endpoint ${uuid} já existe (global), retornando existente`);
                }
                return existingGlobal;
            }
        } catch(e) {
            // getEndpoint() pode falhar se não existir, continuar
        }
        
        // ESTRATÉGIA 2: Verificar via getEndpoints() no elemento (mais específico)
        try {
            const existingLocal = instance.getEndpoints(el).find(ep => {
                try {
                    return ep && ep.getUuid && ep.getUuid() === uuid;
                } catch(e) {
                    return false;
                }
            });
            if (existingLocal) {
                if (window.FLOW_DEBUG) {
                    console.log(`✅ Endpoint ${uuid} já existe (local), retornando existente`);
                }
                return existingLocal;
            }
        } catch(e) {
            // Ignorar erro, continuar criação
        }
        
        // ESTRATÉGIA 3: Verificar lock de criação (prevenir race conditions)
        // 🔥 V7 PROFISSIONAL: Tentar obter existente antes de retornar null
        if (this.endpointCreationLock.has(uuid)) {
            if (window.FLOW_DEBUG) {
                console.warn(`⚠️ [V7] Endpoint ${uuid} está sendo criado, tentando obter existente`);
            }
            // Tentar obter endpoint existente (pode ter sido criado enquanto verificávamos)
            try {
                const existing = instance.getEndpoint(uuid);
                if (existing) {
                    return existing;
                }
            } catch(e) {
                // Ignorar, continuar
            }
            // Se ainda não existe e há lock, aguardar um pouco e tentar novamente (síncrono com timeout curto)
            // Nota: Em race conditions extremas, pode retornar null, mas isso é melhor que duplicação
            // O código chamador deve lidar com null adequadamente
            return null;
        }
        
        // Adicionar lock ANTES de qualquer operação assíncrona
        this.endpointCreationLock.add(uuid);
        
        try {
            // CRÍTICO: Usar instance.addEndpoint() diretamente (já interceptado por preventEndpointDuplication)
            // O interceptor em preventEndpointDuplication() já faz a verificação final
            const endpoint = instance.addEndpoint(el, { uuid, ...options });
            
            // Verificar se realmente foi criado (pode ter sido interceptado)
            if (!endpoint) {
                // Endpoint foi interceptado, tentar obter existente
                try {
                    const existing = instance.getEndpoint(uuid);
                    if (existing) {
                        if (window.FLOW_DEBUG) {
                            console.log(`✅ Endpoint ${uuid} foi interceptado, retornando existente`);
                        }
                        return existing;
                    }
                } catch(e) {}
                return null;
            }
            
            // Registrar endpoint no registry
            const stepId = el.dataset.stepId || el.closest('[data-step-id]')?.dataset.stepId;
            if (stepId) {
                if (!this.endpointRegistry.has(stepId)) {
                    this.endpointRegistry.set(stepId, new Set());
                }
                this.endpointRegistry.get(stepId).add(uuid);
            }
            
            // Configurar event listeners uma única vez
            this.setupEndpointEventListeners(endpoint, uuid);
            
            return endpoint;
        } catch(e) {
            console.error(`❌ Erro ao criar endpoint ${uuid}:`, e);
            return null;
        } finally {
            // Remover lock após criação (com delay para evitar race conditions)
            setTimeout(() => {
                this.endpointCreationLock.delete(uuid);
            }, 100);
        }
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Força visibilidade completa de um endpoint
     * Garante que o endpoint e seu círculo SVG estão visíveis e interativos
     */
    forceEndpointVisibility(endpoint, stepId, endpointType = 'unknown') {
        if (!endpoint || !endpoint.canvas) {
            console.warn(`⚠️ [V7] Endpoint sem canvas para step ${stepId}, tipo ${endpointType}`);
            return false;
        }
        
        try {
            // 1. Garantir que canvas está visível
            endpoint.canvas.style.display = 'block';
            endpoint.canvas.style.visibility = 'visible';
            endpoint.canvas.style.opacity = '1';
            endpoint.canvas.style.pointerEvents = 'auto';
            endpoint.canvas.style.zIndex = '10000';
            endpoint.canvas.style.cursor = 'crosshair';
            endpoint.canvas.style.position = 'absolute';
            
            // 2. Buscar e configurar círculo SVG
            let circle = endpoint.canvas.querySelector('circle');
            
            // Se não encontrou no canvas, buscar no SVG pai
            if (!circle) {
                const svgParent = endpoint.canvas.closest('svg');
                if (svgParent) {
                    const circles = svgParent.querySelectorAll('circle');
                    circles.forEach(c => {
                        const cx = parseFloat(c.getAttribute('cx') || 0);
                        const cy = parseFloat(c.getAttribute('cy') || 0);
                        const r = parseFloat(c.getAttribute('r') || 0);
                        const canvasRect = endpoint.canvas.getBoundingClientRect();
                        const svgRect = svgParent.getBoundingClientRect();
                        const relativeX = canvasRect.left - svgRect.left + canvasRect.width / 2;
                        const relativeY = canvasRect.top - svgRect.top + canvasRect.height / 2;
                        
                        if (Math.abs(cx - relativeX) < 20 && Math.abs(cy - relativeY) < 20 && r > 0) {
                            circle = c;
                        }
                    });
                }
            }
            
            // 3. Configurar círculo SVG se encontrado
            if (circle) {
                const fillColor = endpointType === 'input' ? '#10B981' : '#FFFFFF';
                const strokeColor = endpointType === 'input' ? '#FFFFFF' : '#0D0F15';
                const radius = endpointType === 'button' ? '6' : '7';
                
                if (!circle.getAttribute('fill') || circle.getAttribute('fill') === 'none') {
                    circle.setAttribute('fill', fillColor);
                }
                if (!circle.getAttribute('stroke') || circle.getAttribute('stroke') === 'none') {
                    circle.setAttribute('stroke', strokeColor);
                }
                if (!circle.getAttribute('stroke-width') || circle.getAttribute('stroke-width') === '0') {
                    circle.setAttribute('stroke-width', '2');
                }
                if (!circle.getAttribute('r') || circle.getAttribute('r') === '0') {
                    circle.setAttribute('r', radius);
                }
                
                circle.style.display = 'block';
                circle.style.visibility = 'visible';
                circle.style.opacity = '1';
            }
            
            // 4. Garantir que SVG pai está visível
            const svgParent = endpoint.canvas.closest('svg');
            if (svgParent) {
                svgParent.style.display = 'block';
                svgParent.style.visibility = 'visible';
                svgParent.style.opacity = '1';
                svgParent.style.zIndex = '10000';
                svgParent.style.pointerEvents = 'none';
                svgParent.style.position = 'absolute';
                svgParent.style.left = '0';
                svgParent.style.top = '0';
                svgParent.style.width = '100%';
                svgParent.style.height = '100%';
            }
            
            // 5. Forçar repaint do endpoint
            if (endpoint.repaint && typeof endpoint.repaint === 'function') {
                endpoint.repaint();
            }
            
            // 6. Verificar se está realmente visível após configuração
            requestAnimationFrame(() => {
                const computedStyle = window.getComputedStyle(endpoint.canvas);
                const rect = endpoint.canvas.getBoundingClientRect();
                
                if (computedStyle.display === 'none' || 
                    computedStyle.visibility === 'hidden' || 
                    computedStyle.opacity === '0' ||
                    rect.width === 0 || 
                    rect.height === 0) {
                    console.error(`❌ [V7] Endpoint ${endpointType} do step ${stepId} ainda não está visível após configuração!`, {
                        display: computedStyle.display,
                        visibility: computedStyle.visibility,
                        opacity: computedStyle.opacity,
                        rect: rect
                    });
                }
            });
            
            return true;
        } catch(e) {
            console.error(`❌ [V7] Erro ao forçar visibilidade do endpoint ${endpointType} do step ${stepId}:`, e);
            return false;
        }
    }
    
    /**
     * Adiciona endpoints ao step
     * 🔥 V7 PROFISSIONAL - ManyChat Perfect com Anti-Duplicação Robusta
     * CRÍTICO: Garante que nodes HTML existam antes de criar endpoints
     */
    addEndpoints(element, stepId, step) {
        if (!this.instance) {
            console.error('❌ addEndpoints: jsPlumb instance não existe');
            return;
        }
        
        if (!element) {
            console.error('❌ addEndpoints: element não existe');
            return;
        }
        
        // 🔥 V8 ULTRA: Verificar se element está no DOM antes de criar endpoints
        if (!element.parentElement) {
            console.error('❌ addEndpoints: element não está no DOM!', stepId);
            return;
        }
        
        console.log('🔵 addEndpoints chamado para step:', stepId, {
            element: element,
            parent: element.parentElement?.className || 'sem-parent',
            hasInstance: !!this.instance,
            endpointsInited: element.dataset.endpointsInited
        });
        
        // CRÍTICO: Verificar flag dataset para evitar múltiplas criações
        // 🔥 V8 ULTRA: Se endpoints já foram inicializados, verificar se estão visíveis
        if (element.dataset.endpointsInited === 'true') {
            console.log('ℹ️ Endpoints já inicializados para step:', stepId, '- verificando visibilidade');
            try {
                // Revalidar primeiro
                this.instance.revalidate(element);
                
                // 🔥 CRÍTICO: Verificar se endpoints estão visíveis e forçar visibilidade se necessário
                const endpoints = this.instance.getEndpoints(element);
                let needsRepaint = false;
                
                endpoints.forEach((ep, idx) => {
                    if (ep && ep.canvas) {
                        const computedStyle = window.getComputedStyle(ep.canvas);
                        if (computedStyle.display === 'none' || computedStyle.visibility === 'hidden' || computedStyle.opacity === '0') {
                            ep.canvas.style.display = 'block';
                            ep.canvas.style.visibility = 'visible';
                            ep.canvas.style.opacity = '1';
                            ep.canvas.style.pointerEvents = 'auto';
                            ep.canvas.style.zIndex = '10000';
                            needsRepaint = true;
                            console.log(`✅ Endpoint ${idx} forçado a ficar visível`);
                        }
                    }
                });
                
                // Garantir que SVG overlay está visível
                const svgOverlay = this.contentContainer.querySelector('svg.jtk-overlay') || 
                                 this.contentContainer.querySelector('svg');
                if (svgOverlay) {
                    const svgStyle = window.getComputedStyle(svgOverlay);
                    if (svgStyle.display === 'none' || svgStyle.visibility === 'hidden') {
                        svgOverlay.style.display = 'block';
                        svgOverlay.style.visibility = 'visible';
                        svgOverlay.style.opacity = '1';
                        needsRepaint = true;
                        console.log('✅ SVG overlay forçado a ficar visível');
                    }
                }
                
                if (needsRepaint) {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                }
            } catch(e) {
                console.error('❌ Erro ao revalidar:', e);
            }
            return;
        }
        
        // CRÍTICO: Corrigir endpoints antes de criar novos (remove órfãos e duplicados)
        this.fixEndpoints(element);
        
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Ensure element position absolute
        element.style.position = 'absolute';
        
        // 🔥 V7 PROFISSIONAL: Garantir que layout está completamente calculado antes de criar endpoints
        // CRÍTICO: Aguardar múltiplos frames para garantir que layout está pronto
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // CRÍTICO: Garantir que nodes HTML existam antes de criar endpoints
                const innerWrapper = element.querySelector('.flow-step-block-inner') || element;
                
                // Garantir input node existe e tem dimensões corretas
                let inputNode = innerWrapper.querySelector('.flow-step-node-input');
                if (!inputNode) {
                    inputNode = document.createElement('div');
                    inputNode.className = 'flow-step-node-input';
                    inputNode.style.cssText = 'position: absolute; left: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;';
                    innerWrapper.appendChild(inputNode);
                }
                
                // 🔥 CRÍTICO: Garantir que inputNode tem dimensões antes de criar endpoint
                const inputRect = inputNode.getBoundingClientRect();
                if (inputRect.width === 0 || inputRect.height === 0) {
                    console.warn('⚠️ Input node não tem dimensões, aguardando...');
                    setTimeout(() => this.addEndpoints(element, stepId, step), 100);
                    return;
                }
                
                // Garantir output node existe (se não há botões)
                if (!hasButtons) {
                    let outputNode = innerWrapper.querySelector('.flow-step-node-output-global');
                    if (!outputNode) {
                        outputNode = document.createElement('div');
                        outputNode.className = 'flow-step-node-output-global';
                        outputNode.style.cssText = 'position: absolute; right: -8px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; z-index: 60; pointer-events: none;';
                        innerWrapper.appendChild(outputNode);
                    }
                    
                    // 🔥 CRÍTICO: Garantir que outputNode tem dimensões antes de criar endpoint
                    const outputRect = outputNode.getBoundingClientRect();
                    if (outputRect.width === 0 || outputRect.height === 0) {
                        console.warn('⚠️ Output node não tem dimensões, aguardando...');
                        setTimeout(() => this.addEndpoints(element, stepId, step), 100);
                        return;
                    }
                } else {
                    // Remover output node se botões existem
                    const outputNode = innerWrapper.querySelector('.flow-step-node-output-global');
                    if (outputNode) {
                        outputNode.remove();
                    }
                }
                
                // 🔥 CRÍTICO: Obter dimensões reais do elemento para calcular anchors corretamente
                const elementRect = element.getBoundingClientRect();
                const innerRect = innerWrapper.getBoundingClientRect();
                
                // 1) INPUT endpoint (left outside) - SEMPRE FIXO
                const inputUuid = `endpoint-left-${stepId}`;
                console.log(`🔵 Criando input endpoint para step ${stepId}`, {
                    inputNode: inputNode,
                    uuid: inputUuid,
                    inputRect: inputNode.getBoundingClientRect(),
                    elementRect: elementRect,
                    innerRect: innerRect
                });
                
                // 🔥 FASE 1: Anchor estático com offset (mantido para input)
                // Sintaxe: [x, y, ox, oy, offsetX, offsetY]
                // x=0 (left), y=0.5 (center vertical), ox=-1 (leftward), oy=0, offsetX=-8px, offsetY=0
                const inputEndpoint = this.ensureEndpoint(this.instance, inputNode, inputUuid, {
                    anchor: [0, 0.5, -1, 0, -8, 0], // left outside, center vertical, -8px offset (conforme doc oficial)
                    isSource: false,
                    isTarget: true,
                    maxConnections: -1,
                    // 🔥 V7 PROFISSIONAL: Dot Endpoint conforme documentação oficial
                    // Opções: radius, cssClass, hoverClass
                    endpoint: ['Dot', { 
                        radius: 7,
                        cssClass: 'flow-endpoint-input',
                        hoverClass: 'flow-endpoint-input-hover'
                    }],
                    paintStyle: { fill:'#10B981', outlineStroke:'#FFFFFF', outlineWidth:2 },
                    hoverPaintStyle: { fill:'#FFB800', outlineStroke:'#FFFFFF', outlineWidth:3 },
                    data: { stepId, endpointType: 'input' }
                });
                
                // 🔥 CRÍTICO: Revalidar imediatamente após criar endpoint para recalcular posição
                if (inputEndpoint) {
                    // Revalidar o elemento para recalcular posição do endpoint
                    this.instance.revalidate(inputNode);
                    this.instance.revalidate(element);
                    // Usar forceEndpointVisibility para garantir visibilidade
                    this.forceEndpointVisibility(inputEndpoint, stepId, 'input');
                } else {
                    console.error(`❌ Falha ao criar input endpoint para step ${stepId}`);
                }
                
                // 2) OUTPUT endpoints
                if (hasButtons) {
                    // Remover output global se existir
                    const globalUuid = `endpoint-right-${stepId}`;
                    try {
                        const existingGlobal = this.instance.getEndpoint(globalUuid);
                        if (existingGlobal) {
                            this.instance.deleteEndpoint(existingGlobal);
                        }
                    } catch(e) {}
                    
                    // Criar um endpoint por botão - ANCHOR FIXO baseado no índice
                    customButtons.forEach((btn, index) => {
                const uuid = `endpoint-button-${stepId}-${index}`;
                let buttonContainer = element.querySelector(`[data-endpoint-button="${index}"]`);
                
                // Se container não existe, criar
                if (!buttonContainer) {
                    // Buscar button item
                    const buttonItem = element.querySelector(`.flow-step-button-item[data-button-index="${index}"]`);
                    if (buttonItem) {
                        buttonContainer = document.createElement('div');
                        buttonContainer.className = 'flow-step-button-endpoint-container';
                        buttonContainer.setAttribute('data-endpoint-button', String(index));
                        buttonContainer.style.cssText = 'width:20px; height:20px; position:relative; z-index: 10001; pointer-events: auto;';
                        buttonItem.appendChild(buttonContainer);
                        console.log(`✅ Criado button container para botão ${index} do step ${stepId}`);
                    } else {
                        console.error(`❌ Button item não encontrado para índice ${index} do step ${stepId}`);
                        console.error(`❌ Element HTML:`, element.innerHTML.substring(0, 1000));
                    }
                }
                
                if (!buttonContainer) {
                    console.error(`❌ Não foi possível criar ou encontrar button container para botão ${index} do step ${stepId}`);
                    return; // Pular este botão
                }
                
                        const buttonTarget = buttonContainer;
                        
                        // Anchor fixo: calcular Y baseado no índice do botão
                        const buttonCount = customButtons.length;
                        const buttonSpacing = 1 / (buttonCount + 1);
                        const anchorY = Math.max(0.2, Math.min(0.8, 0.3 + (index * buttonSpacing)));
                        
                        console.log(`🔵 Criando endpoint para botão ${index} do step ${stepId}`, {
                            uuid: uuid,
                            buttonTarget: buttonTarget,
                            anchorY: anchorY,
                            buttonContainer: buttonContainer.getBoundingClientRect()
                        });
                        
                        // 🔥 FASE 1: Dynamic Anchor para botões (evita sobreposição)
                        // Múltiplas posições possíveis: right, top, bottom
                        // JsPlumb escolhe automaticamente a melhor posição
                        const endpoint = this.ensureEndpoint(this.instance, buttonTarget, uuid, {
                            anchor: [
                                [1, anchorY, 1, 0, 8, 0, "right"],  // Right (preferido)
                                [0.5, 0, 0, -1, 0, -8, "top"],      // Top (fallback)
                                [0.5, 1, 0, 1, 0, 8, "bottom"]      // Bottom (fallback)
                            ],
                            isSource: true,
                            isTarget: false,
                            maxConnections: 1,
                            // 🔥 V7 PROFISSIONAL: Dot Endpoint para botões conforme documentação oficial
                            endpoint: ['Dot', { 
                                radius: 6,
                                cssClass: 'flow-endpoint-button',
                                hoverClass: 'flow-endpoint-button-hover'
                            }],
                            paintStyle: { fill:'#FFFFFF', outlineStroke:'#0D0F15', outlineWidth:2 },
                            hoverPaintStyle: { fill:'#FFB800', outlineStroke:'#FFFFFF', outlineWidth:3 },
                            data: { stepId, buttonIndex: index, endpointType: 'button' }
                        });
                        
                        // 🔥 CRÍTICO: Revalidar imediatamente após criar endpoint
                        if (endpoint) {
                            this.instance.revalidate(buttonTarget);
                            this.instance.revalidate(element);
                            this.forceEndpointVisibility(endpoint, stepId, 'button');
                        } else {
                            console.error(`❌ Falha ao criar button endpoint ${index} para step ${stepId}`);
                        }
                    });
                } else {
                    // Sem botões: criar output global único - SEMPRE FIXO
                    const outUuid = `endpoint-right-${stepId}`;
                    const outputNode = innerWrapper.querySelector('.flow-step-node-output-global');
                    
                    if (!outputNode) {
                        console.error(`❌ Output node não encontrado para step ${stepId} sem botões!`);
                        console.error(`❌ innerWrapper:`, innerWrapper);
                        console.error(`❌ innerWrapper HTML:`, innerWrapper.innerHTML.substring(0, 500));
                    } else {
                        console.log(`✅ Criando output global endpoint para step ${stepId}`, {
                            outputNode: outputNode,
                            uuid: outUuid,
                            position: outputNode.getBoundingClientRect()
                        });
                        
                        // 🔥 FASE 1: Dynamic Anchor para output global (evita sobreposição)
                        // Múltiplas posições possíveis: right, top, bottom
                        // JsPlumb escolhe automaticamente a melhor posição baseado na orientação
                        const endpoint = this.ensureEndpoint(this.instance, outputNode, outUuid, {
                            anchor: [
                                [1, 0.5, 1, 0, 8, 0, "right"],      // Right (preferido)
                                [0.5, 0, 0, -1, 0, -8, "top"],      // Top (fallback)
                                [0.5, 1, 0, 1, 0, 8, "bottom"]      // Bottom (fallback)
                            ],
                            isSource: true,
                            isTarget: false,
                            maxConnections: -1,
                            // 🔥 V7 PROFISSIONAL: Dot Endpoint para output global conforme documentação oficial
                            endpoint: ['Dot', { 
                                radius: 7,
                                cssClass: 'flow-endpoint-output',
                                hoverClass: 'flow-endpoint-output-hover'
                            }],
                            paintStyle: { fill:'#FFFFFF', outlineStroke:'#0D0F15', outlineWidth:2 },
                            hoverPaintStyle: { fill:'#FFB800', outlineStroke:'#FFFFFF', outlineWidth:3 },
                            data: { stepId, endpointType: 'global' }
                        });
                        
                        // 🔥 CRÍTICO: Revalidar imediatamente após criar endpoint
                        if (endpoint) {
                            this.instance.revalidate(outputNode);
                            this.instance.revalidate(element);
                            this.forceEndpointVisibility(endpoint, stepId, 'global');
                        } else {
                            console.error(`❌ Falha ao criar output endpoint para step ${stepId}`);
                        }
                    }
                }
                
                // 🔥 CRÍTICO: Revalidar e repintar após criar todos os endpoints (com throttling)
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        try {
                            this.instance.revalidate(element);
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                            console.log(`✅ Endpoints criados e revalidados para step ${stepId}`);
                        } catch(e) {
                            console.error('❌ Erro ao revalidar após criar endpoints:', e);
                        }
                    });
                });
                
                    // Marcar como inicializado APENAS após criar todos os endpoints
                    element.dataset.endpointsInited = 'true';
                });
            });
        
        // 🔥 V8 ULTRA: Garantir que todos os endpoints têm pointer-events: auto e z-index alto
        try {
            const allEndpoints = this.instance.getEndpoints(element);
            console.log(`🔵 Configurando ${allEndpoints.length} endpoints para step ${stepId}`);
            
            allEndpoints.forEach((endpoint, idx) => {
                if (endpoint && endpoint.canvas) {
                    // 🔥 CRÍTICO: Garantir que canvas está visível e interativo
                    endpoint.canvas.style.display = 'block';
                    endpoint.canvas.style.visibility = 'visible';
                    endpoint.canvas.style.opacity = '1';
                    endpoint.canvas.style.pointerEvents = 'auto';
                    endpoint.canvas.style.zIndex = '10000';
                    endpoint.canvas.style.cursor = 'crosshair';
                    
                    // 🔥 CRÍTICO: Garantir que o SVG circle dentro do canvas está visível
                    const circle = endpoint.canvas.querySelector('circle');
                    if (circle) {
                        circle.style.display = 'block';
                        circle.style.visibility = 'visible';
                        circle.style.opacity = '1';
                        // Garantir atributos SVG se não existirem
                        if (!circle.getAttribute('fill') || circle.getAttribute('fill') === 'none') {
                            const fillColor = endpoint.paintStyle?.fill || (endpoint.data?.endpointType === 'input' ? '#10B981' : '#FFFFFF');
                            circle.setAttribute('fill', fillColor);
                        }
                        if (!circle.getAttribute('stroke') || circle.getAttribute('stroke') === 'none') {
                            const strokeColor = endpoint.paintStyle?.outlineStroke || (endpoint.data?.endpointType === 'input' ? '#FFFFFF' : '#0D0F15');
                            circle.setAttribute('stroke', strokeColor);
                        }
                        if (!circle.getAttribute('stroke-width')) {
                            circle.setAttribute('stroke-width', endpoint.paintStyle?.outlineWidth || '2');
                        }
                        if (!circle.getAttribute('r') || circle.getAttribute('r') === '0') {
                            circle.setAttribute('r', endpoint.data?.endpointType === 'button' ? '6' : '7');
                        }
                    }
                    
                    // Garantir que o SVG parent também tenha z-index alto
                    const svgParent = endpoint.canvas.closest('svg');
                    if (svgParent) {
                        svgParent.style.zIndex = '10000';
                        svgParent.style.pointerEvents = 'none'; // SVG não intercepta, apenas os endpoints
                        svgParent.style.display = 'block';
                        svgParent.style.visibility = 'visible';
                        svgParent.style.opacity = '1';
                        svgParent.style.position = 'absolute';
                        svgParent.style.left = '0';
                        svgParent.style.top = '0';
                        svgParent.style.width = '100%';
                        svgParent.style.height = '100%';
                    }
                    
                    // Forçar repaint do endpoint
                    try {
                        if (endpoint.repaint) {
                            endpoint.repaint();
                        }
                    } catch(e) {
                        // Ignorar erros
                    }
                    
                    console.log(`✅ Endpoint ${idx} configurado:`, {
                        uuid: endpoint.getUuid(),
                        canvas: endpoint.canvas,
                        circle: circle,
                        circleFill: circle?.getAttribute('fill'),
                        circleR: circle?.getAttribute('r'),
                        position: endpoint.canvas.getBoundingClientRect(),
                        computedDisplay: window.getComputedStyle(endpoint.canvas).display,
                        computedZIndex: window.getComputedStyle(endpoint.canvas).zIndex
                    });
                } else {
                    console.warn(`⚠️ Endpoint ${idx} não tem canvas:`, endpoint);
                }
            });
            
            console.log(`✅ ${allEndpoints.length} endpoints configurados para step:`, stepId);
            
            // 🔥 CRÍTICO: Forçar repaint múltiplas vezes para garantir que endpoints apareçam
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    try {
                        this.instance.revalidate(element);
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                        
                        // 🔥 CRÍTICO: Garantir que SVG overlay está visível após criar endpoints
                        const svgOverlay = this.contentContainer.querySelector('svg.jtk-overlay') || 
                                         this.contentContainer.querySelector('svg');
                        if (svgOverlay) {
                            svgOverlay.style.position = 'absolute';
                            svgOverlay.style.left = '0';
                            svgOverlay.style.top = '0';
                            svgOverlay.style.width = '100%';
                            svgOverlay.style.height = '100%';
                            svgOverlay.style.zIndex = '10000';
                            svgOverlay.style.pointerEvents = 'none';
                            svgOverlay.style.display = 'block';
                            svgOverlay.style.visibility = 'visible';
                            svgOverlay.style.opacity = '1';
                            console.log(`✅ SVG overlay configurado após criar endpoints para step ${stepId}`);
                        }
                        
                        // 🔥 CRÍTICO: Garantir que todos os endpoints estão visíveis
                        const allEndpoints = this.instance.getEndpoints(element);
                        allEndpoints.forEach((ep, idx) => {
                            if (ep && ep.canvas) {
                                ep.canvas.style.display = 'block';
                                ep.canvas.style.visibility = 'visible';
                                ep.canvas.style.opacity = '1';
                                ep.canvas.style.pointerEvents = 'auto';
                                ep.canvas.style.zIndex = '10000';
                                
                                // 🔥 CRÍTICO: Garantir que o SVG circle dentro do canvas está visível
                                const circle = ep.canvas.querySelector('circle');
                                if (circle) {
                                    circle.style.display = 'block';
                                    circle.style.visibility = 'visible';
                                    circle.style.opacity = '1';
                                    // Garantir atributos SVG se não existirem
                                    if (!circle.getAttribute('fill') || circle.getAttribute('fill') === 'none') {
                                        const fillColor = ep.paintStyle?.fill || (ep.data?.endpointType === 'input' ? '#10B981' : '#FFFFFF');
                                        circle.setAttribute('fill', fillColor);
                                    }
                                    if (!circle.getAttribute('stroke') || circle.getAttribute('stroke') === 'none') {
                                        const strokeColor = ep.paintStyle?.outlineStroke || (ep.data?.endpointType === 'input' ? '#FFFFFF' : '#0D0F15');
                                        circle.setAttribute('stroke', strokeColor);
                                    }
                                    if (!circle.getAttribute('stroke-width')) {
                                        circle.setAttribute('stroke-width', ep.paintStyle?.outlineWidth || '2');
                                    }
                                    if (!circle.getAttribute('r') || circle.getAttribute('r') === '0') {
                                        circle.setAttribute('r', ep.data?.endpointType === 'button' ? '6' : '7');
                                    }
                                }
                                
                                // Forçar repaint do endpoint
                                try {
                                    if (ep.repaint) {
                                        ep.repaint();
                                    }
                                } catch(e) {
                                    // Ignorar erros
                                }
                            }
                        });
                        
                        // Repintar novamente após configurar estilos
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                        console.log(`✅ Repaint executado para step ${stepId}`);
                    } catch(e) {
                        console.error('❌ Erro ao fazer repaint:', e);
                    }
                });
            });
        } catch(e) {
            console.error('❌ Erro ao configurar endpoints:', e);
        }
        
        // Revalidar após criar endpoints
        try {
            // 🔥 V8 ULTRA: Revalidar e repintar com delay para garantir renderização
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    try {
                        this.instance.revalidate(element);
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                        console.log(`✅ Revalidação e repaint executados para step ${stepId}`);
                    } catch(e) {
                        console.error('❌ Erro ao revalidar após criar endpoints:', e);
                    }
                });
            });
        } catch(e) {
            console.error('❌ Erro ao agendar revalidação:', e);
        }
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Configura draggable para um step de forma robusta
     */
    setupDraggableForStep(stepElement, stepId, innerWrapper) {
        if (!this.instance) {
            console.error('❌ [V7] setupDraggableForStep: instance não existe');
            // Tentar novamente após um delay
            setTimeout(() => {
                if (this.instance) {
                    this.setupDraggableForStep(stepElement, stepId, innerWrapper);
                }
            }, 500);
            return;
        }
        
        if (!stepElement.parentElement) {
            console.error('❌ [V7] setupDraggableForStep: elemento não está no DOM');
            // Aguardar estar no DOM
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    if (stepElement.parentElement) {
                        this.setupDraggableForStep(stepElement, stepId, innerWrapper);
                    }
                });
            });
            return;
        }
        
        // Buscar drag handle
        const dragHandle = innerWrapper?.querySelector('.flow-drag-handle');
        
        // 🔥 V7 PROFISSIONAL: Configurar draggable com containment CORRETO
        // CRÍTICO: Containment deve ser contentContainer (onde elementos estão)
        // O jsPlumb calcula posições relativas ao containment especificado
        const draggableOptions = {
            containment: this.contentContainer || this.canvas,
            drag: (params) => {
                // Revalidar endpoints durante drag
                if (this.instance) {
                    try {
                        this.instance.revalidate(stepElement);
                        const endpoints = this.instance.getEndpoints(stepElement);
                        endpoints.forEach(ep => {
                            if (ep && ep.canvas) {
                                ep.canvas.style.display = 'block';
                                ep.canvas.style.visibility = 'visible';
                                ep.canvas.style.opacity = '1';
                            }
                        });
                    } catch(e) {
                        // Ignorar erros durante drag
                    }
                }
                this.onStepDrag(params);
            },
            stop: (params) => {
                console.log('🔵 [V7] Drag parado para step:', stepId);
                if (this.instance) {
                    try {
                        this.instance.revalidate(stepElement);
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
                    } catch(e) {
                        console.error('❌ [V7] Erro ao repintar após drag:', e);
                    }
                }
                this.onStepDragStop(params);
            },
            cursor: 'move',
            start: (params) => {
                console.log('🔵 [V7] Drag iniciado para step:', stepId, params);
                // Garantir que SVG overlay está visível
                if (this.instance) {
                    try {
                        const svgOverlay = this.canvas.querySelector('svg.jtk-overlay') || 
                                         this.canvas.querySelector('svg');
                        if (svgOverlay) {
                            svgOverlay.style.display = 'block';
                            svgOverlay.style.visibility = 'visible';
                            svgOverlay.style.opacity = '1';
                        }
                    } catch(e) {
                        // Ignorar erros
                    }
                }
                // 🔥 CRÍTICO: NÃO retornar false ou prevenir default aqui
                // Isso pode bloquear o drag
            }
        };
        
        // 🔥 V7 PROFISSIONAL: Se dragHandle existe, usar apenas ele
        if (dragHandle) {
            draggableOptions.handle = dragHandle;
            console.log('✅ [V7] Usando drag handle para step:', stepId, {
                handle: dragHandle,
                handleRect: dragHandle.getBoundingClientRect()
            });
        } else {
            // Sem handle: permitir drag pelo card inteiro, mas excluir elementos interativos
            draggableOptions.filter = '.flow-step-footer, .flow-step-btn-action, .jtk-endpoint, .flow-step-button-endpoint-container';
            console.log('⚠️ [V7] Drag handle não encontrado, usando card inteiro para step:', stepId);
            // 🔥 CRÍTICO: Garantir que o card inteiro pode ser arrastado
            stepElement.removeAttribute('data-jtk-not-draggable');
            stepElement.style.pointerEvents = 'auto';
        }
        
        try {
            // CRÍTICO: Garantir que elemento está no DOM antes de configurar draggable
            if (!stepElement.parentElement) {
                console.error('❌ [V7] Elemento não está no DOM antes de configurar draggable');
                return;
            }
            
            // Remover draggable anterior se existir
            try {
                this.instance.setDraggable(stepElement, false);
            } catch(e) {
                // Ignorar erro se não estava draggable
            }
            
            // 🔥 CRÍTICO: Garantir que elemento pode ser arrastado
            // Remover qualquer atributo que possa bloquear drag
            stepElement.removeAttribute('data-jtk-not-draggable');
            stepElement.style.pointerEvents = 'auto';
            stepElement.style.cursor = dragHandle ? 'default' : 'move';
            
            // Configurar draggable
            this.instance.draggable(stepElement, draggableOptions);
            
            // 🔥 CRÍTICO: Verificar se draggable foi configurado corretamente
            const isDraggable = this.instance.isDraggable ? this.instance.isDraggable(stepElement) : true;
            console.log('✅ [V7] Draggable configurado para step:', stepId, {
                hasHandle: !!dragHandle,
                containment: draggableOptions.containment?.className || draggableOptions.containment?.id,
                elementInDOM: !!stepElement.parentElement,
                elementPosition: stepElement.style.transform,
                isDraggable: isDraggable,
                elementStyle: {
                    position: stepElement.style.position,
                    pointerEvents: stepElement.style.pointerEvents,
                    cursor: stepElement.style.cursor
                }
            });
            
            if (!isDraggable && this.instance.isDraggable) {
                console.error('❌ [V7] Draggable NÃO foi configurado corretamente! Tentando novamente...');
                // Tentar novamente
                setTimeout(() => {
                    try {
                        this.instance.draggable(stepElement, draggableOptions);
                        const retryIsDraggable = this.instance.isDraggable(stepElement);
                        console.log('✅ [V7] Retry draggable:', retryIsDraggable);
                    } catch(e) {
                        console.error('❌ [V7] Erro no retry:', e);
                    }
                }, 100);
            }
        } catch (draggableError) {
            console.error('❌ [V7] Erro ao chamar instance.draggable:', draggableError, {
                stepId: stepId,
                hasInstance: !!this.instance,
                hasElement: !!stepElement,
                elementInDOM: !!stepElement.parentElement,
                error: draggableError.message
            });
            // Tentar novamente após um delay
            setTimeout(() => {
                try {
                    if (this.instance && stepElement.parentElement) {
                        this.instance.draggable(stepElement, draggableOptions);
                        console.log('✅ [V7] Draggable configurado após retry para step:', stepId);
                    } else {
                        console.error('❌ [V7] Instance ou elemento não disponível para retry');
                    }
                } catch (retryError) {
                    console.error('❌ [V7] Erro ao configurar draggable após retry:', retryError);
                }
            }, 200);
        }
    }
    
    /**
     * 🔥 FASE 1: Snap to Grid Profissional
     * Calcula posição com snap ao grid de 20px
     */
    snapToGrid(x, y) {
        const gridSize = this.gridSize || 20;
        return {
            x: Math.round(x / gridSize) * gridSize,
            y: Math.round(y / gridSize) * gridSize
        };
    }
    
    /**
     * 🔥 FASE 1: Repaint Throttling (60fps)
     * Throttle repaintEverything para evitar repaints excessivos
     */
    throttledRepaint() {
        if (this.repaintFrameId) {
            return; // Já agendado
        }
        
        this.repaintFrameId = requestAnimationFrame(() => {
            if (this.instance) {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
            }
            this.repaintFrameId = null;
        });
    }
    
    /**
     * Callback quando step é arrastado (otimizado)
     * 🔥 FASE 1: Adicionado snap to grid durante drag
     */
    onStepDrag(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            // 🔥 FASE 1: Adicionar classe oficial jsPlumb
            element.classList.add('dragging');
            element.classList.add('jtk-surface-element-dragging');
            
            // 🔥 FASE 1: Snap to grid durante drag
            if (params.pos && params.pos.length >= 2) {
                const snapped = this.snapToGrid(params.pos[0], params.pos[1]);
                // Atualizar posição com snap
                element.style.transform = `translate3d(${snapped.x}px, ${snapped.y}px, 0)`;
            }
            
            // Cancelar frame anterior
            if (this.dragFrameId) {
                cancelAnimationFrame(this.dragFrameId);
            }
            
            // CRÍTICO: Revalidar e repintar durante drag (com throttling)
            this.dragFrameId = requestAnimationFrame(() => {
                if (this.instance) {
                    // 🔥 V5.0: Corrigir endpoints durante drag (remove duplicados que podem aparecer)
                    this.fixEndpoints(element);
                    // Revalidar o elemento arrastado
                    this.instance.revalidate(element);
                    // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                    this.throttledRepaint();
                }
                this.dragFrameId = null;
            });
        }
    }
    
    /**
     * Callback quando drag para
     * 🔥 FASE 1: Adicionado snap to grid final e classes oficiais
     */
    onStepDragStop(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            // 🔥 FASE 1: Remover classes oficiais jsPlumb
            element.classList.remove('dragging');
            element.classList.remove('jtk-surface-element-dragging');
            // 🔥 FASE 1: Adicionar classe "most recently dragged"
            element.classList.add('jtk-most-recently-dragged');
            setTimeout(() => {
                element.classList.remove('jtk-most-recently-dragged');
            }, 1000);
            
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
            
            // 🔥 FASE 1: Snap to grid profissional
            const snapped = this.snapToGrid(x, y);
            x = snapped.x;
            y = snapped.y;
            
            // Atualizar posição usando translate3d
            element.style.transform = `translate3d(${x}px, ${y}px, 0)`;
            this.stepTransforms.set(stepId, { x, y });
            
            // Atualizar no Alpine
            this.updateStepPosition(stepId, { x, y });
            
            // 🔥 V5.0: Corrigir endpoints após drag (remove duplicados)
            this.fixEndpoints(element);
            
            // CRÍTICO: Revalidar e repintar após drag parar (com throttling)
            if (this.instance) {
                // Revalidar o elemento para recalcular endpoints na nova posição
                this.instance.revalidate(element);
                // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                this.throttledRepaint();
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
     * 🔥 V5.0 - Reconcile: compara conexões desejadas vs existentes, só cria/remove o que mudou
     */
    reconnectAll() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        if (!this.instance) {
            console.warn('⚠️ jsPlumb instance não disponível em reconnectAll()');
            return;
        }
        
        const steps = this.alpine.config.flow_steps;
        if (!Array.isArray(steps)) return;
        
        // 🔥 V5.0: Reconcile - calcular conexões desejadas
        const desiredConnections = new Map(); // connId -> { sourceUuid, targetUuid, type }
        
        steps.forEach(step => {
            if (!step || !step.id) return;
            const stepId = String(step.id);
            const stepConfig = step.config || {};
            const customButtons = stepConfig.custom_buttons || [];
            const hasButtons = customButtons.length > 0;
            const connections = step.connections || {};
            
            if (hasButtons) {
                customButtons.forEach((btn, idx) => {
                    if (btn.target_step) {
                        const targetId = String(btn.target_step);
                        const connId = `button-${stepId}-${idx}-${targetId}`;
                        desiredConnections.set(connId, {
                            sourceUuid: `endpoint-button-${stepId}-${idx}`,
                            targetUuid: `endpoint-left-${targetId}`,
                            type: 'button',
                            stepId,
                            buttonIndex: idx,
                            targetId
                        });
                    }
                });
            } else {
                ['next','pending','retry'].forEach(type => {
                    if (connections[type]) {
                        const targetId = String(connections[type]);
                        const connId = `${stepId}-${targetId}-${type}`;
                        desiredConnections.set(connId, {
                            sourceUuid: `endpoint-right-${stepId}`,
                            targetUuid: `endpoint-left-${targetId}`,
                            type: type,
                            stepId,
                            targetId
                        });
                    }
                });
            }
        });
        
        // 🔥 V5.0: Obter conexões existentes
        const existingConnections = new Map();
        this.connections.forEach((conn, connId) => {
            try {
                const source = conn.getSource();
                const target = conn.getTarget();
                if (source && target) {
                    const sourceUuid = source.getUuid ? source.getUuid() : null;
                    const targetUuid = target.getUuid ? target.getUuid() : null;
                    if (sourceUuid && targetUuid) {
                        existingConnections.set(connId, { sourceUuid, targetUuid, connection: conn });
                    }
                }
            } catch(e) {
                // Ignorar erro
            }
        });
        
        // 🔥 V5.0: Remover conexões que não devem existir
        existingConnections.forEach((existing, connId) => {
            if (!desiredConnections.has(connId)) {
                try {
                    this.instance.deleteConnection(existing.connection);
                    this.connections.delete(connId);
                } catch(e) {
                    console.warn(`⚠️ Erro ao remover conexão ${connId}:`, e);
                }
            }
        });
        
        // 🔥 V7 PROFISSIONAL: Criar conexões que faltam com retry automático
        requestAnimationFrame(() => {
            const pendingConnections = [];
            
            desiredConnections.forEach((desired, connId) => {
                // Verificar se já existe
                if (this.connections.has(connId)) {
                    return; // Já existe
                }
                
                try {
                    const srcEp = this.instance.getEndpoint(desired.sourceUuid);
                    const tgtEp = this.instance.getEndpoint(desired.targetUuid);
                    if (srcEp && tgtEp) {
                        const conn = this.instance.connect({ 
                            source: srcEp,
                            target: tgtEp
                        });
                        if (conn) {
                            this.connections.set(connId, conn);
                        }
                    } else {
                        // Endpoints não encontrados - adicionar à fila de retry
                        pendingConnections.push({ connId, desired });
                    }
                } catch (e) { 
                    console.warn(`⚠️ [V7] Erro ao conectar ${connId}:`, e);
                }
            });
            
            // Retry automático para conexões pendentes (endpoints podem não estar prontos ainda)
            if (pendingConnections.length > 0) {
                let retryCount = 0;
                const maxRetries = 5;
                const retryInterval = setInterval(() => {
                    retryCount++;
                    const stillPending = [];
                    
                    pendingConnections.forEach(({ connId, desired }) => {
                        try {
                            const srcEp = this.instance.getEndpoint(desired.sourceUuid);
                            const tgtEp = this.instance.getEndpoint(desired.targetUuid);
                            if (srcEp && tgtEp) {
                                const conn = this.instance.connect({ 
                                    source: srcEp,
                                    target: tgtEp
                                });
                                if (conn) {
                                    this.connections.set(connId, conn);
                                }
                            } else {
                                stillPending.push({ connId, desired });
                            }
                        } catch (e) {
                            stillPending.push({ connId, desired });
                        }
                    });
                    
                    if (stillPending.length === 0 || retryCount >= maxRetries) {
                        clearInterval(retryInterval);
                        if (stillPending.length > 0) {
                            console.warn(`⚠️ [V7] ${stillPending.length} conexões não puderam ser criadas após ${maxRetries} tentativas`);
                        }
                    }
                }, 200);
            }
            
            // Final repaint
            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
            this.throttledRepaint();
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
                // 🔥 V7 PROFISSIONAL: Overlays conforme documentação oficial
                // Arrow overlay já vem dos ConnectionOverlays defaults
                // Adicionar Label overlay apenas se houver label
                overlays: [
                    // Arrow overlay no final (já vem dos defaults, mas podemos sobrescrever)
                    {
                        type: 'Arrow',
                        options: {
                            width: 12,
                            length: 15,
                            location: 1,
                            direction: 1,
                            foldback: 0.623,
                            cssClass: 'flow-arrow-overlay',
                            paintStyle: {
                                stroke: '#FFFFFF',
                                strokeWidth: 2,
                                fill: '#FFFFFF'
                            }
                        }
                    },
                    // Label overlay no meio (se houver label)
                    ...(this.getConnectionLabel(connectionType) ? [{
                        type: 'Label',
                        options: {
                            label: this.getConnectionLabel(connectionType),
                            location: 0.5,
                            cssClass: 'flow-label-overlay',
                            useHTMLElement: true  // Usar elemento HTML para melhor controle CSS
                        }
                    }] : [])
                ],
                data: {
                    sourceStepId: sourceId,
                    targetStepId: targetId,
                    connectionType: connectionType
                }
            });
            
            if (connection) {
                this.connections.set(connId, connection);
                
                // 🔥 FASE 1: Adicionar classe oficial jsPlumb quando conectado
                if (sourceElement) sourceElement.classList.add('jtk-connected');
                if (targetElement) targetElement.classList.add('jtk-connected');
                
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
                
                // 🔥 FASE 1: Adicionar classe oficial jsPlumb quando conectado
                if (sourceElement) sourceElement.classList.add('jtk-connected');
                if (targetElement) targetElement.classList.add('jtk-connected');
                
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
     * 🔥 FASE 1: Adicionar classes oficiais jsPlumb
     */
    onConnectionCreated(info) {
        if (!info || !info.sourceEndpoint || !info.targetEndpoint) return;
        const sUuid = info.sourceEndpoint.getUuid ? info.sourceEndpoint.getUuid() : null;
        const tUuid = info.targetEndpoint.getUuid ? info.targetEndpoint.getUuid() : null;
        if (!sUuid || !tUuid) return;
        
        // 🔥 FASE 1: Adicionar classe oficial jsPlumb quando conectado
        try {
            const sourceElement = info.sourceEndpoint.getElement ? info.sourceEndpoint.getElement() : null;
            const targetElement = info.targetEndpoint.getElement ? info.targetEndpoint.getElement() : null;
            if (sourceElement) sourceElement.classList.add('jtk-connected');
            if (targetElement) targetElement.classList.add('jtk-connected');
        } catch(e) {
            // Ignorar erro se elementos não disponíveis
        }
        
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
     * 🔥 V5.0 - Tornado público e melhorado com null-safety
     */
    editStep(stepId) {
        if (window.FLOW_DEBUG) {
            console.log('🔵 editStep chamado com stepId:', stepId);
        }
        
        // 🔥 V5.0: Estratégia unificada - tentar todas as formas em ordem
        const strategies = [
            () => this.alpine && typeof this.alpine.openStepModal === 'function' ? this.alpine.openStepModal(stepId) : null,
            () => window.alpineFlowEditor && typeof window.alpineFlowEditor.openStepModal === 'function' ? window.alpineFlowEditor.openStepModal(stepId) : null,
            () => {
                try {
                    if (typeof Alpine !== 'undefined' && Alpine.$data) {
                        const alpineElement = document.querySelector('[x-data*="botConfigApp"]');
                        if (alpineElement) {
                            const alpineApp = Alpine.$data(alpineElement);
                            if (alpineApp && typeof alpineApp.openStepModal === 'function') {
                                alpineApp.openStepModal(stepId);
                                return true;
                            }
                        }
                    }
                } catch (e) {
                    if (window.FLOW_DEBUG) {
                        console.warn('⚠️ Erro ao buscar contexto Alpine via DOM:', e);
                    }
                }
                return null;
            }
        ];
        
        for (const strategy of strategies) {
            try {
                const result = strategy();
                if (result === true || result === undefined) {
                    return; // Sucesso
                }
            } catch (e) {
                if (window.FLOW_DEBUG) {
                    console.warn('⚠️ Erro em estratégia de abertura de modal:', e);
                }
            }
        }
        
        console.error('❌ Não foi possível abrir modal de edição para step:', stepId);
    }
    
    /**
     * Atualiza endpoints de um step
     * 🔥 V5.0 - Reset flag para permitir recriação
     */
    updateStepEndpoints(stepId) {
        const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === String(stepId));
        if (!step) return;
        
        const element = this.steps.get(String(stepId));
        if (!element) return;
        
        // 🔥 V5.0: Reset flag para permitir recriação
        element.dataset.endpointsInited = 'false';
        
        // 🔥 V5.0: Corrigir endpoints antes de remover
        this.fixEndpoints(element);
        
        // Verificar se estrutura mudou (botões adicionados/removidos)
        const oldHasButtons = (step.config?.custom_buttons || []).length > 0;
        const newHasButtons = (step.config?.custom_buttons || []).length > 0;
        
        if (oldHasButtons !== newHasButtons) {
            // Estrutura mudou, corrigir endpoints primeiro (remove órfãos)
            this.fixEndpoints(element);
            // Depois remover todos e recriar
            try {
                this.instance.removeAllEndpoints(element);
            } catch(e) {
                console.warn('⚠️ Erro ao remover endpoints:', e);
            }
            this.endpointRegistry.delete(String(stepId));
            // Reset flag para permitir recriação
            element.dataset.endpointsInited = 'false';
        }
        
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
    /**
     * 🔥 V7 PROFISSIONAL: Organização hierárquica vertical (estilo Hierarchy Layout)
     * Baseado em BFS para organizar em camadas respeitando conexões
     */
    organizeVertical() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        // 1. Identificar raiz (start step ou step sem conexões de entrada)
        const rootStep = steps.find(s => 
            String(s.id) === String(this.alpine.config.flow_start_step_id) ||
            !this.hasIncomingConnections(s.id, steps)
        ) || steps[0];
        
        // 2. Organizar em camadas usando BFS (Breadth-First Search)
        const layers = this.organizeInLayers(rootStep, steps);
        
        // 3. Calcular posições hierárquicas
        const positions = this.calculateHierarchyPositions(layers, 'vertical');
        
        // 4. Aplicar posições
        this.instance.setSuspendDrawing(true);
        positions.forEach(({ stepId, position }) => {
            this.updateStepPosition(stepId, position);
            const element = this.steps.get(String(stepId));
            if (element) {
                element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
                this.stepTransforms.set(String(stepId), position);
                this.instance.revalidate(element);
            }
        });
        this.instance.setSuspendDrawing(false);
        
        // 5. Repintar e reconectar
        setTimeout(() => {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
            this.reconnectAll();
            this.adjustCanvasSize();
        }, 50);
    }
    
    /**
     * Organiza steps horizontalmente
     */
    /**
     * 🔥 V7 PROFISSIONAL: Organização hierárquica horizontal (estilo Hierarchy Layout)
     * Baseado em BFS para organizar em camadas respeitando conexões
     */
    organizeHorizontal() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        // 1. Identificar raiz (start step ou step sem conexões de entrada)
        const rootStep = steps.find(s => 
            String(s.id) === String(this.alpine.config.flow_start_step_id) ||
            !this.hasIncomingConnections(s.id, steps)
        ) || steps[0];
        
        // 2. Organizar em camadas usando BFS (Breadth-First Search)
        const layers = this.organizeInLayers(rootStep, steps);
        
        // 3. Calcular posições hierárquicas (horizontal)
        const positions = this.calculateHierarchyPositions(layers, 'horizontal');
        
        // 4. Aplicar posições
        this.instance.setSuspendDrawing(true);
        positions.forEach(({ stepId, position }) => {
            this.updateStepPosition(stepId, position);
            const element = this.steps.get(String(stepId));
            if (element) {
                element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
                this.stepTransforms.set(String(stepId), position);
                this.instance.revalidate(element);
            }
        });
        this.instance.setSuspendDrawing(false);
        
        // 5. Repintar e reconectar
        setTimeout(() => {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
            this.reconnectAll();
            this.adjustCanvasSize();
        }, 50);
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Organiza fluxo completo hierarquicamente
     */
    organizeFlowComplete() {
        this.organizeVertical(); // Usa organização vertical por padrão
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Organiza por grupos (mesmo comportamento que vertical)
     */
    organizeByGroups() {
        this.organizeVertical();
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Grid Layout manual (alternativa ao GridLayout do Toolkit)
     * Organiza elementos em grid retangular
     * 
     * @param {Object} options - Opções do grid layout
     * @param {number} options.columns - Número fixo de colunas (-1 = automático)
     * @param {number} options.rows - Número fixo de linhas (-1 = automático)
     * @param {string} options.orientation - 'row-first' ou 'column-first' (padrão: 'row-first')
     * @param {Object} options.padding - Padding { x: 30, y: 30 }
     * @param {string} options.horizontalAlignment - 'start', 'center', 'end' (padrão: 'center')
     * @param {string} options.verticalAlignment - 'start', 'center', 'end' (padrão: 'center')
     */
    organizeGrid(options = {}) {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        const {
            columns = -1,
            rows = -1,
            orientation = 'row-first',
            padding = { x: 30, y: 30 },
            horizontalAlignment = 'center',
            verticalAlignment = 'center'
        } = options;
        
        // Calcular dimensões do grid
        const totalSteps = steps.length;
        let gridColumns = columns;
        let gridRows = rows;
        
        if (columns === -1 && rows === -1) {
            // Grid quadrado aproximado
            gridColumns = Math.ceil(Math.sqrt(totalSteps));
            gridRows = Math.ceil(totalSteps / gridColumns);
        } else if (columns !== -1) {
            gridColumns = columns;
            gridRows = Math.ceil(totalSteps / gridColumns);
        } else if (rows !== -1) {
            gridRows = rows;
            gridColumns = Math.ceil(totalSteps / gridRows);
        }
        
        // Calcular tamanho do step + espaçamento
        const stepWidth = 320;  // Largura do step
        const stepHeight = 200; // Altura aproximada do step
        const cellWidth = stepWidth + padding.x;
        const cellHeight = stepHeight + padding.y;
        
        // Calcular posições
        const positions = [];
        const startX = 100;
        const startY = 100;
        
        steps.forEach((step, index) => {
            let row, col;
            
            if (orientation === 'row-first') {
                row = Math.floor(index / gridColumns);
                col = index % gridColumns;
            } else {
                col = Math.floor(index / gridRows);
                row = index % gridRows;
            }
            
            // Calcular posição base
            let x = startX + (col * cellWidth);
            let y = startY + (row * cellHeight);
            
            // Aplicar alinhamento horizontal
            if (horizontalAlignment === 'center') {
                // Já está centralizado
            } else if (horizontalAlignment === 'start') {
                x = startX + (col * cellWidth);
            } else if (horizontalAlignment === 'end') {
                x = startX + (col * cellWidth) + (cellWidth - stepWidth);
            }
            
            // Aplicar alinhamento vertical
            if (verticalAlignment === 'center') {
                y = startY + (row * cellHeight) + ((cellHeight - stepHeight) / 2);
            } else if (verticalAlignment === 'start') {
                y = startY + (row * cellHeight);
            } else if (verticalAlignment === 'end') {
                y = startY + (row * cellHeight) + (cellHeight - stepHeight);
            }
            
            positions.push({
                stepId: step.id,
                position: { x, y }
            });
        });
        
        // Aplicar posições
        this.instance.setSuspendDrawing(true);
        positions.forEach(({ stepId, position }) => {
            this.updateStepPosition(stepId, position);
            const element = this.steps.get(String(stepId));
            if (element) {
                element.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`;
                this.stepTransforms.set(String(stepId), position);
                this.instance.revalidate(element);
            }
        });
        this.instance.setSuspendDrawing(false);
        
        // Repintar e reconectar
        setTimeout(() => {
                            // 🔥 FASE 1: Usar throttledRepaint ao invés de repaintEverything direto
                            this.throttledRepaint();
            this.reconnectAll();
            this.adjustCanvasSize();
        }, 50);
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Column Layout (Grid com 1 coluna)
     * Especialização do Grid Layout
     */
    organizeColumn() {
        this.organizeGrid({ columns: 1 });
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Row Layout (Grid com 1 linha)
     * Especialização do Grid Layout
     */
    organizeRow() {
        this.organizeGrid({ rows: 1 });
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Organiza steps em camadas usando BFS (Breadth-First Search)
     * Baseado no algoritmo Sugiyama modificado (usado pelo Hierarchy Layout)
     */
    organizeInLayers(rootStep, allSteps) {
        const layers = [];
        const visited = new Set();
        const queue = [{ step: rootStep, layer: 0 }];
        
        while (queue.length > 0) {
            const { step, layer } = queue.shift();
            
            if (visited.has(String(step.id))) continue;
            visited.add(String(step.id));
            
            if (!layers[layer]) layers[layer] = [];
            layers[layer].push(step);
            
            // Encontrar steps conectados (filhos) - respeitando direção das conexões
            const children = this.getConnectedSteps(step.id, allSteps);
            children.forEach(child => {
                if (!visited.has(String(child.id))) {
                    queue.push({ step: child, layer: layer + 1 });
                }
            });
        }
        
        // Adicionar steps não conectados como raízes adicionais
        allSteps.forEach(step => {
            if (!visited.has(String(step.id))) {
                if (!layers[0]) layers[0] = [];
                layers[0].push(step);
            }
        });
        
        return layers;
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Calcula posições hierárquicas baseado em camadas
     * Conforme documentação Hierarchy Layout (axis, alignment, placementStrategy)
     */
    calculateHierarchyPositions(layers, axis = 'vertical') {
        const positions = [];
        const layerSpacing = axis === 'vertical' ? 250 : 320;  // Espaçamento entre camadas
        const stepSpacing = axis === 'vertical' ? 320 : 250;   // Espaçamento entre steps na mesma camada
        const startX = 100;
        const startY = 100;
        
        layers.forEach((layer, layerIndex) => {
            const layerSize = layer.length;
            const layerStart = axis === 'vertical' 
                ? startX - ((layerSize * stepSpacing) / 2) + (stepSpacing / 2)
                : startX + (layerIndex * layerSpacing);
            
            layer.forEach((step, stepIndex) => {
                const position = axis === 'vertical'
                    ? {
                        x: layerStart + (stepIndex * stepSpacing),
                        y: startY + (layerIndex * layerSpacing)
                    }
                    : {
                        x: layerStart,
                        y: startY - ((layerSize * stepSpacing) / 2) + (stepIndex * stepSpacing) + (stepSpacing / 2)
                    };
                
                positions.push({
                    stepId: step.id,
                    position: position
                });
            });
        });
        
        return positions;
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Verifica se step tem conexões de entrada
     */
    hasIncomingConnections(stepId, allSteps) {
        return allSteps.some(step => {
            if (!step.connections) return false;
            return Object.values(step.connections).some(targetId => 
                String(targetId) === String(stepId)
            );
        });
    }
    
    /**
     * 🔥 V7 PROFISSIONAL: Obtém steps conectados (filhos) de um step
     */
    getConnectedSteps(stepId, allSteps) {
        const step = allSteps.find(s => String(s.id) === String(stepId));
        if (!step || !step.connections) return [];
        
        return Object.values(step.connections)
            .map(targetId => allSteps.find(s => String(s.id) === String(targetId)))
            .filter(Boolean);
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


