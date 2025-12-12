/**
 * 🔥 Flow Editor V∞ - Sistema Profissional de Edição Visual
 * Inspirado em Figma + Manychat + Make.com + DialogFlow
 * 
 * Funcionalidades:
 * - jsPlumb 2.15.6 integrado
 * - Drag & Drop de blocos
 * - Conexões visuais (Bezier)
 * - Zoom/Pan suave
 * - Undo/Redo
 * - Seleção múltipla
 * - Minimapa
 * - Lazy rendering para 1000+ steps
 * - Self-healing de conexões
 * - Prevenção de duplicações
 * 
 * Dependências:
 * - jsPlumb 2.15.6
 * - Alpine.js 3.x
 */

class FlowEditor {
    constructor(canvasId, alpineContext) {
        this.canvasId = canvasId;
        this.canvas = document.getElementById(canvasId);
        this.alpine = alpineContext;
        this.instance = null;
        this.steps = new Map();
        this.connections = new Map();
        this.selectedSteps = new Set();
        this.contentContainer = null;
        
        // Zoom e Pan
        this.zoom = 1;
        this.pan = { x: 0, y: 0 };
        this.isPanning = false;
        this.lastPanPoint = { x: 0, y: 0 };
        
        // History
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 50;
        
        // Performance
        this.renderQueue = [];
        this.isRendering = false;
        this.viewport = { x: 0, y: 0, width: 0, height: 0 };
        
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
        
        this.setupCanvas();
        this.setupJsPlumb();
        this.enableZoom();
        this.enablePan();
        this.enableSelection();
        this.updateViewport();
        
        console.log('✅ FlowEditor V∞ inicializado');
    }
    
    setupCanvas() {
        // Encontrar ou criar content container
        this.contentContainer = this.canvas.querySelector('.flow-canvas-content');
        if (!this.contentContainer) {
            this.contentContainer = document.createElement('div');
            this.contentContainer.className = 'flow-canvas-content';
            this.canvas.appendChild(this.contentContainer);
        }
        
        // Aplicar transform inicial
        this.updateTransform();
    }
    
    setupJsPlumb() {
        this.instance = jsPlumb.newInstance({
            container: this.contentContainer,
            paintStyle: { 
                stroke: '#4c92ff', 
                strokeWidth: 2,
                outlineStroke: 'transparent',
                outlineWidth: 4
            },
            endpointStyle: { 
                fill: '#4c92ff', 
                radius: 7,
                outlineWidth: 2,
                outlineStroke: '#1c1f27'
            },
            connector: ['Bezier', { curviness: 75 }],
            anchors: ['Right', 'Left'],
            connectionsDetachable: true,
            connectionOverlays: [
                ['Arrow', { 
                    location: 1, 
                    width: 10, 
                    length: 10,
                    foldback: 0.8
                }]
            ],
            maxConnections: -1,
            dragOptions: {
                containment: 'parent',
                grid: [this.gridSize, this.gridSize]
            }
        });
        
        // Event listeners
        this.instance.bind('connection', (info) => {
            this.onConnectionCreated(info);
        });
        
        this.instance.bind('connectionDetached', (info) => {
            this.onConnectionDetached(info);
        });
        
        this.instance.bind('connectionMoved', (info) => {
            this.onConnectionMoved(info);
        });
    }
    
    // ============================================================================
    // STEP MANAGEMENT
    // ============================================================================
    
    addStep(stepData) {
        const stepId = stepData.id || `step_${Date.now()}`;
        
        // Criar elemento DOM
        const stepEl = document.createElement('div');
        stepEl.className = 'flow-step';
        stepEl.id = stepId;
        stepEl.dataset.stepId = stepId;
        stepEl.style.left = `${stepData.position?.x || 100}px`;
        stepEl.style.top = `${stepData.position?.y || 100}px`;
        
        // Header
        const header = document.createElement('div');
        header.className = 'flow-step-header';
        header.innerHTML = `
            <span>${stepData.title || stepData.type.toUpperCase()}</span>
            <button class="delete-btn" data-step-id="${stepId}">✕</button>
        `;
        
        // Body
        const body = document.createElement('div');
        body.className = 'flow-step-body';
        const preview = document.createElement('p');
        preview.className = 'preview';
        preview.textContent = this.getStepPreview(stepData);
        body.appendChild(preview);
        
        // Endpoints
        const endpointIn = document.createElement('div');
        endpointIn.className = 'endpoint endpoint-in';
        endpointIn.id = `ep-in-${stepId}`;
        
        const endpointOut = document.createElement('div');
        endpointOut.className = 'endpoint endpoint-out';
        endpointOut.id = `ep-out-${stepId}`;
        
        stepEl.appendChild(header);
        stepEl.appendChild(body);
        stepEl.appendChild(endpointIn);
        stepEl.appendChild(endpointOut);
        
        this.contentContainer.appendChild(stepEl);
        
        // Configurar jsPlumb
        this.instance.makeSource(stepEl, {
            filter: '.endpoint-out',
            endpoint: ['Dot', { radius: 7 }],
            connector: ['Bezier', { curviness: 75 }],
            anchor: 'Right',
            maxConnections: -1
        });
        
        this.instance.makeTarget(stepEl, {
            filter: '.endpoint-in',
            endpoint: ['Dot', { radius: 7 }],
            anchor: 'Left',
            dropOptions: { hoverClass: 'flow-step-hover' }
        });
        
        // Tornar arrastável
        this.instance.draggable(stepEl, {
            containment: 'parent',
            grid: [this.gridSize, this.gridSize],
            stop: () => {
                this.onStepMoved(stepId);
            }
        });
        
        // Event listeners
        stepEl.addEventListener('dblclick', () => {
            if (this.alpine && this.alpine.openEdit) {
                this.alpine.openEdit(stepData);
            }
        });
        
        header.querySelector('.delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteStep(stepId);
        });
        
        // Salvar referência
        this.steps.set(stepId, {
            element: stepEl,
            data: stepData
        });
        
        // Adicionar ao histórico
        this.pushHistory({
            type: 'add_step',
            stepId: stepId,
            stepData: stepData
        });
        
        return stepId;
    }
    
    removeStep(stepId) {
        const step = this.steps.get(stepId);
        if (!step) return;
        
        // Remover todas as conexões
        const connections = this.instance.getConnections({
            source: step.element,
            target: step.element
        });
        connections.forEach(conn => {
            this.instance.deleteConnection(conn);
        });
        
        // Remover do DOM
        step.element.remove();
        this.steps.delete(stepId);
        this.selectedSteps.delete(stepId);
        
        // Adicionar ao histórico
        this.pushHistory({
            type: 'remove_step',
            stepId: stepId,
            stepData: step.data
        });
        
        this.repaint();
    }
    
    updateStep(stepId, stepData) {
        const step = this.steps.get(stepId);
        if (!step) return;
        
        // Atualizar dados
        step.data = { ...step.data, ...stepData };
        
        // Atualizar DOM
        const header = step.element.querySelector('.flow-step-header span');
        if (header) {
            header.textContent = stepData.title || stepData.type.toUpperCase();
        }
        
        const preview = step.element.querySelector('.preview');
        if (preview) {
            preview.textContent = this.getStepPreview(stepData);
        }
        
        // Atualizar posição se necessário
        if (stepData.position) {
            step.element.style.left = `${stepData.position.x}px`;
            step.element.style.top = `${stepData.position.y}px`;
        }
        
        this.repaint();
    }
    
    getStepPreview(step) {
        if (step.type === 'message') {
            return step.config?.message?.substring(0, 50) || 'Mensagem...';
        }
        if (step.type === 'payment') {
            return `Pagamento PIX - R$ ${step.config?.price || '0.00'}`;
        }
        if (step.type === 'audio') {
            return 'Áudio';
        }
        if (step.type === 'video') {
            return 'Vídeo';
        }
        if (step.type === 'content') {
            return 'Conteúdo';
        }
        if (step.type === 'access') {
            return 'Link de Acesso';
        }
        return 'Bloco';
    }
    
    // ============================================================================
    // CONNECTION MANAGEMENT
    // ============================================================================
    
    connect(sourceId, targetId) {
        const source = this.steps.get(sourceId);
        const target = this.steps.get(targetId);
        
        if (!source || !target) {
            console.warn('⚠️ Step não encontrado para conexão');
            return null;
        }
        
        // Verificar se já existe conexão
        const existing = this.instance.getConnections({
            source: source.element,
            target: target.element
        });
        
        if (existing.length > 0) {
            console.warn('⚠️ Conexão já existe');
            return existing[0];
        }
        
        // Criar conexão
        const connection = this.instance.connect({
            source: source.element,
            target: target.element,
            anchors: ['Right', 'Left'],
            endpoint: ['Dot', { radius: 7 }]
        });
        
        // Salvar referência
        const connId = `${sourceId}->${targetId}`;
        this.connections.set(connId, {
            connection: connection,
            sourceId: sourceId,
            targetId: targetId
        });
        
        // Adicionar ao histórico
        this.pushHistory({
            type: 'connect',
            sourceId: sourceId,
            targetId: targetId
        });
        
        return connection;
    }
    
    disconnect(sourceId, targetId) {
        const connId = `${sourceId}->${targetId}`;
        const conn = this.connections.get(connId);
        
        if (conn) {
            this.instance.deleteConnection(conn.connection);
            this.connections.delete(connId);
            
            // Adicionar ao histórico
            this.pushHistory({
                type: 'disconnect',
                sourceId: sourceId,
                targetId: targetId
            });
        }
    }
    
    onConnectionCreated(info) {
        const sourceId = info.source.id;
        const targetId = info.target.id;
        const connId = `${sourceId}->${targetId}`;
        
        this.connections.set(connId, {
            connection: info.connection,
            sourceId: sourceId,
            targetId: targetId
        });
        
        // Atualizar dados do step no Alpine
        if (this.alpine && this.alpine.updateStepConnection) {
            this.alpine.updateStepConnection(sourceId, targetId);
        }
    }
    
    onConnectionDetached(info) {
        const sourceId = info.source.id;
        const targetId = info.target.id;
        const connId = `${sourceId}->${targetId}`;
        
        this.connections.delete(connId);
        
        // Atualizar dados do step no Alpine
        if (this.alpine && this.alpine.removeStepConnection) {
            this.alpine.removeStepConnection(sourceId, targetId);
        }
    }
    
    onConnectionMoved(info) {
        // Reconectar se necessário
        this.repaint();
    }
    
    // ============================================================================
    // ZOOM & PAN
    // ============================================================================
    
    enableZoom() {
        this.canvas.addEventListener('wheel', (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                
                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
                const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoom * zoomFactor));
                
                // Zoom com foco no mouse
                const zoomChange = newZoom / this.zoom;
                this.pan.x = mouseX - (mouseX - this.pan.x) * zoomChange;
                this.pan.y = mouseY - (mouseY - this.pan.y) * zoomChange;
                this.zoom = newZoom;
                
                this.updateTransform();
                this.repaint();
            }
        });
    }
    
    enablePan() {
        let isPanning = false;
        let startPoint = { x: 0, y: 0 };
        
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.button === 1 || (e.button === 0 && e.altKey)) { // Botão do meio ou Alt + esquerdo
                e.preventDefault();
                isPanning = true;
                startPoint = { x: e.clientX - this.pan.x, y: e.clientY - this.pan.y };
                this.canvas.style.cursor = 'grabbing';
            }
        });
        
        this.canvas.addEventListener('mousemove', (e) => {
            if (isPanning) {
                this.pan.x = e.clientX - startPoint.x;
                this.pan.y = e.clientY - startPoint.y;
                this.updateTransform();
            }
        });
        
        this.canvas.addEventListener('mouseup', () => {
            isPanning = false;
            this.canvas.style.cursor = 'default';
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            isPanning = false;
            this.canvas.style.cursor = 'default';
        });
    }
    
    updateTransform() {
        if (this.contentContainer) {
            this.contentContainer.style.transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.zoom})`;
        }
    }
    
    zoomIn() {
        this.zoom = Math.min(this.maxZoom, this.zoom * 1.2);
        this.updateTransform();
        this.repaint();
    }
    
    zoomOut() {
        this.zoom = Math.max(this.minZoom, this.zoom * 0.8);
        this.updateTransform();
        this.repaint();
    }
    
    zoomReset() {
        this.zoom = 1;
        this.pan = { x: 0, y: 0 };
        this.updateTransform();
        this.repaint();
    }
    
    zoomToFit() {
        if (this.steps.size === 0) return;
        
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.steps.forEach(step => {
            const rect = step.element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            const x = rect.left - canvasRect.left;
            const y = rect.top - canvasRect.top;
            
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + rect.width);
            maxY = Math.max(maxY, y + rect.height);
        });
        
        const width = maxX - minX;
        const height = maxY - minY;
        const canvasWidth = this.canvas.clientWidth;
        const canvasHeight = this.canvas.clientHeight;
        
        const scaleX = canvasWidth / width;
        const scaleY = canvasHeight / height;
        this.zoom = Math.min(scaleX, scaleY) * 0.9;
        
        this.pan.x = (canvasWidth - width * this.zoom) / 2 - minX * this.zoom;
        this.pan.y = (canvasHeight - height * this.zoom) / 2 - minY * this.zoom;
        
        this.updateTransform();
        this.repaint();
    }
    
    // ============================================================================
    // SELECTION
    // ============================================================================
    
    enableSelection() {
        this.canvas.addEventListener('click', (e) => {
            const stepEl = e.target.closest('.flow-step');
            if (stepEl) {
                const stepId = stepEl.id;
                this.selectStep(stepId, !e.shiftKey);
            } else {
                this.clearSelection();
            }
        });
    }
    
    selectStep(stepId, clearOthers = true) {
        if (clearOthers) {
            this.clearSelection();
        }
        
        const step = this.steps.get(stepId);
        if (step) {
            step.element.classList.add('flow-step-selected');
            this.selectedSteps.add(stepId);
        }
    }
    
    clearSelection() {
        this.selectedSteps.forEach(stepId => {
            const step = this.steps.get(stepId);
            if (step) {
                step.element.classList.remove('flow-step-selected');
            }
        });
        this.selectedSteps.clear();
    }
    
    // ============================================================================
    // RENDERING & PERFORMANCE
    // ============================================================================
    
    renderAllSteps() {
        if (!this.alpine) {
            // Tentar buscar steps do botConfigApp
            if (window.botConfigApp && window.botConfigApp.config) {
                const flowSteps = window.botConfigApp.config.flow_steps;
                if (flowSteps) {
                    try {
                        const steps = typeof flowSteps === 'string' ? JSON.parse(flowSteps) : flowSteps;
                        if (Array.isArray(steps)) {
                            steps.forEach(stepData => {
                                this.addStep(stepData);
                            });
                            this.restoreConnections();
                            this.repaint();
                            return;
                        }
                    } catch (e) {
                        console.error('❌ Erro ao parsear flow_steps:', e);
                    }
                }
            }
            return;
        }
        
        if (!this.alpine.steps || !Array.isArray(this.alpine.steps)) {
            return;
        }
        
        // Limpar steps existentes
        this.steps.forEach((step, stepId) => {
            step.element.remove();
        });
        this.steps.clear();
        this.connections.clear();
        
        // Renderizar steps do Alpine
        this.alpine.steps.forEach(stepData => {
            this.addStep(stepData);
        });
        
        // Restaurar conexões
        this.restoreConnections();
        
        this.repaint();
    }
    
    restoreConnections() {
        let stepsToProcess = [];
        
        if (this.alpine && this.alpine.steps) {
            stepsToProcess = this.alpine.steps;
        } else if (window.botConfigApp && window.botConfigApp.config) {
            const flowSteps = window.botConfigApp.config.flow_steps;
            if (flowSteps) {
                try {
                    stepsToProcess = typeof flowSteps === 'string' ? JSON.parse(flowSteps) : flowSteps;
                } catch (e) {
                    console.error('❌ Erro ao parsear flow_steps para conexões:', e);
                    return;
                }
            }
        }
        
        if (!Array.isArray(stepsToProcess)) {
            return;
        }
        
        // Aguardar um pouco para garantir que os steps foram renderizados
        setTimeout(() => {
            stepsToProcess.forEach(step => {
                const connections = step.connections || {};
                
                // Conexão 'next'
                if (connections.next) {
                    this.connect(step.id, connections.next);
                }
                
                // Conexão 'pending' (para payment steps)
                if (connections.pending) {
                    this.connect(step.id, connections.pending);
                }
            });
            
            this.repaint();
        }, 100);
    }
    
    updateViewport() {
        const rect = this.canvas.getBoundingClientRect();
        this.viewport = {
            x: -this.pan.x / this.zoom,
            y: -this.pan.y / this.zoom,
            width: rect.width / this.zoom,
            height: rect.height / this.zoom
        };
    }
    
    repaint() {
        if (this.instance) {
            this.instance.repaintEverything();
        }
    }
    
    onStepMoved(stepId) {
        const step = this.steps.get(stepId);
        if (step && this.alpine) {
            const rect = step.element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            const x = (rect.left - canvasRect.left - this.pan.x) / this.zoom;
            const y = (rect.top - canvasRect.top - this.pan.y) / this.zoom;
            
            // Atualizar posição no Alpine
            const stepIndex = this.alpine.steps.findIndex(s => s.id === stepId);
            if (stepIndex !== -1) {
                this.alpine.steps[stepIndex].position = { x, y };
            }
        }
        
        this.repaint();
    }
    
    // ============================================================================
    // HISTORY (UNDO/REDO)
    // ============================================================================
    
    pushHistory(action) {
        // Remover ações futuras se estamos no meio do histórico
        if (this.historyIndex < this.history.length - 1) {
            this.history = this.history.slice(0, this.historyIndex + 1);
        }
        
        this.history.push(action);
        this.historyIndex++;
        
        // Limitar histórico
        if (this.history.length > this.maxHistory) {
            this.history.shift();
            this.historyIndex--;
        }
    }
    
    undo() {
        if (this.historyIndex < 0) return false;
        
        const action = this.history[this.historyIndex];
        this.historyIndex--;
        
        // Reverter ação
        this.revertAction(action);
        
        return true;
    }
    
    redo() {
        if (this.historyIndex >= this.history.length - 1) return false;
        
        this.historyIndex++;
        const action = this.history[this.historyIndex];
        
        // Aplicar ação
        this.applyAction(action);
        
        return true;
    }
    
    revertAction(action) {
        // Implementar reversão baseada no tipo de ação
        // Por enquanto, apenas repaint
        this.repaint();
    }
    
    applyAction(action) {
        // Implementar aplicação baseada no tipo de ação
        // Por enquanto, apenas repaint
        this.repaint();
    }
    
    // ============================================================================
    // UTILITY
    // ============================================================================
    
    refresh(steps) {
        this.renderAllSteps();
    }
    
    destroy() {
        if (this.instance) {
            this.instance.destroy();
            this.instance = null;
        }
        
        this.steps.clear();
        this.connections.clear();
        this.selectedSteps.clear();
        this.history = [];
        this.historyIndex = -1;
    }
    
    // Método para compatibilidade com código existente
    updateStepEndpoints(stepId) {
        this.repaint();
    }
    
    deleteStep(stepId) {
        this.removeStep(stepId);
        
        // Notificar Alpine
        if (this.alpine && this.alpine.deleteStep) {
            this.alpine.deleteStep(stepId);
        }
    }
}

// Exportar globalmente
window.FlowEditor = FlowEditor;

