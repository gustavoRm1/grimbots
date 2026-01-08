# Relatório Técnico do Sistema de Tracking (estado atual, pós Purchase duplo na delivery)

## 1) Fluxo end-to-end (Facebook → Redirect → Cloaker → HTML Pixel → Bot → Payment → Delivery)
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
- Pagamento confirmado → `send_payment_delivery` gera `delivery_token` e envia link `/delivery/<token>` quando Meta Pixel ativo (@app.py#348-497).
- Delivery page dispara Purchase duplo: client-side `fbq('track','Purchase', eventID=purchase_<payment.id>)` + server-side `send_meta_pixel_purchase_event` com mesmo event_id (@app.py#9977-10267; @app.py#12118-12355; templates/delivery.html).

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

## 10) Delivery Page com Purchase duplo (NOVO)
- Rota: `/delivery/<delivery_token>` (@app.py#9977-10267).
- Busca Payment por delivery_token; se status != paid, revalida no gateway e só segue se pago.
- Recupera tracking_data prioritariamente via `BotUser.tracking_session_id` → `payment.tracking_token` → Redis.
- Pool correto: tenta pool_id do tracking_data; senão primeiro PoolBot do bot.
- Pixel habilitado se `meta_tracking_enabled` e `meta_events_purchase` e credenciais presentes.
- `purchase_event_id = f"purchase_{payment.id}` persistido em `meta_event_id`; usado tanto no client quanto no server.
- `pixel_config` enviado ao template inclui: pixel_id, event_id, external_id normalizado (fbclid), fbp/fbc, tracking_token, value/currency, content_id/content_name.
- Renderiza antes de enfileirar server-side (client-side dispara primeiro para dedup automática).

### Trecho-chave: delivery_page (injeção dos dados)
```python
# app.py (delivery_page) trechos-chave
purchase_event_id = f"purchase_{payment.id}"
payment.meta_event_id = purchase_event_id
db.session.commit(); db.session.refresh(payment)

pixel_config = {
    'pixel_id': pool.meta_pixel_id if has_meta_pixel else None,
    'event_id': purchase_event_id,           # dedup client/server
    'external_id': external_id_normalized,
    'fbp': fbp_value,
    'fbc': fbc_value,
    'tracking_token': tracking_data.get('tracking_token') or payment.tracking_token,
    'value': float(payment.amount),
    'currency': 'BRL',
    'content_id': str(pool.id) if pool else str(payment.bot_id),
    'content_name': payment.product_name or payment.bot.name,
}
response = render_template('delivery.html',
    payment=payment,
    pixel_config=pixel_config,
    has_meta_pixel=has_meta_pixel,
    redirect_url=redirect_url
)
# Após render, enfileira server-side Purchase (event_id igual)
```

### Trecho-chave: delivery.html (Purchase client-side + beacon)
```html
{% if has_meta_pixel and pixel_config.pixel_id %}
<script>
  !function(f,b,e,v,n,t,s){...}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', '{{ pixel_config.pixel_id }}');
</script>
{% endif %}

<script>
// Purchase client-side deduplicado
(function() {
  {% if has_meta_pixel and pixel_config.pixel_id and pixel_config.event_id %}
  if (typeof fbq === 'undefined') return;
  fbq('track', 'Purchase', {
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}',
    content_type: 'product',
    content_name: '{{ pixel_config.content_name }}',
    content_ids: ['{{ pixel_config.content_id }}']
  }, {
    eventID: '{{ pixel_config.event_id }}' // dedup
  });
  console.log('[META PIXEL] Purchase client-side disparado', {
    eventID: '{{ pixel_config.event_id }}',
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}'
  });
  // Beacon opcional para cookies atualizados
  {% if pixel_config.tracking_token %}
  setTimeout(function() {
    const getCookie = (name) => {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop().split(';').shift();
      return null;
    };
    const fbp = getCookie('_fbp');
    const fbc = getCookie('_fbc');
    const fbi = getCookie('_fbi');
    if (fbp || fbc || fbi) {
      const payload = {
        tracking_token: '{{ pixel_config.tracking_token }}',
        _fbp: fbp,
        _fbc: fbc,
        _fbi: fbi,
        page_type: 'delivery'
      };
      navigator.sendBeacon('/api/tracking/cookies',
        new Blob([JSON.stringify(payload)], { type: 'application/json' }));
    }
  }, 800);
  {% endif %}
  {% endif %}
})();
</script>
```

## 11) Critérios de deduplicação e alinhamento client/server
- `event_id` único por Purchase: `purchase_<payment.id>` compartilhado entre browser e server.
- Pixel_id sempre do pool correto; multi-tenant respeita `PoolBot`.
- Client-side dispara primeiro; server-side enfileira após render, ambos deduplicam via event_id.
- fbp/fbc e external_id normalizado (fbclid) propagados do tracking_data/Redis ao template.

## 12) Riscos e pontos de atenção
- Se pool.meta_events_purchase desativado, delivery renderiza sem pixel (não dispara client-side).
- Se tracking_data ausente: fbp/fbc podem faltar; external_id pode cair para telegram_id hash (menor match quality).
- Se gateway não confirmar “paid” em tempo real, delivery retorna página de erro sem disparar Purchase.
- Se Celery parado, client-side ainda envia Purchase; dedup segura quando o worker voltar.

## 13) Passos mínimos se algo falhar (atualizado)
1) Garantir tabela/permissões `meta_tracking_sessions` (scripts acima).
2) Confirmar Meta Pixel por pool: `meta_tracking_enabled`, `meta_pixel_id`, `meta_access_token`, `meta_events_purchase=True`.
3) Verificar worker Celery ativo; checar logs `[META RAW RESPONSE]` para Purchase com `purchase_<payment.id>`.
4) No browser (delivery): console deve mostrar `[META PIXEL] Purchase client-side disparado` com eventID `purchase_<payment.id>`.

## 9) Passos mínimos se algo falhar
1) Garantir tabela e permissões:
   ```bash
   ./scripts/create_meta_tracking_sessions.sh "postgres://postgres:SENHA@localhost:5432/grimbots"
   ./scripts/grant_meta_tracking_sessions.sh "postgres://postgres:SENHA@localhost:5432/grimbots" grimbots
   ```
2) Reiniciar app/worker para limpar sessões de DB sujas (se houve falhas anteriores).
3) Verificar logs de PageView/Purchase em `[META RAW RESPONSE]` para confirmar recepção no Meta.
