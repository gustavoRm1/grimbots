/**
 * Flow Editor V2.0 - Editor Visual de Fluxo com jsPlumb
 * Sistema completo de edição visual de fluxos de bot
 * Versão: 2.0.0 - Visual Dashboard + jsPlumb 2.x Compatible
 * 
 * Dependências:
 * - jsPlumb 2.15.6 (CDN)
 * - Alpine.js 3.x (CDN)
 * 
 * Design System:
 * - Background: #0D0F15
 * - Cards: #15171F
 * - Borda: #242836
 * - Linhas: #1f232e
 * - Títulos: #FFFFFF
 * - Textos: #A1A1A9
 * - Amarelo: #FFB800 / #FFC633
 * - Verde: #10B981
 * - Azul: #3B82F6
 * - Vermelho: #EF4444
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
        this.zoomLevel = 1;
        this.pan = { x: 0, y: 0 };
        this.isPanning = false;
        this.lastPanPoint = { x: 0, y: 0 };
        this.snapToGrid = false;
        this.gridSize = 20;
        
        // Cores por tipo de conexão (White with Glow Style)
        this.connectionColors = {
            next: '#FFFFFF',      // Branco
            pending: '#FFFFFF',   // Branco
            retry: '#FFFFFF'      // Branco
        };
        
        // Cores por tipo de step (Dashboard Style)
        this.stepColors = {
            content: '#3B82F6',   // Azul
            message: '#8B5CF6',    // Roxo
            audio: '#EC4899',      // Rosa
            video: '#F59E0B',      // Amarelo
            buttons: '#10B981',    // Verde
            payment: '#EF4444',    // Vermelho
            access: '#14B8A6'      // Ciano
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
        
        // Inicializar jsPlumb 2.x (API correta)
        try {
            this.instance = jsPlumb;
            
            // Configurar container
            if (typeof this.instance.setContainer === 'function') {
                this.instance.setContainer(this.canvas);
            }
            
            // Configurar defaults (White Connections with Glow)
            if (typeof this.instance.importDefaults === 'function') {
                this.instance.importDefaults({
                    paintStyle: { 
                        stroke: '#FFFFFF', 
                        strokeWidth: 2,
                        strokeDasharray: '0',
                        filter: 'drop-shadow(0 0 2px rgba(255, 255, 255, 0.5))'
                    },
                    hoverPaintStyle: { 
                        stroke: '#FFFFFF', 
                        strokeWidth: 3,
                        filter: 'drop-shadow(0 0 4px rgba(255, 255, 255, 0.8))'
                    },
                    connector: ['Bezier', { curviness: 70, stub: [10, 15], gap: 5, cornerRadius: 5 }],
                    endpoint: ['Dot', { radius: 6 }],
                    endpointStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 2 },
                    endpointHoverStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 3 },
                    anchors: ['Top', 'Bottom'],
                    maxConnections: -1
                });
            }
            
            // Bind eventos
            setTimeout(() => {
                this.instance.bind('connection', (info) => this.onConnectionCreated(info));
                this.instance.bind('connectionDetached', (info) => this.onConnectionDetached(info));
                
                // Remover conexão com duplo clique
                this.instance.bind('click', (conn, originalEvent) => {
                    if (originalEvent && originalEvent.detail === 2) {
                        this.removeConnection(conn);
                    }
                });
                
                // Remover conexão com botão direito
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
        
        // Configurar canvas
        this.setupCanvas();
        
        // Renderizar steps existentes
        this.renderAllSteps();
        
        // Habilitar interações
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
    }
    
    /**
     * Configura o canvas com grid background (pontos translúcidos)
     */
    setupCanvas() {
        if (!this.canvas) return;
        
        // Aplicar estilo do canvas com pontos translúcidos
        this.canvas.style.background = '#0D0F15';
        // Grid com pontos brancos translúcidos (usando radial-gradient)
        this.canvas.style.backgroundImage = `
            radial-gradient(circle, rgba(255, 255, 255, 0.15) 1px, transparent 1px)
        `;
        this.canvas.style.backgroundSize = `${this.gridSize}px ${this.gridSize}px`;
        this.canvas.style.backgroundPosition = '0 0';
    }
    
    /**
     * Habilita zoom com scroll
     */
    enableZoom() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('wheel', (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                this.zoomLevel = Math.max(0.5, Math.min(2, this.zoomLevel * delta));
                this.applyZoom();
            }
        }, { passive: false });
    }
    
    /**
     * Aplica zoom ao canvas
     */
    applyZoom() {
        if (!this.canvas) return;
        
        this.canvas.style.transform = `scale(${this.zoomLevel})`;
        this.canvas.style.transformOrigin = 'top left';
        
        setTimeout(() => {
            if (this.instance) {
                this.instance.repaintEverything();
            }
        }, 10);
    }
    
    /**
     * Zoom in
     */
    zoomIn() {
        this.zoomLevel = Math.min(2, this.zoomLevel * 1.2);
        this.applyZoom();
    }
    
    /**
     * Zoom out
     */
    zoomOut() {
        this.zoomLevel = Math.max(0.5, this.zoomLevel * 0.8);
        this.applyZoom();
    }
    
    /**
     * Reset zoom
     */
    zoomReset() {
        this.zoomLevel = 1;
        this.applyZoom();
    }
    
    /**
     * Habilita pan (arrastar canvas) - Botão direito
     */
    enablePan() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('mousedown', (e) => {
            // Pan com botão direito (button === 2) ou botão do meio (button === 1)
            if (e.button === 2 || e.button === 1 || (e.button === 0 && e.altKey)) {
                e.preventDefault();
                this.isPanning = true;
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
                this.canvas.style.cursor = 'grabbing';
            }
        });
        
        // Prevenir menu de contexto no botão direito
        this.canvas.addEventListener('contextmenu', (e) => {
            if (e.button === 2) {
                e.preventDefault();
            }
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isPanning) {
                e.preventDefault();
                const dx = e.clientX - this.lastPanPoint.x;
                const dy = e.clientY - this.lastPanPoint.y;
                this.pan.x += dx;
                this.pan.y += dy;
                this.lastPanPoint = { x: e.clientX, y: e.clientY };
                this.updateCanvasTransform();
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            this.isPanning = false;
            this.canvas.style.cursor = 'grab';
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            this.isPanning = false;
            this.canvas.style.cursor = 'grab';
        });
    }
    
    /**
     * Atualiza transform do canvas (zoom + pan)
     */
    updateCanvasTransform() {
        if (!this.canvas) return;
        this.canvas.style.transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoomLevel})`;
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
        
        steps.forEach(step => {
            this.renderStep(step);
        });
        
        this.reconnectAll();
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
        
        const color = this.stepColors[stepType] || '#6B7280';
        const icon = this.stepIcons[stepType] || 'fa-circle';
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        
        // HTML do bloco (Red Header Style - ManyChat/Make.com)
        stepElement.innerHTML = `
            <div class="flow-step-header">
                <div class="flow-step-header-content">
                    <div class="flow-step-icon-center">
                        <i class="fas fa-video" style="color: #FFFFFF;"></i>
                    </div>
                    <div class="flow-step-title-center">
                        ${this.getStepTypeLabel(stepType)}
                    </div>
                    ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
                </div>
            </div>
            <div class="flow-step-body">
                <div class="flow-step-preview">
                    ${this.getStepPreview(step)}
                </div>
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
        `;
        
        this.canvas.appendChild(stepElement);
        
        // Tornar arrastável (Drag suave e fluido)
        this.instance.draggable(stepElement, {
            containment: 'parent',
            grid: this.snapToGrid ? [this.gridSize, this.gridSize] : false,
            drag: (params) => {
                this.onStepDrag(params);
                // Repintar conexões durante o drag para suavidade
                if (this.instance) {
                    this.instance.repaint(params.el);
                }
            },
            stop: (params) => {
                this.onStepDragStop(params);
                // Repintar todas as conexões após parar
                if (this.instance) {
                    this.instance.repaintEverything();
                }
            },
            cursor: 'move',
            zIndex: 1000
        });
        
        // Adicionar endpoints
        this.addEndpoints(stepElement, stepId);
        
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
        
        const previewEl = element.querySelector('.flow-step-preview');
        if (previewEl) {
            previewEl.innerHTML = this.getStepPreview(step);
        }
        
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        if (isStartStep) {
            element.classList.add('flow-step-initial');
        } else {
            element.classList.remove('flow-step-initial');
        }
    }
    
    /**
     * Adiciona endpoints ao step
     */
    addEndpoints(element, stepId) {
        // Endpoint superior (entrada) - Branco
        this.instance.addEndpoint(element, {
            uuid: `endpoint-top-${stepId}`,
            anchor: 'Top',
            maxConnections: -1,
            isSource: false,
            isTarget: true,
            endpoint: ['Dot', { radius: 6 }],
            paintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 2 },
            hoverPaintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 3 }
        });
        
        // Endpoint inferior (saída) - Branco
        this.instance.addEndpoint(element, {
            uuid: `endpoint-bottom-${stepId}`,
            anchor: 'Bottom',
            maxConnections: -1,
            isSource: true,
            isTarget: false,
            endpoint: ['Dot', { radius: 6 }],
            paintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 2 },
            hoverPaintStyle: { fill: '#FFFFFF', outlineStroke: '#0D0F15', outlineWidth: 3 }
        });
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
            const connections = step.connections || {};
            
            if (!this.steps.has(stepId)) return;
            
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
        });
    }
    
    /**
     * Cria uma conexão entre dois steps
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
        
        const color = this.connectionColors[connectionType] || '#FFFFFF';
        const label = this.getConnectionLabel(connectionType);
        
        try {
            const connection = this.instance.connect({
                source: `endpoint-bottom-${sourceId}`,
                target: `endpoint-top-${targetId}`,
                paintStyle: { 
                    stroke: '#FFFFFF', 
                    strokeWidth: 2,
                    filter: 'drop-shadow(0 0 2px rgba(255, 255, 255, 0.5))'
                },
                hoverPaintStyle: { 
                    stroke: '#FFFFFF', 
                    strokeWidth: 3,
                    filter: 'drop-shadow(0 0 4px rgba(255, 255, 255, 0.8))'
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
            const { sourceStepId, targetStepId, connectionType } = data;
            
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const sourceStep = steps.find(s => String(s.id) === String(sourceStepId));
                
                if (sourceStep && sourceStep.connections) {
                    delete sourceStep.connections[connectionType];
                }
            }
            
            const connId = `${sourceStepId}-${targetStepId}-${connectionType}`;
            this.connections.delete(connId);
        }
        
        this.instance.deleteConnection(connection);
    }
    
    /**
     * Callback quando conexão é criada
     */
    onConnectionCreated(info) {
        const sourceUuid = info.sourceId || info.source?.getUuid?.();
        const targetUuid = info.targetId || info.target?.getUuid?.();
        
        const sourceStepId = sourceUuid ? sourceUuid.replace('endpoint-bottom-', '').replace('endpoint-top-', '') : null;
        const targetStepId = targetUuid ? targetUuid.replace('endpoint-bottom-', '').replace('endpoint-top-', '') : null;
        
        if (sourceStepId && targetStepId && sourceUuid?.includes('bottom') && targetUuid?.includes('top')) {
            const connectionType = 'next';
            this.updateAlpineConnection(sourceStepId, targetStepId, connectionType);
            
            if (info.connection) {
                const color = '#FFFFFF';
                const label = this.getConnectionLabel(connectionType);
                
                info.connection.setPaintStyle({ 
                    stroke: color, 
                    strokeWidth: 2,
                    filter: 'drop-shadow(0 0 2px rgba(255, 255, 255, 0.5))'
                });
                info.connection.setHoverPaintStyle({ 
                    stroke: color, 
                    strokeWidth: 3,
                    filter: 'drop-shadow(0 0 4px rgba(255, 255, 255, 0.8))'
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
                
                info.connection.setData({
                    sourceStepId: sourceStepId,
                    targetStepId: targetStepId,
                    connectionType: connectionType
                });
                
                const connId = `${sourceStepId}-${targetStepId}-${connectionType}`;
                this.connections.set(connId, info.connection);
            }
        }
    }
    
    /**
     * Callback quando conexão é removida
     */
    onConnectionDetached(info) {
        // Já tratado em removeConnection
    }
    
    /**
     * Callback quando step é arrastado
     */
    onStepDrag(params) {
        const element = params.el;
        const stepId = element.dataset.stepId;
        
        if (stepId) {
            element.classList.add('dragging');
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
            
            const rect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            let x = rect.left - canvasRect.left;
            let y = rect.top - canvasRect.top;
            
            // Snap to grid se habilitado
            if (this.snapToGrid) {
                x = Math.round(x / this.gridSize) * this.gridSize;
                y = Math.round(y / this.gridSize) * this.gridSize;
            }
            
            const position = { x: Math.round(x), y: Math.round(y) };
            this.updateStepPosition(stepId, position);
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
            return text.substring(0, 50) + (text.length > 50 ? '...' : '');
        } else if (type === 'payment') {
            const amount = config.amount || '';
            return amount ? `R$ ${amount}` : 'Pagamento';
        } else if (type === 'access') {
            return config.message || 'Acesso liberado';
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
     * Destruir instância
     */
    destroy() {
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
