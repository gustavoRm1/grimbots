# 🔄 PUSH PARA ORIGIN/MAIN

## ⚠️ IMPORTANTE

O commit deve ser feito no **origin/main** (repositório remoto), não apenas no main local.

---

## 📋 COMANDOS CORRETOS

### 1. Verificar estado atual
```bash
git status
git branch -a  # Ver todas as branches (local e remoto)
```

### 2. Verificar se está na branch main local
```bash
git checkout main
# ou
git checkout master
```

### 3. Verificar se origin/main está atualizado
```bash
git fetch origin
git log origin/main --oneline -5  # Ver últimos 5 commits do origin/main
```

### 4. Adicionar arquivos ao staging
```bash
git add models.py
git add bot_manager.py
git add app.py
git add templates/bot_config.html
git add migrations/add_flow_fields.py
git add EXECUTAR_MIGRATION_FLOW.sh
git add DEBATE_PROFUNDO_QI500_EDITOR_FLUXO.md
git add COMMIT_FLUXO_IMPLEMENTACAO.md
```

### 5. Criar commit
```bash
git commit -m "feat: Implementação completa do editor de fluxograma visual

- Adicionado campos flow_enabled e flow_steps ao BotConfig
- Adicionado campo flow_step_id ao Payment  
- Implementado executor de fluxo recursivo (síncrono até payment, assíncrono após)
- Implementado lista visual de steps no frontend
- Suporte a condições limitadas (payment: next/pending, message: retry)
- Fallback robusto para welcome_message se fluxo falhar
- Backward compatible - bots antigos continuam funcionando normalmente

Arquitetura: Híbrida (lista visual padrão + executor recursivo stateless)
Performance: Síncrono até payment (rápido), assíncrono após callback (pesado)
Estado: Stateless (apenas payment.flow_step_id para determinar próximo step)"
```

### 6. **PUSH PARA ORIGIN/MAIN** (CRÍTICO)
```bash
git push origin main
```

**OU se a branch remota se chama master:**
```bash
git push origin master
```

---

## 🔍 VERIFICAR SE FOI ENVIADO CORRETAMENTE

```bash
# Ver commits no origin/main
git log origin/main --oneline -5

# Verificar se seu commit está lá
git log origin/main --oneline | grep "fluxograma visual"
```

---

## ⚠️ SE JÁ FEZ COMMIT NO MAIN LOCAL

Se você já fez commit no main local mas não fez push, basta fazer:

```bash
git push origin main
```

Se você fez commit em outra branch, precisa fazer merge ou cherry-pick:

```bash
# Opção 1: Fazer merge da branch atual para main
git checkout main
git merge sua-branch-aqui
git push origin main

# Opção 2: Fazer cherry-pick do commit específico
git checkout main
git cherry-pick <hash-do-commit>
git push origin main
```

---

## ✅ VERIFICAÇÃO FINAL

Após o push, verifique no GitHub/GitLab que o commit está em `origin/main`:

```bash
git log origin/main --oneline -1
```

O commit deve aparecer com a mensagem "feat: Implementação completa do editor de fluxograma visual"

---

**Status:** Aguardando push para origin/main

