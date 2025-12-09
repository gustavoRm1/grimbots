/**
 * Flow Editor V3.0 - Editor Visual de Fluxo Profissional
 * Sistema completo de edição visual de fluxos de bot
 * Versão: 3.0.0 - Red Header Style + White Connections + Premium UX
 * 
 * Dependências:
 * - jsPlumb 2.15.6 (CDN)
 * - Alpine.js 3.x (CDN)
 * 
 * Design System:
 * - Header: #E02727 (vermelho)
 * - Body: #0F0F14 (preto premium)
 * - Border: #242836
 * - Connections: #FFFFFF (branco com glow)
 * - Grid: pontos brancos translúcidos
 * - Fonte: Inter
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
        this.contentContainer = null; // Container interno para aplicar transform apenas ao conteúdo
        this.zoomLevel = 1;
        this.pan = { x: 0, y: 0 };
        this.isPanning = false;
        this.lastPanPoint = { x: 0, y: 0 };
        this.snapToGrid = false;
        this.gridSize = 20;
        this.dragRepaintFrame = null;
        
        // Canvas infinito e performance
        this.canvasBounds = { minX: -10000, minY: -10000, maxX: 10000, maxY: 10000 };
        this.viewport = { x: 0, y: 0, width: 0, height: 0 };
        this.animationFrameId = null;
        this.zoomTarget = 1;
        this.isZooming = false;
        
        // Snapping
        this.snapEnabled = true;
        this.snapThreshold = 10;
        this.snapLines = { horizontal: [], vertical: [] };
        this.showSnapLines = false;
        
        // Organização automática
        this.layoutSpacing = { x: 320, y: 200 };
        
        // Virtualização
        this.visibleSteps = new Set();
        this.lastViewportUpdate = 0;
        
        // Cores por tipo de conexão (todas brancas)
        this.connectionColors = {
            next: '#FFFFFF',
            pending: '#FFFFFF',
            retry: '#FFFFFF'
        };
        
        // Ícones por tipo de step
        this.stepIcons = {
            content: 'fa-file-alt',
            message: 'fa-comment',
            audio: 'fa-headphones',
            video: 'fa-video',
            buttons: 'fa-mouse-pointer',
            payment: 'fa-credit-card',
            access: 'fa-key'
        };
        
        this.init();
    }
    
    init() {
        if (!this.canvas) {
            console.error('❌ Canvas não encontrado:', this.canvasId);
            return;
        }
        
        if (typeof jsPlumb === 'undefined') {
            console.error('❌ jsPlumb não está carregado.');
            return;
        }
        
        // Inicializar jsPlumb 2.x
        try {
            this.instance = jsPlumb;
            
            // jsPlumb deve usar o canvas (não o contentContainer) para detectar limites
            if (typeof this.instance.setContainer === 'function') {
                this.instance.setContainer(this.canvas);
            }
            
            // Configurar defaults (White Connections with Glow)
            if (typeof this.instance.importDefaults === 'function') {
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
                    connector: ['Bezier', { curviness: 75, stub: [10, 15], gap: 5 }],
                    endpoint: ['Dot', { radius: 7 }],
                    endpointStyle: { 
                        fill: '#FFFFFF', 
                        outlineStroke: '#0D0F15', 
                        outlineWidth: 2,
                        strokeWidth: 2
                    },
                    endpointHoverStyle: { 
                        fill: '#FFFFFF', 
                        outlineStroke: '#0D0F15', 
                        outlineWidth: 3,
                        strokeWidth: 3
                    },
                    anchors: ['Top', 'Bottom'],
                    maxConnections: -1
                });
            }
            
            // Bind eventos
            setTimeout(() => {
                this.instance.bind('connection', (info) => this.onConnectionCreated(info));
                this.instance.bind('connectionDetached', (info) => this.onConnectionDetached(info));
                
                this.instance.bind('click', (conn, originalEvent) => {
                    if (originalEvent && originalEvent.detail === 2) {
                        this.removeConnection(conn);
                    }
                });
                
                this.instance.bind('contextmenu', (conn, originalEvent) => {
                    if (originalEvent) {
                        originalEvent.preventDefault();
                        this.removeConnection(conn);
                    }
                });
            }, 100);
            
            console.log('✅ jsPlumb inicializado');
        } catch (error) {
            console.error('❌ Erro ao inicializar jsPlumb:', error);
            return;
        }
        
        this.setupCanvas();
        this.renderAllSteps();
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
    }
    
    /**
     * Configura o canvas com grid premium e canvas infinito
     */
    setupCanvas() {
        if (!this.canvas) return;
        
        // Canvas infinito - remover limites
        this.canvas.style.position = 'relative';
        this.canvas.style.overflow = 'auto'; // Permitir scroll quando necessário
        this.canvas.style.width = '100%';
        // Dimensões iniciais serão ajustadas dinamicamente pelo applyZoom()
        this.canvas.style.height = '600px';
        this.canvas.style.minHeight = '600px';
        this.canvas.style.minWidth = '100%';
        
        // Background com grid - configurado para se repetir infinitamente
        // O grid NÃO será afetado pelo transform porque está no canvas
        this.canvas.style.background = '#0D0F15';
        this.canvas.style.backgroundImage = `
            radial-gradient(circle, rgba(255, 255, 255, 0.25) 1.5px, transparent 1.5px)
        `;
        this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
        this.canvas.style.backgroundRepeat = 'repeat';
        this.canvas.style.backgroundPosition = '0 0';
        
        // Criar container interno para aplicar transform apenas ao conteúdo
        // Isso permite que o grid background permaneça fixo enquanto o conteúdo é transformado
        this.contentContainer = document.createElement('div');
        this.contentContainer.className = 'flow-canvas-content';
        this.contentContainer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            transform-origin: top left;
            will-change: transform;
            pointer-events: auto;
        `;
        
        // Mover steps existentes para o container (se houver)
        Array.from(this.canvas.children).forEach(child => {
            if (child.classList.contains('flow-step-block')) {
                this.contentContainer.appendChild(child);
            }
        });
        
        this.canvas.appendChild(this.contentContainer);
        
        // Atualizar viewport inicial
        this.updateViewport();
        
        // Expandir canvas automaticamente conforme cards
        this.expandCanvasBounds();
    }
    
    /**
     * Atualiza viewport para virtualização
     */
    updateViewport() {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const now = performance.now();
        
        // Throttle: atualizar viewport no máximo a cada 100ms
        if (now - this.lastViewportUpdate < 100) return;
        this.lastViewportUpdate = now;
        
        // Calcular viewport em coordenadas do mundo (considerando zoom/pan)
        this.viewport = {
            x: -this.pan.x / this.zoomLevel,
            y: -this.pan.y / this.zoomLevel,
            width: rect.width / this.zoomLevel,
            height: rect.height / this.zoomLevel
        };
        
        // Atualizar quais steps estão visíveis
        this.updateVisibleSteps();
    }
    
    /**
     * Atualiza conjunto de steps visíveis (virtualização)
     */
    updateVisibleSteps() {
        this.visibleSteps.clear();
        
        this.steps.forEach((element, stepId) => {
            const rect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            // Verificar se está dentro da viewport (com margem)
            const margin = 100; // Margem para pré-carregar
            const isVisible = 
                rect.right + margin >= canvasRect.left &&
                rect.left - margin <= canvasRect.right &&
                rect.bottom + margin >= canvasRect.top &&
                rect.top - margin <= canvasRect.bottom;
            
            if (isVisible) {
                this.visibleSteps.add(stepId);
                // Mostrar elemento
                element.style.display = '';
            } else {
                // Ocultar elemento (mas manter no DOM para jsPlumb)
                // Não ocultamos completamente para não quebrar conexões
                // Apenas otimizamos renderização visual se necessário
            }
        });
    }
    
    /**
     * Expande bounds do canvas automaticamente conforme posição dos cards
     * E ajusta dimensões do canvas se necessário para acomodar todos os cards
     */
    expandCanvasBounds() {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        let minX = 0, minY = 0, maxX = rect.width, maxY = rect.height;
        
        if (this.steps.size > 0) {
            this.steps.forEach((element) => {
                const step = this.alpine?.config?.flow_steps?.find(s => 
                    String(s.id) === element.dataset.stepId
                );
                if (step && step.position) {
                    const x = step.position.x;
                    const y = step.position.y;
                    minX = Math.min(minX, x - 200);
                    minY = Math.min(minY, y - 200);
                    maxX = Math.max(maxX, x + 500);
                    maxY = Math.max(maxY, y + 400);
                }
            });
        }
        
        // Atualizar bounds (com margem)
        this.canvasBounds = {
            minX: minX - 1000,
            minY: minY - 1000,
            maxX: maxX + 1000,
            maxY: maxY + 1000
        };
        
        // Ajustar dimensões do canvas se os cards estiverem fora dos limites atuais
        // Considerar o zoom level para calcular dimensões necessárias
        const requiredWidth = Math.max(rect.width, maxX + 500);
        const requiredHeight = Math.max(rect.height, maxY + 500);
        
        // Se necessário, expandir canvas (mas respeitando o zoom atual)
        // O applyZoom() já ajusta baseado no zoom, mas aqui garantimos espaço mínimo
        const currentWidth = parseFloat(this.canvas.style.width) || rect.width;
        const currentHeight = parseFloat(this.canvas.style.height) || rect.height;
        
        if (requiredWidth > currentWidth || requiredHeight > currentHeight) {
            // Aplicar dimensões mínimas necessárias
            this.canvas.style.width = `${Math.max(currentWidth, requiredWidth)}px`;
            this.canvas.style.height = `${Math.max(currentHeight, requiredHeight)}px`;
        }
    }
    
    /**
     * Habilita zoom com scroll suave (Google Maps style)
     * Suporta: Ctrl/Cmd + Scroll, Pinch zoom (touchpad), Wheel zoom
     */
    enableZoom() {
        if (!this.canvas) return;
        
        let zoomStartTime = 0;
        let zoomStartLevel = 1;
        let zoomTargetLevel = 1;
        let isZooming = false;
        
        const smoothZoom = (targetZoom, centerX, centerY) => {
            if (isZooming) return;
            isZooming = true;
            zoomStartLevel = this.zoomLevel;
            zoomTargetLevel = Math.max(0.1, Math.min(5, targetZoom));
            
            const startTime = performance.now();
            const duration = 200; // 200ms para suavização
            
            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                
                // Easing function (ease-out cubic)
                const ease = 1 - Math.pow(1 - progress, 3);
                
                this.zoomLevel = zoomStartLevel + (zoomTargetLevel - zoomStartLevel) * ease;
                
                // Zoom em relação ao ponto do mouse (centerX, centerY)
                if (centerX !== undefined && centerY !== undefined) {
                    const zoomChange = this.zoomLevel / zoomStartLevel;
                    const worldX = (centerX - this.pan.x) / zoomStartLevel;
                    const worldY = (centerY - this.pan.y) / zoomStartLevel;
                    
                    this.pan.x = centerX - worldX * this.zoomLevel;
                    this.pan.y = centerY - worldY * this.zoomLevel;
                }
                
                this.applyZoom();
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    isZooming = false;
                }
            };
            
            requestAnimationFrame(animate);
        };
        
        this.canvas.addEventListener('wheel', (e) => {
            // Zoom com Ctrl/Cmd + Scroll ou apenas scroll (sem modificador)
            if (e.ctrlKey || e.metaKey || true) {
                e.preventDefault();
                
                const rect = this.canvas.getBoundingClientRect();
                const centerX = e.clientX - rect.left;
                const centerY = e.clientY - rect.top;
                
                // Calcular delta de zoom suave
                const zoomDelta = -e.deltaY * 0.001;
                const newZoom = this.zoomLevel * (1 + zoomDelta);
                
                smoothZoom(newZoom, centerX, centerY);
            }
        }, { passive: false });
        
        // Suporte para pinch zoom (touchpad)
        let lastPinchDistance = 0;
        this.canvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 2) {
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                lastPinchDistance = Math.hypot(
                    touch2.clientX - touch1.clientX,
                    touch2.clientY - touch1.clientY
                );
            }
        }, { passive: false });
        
        this.canvas.addEventListener('touchmove', (e) => {
            if (e.touches.length === 2) {
                e.preventDefault();
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                const currentDistance = Math.hypot(
                    touch2.clientX - touch1.clientX,
                    touch2.clientY - touch1.clientY
                );
                
                if (lastPinchDistance > 0) {
                    const rect = this.canvas.getBoundingClientRect();
                    const centerX = (touch1.clientX + touch2.clientX) / 2 - rect.left;
                    const centerY = (touch1.clientY + touch2.clientY) / 2 - rect.top;
                    
                    const zoomDelta = currentDistance / lastPinchDistance;
                    const newZoom = this.zoomLevel * zoomDelta;
                    
                    smoothZoom(newZoom, centerX, centerY);
                }
                
                lastPinchDistance = currentDistance;
            }
        }, { passive: false });
    }
    
    /**
     * Aplica zoom ao canvas (combinado com pan) - Otimizado com requestAnimationFrame
     * Ajusta dimensões do canvas dinamicamente baseado no zoom (width e height)
     */
    applyZoom() {
        if (!this.canvas) return;
        
        // Cancelar frame anterior se existir
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        
        this.animationFrameId = requestAnimationFrame(() => {
            this.updateCanvasTransform();
            
            // Obter dimensões base do container pai
            const parent = this.canvas.parentElement;
            if (!parent) return;
            
            const parentRect = parent.getBoundingClientRect();
            const baseWidth = parentRect.width || 1200; // Largura base
            const baseHeight = 600; // Altura base em pixels
            
            // Limites
            const minSize = 600;
            const maxWidth = 20000; // Largura máxima aumentada para mais espaço
            const maxHeight = 20000; // Altura máxima aumentada para mais espaço
            
            // Calcular dimensões proporcionais ao zoom inverso
            // Zoom 1.0 = tamanho base, Zoom 0.5 = tamanho 2x, Zoom 0.1 = tamanho 10x
            const scaleFactor = 1 / this.zoomLevel;
            let calculatedWidth = Math.max(minSize, Math.min(maxWidth, baseWidth * scaleFactor));
            let calculatedHeight = Math.max(minSize, Math.min(maxHeight, baseHeight * scaleFactor));
            
            // Verificar se há cards que precisam de mais espaço e ajustar
            if (this.steps.size > 0) {
                this.steps.forEach((element) => {
                    const step = this.alpine?.config?.flow_steps?.find(s => 
                        String(s.id) === element.dataset.stepId
                    );
                    if (step && step.position) {
                        const x = step.position.x;
                        const y = step.position.y;
                        // Garantir espaço suficiente para todos os cards (com margem de 500px)
                        const requiredWidth = (x + 500) * scaleFactor;
                        const requiredHeight = (y + 400) * scaleFactor;
                        calculatedWidth = Math.max(calculatedWidth, requiredWidth);
                        calculatedHeight = Math.max(calculatedHeight, requiredHeight);
                    }
                });
            }
            
            // Aplicar dimensões calculadas
            this.canvas.style.width = `${calculatedWidth}px`;
            this.canvas.style.height = `${calculatedHeight}px`;
            this.canvas.style.minWidth = `${calculatedWidth}px`;
            this.canvas.style.minHeight = `${calculatedHeight}px`;
            
            // Atualizar grid background - o grid se expande automaticamente com o canvas
            // O background-repeat: repeat garante que o grid preenche toda a área expandida
            // IMPORTANTE: background-size em pixels absolutos para que não seja afetado pelo transform
            this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
            this.canvas.style.backgroundRepeat = 'repeat';
            this.canvas.style.backgroundPosition = '0 0';
            
            // Garantir que o overflow permite ver o grid expandido
            this.canvas.style.overflow = 'auto';
            
            // Debug: log das dimensões (pode remover depois)
            console.log(`Canvas expandido: ${calculatedWidth}x${calculatedHeight}px (zoom: ${this.zoomLevel.toFixed(2)})`);
            
            // Repintar jsPlumb de forma otimizada
            if (this.instance) {
                this.instance.repaintEverything();
            }
            
            // Atualizar viewport para virtualização
            this.updateViewport();
            
            // Expandir bounds do canvas automaticamente
            this.expandCanvasBounds();
            
            this.animationFrameId = null;
        });
    }
    
    /**
     * Zoom in com foco no card selecionado
     */
    zoomIn() {
        const targetZoom = Math.min(5, this.zoomLevel * 1.2);
        this.zoomToLevel(targetZoom);
    }
    
    /**
     * Zoom out com foco no card selecionado
     */
    zoomOut() {
        const targetZoom = Math.max(0.1, this.zoomLevel * 0.8);
        this.zoomToLevel(targetZoom);
    }
    
    /**
     * Zoom para nível específico com foco automático
     */
    zoomToLevel(targetZoom, focusElement = null) {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        let centerX = rect.width / 2;
        let centerY = rect.height / 2;
        
        // Se houver elemento focado, centralizar nele
        if (focusElement) {
            const elementRect = focusElement.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            centerX = elementRect.left + elementRect.width / 2 - canvasRect.left;
            centerY = elementRect.top + elementRect.height / 2 - canvasRect.top;
        } else if (this.selectedStep) {
            const element = this.steps.get(String(this.selectedStep));
            if (element) {
                const elementRect = element.getBoundingClientRect();
                const canvasRect = this.canvas.getBoundingClientRect();
                centerX = elementRect.left + elementRect.width / 2 - canvasRect.left;
                centerY = elementRect.top + elementRect.height / 2 - canvasRect.top;
            }
        }
        
        // Calcular novo pan para manter o ponto centralizado
        const zoomChange = targetZoom / this.zoomLevel;
        const worldX = (centerX - this.pan.x) / this.zoomLevel;
        const worldY = (centerY - this.pan.y) / this.zoomLevel;
        
        this.zoomLevel = targetZoom;
        this.pan.x = centerX - worldX * this.zoomLevel;
        this.pan.y = centerY - worldY * this.zoomLevel;
        
        this.applyZoom();
    }
    
    /**
     * Reset zoom e pan
     */
    zoomReset() {
        this.zoomLevel = 1;
        this.pan = { x: 0, y: 0 };
        this.applyZoom();
    }
    
    /**
     * Zoom para fit (ajustar todos os cards na tela)
     */
    zoomToFit() {
        if (!this.canvas || this.steps.size === 0) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const padding = 50;
        
        // Calcular bounding box de todos os steps
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.steps.forEach((element) => {
            const stepRect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            const x = stepRect.left - canvasRect.left;
            const y = stepRect.top - canvasRect.top;
            const w = stepRect.width;
            const h = stepRect.height;
            
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + w);
            maxY = Math.max(maxY, y + h);
        });
        
        if (minX === Infinity) return;
        
        const contentWidth = maxX - minX + padding * 2;
        const contentHeight = maxY - minY + padding * 2;
        
        const scaleX = (rect.width - padding * 2) / contentWidth;
        const scaleY = (rect.height - padding * 2) / contentHeight;
        const newZoom = Math.min(scaleX, scaleY, 1); // Não aumentar além de 1x
        
        // Centralizar
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        this.zoomLevel = newZoom;
        this.pan.x = rect.width / 2 - centerX * newZoom;
        this.pan.y = rect.height / 2 - centerY * newZoom;
        
        this.applyZoom();
    }
    
    /**
     * Habilita pan suave (arrastar canvas) - Otimizado com requestAnimationFrame
     * Suporta: Botão direito, meio, Alt + arrastar, Space + arrastar
     */
    enablePan() {
        if (!this.canvas) return;
        
        let panFrameId = null;
        
        const updatePan = () => {
            if (this.isPanning) {
                this.updateCanvasTransform();
                panFrameId = requestAnimationFrame(updatePan);
            } else {
                panFrameId = null;
            }
        };
        
        this.canvas.addEventListener('mousedown', (e) => {
            // Pan apenas se não estiver sobre um step e for botão direito/meio/alt/space
            const isOverStep = e.target.closest('.flow-step-block');
            const isOverButton = e.target.closest('button');
            const isOverEndpoint = e.target.closest('.jtk-endpoint');
            
            if (!isOverStep && !isOverButton && !isOverEndpoint && 
                (e.button === 2 || e.button === 1 || e.altKey || e.spaceKey)) {
                e.preventDefault();
                this.isPanning = true;
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
                this.canvas.style.cursor = 'grabbing';
                this.canvas.classList.add('panning');
                
                if (!panFrameId) {
                    panFrameId = requestAnimationFrame(updatePan);
                }
            }
        });
        
        // Detectar tecla Space pressionada
        let spacePressed = false;
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !e.target.matches('input, textarea')) {
                spacePressed = true;
                if (this.canvas) {
                    this.canvas.style.cursor = 'grab';
                }
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (e.code === 'Space') {
                spacePressed = false;
                if (this.canvas && !this.isPanning) {
                    this.canvas.style.cursor = 'default';
                }
            }
        });
        
        this.canvas.addEventListener('contextmenu', (e) => {
            const isOverStep = e.target.closest('.flow-step-block');
            if (!isOverStep) {
                e.preventDefault();
            }
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isPanning) {
                e.preventDefault();
                const dx = e.clientX - this.lastPanPoint.x;
                const dy = e.clientY - this.lastPanPoint.y;
                
                // Canvas infinito - sem limites
                this.pan.x += dx;
                this.pan.y += dy;
                
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
                // updatePan() já está rodando via requestAnimationFrame
            } else if (spacePressed && e.buttons === 1) {
                // Pan com Space + arrastar
                if (!this.isPanning) {
                    this.isPanning = true;
                    this.lastPanPoint = { x: e.clientX, y: e.clientY };
                    this.canvas.style.cursor = 'grabbing';
                    this.canvas.classList.add('panning');
                    
                    if (!panFrameId) {
                        panFrameId = requestAnimationFrame(updatePan);
                    }
                }
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isPanning = false;
            this.canvas.style.cursor = spacePressed ? 'grab' : 'default';
            this.canvas.classList.remove('panning');
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.isPanning = false;
            this.canvas.style.cursor = 'default';
            this.canvas.classList.remove('panning');
        });
    }
    
    /**
     * Atualiza transform do canvas (zoom + pan combinados)
     * IMPORTANTE: O transform é aplicado apenas ao container de conteúdo, NÃO ao canvas
     * Isso permite que o grid background permaneça fixo e se expanda corretamente
     */
    updateCanvasTransform() {
        if (!this.canvas) return;
        
        // Aplicar transform apenas ao container de conteúdo, não ao canvas
        // O canvas mantém o grid background fixo que se repete conforme expande
        if (this.contentContainer) {
            this.contentContainer.style.transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoomLevel})`;
            this.contentContainer.style.pointerEvents = 'auto'; // Habilitar interação quando transformado
        } else {
            // Fallback: aplicar no canvas se container não existir
            this.canvas.style.transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoomLevel})`;
        }
        
        this.canvas.style.transformOrigin = 'top left';
    }
    
    /**
     * Habilita seleção visual
     */
    enableSelection() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('click', (e) => {
            if (e.target.closest('button')) return;
            
            const stepElement = e.target.closest('.flow-step-block');
            if (stepElement) {
                this.selectStep(stepElement.dataset.stepId);
            } else {
                this.deselectStep();
            }
        });
    }
    
    /**
     * Seleciona um step
     */
    selectStep(stepId) {
        this.deselectStep();
        
        const element = this.steps.get(String(stepId));
        if (element) {
            element.classList.add('flow-step-selected');
            this.selectedStep = stepId;
        }
    }
    
    /**
     * Deseleciona step atual
     */
    deselectStep() {
        if (this.selectedStep) {
            const element = this.steps.get(String(this.selectedStep));
            if (element) {
                element.classList.remove('flow-step-selected');
            }
        }
        this.selectedStep = null;
    }
    
    /**
     * Renderiza todos os steps
     */
    renderAllSteps() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        const steps = this.alpine.config.flow_steps;
        this.clearCanvas();
        
        // Compatibilidade: converter steps antigos automaticamente
        steps.forEach(step => {
            // Garantir que config existe
            if (!step.config) {
                step.config = {};
            }
            // Garantir que custom_buttons existe
            if (!step.config.custom_buttons) {
                step.config.custom_buttons = [];
            }
            // Garantir que connections existe
            if (!step.connections) {
                step.connections = {};
            }
        });
        
        steps.forEach(step => {
            this.renderStep(step);
        });
        
        // Aguardar DOM renderizar antes de conectar
        setTimeout(() => {
            this.reconnectAll();
        }, 50);
    }
    
    /**
     * Renderiza um step individual
     */
    renderStep(step) {
        if (!step || !step.id) {
            console.error('❌ Step inválido:', step);
            return;
        }
        
        const stepId = String(step.id);
        const stepType = step.type || 'message';
        const stepConfig = step.config || {};
        
        if (this.steps.has(stepId)) {
            this.updateStep(step);
            return;
        }
        
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block';
        stepElement.dataset.stepId = stepId;
        
        const position = step.position || { x: 100, y: 100 };
        stepElement.style.left = `${position.x}px`;
        stepElement.style.top = `${position.y}px`;
        
        const icon = this.stepIcons[stepType] || 'fa-circle';
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        
        // Obter botões customizados
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Preparar conteúdo conforme hierarquia: Header → Mídia → URL → Texto → Botões → Ações → Outputs
        const mediaUrl = stepConfig.media_url || '';
        const hasMedia = !!mediaUrl;
        const previewText = this.getStepPreview(step);
        
        // Renderizar mídia (se houver)
        let mediaHTML = '';
        if (hasMedia) {
            const mediaType = stepConfig.media_type || 'video';
            const mediaIcon = mediaType === 'video' ? 'fa-video' : 'fa-image';
            mediaHTML = `
                <div class="flow-step-media-preview">
                    <i class="fas ${mediaIcon}"></i>
                    <span>${mediaType === 'video' ? 'Vídeo' : 'Foto'}</span>
                </div>
            `;
        }
        
        // Renderizar botões no body (conforme especificação: dentro do próprio botão)
        let buttonsHTML = '';
        if (hasButtons) {
            buttonsHTML = '<div class="flow-step-buttons-container">';
            customButtons.forEach((btn, index) => {
                const btnText = btn.text || `Botão ${index + 1}`;
                buttonsHTML += `
                    <div class="flow-step-button-item" data-button-index="${index}" data-button-id="${btn.id || `btn-${index}`}">
                        <span class="flow-step-button-text">${this.escapeHtml(btnText)}</span>
                        <div class="flow-step-button-endpoint-container" data-endpoint-button="${index}"></div>
                    </div>
                `;
            });
            buttonsHTML += '</div>';
        }
        
        // HTML do bloco seguindo hierarquia INTUITIVA: Header → Mídia → Texto → Botões → Ações → Outputs
        stepElement.innerHTML = `
            <div class="flow-step-header">
                <div class="flow-step-header-content">
                    <div class="flow-step-icon-center">
                        <i class="fas ${icon}" style="color: #FFFFFF;"></i>
                    </div>
                    <div class="flow-step-title-center">
                        ${this.getStepTypeLabel(stepType)}
                    </div>
                    ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
                </div>
            </div>
            <div class="flow-step-body">
                ${mediaHTML}
                ${previewText ? `<div class="flow-step-preview">${previewText}</div>` : ''}
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
        
        // Adicionar ao container de conteúdo se existir, senão ao canvas diretamente
        if (this.contentContainer) {
            this.contentContainer.appendChild(stepElement);
        } else {
            this.canvas.appendChild(stepElement);
        }
        
        // Tornar arrastável (Drag otimizado)
        this.instance.draggable(stepElement, {
            containment: 'parent',
            grid: this.snapToGrid ? [this.gridSize, this.gridSize] : false,
            drag: (params) => {
                this.onStepDrag(params);
                // Repintar apenas a conexão do elemento sendo arrastado (otimizado)
                if (this.dragRepaintFrame) {
                    cancelAnimationFrame(this.dragRepaintFrame);
                }
                this.dragRepaintFrame = requestAnimationFrame(() => {
                    if (this.instance) {
                        this.instance.repaint(params.el);
                    }
                });
            },
            stop: (params) => {
                this.onStepDragStop(params);
                if (this.dragRepaintFrame) {
                    cancelAnimationFrame(this.dragRepaintFrame);
                }
                // Repintar todas as conexões após parar
                if (this.instance) {
                    this.instance.repaintEverything();
                }
            },
            cursor: 'move',
            zIndex: 1000
        });
        
        // Adicionar endpoints (agora com lógica dinâmica)
        this.addEndpoints(stepElement, stepId, step);
        
        this.steps.set(stepId, stepElement);
        
        if (isStartStep) {
            stepElement.classList.add('flow-step-initial');
        }
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
        
        const position = step.position || { x: 100, y: 100 };
        element.style.left = `${position.x}px`;
        element.style.top = `${position.y}px`;
        
        // Remover endpoints antigos antes de re-renderizar
        this.instance.removeAllEndpoints(element);
        
        // Re-renderizar conteúdo do step seguindo hierarquia: Header → Mídia → URL → Texto → Botões → Ações → Outputs
        const stepType = step.type || 'message';
        const stepConfig = step.config || {};
        const icon = this.stepIcons[stepType] || 'fa-circle';
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // Preparar conteúdo conforme hierarquia
        const mediaUrl = stepConfig.media_url || '';
        const hasMedia = !!mediaUrl;
        const previewText = this.getStepPreview(step);
        
        // Renderizar mídia (se houver) - com thumbnail real
        let mediaHTML = '';
        if (hasMedia) {
            const mediaType = stepConfig.media_type || 'video';
            const mediaIcon = mediaType === 'video' ? 'fa-video' : 'fa-image';
            
            if (mediaType === 'photo' || mediaType === 'image') {
                mediaHTML = `
                    <div class="flow-step-media-preview">
                        <img src="${this.escapeHtml(mediaUrl)}" 
                             alt="Preview" 
                             class="flow-step-media-thumbnail"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                             loading="lazy" />
                        <div class="flow-step-media-fallback" style="display: none;">
                            <i class="fas ${mediaIcon}"></i>
                            <span>Foto</span>
                        </div>
                    </div>
                `;
            } else {
                mediaHTML = `
                    <div class="flow-step-media-preview flow-step-video-preview">
                        <div class="flow-step-video-thumbnail-container">
                            <img src="${this.escapeHtml(mediaUrl)}" 
                                 alt="Video thumbnail" 
                                 class="flow-step-video-thumbnail"
                                 onerror="this.style.display='none';"
                                 loading="lazy" />
                            <div class="flow-step-video-overlay">
                                <i class="fas fa-play-circle"></i>
                            </div>
                        </div>
                    </div>
                `;
            }
        }
        
        // Renderizar botões no body (dentro do próprio botão conforme especificação)
        let buttonsHTML = '';
        if (hasButtons) {
            buttonsHTML = '<div class="flow-step-buttons-container">';
            customButtons.forEach((btn, index) => {
                const btnText = btn.text || `Botão ${index + 1}`;
                buttonsHTML += `
                    <div class="flow-step-button-item" data-button-index="${index}" data-button-id="${btn.id || `btn-${index}`}">
                        <span class="flow-step-button-text">${this.escapeHtml(btnText)}</span>
                        <div class="flow-step-button-endpoint-container" data-endpoint-button="${index}"></div>
                    </div>
                `;
            });
            buttonsHTML += '</div>';
        }
        
        // Atualizar HTML seguindo hierarquia EXATA
        const headerEl = element.querySelector('.flow-step-header');
        const bodyEl = element.querySelector('.flow-step-body');
        
        if (headerEl) {
            const headerContent = headerEl.querySelector('.flow-step-header-content');
            if (headerContent) {
                headerContent.innerHTML = `
                    <div class="flow-step-icon-center">
                        <i class="fas ${icon}" style="color: #FFFFFF;"></i>
                    </div>
                    <div class="flow-step-title-center">
                        ${this.getStepTypeLabel(stepType)}
                    </div>
                    ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
                `;
            }
        }
        
        if (bodyEl) {
            // Ordem visual intuitiva: Mídia → Texto → Botões
            bodyEl.innerHTML = `
                ${mediaHTML}
                ${previewText ? `<div class="flow-step-preview">${previewText}</div>` : ''}
                ${buttonsHTML}
            `;
        }
        
        // Adicionar ou remover container de saída global (deve desaparecer se botões forem adicionados)
        let globalOutputContainer = element.querySelector('.flow-step-global-output-container');
        if (!hasButtons) {
            // Sem botões: criar container de saída global se não existir
            if (!globalOutputContainer) {
                globalOutputContainer = document.createElement('div');
                globalOutputContainer.className = 'flow-step-global-output-container';
                element.appendChild(globalOutputContainer);
            }
        } else {
            // Com botões: remover container de saída global (deve desaparecer)
            if (globalOutputContainer) {
                // Remover endpoints do container antes de remover o container
                try {
                    const endpoints = this.instance.getEndpoints(globalOutputContainer);
                    endpoints.forEach(ep => {
                        try {
                            this.instance.deleteEndpoint(ep);
                        } catch (e) {
                            // Ignorar erros
                        }
                    });
                } catch (e) {
                    // Ignorar erros
                }
                globalOutputContainer.remove();
            }
        }
        
        // Re-adicionar endpoints (atualiza automaticamente conforme botões)
        this.addEndpoints(element, stepId, step);
        
        // Atualizar classe de step inicial
        if (isStartStep) {
            element.classList.add('flow-step-initial');
        } else {
            element.classList.remove('flow-step-initial');
        }
        
        // Reconectar após atualização
        setTimeout(() => {
            this.reconnectAll();
        }, 50);
    }
    
    /**
     * Adiciona endpoints ao step conforme especificação EXATA
     * 
     * ESPECIFICAÇÃO:
     * 1. INPUT: Topo-central do container ROOT (nunca em subcomponents)
     * 2. SAÍDAS COM BOTÕES: Um endpoint por botão, lado direito, dentro do próprio botão
     * 3. SAÍDA SEM BOTÕES: Uma saída global centro-direita (desaparece se botões forem adicionados)
     */
    addEndpoints(element, stepId, step) {
        const stepConfig = step.config || {};
        const customButtons = stepConfig.custom_buttons || [];
        const hasButtons = customButtons.length > 0;
        
        // ============================================
        // 1. ENTRADA (INPUT) - Topo-central do container ROOT
        // ============================================
        // IMPORTANTE: Endpoint no elemento ROOT (stepElement), nunca em subcomponents
        this.instance.addEndpoint(element, {
            uuid: `endpoint-top-${stepId}`,
            anchor: ['TopCenter', { dy: -5 }],
            maxConnections: -1,
            isSource: false,
            isTarget: true,
            endpoint: ['Dot', { radius: 7 }],
            paintStyle: { 
                fill: '#FFFFFF', 
                outlineStroke: '#0D0F15', 
                outlineWidth: 2,
                strokeWidth: 2
            },
            hoverPaintStyle: { 
                fill: '#FFFFFF', 
                outlineStroke: '#0D0F15', 
                outlineWidth: 3,
                strokeWidth: 3
            },
            data: {
                stepId: stepId,
                endpointType: 'input'
            }
        });
        
        // ============================================
        // 2. SAÍDAS COM BOTÕES - Endpoint individual por botão
        // ============================================
        if (hasButtons) {
            // Remover output global se existir (deve desaparecer quando há botões)
            const globalOutputContainer = element.querySelector('.flow-step-global-output-container');
            if (globalOutputContainer) {
                // Remover endpoint do container global se existir
                const globalEndpoint = this.instance.getEndpoints(globalOutputContainer);
                globalEndpoint.forEach(ep => {
                    try {
                        this.instance.deleteEndpoint(ep);
                    } catch (e) {
                        // Ignorar erros
                    }
                });
                globalOutputContainer.remove();
            }
            
            // Criar endpoint para cada botão (lado direito, dentro do próprio botão)
            customButtons.forEach((btn, index) => {
                const buttonContainer = element.querySelector(`[data-endpoint-button="${index}"]`);
                if (buttonContainer) {
                    // Endpoint no container do botão (lado direito, verticalmente centralizado)
                    this.instance.addEndpoint(buttonContainer, {
                        uuid: `endpoint-button-${stepId}-${index}`,
                        anchor: ['Right', { dx: 5 }],
                        maxConnections: 1,
                        isSource: true,
                        isTarget: false,
                        endpoint: ['Dot', { radius: 6 }],
                        paintStyle: { 
                            fill: '#FFFFFF', 
                            outlineStroke: '#0D0F15', 
                            outlineWidth: 2,
                            strokeWidth: 2
                        },
                        hoverPaintStyle: { 
                            fill: '#FFFFFF', 
                            outlineStroke: '#0D0F15', 
                            outlineWidth: 3,
                            strokeWidth: 3
                        },
                        data: {
                            stepId: stepId,
                            buttonIndex: index,
                            buttonId: btn.id || `btn-${index}`,
                            endpointType: 'button'
                        }
                    });
                }
            });
        } else {
            // ============================================
            // 3. SAÍDA SEM BOTÕES - Endpoint global centro-direita
            // ============================================
            // Garantir que o container existe
            let globalOutputContainer = element.querySelector('.flow-step-global-output-container');
            if (!globalOutputContainer) {
                globalOutputContainer = document.createElement('div');
                globalOutputContainer.className = 'flow-step-global-output-container';
                element.appendChild(globalOutputContainer);
            }
            
            // Criar endpoint no centro-direita (alinhado verticalmente com o meio do card)
            this.instance.addEndpoint(globalOutputContainer, {
                uuid: `endpoint-bottom-${stepId}`,
                anchor: ['Right', { dx: 5 }],
                maxConnections: -1,
                isSource: true,
                isTarget: false,
                endpoint: ['Dot', { radius: 7 }],
                paintStyle: { 
                    fill: '#FFFFFF', 
                    outlineStroke: '#0D0F15', 
                    outlineWidth: 2,
                    strokeWidth: 2
                },
                hoverPaintStyle: { 
                    fill: '#FFFFFF', 
                    outlineStroke: '#0D0F15', 
                    outlineWidth: 3,
                    strokeWidth: 3
                },
                data: {
                    stepId: stepId,
                    endpointType: 'global'
                }
            });
        }
    }
    
    /**
     * Reconecta todas as conexões
     */
    reconnectAll() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
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
            
            // Se tem botões, conectar pelos endpoints dos botões
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
                // Sem botões, usar conexões padrão (next, pending, retry)
                if (connections.next) {
                    const targetId = String(connections.next);
                    if (this.steps.has(targetId)) {
                        this.createConnection(stepId, targetId, 'next');
                    }
                }
                
                if (connections.pending) {
                    const targetId = String(connections.pending);
                    if (this.steps.has(targetId)) {
                        this.createConnection(stepId, targetId, 'pending');
                    }
                }
                
                if (connections.retry) {
                    const targetId = String(connections.retry);
                    if (this.steps.has(targetId)) {
                        this.createConnection(stepId, targetId, 'retry');
                    }
                }
            }
        });
    }
    
    /**
     * Cria uma conexão entre dois steps (branca com glow)
     * Usado para steps SEM botões (conexão global)
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
        
        const label = this.getConnectionLabel(connectionType);
        
        try {
            const connection = this.instance.connect({
                source: `endpoint-bottom-${sourceId}`,
                target: `endpoint-top-${targetId}`,
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
                        label: label,
                        location: 0.5,
                        cssClass: 'connection-label-white',
                        labelStyle: {
                            color: '#FFFFFF',
                            backgroundColor: '#0D0F15',
                            border: '1px solid #242836',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            fontSize: '10px',
                            fontWeight: '600',
                            fontFamily: 'Inter, sans-serif'
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
                
                // Adicionar animação de highlight
                setTimeout(() => {
                    if (this.instance) {
                        this.instance.repaint(connection);
                    }
                }, 10);
                
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceId);
                if (step && (!step.connections || !step.connections[connectionType])) {
                    this.updateAlpineConnection(sourceId, targetId, connectionType);
                }
            }
            
            return connection;
        } catch (error) {
            console.error(`❌ Erro ao criar conexão:`, error);
            return null;
        }
    }
    
    /**
     * Cria uma conexão a partir de um botão específico
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
                target: `endpoint-top-${targetId}`,
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
                            fontWeight: '600',
                            fontFamily: 'Inter, sans-serif'
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
                
                // Adicionar animação de highlight
                setTimeout(() => {
                    if (this.instance) {
                        this.instance.repaint(connection);
                    }
                }, 10);
            }
            
            return connection;
        } catch (error) {
            console.error(`❌ Erro ao criar conexão do botão:`, error);
            return null;
        }
    }
    
    /**
     * Atualiza conexão no Alpine.js
     */
    updateAlpineConnection(sourceStepId, targetStepId, connectionType) {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        const steps = this.alpine.config.flow_steps;
        const sourceStep = steps.find(s => String(s.id) === String(sourceStepId));
        
        if (sourceStep) {
            if (!sourceStep.connections) {
                sourceStep.connections = {};
            }
            sourceStep.connections[connectionType] = String(targetStepId);
        }
    }
    
    /**
     * Remove uma conexão
     */
    removeConnection(connection) {
        if (!connection) return;
        
        const data = connection.getData();
        if (data) {
            const { sourceStepId, targetStepId, connectionType, buttonIndex } = data;
            
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const sourceStep = steps.find(s => String(s.id) === String(sourceStepId));
                
                if (sourceStep) {
                    // Se for conexão de botão, limpar target_step do botão
                    if (connectionType === 'button' && buttonIndex !== null && buttonIndex !== undefined) {
                        if (sourceStep.config && sourceStep.config.custom_buttons && sourceStep.config.custom_buttons[buttonIndex]) {
                            sourceStep.config.custom_buttons[buttonIndex].target_step = null;
                        }
                    } else if (sourceStep.connections) {
                        // Se for conexão padrão, remover do objeto connections
                        delete sourceStep.connections[connectionType];
                    }
                }
            }
            
            const connId = connectionType === 'button' && buttonIndex !== null && buttonIndex !== undefined
                ? `button-${sourceStepId}-${buttonIndex}-${targetStepId}`
                : `${sourceStepId}-${targetStepId}-${connectionType}`;
            this.connections.delete(connId);
        }
        
        this.instance.deleteConnection(connection);
    }
    
    /**
     * Callback quando conexão é criada
     * Identifica qual botão criou a conexão e atualiza Alpine.js corretamente
     */
    onConnectionCreated(info) {
        const sourceUuid = info.sourceId || info.source?.getUuid?.();
        const targetUuid = info.targetId || info.target?.getUuid?.();
        
        if (!sourceUuid || !targetUuid) return;
        
        // Detectar tipo de endpoint de origem conforme especificação
        let sourceStepId = null;
        let buttonIndex = null;
        let connectionType = 'next';
        
        // Extrair stepId e buttonIndex do UUID
        if (sourceUuid.includes('endpoint-button-')) {
            // Conexão de botão: endpoint-button-{stepId}-{buttonIndex}
            const match = sourceUuid.match(/endpoint-button-([^-]+)-(\d+)/);
            if (match) {
                sourceStepId = match[1];
                buttonIndex = parseInt(match[2]);
                connectionType = 'button';
            }
        } else if (sourceUuid.includes('endpoint-bottom-')) {
            // Conexão global (sem botões): endpoint-bottom-{stepId}
            sourceStepId = sourceUuid.replace('endpoint-bottom-', '');
            connectionType = 'next'; // Default para conexões globais
        }
        
        const targetStepId = targetUuid.includes('endpoint-top-') 
            ? targetUuid.replace('endpoint-top-', '') 
            : null;
        
        if (!sourceStepId || !targetStepId) return;
        
        // Atualizar Alpine.js conforme tipo de conexão
        if (connectionType === 'button' && buttonIndex !== null && buttonIndex !== undefined) {
            // Conexão de botão: atualizar target_step do botão específico
            const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceStepId);
            if (step && step.config && step.config.custom_buttons && step.config.custom_buttons[buttonIndex]) {
                step.config.custom_buttons[buttonIndex].target_step = targetStepId;
            }
        } else {
            // Conexão global: atualizar connections do step
            this.updateAlpineConnection(sourceStepId, targetStepId, connectionType);
        }
        
        if (info.connection) {
            const label = connectionType === 'button' ? 'Botão' : this.getConnectionLabel(connectionType);
            
            info.connection.setPaintStyle({ 
                stroke: '#FFFFFF', 
                strokeWidth: 2.5,
                strokeOpacity: 0.9
            });
            info.connection.setHoverPaintStyle({ 
                stroke: '#FFFFFF', 
                strokeWidth: 3.5,
                strokeOpacity: 1
            });
            
            info.connection.setLabel({
                label: label,
                location: 0.5,
                cssClass: 'connection-label-white',
                labelStyle: {
                    color: '#FFFFFF',
                    backgroundColor: '#0D0F15',
                    border: '1px solid #242836',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    fontSize: '10px',
                    fontWeight: '600',
                    fontFamily: 'Inter, sans-serif'
                }
            });
            
            // Salvar dados da conexão incluindo identificação do botão
            info.connection.setData({
                sourceStepId: sourceStepId,
                targetStepId: targetStepId,
                buttonIndex: buttonIndex,
                connectionType: connectionType
            });
            
            const connId = connectionType === 'button' && buttonIndex !== null && buttonIndex !== undefined
                ? `button-${sourceStepId}-${buttonIndex}-${targetStepId}`
                : `${sourceStepId}-${targetStepId}-${connectionType}`;
            this.connections.set(connId, info.connection);
            
            // Repintar para garantir visibilidade
            setTimeout(() => {
                if (this.instance) {
                    this.instance.repaint(info.connection);
                }
            }, 10);
        }
    }
    
    /**
     * Callback quando conexão é removida
     */
    onConnectionDetached(info) {
        // Já tratado em removeConnection
    }
    
    /**
     * Callback quando step é arrastado - com snapping inteligente
     */
    onStepDrag(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.add('dragging');
            
            // Aplicar snapping se habilitado
            if (this.snapEnabled) {
                this.applySnapping(element, params);
            }
        }
    }
    
    /**
     * Aplica snapping magnético ao elemento sendo arrastado
     */
    applySnapping(element, params) {
        if (!this.snapEnabled) return;
        
        const elementRect = element.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();
        
        const elementX = elementRect.left - canvasRect.left;
        const elementY = elementRect.top - canvasRect.top;
        const elementCenterX = elementX + elementRect.width / 2;
        const elementCenterY = elementY + elementRect.height / 2;
        
        let snapX = null, snapY = null;
        let snapLines = { horizontal: [], vertical: [] };
        
        // Verificar snapping com outros steps
        this.steps.forEach((otherElement, otherStepId) => {
            if (otherElement === element) return;
            
            const otherRect = otherElement.getBoundingClientRect();
            const otherX = otherRect.left - canvasRect.left;
            const otherY = otherRect.top - canvasRect.top;
            const otherCenterX = otherX + otherRect.width / 2;
            const otherCenterY = otherY + otherRect.height / 2;
            
            // Snapping horizontal (alinhar centros ou bordas)
            const centerXDiff = Math.abs(elementCenterX - otherCenterX);
            if (centerXDiff < this.snapThreshold) {
                snapX = otherCenterX - elementRect.width / 2;
                snapLines.vertical.push({
                    x: otherCenterX,
                    y1: Math.min(elementY, otherY) - 20,
                    y2: Math.max(elementY + elementRect.height, otherY + otherRect.height) + 20
                });
            }
            
            // Snapping vertical (alinhar centros ou bordas)
            const centerYDiff = Math.abs(elementCenterY - otherCenterY);
            if (centerYDiff < this.snapThreshold) {
                snapY = otherCenterY - elementRect.height / 2;
                snapLines.horizontal.push({
                    y: otherCenterY,
                    x1: Math.min(elementX, otherX) - 20,
                    x2: Math.max(elementX + elementRect.width, otherX + otherRect.width) + 20
                });
            }
            
            // Snapping de bordas
            const leftDiff = Math.abs(elementX - otherX);
            const rightDiff = Math.abs((elementX + elementRect.width) - (otherX + otherRect.width));
            const topDiff = Math.abs(elementY - otherY);
            const bottomDiff = Math.abs((elementY + elementRect.height) - (otherY + otherRect.height));
            
            if (leftDiff < this.snapThreshold) {
                snapX = otherX;
                snapLines.vertical.push({
                    x: otherX,
                    y1: Math.min(elementY, otherY) - 20,
                    y2: Math.max(elementY + elementRect.height, otherY + otherRect.height) + 20
                });
            } else if (rightDiff < this.snapThreshold) {
                snapX = otherX + otherRect.width - elementRect.width;
                snapLines.vertical.push({
                    x: otherX + otherRect.width,
                    y1: Math.min(elementY, otherY) - 20,
                    y2: Math.max(elementY + elementRect.height, otherY + otherRect.height) + 20
                });
            }
            
            if (topDiff < this.snapThreshold) {
                snapY = otherY;
                snapLines.horizontal.push({
                    y: otherY,
                    x1: Math.min(elementX, otherX) - 20,
                    x2: Math.max(elementX + elementRect.width, otherX + otherRect.width) + 20
                });
            } else if (bottomDiff < this.snapThreshold) {
                snapY = otherY + otherRect.height - elementRect.height;
                snapLines.horizontal.push({
                    y: otherY + otherRect.height,
                    x1: Math.min(elementX, otherX) - 20,
                    x2: Math.max(elementX + elementRect.width, otherX + otherRect.width) + 20
                });
            }
        });
        
        // Aplicar snap
        if (snapX !== null || snapY !== null) {
            const currentLeft = parseFloat(element.style.left) || 0;
            const currentTop = parseFloat(element.style.top) || 0;
            
            // Converter coordenadas de tela para coordenadas do canvas (considerando zoom/pan)
            if (snapX !== null) {
                const worldX = (snapX - this.pan.x) / this.zoomLevel;
                element.style.left = `${worldX}px`;
            }
            
            if (snapY !== null) {
                const worldY = (snapY - this.pan.y) / this.zoomLevel;
                element.style.top = `${worldY}px`;
            }
        }
        
        // Mostrar linhas-guia
        this.showSnapLines = snapLines.horizontal.length > 0 || snapLines.vertical.length > 0;
        this.snapLines = snapLines;
        this.renderSnapLines();
    }
    
    /**
     * Renderiza linhas-guia de snapping
     */
    renderSnapLines() {
        // Remover linhas antigas
        const oldLines = this.canvas.querySelectorAll('.snap-line');
        oldLines.forEach(line => line.remove());
        
        if (!this.showSnapLines) return;
        
        // Criar linhas-guia
        this.snapLines.horizontal.forEach(line => {
            const lineEl = document.createElement('div');
            lineEl.className = 'snap-line snap-line-horizontal';
            lineEl.style.cssText = `
                position: absolute;
                left: ${line.x1}px;
                top: ${line.y}px;
                width: ${line.x2 - line.x1}px;
                height: 1px;
                background: #FFB800;
                opacity: 0.6;
                pointer-events: none;
                z-index: 9999;
            `;
            this.canvas.appendChild(lineEl);
        });
        
        this.snapLines.vertical.forEach(line => {
            const lineEl = document.createElement('div');
            lineEl.className = 'snap-line snap-line-vertical';
            lineEl.style.cssText = `
                position: absolute;
                left: ${line.x}px;
                top: ${line.y1}px;
                width: 1px;
                height: ${line.y2 - line.y1}px;
                background: #FFB800;
                opacity: 0.6;
                pointer-events: none;
                z-index: 9999;
            `;
            this.canvas.appendChild(lineEl);
        });
    }
    
    /**
     * Callback quando drag para - limpar linhas-guia
     */
    onStepDragStop(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.remove('dragging');
            
            // Remover linhas-guia
            this.showSnapLines = false;
            const snapLines = this.canvas.querySelectorAll('.snap-line');
            snapLines.forEach(line => line.remove());
            
            const rect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            let x = rect.left - canvasRect.left;
            let y = rect.top - canvasRect.top;
            
            // Ajustar para zoom e pan
            x = (x - this.pan.x) / this.zoomLevel;
            y = (y - this.pan.y) / this.zoomLevel;
            
            // Snap to grid se habilitado
            if (this.snapToGrid) {
                x = Math.round(x / this.gridSize) * this.gridSize;
                y = Math.round(y / this.gridSize) * this.gridSize;
            }
            
            const position = { x: Math.round(x), y: Math.round(y) };
            this.updateStepPosition(stepId, position);
            
            // Expandir bounds do canvas
            this.expandCanvasBounds();
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
     * Remove um step
     */
    deleteStep(stepId) {
        if (!confirm('Tem certeza que deseja remover este step?')) {
            return;
        }
        
        const id = String(stepId);
        const element = this.steps.get(id);
        
        if (element) {
            const connectionsToRemove = [];
            this.connections.forEach((conn) => {
                const data = conn.getData();
                if (data && (data.sourceStepId === id || data.targetStepId === id)) {
                    connectionsToRemove.push(conn);
                }
            });
            
            connectionsToRemove.forEach(conn => {
                this.removeConnection(conn);
            });
            
            this.instance.remove(element);
            element.remove();
            this.steps.delete(id);
            
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const index = steps.findIndex(s => String(s.id) === id);
                if (index !== -1) {
                    steps.splice(index, 1);
                }
                
                if (this.alpine.config.flow_start_step_id === id) {
                    this.alpine.config.flow_start_step_id = null;
                }
            }
        }
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
     * Limpa o canvas
     */
    clearCanvas() {
        this.steps.forEach((element) => {
            this.instance.remove(element);
            element.remove();
        });
        this.steps.clear();
        this.connections.clear();
    }
    
    /**
     * Atualiza endpoints de um step após mudanças (adicionar/remover botões)
     * Conforme especificação: atualizar automaticamente ao mover/adicionar/excluir/editar botões
     */
    updateStepEndpoints(stepId) {
        const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === String(stepId));
        if (!step) return;
        
        const element = this.steps.get(String(stepId));
        if (!element) return;
        
        // Remover todos os endpoints do step
        this.instance.removeAllEndpoints(element);
        
        // Re-adicionar endpoints conforme estado atual
        this.addEndpoints(element, String(stepId), step);
        
        // Reconectar após atualização
        setTimeout(() => {
            this.reconnectAll();
        }, 50);
    }
    
    /**
     * Revalida todas as conexões (chamado após mudanças nos steps)
     */
    revalidateConnections() {
        this.reconnectAll();
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
            // Mostrar 2-4 linhas (aproximadamente 100-200 caracteres)
            const maxLength = 150;
            if (text.length <= maxLength) {
                return text;
            }
            // Quebrar em linhas inteligentes
            const truncated = text.substring(0, maxLength);
            const lastSpace = truncated.lastIndexOf(' ');
            return (lastSpace > 0 ? truncated.substring(0, lastSpace) : truncated) + '...';
        } else if (type === 'payment') {
            const price = config.price || '';
            const productName = config.product_name || '';
            const buttonText = config.button_text || '';
            if (price && productName) {
                return `${productName} - R$ ${price}`;
            }
            return price ? `R$ ${price}` : 'Pagamento';
        } else if (type === 'access') {
            return config.message || config.access_link || 'Acesso liberado';
        }
        
        return this.getStepTypeLabel(type);
    }
    
    getConnectionLabel(type) {
        const labels = {
            next: 'Próximo',
            pending: 'Pendente',
            retry: 'Retry'
        };
        return labels[type] || type;
    }
    
    /**
     * Escapa HTML para prevenir XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Organiza steps verticalmente
     */
    organizeVertical() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        // Ordenar por posição atual
        const sortedSteps = [...steps].sort((a, b) => {
            const posA = a.position || { x: 0, y: 0 };
            const posB = b.position || { x: 0, y: 0 };
            if (Math.abs(posA.x - posB.x) < 100) {
                return posA.y - posB.y;
            }
            return posA.x - posB.x;
        });
        
        let currentY = 100;
        sortedSteps.forEach((step) => {
            const currentX = step.position?.x || 100;
            step.position = { x: currentX, y: currentY };
            currentY += this.layoutSpacing.y;
            
            const element = this.steps.get(String(step.id));
            if (element) {
                element.style.left = `${currentX}px`;
                element.style.top = `${currentY}px`;
            }
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.expandCanvasBounds();
        }, 50);
    }
    
    /**
     * Organiza steps horizontalmente
     */
    organizeHorizontal() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        const sortedSteps = [...steps].sort((a, b) => {
            const posA = a.position || { x: 0, y: 0 };
            const posB = b.position || { x: 0, y: 0 };
            if (Math.abs(posA.y - posB.y) < 100) {
                return posA.x - posB.x;
            }
            return posA.y - posB.y;
        });
        
        let currentX = 100;
        sortedSteps.forEach((step) => {
            const currentY = step.position?.y || 100;
            step.position = { x: currentX, y: currentY };
            currentX += this.layoutSpacing.x;
            
            const element = this.steps.get(String(step.id));
            if (element) {
                element.style.left = `${currentX}px`;
                element.style.top = `${currentY}px`;
            }
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.expandCanvasBounds();
        }, 50);
    }
    
    /**
     * Organiza fluxo completo (hierárquico baseado em conexões)
     */
    organizeFlowComplete() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        const startStepId = this.alpine.config.flow_start_step_id;
        if (!startStepId) {
            this.organizeVertical();
            return;
        }
        
        const graph = new Map();
        const visited = new Set();
        const positions = new Map();
        
        steps.forEach(step => {
            graph.set(String(step.id), []);
        });
        
        steps.forEach(step => {
            const stepId = String(step.id);
            const connections = step.connections || {};
            const customButtons = step.config?.custom_buttons || [];
            
            if (connections.next) {
                graph.get(stepId).push(String(connections.next));
            }
            if (connections.pending) {
                graph.get(stepId).push(String(connections.pending));
            }
            if (connections.retry) {
                graph.get(stepId).push(String(connections.retry));
            }
            
            customButtons.forEach(btn => {
                if (btn.target_step) {
                    graph.get(stepId).push(String(btn.target_step));
                }
            });
        });
        
        const queue = [{ id: String(startStepId), x: 100, y: 100, level: 0 }];
        const levelWidths = new Map();
        
        while (queue.length > 0) {
            const current = queue.shift();
            const currentId = current.id;
            
            if (visited.has(currentId)) continue;
            visited.add(currentId);
            
            positions.set(currentId, { x: current.x, y: current.y });
            
            const children = graph.get(currentId) || [];
            const level = current.level + 1;
            
            if (!levelWidths.has(level)) {
                levelWidths.set(level, 0);
            }
            
            let childX = 100;
            let childY = current.y + this.layoutSpacing.y;
            
            children.forEach((childId) => {
                if (!visited.has(childId)) {
                    const width = levelWidths.get(level);
                    childX = 100 + width * this.layoutSpacing.x;
                    levelWidths.set(level, width + 1);
                    
                    queue.push({ id: childId, x: childX, y: childY, level: level });
                }
            });
        }
        
        positions.forEach((pos, stepId) => {
            const step = steps.find(s => String(s.id) === stepId);
            if (step) {
                step.position = pos;
                const element = this.steps.get(stepId);
                if (element) {
                    element.style.left = `${pos.x}px`;
                    element.style.top = `${pos.y}px`;
                }
            }
        });
        
        steps.forEach(step => {
            if (!positions.has(String(step.id))) {
                const x = 100 + (positions.size * this.layoutSpacing.x);
                const y = 100;
                step.position = { x, y };
                const element = this.steps.get(String(step.id));
                if (element) {
                    element.style.left = `${x}px`;
                    element.style.top = `${y}px`;
                }
            }
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.expandCanvasBounds();
            this.zoomToFit();
        }, 50);
    }
    
    /**
     * Organiza steps por grupos
     */
    organizeByGroups() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) return;
        
        const steps = this.alpine.config.flow_steps;
        if (steps.length === 0) return;
        
        const groups = [];
        const assigned = new Set();
        
        steps.forEach(step => {
            if (assigned.has(String(step.id))) return;
            
            const group = [step];
            assigned.add(String(step.id));
            const posA = step.position || { x: 0, y: 0 };
            
            steps.forEach(otherStep => {
                if (assigned.has(String(otherStep.id))) return;
                
                const posB = otherStep.position || { x: 0, y: 0 };
                const distance = Math.hypot(posB.x - posA.x, posB.y - posA.y);
                
                if (distance < 300) {
                    group.push(otherStep);
                    assigned.add(String(otherStep.id));
                }
            });
            
            groups.push(group);
        });
        
        let groupStartY = 100;
        groups.forEach((group, groupIndex) => {
            let currentY = groupStartY;
            
            group.forEach((step) => {
                const x = 100 + groupIndex * (this.layoutSpacing.x * 2);
                step.position = { x, y: currentY };
                currentY += this.layoutSpacing.y;
                
                const element = this.steps.get(String(step.id));
                if (element) {
                    element.style.left = `${x}px`;
                    element.style.top = `${currentY}px`;
                }
            });
            
            groupStartY = currentY + 100;
        });
        
        setTimeout(() => {
            this.reconnectAll();
            this.expandCanvasBounds();
        }, 50);
    }
    
    /**
     * Destruir instância
     */
    destroy() {
        // Limpar linhas-guia
        if (this.canvas) {
            const snapLines = this.canvas.querySelectorAll('.snap-line');
            snapLines.forEach(line => line.remove());
        }
        
        // Cancelar animações
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        
        this.clearCanvas();
        if (this.instance) {
            try {
                this.instance.destroy();
            } catch (e) {
                // Ignorar erros de destroy
            }
            this.instance = null;
        }
    }
}

// Exportar para uso global
window.FlowEditor = FlowEditor;
