/**
 * Flow Editor - Editor Visual de Fluxo com jsPlumb
 * Sistema completo de edição visual de fluxos de bot
 * Versão: 2.0.1 - Correção jsPlumb 2.x
 * 
 * Dependências:
 * - jsPlumb 2.15.6 (CDN)
 * - Alpine.js 3.x (CDN)
 */

class FlowEditor {
    constructor(canvasId, alpineContext) {
        this.canvasId = canvasId;
        this.canvas = document.getElementById(canvasId);
        this.alpine = alpineContext; // Referência ao contexto Alpine.js
        this.instance = null; // Instância do jsPlumb
        this.steps = new Map(); // Map<stepId, DOMElement>
        this.connections = new Map(); // Map<connectionId, jsPlumbConnection>
        this.currentDragging = null; // Step sendo arrastado
        this.connectionMode = null; // 'next' | 'pending' | 'retry' | null
        this.selectedStep = null; // Step selecionado
        this.zoomLevel = 1; // Nível de zoom atual
        
        // Cores por tipo de conexão
        this.connectionColors = {
            next: '#10B981',      // Verde (sucesso)
            pending: '#F59E0B',   // Amarelo (pendente)
            retry: '#EF4444'      // Vermelho (erro/retry)
        };
        
        // Cores por tipo de step
        this.stepColors = {
            content: '#3B82F6',   // Azul
            message: '#8B5CF6',   // Roxo
            audio: '#EC4899',     // Rosa
            video: '#F59E0B',     // Amarelo
            buttons: '#10B981',   // Verde
            payment: '#EF4444',   // Vermelho
            access: '#14B8A6'     // Ciano
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
        console.log('🔵 FlowEditor.init() chamado - Versão 2.0.1');
        
        if (!this.canvas) {
            console.error('❌ Canvas não encontrado:', this.canvasId);
            return;
        }
        
        // Verificar se jsPlumb está disponível
        if (typeof jsPlumb === 'undefined') {
            console.error('❌ jsPlumb não está carregado. Verifique se o script foi incluído antes deste arquivo.');
            return;
        }
        
        console.log('✅ jsPlumb disponível:', typeof jsPlumb);
        console.log('✅ jsPlumb métodos disponíveis:', Object.keys(jsPlumb).filter(k => typeof jsPlumb[k] === 'function').slice(0, 10));
        
        // Inicializar jsPlumb (API 2.x)
        // jsPlumb 2.x usa a instância padrão global diretamente
        try {
            // Verificar se jsPlumb está realmente disponível
            if (!jsPlumb || typeof jsPlumb !== 'object') {
                throw new Error('jsPlumb não está disponível como objeto');
            }
            
            // jsPlumb 2.x: usar a instância padrão diretamente
            this.instance = jsPlumb;
            
            // Configurar container
            if (typeof this.instance.setContainer === 'function') {
                this.instance.setContainer(this.canvas);
            }
            
            // Configurar defaults
            if (typeof this.instance.importDefaults === 'function') {
                this.instance.importDefaults({
                    paintStyle: { stroke: '#10B981', strokeWidth: 2 },
                    hoverPaintStyle: { stroke: '#34D399', strokeWidth: 3 },
                    connector: ['Bezier', { curviness: 50, stub: [10, 15], gap: 5 }],
                    endpoint: ['Dot', { radius: 8 }],
                    endpointStyle: { fill: '#10B981', outlineStroke: '#FFFFFF', outlineWidth: 2 },
                    endpointHoverStyle: { fill: '#34D399', outlineStroke: '#FFFFFF', outlineWidth: 3 },
                    anchors: ['Top', 'Bottom'],
                    maxConnections: -1,
                    dragOptions: {
                        cursor: 'grabbing',
                        zIndex: 2000
                    }
                });
            } else {
                // Se importDefaults não existe, configurar diretamente
                this.instance.Defaults = this.instance.Defaults || {};
                this.instance.Defaults.paintStyle = { stroke: '#10B981', strokeWidth: 2 };
                this.instance.Defaults.hoverPaintStyle = { stroke: '#34D399', strokeWidth: 3 };
                this.instance.Defaults.connector = ['Bezier', { curviness: 50, stub: [10, 15], gap: 5 }];
                this.instance.Defaults.endpoint = ['Dot', { radius: 8 }];
                this.instance.Defaults.endpointStyle = { fill: '#10B981', outlineStroke: '#FFFFFF', outlineWidth: 2 };
                this.instance.Defaults.endpointHoverStyle = { fill: '#34D399', outlineStroke: '#FFFFFF', outlineWidth: 3 };
                this.instance.Defaults.anchors = ['Top', 'Bottom'];
                this.instance.Defaults.maxConnections = -1;
            }
            
            console.log('✅ jsPlumb inicializado:', this.instance ? 'OK' : 'FALHOU');
        } catch (error) {
            console.error('❌ Erro ao inicializar jsPlumb:', error);
            console.error('jsPlumb disponível:', typeof jsPlumb);
            if (jsPlumb) {
                console.error('jsPlumb tipo:', typeof jsPlumb);
                console.error('jsPlumb chaves:', Object.keys(jsPlumb).slice(0, 20));
            }
            return;
        }
        
        // Habilitar drag em todos os elementos com classe flow-step-block
        // No jsPlumb 2.x, eventos podem ser registrados diretamente
        setTimeout(() => {
            this.instance.bind('connection', (info) => this.onConnectionCreated(info));
            this.instance.bind('connectionDetached', (info) => this.onConnectionDetached(info));
            this.instance.bind('connectionMoved', (info) => this.onConnectionMoved(info));
            
            // Habilitar remoção de conexão com duplo clique
            this.instance.bind('click', (conn, originalEvent) => {
                if (originalEvent.detail === 2) { // Duplo clique
                    this.removeConnection(conn);
                }
            });
            
            // Habilitar remoção com botão direito
            this.instance.bind('contextmenu', (conn, originalEvent) => {
                originalEvent.preventDefault();
                this.removeConnection(conn);
            });
            
            console.log('✅ jsPlumb inicializado');
        }, 100);
        
        // Renderizar steps existentes
        this.renderAllSteps();
        
        // Habilitar zoom com scroll
        this.enableZoom();
        
        // Habilitar seleção ao clicar
        this.enableSelection();
    }
    
    /**
     * Habilita zoom com scroll do mouse
     */
    enableZoom() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('wheel', (e) => {
            // Zoom com Ctrl/Cmd + Scroll
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
        if (!this.instance || !this.canvas) return;
        
        // Aplicar zoom no canvas diretamente
        this.canvas.style.transform = `scale(${this.zoomLevel})`;
        this.canvas.style.transformOrigin = 'top left';
        
        // Repintar jsPlumb após zoom
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
     * Habilita seleção visual ao clicar
     */
    enableSelection() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('click', (e) => {
            // Ignorar cliques em botões
            if (e.target.closest('button')) {
                return;
            }
            
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
        // Deselecionar anterior
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
     * Renderiza todos os steps do fluxo
     */
    renderAllSteps() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        const steps = this.alpine.config.flow_steps;
        
        // Limpar canvas
        this.clearCanvas();
        
        // Renderizar cada step
        steps.forEach(step => {
            this.renderStep(step);
        });
        
        // Reconectar todas as conexões
        this.reconnectAll();
        
        console.log(`✅ ${steps.length} steps renderizados`);
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
        
        // Verificar se já existe
        if (this.steps.has(stepId)) {
            this.updateStep(step);
            return;
        }
        
        // Criar elemento DOM
        const stepElement = document.createElement('div');
        stepElement.id = `step-${stepId}`;
        stepElement.className = 'flow-step-block';
        stepElement.dataset.stepId = stepId;
        
        // Posição (restaurar ou padrão)
        const position = step.position || { x: 100, y: 100 };
        stepElement.style.left = `${position.x}px`;
        stepElement.style.top = `${position.y}px`;
        
        // Cor e ícone
        const color = this.stepColors[stepType] || '#6B7280';
        const icon = this.stepIcons[stepType] || 'fa-circle';
        
        // Verificar se é step inicial
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        
        // HTML do bloco
        stepElement.innerHTML = `
            <div class="flow-step-header" style="background: ${color};">
                <div class="flow-step-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="flow-step-title">
                    ${this.getStepTypeLabel(stepType)}
                </div>
                ${isStartStep ? '<div class="flow-step-start-badge">⭐</div>' : ''}
            </div>
            <div class="flow-step-body">
                <div class="flow-step-preview">
                    ${this.getStepPreview(step)}
                </div>
            </div>
            <div class="flow-step-footer">
                <button class="flow-step-btn-edit" onclick="window.flowEditor?.editStep('${stepId}')" title="Editar">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="flow-step-btn-delete" onclick="window.flowEditor?.deleteStep('${stepId}')" title="Remover">
                    <i class="fas fa-trash"></i>
                </button>
                ${!isStartStep ? `<button class="flow-step-btn-start" onclick="window.flowEditor?.setStartStep('${stepId}')" title="Definir como inicial">⭐</button>` : ''}
            </div>
        `;
        
        // Adicionar ao canvas
        this.canvas.appendChild(stepElement);
        
        // Tornar arrastável
        this.instance.draggable(stepElement, {
            containment: 'parent',
            grid: [10, 10],
            drag: (params) => this.onStepDrag(params),
            stop: (params) => this.onStepDragStop(params)
        });
        
        // Adicionar endpoints
        this.addEndpoints(stepElement, stepId);
        
        // Salvar referência
        this.steps.set(stepId, stepElement);
        
        // Aplicar estilo de highlight se for step inicial
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
        
        // Atualizar posição se mudou
        const position = step.position || { x: 100, y: 100 };
        element.style.left = `${position.x}px`;
        element.style.top = `${position.y}px`;
        
        // Atualizar preview
        const previewEl = element.querySelector('.flow-step-preview');
        if (previewEl) {
            previewEl.innerHTML = this.getStepPreview(step);
        }
        
        // Atualizar highlight de step inicial
        const isStartStep = this.alpine.config.flow_start_step_id === stepId;
        if (isStartStep) {
            element.classList.add('flow-step-initial');
        } else {
            element.classList.remove('flow-step-initial');
        }
    }
    
    /**
     * Adiciona endpoints (pontos de conexão) ao step
     */
    addEndpoints(element, stepId) {
        // Endpoint superior (entrada) - verde
        this.instance.addEndpoint(element, {
            uuid: `endpoint-top-${stepId}`,
            anchor: 'Top',
            maxConnections: -1,
            isSource: false,
            isTarget: true,
            endpoint: ['Dot', { radius: 8 }],
            paintStyle: { fill: '#10B981', outlineStroke: '#FFFFFF', outlineWidth: 2 },
            hoverPaintStyle: { fill: '#34D399', outlineStroke: '#FFFFFF', outlineWidth: 3 }
        });
        
        // Endpoint inferior (saída) - vermelho
        this.instance.addEndpoint(element, {
            uuid: `endpoint-bottom-${stepId}`,
            anchor: 'Bottom',
            maxConnections: -1,
            isSource: true,
            isTarget: false,
            endpoint: ['Dot', { radius: 8 }],
            paintStyle: { fill: '#EF4444', outlineStroke: '#FFFFFF', outlineWidth: 2 },
            hoverPaintStyle: { fill: '#F87171', outlineStroke: '#FFFFFF', outlineWidth: 3 }
        });
    }
    
    /**
     * Reconecta todas as conexões baseado nos dados do Alpine
     */
    reconnectAll() {
        if (!this.alpine || !this.alpine.config || !this.alpine.config.flow_steps) {
            return;
        }
        
        // Limpar conexões existentes
        this.instance.deleteEveryConnection();
        this.connections.clear();
        
        // Reconectar baseado nos dados
        const steps = this.alpine.config.flow_steps;
        if (!Array.isArray(steps)) {
            return;
        }
        
        steps.forEach(step => {
            if (!step || !step.id) return;
            
            const stepId = String(step.id);
            const connections = step.connections || {};
            
            // Verificar se step existe no DOM antes de conectar
            if (!this.steps.has(stepId)) {
                console.warn(`⚠️ Step ${stepId} não renderizado ainda - pulando conexões`);
                return;
            }
            
            // Conexão 'next'
            if (connections.next) {
                const targetId = String(connections.next);
                if (this.steps.has(targetId)) {
                    this.createConnection(stepId, targetId, 'next');
                }
            }
            
            // Conexão 'pending'
            if (connections.pending) {
                const targetId = String(connections.pending);
                if (this.steps.has(targetId)) {
                    this.createConnection(stepId, targetId, 'pending');
                }
            }
            
            // Conexão 'retry'
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
        
        // Validar que não é a mesma step
        if (sourceId === targetId) {
            console.warn(`⚠️ Tentativa de conectar step consigo mesmo: ${sourceId}`);
            return null;
        }
        
        const sourceElement = this.steps.get(sourceId);
        const targetElement = this.steps.get(targetId);
        
        if (!sourceElement || !targetElement) {
            console.warn(`⚠️ Step não encontrado para conexão: ${sourceId} → ${targetId}`);
            return null;
        }
        
        // Verificar se conexão já existe
        const connId = `${sourceId}-${targetId}-${connectionType}`;
        if (this.connections.has(connId)) {
            console.debug(`ℹ️ Conexão já existe: ${connId}`);
            return this.connections.get(connId);
        }
        
        const color = this.connectionColors[connectionType] || '#10B981';
        const label = this.getConnectionLabel(connectionType);
        
        try {
            const connection = this.instance.connect({
                source: `endpoint-bottom-${sourceId}`,
                target: `endpoint-top-${targetId}`,
                paintStyle: { stroke: color, strokeWidth: 2 },
                hoverPaintStyle: { stroke: color, strokeWidth: 3 },
                overlays: [
                    ['Label', {
                        label: label,
                        location: 0.5,
                        cssClass: 'connection-label',
                        labelStyle: {
                            color: color,
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            fontWeight: 'bold'
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
                
                // Adicionar classe para animação
            // Adicionar animação de conexão (se possível)
            try {
                const overlays = connection.getOverlays();
                if (overlays && overlays.length > 0) {
                    // Adicionar classe de animação via CSS
                    setTimeout(() => {
                        this.instance.repaint(connection);
                    }, 10);
                }
            } catch (e) {
                // Ignorar erros de animação
            }
                
                // Atualizar dados no Alpine (apenas se não existir)
                const step = this.alpine?.config?.flow_steps?.find(s => String(s.id) === sourceId);
                if (step && (!step.connections || !step.connections[connectionType])) {
                    this.updateAlpineConnection(sourceId, targetId, connectionType);
                }
            }
            
            return connection;
        } catch (error) {
            console.error(`❌ Erro ao criar conexão ${sourceId} → ${targetId}:`, error);
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
            
            // Remover do Alpine
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const sourceStep = steps.find(s => String(s.id) === String(sourceStepId));
                
                if (sourceStep && sourceStep.connections) {
                    delete sourceStep.connections[connectionType];
                }
            }
            
            // Remover do Map
            const connId = `${sourceStepId}-${targetStepId}-${connectionType}`;
            this.connections.delete(connId);
        }
        
        // Remover do jsPlumb
        this.instance.deleteConnection(connection);
    }
    
    /**
     * Callback quando conexão é criada
     */
    onConnectionCreated(info) {
        const sourceUuid = info.sourceId || info.source?.getUuid?.();
        const targetUuid = info.targetId || info.target?.getUuid?.();
        
        // Extrair step IDs dos UUIDs dos endpoints
        const sourceStepId = sourceUuid ? sourceUuid.replace('endpoint-bottom-', '').replace('endpoint-top-', '') : null;
        const targetStepId = targetUuid ? targetUuid.replace('endpoint-bottom-', '').replace('endpoint-top-', '') : null;
        
        if (sourceStepId && targetStepId && sourceUuid?.includes('bottom') && targetUuid?.includes('top')) {
            // Conexão criada via drag - determinar tipo (por padrão 'next')
            // O usuário pode editar depois no modal
            const connectionType = 'next';
            this.updateAlpineConnection(sourceStepId, targetStepId, connectionType);
            
            // Atualizar visual da conexão
            if (info.connection) {
                const color = this.connectionColors[connectionType] || '#10B981';
                const label = this.getConnectionLabel(connectionType);
                
                info.connection.setPaintStyle({ stroke: color, strokeWidth: 2 });
                info.connection.setHoverPaintStyle({ stroke: color, strokeWidth: 3 });
                
                // Adicionar label
                info.connection.setLabel({
                    label: label,
                    location: 0.5,
                    cssClass: 'connection-label',
                    labelStyle: {
                        color: color,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 'bold'
                    }
                });
                
                // Salvar dados da conexão
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
     * Callback quando conexão é movida
     */
    onConnectionMoved(info) {
        // Atualizar se necessário
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
            
            // Salvar posição no Alpine
            const rect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            const position = {
                x: rect.left - canvasRect.left,
                y: rect.top - canvasRect.top
            };
            
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
            step.position.x = Math.round(position.x);
            step.position.y = Math.round(position.y);
        }
    }
    
    /**
     * Remove um step
     */
    deleteStep(stepId) {
        if (!confirm(`Tem certeza que deseja remover este step?`)) {
            return;
        }
        
        const id = String(stepId);
        const element = this.steps.get(id);
        
        if (element) {
            // Remover todas as conexões relacionadas
            const connectionsToRemove = [];
            this.connections.forEach((conn, connId) => {
                const data = conn.getData();
                if (data && (data.sourceStepId === id || data.targetStepId === id)) {
                    connectionsToRemove.push(conn);
                }
            });
            
            connectionsToRemove.forEach(conn => {
                this.removeConnection(conn);
            });
            
            // Remover do jsPlumb
            this.instance.remove(element);
            
            // Remover do DOM
            element.remove();
            
            // Remover do Map
            this.steps.delete(id);
            
            // Remover do Alpine
            if (this.alpine && this.alpine.config && this.alpine.config.flow_steps) {
                const steps = this.alpine.config.flow_steps;
                const index = steps.findIndex(s => String(s.id) === id);
                if (index !== -1) {
                    steps.splice(index, 1);
                }
                
                // Limpar step inicial se for este
                if (this.alpine.config.flow_start_step_id === id) {
                    this.alpine.config.flow_start_step_id = null;
                }
            }
            
            console.log(`✅ Step ${id} removido`);
        }
    }
    
    /**
     * Define step como inicial
     */
    setStartStep(stepId) {
        if (this.alpine && this.alpine.config) {
            this.alpine.config.flow_start_step_id = String(stepId);
            this.renderAllSteps(); // Re-renderizar para atualizar highlight
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
        this.steps.forEach((element, stepId) => {
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
            this.instance.destroy();
            this.instance = null;
        }
    }
}

// Exportar para uso global
window.FlowEditor = FlowEditor;

