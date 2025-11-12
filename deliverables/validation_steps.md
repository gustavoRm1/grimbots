# Validation Steps

1. **Confirmar variÃ¡veis de ambiente**
   ```bash
   cd /root/grimbots
   grep -n "^ENCRYPTION_KEY=" .env || echo "ENCRYPTION_KEY=9zyoXLwUS3CY4bzTqyB1NzdQWT3R3js7ehgXpssRK_Y=" >> .env
   set -a; source .env; set +a
   ```

2. **Aplicar patch e instalar dependÃªncias**
   ```bash
   git checkout -b fix/tracking-hotfix-$(date +%Y%m%d%H%M)
   bash deliverables/apply_patch.sh
   ```

3. **Reiniciar serviÃ§os (executar na VPS)**
   ```bash
   ./restart-app.sh
   pkill -f start_rq_worker.py || true
   nohup python start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &
   nohup python start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
   nohup python start_rq_worker.py tasks > logs/rq-tasks.log 2>&1 &
   pkill -f celery || true
   nohup celery -A celery_app worker -l info > logs/celery.log 2>&1 &
   ```

4. **Clique de teste e verificaÃ§Ã£o no Redis**
   - Acesse `https://app.grimbots.online/go/<slug>?grim=TESTE&fbclid=FBCLID_TESTE` em um navegador.
   - Anote o `tracking_token` do parÃ¢metro `tt` ou recupere pelo log.
   ```bash
   redis-cli GET tracking:<tracking_token>
   ```
   Esperado: JSON com `pageview_event_id`, `pageview_ts`, `fbp`, `fbc`, `client_ip`, `client_ua`.

5. **Gerar pagamento de teste e validar logs**
   - Conclua um pagamento real/sandbox.
   ```bash
   tail -f logs/rq-webhook.log | grep -i Purchase
   tail -f logs/celery.log | grep -i "Events Received"
   ```
   Confirmar: `meta_purchase_sent` atualizado e Celery acusa `EventsReceived: 1`.

6. **Consulta no banco**
   ```bash
   psql -U grimbots -d grimbots -c "SELECT payment_id, status, tracking_token, meta_purchase_sent, paid_at FROM payments ORDER BY created_at DESC LIMIT 10;"
   ```

7. **Meta Events Manager (modo teste)**
   - Verificar que `PageView` (browser) e `Purchase` (server) compartilham o mesmo `event_id` e aparecem como `Deduplicated`.

