/**
 * Flow Editor V5.0 - ManyChat Quality Rebuild
 * Rebuild completo e funcional usando React Flow
 * 
 * CDN Dependencies:
 * - React 18.x (production)
 * - ReactDOM 18.x (production)
 * - React Flow 11.x (via @xyflow/react)
 * - Dagre (layout automático)
 */

(function() {
    'use strict';

    // Aguardar carregamento do React Flow
    function waitForReactFlow(callback) {
        if (typeof React !== 'undefined' && typeof ReactFlow !== 'undefined') {
            callback();
        } else {
            setTimeout(() => waitForReactFlow(callback), 100);
        }
    }

    waitForReactFlow(function() {
        const { useState, useCallback, useMemo, useEffect, useRef } = React;
        const ReactFlowLib = ReactFlow;
        
        // Extrair componentes do React Flow
        const ReactFlowComponent = ReactFlowLib.ReactFlow || ReactFlowLib.default;
        const Background = ReactFlowLib.Background;
        const Controls = ReactFlowLib.Controls;
        const MiniMap = ReactFlowLib.MiniMap;
        const useNodesState = ReactFlowLib.useNodesState;
        const useEdgesState = ReactFlowLib.useEdgesState;
        const addEdge = ReactFlowLib.addEdge;
        const Position = ReactFlowLib.Position;
        const Handle = ReactFlowLib.Handle;
        const MarkerType = ReactFlowLib.MarkerType;
        const useReactFlow = ReactFlowLib.useReactFlow;

        // Verificar Dagre
        let dagre = null;
        if (typeof dagreLib !== 'undefined') {
            dagre = dagreLib;
        }

        /**
         * MessageNode Component - Preview completo
         */
        function MessageNode({ data, selected }) {
            const nodeData = data || {};
            const config = nodeData.config || {};
            const customButtons = config.custom_buttons || [];
            const mediaUrl = config.media_url || '';
            const mediaType = config.media_type || 'video';
            const text = config.text || config.message || '';
            const stepType = nodeData.type || 'message';
            const isStartStep = nodeData.is_start || false;

            const typeLabels = {
                message: 'Mensagem',
                payment: 'Pagamento',
                access: 'Acesso',
                content: 'Conteúdo'
            };

            const typeIcons = {
                message: 'fa-comment',
                payment: 'fa-credit-card',
                access: 'fa-key',
                content: 'fa-file-alt'
            };

            return React.createElement('div', {
                className: 'flow-node-message',
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
                    transition: 'transform 0.1s ease-out',
                    cursor: 'move'
                }
            }, [
                // Header
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
                        className: `fas ${typeIcons[stepType] || 'fa-comment'}`,
                        style: { color: '#FFFFFF', fontSize: '18px' }
                    }),
                    React.createElement('span', {
                        key: 'title',
                        style: {
                            color: '#FFFFFF',
                            fontSize: '14px',
                            fontWeight: '600'
                        }
                    }, typeLabels[stepType] || stepType),
                    isStartStep && React.createElement('span', {
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
                                onError: function(e) {
                                    e.target.style.display = 'none';
                                }
                            })
                        ) : (
                            React.createElement('div', {
                                key: 'video',
                                style: {
                                    width: '100%',
                                    height: '100%',
                                    position: 'relative',
                                    background: '#0D0F15',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
                                }
                            }, [
                                React.createElement('i', {
                                    key: 'play',
                                    className: 'fas fa-play',
                                    style: {
                                        color: 'white',
                                        fontSize: '2.5rem',
                                        opacity: 0.7
                                    }
                                })
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
                            marginBottom: customButtons.length > 0 ? '12px' : '0'
                        }
                    }, text.length > 120 ? text.substring(0, 120) + '...' : text),

                    // Botões
                    customButtons.length > 0 && React.createElement('div', {
                        key: 'buttons',
                        style: {
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px'
                        }
                    }, customButtons.map(function(btn, index) {
                        return React.createElement('div', {
                            key: 'btn-' + index,
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
                            }, btn.text || 'Botão ' + (index + 1)),
                            React.createElement(Handle, {
                                key: 'handle',
                                type: 'source',
                                position: Position.Right,
                                id: 'btn-' + index,
                                style: {
                                    width: '12px',
                                    height: '12px',
                                    background: '#E02727',
                                    border: '2px solid #FFFFFF',
                                    borderRadius: '50%',
                                    right: '-6px'
                                }
                            })
                        ]);
                    }))
                ]),

                // Footer
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
                        onClick: function(e) {
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
                        onClick: function(e) {
                            e.stopPropagation();
                            if (window.alpineFlowEditor && window.alpineFlowEditor.removeFlowStep) {
                                window.alpineFlowEditor.removeFlowStep(nodeData.id);
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

                // Handle entrada
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
            ]);
        }

        /**
         * FlowEditorReact Component Principal
         */
        function FlowEditorReact({ alpineContext, canvasId }) {
            const [nodes, setNodes, onNodesChange] = useNodesState([]);
            const [edges, setEdges, onEdgesChange] = useEdgesState([]);
            const reactFlowInstance = useRef(null);
            const { fitView, getViewport, setViewport, zoomTo } = useReactFlow();

            // Converter steps para nodes
            const convertStepsToNodes = useCallback(function(flowSteps, startStepId) {
                if (!flowSteps || !Array.isArray(flowSteps)) return [];
                return flowSteps.map(function(step) {
                    const position = step.position || { x: 100, y: 100 };
                    const isStart = String(step.id) === String(startStepId);
                    return {
                        id: String(step.id),
                        type: 'messageNode',
                        position: { x: position.x || 100, y: position.y || 100 },
                        data: Object.assign({}, step, { is_start: isStart }),
                        selected: false
                    };
                });
            }, []);

            // Converter conexões para edges
            const convertConnectionsToEdges = useCallback(function(flowSteps) {
                if (!flowSteps || !Array.isArray(flowSteps)) return [];
                const edges = [];
                flowSteps.forEach(function(sourceStep) {
                    const config = sourceStep.config || {};
                    const customButtons = config.custom_buttons || [];
                    const connections = sourceStep.connections || {};

                    // Conexões de botões
                    customButtons.forEach(function(button, buttonIndex) {
                        if (button.target_step) {
                            edges.push({
                                id: 'edge-' + sourceStep.id + '-btn-' + buttonIndex + '-' + button.target_step,
                                source: String(sourceStep.id),
                                sourceHandle: 'btn-' + buttonIndex,
                                target: String(button.target_step),
                                type: 'smoothstep',
                                style: { stroke: '#FFFFFF', strokeWidth: 2 },
                                markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
                            });
                        }
                    });

                    // Conexões globais
                    ['next', 'pending', 'retry'].forEach(function(connType) {
                        if (connections[connType]) {
                            edges.push({
                                id: 'edge-' + sourceStep.id + '-' + connType + '-' + connections[connType],
                                source: String(sourceStep.id),
                                target: String(connections[connType]),
                                type: 'smoothstep',
                                style: { 
                                    stroke: connType === 'next' ? '#FFFFFF' : connType === 'pending' ? '#F59E0B' : '#EF4444',
                                    strokeWidth: 2
                                },
                                markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
                            });
                        }
                    });
                });
                return edges;
            }, []);

            // Carregar dados do Alpine
            useEffect(function() {
                if (!alpineContext || !alpineContext.config) return;
                const flowSteps = alpineContext.config.flow_steps || [];
                const startStepId = alpineContext.config.flow_start_step_id;
                const newNodes = convertStepsToNodes(flowSteps, startStepId);
                const newEdges = convertConnectionsToEdges(flowSteps);
                setNodes(newNodes);
                setEdges(newEdges);
                setTimeout(function() {
                    fitView({ padding: 0.2, duration: 400 });
                }, 100);
            }, [alpineContext?.config?.flow_steps, alpineContext?.config?.flow_start_step_id]);

            // Snapping ao grid
            const onNodeDragStop = useCallback(function(event, node) {
                const snappedPosition = {
                    x: Math.round(node.position.x / 20) * 20,
                    y: Math.round(node.position.y / 20) * 20
                };
                setNodes(function(nds) {
                    return nds.map(function(n) {
                        return n.id === node.id ? Object.assign({}, n, { position: snappedPosition }) : n;
                    });
                });
                // Atualizar Alpine
                if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                    const stepIndex = alpineContext.config.flow_steps.findIndex(function(s) {
                        return String(s.id) === String(node.id);
                    });
                    if (stepIndex !== -1) {
                        if (!alpineContext.config.flow_steps[stepIndex].position) {
                            alpineContext.config.flow_steps[stepIndex].position = {};
                        }
                        alpineContext.config.flow_steps[stepIndex].position.x = snappedPosition.x;
                        alpineContext.config.flow_steps[stepIndex].position.y = snappedPosition.y;
                        if (alpineContext.saveConfigDebounced) {
                            alpineContext.saveConfigDebounced();
                        }
                    }
                }
            }, [setNodes, alpineContext]);

            // Atualizar posição durante drag
            const onNodeDrag = useCallback(function(event, node) {
                if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                    const stepIndex = alpineContext.config.flow_steps.findIndex(function(s) {
                        return String(s.id) === String(node.id);
                    });
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
            const onConnect = useCallback(function(params) {
                const newEdge = Object.assign({}, params, {
                    type: 'smoothstep',
                    style: { stroke: '#FFFFFF', strokeWidth: 2 },
                    markerEnd: { type: MarkerType.ArrowClosed, color: '#FFFFFF' }
                });
                setEdges(function(eds) {
                    return addEdge(newEdge, eds);
                });

                // Atualizar Alpine
                if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                    const sourceStepIndex = alpineContext.config.flow_steps.findIndex(function(s) {
                        return String(s.id) === String(params.source);
                    });
                    if (sourceStepIndex !== -1) {
                        const sourceStep = alpineContext.config.flow_steps[sourceStepIndex];
                        const config = sourceStep.config || {};
                        const customButtons = config.custom_buttons || [];
                        if (params.sourceHandle && params.sourceHandle.startsWith('btn-')) {
                            const buttonIndex = parseInt(params.sourceHandle.replace('btn-', ''));
                            if (customButtons[buttonIndex]) {
                                customButtons[buttonIndex].target_step = params.target;
                            }
                        } else {
                            if (!sourceStep.connections) {
                                sourceStep.connections = {};
                            }
                            sourceStep.connections.next = params.target;
                        }
                        if (alpineContext.saveConfigDebounced) {
                            alpineContext.saveConfigDebounced();
                        }
                    }
                }
            }, [setEdges, alpineContext]);

            // Remover edge
            const onEdgesDelete = useCallback(function(deletedEdges) {
                deletedEdges.forEach(function(edge) {
                    if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                        const sourceStepIndex = alpineContext.config.flow_steps.findIndex(function(s) {
                            return String(s.id) === String(edge.source);
                        });
                        if (sourceStepIndex !== -1) {
                            const sourceStep = alpineContext.config.flow_steps[sourceStepIndex];
                            const config = sourceStep.config || {};
                            const customButtons = config.custom_buttons || [];
                            if (edge.sourceHandle && edge.sourceHandle.startsWith('btn-')) {
                                const buttonIndex = parseInt(edge.sourceHandle.replace('btn-', ''));
                                if (customButtons[buttonIndex]) {
                                    customButtons[buttonIndex].target_step = null;
                                }
                            } else {
                                if (sourceStep.connections) {
                                    delete sourceStep.connections.next;
                                }
                            }
                            if (alpineContext.saveConfigDebounced) {
                                alpineContext.saveConfigDebounced();
                            }
                        }
                    }
                });
            }, [alpineContext]);

            // Layout automático
            const organizeLayout = useCallback(function(direction) {
                if (!dagre) {
                    console.warn('⚠️ Dagre não disponível');
                    return;
                }
                const dagreGraph = new dagre.graphlib.Graph();
                dagreGraph.setDefaultEdgeLabel(function() { return {}; });
                dagreGraph.setGraph({ 
                    rankdir: direction === 'vertical' ? 'TB' : 'LR',
                    nodesep: 50,
                    ranksep: 100
                });
                nodes.forEach(function(node) {
                    dagreGraph.setNode(node.id, { width: 280, height: 200 });
                });
                edges.forEach(function(edge) {
                    dagreGraph.setEdge(edge.source, edge.target);
                });
                dagre.layout(dagreGraph);
                const newNodes = nodes.map(function(node) {
                    const nodeWithPosition = dagreGraph.node(node.id);
                    return Object.assign({}, node, {
                        position: {
                            x: nodeWithPosition.x - 140,
                            y: nodeWithPosition.y - 100
                        }
                    });
                });
                setNodes(newNodes);
                if (alpineContext && alpineContext.config && alpineContext.config.flow_steps) {
                    newNodes.forEach(function(node) {
                        const stepIndex = alpineContext.config.flow_steps.findIndex(function(s) {
                            return String(s.id) === String(node.id);
                        });
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
                setTimeout(function() {
                    fitView({ padding: 0.2, duration: 400 });
                }, 100);
            }, [nodes, edges, setNodes, alpineContext, fitView]);

            // Expor métodos globais
            useEffect(function() {
                window.flowEditorReact = {
                    zoomIn: function() {
                        const viewport = getViewport();
                        zoomTo(viewport.zoom + 0.2);
                    },
                    zoomOut: function() {
                        const viewport = getViewport();
                        zoomTo(Math.max(0.2, viewport.zoom - 0.2));
                    },
                    zoomReset: function() {
                        setViewport({ x: 0, y: 0, zoom: 1 });
                    },
                    zoomToFit: function() {
                        fitView({ padding: 0.2, duration: 400 });
                    },
                    organizeVertical: function() { organizeLayout('vertical'); },
                    organizeHorizontal: function() { organizeLayout('horizontal'); },
                    organizeFlowComplete: function() { organizeLayout('vertical'); },
                    organizeByGroups: function() { organizeLayout('vertical'); },
                    updateStep: function(stepId, stepData) {
                        setNodes(function(nds) {
                            return nds.map(function(n) {
                                return String(n.id) === String(stepId) 
                                    ? Object.assign({}, n, { data: Object.assign({}, n.data, stepData) })
                                    : n;
                            });
                        });
                    },
                    deleteStep: function(stepId) {
                        setNodes(function(nds) {
                            return nds.filter(function(n) {
                                return String(n.id) !== String(stepId);
                            });
                        });
                        setEdges(function(eds) {
                            return eds.filter(function(e) {
                                return String(e.source) !== String(stepId) && String(e.target) !== String(stepId);
                            });
                        });
                    },
                    renderAllSteps: function() {
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
            }, [getViewport, zoomTo, setViewport, fitView, organizeLayout, convertStepsToNodes, convertConnectionsToEdges, setNodes, setEdges, alpineContext]);

            const nodeTypes = useMemo(function() {
                return { messageNode: MessageNode };
            }, []);

            return React.createElement('div', {
                style: { width: '100%', height: '100%' }
            }, [
                React.createElement(ReactFlowComponent, {
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
                    snapToGrid: true,
                    snapGrid: [20, 20],
                    minZoom: 0.2,
                    maxZoom: 2,
                    defaultViewport: { x: 0, y: 0, zoom: 1 },
                    fitView: true,
                    panOnScroll: true,
                    panOnDrag: [1, 2],
                    zoomOnScroll: true,
                    zoomOnPinch: true,
                    zoomOnDoubleClick: false,
                    selectionOnDrag: true,
                    translateExtent: [[-10000, -10000], [10000, 10000]],
                    onInit: function(instance) {
                        reactFlowInstance.current = instance;
                    },
                    style: {
                        background: '#0D0F15',
                        backgroundImage: 'radial-gradient(circle, rgba(255, 255, 255, 0.25) 1.5px, transparent 1.5px)',
                        backgroundSize: '20px 20px'
                    }
                }, [
                    React.createElement(Background, { 
                        key: 'bg', 
                        variant: 'dots', 
                        gap: 20, 
                        size: 1, 
                        color: 'rgba(255, 255, 255, 0.1)' 
                    }),
                    React.createElement(Controls, { 
                        key: 'controls', 
                        showInteractive: true, 
                        position: 'bottom-right' 
                    }),
                    React.createElement(MiniMap, { 
                        key: 'minimap',
                        nodeColor: '#E02727',
                        maskColor: 'rgba(0, 0, 0, 0.8)',
                        style: { background: '#13151C' }
                    })
                ])
            ]);
        }

        // Expor globalmente
        window.FlowEditorReact = FlowEditorReact;
        window.MessageNode = MessageNode;
        
        console.log('✅ FlowEditorReact carregado e disponível globalmente');
    });
    
    // Se React Flow não carregar em 10 segundos, logar erro
    setTimeout(function() {
        if (typeof window.FlowEditorReact === 'undefined') {
            console.error('❌ FlowEditorReact não foi carregado após 10 segundos');
            console.error('Verifique se React, ReactDOM e ReactFlow estão carregados via CDN');
        }
    }, 10000);
})();
