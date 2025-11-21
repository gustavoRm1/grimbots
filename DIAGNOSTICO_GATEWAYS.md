# 🔍 DIAGNÓSTICO: Gateways Não Funcionando

## 📊 Problema Identificado

Os logs mostram erros de descriptografia de credenciais:
```
2025-11-21 16:19:30,852 - ERROR - Erro ao descriptografar api_key gateway 6
2025-11-21 16:19:30,853 - ERROR - Erro ao descriptografar split_user_id gateway 5
```

## 🔍 Causa Raiz

A `ENCRYPTION_KEY` foi alterada ou não está correta no ambiente. Quando as credenciais são descriptografadas:
1. As properties do modelo `Gateway` tentam descriptografar usando `ENCRYPTION_KEY` atual
2. Se a chave estiver incorreta, a descriptografia falha
3. As properties retornam `None` (tratado no try/except)
4. Os gateways são criados com credenciais `None`
5. As APIs dos gateways retornam erro 400 (credenciais inválidas)

## ✅ Correções Implementadas

### 1. Validação Antes de Criar Gateway (`bot_manager.py`)
- Verifica se credenciais foram descriptografadas corretamente
- Compara campos internos (`_api_key`, `_product_hash`) com properties descriptografadas
- Se campo interno existe mas property retorna `None` → erro de descriptografia detectado
- Retorna erro claro com instruções para reconfigurar gateway

### 2. Logs Melhorados (`utils/encryption.py`)
- Logs detalhados quando descriptografia falha
- Mostra tipo de erro, valor tentado, status da ENCRYPTION_KEY
- Instruções claras de como resolver

### 3. Validação no GatewayFactory (já existia, mantida)
- Valida credenciais obrigatórias por gateway
- Não cria gateway se credenciais estiverem ausentes

## 🛠️ Como Resolver

### Opção 1: Restaurar ENCRYPTION_KEY Original
Se você tem backup da `ENCRYPTION_KEY` original:
```bash
# Editar .env
nano .env

# Adicionar/atualizar:
ENCRYPTION_KEY=sua_chave_original_aqui
```

### Opção 2: Reconfigurar Gateways (Recomendado)
Se não tem a chave original, precisa reconfigurar todos os gateways:

1. **Acesse a página de Settings**:
   - `/settings` → Aba "Gateways"

2. **Para cada gateway configurado**:
   - Clique em "Apagar Credenciais"
   - Reconfigure com as credenciais corretas

3. **Gateways Afetados**:
   - Paradise: `api_key`, `product_hash`
   - WiinPay: `api_key`, `split_user_id`
   - SyncPay: `client_id`, `client_secret`
   - PushynPay: `api_key`
   - Átomo Pay: `api_token`
   - Outros...

### Opção 3: Gerar Nova ENCRYPTION_KEY (Para Novos Gateways)
Se vai reconfigurar todos os gateways, pode gerar nova chave:
```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```
Adicione a saída ao `.env`.

⚠️ **ATENÇÃO**: Se gerar nova chave, TODOS os gateways existentes precisam ser reconfigurados.

## 📋 Checklist de Verificação

- [ ] Verificar se `ENCRYPTION_KEY` está no `.env`
- [ ] Verificar se `ENCRYPTION_KEY` não foi alterada recentemente
- [ ] Ver logs para identificar quais gateways estão falhando
- [ ] Reconfigurar gateways afetados
- [ ] Testar criação de PIX após reconfiguração

## 🔄 Próximos Passos

1. Verificar logs para identificar todos os gateways afetados
2. Decidir: restaurar chave original OU reconfigurar gateways
3. Aplicar solução escolhida
4. Validar que gateways voltaram a funcionar

