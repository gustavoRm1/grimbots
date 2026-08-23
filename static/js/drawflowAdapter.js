/**
 * drawflowAdapter.js — Camada de tradução bidirecional (v2 - outputs posicionais)
 * Drawflow (formato nativo do canvas) ⇄ Grimbots (schema do banco/engine)
 *
 * CONVENÇÃO DE OUTPUTS (posicional, nativa do Drawflow output_1..N):
 *   condition : output_1 = TRUE,  output_2 = FALSE
 *   payment   : output_1 = next,  output_2 = pending, output_3 = retry
 *   buttons   : output_{i+1} = custom_buttons[i]  (0 botões → output_1 = next)
 *   demais    : output_1 = next
 *   access/settings: sem outputs (fim de fluxo / config global)
 *
 * FONTE ÚNICA DE VERDADE (ajustes aprovados na Fase 1):
 * - target_step em custom_buttons[] e conditions[] é escrito SOMENTE aqui
 * - flow_start_step_id pré-existente é PRESERVADO no import; auto-set só em flow novo
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.DrawflowAdapter = factory();
})(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    var TERMINAL_TYPES = ['access', 'settings'];

    function clone(o) { return JSON.parse(JSON.stringify(o || {})); }

    function defaultCondition() {
        return {
            id: 'cond_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
            condition_type: 'payment_status',
            // text_validation
            validation: 'any', value: '',
            // button_click
            button_text: '',
            // payment_status
            status: 'paid',
            // time_elapsed
            minutes: 5, seconds: 0,
            // roteamento
            target_step: '', fallback_step: '',
            max_attempts: null, order: 0
        };
    }

    /**
     * Semântica de cada output na ordem posicional.
     * condType: tipo atual da condição (para saída única em time_elapsed).
     */
    function outputSemantics(type, customButtons, condType) {
        if (type === 'condition') {
            return condType === 'time_elapsed' ? ['after'] : ['true', 'false'];
        }
        if (type === 'payment') return ['next', 'pending', 'retry'];
        if (TERMINAL_TYPES.indexOf(type) !== -1) return [];
        var n = (customButtons || []).length;
        if (n > 0) { var t = []; for (var i = 0; i < n; i++) t.push('btn:' + i); return t; }
        return ['next'];
    }

    function computeOutputs(type, customButtons, condType) {
        return outputSemantics(type, customButtons, condType).map(function (_, i) { return 'output_' + (i + 1); });
    }

    /** key da tag: 'next'→output_1, 'btn:2'→output_3 */
    function tagToKey(tag) {
        if (tag === 'btn:undefined') return null;
        if (tag.indexOf('btn:') === 0) return 'output_' + (parseInt(tag.slice(4), 10) + 1);
        return null; // resolvido pelo índice no array de semantics
    }

    /**
     * toDrawflow(botConfig) → dados para editor.import()
     * Ajuste #2: preserva flow_start_step_id em __grim (não recalcula).
     */
    function toDrawflow(botConfig) {
        botConfig = botConfig || {};
        var steps = botConfig.flow_steps || [];
        var nodes = {};
        var idMap = {};

        steps.forEach(function (step, idx) {
            var nodeId = String(step.id);
            idMap[step.id] = nodeId;

            var type = step.type || 'message';
            var config = clone(step.config);
            config.__meta = {
                type: type,
                order: (step.order !== undefined ? step.order : idx),
                delay_seconds: step.delay_seconds || 0,
                conditions: Array.isArray(step.conditions) ? clone(step.conditions) : [],
                title: step.title || ''
            };

            var outs = {};
            var _c0d = (config.__meta.conditions && config.__meta.conditions[0]) || {};
            computeOutputs(type, config.custom_buttons, _c0d.condition_type).forEach(function (k) { outs[k] = { connections: [] }; });

            nodes[nodeId] = {
                id: nodeId, name: type, data: config, class: type, html: '', typenode: false,
                inputs: { input_1: { connections: [] } },
                outputs: outs,
                pos_x: (step.position && typeof step.position.x === 'number') ? step.position.x : 100 + (idx % 4) * 300,
                pos_y: (step.position && typeof step.position.y === 'number') ? step.position.y : 100 + Math.floor(idx / 4) * 200
            };
        });

        steps.forEach(function (step) {
            var srcId = idMap[step.id];
            if (!srcId || !nodes[srcId]) return;
            var _c0 = (step.conditions && step.conditions[0]) || {};
            var sem = outputSemantics(step.type, step.config && step.config.custom_buttons, _c0.condition_type);

            function keyOf(tag) {
                var i = sem.indexOf(tag);
                return i === -1 ? null : 'output_' + (i + 1);
            }
            function wire(tag, targetStepId) {
                if (!targetStepId) return;
                var k = keyOf(tag); if (!k) return;
                var dstId = idMap[targetStepId];
                if (!dstId || !nodes[dstId]) return;
                // 🔥 DUPLO LADO: Drawflow desenha linhas importadas a partir do
                // lado dos INPUTS; gravar só outputs fazia as linhas sumirem no F5.
                // Formato do lado input (src/drawflow.js L713): {node, input}
                nodes[srcId].outputs[k].connections.push({ node: dstId, output: 'input_1' });
                nodes[dstId].inputs.input_1.connections.push({ node: srcId, input: k });
            }

            var conns = step.connections || {};
            wire('next', conns.next);
            wire('pending', conns.pending);
            wire('retry', conns.retry);

            (step.config && step.config.custom_buttons || []).forEach(function (btn, i) {
                wire('btn:' + i, btn.target_step);
            });

            if (step.type === 'condition' && step.conditions && step.conditions[0]) {
                var c0t = step.conditions[0];
                if (c0t.condition_type === 'time_elapsed') {
                    // ⏱️ saída ÚNICA: após o tempo -> target_step
                    wire('after', c0t.target_step);
                } else {
                    wire('true', c0t.target_step);
                    wire('false', c0t.fallback_step);
                }
            }
        });

        return {
            drawflow: { Home: { data: nodes } },
            __grim: { flow_start_step_id: botConfig.flow_start_step_id || null }
        };
    }

    /**
     * toGrimbots(drawflowData, prevBotConfig) → { flow_steps, flow_start_step_id }
     */
    function toGrimbots(drawflowData, prevBotConfig) {
        prevBotConfig = prevBotConfig || {};
        var home = (drawflowData && drawflowData.drawflow && drawflowData.drawflow.Home) || {};
        var nodes = home.data || {};

        // edges[srcId] = { tag: dstId } — via semântica posicional de cada node
        var edges = {};
        Object.keys(nodes).forEach(function (id) {
            var n = nodes[id];
            var meta = (n.data && n.data.__meta) || {};
            var type = meta.type || n.name || 'message';
            var _c0m = (meta.conditions && meta.conditions[0]) || {};
            var sem = outputSemantics(type, n.data && n.data.custom_buttons, _c0m.condition_type);
            var m = {};
            sem.forEach(function (tag, i) {
                var k = 'output_' + (i + 1);
                var conns = (n.outputs && n.outputs[k] && n.outputs[k].connections) || [];
                if (conns.length > 0) m[tag] = String(conns[0].node);
            });
            edges[id] = m;
        });

        var flowSteps = [];
        Object.keys(nodes).forEach(function (nodeId) {
            var n = nodes[nodeId];
            var meta = n.data.__meta || {};
            var type = meta.type || n.name || 'message';
            var config = clone(n.data);
            delete config.__meta;

            var step = {
                id: String(nodeId),
                type: type,
                order: (meta.order !== undefined ? meta.order : 0),
                config: config,
                connections: {},
                conditions: Array.isArray(meta.conditions) ? clone(meta.conditions) : [],
                delay_seconds: meta.delay_seconds || 0,
                position: { x: n.pos_x || 0, y: n.pos_y || 0 }
            };

            var e = edges[nodeId] || {};
            if (e.next) step.connections.next = e.next;
            if (e.pending) step.connections.pending = e.pending;
            if (e.retry) step.connections.retry = e.retry;

            // 🔥 ALIAS PAYMENT: engine lê 'amount'/'description' no override por step
            // (bot_manager: "Usar valores do step se especificados")
            if (type === 'payment') {
                if (config.price !== null && config.price !== undefined && config.price !== '') {
                    config.amount = Number(config.price);
                }
                var _desc = config.product_name || config.button_text || '';
                if (_desc && !config.description) config.description = _desc;
            }

            // AJUSTE #1: adapter é o ÚNICO que escreve target_step
            (step.config.custom_buttons || []).forEach(function (btn, i) {
                btn.target_step = e['btn:' + i] || '';
            });

            if (type === 'condition') {
                if (!step.conditions || step.conditions.length === 0) step.conditions = [defaultCondition()];
                var _c0e = step.conditions[0];
                if (_c0e.condition_type === 'time_elapsed') {
                    // ⏱️ saída única: output_1 = target (após o tempo)
                    _c0e.target_step = e['after'] || e['true'] || '';
                    _c0e.fallback_step = '';
                } else {
                    _c0e.target_step = e['true'] || '';
                    _c0e.fallback_step = e['false'] || '';
                }
                step.conditions[0].order = 0;
            }

            // 🔥 FIX CRÍTICO: conditions[] só existe em nós condition.
            // Em qualquer outro tipo, limpar (evita pausa indevida no engine).
            if (type !== 'condition' && step.conditions && step.conditions.length > 0) {
                step.conditions = [];
            }

            flowSteps.push(step);
        });

        flowSteps.sort(function (a, b) { return (a.order || 0) - (b.order || 0); });

        // Subscription injection: injeta config.subscription no payment step pai
        var subSteps = flowSteps.filter(function(s) { return s.type === 'subscription'; });
        subSteps.forEach(function(sub) {
            var parentPayment = flowSteps.find(function(s) {
                return s.type === 'payment' &&
                    (s.connections.next === sub.id || s.connections.pending === sub.id);
            });
            if (parentPayment) {
                parentPayment.config.subscription = {
                    enabled: true,
                    duration_type: sub.config.duration_type || 'days',
                    duration_value: sub.config.duration_value || 30,
                    vip_chat_id: sub.config.vip_chat_id || '',
                    vip_group_link: sub.config.vip_group_link || ''
                };
            } else {
                console.warn('⚠️ Subscription ' + sub.id + ' sem payment step pai');
            }
        });
        flowSteps = flowSteps.filter(function(s) { return s.type !== 'subscription'; });

        // AJUSTE #2: preservar start pré-existente
        var prevStart = prevBotConfig.flow_start_step_id || null;
        var onCanvas = {};
        flowSteps.forEach(function (s) { onCanvas[s.id] = true; });

        var startId;
        if (prevStart && onCanvas[String(prevStart)]) startId = String(prevStart);
        else if (prevStart) startId = null;
        else if (flowSteps.length > 0) startId = flowSteps[0].id;
        else startId = null;

        return { flow_steps: flow_steps_sorted(flowSteps), flow_start_step_id: startId };
    }

    function flow_steps_sorted(s) { return s; } // já ordenado acima; explícito p/ clareza

    return {
        toDrawflow: toDrawflow,
        toGrimbots: toGrimbots,
        computeOutputs: computeOutputs,
        outputSemantics: outputSemantics,
        _internals: { TERMINAL_TYPES: TERMINAL_TYPES, defaultCondition: defaultCondition }
    };
});
