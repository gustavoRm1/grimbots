# Implementação QI 500 - Multi-Gateway e Tracking Universal

## ✅ Status da Implementação

**P0 (Urgente) - CONCLUÍDO:**
- ✅ Migration para `tracking_token` no modelo Payment
- ✅ GatewayAdapter movido para raiz e integrado ao GatewayFactory
- ✅ TrackingService V4 implementado

**P1 (Alta Prioridade) - CONCLUÍDO:**
- ✅ bot_manager atualizado para usar TrackingServiceV4
- ✅ `extract_producer_hash` adicionado à interface e implementado em AtomPay
- ✅ Webhook atualizado para usar GatewayAdapter

**P2 (Média Prioridade) - CONCLUÍDO:**
- ✅ Middleware de validação criado

## 📋 Arquivos Modificados

### Arquivos Criados:
1. `gateway_adapter.py` - Adapter para normalização de gateways
2. `migrations/migrations_add_tracking_token.py` - Migration para tracking_token
3. `middleware/gateway_validator.py` - Middleware de validação
4. `middleware/__init__.py` - Pacote de middleware

### Arquivos Modificados:
1. `models.py` - Adicionado campo `tracking_token` em Payment
2. `gateway_factory.py` - Suporte a `use_adapter` e integração com GatewayAdapter
3. `gateway_interface.py` - Adicionado método `extract_producer_hash`
4. `gateway_atomopay.py` - Implementado `extract_producer_hash`
5. `utils/tracking_service.py` - Implementado TrackingServiceV4
6. `bot_manager.py` - Integrado TrackingServiceV4 na geração de pagamentos
7. `app.py` - Webhook atualizado para usar GatewayAdapter e TrackingServiceV4

## 🚀 Como Executar

### 1. Aplicar Migration

```bash
# Aplicar migration para tracking_token
python migrations/migrations_add_tracking_token.py
```

**Rollback (se necessário):**
```bash
python migrations/migrations_add_tracking_token.py rollback
```

### 2. Verificar Implementação

```bash
# Verificar se tracking_token existe no Payment
python -c "from models import Payment, db; from app import app; app.app_context().push(); print('✅ Tracking token:', hasattr(Payment, 'tracking_token'))"
```

### 3. Testar GatewayAdapter

```python
from gateway_factory import GatewayFactory

# Criar gateway com adapter (padrão)
gateway = GatewayFactory.create_gateway('atomopay', {'api_token': 'test'})

# Criar gateway sem adapter
gateway_direct = GatewayFactory.create_gateway('atomopay', {'api_token': 'test'}, use_adapter=False)
```

### 4. Testar TrackingServiceV4

```python
from utils.tracking_service import TrackingServiceV4

tracking_service = TrackingServiceV4()

# Gerar tracking_token
token = tracking_service.generate_tracking_token(
    bot_id=1,
    customer_user_id='123456',
    fbclid='PAZ123...'
)

# Salvar tracking data
tracking_service.save_tracking_data(
    tracking_token=token,
    bot_id=1,
    customer_user_id='123456',
    fbclid='PAZ123...'
)

# Recuperar tracking data
data = tracking_service.recover_tracking_data(tracking_token=token)
```

## 🔍 Validações

### Critérios de Aceite P0:

✅ **Migration aplicada:** `tracking_token` existe na tabela `payment` e índice criado
✅ **GatewayAdapter integrado:** GatewayFactory cria gateways com adapter por padrão
✅ **TrackingServiceV4:** Métodos `generate_tracking_token`, `save_tracking_data`, `recover_tracking_data` implementados

### Critérios de Aceite P1:

✅ **bot_manager:** Gera `tracking_token` e salva no Payment e no Redis
✅ **extract_producer_hash:** Implementado na interface e em AtomPay
✅ **Webhook:** Usa GatewayAdapter para normalização e extração de producer_hash

### Critérios de Aceite P2:

✅ **Middleware:** Validação de Content-Type e gateway_type implementada

## 📊 Fluxo de Tracking V4

1. **Geração de Pagamento (`bot_manager._generate_pix_payment`):**
   - Gera `tracking_token` via `TrackingServiceV4.generate_tracking_token()`
   - Gera `fbp` e `fbc`
   - Constrói `external_ids` array
   - Salva tracking data no Redis com múltiplas chaves
   - Salva `tracking_token` no Payment

2. **Webhook (`app.payment_webhook`):**
   - Processa webhook via GatewayAdapter (normalizado)
   - Extrai `producer_hash` via adapter para multi-tenant
   - Busca Payment por múltiplas chaves (gateway_transaction_id, gateway_hash, etc)
   - Atualiza Payment com status

3. **Meta Pixel Purchase (`app.send_meta_pixel_purchase_event`):**
   - Recupera tracking data via `tracking_token` (PRIORIDADE 0)
   - Fallback para Redis (fbclid, telegram_user_id)
   - Usa `fbp`, `fbc`, `external_ids` do tracking data
   - Envia evento Purchase apenas quando status == 'paid'

## 🔐 Segurança

- **Sanitização de logs:** Campos sensíveis (api_key, api_token, etc) são mascarados nos logs
- **Rate limiting:** Webhooks têm rate limiting configurável
- **Validação de entrada:** Content-Type e gateway_type são validados

## 🐛 Troubleshooting

### Migration falha:
```bash
# Verificar se tabela payment existe
python -c "from models import Payment, db; from app import app; app.app_context().push(); print(db.inspect(db.engine).get_table_names())"
```

### GatewayAdapter não funciona:
```python
# Verificar import
from gateway_adapter import GatewayAdapter
print(GatewayAdapter)
```

### TrackingServiceV4 não salva no Redis:
```bash
# Verificar conexão Redis
python -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

## 📝 Próximos Passos (Opcional)

- [ ] Adicionar testes unitários
- [ ] Adicionar testes de integração
- [ ] Implementar validação de assinatura de webhook (HMAC)
- [ ] Dashboard de health-check dos webhooks
- [ ] Retry automático na publicação do Pixel (dead-letter queue)

## 📚 Referências

- `DIAGNOSTICO_COMPLETO_QI500.md` - Diagnóstico completo do sistema
- `PLANO_ACAO_DEFINITIVO_QI200.md` - Plano de ação original
- `RELATORIO_TECNICO_COMPLETO_QI200.md` - Relatório técnico completo

