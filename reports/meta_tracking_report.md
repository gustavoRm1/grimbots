# Relatório Técnico do Sistema de Tracking (estado atual)

## 1) Fluxo end-to-end (Facebook → Redirect → Cloaker → HTML Pixel → Bot → Delivery)
- Entrada: `GET /go/<slug>` em `public_redirect` (@app.py#6511-7054).
- Cloaker: valida antes de qualquer tracking; se bloquear, retorna `cloaker_block.html` 403 (sem alterar headers/cookies) (@app.py#6545-6578).
- Seleção de bot e métricas: incrementos atômicos em `PoolBot` e `RedirectPool` (@app.py#6598-6624).
- Identificadores: `tracking_token = uuid4().hex`, `root_event_id = f"evt_{tracking_token}"` (@app.py#6686-6689).
- Captura de IDs/cookies/UTMs/IP/UA e click_ts salvo no Redis se fbclid presente (@app.py#6643-6746).
- FBC canônico gerado se fbclid e não houver `_fbc` (@app.py#6739-6742).
- Upsert canônico em `meta_tracking_sessions` com `pageview_sent=True` (@app.py#6765-6798). Protegido com rollback em erro de permissão/tabela faltante.
- Merge e persistência do tracking no Redis via `TrackingServiceV4.save_tracking_token` (@app.py#6815-6887).
- Renderização do HTML bridge `templates/telegram_redirect.html` com `pageview_event_id = root_event_id`, `pixel_id`, `tracking_token` (@app.py#6911-7023).
- Fallback: se renderização falhar ou bot inválido, redirect 302 direto para t.me/<bot>?start=<tracking_token>.

### Trecho-chave: public_redirect (captura, upsert e render)
```python
# app.py (public_redirect) trechos essenciais
@app.route('/go/<slug>')
@limiter.limit("10000 per hour")
def public_redirect(slug):
    # Cloaker (bloqueia antes de tracking)
    if pool.meta_cloaker_enabled:
        validation_result = validate_cloaker_access(request, pool, slug)
        if not validation_result['allowed']:
            return render_template('cloaker_block.html', pool_name=pool.name, slug=slug), 403

    # Seleção de bot e métricas (atomic update)
    pool_bot = pool.select_bot()
    db.session.execute(
        update(PoolBot).where(PoolBot.id == pool_bot.id)
        .values(total_redirects=text('COALESCE(total_redirects, 0) + 1'))
    )
    db.session.commit()

    # Identificadores e payload inicial
    tracking_token = uuid.uuid4().hex
    root_event_id = f"evt_{tracking_token}"
    tracking_payload = {
        'tracking_token': tracking_token,
        'fbclid': fbclid_to_save,
        'fbp': fbp_cookie,
        'fbc': fbc_cookie,
        'fbc_origin': fbc_origin,
        'pageview_event_id': root_event_id,
        'pageview_ts': pageview_ts,
        'client_ip': user_ip if user_ip else None,
        'client_user_agent': user_agent if user_agent and user_agent.strip() else None,
        'event_source_url': request.url or f'https://{request.host}/go/{pool.slug}',
        'first_page': request.url or f'https://{request.host}/go/{pool.slug}',
        'pageview_sent': False,
        **{k: v for k, v in utms.items() if v}
    }

    # Upsert meta_tracking_sessions
    from models import MetaTrackingSession, get_brazil_time
    try:
        session_row = MetaTrackingSession.query.filter_by(tracking_token=tracking_token).first()
        now_ts = get_brazil_time()
        if not session_row:
            session_row = MetaTrackingSession(
                tracking_token=tracking_token,
                root_event_id=root_event_id,
                pageview_sent=True,
                pageview_sent_at=now_ts,
                fbclid=fbclid_to_save,
                fbc=fbc_cookie,
                fbp=fbp_cookie,
                user_external_id=None
            )
            db.session.add(session_row)
        else:
            session_row.root_event_id = session_row.root_event_id or root_event_id
            session_row.pageview_sent = True
            session_row.pageview_sent_at = now_ts
            session_row.fbclid = session_row.fbclid or fbclid_to_save
            session_row.fbc = session_row.fbc or fbc_cookie
            session_row.fbp = session_row.fbp or fbp_cookie
        db.session.commit()
        tracking_payload['pageview_sent'] = True
    except Exception as e:
        logger.error("[META TRACKING SESSION] ...", exc_info=True)
        db.session.rollback()

    # Render HTML bridge com event_id e tracking_token
    return render_template('telegram_redirect.html',
        bot_username=bot_username_safe,
        tracking_token=tracking_token_safe,
        pixel_id=pixel_id_to_template,
        utmify_pixel_id=utmify_pixel_id_to_template,
        pageview_event_id=pageview_event_id_safe,
        fbclid=sanitize_js_value(fbclid) if fbclid else '',
        utm_source=sanitize_js_value(request.args.get('utm_source', '')),
        utm_campaign=sanitize_js_value(request.args.get('utm_campaign', '')),
        utm_medium=sanitize_js_value(request.args.get('utm_medium', '')),
        utm_content=sanitize_js_value(request.args.get('utm_content', '')),
        utm_term=sanitize_js_value(request.args.get('utm_term', '')),
        grim=sanitize_js_value(request.args.get('grim', ''))
    )
```

## 2) HTML bridge (templates/telegram_redirect.html)
- Carrega `clientParamBuilder` para capturar `_fbc`, `_fbp`, `_fbi` e envia para `/api/tracking/cookies` via Beacon (@telegram_redirect.html#8-83).
- Carrega Meta Pixel JS e dispara `fbq('track','PageView', {}, { eventID: '<server pageview_event_id>' })` (@telegram_redirect.html#84-103).
- Botão `Start` redireciona para o bot com `start=<tracking_token>` (@telegram_redirect.html#218-249).

### Trecho-chave: PageView JS dedicado
```html
<!-- telegram_redirect.html -->
<script>
    // clientParamBuilder para fbc/fbp/_fbi
    ...
    // Meta Pixel JS
    fbq('init', '{{ pixel_id }}');
    fbq('track', 'PageView', {}, { eventID: '{{ pageview_event_id }}' });
</script>
```

### Trecho-chave: Captura e envio de cookies do browser para o backend
```html
<!-- telegram_redirect.html -->
const trackingToken = '{{ tracking_token }}';
const updated_cookies = await clientParamBuilder.processAndCollectAllParams(currentUrl, getIpFn);
if (trackingToken && (updated_cookies['_fbc'] || updated_cookies['_fbp'] || updated_cookies['_fbi'])) {
    const cookiePayload = JSON.stringify({
        tracking_token: trackingToken,
        _fbp: updated_cookies['_fbp'] || null,
        _fbc: updated_cookies['_fbc'] || null,
        _fbi: updated_cookies['_fbi'] || null
    });
    navigator.sendBeacon('/api/tracking/cookies', new Blob([cookiePayload], { type: 'application/json' }));
}
```

## 3) PageView server-side
- Função `send_meta_pixel_pageview_event` (@app.py#10516-10920).
- `event_id`: `root_event_id` (evt_<tracking_token>) recebido de `public_redirect` (@app.py#10899-10909).
- `event_time`: `pageview_ts` salvo no tracking_data ou `int(time.time())` se ausente (@app.py#10897-10904).
- `external_id`: fbclid normalizado (hash MD5 se >80 chars) (@app.py#10570-10599).
- `user_data`: inclui external_id, fbp/fbc (param builder/Redis), client_ip (param builder ou get_user_ip), client_user_agent (@app.py#10644-10703, @app.py#10782-10841).
- Enfileira no Celery `send_meta_event` (logs `[META RAW RESPONSE]`) (@app.py#10911-10918).

### Trecho-chave: construção do PageView (servidor)
```python
# app.py (send_meta_pixel_pageview_event)
external_id = normalize_external_id(external_id_raw)
event_id = pageview_event_id or f\"pageview_{pool.id}_{int(time.time())}_{external_id[:8] if external_id else 'unknown'}\"
...
event_data = {
    'event_name': 'PageView',
    'event_time': event_time,
    'event_id': event_id,
    'action_source': 'website',
    'event_source_url': event_source_url,
    'user_data': user_data,
    'custom_data': custom_data
}
task = send_meta_event.delay(...)
```

### Trecho-chave: Enfileiramento e logging bruto (PageView)
```python
# app.py (send_meta_pixel_pageview_event)
task = send_meta_event.delay(
    pixel_id=pool.meta_pixel_id,
    access_token=access_token,
    event_data=event_data,
    test_code=pool.meta_test_event_code
)
logger.info(f\"📤 PageView enfileirado: Pool {pool.id} | Event ID: {event_id} | Task: {task.id}\")
```

## 4) Funil no bot
- `tracking_token` está no `/start`; estados do funil armazenados. O tracking_data permanece no Redis pelo tracking_token.
- `meta_tracking_sessions` guarda `root_event_id` e `pageview_sent` como fonte canônica; usada apenas como store auxiliar (sem gating em Purchase após patch atual).

## 5) Purchase server-side (CAPI)
- Função `send_meta_pixel_purchase_event(payment)` (@app.py#12118-12355).
- `event_id`: exclusivo para Purchase, `purchase_{payment.id}` (@app.py#12194-12201).
- `event_time`: `int(payment.created_at.timestamp())` (@app.py#12202-12204).
- `user_data`: external_id estável (hash de `customer_user_id` ou `bot_user.id`), fbc/fbp, client_ip, client_user_agent; fbclid não vai em external_id (@app.py#12223-12241).
- `action_source`: website; `event_source_url` derivado de tracking_data ou slug/bot (@app.py#12243-12254).
- Enfileira direto no Celery (`send_meta_event`) sem gating de PageView; marca `meta_purchase_sent` após enfileirar (@app.py#12272-12292).
- Logs brutos no worker: `[META RAW RESPONSE]` em `utils/meta_pixel.py` e `celery_app.py`.

### Trecho-chave: Purchase server-side
```python
# app.py (send_meta_pixel_purchase_event)
purchase_event_id = f\"purchase_{payment.id}\"
event_time = int(payment.created_at.timestamp()) if getattr(payment, \"created_at\", None) else int(time.time())
stable_external_id = hashlib.sha256(str(payment.customer_user_id).encode(\"utf-8\")).hexdigest() if payment.customer_user_id else ...
user_data = MetaPixelAPI._build_user_data(
    customer_user_id=str(payment.customer_user_id) if payment.customer_user_id else None,
    external_id=stable_external_id,
    ...
    fbp=fbp_value,
    fbc=fbc_value,
)
event_data = {
    \"event_name\": \"Purchase\",
    \"event_time\": event_time,
    \"event_id\": purchase_event_id,
    \"action_source\": \"website\",
    \"event_source_url\": event_source_url,
    \"user_data\": user_data,
    \"custom_data\": custom_data,
}
task = send_meta_event.delay(**kwargs)
```

## 6) Persistência/infra
- Tabela `meta_tracking_sessions` definida em `models.py` (@models.py#26-44). Campos: id, tracking_token (unique), root_event_id, pageview_sent, pageview_sent_at, fbclid, fbc, fbp, user_external_id, created_at, updated_at.
- Scripts auxiliares:
  - `scripts/create_meta_tracking_sessions.sh` cria a tabela (Postgres).
  - `scripts/grant_meta_tracking_sessions.sh` aplica GRANT na tabela e sequência para o usuário da aplicação.

### Trecho-chave: definição do modelo
```python
# models.py
class MetaTrackingSession(db.Model):
    __tablename__ = \"meta_tracking_sessions\"
    id = db.Column(db.Integer, primary_key=True)
    tracking_token = db.Column(db.Text, unique=True, nullable=False, index=True)
    root_event_id = db.Column(db.Text, nullable=False)
    pageview_sent = db.Column(db.Boolean, default=False)
    pageview_sent_at = db.Column(db.DateTime)
    fbclid = db.Column(db.Text)
    fbc = db.Column(db.Text)
    fbp = db.Column(db.Text)
    user_external_id = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_brazil_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time, nullable=False)
```

### Scripts auxiliares (execução)
```bash
# Criação da tabela (Postgres)
./scripts/create_meta_tracking_sessions.sh \"postgres://USER:PASS@HOST:5432/DB\"

# Concessão de permissão ao usuário da app
./scripts/grant_meta_tracking_sessions.sh \"postgres://USER_PRIV:PASS@HOST:5432/DB\" APP_USER
```

## 7) Condições para funcionamento robusto
- Banco: tabela criada + permissões concedidas ao usuário de app (SELECT/INSERT/UPDATE/DELETE; USAGE/SELECT/UPDATE na sequência).
- Meta Pixel: `meta_tracking_enabled=True`, `meta_pixel_id`, `meta_access_token` válidos por pool.
- Celery/Workers: ativos para processar `send_meta_event` (PageView/Purchase).
- HTML bridge renderizando (evitar cair no fallback por erro de renderização ou bot sem username).
- Rede/infra: Postgres acessível, pg_hba/config corretos; logs acessíveis para grep `[META RAW RESPONSE]`.

## 8) Observações de estado atual
- Purchase client-side (fbq Purchase) foi removido; apenas server-side envia Purchase com `event_id = purchase_<payment.id>`.
- `meta_tracking_sessions` hoje não bloqueia Purchase; serve como store canônica. Erros de permissão nessa tabela foram mitigados via GRANT.
- Rollback adicionado no upsert de `meta_tracking_sessions` para evitar transações sujas e 500s (@app.py#6791-6797).

## 9) Passos mínimos se algo falhar
1) Garantir tabela e permissões:
   ```bash
   ./scripts/create_meta_tracking_sessions.sh "postgres://postgres:SENHA@localhost:5432/grimbots"
   ./scripts/grant_meta_tracking_sessions.sh "postgres://postgres:SENHA@localhost:5432/grimbots" grimbots
   ```
2) Reiniciar app/worker para limpar sessões de DB sujas (se houve falhas anteriores).
3) Verificar logs de PageView/Purchase em `[META RAW RESPONSE]` para confirmar recepção no Meta.
