# 📋 RESUMO FINAL PRÉ-DEPLOY - Meta Pixel Tracking

**Status:** ✅ Hotfix aplicado | ⏳ Aguardando validação final

---

## ✅ O QUE JÁ FOI FEITO

### 1. Hotfix Aplicado
- ✅ Commit movido para ANTES de enviar Meta Pixel (app.py linha ~7973)
- ✅ Logs de deduplicação adicionados (app.py linha ~7520)
- ✅ Logs de recuperação de tracking melhorados (bot_manager.py linha ~4057)
- ✅ `creation_time` já removido anteriormente
- ✅ Idempotência verificada (`meta_purchase_sent` guard presente)

### 2. Análise de Código
- ✅ UmbrellaPag não envia `customer.id` inválido (já corrigido)
- ✅ `fbclid` = String(255) no model (OK)
- ✅ `tracking_token` = String(200) no model (OK)
- ⚠️ `meta_event_id` = String(100) (pode ser curto, mas aceitável)
- ❌ `pageview_event_id` **NÃO EXISTE** no Payment model

---

## 🚨 PROBLEMA CRÍTICO IDENTIFICADO

### `pageview_event_id` não está no Payment model

**Impacto:**
- Se Redis expirar (TTL 30 dias) ou falhar, Purchase não conseguirá reutilizar `pageview_event_id` do PageView
- Deduplicação falhará → Meta não atribuirá como "Navegador + Servidor"

**Solução:**
1. Adicionar coluna `pageview_event_id VARCHAR(256)` ao Payment
2. Salvar `pageview_event_id` no Payment quando gerar PIX (bot_manager.py)
3. Usar Payment como fallback se Redis estiver vazio (app.py)

**Migration SQL (NÃO APLICAR SEM CONFIRMAÇÃO):**
```sql
BEGIN;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS pageview_event_id VARCHAR(256);
CREATE INDEX IF NOT EXISTS idx_payments_pageview_event_id ON payments(pageview_event_id);
COMMIT;
```

---

## 📤 COMANDOS PARA EXECUTAR NO SERVIDOR

### Execute estes 5 comandos e cole as saídas EXATAS:

#### 1. Schema do banco
```bash
psql -c "\d+ payments"
```

#### 2. Tamanhos das colunas
```bash
psql -c "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name='payments' AND column_name IN ('tracking_token','fbclid','pageview_event_id','meta_event_id');"
```

#### 3. Verificar truncamento
```bash
psql -c "SELECT payment_id, length(fbclid) AS fbclid_len, length(tracking_token) AS token_len, length(meta_event_id) AS event_id_len FROM payments WHERE fbclid IS NOT NULL ORDER BY created_at DESC LIMIT 20;"
```

#### 4. Redis (pegar token real)
```bash
# Listar tokens recentes
redis-cli KEYS "tracking:*" | tail -n 10

# Pegar conteúdo de um token (substituir <TOKEN>)
redis-cli GET "tracking:<TOKEN>"
```

#### 5. Logs após simular webhook
```bash
# Após enviar curl do webhook paid, rodar:
tail -n 200 logs/rq-webhook.log | grep -A 5 -B 5 "Purchase ENVIADO\|Meta Purchase\|paid e commitado"
tail -n 200 logs/celery.log | grep -A 5 -B 5 "Purchase ENVIADO\|Deduplicação\|Events Received"
```

---

## ✅ CHECKLIST FINAL

Marque cada item após validar:

- [ ] **Schema:** `fbclid` = varchar(255) ou text
- [ ] **Schema:** `tracking_token` = varchar(200) ou maior
- [ ] **Schema:** `pageview_event_id` existe (ou migration aplicada) ❌ **CRÍTICO**
- [ ] **Schema:** `meta_event_id` = varchar(100) ou maior (aceitável)
- [ ] **Redis:** `tracking:<token>` contém `pageview_event_id`, `fbp`, `fbc`, `fbclid` full
- [ ] **Código:** `creation_time` não está presente ✅
- [ ] **Código:** Webhook faz commit ANTES de enviar Meta Pixel ✅
- [ ] **Código:** `meta_purchase_sent` guard presente ✅
- [ ] **ENV:** `ENCRYPTION_KEY` exportada nos workers
- [ ] **Gateway:** UmbrellaPag não envia `customer.id` inválido ✅
- [ ] **Teste:** Simulação webhook paid mostra logs corretos
- [ ] **Meta:** 2-3 vendas reais confirmadas como "Navegador + Servidor"

---

## 🚀 PRÓXIMOS PASSOS

1. **Executar comandos acima** e cole saídas
2. **Validar schema** (especialmente `pageview_event_id`)
3. **Aplicar migration** se necessário (com backup!)
4. **Testar webhook paid** (simulação)
5. **Validar no Meta Events Manager** após 1-2 vendas reais

---

## 🔄 ROLLBACK (se necessário)

```bash
git checkout main
git reset --hard origin/main
systemctl restart start_rq_worker.service celery.service grimbots.service
```

**Nota:** Se migration foi aplicada, reverter com:
```sql
ALTER TABLE payments DROP COLUMN IF EXISTS pageview_event_id;
```

---

**Aguardando suas saídas dos 5 comandos para análise final e autorização de deploy.**

