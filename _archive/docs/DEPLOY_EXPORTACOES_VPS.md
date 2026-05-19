# 🚀 DEPLOY - EXPORTAÇÕES CSV NA VPS
## Instruções para Aplicar na VPS

**Data:** 2025-11-13  
**Status:** Pronto para Deploy

---

## ✅ CHECKLIST DE DEPLOY

### 1. **Verificar Código Atualizado**
```bash
# Conectar ao VPS
ssh root@grimbots

# Ir para o diretório do projeto
cd ~/grimbots

# Verificar se o código foi atualizado
git status
git log --oneline -5

# Se necessário, fazer pull
git pull origin main  # ou master, conforme sua branch
```

### 2. **Criar Diretório de Exports**
```bash
# Criar diretório exports (se não existir)
mkdir -p exports

# Verificar permissões
chmod 755 exports

# Verificar se o diretório foi criado
ls -la exports/
```

### 3. **Verificar Scripts de Extração**
```bash
# Verificar se os scripts existem
ls -la scripts/extrair_vendas_umbrella_hoje*

# Dar permissão de execução (se necessário)
chmod +x scripts/extrair_vendas_umbrella_hoje.sh
chmod +x scripts/extrair_vendas_umbrella_hoje_csv.sh
```

### 4. **Reiniciar Serviços**
```bash
# Reiniciar aplicação Flask
./restart-app.sh

# OU manualmente:
systemctl restart grimbots.service

# Verificar status
systemctl status grimbots.service
```

### 5. **Verificar Logs**
```bash
# Verificar logs do Gunicorn
tail -f logs/error.log

# Verificar logs do aplicativo
journalctl -u grimbots.service -f
```

---

## 🧪 TESTES DE VALIDAÇÃO

### 1. **Testar Página de Exportações**
```bash
# Acessar no navegador:
# https://app.grimbots.online/admin/exports

# Verificar se a página carrega corretamente
# Deve mostrar mensagem "Nenhum arquivo CSV disponível" se não houver arquivos
```

### 2. **Testar Geração de CSV**
```bash
# No painel admin, clicar em "Gerar Novo CSV (Hoje)"
# Verificar se aparece mensagem de sucesso
# Verificar se os arquivos foram criados:

ls -la exports/

# Deve mostrar arquivos como:
# vendas_umbrella_todas_YYYY-MM-DD.csv
# vendas_umbrella_pagas_YYYY-MM-DD.csv
```

### 3. **Testar Download de CSV**
```bash
# No painel admin, clicar em "Baixar" ao lado de um arquivo
# Verificar se o arquivo é baixado corretamente
# Verificar se o arquivo contém dados válidos
```

### 4. **Verificar Logs de Auditoria**
```bash
# Verificar se as ações foram registradas
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    id,
    admin_id,
    action,
    description,
    created_at
FROM audit_logs
WHERE action IN ('view_exports', 'download_csv', 'generate_csv')
ORDER BY created_at DESC
LIMIT 10;
"
```

---

## 🔍 VALIDAÇÃO COMPLETA

### 1. **Verificar Rotas**
```bash
# Testar rota de listagem
curl -X GET https://app.grimbots.online/admin/exports \
  -H "Cookie: session=SEU_SESSION_COOKIE" \
  -v

# Deve retornar status 200 se autenticado
```

### 2. **Verificar Geração de CSV**
```bash
# Executar script Python diretamente
cd ~/grimbots
source venv/bin/activate
python scripts/extrair_vendas_umbrella_hoje.py

# Verificar se os arquivos foram criados
ls -la exports/

# Verificar conteúdo dos arquivos
head -5 exports/vendas_umbrella_todas_$(date +%Y-%m-%d).csv
head -5 exports/vendas_umbrella_pagas_$(date +%Y-%m-%d).csv
```

### 3. **Verificar Permissões**
```bash
# Verificar permissões do diretório exports
ls -la exports/

# Verificar permissões dos arquivos CSV
ls -la exports/*.csv

# Se necessário, corrigir permissões
chmod 644 exports/*.csv
chmod 755 exports/
```

### 4. **Verificar Banco de Dados**
```bash
# Verificar se há vendas do UmbrellaPay de hoje
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    COUNT(*) as total_vendas,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as vendas_pagas
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND created_at >= CURRENT_DATE;
"
```

---

## 🚨 TROUBLESHOOTING

### Problema: Página não carrega
**Solução:**
```bash
# Verificar se o serviço está rodando
systemctl status grimbots.service

# Verificar logs de erro
tail -f logs/error.log

# Reiniciar serviço
systemctl restart grimbots.service
```

### Problema: CSV não é gerado
**Solução:**
```bash
# Verificar se o script Python está funcionando
cd ~/grimbots
source venv/bin/activate
python scripts/extrair_vendas_umbrella_hoje.py

# Verificar se há vendas do UmbrellaPay de hoje
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT COUNT(*) FROM payments 
WHERE gateway_type = 'umbrellapag' 
  AND created_at >= CURRENT_DATE;
"

# Verificar permissões do diretório exports
ls -la exports/
chmod 755 exports/
```

### Problema: Arquivo não é baixado
**Solução:**
```bash
# Verificar se o arquivo existe
ls -la exports/*.csv

# Verificar permissões do arquivo
chmod 644 exports/*.csv

# Verificar logs do servidor
tail -f logs/error.log
```

### Problema: Erro 500 ao gerar CSV
**Solução:**
```bash
# Verificar logs de erro
tail -f logs/error.log

# Verificar se o módulo Python está disponível
cd ~/grimbots
source venv/bin/activate
python -c "from scripts.extrair_vendas_umbrella_hoje import extrair_vendas_umbrella_hoje; print('OK')"

# Verificar se o script shell existe
ls -la scripts/extrair_vendas_umbrella_hoje_csv.sh
```

---

## ✅ CHECKLIST FINAL

### Antes de Finalizar:
- [ ] ✅ Código atualizado no VPS
- [ ] ✅ Diretório `exports/` criado
- [ ] ✅ Serviços reiniciados
- [ ] ✅ Página `/admin/exports` carrega corretamente
- [ ] ✅ Geração de CSV funciona
- [ ] ✅ Download de CSV funciona
- [ ] ✅ Logs de auditoria funcionam
- [ ] ✅ Permissões corretas
- [ ] ✅ Testes de segurança realizados

---

## 📊 COMANDOS RÁPIDOS

### Deploy Rápido:
```bash
# 1. Atualizar código
cd ~/grimbots && git pull origin main

# 2. Criar diretório
mkdir -p exports && chmod 755 exports

# 3. Reiniciar serviço
./restart-app.sh

# 4. Verificar logs
tail -f logs/error.log
```

### Validação Rápida:
```bash
# 1. Verificar se há vendas
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT COUNT(*) FROM payments 
WHERE gateway_type = 'umbrellapag' 
  AND created_at >= CURRENT_DATE;
"

# 2. Gerar CSV manualmente
cd ~/grimbots
source venv/bin/activate
python scripts/extrair_vendas_umbrella_hoje.py

# 3. Verificar arquivos criados
ls -la exports/
```

---

## 🎯 PRÓXIMOS PASSOS

1. **Testar no Navegador**: Acessar `/admin/exports` e testar funcionalidade
2. **Gerar CSV de Teste**: Criar um CSV de teste para validar
3. **Validar Download**: Baixar um CSV e verificar conteúdo
4. **Monitorar Logs**: Verificar logs de auditoria
5. **Documentar**: Documentar qualquer problema encontrado

---

**Status:** ✅ **Pronto para Deploy**  
**Próximo:** Executar comandos no VPS e testar funcionalidade

