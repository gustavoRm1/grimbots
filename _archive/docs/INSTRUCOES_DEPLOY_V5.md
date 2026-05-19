# 🚀 INSTRUÇÕES DE DEPLOY V5.0 - FLOW BUILDER

## 📋 Pré-requisitos

- Acesso ao servidor/repositório
- Backup dos arquivos modificados
- Feature flag `config.flow_enabled` configurada

## 🔄 Passos de Deploy

### 1. Backup (OBRIGATÓRIO)

```bash
# Criar backup dos arquivos modificados
cp static/js/flow_editor.js static/js/flow_editor.js.backup
cp templates/bot_config.html templates/bot_config.html.backup
```

### 2. Aplicar Mudanças

```bash
# Verificar que os arquivos foram atualizados
git status

# Verificar diff
git diff static/js/flow_editor.js
git diff templates/bot_config.html
```

### 3. Limpar Cache do Frontend

```bash
# Se usar build step (webpack/parcel/gulp)
npm run build

# Ou limpar cache do navegador
# No Chrome: DevTools > Application > Clear Storage > Clear site data
```

### 4. Ativar Feature Flag

A feature já está opcional via `config.flow_enabled`. Para ativar:

1. Acessar Bot Config
2. Verificar que `config.flow_enabled === true`
3. Se não estiver, ativar manualmente no código ou via UI

### 5. Testar em Homologação

1. Acessar página do Bot Config
2. Abrir aba "Flow"
3. Verificar que canvas aparece
4. Executar checklist de QA (ver `CHECKLIST_QA_V5.md`)

### 6. Deploy em Produção

```bash
# Commit das mudanças
git add static/js/flow_editor.js templates/bot_config.html
git commit -m "feat: Flow Builder V5.0 - ManyChat-level com anti-duplicação robusta"

# Push (se aplicável)
git push origin main

# Ou deploy via CI/CD conforme política interna
```

## 🔙 Rollback

Se algo falhar, reverter para commit anterior:

```bash
# Opção 1: Restaurar backup
cp static/js/flow_editor.js.backup static/js/flow_editor.js
cp templates/bot_config.html.backup templates/bot_config.html

# Opção 2: Git revert
git revert HEAD

# Opção 3: Desabilitar feature flag
# No código: config.flow_enabled = false
```

## 🐛 Debug

### Habilitar Logs de Debug

No console do navegador:

```javascript
window.FLOW_DEBUG = true;
```

Isso ativa logs detalhados no console para:
- Criação de endpoints
- Conexões
- ReconnectAll
- Erros

### Verificar Endpoints Duplicados

No console do navegador:

```javascript
// Contar endpoints
document.querySelectorAll('.jtk-endpoint').length

// Verificar endpoints por step
window.flowEditor?.steps.forEach((el, stepId) => {
    const endpoints = window.flowEditor?.instance?.getEndpoints(el) || [];
    console.log(`Step ${stepId}: ${endpoints.length} endpoints`);
});
```

### Verificar Flag de Endpoints

```javascript
// Verificar se flag está sendo usada
window.flowEditor?.steps.forEach((el, stepId) => {
    console.log(`Step ${stepId}: endpointsInited = ${el.dataset.endpointsInited}`);
});
```

## 📝 Checklist Pós-Deploy

- [ ] Feature flag ativada
- [ ] Cache limpo
- [ ] Testes básicos executados
- [ ] Console sem erros
- [ ] Endpoints não duplicam
- [ ] Modal funciona
- [ ] Drag funciona pelo handle
- [ ] Zoom/pan funcionam
- [ ] Conexões persistem

## 🔒 Segurança

- Nenhuma mudança em autenticação/autorização
- Nenhuma mudança em APIs sensíveis
- Apenas frontend (JS/CSS/HTML)
- Feature flag garante isolamento

## 📞 Suporte

Em caso de problemas:

1. Verificar console do navegador (F12)
2. Verificar se `window.flowEditor` existe
3. Verificar se `jsPlumb` está carregado
4. Verificar se `Alpine.js` está carregado
5. Executar checklist de debug acima

