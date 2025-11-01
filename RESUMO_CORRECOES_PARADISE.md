# ✅ CORREÇÕES PARADISE - IDs DUPLICADOS

## 🎯 PROBLEMA IDENTIFICADO

PIXs gerados na Paradise retornando IDs duplicados no painel, causando alguns PIXs não aparecerem no painel.

## 🔍 CAUSA RAIZ

O campo `offerHash` estava sendo enviado para a API Paradise, causando IDs duplicados quando o mesmo `offerHash` fixo era usado para múltiplos PIXs.

## ✅ CORREÇÕES APLICADAS

### 1. **Remoção do offerHash** (`gateway_paradise.py`)
- ✅ `offerHash` agora é IGNORADO no payload
- ✅ Log adicionado: `offerHash ignorado para evitar duplicação`

### 2. **Validação de Reference Único** (`gateway_paradise.py`)
- ✅ Verifica se já existe payment com mesmo reference antes de criar
- ✅ Se duplicado, adiciona timestamp para garantir unicidade

### 3. **Reutilização de PIX Segura** (`bot_manager.py`)
- ✅ Para Paradise, verifica se PIX antigo tem `gateway_transaction_hash` válido
- ✅ PIX sem hash não é reutilizado (gera novo)

### 4. **Logs Detalhados** (`gateway_paradise.py`)
- ✅ Mostra `Transaction ID`, `Paradise ID (painel)`, `Reference enviado`
- ✅ Alerta se ID retornado difere do reference
- ✅ Mostra qual ID usar para verificar no painel

### 5. **Validação de ProductHash** (`gateway_paradise.py`)
- ✅ Verifica se `productHash` está configurado corretamente
- ✅ Valida formato (deve começar com `prod_`)

### 6. **Script de Diagnóstico** (`diagnose_paradise_missing_transactions.py`)
- ✅ Verifica pagamentos PENDING e consulta status na Paradise
- ✅ Mostra estatísticas de gateways

### 7. **Script de Correção** (`corrigir_paradise_transaction_hash.py`)
- ✅ Corrige pagamentos antigos sem `gateway_transaction_hash`
- ✅ Adiciona hash temporário para facilitar reconciliação

## 🚀 DEPLOY NA VPS

```bash
cd ~/grimbots
source venv/bin/activate

# 1. Atualizar código
git pull origin main
sudo systemctl restart grimbots

# 2. Verificar logs detalhados
sudo journalctl -u grimbots -f | grep -E "Paradise.*ID|offerHash ignorado|Reference corrigido"

# 3. Monitorar próximos PIXs
sudo journalctl -u grimbots -f | grep -E "Paradise.*PIX gerado|Paradise ID.*painel|Reference enviado"

# 4. (Opcional) Corrigir pagamentos antigos
python3 corrigir_paradise_transaction_hash.py

# 5. (Opcional) Diagnóstico completo
python3 diagnose_paradise_missing_transactions.py
```

## 📊 O QUE ESPERAR APÓS DEPLOY

### Logs Corretos:
```
⚠️ Paradise: offerHash ignorado (e87f909afc) para evitar duplicação
✅ Paradise: PIX gerado com SUCESSO
   Transaction ID (numérico): 155342
   Paradise ID (aparece no painel): BOT4-1761947869-6875d06b
   Transaction Hash (usado para consulta): BOT4-1761947869-6875d06b
   Reference enviado: BOT2-1761957830-8ee6ec87
   Product Hash: prod_6c60b3dd3ae2c63e
   QR Code válido: ✅
```

### Se IDs Diferirem:
```
⚠️ Paradise gerou ID diferente do reference enviado!
   Reference enviado: BOT2-1761957830-8ee6ec87
   ID retornado: BOT4-1761947869-6875d06b
   💡 Use o ID retornado (BOT4-1761947869-6875d06b) para verificar no painel Paradise
```

## ✅ RESULTADO ESPERADO

- ✅ Todos os PIXs gerados terão IDs ÚNICOS no painel Paradise
- ✅ Nenhum `offerHash` será enviado
- ✅ Reference sempre será único (com timestamp se necessário)
- ✅ Logs detalhados para debugging
- ✅ PIXs antigos sem hash não serão reutilizados
- ✅ Reconciliador atualizará pagamentos corretamente

## 🔍 VERIFICAÇÃO

Após deploy, verificar no painel Paradise:
- ✅ Novos PIXs devem aparecer imediatamente
- ✅ Cada PIX deve ter ID único (não duplicados)
- ✅ IDs devem corresponder aos logs do sistema

## 📝 ARQUIVOS MODIFICADOS

1. `gateway_paradise.py` - Remoção de offerHash, validações robustas
2. `bot_manager.py` - Reutilização segura de PIX, verificação de hash
3. `diagnose_paradise_missing_transactions.py` - Script de diagnóstico
4. `corrigir_paradise_transaction_hash.py` - Script de correção

