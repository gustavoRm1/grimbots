/**
 * test_adapter.js — Testes dos 5 cenários aprovados (Fase 2)
 * Roda: node test_adapter.js
 */
const adapter = require('./static/js/drawflowAdapter.js');

let passed = 0, failed = 0;
function check(name, cond, detail) {
    if (cond) { passed++; console.log(`  PASS  ${name}`); }
    else { failed++; console.log(`  FAIL  ${name}${detail ? ' -> ' + JSON.stringify(detail) : ''}`); }
}
function section(t) { console.log('\n' + '='.repeat(64) + '\n' + t + '\n' + '='.repeat(64)); }

// ─────────────────────────────────────────────────────────────
// TESTE 1: Flow do zero, primeiro node → flow_start_step_id auto-setado
// ─────────────────────────────────────────────────────────────
section('TESTE 1: auto-set de flow_start_step_id no primeiro node (flow novo)');
{
    // Simula: usuário criou 1 node no canvas (via editor), exportou
    const drawflowData = {
        drawflow: { Home: { data: {
            'step_A': { id:'step_A', name:'message', class:'message', data:{ message:'oi', __meta:{type:'message',order:0,delay_seconds:0} },
                        inputs:{input_1:{connections:[]}}, outputs:{output_1:{connections:[]}}, pos_x:100, pos_y:100 }
        }}},
        __grim: { flow_start_step_id: null }
    };
    const result = adapter.toGrimbots(drawflowData, { flow_start_step_id: null }); // canvas estava vazio antes
    check('flow_start_step_id == primeiro node', result.flow_start_step_id === 'step_A', result.flow_start_step_id);

    // Segundo node adicionado depois — start NÃO muda
    drawflowData.drawflow.Home.data['step_B'] = { id:'step_B', name:'payment', class:'payment',
        data:{ __meta:{type:'payment',order:1,delay_seconds:0} },
        inputs:{input_1:{connections:[{node:'step_A',output:'output_1'}]}},
        outputs:{output_1:{connections:[]},output_pending:{connections:[]},output_retry:{connections:[]}},
        pos_x:400, pos_y:100 };
    drawflowData.drawflow.Home.data['step_A'].outputs.output_1.connections.push({node:'step_B',output:'input_1'});
    const r2 = adapter.toGrimbots(drawflowData, { flow_start_step_id: 'step_A' });
    check('start preservado após 2º node', r2.flow_start_step_id === 'step_A', r2.flow_start_step_id);
}

// ─────────────────────────────────────────────────────────────
// TESTE 2: Flow existente com flow_start_step_id no banco → NÃO muda
// ─────────────────────────────────────────────────────────────
section('TESTE 2: preserva flow_start_step_id do banco no load');
{
    const botConfig = {
        flow_start_step_id: 'step_B',
        flow_steps: [
            { id:'step_A', type:'message', order:0, config:{message:'a'}, connections:{next:'step_B'}, conditions:[], delay_seconds:0, position:{x:100,y:100} },
            { id:'step_B', type:'payment', order:1, config:{price:97}, connections:{}, conditions:[], delay_seconds:0, position:{x:400,y:100} }
        ]
    };
    const df = adapter.toDrawflow(botConfig);                 // import
    const back = adapter.toGrimbots(df, botConfig);           // export
    check('start do banco preservado (não vira step_A/order 0)', back.flow_start_step_id === 'step_B', back.flow_start_step_id);

    // Start deletado do canvas → vira null (não aponta pra fantasma)
    delete df.drawflow.Home.data['step_B'];
    df.drawflow.Home.data['step_A'].outputs.output_1.connections = [];
    const r3 = adapter.toGrimbots(df, botConfig);
    check('start deletado → null (sem referência fantasma)', r3.flow_start_step_id === null, r3.flow_start_step_id);
}

// ─────────────────────────────────────────────────────────────
// TESTE 3: Condição true/false → target_step/fallback_step sobrevivem a save+reload
// ─────────────────────────────────────────────────────────────
section('TESTE 3: condição true/false round-trip');
{
    const botConfig = {
        flow_start_step_id: 'cond_1',
        flow_steps: [
            { id:'cond_1', type:'condition', order:0,
              config:{condition_type:'payment_status', condition_value:'paid'},
              connections:{}, 
              conditions:[{id:'c1',condition_type:'payment_status',validation:'any',value:'paid',
                           target_step:'', fallback_step:'', max_attempts:null, order:0}],
              delay_seconds:0, position:{x:100,y:100} },
            { id:'ok_step', type:'access', order:1, config:{access_link:'https://ok'}, connections:{}, conditions:[], delay_seconds:0, position:{x:400,y:50} },
            { id:'fail_step', type:'downsell', order:2, config:{price:47}, connections:{}, conditions:[], delay_seconds:0, position:{x:400,y:250} }
        ]
    };
    // Usuário desenha: output_1(true) → ok_step, output_2(false) → fail_step
    const df = adapter.toDrawflow(botConfig);
    df.drawflow.Home.data['cond_1'].outputs.output_1.connections.push({node:'ok_step', output:'input_1'});
    df.drawflow.Home.data['cond_1'].outputs.output_2.connections.push({node:'fail_step', output:'input_1'});

    // SAVE (o que iria pro banco)
    const saved = adapter.toGrimbots(df, botConfig);
    const cond = saved.flow_steps.find(s => s.id === 'cond_1').conditions[0];
    check('target_step == ok_step (engine lê conditions[].target_step)', cond.target_step === 'ok_step', cond);
    check('fallback_step == fail_step', cond.fallback_step === 'fail_step', cond);
    check('sem resíduos true_step_id/false_step_id', !('true_step_id' in cond) && !('false_step_id' in cond));

    // RELOAD da página: banco → import → export de novo
    const df2 = adapter.toDrawflow(saved);
    const reloaded = adapter.toGrimbots(df2, saved);
    const cond2 = reloaded.flow_steps.find(s => s.id === 'cond_1').conditions[0];
    check('round-trip: target_step estável', cond2.target_step === 'ok_step', cond2);
    check('round-trip: fallback_step estável', cond2.fallback_step === 'fail_step', cond2);
}

// ─────────────────────────────────────────────────────────────
// TESTE 4: Botão customizado → custom_buttons[n].target_step round-trip
// ─────────────────────────────────────────────────────────────
section('TESTE 4: botão customizado target_step round-trip');
{
    const botConfig = {
        flow_start_step_id: 'msg_1',
        flow_steps: [
            { id:'msg_1', type:'buttons', order:0,
              config:{ message:'Escolha', custom_buttons:[{text:'Ver planos', target_step:''},{text:'Suporte', target_step:''}] },
              connections:{}, conditions:[], delay_seconds:0, position:{x:100,y:100} },
            { id:'planos', type:'content', order:1, config:{message:'planos'}, connections:{}, conditions:[], delay_seconds:0, position:{x:400,y:50} },
            { id:'suporte', type:'redirect', order:2, config:{redirect_url:'https://t.me/sup'}, connections:{}, conditions:[], delay_seconds:0, position:{x:400,y:250} }
        ]
    };
    const df = adapter.toDrawflow(botConfig);
    // Desenho: btn0 → output_1 → planos, btn1 → output_2 → suporte
    df.drawflow.Home.data['msg_1'].outputs.output_1.connections.push({node:'planos', output:'input_1'});
    df.drawflow.Home.data['msg_1'].outputs.output_2.connections.push({node:'suporte', output:'input_1'});

    const saved = adapter.toGrimbots(df, botConfig);
    const msg = saved.flow_steps.find(s => s.id === 'msg_1');
    check('btn[0].target_step == planos', msg.config.custom_buttons[0].target_step === 'planos', msg.config.custom_buttons);
    check('btn[1].target_step == suporte', msg.config.custom_buttons[1].target_step === 'suporte');
    check('connections.next NÃO setado quando há botões', !msg.connections.next, msg.connections);

    // Reload
    const df2 = adapter.toDrawflow(saved);
    const re = adapter.toGrimbots(df2, saved);
    const msg2 = re.flow_steps.find(s => s.id === 'msg_1');
    check('round-trip btn[0]', msg2.config.custom_buttons[0].target_step === 'planos');
    check('round-trip btn[1]', msg2.config.custom_buttons[1].target_step === 'suporte');
}

// ─────────────────────────────────────────────────────────────
// TESTE 5: Flow com 12 nodes conectados → refresh full, ZERO conexões perdidas
// ─────────────────────────────────────────────────────────────
section('TESTE 5: 12 nodes, refresh full (import→export→import→export), zero perdas');
{
    // Monta cadeia: msg → payment(pending/retry) → cond(true/false) → buttons(2 btns) → ... total 12
    const steps = [];
    const types = ['message','payment','condition','buttons','content','audio','video','subscription','downsell','upsell','redirect','message'];
    types.forEach((t, i) => {
        steps.push({ id:'n'+i, type:t, order:i, config:{message:'m'+i, price:10+i,
            custom_buttons: t==='buttons' ? [{text:'A',target_step:''},{text:'B',target_step:''}] : []},
            connections:{}, 
            conditions: t==='condition' ? [{id:'cc',condition_type:'payment_status',validation:'any',value:'',target_step:'',fallback_step:'',max_attempts:null,order:0}] : [],
            delay_seconds:0, position:{x:(i%4)*300, y:Math.floor(i/4)*200} });
    });
    // fios em TAGS semânticas: cond: true,false | payment: next,pending,retry | btns: btn:i
    const wires = [
        ['n0','next','n1'], ['n1','next','n2'], ['n1','pending','n11'], ['n1','retry','n10'],
        ['n2','true','n3'], ['n2','false','n9'],
        ['n3','btn:0','n4'], ['n3','btn:1','n5'],
        ['n4','next','n6'], ['n5','next','n7'], ['n6','next','n8'], ['n7','next','n8'],
        ['n8','next','n9']
    ];
    // helper: aplica fios num drawflowData (tag → chave posicional via semântica do node)
    function wireAll(df) {
        wires.forEach(([src,tag,dst]) => {
            const node = df.drawflow.Home.data[src];
            if (!node) throw new Error('node ausente: '+src);
            const sem = adapter.outputSemantics(node.data.__meta.type, node.data.custom_buttons);
            const idx = sem.indexOf(tag);
            if (idx === -1) throw new Error('tag '+tag+' não existe em '+src+' ('+sem.join(',')+')');
            const key = 'output_' + (idx + 1);
            if (!node.outputs[key]) throw new Error('output ausente: '+src+'.'+key);
            node.outputs[key].connections.push({node:dst, output:'input_1'});
        });
        return df;
    }
    let botConfig = { flow_start_step_id:'n0', flow_steps:steps };

    // helper: conta edges totais num schema grimbots
    function countEdges(gc) {
        let n = 0;
        gc.flow_steps.forEach(s => {
            ['next','pending','retry'].forEach(k => { if (s.connections[k]) n++; });
            (s.config.custom_buttons||[]).forEach(b => { if (b.target_step) n++; });
            (s.conditions||[]).forEach(c => { if (c.target_step) n++; if (c.fallback_step) n++; });
        });
        return n;
    }

    const TOTAL = wires.length; // 13 conexões

    // Ciclo completo: banco → import → (usuário mexe nada) → export → "salva" → reload → import → export
    let df1 = wireAll(adapter.toDrawflow(botConfig));
    let gc1 = adapter.toGrimbots(df1, botConfig);
    check(`save 1: ${TOTAL}/${TOTAL} conexões`, countEdges(gc1) === TOTAL, countEdges(gc1));

    let df2 = adapter.toDrawflow(gc1);          // reload da página
    let gc2 = adapter.toGrimbots(df2, gc1);     // save sem mexer em nada
    check(`refresh+save: ${TOTAL}/${TOTAL} conexões`, countEdges(gc2) === TOTAL, countEdges(gc2));

    // Verifica fio a fio que cada conexão sobreviveu com o MESMO destino (posicional)
    let allWired = wires.every(([src,out,dst]) => {
        const s = gc2.flow_steps.find(x => x.id === src);
        if (!s) return false;
        const sem = adapter.outputSemantics(s.type, s.config.custom_buttons);
        const idx = sem.indexOf(out);              // ex: 'true'→0, 'btn:0'→0, 'pending'→1
        if (idx === -1) return false;
        if (out === 'next') return s.connections.next === dst;
        if (out === 'pending') return s.connections.pending === dst;
        if (out === 'retry') return s.connections.retry === dst;
        if (out.startsWith('btn:')) { const i=+out.slice(4); return (s.config.custom_buttons[i]||{}).target_step === dst; }
        if (out === 'true') return (s.conditions[0]||{}).target_step === dst;
        if (out === 'false') return (s.conditions[0]||{}).fallback_step === dst;
        return false;
    });
    check('todos os 13 fios com destino EXATO preservado', allWired);

    // start preservado no meio de tudo
    check('start n0 preservado nos 2 ciclos', gc1.flow_start_step_id==='n0' && gc2.flow_start_step_id==='n0');

    // posições preservadas (canvas não "desmancha")
    const posOK = gc2.flow_steps.every(s => {
        const orig = steps.find(o => o.id===s.id).position;
        return s.position.x===orig.x && s.position.y===orig.y;
    });
    check('posições x/y preservadas (layout estável)', posOK);
}

// ─────────────────────────────────────────────────────────────
console.log('\n' + '='.repeat(64));
console.log(`RESULTADO: ${passed} PASS, ${failed} FAIL`);
process.exit(failed > 0 ? 1 : 0);
