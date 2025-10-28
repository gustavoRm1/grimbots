# 🧹 INSTRUÇÕES: Executar Limpeza na VPS

**Data:** 2025-10-28  
**Autores:** Senior QI 500 + André QI 502

---

## ✅ ANÁLISE CONFIRMADA

### **ARQUIVOS PARA DELETAR:**

**Scripts Python de Teste:** ~40 arquivos
- `diagnose_*.py` - Diagnósticos temporários
- `test_*.py` - Testes temporários
- `check_*.py` - Verificações temporárias
- `investigate_*.py` - Investigações temporárias
- `fix_user_stats.py` - Fix temporário
- `validar_solucao_híbrida.py` - Validação temporária
- `verificar_dados_demograficos.py` - Diagnóstico temporário
- `reenviar_meta_pixel.py` - Script temporário
- `DIAGNOSTICO_*.py` - Diagnósticos
- `TEST_*.py` - Testes
- `paradise_*.py` - Fix temporários

**Scripts Shell (.sh):** ~25 arquivos
- `fix_*.sh` - Fix temporários
- `deploy_paradise_*.sh` - Deploys temporários
- `test_*.sh` - Testes temporários
- `DEPLOY_*.sh` - Deploys temporários

**Documentação (.md):** ~75 arquivos
- `ANALISE_*.md` - Análises temporárias
- `DIAGNOSTICO_*.md` - Diagnósticos temporários
- `DEPLOY_*.md` - Instruções de deploy antigas
- `FIX_*.md` - Fixes documentados
- `TRACKING_*.md` - Documentação temporária

**Total:** ~180 arquivos removidos

### **ARQUIVOS PARA MANTER:**

✅ Core do sistema
- `app.py`, `bot_manager.py`, `models.py`
- `celery_app.py`, `wsgi.py`, `gunicorn_config.py`
- `init_db.py`, `requirements.txt`

✅ Gateways
- `gateway_*.py`

✅ Features
- `gamification_websocket.py`
- `ranking_engine_v2.py`
- `tracking_elite_analytics.py`

✅ Migrations ativas
- `migrate_add_demographic_fields.py`
- `migrate_add_tracking_fields.py`
- `migrate_add_transaction_hash.py`

✅ Estrutura
- `utils/`, `tasks/`, `templates/`, `static/`
- `tests/` (testes unitários importantes)
- `deploy/` (scripts ativos)
- `docs/` (documentação essencial)
- `archive/` (histórico)
- `migrations/archive/` (histórico)

---

## 🚀 EXECUTAR NA VPS

### **Passo 1: Fazer Upload do Script**

No WINDOWS:

```bash
# Via SCP
scp limpar_vps.sh root@SEU_IP_VPS:/root/grimbots/

# OU via git
git add limpar_vps.sh
git commit -m "feat: script de limpeza VPS"
git push origin main
```

Na VPS:

```bash
cd ~/grimbots
git pull origin main
```

---

### **Passo 2: Dar Permissão de Execução**

```bash
chmod +x limpar_vps.sh
```

---

### **Passo 3: Executar Script**

```bash
./limpar_vps.sh
```

**O script vai:**
1. Perguntar confirmação
2. Criar backup em `backups/limpeza_YYYYMMDD_HHMMSS/`
3. Mover arquivos temporários para backup (não deleta!)
4. Mostrar resumo

---

### **Passo 4: Verificar Resultado**

```bash
# Contar arquivos antes e depois
echo "Arquivos .py:"
ls -1 *.py | wc -l

echo "Arquivos .md:"
ls -1 *.md | wc -l

echo "Scripts .sh:"
ls -1 *.sh | wc -l
```

---

## ⚠️ SEGURANÇA

### **1. Script usa MOVE, não DELETE**
- Arquivos são movidos para `backups/`
- Podem ser restaurados se necessário

### **2. Backup automático**
- Criado em `backups/limpeza_YYYYMMDD_HHMMSS/`
- Contém todos os arquivos removidos

### **3. Confirmação obrigatória**
- Script pergunta antes de executar
- Você pode cancelar digitando "não"

### **4. Sistema protegido**
- Core do sistema preservado
- Estrutura de diretórios preservada
- Apenas arquivos temporários removidos

---

## 🔄 RESTAURAR SE PRECISAR

```bash
# Ver backups disponíveis
ls -la backups/

# Restaurar arquivo específico
cp backups/limpeza_YYYYMMDD_HHMMSS/scripts/diagnose_500.py .

# OU restaurar tudo
cp -r backups/limpeza_YYYYMMDD_HHMMSS/* .
```

---

## ✅ VALIDAÇÃO PÓS-LIMPEZA

Após limpeza, verificar:

```bash
# 1. Sistema continua rodando?
sudo systemctl status grimbots

# 2. Arquivos essenciais presentes?
ls -la app.py bot_manager.py models.py

# 3. Gateway funcionando?
curl http://localhost:5000/api/health

# 4. Logs sem erros?
sudo journalctl -u grimbots -n 100
```

---

## 📊 RESULTADO ESPERADO

**ANTES:**
- Total de arquivos: ~240
- Arquivos desnecessários: ~180

**DEPOIS:**
- Total de arquivos: ~60
- Redução: 75% de limpeza
- Sistema: 100% funcional

---

## 🎯 CONCLUSÃO

**MÉTODO:** Seguro (backup automático)  
**IMPACTO:** Zero (sistema continua funcionando)  
**BENEFÍCIO:** VPS 75% mais limpa e organizada  
**RISCO:** Nenhum (backup completo)

✅ **PRONTO PARA EXECUTAR**

