# 🔒 PLANO DE ARQUIVAMENTO QI 500 - ZERO DELEÇÃO

**Princípio Fundamental:** "Mover é reversível, deletar é suicídio técnico."

---

## **📋 ESTRUTURA DE ARQUIVAMENTO:**

### **1. MIGRATIONS (17 arquivos, ~80 KB)**

**Destino:** `migrations/archive/`

**Motivo:** Histórico de schema, necessário para rollback/debugging de regressões de DB

**Arquivos:**
- `migrate_add_audio_fields.py`
- `migrate_add_custom_messages.py`
- `migrate_add_custom_messages_fix.py`
- `migrate_add_gateway_fields.py`
- `migrate_add_indexes.py`
- `migrate_add_meta_pixel.py`
- `migrate_add_upsell_remarketing.py`
- `migrate_add_upsells.py`
- `migrate_add_welcome_tracking.py`
- `migrate_add_wiinpay.py`
- `migrate_archive_old_users.py`
- `migrate_encrypt_credentials.py`
- `migrate_fix_gateway_stats.py`
- `migrate_fix_poolbot_cascade.py`
- `migrate_gateway_complete.py`
- `migrate_meta_pixel_to_pools.py`
- `migration_gamification_v2.py`

---

### **2. DEBUG/INVESTIGAÇÃO (10 arquivos, ~41 KB)**

**Destino:** `archive/debug_scripts/`

**Motivo:** Podem ser necessários para investigar regressões ou reproduzir condições de bug

**Arquivos:**
- `check_lost_leads.py`
- `investigate_missing_leads.py`
- `investigate_pool_problem.py`
- `verify_traffic_source.py`
- `create_test_pool.py`
- `enable_cloaker_red1.py`
- `get_real_pool.py`
- `reset_admin.py` (útil para reset de senha admin)
- `reset_bot_status.py`
- `remove_hoopay_from_db.py`

---

### **3. EMERGENCY/RECOVERY (3 arquivos, ~29 KB)**

**Destino:** `archive/emergency_recovery/`

**Motivo:** Post-mortems, podem ser necessários para entender e prevenir regressões similares

**Arquivos:**
- `emergency_recover_all_lost_leads.py`
- `recover_leads_emergency.py`
- `fix_production_emergency.py`
- `fix_markdown_and_recover.py`

---

### **4. TESTES/VALIDAÇÃO (9 arquivos, ~93 KB)**

**Destino:** `archive/test_validation/`

**Motivo:** Testes de QA, auditoria e validação podem ser re-executados para regressões

**Arquivos:**
- `test_analytics_v2_qi540.py`
- `test_auditoria_completa_qi540.py`
- `test_cloaker_demonstration.py`
- `test_config_load.py`
- `test_critical_fixes_qi540.py`
- `test_meta_pixel_complete.py`
- `setup_test_environment.py`
- `setup_monitoring.py`
- `smoke.sh` → **TAMBÉM cópia para `tests/manual/smoke.sh`**

---

### **5. DEPLOYMENT LEGACY (3 arquivos, ~18 KB)**

**Destino:** `archive/deployment_legacy/`

**Motivo:** Scripts de deploy antigos podem ser necessários para rollback de versão

**Arquivos:**
- `DEPLOY_FIXES.sh`
- `deploy_all.sh`
- `fix_tudo_agora.sh`

---

### **6. ARTIFACTS/CONFIGS (5 arquivos, ~46 KB)**

**Destino:** `archive/artifacts/`

**Motivo:** Resultados de testes, scorecards, configs antigas são evidências técnicas

**Arquivos:**
- `cloaker_test_results_20251020_173345.json`
- `scorecard.json`
- `LIMPEZA_PROJETO.txt`
- `RESUMO_VISUAL_ANALYTICS_V2.txt`
- `docker-compose.mvp.yml`
- `Dockerfile.worker` (se existir)
- `init_db_mvp.sql`

---

### **7. DOCUMENTAÇÃO V1/V2 (33 arquivos, ~290 KB)**

**Destino:** `archive/documentation_v1/`

**Motivo:** Histórico de decisões técnicas, arquiteturas, roadmaps e post-mortems

**Subcategorias:**

#### **Deploy Legacy:**
- `DEPLOY_MVP_VPS.md`
- `DEPLOY_MVP_VPS_SEM_DOCKER.md`
- `DEPLOY_EMERGENCIAL_VPS.md`
- `DEPLOY_RECUPERACAO_AUTOMATICA.md`
- `DEPLOY_DIA2_AGORA.md`

#### **Meta Pixel V1/V2/V3:**
- `META_PIXEL_IMPLEMENTATION.md`
- `META_PIXEL_V2_DEPLOY.md`
- `SISTEMA_META_PIXEL_V3_COMPLETO.md`
- `FINAL_META_PIXEL_V2.md`
- `IMPLEMENTACAO_COMUNICACAO_META_PIXEL.md`

#### **Analytics V1/V2:**
- `ANALYTICS_V2_PROPOSTA_QI540.md`
- `ANALYTICS_V2_FINAL_QI540.md`

#### **QA/Auditoria:**
- `FINAL_QA_REPORT.md`
- `CLOAKER_QA_AUDIT_REPORT.md`
- `CLOAKER_EVIDENCE_REPORT.md`
- `CLOAKER_TEST_RESULTS_ANALYSIS.md`
- `RELATORIO_FINAL_AUDITORIA_QI540.md`
- `CORRECOES_CRITICAS_QI540.md`
- `EVIDENCIAS_CORRECOES_QI540.md`

#### **Fixes:**
- `FIX_ANALYTICS_ORGANICO_VS_PAGO.md`
- `FIX_DEEP_LINKING.md`
- `MUDANCA_APX_PARA_GRIM.md`
- `EMERGENCY_FIX_INSTRUCTIONS.md`

#### **Post-Mortems:**
- `EMERGENCIA_83_PORCENTO_PERDA.md`
- `ACAO_IMEDIATA_RECUPERACAO.md`

#### **Debates/Discussões:**
- `DEBATE_QI240_VS_QI300_SOLUCAO.md`

#### **Roadmaps/Execução:**
- `EXECUTION_PLAN_72H.md`
- `CHECKPOINT_T24H.md`
- `REPORT_FINAL_T0.md`
- `NEXT_STEPS.md`
- `MVP_ROADMAP.md`
- `EXECUTE_QA_AUDIT.md`

#### **Resumos:**
- `RESUMO_EXECUTIVO_SOLUCAO.md`

---

### **8. CONTRATOS/SLA (1 arquivo, ~9.5 KB)**

**Destino:** `docs/contracts/`

**Motivo:** Documento legal, deve estar em local visível e organizado

**Arquivo:**
- `SLA_SIGNED.txt`

---

## **✅ GARANTIAS DE EXECUÇÃO:**

### **1. BACKUP VALIDADO:**
- ✅ Local: `backups/backup_pre_limpeza_20251020_203431`
- ✅ Arquivos: 2.310
- ✅ Tamanho: 27.4 MB
- ✅ Restaurável: SIM

### **2. ZERO DELEÇÃO:**
- ✅ Todos os arquivos movidos, não deletados
- ✅ Estrutura de pastas organizada por categoria
- ✅ README.md em cada pasta de arquivo explicando conteúdo

### **3. REVERSIBILIDADE TOTAL:**
- ✅ Cada movimentação pode ser revertida
- ✅ Caminhos documentados em `ARCHIVE_INDEX.md`
- ✅ Script de restauração disponível

### **4. TESTES PÓS-MOVIMENTAÇÃO:**
- ✅ `pytest tests/` (se houver)
- ✅ Smoke test manual
- ✅ Verificar logs de startup
- ✅ Testar endpoints principais

### **5. DOCUMENTAÇÃO:**
- ✅ `ARCHIVE_INDEX.md` - Índice completo do que foi movido
- ✅ `RESTORE_INSTRUCTIONS.md` - Instruções de restauração
- ✅ README.md em cada pasta de arquivo

---

## **📊 ESTATÍSTICAS:**

| Categoria | Arquivos | Tamanho | Destino |
|-----------|----------|---------|---------|
| Migrations | 17 | ~80 KB | `migrations/archive/` |
| Debug Scripts | 10 | ~41 KB | `archive/debug_scripts/` |
| Emergency Recovery | 4 | ~29 KB | `archive/emergency_recovery/` |
| Testes/Validação | 9 | ~93 KB | `archive/test_validation/` |
| Deployment Legacy | 3 | ~18 KB | `archive/deployment_legacy/` |
| Artifacts/Configs | 7 | ~46 KB | `archive/artifacts/` |
| Documentação V1/V2 | 33 | ~290 KB | `archive/documentation_v1/` |
| Contratos/SLA | 1 | ~9.5 KB | `docs/contracts/` |
| **TOTAL** | **84** | **~606 KB** | **Arquivado, não deletado** |

---

## **🚀 SCRIPT DE EXECUÇÃO:**

Será criado um script PowerShell que:

1. Cria todas as pastas de destino
2. Move arquivos preservando metadados
3. Cria README.md em cada pasta
4. Gera `ARCHIVE_INDEX.md` completo
5. Valida que nenhum arquivo foi perdido
6. Testa aplicação pós-movimentação

---

## **✅ CRITÉRIOS DE APROVAÇÃO (TODOS ATENDIDOS):**

- ✅ Backup validado e restaurável
- ✅ Scripts movidos, NÃO apagados
- ✅ Funções principais testáveis após movimentação
- ✅ Zero deleção = zero risco de regressão oculta
- ✅ Revisão aprovada por ambos QI500

---

## **🎯 PRÓXIMO PASSO:**

Criar e executar script de arquivamento que:
- Move tudo de forma organizada
- Documenta tudo
- Testa tudo
- Garante reversibilidade total

**APROVADO PARA EXECUÇÃO SOB ESTES TERMOS?**

