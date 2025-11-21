# 🔍 Diagnóstico e Correções - Gateways de Pagamento

## ❌ Problemas Identificados

### 1. **Erro de Descriptografia (ENCRYPTION_KEY)**
- **Sintoma**: `❌ syncpay: api_key ausente ou não descriptografado`
- **Causa Raiz**: `ENCRYPTION_KEY` foi alterada após salvar credenciais no banco
- **Impacto**: Gateways não conseguem descriptografar credenciais salvas

### 2. **Paradise API Retornando 400 Bad Request**
- **Sintoma**: `Status 400` com mensagem genérica
- **Causa Raiz**: Credenciais inválidas ou mal configuradas (api_key, product_hash, store_id)
- **Impacto**: PIX não é gerado, vendas são perdidas

### 3. **Fallback de Credenciais Mascarando Erros**
- **Problema**: Paradise usava credenciais padrão quando não configuradas
- **Impacto**: Erros de configuração não eram detectados

---

## ✅ Correções Implementadas

### 1. **Detecção Robusta de Erros de Descriptografia**

#### `models.py` - Properties do Gateway
- ✅ Captura exceções específicas (`RuntimeError` para erros de descriptografia)
- ✅ Verifica se descriptografia retornou `None` (indica falha)
- ✅ Logs detalhados mostrando campo interno vs. property retornada
- ✅ Mensagens claras indicando que `ENCRYPTION_KEY` foi alterada

```python
# Exemplo: api_key property
@property
def api_key(self):
    try:
        decrypted = decrypt(self._api_key)
        if decrypted is None:
            # Log erro e retorna None
        return decrypted
    except RuntimeError as e:
        # Erro de descriptografia (ENCRYPTION_KEY incorreta)
        # Log detalhado e retorna None
```

### 2. **Validação Prévia Antes de Criar Gateway**

#### `bot_manager.py` - Função `_generate_pix_payment`
- ✅ Extrai credenciais com try/except para capturar erros
- ✅ Valida se campo interno existe mas descriptografia falhou
- ✅ Retorna `None` imediatamente se erro de descriptografia detectado
- ✅ Validação específica por gateway:
  - **SyncPay**: Requer `client_id` e `client_secret` (não `api_key`)
  - **Paradise**: Requer `api_key` (formato `sk_...`) e `product_hash` (formato `prod_...`)
  - **PushynPay/WiinPay**: Requer `api_key`

### 3. **Validação de Formato e Credenciais no Paradise**

#### `gateway_paradise.py` - Método `__init__`
- ✅ **Removido fallback padrão** que mascarava erros
- ✅ Validação obrigatória de `api_key` e `product_hash`
- ✅ Validação de formato:
  - `api_key` deve começar com `sk_`
  - `product_hash` deve começar com `prod_`
- ✅ Validação de `store_id` (obrigatório para split)

#### `gateway_paradise.py` - Método `generate_pix`
- ✅ Validação prévia antes de enviar payload:
  - `api_key` presente e formato correto
  - `product_hash` presente e formato correto
  - `productHash` no payload corresponde ao configurado

### 4. **Diagnóstico Detalhado para Erro 400**

#### `gateway_paradise.py` - Tratamento de Erro 400
- ✅ Logs estruturados com seções claras:
  - 🔑 **CREDENCIAIS ENVIADAS**: API Key, Product Hash, Store ID
  - 📊 **PAYLOAD**: Valor, Reference, Split, Dados do Cliente
  - 🔍 **POSSÍVEIS CAUSAS**: Lista ordenada por probabilidade
  - ✅ **AÇÕES RECOMENDADAS**: Passos para resolver o problema
- ✅ Mascaramento de dados sensíveis (CPF, API Key parcial)
- ✅ Validação de formatos (tamanho de CPF, telefone, etc.)

---

## 🎯 Ações Necessárias

### Se Erro de Descriptografia (`ENCRYPTION_KEY` alterada):

1. **Opção 1: Restaurar ENCRYPTION_KEY Original**
   - Restaure a `ENCRYPTION_KEY` original no `.env`
   - Reinicie o sistema

2. **Opção 2: Reconfigurar Gateways (RECOMENDADO)**
   - Acesse `/settings` no painel administrativo
   - Reconfigure cada gateway com as credenciais corretas
   - As novas credenciais serão criptografadas com a `ENCRYPTION_KEY` atual

### Se Paradise Retornando 400:

1. **Verificar no Painel Paradise:**
   - ✅ Product Hash existe e está ativo
   - ✅ API Key está ativa e tem permissões para criar transações
   - ✅ Store ID existe e tem permissão para split

2. **Verificar Configuração no Sistema:**
   - Acesse `/settings` no painel administrativo
   - Verifique se `api_key` começa com `sk_`
   - Verifique se `product_hash` começa com `prod_`
   - Verifique se `store_id` está correto

3. **Verificar Logs:**
   - Procure por seção `🔍 ===== DIAGNÓSTICO PARADISE 400 BAD REQUEST =====`
   - Siga as **AÇÕES RECOMENDADAS** indicadas nos logs

---

## 📊 Melhorias de Logging

### Antes:
```
❌ Paradise API Error: 400
❌ Response: {"status":"error","message":"..."}
```

### Depois:
```
🔍 ===== DIAGNÓSTICO PARADISE 400 BAD REQUEST =====
   Mensagem da API: Não foi possível processar seu pagamento...
   Acquirer: ParadiseBank
   ════════════════════════════════════════════════
   🔑 CREDENCIAIS ENVIADAS:
   - API Key: sk_533e344... (len=64)
   - Product Hash: prod_d3f55c48315... (valido=✅)
   - Store ID: 177
   ════════════════════════════════════════════════
   📊 PAYLOAD:
   - Valor: R$ 19.97 (1997 centavos)
   - Reference: BOT44-1763743109-...
   - Split: 1.0% (19 centavos)
   - Cliente: Paulo | pixBOT441...@bot.digital
   - CPF: 252*** (len=11)
   - Telefone: 11055*** (len=11)
   ════════════════════════════════════════════════
   🔍 POSSÍVEIS CAUSAS (em ordem de probabilidade):
   1. ❌ API Key inválida ou sem permissões
      → Verificar se api_key começa com 'sk_' e está ativa no painel Paradise
   2. ❌ Product Hash não existe ou foi deletado no painel Paradise
      → Verificar se 'prod_d3f55c48315...' existe no painel Paradise
   ...
   ✅ AÇÕES RECOMENDADAS:
   1. Verificar no painel Paradise se Product Hash existe
   2. Verificar no painel Paradise se API Key está ativa
   ...
```

---

## 🔒 Segurança

- ✅ Dados sensíveis mascarados nos logs (CPF, API Key parcial)
- ✅ Validação de formato antes de usar credenciais
- ✅ Erros de descriptografia não expõem informações sensíveis

---

## ✅ Status

- [x] Detecção de erros de descriptografia
- [x] Validação prévia de credenciais
- [x] Validação específica por gateway
- [x] Remoção de fallback padrão (Paradise)
- [x] Diagnóstico detalhado para erro 400
- [x] Logs estruturados e informativos
- [x] Validação de formato de credenciais

---

**Última atualização**: 2025-01-21
