# SCRIPT DE ARQUIVAMENTO SEGURO QI 500
# Principio: MOVER TUDO, DELETAR NADA
# Data: 2025-10-20

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ARQUIVAMENTO SEGURO QI 500 - ZERO DELECAO" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Validar backup existe
$backupPath = ".\backups\backup_pre_limpeza_20251020_203431"
if (-not (Test-Path $backupPath)) {
    Write-Host "[ERRO] Backup nao encontrado em $backupPath" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Backup validado: $backupPath" -ForegroundColor Green
Write-Host ""

# Criar estrutura de pastas
Write-Host "[EXECUTANDO] Criando estrutura de pastas..." -ForegroundColor Yellow

$folders = @(
    "archive\debug_scripts",
    "archive\emergency_recovery",
    "archive\test_validation",
    "archive\deployment_legacy",
    "archive\artifacts",
    "archive\documentation_v1\deploy",
    "archive\documentation_v1\meta_pixel",
    "archive\documentation_v1\analytics",
    "archive\documentation_v1\qa_audit",
    "archive\documentation_v1\fixes",
    "archive\documentation_v1\post_mortems",
    "archive\documentation_v1\roadmaps",
    "migrations\archive",
    "docs\contracts",
    "tests\manual"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    Write-Host "  [OK] $folder" -ForegroundColor Gray
}

Write-Host ""

# Funcao para mover arquivo com log
function Move-FileWithLog {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Category
    )
    
    if (Test-Path $Source) {
        Move-Item -Path $Source -Destination $Destination -Force
        $script:movedFiles++
        $fileName = Split-Path $Source -Leaf
        $script:archiveLog += "| $Category | $Source | $Destination |`n"
        Write-Host "  [OK] $fileName" -ForegroundColor Gray
        return $true
    } else {
        Write-Host "  [AVISO] Nao encontrado: $Source" -ForegroundColor DarkYellow
        return $false
    }
}

# Inicializar log
$script:movedFiles = 0
$script:archiveLog = "# INDICE DE ARQUIVAMENTO`n`n"
$script:archiveLog += "Data: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
$script:archiveLog += "Backup: backups\backup_pre_limpeza_20251020_203431`n`n"
$script:archiveLog += "| Categoria | Origem | Destino |`n"
$script:archiveLog += "|-----------|--------|---------|`n"

# 1. MIGRATIONS
Write-Host "[MOVENDO] MIGRATIONS (17 arquivos)..." -ForegroundColor Yellow
$migrations = @(
    "migrate_add_audio_fields.py",
    "migrate_add_custom_messages.py",
    "migrate_add_custom_messages_fix.py",
    "migrate_add_gateway_fields.py",
    "migrate_add_indexes.py",
    "migrate_add_meta_pixel.py",
    "migrate_add_upsell_remarketing.py",
    "migrate_add_upsells.py",
    "migrate_add_welcome_tracking.py",
    "migrate_add_wiinpay.py",
    "migrate_archive_old_users.py",
    "migrate_encrypt_credentials.py",
    "migrate_fix_gateway_stats.py",
    "migrate_fix_poolbot_cascade.py",
    "migrate_gateway_complete.py",
    "migrate_meta_pixel_to_pools.py",
    "migration_gamification_v2.py"
)
foreach ($file in $migrations) {
    Move-FileWithLog -Source $file -Destination "migrations\archive\$file" -Category "Migration"
}
Write-Host ""

# 2. DEBUG SCRIPTS
Write-Host "[MOVENDO] DEBUG SCRIPTS (10 arquivos)..." -ForegroundColor Yellow
$debugScripts = @(
    "check_lost_leads.py",
    "investigate_missing_leads.py",
    "investigate_pool_problem.py",
    "verify_traffic_source.py",
    "create_test_pool.py",
    "enable_cloaker_red1.py",
    "get_real_pool.py",
    "reset_admin.py",
    "reset_bot_status.py",
    "remove_hoopay_from_db.py"
)
foreach ($file in $debugScripts) {
    Move-FileWithLog -Source $file -Destination "archive\debug_scripts\$file" -Category "Debug"
}
Write-Host ""

# 3. EMERGENCY RECOVERY
Write-Host "[MOVENDO] EMERGENCY RECOVERY (4 arquivos)..." -ForegroundColor Yellow
$emergencyScripts = @(
    "emergency_recover_all_lost_leads.py",
    "recover_leads_emergency.py",
    "fix_production_emergency.py",
    "fix_markdown_and_recover.py"
)
foreach ($file in $emergencyScripts) {
    Move-FileWithLog -Source $file -Destination "archive\emergency_recovery\$file" -Category "Emergency"
}
Write-Host ""

# 4. TESTES/VALIDACAO
Write-Host "[MOVENDO] TESTES/VALIDACAO (9 arquivos)..." -ForegroundColor Yellow
$testScripts = @(
    "test_analytics_v2_qi540.py",
    "test_auditoria_completa_qi540.py",
    "test_cloaker_demonstration.py",
    "test_config_load.py",
    "test_critical_fixes_qi540.py",
    "test_meta_pixel_complete.py",
    "setup_test_environment.py",
    "setup_monitoring.py",
    "smoke.sh"
)
foreach ($file in $testScripts) {
    Move-FileWithLog -Source $file -Destination "archive\test_validation\$file" -Category "Test"
}
# Copiar smoke.sh tambem para tests/manual
if (Test-Path "archive\test_validation\smoke.sh") {
    Copy-Item "archive\test_validation\smoke.sh" -Destination "tests\manual\smoke.sh" -Force
    Write-Host "  [OK] smoke.sh copiado para tests\manual\" -ForegroundColor Green
}
Write-Host ""

# 5. DEPLOYMENT LEGACY
Write-Host "[MOVENDO] DEPLOYMENT LEGACY (3 arquivos)..." -ForegroundColor Yellow
$deployScripts = @(
    "DEPLOY_FIXES.sh",
    "deploy_all.sh",
    "fix_tudo_agora.sh"
)
foreach ($file in $deployScripts) {
    Move-FileWithLog -Source $file -Destination "archive\deployment_legacy\$file" -Category "Deploy"
}
Write-Host ""

# 6. ARTIFACTS
Write-Host "[MOVENDO] ARTIFACTS (7 arquivos)..." -ForegroundColor Yellow
$artifacts = @(
    "cloaker_test_results_20251020_173345.json",
    "scorecard.json",
    "LIMPEZA_PROJETO.txt",
    "RESUMO_VISUAL_ANALYTICS_V2.txt",
    "docker-compose.mvp.yml",
    "Dockerfile.worker",
    "init_db_mvp.sql"
)
foreach ($file in $artifacts) {
    Move-FileWithLog -Source $file -Destination "archive\artifacts\$file" -Category "Artifact"
}
Write-Host ""

# 7. DOCUMENTACAO - DEPLOY
Write-Host "[MOVENDO] DOCS - DEPLOY (5 arquivos)..." -ForegroundColor Yellow
$docsDeploy = @(
    "DEPLOY_MVP_VPS.md",
    "DEPLOY_MVP_VPS_SEM_DOCKER.md",
    "DEPLOY_EMERGENCIAL_VPS.md",
    "DEPLOY_RECUPERACAO_AUTOMATICA.md",
    "DEPLOY_DIA2_AGORA.md"
)
foreach ($file in $docsDeploy) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\deploy\$file" -Category "Doc-Deploy"
}
Write-Host ""

# 8. DOCUMENTACAO - META PIXEL
Write-Host "[MOVENDO] DOCS - META PIXEL (5 arquivos)..." -ForegroundColor Yellow
$docsMetaPixel = @(
    "META_PIXEL_IMPLEMENTATION.md",
    "META_PIXEL_V2_DEPLOY.md",
    "SISTEMA_META_PIXEL_V3_COMPLETO.md",
    "FINAL_META_PIXEL_V2.md",
    "IMPLEMENTACAO_COMUNICACAO_META_PIXEL.md"
)
foreach ($file in $docsMetaPixel) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\meta_pixel\$file" -Category "Doc-MetaPixel"
}
Write-Host ""

# 9. DOCUMENTACAO - ANALYTICS
Write-Host "[MOVENDO] DOCS - ANALYTICS (2 arquivos)..." -ForegroundColor Yellow
$docsAnalytics = @(
    "ANALYTICS_V2_PROPOSTA_QI540.md",
    "ANALYTICS_V2_FINAL_QI540.md"
)
foreach ($file in $docsAnalytics) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\analytics\$file" -Category "Doc-Analytics"
}
Write-Host ""

# 10. DOCUMENTACAO - QA/AUDIT
Write-Host "[MOVENDO] DOCS - QA/AUDIT (7 arquivos)..." -ForegroundColor Yellow
$docsQA = @(
    "FINAL_QA_REPORT.md",
    "CLOAKER_QA_AUDIT_REPORT.md",
    "CLOAKER_EVIDENCE_REPORT.md",
    "CLOAKER_TEST_RESULTS_ANALYSIS.md",
    "RELATORIO_FINAL_AUDITORIA_QI540.md",
    "CORRECOES_CRITICAS_QI540.md",
    "EVIDENCIAS_CORRECOES_QI540.md"
)
foreach ($file in $docsQA) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\qa_audit\$file" -Category "Doc-QA"
}
Write-Host ""

# 11. DOCUMENTACAO - FIXES
Write-Host "[MOVENDO] DOCS - FIXES (4 arquivos)..." -ForegroundColor Yellow
$docsFixes = @(
    "FIX_ANALYTICS_ORGANICO_VS_PAGO.md",
    "FIX_DEEP_LINKING.md",
    "MUDANCA_APX_PARA_GRIM.md",
    "EMERGENCY_FIX_INSTRUCTIONS.md"
)
foreach ($file in $docsFixes) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\fixes\$file" -Category "Doc-Fixes"
}
Write-Host ""

# 12. DOCUMENTACAO - POST-MORTEMS
Write-Host "[MOVENDO] DOCS - POST-MORTEMS (3 arquivos)..." -ForegroundColor Yellow
$docsPostMortems = @(
    "EMERGENCIA_83_PORCENTO_PERDA.md",
    "ACAO_IMEDIATA_RECUPERACAO.md",
    "DEBATE_QI240_VS_QI300_SOLUCAO.md"
)
foreach ($file in $docsPostMortems) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\post_mortems\$file" -Category "Doc-PostMortem"
}
Write-Host ""

# 13. DOCUMENTACAO - ROADMAPS
Write-Host "[MOVENDO] DOCS - ROADMAPS (7 arquivos)..." -ForegroundColor Yellow
$docsRoadmaps = @(
    "EXECUTION_PLAN_72H.md",
    "CHECKPOINT_T24H.md",
    "REPORT_FINAL_T0.md",
    "NEXT_STEPS.md",
    "MVP_ROADMAP.md",
    "EXECUTE_QA_AUDIT.md",
    "RESUMO_EXECUTIVO_SOLUCAO.md"
)
foreach ($file in $docsRoadmaps) {
    Move-FileWithLog -Source $file -Destination "archive\documentation_v1\roadmaps\$file" -Category "Doc-Roadmap"
}
Write-Host ""

# 14. CONTRATOS/SLA
Write-Host "[MOVENDO] CONTRATOS/SLA (1 arquivo)..." -ForegroundColor Yellow
Move-FileWithLog -Source "SLA_SIGNED.txt" -Destination "docs\contracts\SLA_SIGNED.txt" -Category "Contract"
Write-Host ""

# Criar README em cada pasta
Write-Host "[EXECUTANDO] Criando README.md em cada pasta..." -ForegroundColor Yellow

@"
# Migrations Archive

Migrations ja executadas no banco de dados.

**Nao deletar:** Historico necessario para rollback e debugging de schema.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "migrations\archive\README.md" -Encoding UTF8

@"
# Debug Scripts Archive

Scripts de debug e investigacao pontuais.

**Proposito:** Investigar regressoes, reproduzir bugs, analise de dados.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\debug_scripts\README.md" -Encoding UTF8

@"
# Emergency Recovery Archive

Scripts de recuperacao de emergencias ja resolvidas.

**Proposito:** Post-mortems, prevencao de regressoes similares.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\emergency_recovery\README.md" -Encoding UTF8

@"
# Test Validation Archive

Scripts de teste, QA e validacao.

**Proposito:** Re-executar para regressoes, smoke tests.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\test_validation\README.md" -Encoding UTF8

@"
# Deployment Legacy Archive

Scripts de deploy antigos.

**Proposito:** Rollback de versao, historico de deploys.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\deployment_legacy\README.md" -Encoding UTF8

@"
# Artifacts Archive

Resultados de testes, scorecards, configs antigas.

**Proposito:** Evidencias tecnicas, auditorias.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\artifacts\README.md" -Encoding UTF8

@"
# Documentation V1 Archive

Documentacao de versoes anteriores, roadmaps, QA reports.

**Proposito:** Historico de decisoes tecnicas, arquiteturas.

**Backup:** backups\backup_pre_limpeza_20251020_203431

**Data:** $(Get-Date -Format 'yyyy-MM-dd')
"@ | Out-File "archive\documentation_v1\README.md" -Encoding UTF8

Write-Host "  [OK] READMEs criados" -ForegroundColor Green
Write-Host ""

# Salvar log de arquivamento
$script:archiveLog | Out-File "ARCHIVE_INDEX.md" -Encoding UTF8
Write-Host "[OK] Log de arquivamento salvo: ARCHIVE_INDEX.md" -ForegroundColor Green
Write-Host ""

# Estatisticas
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ESTATISTICAS DO ARQUIVAMENTO" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[OK] Arquivos movidos: $script:movedFiles" -ForegroundColor Green
Write-Host "[OK] Zero arquivos deletados" -ForegroundColor Green
Write-Host "[OK] Backup preservado: $backupPath" -ForegroundColor Green
Write-Host "[OK] Indice gerado: ARCHIVE_INDEX.md" -ForegroundColor Green
Write-Host ""

# Criar script de restauracao
@"
# SCRIPT DE RESTAURACAO DE EMERGENCIA

Se algo der errado, execute:

``````powershell
# Restaurar do backup
Copy-Item -Path "backups\backup_pre_limpeza_20251020_203431\*" -Destination . -Recurse -Force

# OU restaurar do archive manualmente consultando:
# ARCHIVE_INDEX.md
``````

**Data do Backup:** 2025-10-20 20:34
**Arquivos no Backup:** 2.310
**Tamanho:** 27.4 MB
"@ | Out-File "RESTORE_INSTRUCTIONS.md" -Encoding UTF8

Write-Host "[OK] Instrucoes de restauracao criadas: RESTORE_INSTRUCTIONS.md" -ForegroundColor Green
Write-Host ""

Write-Host "================================================================================" -ForegroundColor Green
Write-Host "ARQUIVAMENTO CONCLUIDO COM SUCESSO!" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Proximos passos:" -ForegroundColor Yellow
Write-Host "  1. Testar aplicacao: python app.py" -ForegroundColor White
Write-Host "  2. Verificar logs de startup" -ForegroundColor White
Write-Host "  3. Testar endpoints principais" -ForegroundColor White
Write-Host "  4. Se algo der errado: Ver RESTORE_INSTRUCTIONS.md" -ForegroundColor White
Write-Host ""
