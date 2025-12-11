# ✅ CHECKLIST DE QA V5.0 - FLOW BUILDER

## 🧪 Testes Unitários/Integração

### Test A - Render básico
- [ ] Carregar página → aba Flow
- [ ] Cards aparecem visíveis
- [ ] Console sem erros Alpine
- [ ] Endpoints aparecem corretamente (input à esquerda, output à direita)

### Test B - Input node fixed left
- [ ] Criar step sem botões
- [ ] Verificar `.flow-step-node-input` existe
- [ ] Verificar posição: input node à esquerda do card (left: -8px)
- [ ] Endpoint UUID: `endpoint-left-{id}` existe e é único

### Test C - Global output for no-buttons
- [ ] Step sem botões tem `.flow-step-node-output-global`
- [ ] Posição: output node à direita do card (right: -8px)
- [ ] Endpoint UUID: `endpoint-right-{id}` existe e é único
- [ ] NÃO há endpoints de botões quando não há botões

### Test D - Buttons outputs
- [ ] Step com 2 botões
- [ ] NÃO tem `.flow-step-node-output-global`
- [ ] Cada botão tem endpoint: `endpoint-button-{id}-0`, `endpoint-button-{id}-1`
- [ ] Conexão visualmente sai do botão, não do card
- [ ] Cada botão tem apenas 1 endpoint (sem duplicação)

### Test E - Connection persistence & dedupe
- [ ] Conectar botão A → B
- [ ] Reload/reconnectAll → conexão restaurada UMA vez
- [ ] Tentar criar mesma conexão 2x → segunda é ignorada
- [ ] Remover conexão → Alpine atualizado corretamente

### Test F - Zoom-to-cursor
- [ ] Hover sobre canvas
- [ ] Ctrl+wheel ou wheel direto
- [ ] Ponto sob cursor permanece sob cursor após zoom
- [ ] Conexões não se desfazem durante zoom
- [ ] Endpoints permanecem alinhados

### Test G - Drag performance
- [ ] Drag rápido de card 100x
- [ ] Sem erros no console
- [ ] Endpoints não se desprendem
- [ ] FPS aceitável (sem stutters visíveis)
- [ ] Nenhuma duplicação de endpoints após drag
- [ ] Drag funciona apenas pelo header (handle)

### Test H - Modal & Alpine safety
- [ ] Abrir modal para editar step (clicar botão editar)
- [ ] Modal abre sem erros JS
- [ ] Fechar modal
- [ ] Console SEM erros Alpine sobre `editingStep null`
- [ ] Salvar alterações funciona

### Test I - ReconnectAll reconcile
- [ ] Criar 3 conexões
- [ ] Chamar reconnectAll()
- [ ] Conexões existentes não são deletadas e recriadas
- [ ] Apenas conexões novas são criadas
- [ ] Conexões removidas do Alpine são deletadas

### Test J - Dataset flag
- [ ] Adicionar step → `dataset.endpointsInited = 'true'`
- [ ] Chamar addEndpoints novamente → não cria duplicados
- [ ] Atualizar step (adicionar botão) → flag resetada, endpoints recriados

## 🎯 Critérios de Aceitação (MUST PASS)

### ✅ CA1: Endpoints por botão
- [ ] Ao adicionar step com 2 botões: cada botão tem apenas 1 endpoint visível e clicável
- [ ] Não existe endpoint global no lado direito quando há botões

### ✅ CA2: Zero duplicação
- [ ] Ao mover card 100x rapidamente: nenhuma duplicação de `<circle>` ou `.jtk-endpoint` no DOM
- [ ] Verificar com DevTools: `document.querySelectorAll('.jtk-endpoint').length` = número esperado

### ✅ CA3: Conexões persistentes
- [ ] Ao criar conexão por drag no endpoint: conexão é criada
- [ ] Propriedade `target` é salva no Alpine `config.flow_steps[].config.custom_buttons[].target_step`

### ✅ CA4: Modal funcional
- [ ] Modal Edit Step abre sem erros JS no console
- [ ] Salva alterações corretamente
- [ ] Bindings Alpine funcionam (x-model sem erros)

### ✅ CA5: Zoom focado
- [ ] Zoom in/out foca no cursor
- [ ] Conexões não se desfazem (repaint correto)
- [ ] Endpoints permanecem alinhados

### ✅ CA6: Performance
- [ ] Durante drag: sem quedas visíveis (throttle/repaint 60fps)
- [ ] Console sem warnings de performance

### ✅ CA7: Backwards compatibility
- [ ] Nenhum outro comportamento do BotConfig quebrado
- [ ] Feature flag `config.flow_enabled` funciona
- [ ] Fluxo desabilitado não inicializa editor

## 📊 Resultados dos Testes

### Ambiente de Teste
- **Navegador**: _______________
- **Versão**: _______________
- **OS**: _______________
- **Data**: _______________

### Resultados
- **Test A**: [ ] PASS [ ] FAIL
- **Test B**: [ ] PASS [ ] FAIL
- **Test C**: [ ] PASS [ ] FAIL
- **Test D**: [ ] PASS [ ] FAIL
- **Test E**: [ ] PASS [ ] FAIL
- **Test F**: [ ] PASS [ ] FAIL
- **Test G**: [ ] PASS [ ] FAIL
- **Test H**: [ ] PASS [ ] FAIL
- **Test I**: [ ] PASS [ ] FAIL
- **Test J**: [ ] PASS [ ] FAIL

### Critérios de Aceitação
- **CA1**: [ ] PASS [ ] FAIL
- **CA2**: [ ] PASS [ ] FAIL
- **CA3**: [ ] PASS [ ] FAIL
- **CA4**: [ ] PASS [ ] FAIL
- **CA5**: [ ] PASS [ ] FAIL
- **CA6**: [ ] PASS [ ] FAIL
- **CA7**: [ ] PASS [ ] FAIL

### Observações
_________________________________________________
_________________________________________________
_________________________________________________

