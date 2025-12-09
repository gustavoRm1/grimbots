/**
 * Flow Editor V4.0 - React Flow Rebuild
 * Rebuild completo inspirado em ManyChat, Botpress, Make.com, Figma
 * 
 * Dependências (via CDN):
 * - React 18.x
 * - ReactDOM 18.x
 * - React Flow 11.x
 * - Dagre (layout automático)
 * 
 * Design System:
 * - Background: #0D0F15
 * - Cards: #13151C
 * - Border: #242836
 * - Connections: #FFFFFF
 * - Grid: 20x20px
 */

(function() {
    'use strict';

    // Verificar se React Flow está disponível
    if (typeof React === 'undefined' || typeof ReactFlow === 'undefined') {
        console.error('❌ React ou React Flow não está disponível. Carregue via CDN primeiro.');
        return;
    }

    const { useState, useCallback, useMemo, useEffect, useRef } = React;
    const { 
        ReactFlow, 
        Background, 
        Controls, 
        MiniMap,
        Panel,
        useNodesState,
        useEdgesState,
        addEdge,
        ConnectionMode,
        MarkerType,
        Position,
        Handle,
        getNodesBounds,
        getViewportForBounds,
        useReactFlow
    } = ReactFlow;

    // Importar Dagre para layout automático
    let dagre = null;
    if (typeof dagreLib !== 'undefined') {
        dagre = dagreLib;
    }

    /**
     * Componente MessageNode - Preview completo do step
     */
    function MessageNode({ data, selected }) {
        const nodeData = data || {};
        const config = nodeData.config || {};
        const customButtons = config.custom_buttons || [];
        const mediaUrl = config.media_url || '';
        const mediaType = config.media_type || 'video';
        const text = config.text || nodeData.text || '';
        const stepType = nodeData.type || 'message';
        const isStartStep = nodeData.is_start || false;

        // Ícones por tipo
        const typeIcons = {
            message: 'fa-comment',
            payment: 'fa-credit-card',
            access: 'fa-key',
            content: 'fa-file-alt'
        };

        const icon = typeIcons[stepType] || 'fa-comment';

        return (
            React.createElement('div', {
                className: `flow-node ${selected ? 'selected' : ''} ${isStartStep ? 'start-step' : ''}`,
                style: {
                    width: '280px',
                    minHeight: '180px',
                    background: '#13151C',
                    border: isStartStep ? '2px solid #FFB800' : '1px solid #242836',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    boxShadow: selected 
                        ? '0 8px 24px rgba(255, 184, 0, 0.3)' 
                        : '0 2px 12px rgba(0, 0, 0, 0.3)',
                    transition: 'all 0.2s ease',
                    cursor: 'move'
                }
            }, [
                // Header vermelho
                React.createElement('div', {
                    key: 'header',
                    style: {
                        background: '#E02727',
                        padding: '12px 16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        position: 'relative'
                    }
                }, [
                    React.createElement('i', {
                        key: 'icon',
                        className: `fas ${icon}`,
                        style: { color: '#FFFFFF', fontSize: '18px' }
                    }),
                    React.createElement('span', {
                        key: 'title',
                        style: {
                            color: '#FFFFFF',
                            fontSize: '14px',
                            fontWeight: '600',
                            textTransform: 'capitalize'
                        }
                    }, stepType === 'message' ? 'Mensagem' : stepType === 'payment' ? 'Pagamento' : stepType === 'access' ? 'Acesso' : 'Conteúdo'),
                    isStartStep && React.createElement('div', {
                        key: 'badge',
                        style: {
                            position: 'absolute',
                            right: '12px',
                            fontSize: '18px'
                        }
                    }, '⭐')
                ]),

                // Body
                React.createElement('div', {
                    key: 'body',
                    style: {
                        padding: '12px',
                        background: '#0F0F14'
                    }
                }, [
                    // Mídia
                    mediaUrl && React.createElement('div', {
                        key: 'media',
                        style: {
                            marginBottom: '12px',
                            borderRadius: '8px',
                            overflow: 'hidden',
                            background: '#13151C',
                            border: '1px solid #242836',
                            height: '120px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            position: 'relative'
                        }
                    }, [
                        mediaType === 'photo' || mediaType === 'image' ? (
                            React.createElement('img', {
                                key: 'img',
                                src: mediaUrl,
                                alt: 'Preview',
                                style: {
                                    width: '100%',
                                    height: '100%',
                                    objectFit: 'cover'
                                },
                                onError: (e) => {
                                    e.target.style.display = 'none';
                                    e.target.parentElement.innerHTML = '<div style="display: flex; align-items: center; gap: 10px; padding: 14px; color: #FFFFFF; font-size: 14px;"><i class="fas fa-image" style="color: #60A5FA;"></i> Mídia não disponível</div>';
                                }
                            })
                        ) : (
                            React.createElement('div', {
                                key: 'video',
                                style: {
                                    width: '100%',
                                    height: '100%',
                                    position: 'relative',
                                    background: '#0D0F15'
                                }
                            }, [
                                React.createElement('video', {
                                    key: 'video-el',
                                    src: mediaUrl,
                                    style: {
                                        width: '100%',
                                        height: '100%',
                                        objectFit: 'cover'
                                    },
                                    onError: (e) => {
                                        e.target.style.display = 'none';
                                    }
                                }),
                                React.createElement('div', {
                                    key: 'overlay',
                                    style: {
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        width: '100%',
                                        height: '100%',
                                        background: 'rgba(0, 0, 0, 0.4)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: 'white',
                                        fontSize: '2.5rem',
                                        pointerEvents: 'none'
                                    }
                                }, React.createElement('i', { className: 'fas fa-play' }))
                            ])
                        )
                    ]),

                    // Texto
                    text && React.createElement('div', {
                        key: 'text',
                        style: {
                            padding: '10px 12px',
                            color: '#FFFFFF',
                            fontSize: '13px',
                            lineHeight: '1.5',
                            wordWrap: 'break-word',
                            whiteSpace: 'pre-wrap',
                            maxHeight: '90px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 4,
                            WebkitBoxOrient: 'vertical',
                            marginBottom: '12px'
                        }
                    }, text.substring(0, 120) + (text.length > 120 ? '...' : '')),

                    // Botões
                    customButtons.length > 0 && React.createElement('div', {
                        key: 'buttons',
                        style: {
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px',
                            marginBottom: '12px'
                        }
                    }, customButtons.map((btn, index) => 
                        React.createElement('div', {
                            key: `btn-${index}`,
                            style: {
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '12px 16px',
                                background: 'linear-gradient(135deg, rgba(224, 39, 39, 0.15) 0%, rgba(239, 68, 68, 0.15) 100%)',
                                border: '2px solid rgba(224, 39, 39, 0.4)',
                                borderRadius: '10px',
                                position: 'relative',
                                minHeight: '44px'
                            }
                        }, [
                            React.createElement('span', {
                                key: 'btn-text',
                                style: {
                                    color: '#FFFFFF',
                                    fontSize: '14px',
                                    fontWeight: '600',
                                    flex: 1,
                                    paddingRight: '12px'
                                }
                            }, btn.text || `Botão ${index + 1}`),
                            React.createElement(Handle, {
                                key: 'handle',
                                type: 'source',
                                position: Position.Right,
                                id: `btn-${index}`,
                                style: {
                                    width: '12px',
                                    height: '12px',
                                    background: '#E02727',
                                    border: '2px solid #FFFFFF',
                                    borderRadius: '50%',
                                    right: '-6px'
                                }
                            })
                        ])
                    ))
                ]),

                // Footer (ações)
                React.createElement('div', {
                    key: 'footer',
                    style: {
                        padding: '8px 12px',
                        background: '#0F0F14',
                        borderTop: '1px solid #242836',
                        display: 'flex',
                        gap: '8px',
                        justifyContent: 'flex-end'
                    }
                }, [
                    React.createElement('button', {
                        key: 'edit',
                        onClick: (e) => {
                            e.stopPropagation();
                            if (window.alpineFlowEditor && window.alpineFlowEditor.openStepModal) {
                                window.alpineFlowEditor.openStepModal(nodeData.id);
                            }
                        },
                        style: {
                            padding: '6px 10px',
                            background: 'transparent',
                            border: '1px solid #242836',
                            borderRadius: '6px',
                            color: '#FFFFFF',
                            cursor: 'pointer',
                            fontSize: '12px'
                        },
                        title: 'Editar'
                    }, React.createElement('i', { className: 'fas fa-edit' })),
                    React.createElement('button', {
                        key: 'delete',
                        onClick: (e) => {
                            e.stopPropagation();
                            if (window.alpineFlowEditor && window.alpineFlowEditor.deleteStep) {
                                window.alpineFlowEditor.deleteStep(nodeData.id);
                            }
                        },
                        style: {
                            padding: '6px 10px',
                            background: 'transparent',
                            border: '1px solid #242836',
                            borderRadius: '6px',
                            color: '#EF4444',
                            cursor: 'pointer',
                            fontSize: '12px'
                        },
                        title: 'Remover'
                    }, React.createElement('i', { className: 'fas fa-trash' }))
                ]),

                // Handle de entrada (sempre à esquerda)
                React.createElement(Handle, {
                    key: 'input',
                    type: 'target',
                    position: Position.Left,
                    style: {
                        width: '14px',
                        height: '14px',
                        background: '#10B981',
                        border: '2px solid #FFFFFF',
                        borderRadius: '50%',
                        left: '-7px'
                    }
                })
            ])
        );
    }

    /**
     * Componente principal FlowEditorReact
     */
    function FlowEditorReact({ alpineContext, canvasId }) {
        const [nodes, setNodes, onNodesChange] = useNodesState([]);
        const [edges, setEdges, onEdgesChange] = useEdgesState([]);
        const [snapToGrid, setSnapToGrid] = useState(true);
        const reactFlowWrapper = useRef(null);
        const { fitView, getViewport, setViewport, zoomTo, project } = useReactFlow();

        // Converter flow_steps do Alpine para nodes do React Flow
        const convertStepsToNodes = useCallback((flowSteps, startStepId) => {
            if (!flowSteps || !Array.isArray(flowSteps)) return [];

            return flowSteps.map(step => {
                const position = step.position || { x: 100, y: 100 };
                const isStart = String(step.id) === String(startStepId);

                return {
                    id: String(step.id),
                    type: 'messageNode',
                    position: { x: position.x || 100, y: position.y || 100 },
                    data: {
                        ...step,
                        is_start: isStart
                    },
                    selected: false
                };
            });
        }, []);

        // Converter conexões do Alpine para edges do React Flow
        const convertConnectionsToEdges = useCallback((flowSteps) => {
            if (!flowSteps || !Array.isArray(flowSteps)) return [];

            const edges = [];

            flowSteps.forEach(sourceStep => {
                const config = sourceStep.config || {};
                const customButtons = config.custom_buttons || [];
                const connections = sourceStep.connections || {};

                // Conexões de botões customizados
                customButtons.forEach((button, buttonIndex) => {
                    if (button.target_step) {
                        edges.push({
                            id: `edge-${sourceStep.id}-btn-${buttonIndex}-${button.target_step}`,
                            source: String(sourceStep.id),
                            sourceHandle: `btn-${buttonIndex}`,
                            target: String(button.target_step),
                            type: 'smoothstep',
                            style: { stroke: '#FFFFFF', strokeWidth: 2 },
                            markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
                        });
                    }
                });

                // Conexões globais (next, pending, retry)
                ['next', 'pending', 'retry'].forEach(connType => {
                    if (connections[connType]) {
                        edges.push({
                            id: `edge-${sourceStep.id}-${connType}-${connections[connType]}`,
                            source: String(sourceStep.id),
                            target: String(connections[connType]),
                            type: 'smoothstep',
                            style: { 
                                stroke: connType === 'next' ? '#FFFFFF' : connType === 'pending' ? '#F59E0B' : '#EF4444',
                                strokeWidth: 2
                            },
                            label: connType === 'next' ? 'Next' : connType === 'pending' ? 'Pending' : 'Retry',
                            labelStyle: { fill: '#FFFFFF', fontWeight: 600 },
                            labelBgStyle: { fill: '#0D0F15', fillOpacity: 0.8 },
                            markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
                        });
                    }
                });
            });

            return edges;
        }, []);

        // Carregar dados do Alpine
        useEffect(() => {
            if (!alpineContext || !alpineContext.config) return;

            const flowSteps = alpineContext.config.flow_steps || [];
            const startStepId = alpineContext.config.flow_start_step_id;

            const newNodes = convertStepsToNodes(flowSteps, startStepId);
            const newEdges = convertConnectionsToEdges(flowSteps);

            setNodes(newNodes);
            setEdges(newEdges);

            // Fit view após carregar
            setTimeout(() => {
                fitView({ padding: 0.2, duration: 400 });
            }, 100);
        }, [alpineContext?.config?.flow_steps, alpineContext?.config?.flow_start_step_id]);

        // Snapping magnético ao grid
        const onNodeDragStop = useCallback((event, node) => {
            if (!snapToGrid) return;

            const snappedPosition = {
                x: Math.round(node.position.x / 20) * 20,
                y: Math.round(node.position.y / 20) * 20
            };

            setNodes((nds) =>
                nds.map((n) =>
                    n.id === node.id
                        ? { ...n, position: snappedPosition }
                        : n
                )
            );

            // Atualizar no Alpine
            if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                const stepIndex = alpineContext.config.flow_steps.findIndex(s => String(s.id) === String(node.id));
                if (stepIndex !== -1) {
                    if (!alpineContext.config.flow_steps[stepIndex].position) {
                        alpineContext.config.flow_steps[stepIndex].position = {};
                    }
                    alpineContext.config.flow_steps[stepIndex].position.x = snappedPosition.x;
                    alpineContext.config.flow_steps[stepIndex].position.y = snappedPosition.y;
                    
                    // Debounced save
                    if (alpineContext.saveConfigDebounced) {
                        alpineContext.saveConfigDebounced();
                    }
                }
            }
        }, [snapToGrid, setNodes, alpineContext]);

        // Atualizar posição durante drag
        const onNodeDrag = useCallback((event, node) => {
            if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                const stepIndex = alpineContext.config.flow_steps.findIndex(s => String(s.id) === String(node.id));
                if (stepIndex !== -1) {
                    if (!alpineContext.config.flow_steps[stepIndex].position) {
                        alpineContext.config.flow_steps[stepIndex].position = {};
                    }
                    alpineContext.config.flow_steps[stepIndex].position.x = node.position.x;
                    alpineContext.config.flow_steps[stepIndex].position.y = node.position.y;
                }
            }
        }, [alpineContext]);

        // Conectar edges
        const onConnect = useCallback((params) => {
            const newEdge = {
                ...params,
                type: 'smoothstep',
                style: { stroke: '#FFFFFF', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
            };
            setEdges((eds) => addEdge(newEdge, eds));

            // Atualizar no Alpine
            if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                const sourceStepIndex = alpineContext.config.flow_steps.findIndex(s => String(s.id) === String(params.source));
                const targetStepId = params.target;

                if (sourceStepIndex !== -1) {
                    const sourceStep = alpineContext.config.flow_steps[sourceStepIndex];
                    const config = sourceStep.config || {};
                    const customButtons = config.custom_buttons || [];

                    // Verificar se é conexão de botão
                    if (params.sourceHandle && params.sourceHandle.startsWith('btn-')) {
                        const buttonIndex = parseInt(params.sourceHandle.replace('btn-', ''));
                        if (customButtons[buttonIndex]) {
                            customButtons[buttonIndex].target_step = targetStepId;
                        }
                    } else {
                        // Conexão global (next)
                        if (!sourceStep.connections) {
                            sourceStep.connections = {};
                        }
                        sourceStep.connections.next = targetStepId;
                    }

                    // Debounced save
                    if (alpineContext.saveConfigDebounced) {
                        alpineContext.saveConfigDebounced();
                    }
                }
            }
        }, [setEdges, alpineContext]);

        // Remover edge
        const onEdgesDelete = useCallback((deletedEdges) => {
            deletedEdges.forEach(edge => {
                if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                    const sourceStepIndex = alpineContext.config.flow_steps.findIndex(s => String(s.id) === String(edge.source));
                    if (sourceStepIndex !== -1) {
                        const sourceStep = alpineContext.config.flow_steps[sourceStepIndex];
                        const config = sourceStep.config || {};
                        const customButtons = config.custom_buttons || [];

                        // Verificar se é conexão de botão
                        if (edge.sourceHandle && edge.sourceHandle.startsWith('btn-')) {
                            const buttonIndex = parseInt(edge.sourceHandle.replace('btn-', ''));
                            if (customButtons[buttonIndex]) {
                                customButtons[buttonIndex].target_step = null;
                            }
                        } else {
                            // Remover conexão global
                            if (sourceStep.connections) {
                                delete sourceStep.connections.next;
                            }
                        }

                        // Debounced save
                        if (alpineContext.saveConfigDebounced) {
                            alpineContext.saveConfigDebounced();
                        }
                    }
                }
            });
        }, [alpineContext]);

        // Layout automático com Dagre
        const organizeLayout = useCallback((direction = 'vertical') => {
            if (!dagre) {
                console.warn('⚠️ Dagre não está disponível. Instale: npm install dagre');
                return;
            }

            const dagreGraph = new dagre.graphlib.Graph();
            dagreGraph.setDefaultEdgeLabel(() => ({}));
            dagreGraph.setGraph({ 
                rankdir: direction === 'vertical' ? 'TB' : 'LR',
                nodesep: 50,
                ranksep: 100
            });

            nodes.forEach((node) => {
                dagreGraph.setNode(node.id, { width: 280, height: 200 });
            });

            edges.forEach((edge) => {
                dagreGraph.setEdge(edge.source, edge.target);
            });

            dagre.layout(dagreGraph);

            const newNodes = nodes.map((node) => {
                const nodeWithPosition = dagreGraph.node(node.id);
                return {
                    ...node,
                    position: {
                        x: nodeWithPosition.x - 140, // Ajustar centro
                        y: nodeWithPosition.y - 100
                    }
                };
            });

            setNodes(newNodes);

            // Atualizar no Alpine
            if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                newNodes.forEach(node => {
                    const stepIndex = alpineContext.config.flow_steps.findIndex(s => String(s.id) === String(node.id));
                    if (stepIndex !== -1) {
                        if (!alpineContext.config.flow_steps[stepIndex].position) {
                            alpineContext.config.flow_steps[stepIndex].position = {};
                        }
                        alpineContext.config.flow_steps[stepIndex].position.x = node.position.x;
                        alpineContext.config.flow_steps[stepIndex].position.y = node.position.y;
                    }
                });

                if (alpineContext.saveConfigDebounced) {
                    alpineContext.saveConfigDebounced();
                }
            }

            setTimeout(() => {
                fitView({ padding: 0.2, duration: 400 });
            }, 100);
        }, [nodes, edges, setNodes, alpineContext, fitView]);

        // Expor métodos globais
        useEffect(() => {
            window.flowEditorReact = {
                zoomIn: () => {
                    const viewport = getViewport();
                    zoomTo(viewport.zoom + 0.2);
                },
                zoomOut: () => {
                    const viewport = getViewport();
                    zoomTo(Math.max(0.2, viewport.zoom - 0.2));
                },
                zoomReset: () => {
                    setViewport({ x: 0, y: 0, zoom: 1 });
                },
                zoomToFit: () => {
                    fitView({ padding: 0.2, duration: 400 });
                },
                organizeVertical: () => organizeLayout('vertical'),
                organizeHorizontal: () => organizeLayout('horizontal'),
                organizeFlowComplete: () => organizeLayout('vertical'),
                organizeByGroups: () => organizeLayout('vertical'),
                addStep: (stepData) => {
                    const newNodes = convertStepsToNodes([stepData], null);
                    setNodes((nds) => [...nds, ...newNodes]);
                },
                updateStep: (stepId, stepData) => {
                    setNodes((nds) =>
                        nds.map((n) =>
                            String(n.id) === String(stepId)
                                ? { ...n, data: { ...n.data, ...stepData } }
                                : n
                        )
                    );
                },
                deleteStep: (stepId) => {
                    setNodes((nds) => nds.filter((n) => String(n.id) !== String(stepId)));
                    setEdges((eds) => eds.filter((e) => String(e.source) !== String(stepId) && String(e.target) !== String(stepId)));
                },
                renderAllSteps: () => {
                    if (alpineContext && alpineContext.config) {
                        const flowSteps = alpineContext.config.flow_steps || [];
                        const startStepId = alpineContext.config.flow_start_step_id;
                        const newNodes = convertStepsToNodes(flowSteps, startStepId);
                        const newEdges = convertConnectionsToEdges(flowSteps);
                        setNodes(newNodes);
                        setEdges(newEdges);
                    }
                }
            };
        }, [getViewport, zoomTo, setViewport, fitView, organizeLayout, convertStepsToNodes, setNodes, setEdges, alpineContext]);

        const nodeTypes = useMemo(() => ({
            messageNode: MessageNode
        }), []);

        return React.createElement('div', {
            ref: reactFlowWrapper,
            style: { width: '100%', height: '100%' }
        }, [
            React.createElement(ReactFlow, {
                key: 'reactflow',
                nodes: nodes,
                edges: edges,
                onNodesChange: onNodesChange,
                onEdgesChange: onEdgesChange,
                onConnect: onConnect,
                onEdgesDelete: onEdgesDelete,
                onNodeDrag: onNodeDrag,
                onNodeDragStop: onNodeDragStop,
                nodeTypes: nodeTypes,
                connectionMode: ConnectionMode.Loose,
                snapToGrid: snapToGrid,
                snapGrid: [20, 20],
                minZoom: 0.2,
                maxZoom: 2,
                defaultViewport: { x: 0, y: 0, zoom: 1 },
                fitView: true,
                panOnScroll: true,
                panOnDrag: [1, 2], // Middle mouse button
                selectionOnDrag: true,
                translateExtent: [[-10000, -10000], [10000, 10000]],
                style: {
                    background: '#0D0F15',
                    backgroundImage: 'radial-gradient(circle, rgba(255, 255, 255, 0.25) 1.5px, transparent 1.5px)',
                    backgroundSize: '20px 20px'
                }
            }, [
                React.createElement(Background, { key: 'bg', gap: 20, size: 1, color: 'rgba(255, 255, 255, 0.1)' }),
                React.createElement(Controls, { key: 'controls', showInteractive: false }),
                React.createElement(MiniMap, { 
                    key: 'minimap',
                    nodeColor: '#E02727',
                    maskColor: 'rgba(0, 0, 0, 0.8)',
                    style: { background: '#13151C' }
                })
            ])
        ]);
    }

    // Expor classe global
    window.FlowEditorReact = FlowEditorReact;
    window.MessageNode = MessageNode;

})();

