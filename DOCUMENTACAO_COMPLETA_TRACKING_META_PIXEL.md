# 📊 DOCUMENTAÇÃO COMPLETA - SISTEMA DE TRACKING META PIXEL

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Fluxo Completo de Tracking](#fluxo-completo-de-tracking)
4. [Componentes Principais](#componentes-principais)
5. [Explicação Linha por Linha](#explicação-linha-por-linha)
6. [Eventos Meta Pixel](#eventos-meta-pixel)
7. [Matching e Deduplicação](#matching-e-deduplicação)
8. [Configuração](#configuração)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 VISÃO GERAL

O sistema de tracking Meta Pixel é uma implementação **server-side** (Conversions API) que permite rastrear eventos de conversão de forma 100% confiável, sem depender de JavaScript do lado do cliente (evita bloqueio de AdBlockers).

### Características Principais:
- ✅ **Server-side tracking** (Conversions API) - 100% confiável
- ✅ **Zero duplicação** garantida via `event_id` único
- ✅ **Alta Match Quality** (8-10/10) via dados completos (`external_id`, `fbp`, `fbc`, `ip`, `user_agent`)
- ✅ **Retry automático** com backoff exponencial
- ✅ **Processamento assíncrono** (Celery) - não bloqueia o redirect
- ✅ **Deduplicação** automática no Meta (mesmo `event_id` = 1 evento)
- ✅ **Configuração por Pool** (não por bot) - 1 campanha = 1 pool = 1 pixel

### Eventos Rastreados:
1. **PageView** - Quando usuário acessa o redirect (`/go/{slug}`)
2. **ViewContent** - Quando usuário inicia conversa com bot (`/start`)
3. **Purchase** - Quando pagamento é confirmado (na página de entrega)

---

## 🏗️ ARQUITETURA

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO DE TRACKING                            │
└─────────────────────────────────────────────────────────────────┘

1. USUÁRIO CLICA NO ANÚNCIO FACEBOOK
   ↓
   URL: https://app.grimbots.online/go/pool1?grim=teste&fbclid=xxx&utm_source=FB

2. REDIRECT (/go/{slug}) - app.py:public_redirect()
   ↓
   ├─ Validação Cloaker (fbclid obrigatório se UTM presente)
   ├─ Geração tracking_token (UUID 32 chars)
   ├─ Salvamento no Redis (tracking:{token})
   └─ Envio PageView (assíncrono - Celery)
       ↓
   HTML renderizado → Injeção cookies (_fbp, _fbc)
   ↓
   Redirect para Telegram: https://t.me/bot?start={tracking_token}

3. USUÁRIO CLICA /START NO TELEGRAM
   ↓
   bot_manager.py:_handle_start_command()
   ├─ Salva tracking_token no BotUser.tracking_session_id
   ├─ Recupera dados do Redis (fbclid, fbp, fbc, UTMs)
   └─ Envio ViewContent (assíncrono - Celery)

4. USUÁRIO COMPRA E ACESSA PÁGINA DE ENTREGA
   ↓
   app.py:delivery_page()
   ├─ Recupera tracking_data do Redis (via tracking_token)
   └─ Renderiza HTML com Meta Pixel JS
       ↓
   Meta Pixel JS dispara Purchase (client-side)
   ↓
   OU Purchase via server-side (se configurado)

5. META ATRIBUI VENDA À CAMPANHA
   ↓
   PageView → ViewContent → Purchase = CONVERSÃO ATRIBUTA
```

---

## 🔄 FLUXO COMPLETO DE TRACKING

### FASE 1: REDIRECT (PageView)

**Arquivo:** `app.py`  
**Função:** `public_redirect(slug)`  
**Localização:** Linha ~4252

#### Passo 1.1: Validação Cloaker

```python
# app.py:4252-4320
def public_redirect(slug):
    """
    Redirect público - Cloaker + Tracking Meta Pixel
    """
    # Buscar pool pelo slug
    pool = RedirectPool.query.filter_by(slug=slug).first()
    
    # Validar acesso (cloaker)
    if not validate_cloaker_access(request, pool):
        return "Acesso bloqueado", 403
    
    # Extrair parâmetros da URL
    fbclid = request.args.get('fbclid', '')
    grim_param = request.args.get('grim', '')
    
    # ✅ CRÍTICO: fbclid é obrigatório para tracking
    if not fbclid:
        logger.warning("⚠️ fbclid ausente - tracking pode ser prejudicado")
```

**Explicação:**
- O sistema busca o `RedirectPool` pelo `slug` da URL
- Valida o acesso via cloaker (verifica `fbclid` e `grim` se necessário)
- Extrai `fbclid` e `grim` da URL para tracking

#### Passo 1.2: Geração tracking_token

```python
# app.py:4385-4398
if pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token:
    tracking_service_v4 = TrackingServiceV4()
    
    # ✅ CRÍTICO: Gerar tracking_token APENAS no redirect (não no bot!)
    tracking_token = uuid.uuid4().hex  # UUID 32 chars (sem hífens)
    pageview_event_id = f"pageview_{uuid.uuid4().hex}"
    pageview_ts = int(time.time())
    TRACKING_TOKEN_TTL = TrackingServiceV4.TRACKING_TOKEN_TTL_SECONDS  # 30 dias
```

**Explicação:**
- Gera um `tracking_token` único (UUID 32 caracteres)
- Gera um `pageview_event_id` único para deduplicação
- Armazena timestamp do PageView
- TTL padrão: 30 dias (dados persistem no Redis)

#### Passo 1.3: Captura Cookies Meta (_fbp, _fbc)

```python
# app.py:4400-4448
# ✅ CRÍTICO V4.1: Capturar FBC do cookie OU dos params (JS pode ter enviado)
# Prioridade: cookie > params (cookie é mais confiável)
fbp_cookie = request.cookies.get('_fbp') or request.args.get('_fbp_cookie')
fbc_cookie = request.cookies.get('_fbc') or request.args.get('_fbc_cookie')

# ✅ FBP: Gerar se não tiver (fallback)
if not fbp_cookie and not is_crawler_request:
    fbp_cookie = TrackingService.generate_fbp()
    # Formato: fb.1.{timestamp_ms}.{random}
    # timestamp: tempo UNIX em MILISSEGUNDOS (não segundos!)

# ✅ FBC: Priorizar cookie REAL (MAIS CONFIÁVEL)
if fbc_cookie:
    fbc_value = fbc_cookie.strip()
    fbc_origin = 'cookie'  # ✅ ORIGEM REAL - Meta confia e atribui
elif fbclid and not is_crawler_request:
    # Gerar _fbc baseado em fbclid (conforme documentação Meta)
    fbc_value = TrackingService.generate_fbc(fbclid)
    # Formato: fb.1.{timestamp_ms}.{fbclid}
    fbc_origin = 'generated_from_fbclid'
else:
    fbc_value = None
    fbc_origin = None
```

**Explicação:**
- **`_fbp` (Facebook Pixel)**: Cookie do browser ou gerado no servidor
  - Formato: `fb.1.{timestamp_ms}.{random}`
  - Timestamp em **MILISSEGUNDOS** (não segundos!)
- **`_fbc` (Facebook Click ID)**: Cookie do browser ou gerado baseado em `fbclid`
  - Prioridade: cookie do browser > gerado baseado em `fbclid`
  - Formato: `fb.1.{timestamp_ms}.{fbclid}`
- **Origem do FBC**: Rastreado (`cookie` ou `generated_from_fbclid`) para garantir qualidade

#### Passo 1.4: Salvamento no Redis

```python
# app.py:4470-4514
tracking_payload = {
    'tracking_token': tracking_token,
    'fbclid': fbclid_to_save,  # ✅ fbclid completo (até 255 chars)
    'fbp': fbp_cookie,
    'fbc': fbc_cookie if fbc_cookie and fbc_origin else None,
    'fbc_origin': fbc_origin,  # ✅ Rastrear origem: 'cookie' ou 'generated_from_fbclid'
    'pageview_event_id': pageview_event_id,
    'pageview_ts': pageview_ts,
    'client_ip': user_ip,  # IP do usuário (prioriza Cloudflare headers)
    'client_user_agent': user_agent,  # User-Agent do browser
    'grim': grim_param or None,
    'event_source_url': request.url,
    'first_page': request.url,
    **{k: v for k, v in utms.items() if v}  # UTMs (utm_source, utm_campaign, etc)
}

# ✅ SALVAR NO REDIS (TTL 30 dias)
ok = tracking_service_v4.save_tracking_token(tracking_token, tracking_payload, ttl=TRACKING_TOKEN_TTL)
```

**Explicação:**
- Salva **todos os dados** de tracking no Redis com chave `tracking:{tracking_token}`
- TTL: 30 dias (dados persistem para matching com Purchase)
- **Índices adicionais:**
  - `tracking:fbclid:{fbclid}` → `tracking_token` (busca rápida por fbclid)
  - `tracking:payment:{payment_id}` → payload completo (fallback)
  - `tracking:chat:{telegram_user_id}` → payload completo (fallback)

#### Passo 1.5: Envio PageView (Assíncrono)

```python
# app.py:4525-4530
external_id, utm_data, pageview_context = send_meta_pixel_pageview_event(
    pool,
    request,
    pageview_event_id=pageview_event_id if not is_crawler_request else None,
    tracking_token=tracking_token
)
```

**Função:** `send_meta_pixel_pageview_event()`  
**Arquivo:** `app.py`  
**Localização:** Linha ~7720

```python
# app.py:7720-8092
def send_meta_pixel_pageview_event(pool, request, pageview_event_id=None, tracking_token=None):
    """
    Enfileira evento PageView para Meta Pixel (ASSÍNCRONO)
    """
    # ✅ VERIFICAÇÃO 0: É crawler? (NÃO enviar PageView para crawlers)
    user_agent = request.headers.get('User-Agent', '')
    if is_crawler(user_agent):
        logger.info(f"🤖 CRAWLER DETECTADO - PageView NÃO será enviado")
        return None, {}, {}
    
    # ✅ VERIFICAÇÃO 1: Pool tem Meta Pixel configurado?
    if not pool.meta_tracking_enabled or not pool.meta_pixel_id or not pool.meta_access_token:
        return None, {}, {}
    
    # ✅ VERIFICAÇÃO 2: Evento PageView está habilitado?
    if not pool.meta_events_pageview:
        return None, {}, {}
    
    # Extrair fbclid e grim
    fbclid_from_request = request.args.get('fbclid', '')
    grim_param = request.args.get('grim', '')
    
    # ✅ PRIORIDADE: fbclid como external_id (obrigatório para matching)
    if fbclid_from_request:
        external_id_raw = fbclid_from_request
    elif grim_param:
        external_id_raw = grim_param  # Fallback
    else:
        external_id_raw = MetaPixelHelper.generate_external_id()  # Sintético
    
    # ✅ CRÍTICO: Normalizar external_id para garantir matching consistente
    external_id = normalize_external_id(external_id_raw)
    # Se fbclid > 80 chars, normalizar para hash MD5 (32 chars)
    # MESMO algoritmo usado em todos os eventos!
    
    # Gerar event_id único
    event_id = pageview_event_id or f"pageview_{pool.id}_{int(time.time())}_{external_id[:8]}"
    
    # Recuperar tracking_data do Redis (se disponível)
    tracking_data = {}
    if tracking_token:
        tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
    
    # Recuperar fbp/fbc (prioridade: Redis > cookie > gerar)
    fbp_value = tracking_data.get('fbp') or request.cookies.get('_fbp')
    fbc_value = tracking_data.get('fbc') or request.cookies.get('_fbc')
    fbc_origin = tracking_data.get('fbc_origin')
    
    # ✅ CRÍTICO: Validar fbc_origin (ignorar fbc sintético)
    if fbc_value and fbc_origin == 'synthetic':
        fbc_value = None  # Meta não atribui com fbc sintético
    
    # Gerar fbp se não tiver
    if not fbp_value:
        fbp_value = TrackingService.generate_fbp()
    
    # ✅ CRÍTICO: Construir user_data usando MetaPixelAPI._build_user_data()
    user_data = MetaPixelAPI._build_user_data(
        customer_user_id=None,  # Não temos telegram_user_id no PageView
        external_id=external_id,  # ✅ fbclid normalizado (será hashado)
        email=None,
        phone=None,
        client_ip=get_user_ip(request),  # IP do usuário
        client_user_agent=request.headers.get('User-Agent', ''),
        fbp=fbp_value,  # ✅ _fbp do cookie ou Redis
        fbc=fbc_value  # ✅ _fbc do cookie, Redis ou gerado
    )
    
    # ✅ VALIDAÇÃO: Garantir que external_id existe (obrigatório para Conversions API)
    if not user_data.get('external_id'):
        user_data['external_id'] = [MetaPixelAPI._hash_data(external_id)]
    
    # Construir custom_data (UTMs, campaign_code, etc)
    custom_data = {
        'pool_id': pool.id,
        'pool_name': pool.name,
        'utm_source': utm_data.get('utm_source'),
        'utm_campaign': utm_data.get('utm_campaign'),
        'campaign_code': campaign_code_value,  # grim tem prioridade
        # ... outros campos
    }
    
    # Construir event_data
    event_data = {
        'event_name': 'PageView',
        'event_time': int(time.time()),
        'event_id': event_id,  # ✅ Único para deduplicação
        'action_source': 'website',
        'event_source_url': request.url,  # ✅ URL do redirect
        'user_data': user_data,  # ✅ Dados do usuário (external_id, fbp, fbc, ip, ua)
        'custom_data': custom_data  # ✅ Dados customizados (UTMs, etc)
    }
    
    # ✅ ENFILEIRAR (NÃO ESPERA RESPOSTA)
    task = send_meta_event.delay(
        pixel_id=pool.meta_pixel_id,
        access_token=access_token,
        event_data=event_data,
        test_code=pool.meta_test_event_code
    )
    
    logger.info(f"📤 PageView enfileirado: Event ID: {event_id} | Task: {task.id}")
    
    # Retornar context para Purchase
    pageview_context = {
        'pageview_event_id': event_id,
        'fbp': fbp_value,
        'fbc': fbc_value,
        'client_ip': get_user_ip(request),
        'client_user_agent': request.headers.get('User-Agent', ''),
        'event_source_url': request.url,
        'tracking_token': tracking_token
    }
    
    return external_id, utm_data, pageview_context
```

**Explicação:**
- Função **não bloqueia** o redirect (assíncrona via Celery)
- Normaliza `external_id` (fbclid > 80 chars → MD5 hash)
- Recupera `fbp`/`fbc` do Redis ou cookie
- Constrói `user_data` com máximo de atributos (Match Quality 8-10/10)
- Enfileira evento via Celery (worker processa em background)
- Retorna `pageview_context` para vincular com Purchase

---

### FASE 2: TELEGRAM /START (ViewContent)

**Arquivo:** `bot_manager.py`  
**Função:** `_handle_start_command()`  
**Localização:** Linha ~3500+

#### Passo 2.1: Processar /start e Salvar tracking_token

```python
# bot_manager.py:_handle_start_command()
def _handle_start_command(self, bot, message, update):
    """
    Processa comando /start e inicia funil
    """
    telegram_user_id = str(message.from_user.id)
    
    # Extrair tracking_token do start param
    start_param = message.text.split('/start', 1)[-1].strip()
    tracking_token = start_param if start_param else None
    
    # Buscar ou criar BotUser
    bot_user = BotUser.query.filter_by(
        bot_id=bot.id,
        telegram_user_id=telegram_user_id
    ).first()
    
    if not bot_user:
        bot_user = BotUser(
            bot_id=bot.id,
            telegram_user_id=telegram_user_id,
            tracking_session_id=tracking_token,  # ✅ SALVAR TRACKING TOKEN
            # ... outros campos
        )
        db.session.add(bot_user)
    else:
        # Atualizar tracking_token se mudou
        if tracking_token and bot_user.tracking_session_id != tracking_token:
            bot_user.tracking_session_id = tracking_token
            logger.info(f"✅ Tracking token atualizado: {tracking_token[:20]}...")
    
    db.session.commit()
```

**Explicação:**
- Extrai `tracking_token` do parâmetro `/start`
- Salva `tracking_token` em `BotUser.tracking_session_id`
- Permite recuperar dados do Redis posteriormente

#### Passo 2.2: Recuperar Dados do Redis

```python
# bot_manager.py:_handle_start_command() (continuação)
# ✅ RECUPERAR DADOS DO REDIS
from utils.tracking_service import TrackingServiceV4
tracking_service_v4 = TrackingServiceV4()

tracking_data = {}
if bot_user.tracking_session_id:
    tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
    
    if tracking_data:
        # ✅ SALVAR DADOS NO BOTUSER (para uso posterior)
        bot_user.fbclid = tracking_data.get('fbclid')
        bot_user.fbp = tracking_data.get('fbp')
        bot_user.fbc = tracking_data.get('fbc')
        bot_user.utm_source = tracking_data.get('utm_source')
        bot_user.utm_campaign = tracking_data.get('utm_campaign')
        bot_user.campaign_code = tracking_data.get('grim')
        bot_user.ip_address = tracking_data.get('client_ip')
        bot_user.user_agent = tracking_data.get('client_user_agent')
        
        db.session.commit()
        
        logger.info(f"✅ Dados de tracking recuperados do Redis: {len(tracking_data)} campos")
```

**Explicação:**
- Recupera dados do Redis usando `tracking_token`
- Salva dados em `BotUser` para uso posterior (Purchase)
- Mantém dados no Redis para matching com Purchase

#### Passo 2.3: Envio ViewContent (Assíncrono)

```python
# bot_manager.py:_handle_start_command() (continuação)
# ✅ ENVIAR VIEWCONTENT (ASSÍNCRONO)
send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id=pool_id)
```

**Função:** `send_meta_pixel_viewcontent_event()`  
**Arquivo:** `bot_manager.py`  
**Localização:** Linha ~78

```python
# bot_manager.py:78-320
def send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id=None):
    """
    Envia evento ViewContent para Meta Pixel quando usuário inicia conversa
    """
    # ✅ VERIFICAÇÃO 1: Buscar pool associado ao bot
    pool_bot = PoolBot.query.filter_by(bot_id=bot.id, pool_id=pool_id).first()
    if not pool_bot:
        return  # Pool não encontrado
    
    pool = pool_bot.pool
    
    # ✅ VERIFICAÇÃO 2: Pool tem Meta Pixel configurado?
    if not pool.meta_tracking_enabled or not pool.meta_pixel_id or not pool.meta_access_token:
        return
    
    # ✅ VERIFICAÇÃO 3: Evento ViewContent está habilitado?
    if not pool.meta_events_viewcontent:
        return
    
    # ✅ VERIFICAÇÃO 4: Já enviou ViewContent? (ANTI-DUPLICAÇÃO)
    if bot_user.meta_viewcontent_sent:
        logger.info(f"⚠️ ViewContent já enviado - ignorando")
        return
    
    # Gerar event_id único
    event_id = MetaPixelAPI._generate_event_id(
        event_type='viewcontent',
        unique_id=f"{pool.id}_{bot_user.telegram_user_id}"
    )
    
    # ✅ CRÍTICO: Recuperar dados do Redis (MESMO DO PAGEVIEW!)
    tracking_data = {}
    if bot_user.tracking_session_id:
        tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
    
    # Normalizar external_id (MESMO ALGORITMO DO PAGEVIEW!)
    external_id_raw = tracking_data.get('fbclid') or getattr(bot_user, 'fbclid', None)
    external_id_value = normalize_external_id(external_id_raw) if external_id_raw else None
    
    # Recuperar fbp/fbc (prioridade: tracking_data > BotUser)
    fbp_value = tracking_data.get('fbp') or getattr(bot_user, 'fbp', None)
    fbc_value = tracking_data.get('fbc') or getattr(bot_user, 'fbc', None)
    fbc_origin = tracking_data.get('fbc_origin')
    
    # ✅ CRÍTICO: Validar fbc_origin (ignorar fbc sintético)
    if fbc_value and fbc_origin == 'synthetic':
        fbc_value = None
    
    # ✅ CRÍTICO: Construir user_data (MESMO FORMATO DO PAGEVIEW!)
    user_data = MetaPixelAPI._build_user_data(
        customer_user_id=str(bot_user.telegram_user_id),  # ✅ Telegram ID
        external_id=external_id_value,  # ✅ fbclid normalizado
        email=None,
        phone=None,
        client_ip=tracking_data.get('client_ip') or getattr(bot_user, 'ip_address', None),
        client_user_agent=tracking_data.get('client_user_agent') or getattr(bot_user, 'user_agent', None),
        fbp=fbp_value,  # ✅ FBP do PageView
        fbc=fbc_value  # ✅ FBC do PageView (apenas se real/cookie)
    )
    
    # Construir custom_data
    custom_data = {
        'content_type': 'product',
        'content_ids': [str(pool.id)],
        'content_name': pool.name,
        'bot_id': bot.id,
        'bot_username': bot.username,
        'utm_source': tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None),
        'utm_campaign': tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None),
        'campaign_code': tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None)
    }
    
    # Construir event_data
    event_data = {
        'event_name': 'ViewContent',
        'event_time': int(time.time()),
        'event_id': event_id,  # ✅ Único para deduplicação
        'action_source': 'website',
        'event_source_url': tracking_data.get('event_source_url') or f'https://app.grimbots.online/go/{pool.slug}',
        'user_data': user_data,  # ✅ MESMOS DADOS DO PAGEVIEW!
        'custom_data': custom_data
    }
    
    # ✅ ENFILEIRAR (ASSÍNCRONO)
    task = send_meta_event.apply_async(
        args=[pool.meta_pixel_id, access_token, event_data, pool.meta_test_event_code],
        priority=5  # Média prioridade
    )
    
    # Marcar como enviado (ANTI-DUPLICAÇÃO)
    bot_user.meta_viewcontent_sent = True
    bot_user.meta_viewcontent_sent_at = get_brazil_time()
    db.session.commit()
    
    logger.info(f"📤 ViewContent enfileirado: Event ID: {event_id} | Task: {task.id}")
```

**Explicação:**
- Recupera dados do Redis usando `tracking_session_id`
- Normaliza `external_id` (MESMO algoritmo do PageView!)
- Constrói `user_data` com MESMOS dados do PageView (garante matching!)
- Enfileira evento via Celery (assíncrono)
- Marca flag `meta_viewcontent_sent` para evitar duplicação

---

### FASE 3: PÁGINA DE ENTREGA (Purchase)

**Arquivo:** `app.py`  
**Função:** `delivery_page(payment_id, token)`  
**Localização:** Linha ~7394

#### Passo 3.1: Recuperar Dados do Redis

```python
# app.py:7394-7462
@app.route('/delivery/<int:payment_id>/<token>')
def delivery_page(payment_id, token):
    """
    Página de entrega - Renderiza HTML com Meta Pixel Purchase
    """
    # Validar token
    payment = Payment.query.filter_by(id=payment_id, delivery_token=token).first_or_404()
    
    # ✅ CRÍTICO: Recuperar tracking_data do Redis
    from utils.tracking_service import TrackingServiceV4
    tracking_service_v4 = TrackingServiceV4()
    
    tracking_data = {}
    
    # ✅ PRIORIDADE 1: tracking_session_id do BotUser (MAIS CONFIÁVEL)
    bot_user = BotUser.query.filter_by(
        bot_id=payment.bot_id,
        telegram_user_id=payment.customer_user_id.replace('user_', '')
    ).first()
    
    if bot_user and bot_user.tracking_session_id:
        tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
    
    # ✅ PRIORIDADE 2: payment.tracking_token (fallback)
    if not tracking_data and payment.tracking_token:
        tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
    
    # ✅ PRIORIDADE 3: tracking:payment:{payment_id} (fallback)
    if not tracking_data:
        raw = tracking_service_v4.redis.get(f"tracking:payment:{payment_id}")
        if raw:
            tracking_data = json.loads(raw)
    
    # ✅ PRIORIDADE 4: fbclid do Payment (fallback final)
    if not tracking_data and payment.fbclid:
        token = tracking_service_v4.redis.get(f"tracking:fbclid:{payment.fbclid}")
        if token:
            tracking_data = tracking_service_v4.recover_tracking_data(token) or {}
```

**Explicação:**
- Recupera dados do Redis com **4 estratégias** (prioridade decrescente)
- Garante que dados sejam recuperados mesmo se uma estratégia falhar

#### Passo 3.2: Construir Configuração do Pixel

```python
# app.py:7430-7462
# ✅ Construir configuração do pixel para renderizar no HTML
pixel_config = {
    'pixel_id': pool.meta_pixel_id if has_meta_pixel else None,
    'event_id': f"purchase_{payment.payment_id}_{int(time.time())}",
    'external_id': tracking_data.get('fbclid'),
    'fbp': tracking_data.get('fbp') or getattr(payment, 'fbp', None),
    'fbc': tracking_data.get('fbc') or getattr(payment, 'fbc', None),
    'value': float(payment.amount),
    'currency': 'BRL',
    'content_id': str(payment.id),
    'content_name': payment.product_name,
    'utm_source': tracking_data.get('utm_source'),
    'utm_campaign': tracking_data.get('utm_campaign'),
    'campaign_code': tracking_data.get('campaign_code') or tracking_data.get('grim')
}

logger.info(f"✅ Delivery - Renderizando página para payment {payment.id} | " +
           f"Pixel: {'✅' if has_meta_pixel else '❌'} | " +
           f"event_id: {pixel_config['event_id'][:30]}...")
```

**Explicação:**
- Constrói `pixel_config` com todos os dados necessários para Purchase
- Inclui `external_id`, `fbp`, `fbc`, `utm_*`, etc.

#### Passo 3.3: Renderizar HTML com Meta Pixel JS

```python
# app.py:7462-7480
return render_template('delivery.html',
    payment=payment,
    bot=bot,
    pixel_config=pixel_config,
    has_meta_pixel=has_meta_pixel
)
```

**Template:** `templates/delivery.html`

```html
<!-- templates/delivery.html -->
{% if has_meta_pixel and pixel_config.pixel_id %}
<!-- Meta Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');

fbq('init', '{{ pixel_config.pixel_id }}');
fbq('track', 'PageView');

// ✅ PURCHASE EVENT (client-side)
fbq('track', 'Purchase', {
    'value': {{ pixel_config.value }},
    'currency': '{{ pixel_config.currency }}',
    'content_ids': ['{{ pixel_config.content_id }}'],
    'content_name': '{{ pixel_config.content_name }}',
    'external_id': '{{ pixel_config.external_id }}',  // ✅ CRÍTICO para matching
    'fbp': '{{ pixel_config.fbp }}',  // ✅ CRÍTICO para matching
    'fbc': '{{ pixel_config.fbc }}',  // ✅ CRÍTICO para matching
    'eventID': '{{ pixel_config.event_id }}'  // ✅ CRÍTICO para deduplicação
});
</script>

<!-- Conversions API (server-side) - ALTERNATIVA -->
<!-- Se configurado, também envia via server-side para garantir -->
{% endif %}
```

**Explicação:**
- Renderiza HTML com Meta Pixel JS (client-side)
- Dispara Purchase com **mesmos dados** do PageView (matching perfeito!)
- `eventID` garante deduplicação (se client-side e server-side enviarem)

---

## 🔧 COMPONENTES PRINCIPAIS

### 1. MetaPixelAPI (`utils/meta_pixel.py`)

**Classe principal:** `MetaPixelAPI`

#### Métodos Principais:

##### `_hash_data(data: str) -> str`
```python
# utils/meta_pixel.py:80-84
@staticmethod
def _hash_data(data: str) -> str:
    """Criptografa dados sensíveis com SHA256"""
    if not data:
        return ""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
```
**Explicação:**
- Hash SHA256 de dados sensíveis (email, telefone, external_id)
- Meta exige dados criptografados para privacidade

##### `_build_user_data(...) -> Dict`
```python
# utils/meta_pixel.py:100-193
@staticmethod
def _build_user_data(
    customer_user_id: str = None,
    email: str = None,
    phone: str = None,
    client_ip: str = None,
    client_user_agent: str = None,
    fbp: str = None,
    fbc: str = None,
    external_id: str = None
) -> Dict:
    """
    Constrói user_data para o evento
    
    ✅ CRÍTICO: external_id IMUTÁVEL e CONSISTENTE
    - Se external_id já for um array (do TrackingService), usar diretamente
    - Caso contrário, construir array com ordem correta:
      PRIORIDADE 1: external_id (fbclid) - SEMPRE PRIMEIRO
      PRIORIDADE 2: customer_user_id (telegram_user_id) - adicionar depois
    """
    user_data = {}
    
    external_ids = []
    
    # ✅ Se external_id já é um array (do TrackingService), usar diretamente
    if isinstance(external_id, list):
        external_ids = external_id
    else:
        # ✅ PRIORIDADE 1: external_id (fbclid) - SEMPRE PRIMEIRO
        if external_id and isinstance(external_id, str) and external_id.strip():
            external_ids.append(MetaPixelAPI._hash_data(external_id.strip()))
        
        # ✅ PRIORIDADE 2: customer_user_id (telegram_user_id) - adicionar depois
        if customer_user_id and isinstance(customer_user_id, str) and customer_user_id.strip():
            customer_id_clean = customer_user_id.strip()
            external_id_clean = external_id.strip() if external_id and isinstance(external_id, str) else None
            if customer_id_clean != external_id_clean:
                customer_id_hash = MetaPixelAPI._hash_data(customer_id_clean)
                if customer_id_hash not in external_ids:
                    external_ids.append(customer_id_hash)
    
    if external_ids:
        user_data['external_id'] = external_ids
    
    # ✅ Email (hashed) - validar antes de processar
    if email and isinstance(email, str) and email.strip():
        email_clean = email.lower().strip()
        if '@' in email_clean and len(email_clean) >= 3:
            user_data['em'] = [MetaPixelAPI._hash_data(email_clean)]
    
    # ✅ Telefone (hashed) - limpar e validar antes de processar
    if phone and isinstance(phone, str):
        phone_clean = ''.join(filter(str.isdigit, phone))
        if phone_clean and len(phone_clean) >= 10:
            user_data['ph'] = [MetaPixelAPI._hash_data(phone_clean)]
    
    # ✅ Dados técnicos (IP e User Agent) - validar formato básico
    if client_ip and isinstance(client_ip, str) and client_ip.strip():
        if len(client_ip.strip()) >= 7:
            user_data['client_ip_address'] = client_ip.strip()
    
    if client_user_agent and isinstance(client_user_agent, str) and client_user_agent.strip():
        if len(client_user_agent.strip()) >= 10:
            user_data['client_user_agent'] = client_user_agent.strip()
    
    # ✅ Cookies do Meta (para matching) - validar formato básico
    if fbp and isinstance(fbp, str) and fbp.strip():
        if len(fbp.strip()) >= 10:
            user_data['fbp'] = fbp.strip()
    
    if fbc and isinstance(fbc, str) and fbc.strip():
        if len(fbc.strip()) >= 10:
            user_data['fbc'] = fbc.strip()
    
    return user_data
```
**Explicação:**
- Constrói `user_data` com **máximo de atributos** (Match Quality 8-10/10)
- **Ordem dos `external_id`:** fbclid primeiro, telegram_user_id depois
- Valida todos os campos antes de adicionar
- Hash de dados sensíveis (email, telefone, external_id)

##### `send_pageview_event(...) -> Dict`
```python
# utils/meta_pixel.py:259-333
@staticmethod
def send_pageview_event(
    pixel_id: str,
    access_token: str,
    event_id: str,
    customer_user_id: str = None,
    external_id: str = None,
    client_ip: str = None,
    client_user_agent: str = None,
    fbp: str = None,
    fbc: str = None,
    utm_source: str = None,
    utm_campaign: str = None,
    campaign_code: str = None,
    event_source_url: str = None
) -> Dict:
    """
    Envia evento PageView para Meta
    """
    url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
    
    # User Data
    user_data = MetaPixelAPI._build_user_data(...)
    
    # Custom Data
    custom_data = {
        'utm_source': utm_source,
        'utm_campaign': utm_campaign,
        'campaign_code': campaign_code
    }
    
    # Payload
    payload = {
        'data': [{
            'event_name': 'PageView',
            'event_time': int(time.time()),
            'event_id': event_id,  # ✅ Único para deduplicação
            'action_source': 'website',
            'event_source_url': event_source_url,
            'user_data': user_data,
            'custom_data': custom_data
        }],
        'access_token': access_token
    }
    
    # Enviar com retry
    success, response_data, error = MetaPixelAPI._send_event_with_retry(url, payload)
    
    return {
        'success': success,
        'response': response_data,
        'error': error,
        'event_type': 'PageView',
        'event_id': event_id
    }
```
**Explicação:**
- Envia evento PageView via Conversions API
- Usa `_send_event_with_retry()` para retry automático
- Retorna resultado (success, response, error)

##### `_send_event_with_retry(...) -> Tuple[bool, Dict, str]`
```python
# utils/meta_pixel.py:196-256
@staticmethod
def _send_event_with_retry(
    url: str,
    payload: Dict,
    max_retries: int = MAX_RETRIES
) -> Tuple[bool, Dict, str]:
    """
    Envia evento com retry automático
    
    Backoff exponencial: [1s, 2s, 4s]
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=15,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GrimPay-MetaPixel/1.0'
                }
            )
            
            response_data = response.json()
            
            if response.status_code == 200:
                return True, response_data, None
            else:
                error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                last_error = error_msg
                
                # Se é erro de autenticação, não retry
                if response.status_code in [401, 403]:
                    break
                    
        except requests.exceptions.Timeout:
            last_error = f"Timeout na tentativa {attempt + 1}"
        except requests.exceptions.RequestException as e:
            last_error = f"Erro de rede na tentativa {attempt + 1}: {str(e)}"
        except Exception as e:
            last_error = f"Erro inesperado na tentativa {attempt + 1}: {str(e)}"
            break
        
        # Delay antes do próximo retry
        if attempt < max_retries - 1:
            delay = MetaPixelAPI.RETRY_DELAYS[min(attempt, len(MetaPixelAPI.RETRY_DELAYS) - 1)]
            time.sleep(delay)
    
    return False, None, last_error or "Erro desconhecido"
```
**Explicação:**
- Retry automático com backoff exponencial (1s, 2s, 4s)
- Máximo 3 tentativas
- Não retry em erros de autenticação (401, 403)

---

### 2. TrackingServiceV4 (`utils/tracking_service.py`)

**Classe principal:** `TrackingServiceV4`

#### Métodos Principais:

##### `save_tracking_token(tracking_token: str, payload: Dict, ttl: int = None) -> bool`
```python
# utils/tracking_service.py:124-261
def save_tracking_token(self, tracking_token: str, payload: Dict, ttl: Optional[int] = None) -> bool:
    """
    Salva tracking_token no Redis
    
    ✅ CRÍTICO: Preserva pageview_event_id e fbc_origin
    """
    if not tracking_token:
        return False
    
    ttl = ttl or TRACKING_TOKEN_TTL_SECONDS  # 30 dias
    key = self._key(tracking_token)  # tracking:{token}
    legacy = self._legacy_key(tracking_token)  # tracking:token:{token}
    
    try:
        # ✅ MERGE com dados existentes (não sobrescrever!)
        current = self.redis.get(key)
        if current:
            previous = json.loads(current)
            if isinstance(previous, dict):
                # ✅ CRÍTICO: Preservar pageview_event_id
                preserved_pageview_event_id = previous.get('pageview_event_id')
                new_pageview_event_id = payload.get('pageview_event_id')
                if preserved_pageview_event_id and not new_pageview_event_id:
                    payload['pageview_event_id'] = preserved_pageview_event_id
                
                # ✅ CRÍTICO V4.1: Preservar fbc APENAS se fbc_origin = 'cookie'
                preserved_fbc = previous.get('fbc')
                preserved_fbc_origin = previous.get('fbc_origin')
                new_fbc = payload.get('fbc')
                new_fbc_origin = payload.get('fbc_origin')
                
                # ✅ PRIORIDADE 1: Novo payload tem fbc REAL (cookie) → usar
                if new_fbc and new_fbc_origin == 'cookie':
                    # Manter fbc do novo payload
                    pass
                # ✅ PRIORIDADE 2: Novo não tem fbc, mas anterior tem fbc REAL → preservar
                elif preserved_fbc and preserved_fbc_origin == 'cookie' and not new_fbc:
                    payload['fbc'] = preserved_fbc
                    payload['fbc_origin'] = 'cookie'
                # ✅ PRIORIDADE 3: Ignorar fbc sintético
                else:
                    payload['fbc'] = None
                    payload['fbc_origin'] = None
                
                # ✅ MERGE: Não sobrescrever com None
                for key, value in payload.items():
                    if value is not None:
                        previous[key] = value
                payload = previous
        
        # Salvar no Redis
        payload["tracking_token"] = tracking_token
        payload["updated_at"] = datetime.utcnow().isoformat()
        payload.setdefault("created_at", datetime.utcnow().isoformat())
        
        json_payload = json.dumps(payload, ensure_ascii=False)
        self.redis.setex(key, ttl, json_payload)
        self.redis.setex(legacy, ttl, json_payload)
        
        # ✅ ÍNDICES ADICIONAIS
        fbclid = payload.get("fbclid")
        if fbclid:
            self.redis.setex(f"tracking:fbclid:{fbclid}", ttl, tracking_token)
        
        customer_user_id = payload.get("customer_user_id")
        if customer_user_id:
            self.redis.setex(f"tracking:chat:{customer_user_id}", ttl, json_payload)
            self.redis.setex(f"tracking:last_token:user:{customer_user_id}", ttl, tracking_token)
        
        payment_id = payload.get("payment_id")
        if payment_id:
            self.redis.setex(f"tracking:payment:{payment_id}", ttl, json_payload)
        
        return True
    except Exception:
        logger.exception("Falha ao salvar tracking_token no Redis")
        return False
```
**Explicação:**
- Salva dados no Redis com TTL de 30 dias
- **Preserva** `pageview_event_id` e `fbc_origin` (não sobrescreve com None)
- Cria **índices adicionais** para busca rápida:
  - `tracking:fbclid:{fbclid}` → `tracking_token`
  - `tracking:chat:{telegram_user_id}` → payload completo
  - `tracking:payment:{payment_id}` → payload completo

##### `recover_tracking_data(tracking_token: str) -> Dict`
```python
# utils/tracking_service.py:263-285
def recover_tracking_data(self, tracking_token: str) -> Dict:
    """
    Recupera tracking_data do Redis
    """
    if not tracking_token:
        return {}
    
    try:
        key = self._key(tracking_token)  # tracking:{token}
        legacy = self._legacy_key(tracking_token)  # tracking:token:{token}
        
        raw = self.redis.get(key)
        if not raw:
            raw = self.redis.get(legacy)
        
        if raw:
            return json.loads(raw)
        
        return {}
    except Exception:
        logger.exception("Erro ao recuperar tracking_token do Redis")
        return {}
```
**Explicação:**
- Recupera dados do Redis usando `tracking_token`
- Suporta chaves legacy (compatibilidade)

---

### 3. normalize_external_id (`utils/meta_pixel.py`)

**Função:** `normalize_external_id(fbclid: str) -> str`

```python
# utils/meta_pixel.py:31-59
def normalize_external_id(fbclid: str) -> str:
    """
    Normaliza external_id para garantir matching consistente entre PageView, ViewContent e Purchase.
    
    ✅ CRÍTICO: Todos os eventos DEVEM usar o MESMO algoritmo de normalização!
    
    Regras:
    - Se fbclid > 80 chars: retorna hash MD5 (32 chars) - mesmo critério usado em todos os eventos
    - Se fbclid <= 80 chars: retorna fbclid original
    - Se fbclid é None/vazio: retorna None
    """
    if not fbclid or not isinstance(fbclid, str):
        return None
    
    fbclid = fbclid.strip()
    if not fbclid:
        return None
    
    # ✅ CRÍTICO: Mesmo critério usado em todos os eventos (80 chars)
    # Se fbclid > 80 chars, normalizar para hash MD5 (32 chars)
    if len(fbclid) > 80:
        normalized = hashlib.md5(fbclid.encode('utf-8')).hexdigest()
        logger.debug(f"🔑 External ID normalizado (MD5): {normalized} (original len={len(fbclid)})")
        return normalized
    
    # Se <= 80 chars, usar original
    return fbclid
```
**Explicação:**
- Normaliza `fbclid` para garantir matching consistente
- Se `fbclid > 80 chars` → hash MD5 (32 chars)
- Se `fbclid <= 80 chars` → usar original
- **CRÍTICO:** Mesmo algoritmo usado em todos os eventos!

---

## 📊 EVENTOS META PIXEL

### Evento 1: PageView

**Quando:** Usuário acessa redirect (`/go/{slug}`)

**Dados Enviados:**
```json
{
  "event_name": "PageView",
  "event_time": 1729440000,
  "event_id": "pageview_abc123_1729440000",
  "action_source": "website",
  "event_source_url": "https://app.grimbots.online/go/pool1?grim=teste&fbclid=xxx",
  "user_data": {
    "external_id": ["hash_sha256_fbclid", "hash_sha256_telegram_id"],
    "fbp": "fb.1.1729440000000.1234567890",
    "fbc": "fb.1.1729440000000.xxx",
    "client_ip_address": "192.168.1.1",
    "client_user_agent": "Mozilla/5.0..."
  },
  "custom_data": {
    "pool_id": 1,
    "pool_name": "Pool 1",
    "utm_source": "FB",
    "utm_campaign": "Campanha 1",
    "campaign_code": "teste"
  }
}
```

**Match Quality:** 8-10/10 (7 atributos: external_id, fbp, fbc, ip, ua)

---

### Evento 2: ViewContent

**Quando:** Usuário inicia conversa com bot (`/start`)

**Dados Enviados:**
```json
{
  "event_name": "ViewContent",
  "event_time": 1729440100,
  "event_id": "viewcontent_1_123456789_1729440100",
  "action_source": "website",
  "event_source_url": "https://app.grimbots.online/go/pool1",
  "user_data": {
    "external_id": ["hash_sha256_fbclid", "hash_sha256_telegram_id"],
    "fbp": "fb.1.1729440000000.1234567890",
    "fbc": "fb.1.1729440000000.xxx",
    "client_ip_address": "192.168.1.1",
    "client_user_agent": "Mozilla/5.0..."
  },
  "custom_data": {
    "content_type": "product",
    "content_ids": ["1"],
    "content_name": "Pool 1",
    "bot_id": 1,
    "bot_username": "bot1",
    "utm_source": "FB",
    "utm_campaign": "Campanha 1",
    "campaign_code": "teste"
  }
}
```

**Match Quality:** 8-10/10 (MESMOS dados do PageView!)

---

### Evento 3: Purchase

**Quando:** Usuário acessa página de entrega (após pagamento)

**Dados Enviados:**
```json
{
  "event_name": "Purchase",
  "event_time": 1729440200,
  "event_id": "purchase_12345_1729440200",
  "action_source": "website",
  "user_data": {
    "external_id": ["hash_sha256_fbclid", "hash_sha256_telegram_id"],
    "fbp": "fb.1.1729440000000.1234567890",
    "fbc": "fb.1.1729440000000.xxx",
    "client_ip_address": "192.168.1.1",
    "client_user_agent": "Mozilla/5.0...",
    "em": ["hash_sha256_email"],  // Se disponível
    "ph": ["hash_sha256_phone"]   // Se disponível
  },
  "custom_data": {
    "value": 97.00,
    "currency": "BRL",
    "content_type": "product",
    "content_ids": ["12345"],
    "content_name": "Produto 1",
    "num_items": 1,
    "content_category": "initial",  // initial, downsell, upsell, remarketing
    "utm_source": "FB",
    "utm_campaign": "Campanha 1",
    "campaign_code": "teste"
  }
}
```

**Match Quality:** 9-10/10 (7+ atributos: external_id, fbp, fbc, ip, ua, email, phone)

---

## 🔗 MATCHING E DEDUPLICAÇÃO

### Matching (PageView → ViewContent → Purchase)

**Critérios de Matching:**
1. **`external_id`** (fbclid hashado) - **OBRIGATÓRIO**
2. **`fbp`** (Facebook Pixel cookie) - Alta prioridade
3. **`fbc`** (Facebook Click ID cookie) - Alta prioridade
4. **`client_ip_address`** - Média prioridade
5. **`client_user_agent`** - Baixa prioridade
6. **`em`** (email hashado) - Alta prioridade (se disponível)
7. **`ph`** (telefone hashado) - Alta prioridade (se disponível)

**Algoritmo de Matching:**
- Meta usa **Event Match Quality** (0-10)
- **7+ atributos** = Match Quality 8-10/10 (matching perfeito!)
- **5-6 atributos** = Match Quality 6-7/10 (matching bom)
- **<5 atributos** = Match Quality <6/10 (matching fraco)

### Deduplicação

**Como funciona:**
- Cada evento tem um **`event_id` único**
- Se o mesmo `event_id` for enviado 2x (client-side + server-side), Meta conta como **1 evento**
- Isso evita duplicação mesmo se ambos os métodos enviarem

**Exemplo:**
```python
# Client-side (delivery.html)
fbq('track', 'Purchase', {
    'eventID': 'purchase_12345_1729440200'  # ✅ Mesmo event_id
});

# Server-side (app.py)
event_data = {
    'event_id': 'purchase_12345_1729440200',  # ✅ Mesmo event_id
    'event_name': 'Purchase',
    ...
}
```

**Resultado:** Meta conta como **1 evento** (deduplicação automática)

---

## ⚙️ CONFIGURAÇÃO

### 1. Configurar Meta Pixel no Pool

**Rota:** `POST /api/pools/{pool_id}/meta-pixel`

**Payload:**
```json
{
  "meta_tracking_enabled": true,
  "meta_pixel_id": "123456789012345",
  "meta_access_token": "EAAxxxxxxxxxxxxx",
  "meta_events_pageview": true,
  "meta_events_viewcontent": true,
  "meta_events_purchase": true
}
```

**Validações:**
- `meta_pixel_id`: 15-16 dígitos numéricos
- `meta_access_token`: Mínimo 50 caracteres
- Teste de conexão via `MetaPixelAPI.test_connection()`

### 2. Configurar URLs no Facebook Ads

**URL de Destino:**
```
https://app.grimbots.online/go/pool1?grim=testecamu01&utm_source=FB&utm_campaign={{campaign.name}}|{{campaign.id}}&utm_medium={{adset.name}}|{{adset.id}}&utm_content={{ad.name}}|{{ad.id}}&utm_term={{placement}}
```

**Parâmetros Obrigatórios:**
- `grim`: Código da campanha (usado como fallback se `fbclid` ausente)
- `fbclid`: Gerado automaticamente pelo Facebook (obrigatório para tracking)

**Parâmetros UTM (opcionais):**
- `utm_source`, `utm_campaign`, `utm_medium`, `utm_content`, `utm_term`

---

## 🐛 TROUBLESHOOTING

### Problema 1: Eventos não aparecem no Meta Events Manager

**Causas Possíveis:**
1. ✅ Verificar se `meta_tracking_enabled = true`
2. ✅ Verificar se `meta_pixel_id` e `meta_access_token` estão configurados
3. ✅ Verificar se evento está habilitado (`meta_events_pageview`, etc)
4. ✅ Verificar logs do Celery (eventos podem estar falhando)
5. ✅ Verificar se `test_code` está configurado (eventos de teste)

**Solução:**
```python
# Verificar logs
tail -f logs/gunicorn.log | grep "META"

# Verificar Celery
celery -A celery_app inspect active
```

---

### Problema 2: Match Quality baixo (<6/10)

**Causas Possíveis:**
1. ✅ `external_id` ausente (fbclid não capturado)
2. ✅ `fbp` ausente (cookie não gerado/injetado)
3. ✅ `fbc` ausente (cookie não gerado/injetado)
4. ✅ `client_ip_address` ausente (Cloudflare não configurado)
5. ✅ Dados diferentes entre eventos (normalização inconsistente)

**Solução:**
- Verificar se `fbclid` está sendo capturado da URL
- Verificar se cookies `_fbp` e `_fbc` estão sendo injetados
- Verificar se `normalize_external_id()` está sendo usado em todos os eventos
- Verificar logs: `[META PAGEVIEW]`, `[META VIEWCONTENT]`, `[META PURCHASE]`

---

### Problema 3: Purchase não atribui à campanha

**Causas Possíveis:**
1. ✅ `external_id` diferente entre PageView e Purchase
2. ✅ `event_id` diferente (deduplicação não funciona)
3. ✅ `fbp`/`fbc` ausentes no Purchase
4. ✅ Purchase enviado antes do PageView (atraso no tracking)

**Solução:**
- Verificar se `external_id` está normalizado (mesmo algoritmo em todos os eventos)
- Verificar se `tracking_token` está sendo salvo no `BotUser.tracking_session_id`
- Verificar se dados do Redis estão sendo recuperados corretamente
- Verificar logs: `[META PURCHASE] tracking_data recuperado: ...`

---

### Problema 4: Duplicação de eventos

**Causas Possíveis:**
1. ✅ Client-side e server-side enviando sem `eventID`
2. ✅ `event_id` diferente entre tentativas
3. ✅ Reenvio manual sem resetar flags

**Solução:**
- Garantir que `event_id` é **único e consistente**
- Usar `eventID` no client-side para deduplicação
- Não reenviar eventos já enviados (verificar flags: `meta_purchase_sent`, etc)

---

## 📝 RESUMO

### Fluxo Completo:
1. **Redirect** (`/go/{slug}`) → Gera `tracking_token`, salva no Redis, envia **PageView**
2. **Telegram** (`/start`) → Recupera dados do Redis, salva em `BotUser`, envia **ViewContent**
3. **Entrega** (`/delivery/{id}/{token}`) → Recupera dados do Redis, renderiza HTML com **Purchase**

### Dados Críticos para Matching:
- ✅ `external_id` (fbclid normalizado) - **OBRIGATÓRIO**
- ✅ `fbp` (cookie do browser) - **ALTA PRIORIDADE**
- ✅ `fbc` (cookie do browser) - **ALTA PRIORIDADE**
- ✅ `client_ip_address` - Média prioridade
- ✅ `client_user_agent` - Baixa prioridade

### Boas Práticas:
1. ✅ Sempre usar `normalize_external_id()` em todos os eventos
2. ✅ Sempre recuperar dados do Redis antes de enviar eventos
3. ✅ Sempre usar `MetaPixelAPI._build_user_data()` para construir `user_data`
4. ✅ Sempre verificar `fbc_origin` antes de usar `fbc` (ignorar sintético)
5. ✅ Sempre usar `event_id` único para deduplicação

---

## 📚 REFERÊNCIAS

- [Meta Conversions API Documentation](https://developers.facebook.com/docs/marketing-api/conversions-api)
- [Event Match Quality](https://www.facebook.com/business/help/765081237991954)
- [External ID Best Practices](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/external-id)

---

**Documentação criada em:** 2025-01-19  
**Versão:** 1.0  
**Autor:** Sistema de Tracking Meta Pixel - GrimPay

