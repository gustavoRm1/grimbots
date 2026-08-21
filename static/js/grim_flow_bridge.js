/**
 * grim_flow_bridge.js — Ponte Drawflow ⇄ Alpine (bot_config.html)
 * Substitui o stack jsPlumb+flow_editor.js mantendo a fachada window.flowEditor.
 *
 * Fonte de verdade:
 *  - Canvas (Drawflow) manda durante a edição
 *  - alpine.config é sincronizado em: save (syncToConfig), criar/remover node (espelho leve),
 *    e modal save (applyStep)
 *  - target_step / flow_start_step_id SEMPRE via DrawflowAdapter (ajustes Fase 1)
 */
(function () {
    'use strict';

    const TYPES = {
        message:      { label:'Mensagem',     icon:'fa-comment-dots',      color:'#60A5FA' },
        content:      { label:'Conteudo',     icon:'fa-photo-video',       color:'#818CF8' },
        audio:        { label:'Audio',        icon:'fa-microphone',        color:'#F472B6' },
        video:        { label:'Video',        icon:'fa-video',             color:'#C084FC' },
        buttons:      { label:'Botoes',       icon:'fa-mouse-pointer',     color:'#34D399' },
        payment:      { label:'Pagamento',    icon:'fa-qrcode',            color:'#4ADE80' },
        access:       { label:'Acesso',       icon:'fa-key',               color:'#FB923C' },
        condition:    { label:'Condicao',     icon:'fa-code-branch',       color:'#FFB800' },
        subscription: { label:'Assinatura',   icon:'fa-crown',             color:'#FFB800' },
        downsell:     { label:'Downsell',     icon:'fa-arrow-down',        color:'#EF4444' },
        upsell:       { label:'Upsell',       icon:'fa-arrow-up',          color:'#22C55E' },
        redirect:     { label:'Redirecionar', icon:'fa-external-link-alt', color:'#C084FC' },
        settings:     { label:'Configuracoes',icon:'fa-cog',               color:'#9CA3AF' }
    };
    const OUT_LABELS = { condition:['TRUE','FALSE'], payment:['PAGO','PENDENTE','RETRY'] };

    const S = { editor:null, alpine:null, inited:false, canvasWasEmpty:true };

    /* ───────── CSS ───────── */
    function injectCss() {
        if (document.getElementById('grim-flow-css')) return;
        const st = document.createElement('style');
        st.id = 'grim-flow-css';
        st.textContent = `
        #drawflow-canvas{width:100%;height:100%;background:#0D0F15;border-radius:12px;}
        .drawflow .drawflow-node{background:#13151C;border:1px solid #2A2D36;border-radius:12px;min-width:220px;color:#E5E7EB;box-shadow:0 2px 12px rgba(0,0,0,.35);}
        .drawflow .drawflow-node:hover{border-color:#FFB800;}
        .drawflow .drawflow-node.selected{border-color:#FFB800!important;box-shadow:0 0 0 2px rgba(255,184,0,.4);}
        .drawflow .input,.drawflow .output{width:14px;height:14px;border-radius:50%;cursor:crosshair;}
        /* 🔥 Cores travadas em TODOS os estados (normal/hover/node selecionado) */
        .drawflow .input{left:-8px;background:#10B981!important;border:2px solid #fff!important;}
        .drawflow .output{right:-8px;background:#FFFFFF!important;border:2px solid #0D0F15!important;}
        .drawflow .output:hover{background:#FFB800!important;transform:scale(1.25);}
        .drawflow .drawflow-node.selected .input{background:#10B981!important;}
        .drawflow .drawflow-node.selected .output{background:#FFFFFF!important;}
        /* Condição: saída 1 = VERDE (TRUE) | saída 2 = VERMELHA (FALSE) */
        .drawflow .drawflow-node.condition .output_1{background:#10B981!important;border-color:#fff!important;}
        .drawflow .drawflow-node.condition .output_2{background:#EF4444!important;border-color:#fff!important;}
        /* Pagamento: PAGO verde | PENDENTE amarela | RETRY vermelha */
        .drawflow .drawflow-node.payment .output_1{background:#10B981!important;border-color:#fff!important;}
        .drawflow .drawflow-node.payment .output_2{background:#F59E0B!important;border-color:#fff!important;}
        .drawflow .drawflow-node.payment .output_3{background:#EF4444!important;border-color:#fff!important;}
        .drawflow svg.connection path.main-path{stroke:#fff;stroke-width:2.5;fill:none;stroke-opacity:.9;}
        .drawflow svg.connection.selected path.main-path,.drawflow svg.connection:hover path.main-path{stroke:#FFB800;stroke-width:3.5;}
        .df-head{display:flex;align-items:center;gap:9px;padding:9px 12px;background:#1C1E26;border-radius:12px 12px 0 0;border-bottom:1px solid #2A2D36;position:relative;}
        .df-icon{width:26px;height:26px;min-width:26px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:11px;}
        .df-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;flex:1;color:#E5E7EB;}
        .df-star{position:absolute;top:-9px;right:-6px;font-size:16px;cursor:pointer;filter:drop-shadow(0 0 4px rgba(255,184,0,.8));display:none;}
        .drawflow-node.is-start .df-star{display:block;animation:gfpulse 2s infinite;}
        @keyframes gfpulse{50%{transform:scale(1.2);}}
        .drawflow-node.is-start{border-color:#FFB800!important;box-shadow:0 0 0 2px rgba(255,184,0,.35),0 0 20px rgba(255,184,0,.25)!important;}
        .df-body{padding:10px 12px;font-size:11px;line-height:1.5;color:#c9cbd3;min-height:38px;max-height:80px;overflow:hidden;word-break:break-word;}
        .df-body.placeholder{color:#6B7280;font-style:italic;}
        .df-out-label{font-size:8px;font-weight:700;text-transform:uppercase;color:#8B8B93;text-align:right;padding:0 14px 2px 0;margin-top:-4px;}
        .df-actions{display:flex;gap:6px;justify-content:center;padding:6px;border-top:1px solid #2A2D36;}
        .df-btn{width:30px;height:26px;border:none;border-radius:6px;background:#E02727;color:#fff;cursor:pointer;font-size:11px;z-index:5;position:relative;}
        .df-btn.edit{background:#242836;}.df-btn.edit:hover{background:#333;}
        .df-btn:hover{filter:brightness(1.2);}
        `;
        document.head.appendChild(st);
    }

    /* ───────── NODE HTML ───────── */
    function nodeHtml(type) {
        const t = TYPES[type] || {label:type,icon:'fa-circle',color:'#888'};
        return `<div class="df-head">
            <div class="df-icon" style="background:${t.color}22;border:1px solid ${t.color}44;color:${t.color}"><i class="fas ${t.icon}"></i></div>
            <div class="df-title">${t.label}</div>
            <div class="df-star" title="Definir como inicio" onclick="event.stopPropagation();GrimFlow.setStart(parentNodeIdGf(this))">⭐</div>
        </div>
        <div class="df-body placeholder" data-df-preview>Nada configurado</div>
        ${(OUT_LABELS[type]||[]).map(l=>`<div class="df-out-label">${l}</div>`).join('')}
        <div class="df-actions">
            <button class="df-btn edit" title="Editar" onclick="event.stopPropagation();window.alpineFlowEditor && window.alpineFlowEditor.openStepModal(parentNodeIdGf(this))"><i class="fas fa-pen"></i></button>
            <button class="df-btn" title="Remover" onclick="event.stopPropagation();GrimFlow.removeNode(parentNodeIdGf(this))"><i class="fas fa-trash"></i></button>
        </div>`;
    }
    window.parentNodeIdGf = function (el) {
        while (el && !el.classList.contains('drawflow-node')) el = el.parentElement;
        return el ? el.id.replace('node-','') : null;
    };

    function defaultData(type) {
        return { message:'', media_url:'', media_type:'video',
            // áudio complementar (offer_sender lê)
            audio_enabled:false, audio_url:'',
            // preço (offer_sender lê pricing_mode/discount_percentage)
            pricing_mode:'fixed', discount_percentage:50,
            price:null, description:'', product_name:'',
            button_text:'', access_link:'', redirect_url:'',
            duration_type:'days', duration_value:null,
            vip_chat_id:'', vip_group_link:'', trigger_product:'', delay_minutes:5,
            open_in:'browser', success_message:'', pending_message:'',
            meta_pixel_id:'', condition_type:'payment_status', condition_value:'',
            custom_buttons:[],
            subscription:{ enabled:false, duration_type:'days', duration_value:null,
                           vip_chat_id:'', vip_group_link:'' },
            __meta:{ type, order:0, delay_seconds:0, conditions:[], title:'' } };
        // 🔥 SEGURANÇA: bot_token REMOVIDO do bloco — troca de token só pelo
        // endpoint dedicado (/api/bots/{id}/token), nunca via canvas
    }

    function refreshPreview(id) {
        try {
            const d = S.editor.getNodeFromId(id);
            const el = document.getElementById('node-'+id);
            if (!d || !el) return;
            const body = el.querySelector('[data-df-preview]');
            const c = d.data; let txt = '';
            if (d.name==='payment') txt = `${c.product_name||'Produto'} — R$ ${(c.price??0)}`;
            else if (d.name==='subscription') txt = c.vip_chat_id ? `👑 VIP: ${c.duration_value||'?'} ${c.duration_type||'dias'} de acesso` : '👑 Acesso VIP';
            else if (d.name==='downsell'||d.name==='upsell') txt = c.pricing_mode==='percentage'
                ? `${c.product_name||d.name} — -${c.discount_percentage??50}%`
                : `${c.product_name||d.name} — R$ ${(c.price??0)}`;
            else if (d.name==='redirect') txt = `${c.button_text||'Acessar'} → ${c.redirect_url||'?'}`;
            else if (d.name==='access') txt = c.access_link || 'Liberar acesso';
            else if (d.name==='settings') txt = 'Configurações globais';
            else if (d.name==='condition') {
                const cd = (c.__meta && c.__meta.conditions && c.__meta.conditions[0]) || {};
                if (cd.condition_type==='text_validation') txt = `Se resposta ${cd.validation||'any'}${cd.value ? ' = "'+cd.value+'"' : ''}`;
                else if (cd.condition_type==='button_click') txt = `Se clicar "${cd.button_text||'?'}"`;
                else if (cd.condition_type==='time_elapsed') txt = `Se passarem ${cd.minutes??5} min`;
                else txt = `Se pagamento == ${cd.status||'paid'}`;
            }
            else if (d.name==='audio') txt = c.audio_url ? '🎙️ Áudio carregado' : '';
            else if ((c.custom_buttons||[]).length) txt = c.custom_buttons.map(b=>`[${b.text||'?'}]`).join(' ');
            else txt = c.message || '';
            body.textContent = txt || 'Nada configurado';
            body.classList.toggle('placeholder', !txt);
        } catch(e){}
    }

    function refreshStartBadges() {
        const start = String(S.alpine?.config?.flow_start_step_id ?? '');
        document.querySelectorAll('#drawflow-canvas .drawflow-node').forEach(n => {
            n.classList.toggle('is-start', n.id.replace('node-','') === start);
        });
    }

    /* ───────── INIT ───────── */
    function init(alpine) {
        injectCss();
        if (S.inited) return true;
        const el = document.getElementById('drawflow-canvas');
        if (!el || typeof Drawflow === 'undefined' || typeof DrawflowAdapter === 'undefined') return false;

        S.alpine = alpine;
        window.alpineFlowEditor = alpine;

        editor_create(el);

        // Espelho leve no alpine.config p/ overlays (empty-state etc.)
        S.editor.on('nodeCreated', function (newId) {
            const idStr = String(newId);
            const node = S.editor.getNodeFromId(newId);
            const type = node?.name || 'message';
            const steps = S.alpine.config.flow_steps;
            if (!steps.find(s => String(s.id) === idStr)) {
                steps.push({ id:idStr, type, order:steps.length,
                    config:{custom_buttons:[]}, connections:{}, conditions:[],
                    delay_seconds:0, position:{x:0,y:0} });
            }
            // AJUSTE #2: auto-set só se canvas estava vazio e sem start prévio
            if (S.canvasWasEmpty && !S.alpine.config.flow_start_step_id) {
                S.alpine.config.flow_start_step_id = idStr;
            }
            refreshPreview(idStr);
            refreshStartBadges();
        });

        S.editor.on('nodeRemoved', function (remId) {
            const idStr = String(remId);
            const steps = S.alpine.config.flow_steps;
            const i = steps.findIndex(s => String(s.id) === idStr);
            if (i !== -1) steps.splice(i, 1);
            if (String(S.alpine.config.flow_start_step_id) === idStr) {
                S.alpine.config.flow_start_step_id = null;
            }
            refreshStartBadges();
        });

        loadFromAlpine();
        S.inited = true;
        return true;
    }

    function editor_create(el) {
        S.editor = new Drawflow(el);
        S.editor.reroute = true;
        S.editor.start();
    }

    function loadFromAlpine() {
        const dfData = DrawflowAdapter.toDrawflow(S.alpine.config);
        S.canvasWasEmpty = Object.keys(dfData.drawflow.Home.data).length === 0;
        S.editor.import(dfData);
        Object.keys(dfData.drawflow.Home.data).forEach(id => refreshPreview(id));

        // 🔥 SETTINGS: injeta valores GLOBAIS atuais no nó (usuário edita em cima do real)
        injectGlobalIntoSettingsNode();

        refreshStartBadges();
    }

    function findSettingsNodeId() {
        const data = S.editor.drawflow.drawflow.Home.data;
        const id = Object.keys(data).find(id => (data[id].data?.__meta?.type || data[id].name) === 'settings');
        return id || null;
    }

    function injectGlobalIntoSettingsNode() {
        const id = findSettingsNodeId();
        if (!id) return;
        const cfg = S.alpine.config;
        const node = S.editor.getNodeFromId(id);
        const d = JSON.parse(JSON.stringify(node.data));
        d.access_link = cfg.access_link || '';
        d.success_message = cfg.success_message || '';
        d.pending_message = cfg.pending_message || '';
        if (cfg.meta_pixel_id) d.meta_pixel_id = cfg.meta_pixel_id;
        S.editor.updateNodeDataFromId(id, d);
    }

    /* ───────── API PÚBLICA ───────── */
    const GrimFlow = {
        init(alpine) { return init(alpine); },

        /** chamado quando aba flow fica visível ou toggle liga */
        ensureInit(alpine) {
            alpine = alpine || S.alpine || window.alpineFlowEditor;
            if (!alpine) return false;
            if (!S.inited) {
                // container precisa estar visível (x-show) p/ medidas do Drawflow
                const el = document.getElementById('drawflow-canvas');
                if (!el || el.offsetParent === null) return false;
                return init(alpine);
            }
            return true;
        },

        destroy() {
            if (S.editor) { try { S.editor.destroy(); } catch(e){} }
            S.editor = null; S.inited = false;
        },

        isReady() { return S.inited && !!S.editor; },

        addNode(type) {
            if (!this.ensureInit()) return;
            const n = S.alpine.config.flow_steps.length;
            const outs = DrawflowAdapter.computeOutputs(type, []).length;
            const x = 140 + (n % 4) * 290 + Math.random()*40;
            const y = 90 + Math.floor(n / 4) * 190 + Math.random()*30;
            S.editor.addNode(type, 1, outs, x, y, type, defaultData(type), nodeHtml(type));
        },

        removeNode(id) {
            if (!S.isReady()) return;
            if (!confirm('Remover este bloco?')) return;
            S.editor.removeNodeId('node-'+id);
        },

        setStart(id) {
            if (!S.alpine) return;
            S.alpine.config.flow_start_step_id = String(id);
            refreshStartBadges();
        },

        /** modal saveStep → reflete no canvas */
        applyStep(step) {
            if (!S.isReady()) return;
            const id = String(step.id);
            try { S.editor.getNodeFromId(id); } catch(e) { return; } // não está no canvas
            const data = JSON.parse(JSON.stringify(step.config || {}));
            data.__meta = {
                type: step.type,
                order: step.order || 0,
                delay_seconds: step.delay_seconds || 0,
                conditions: JSON.parse(JSON.stringify(step.conditions || [])),
                title: step.title || ''
            };
            S.editor.updateNodeDataFromId(id, data);
            this._syncOutputs(id, step.type, data.custom_buttons);
            refreshPreview(id);
        },

        _syncOutputs(id, type, buttons) {
            const desired = DrawflowAdapter.computeOutputs(type, buttons);
            let keys = () => Object.keys(S.editor.drawflow.drawflow.Home.data[id].outputs)
                              .sort((a,b)=>(+a.slice(7))-(+b.slice(7)));
            while (keys().length > desired.length) S.editor.removeNodeOutput(id, keys().pop());
            while (keys().length < desired.length) {
                S.editor.addNodeOutput(id);
            }
            S.editor.updateConnectionNodes(id);
        },

        /** saveConfig → exporta canvas pro schema grimbots dentro do config */
        syncToConfig(config) {
            if (!S.isReady()) return false;
            const exported = S.editor.export();
            const grim = DrawflowAdapter.toGrimbots(exported, config);
            config.flow_steps = grim.flow_steps;
            config.flow_start_step_id = grim.flow_start_step_id;

            // 🔥 SETTINGS: aplica campos do nó no CONFIG GLOBAL (é onde o engine lê!)
            const settingsStep = config.flow_steps.find(s => s.type === 'settings');
            if (settingsStep) {
                const c = settingsStep.config || {};
                if (c.access_link !== undefined && c.access_link !== '') config.access_link = c.access_link;
                if (c.success_message !== undefined) config.success_message = c.success_message;
                if (c.pending_message !== undefined) config.pending_message = c.pending_message;
                if (c.meta_pixel_id !== undefined && c.meta_pixel_id !== '') config.meta_pixel_id = c.meta_pixel_id;
                console.log('✅ Bloco Configuracoes aplicado ao config global');
            }
            return true;
        },

        clearCanvas() {
            if (!S.isReady()) return;
            if (!confirm('Apagar TODO o fluxo?')) return;
            Object.keys(S.editor.drawflow.drawflow.Home.data).forEach(id => {
                try { S.editor.removeNodeId('node-'+id); } catch(e){}
            });
            if (S.alpine) { S.alpine.config.flow_steps = []; S.alpine.config.flow_start_step_id = null; }
        },

        /* Fachada compatível com onclicks antigos do template */
        zoomIn(){ S.editor && S.editor.zoom_in(); },
        zoomOut(){ S.editor && S.editor.zoom_out(); },
        zoomReset(){ S.editor && S.editor.zoom_reset(); },
        renderAllSteps(){ /* noop — Drawflow mantém estado vivo */ },
        updateStepEndpoints(){ /* noop — syncOutputs cobre */ },
        deleteStep(id){ this.removeNode(id); }
    };

    window.GrimFlow = GrimFlow;
    window.flowEditor = GrimFlow; // fachada p/ template antigo
})();
