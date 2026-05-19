# Auditoria UTMify / Tracking

## FASE 1 — Redirecionador (`/go/<slug>`)

### Fluxo completo
- Rota: `public_redirect` @app.py#6488-7044.
- Captura de parâmetros:
  - `fbclid = request.args.get('fbclid', '')` @app.py#6618-6620
  - UTMs (se não crawler): `utm_source`, `utm_campaign`, `utm_medium`, `utm_content`, `utm_term`, `utm_id` @app.py#6685-6693
  - `grim = request.args.get('grim', '')` @app.py#6657-6658
- Controle de crawler: `is_crawler(user_agent)` -> se true, não salva tracking nem UTMs @app.py#6653-6656.
- Cookies Meta (se pixel habilitado): `_fbp`, `_fbc` dos cookies/params @app.py#6674-6680.
- FBCLID: salvo integralmente (sem truncar) + click_ts em Redis @app.py#6695-6717.
- UTM/campaign_code: se fbclid presente, `campaign_code = fbclid`; senão, usa `grim` @app.py#6712-6721.
- **tracking_payload** (vai para Redis via `TrackingServiceV4.save_tracking_token`):
  - Campos: `tracking_token`, `fbclid`, `fbp`, `fbc`, `fbc_origin`, `pageview_event_id`, `pageview_ts`, `client_ip`, `client_user_agent`, `grim`, `event_source_url`, `first_page`, `pageview_sent`, `pixel_id`, e todos os UTMs com valor (`utm_source`, `utm_campaign`, `utm_medium`, `utm_content`, `utm_term`, `utm_id`, `campaign_code`) @app.py#6723-6740.
- Upsert em `meta_tracking_sessions`: salva `fbclid`, `fbc`, `fbp`, `root_event_id`, `pageview_sent_at` @app.py#6742-6768.
- PageView Meta Pixel: `send_meta_pixel_pageview_event`, merge de `pageview_context` com `tracking_payload`, salva no Redis (não sobrescreve IP/UA) @app.py#6776-6869.
- Renderização/redirect:
  - HTML bridge (`telegram_redirect.html`) com Pixel/Utmify se configurados, passando UTMs sanitizadas @app.py#6884-6990.
  - Fallback redirect direto com cookies `_fbp/_fbc` @app.py#6995-7044.

### Frontend (telegram_redirect.html)
- Local: `templates/telegram_redirect.html`.
- Meta Parameter Builder (clientParamBuilder) carrega antes do Pixel para capturar fbc/fbp/IP e envia via Beacon/Fetch para `/api/tracking/cookies` com `tracking_token` @telegram_redirect.html#8-78.
- Meta Pixel: init + PageView; espera ~800ms/dwell mínimo 1.5s antes do redirect, garantindo cookies @telegram_redirect.html#84-105, #248-404.
- Utmify:
  - Script de UTMs (`utms/latest.js`) com `data-utmify-prevent-*`, onload chama `loadUtmifyPixel` @telegram_redirect.html#102-130.
  - Pixel Utmify (`pixel.js`) carrega após UTMs; tracking_token, utm_source/campaign/medium/content/term/grim são passados no template.
- Cookies: envia `_fbp/_fbc` (e `_fbi` para IP) para backend via Beacon/Fetch @telegram_redirect.html#258-328.
- Redirect para Telegram sempre com `tracking_token` no start param; respeita carregamento Utmify/PB e dwell @telegram_redirect.html#236-413.
- Fallback noscript: meta refresh para `t.me/<bot_username>?start=<tracking_token>` @telegram_redirect.html#417-425.

### Observação
- Não há whitelist de parâmetros; usa `request.args` diretamente. Todas UTMs padrão + `utm_id` são capturadas e salvas.

## FASE 2 — Persistência (models.py / bot_manager.py)

### Bot (models.py)
- Classe `Bot` @models.py#209-283.
- **Não existe** campo `utmify_token` ou config JSON para UTMify. Campos Meta em Bot estão depreciados (moveram para RedirectPool).

### BotUser (models.py)
- UTMs: `utm_source`, `utm_campaign`, `utm_content`, `utm_medium`, `utm_term` (String 255) @models.py#1145-1150.
- Tracking: `fbclid`, `campaign_code`, `external_id`, `last_click_context_url`, `last_fbclid`, `last_fbp`, `last_fbc`, `fbp`, `fbc`, `ip_address`, `user_agent`, `tracking_session_id`, `click_timestamp` @models.py#1151-1169.

### Payment (models.py)
- UTMs: `utm_source`, `utm_campaign`, `utm_content`, `utm_medium`, `utm_term` (String 255) @models.py#1062-1069.
- Tracking: `fbclid`, `fbc`, `fbp`, `campaign_code`, `click_context_url`, `tracking_token`, `pageview_event_id` @models.py#1070-1079.

### Hidratação no /start (bot_manager.py)
- Em `_handle_start_command`, ao enriquecer `bot_user` com `tracking_data` V4: @bot_manager.py#4267-4276
  - Atribui: `utm_source`, `utm_campaign`, `utm_content`, `utm_medium` (e tracking cookies/IP/UA).
  - **Lacuna:** `utm_term` não é atribuído ao `bot_user`.

## FASE 3 — Gatilho de venda (`_generate_pix_payment`)

### Localização e dados disponíveis
- `_generate_pix_payment` @bot_manager.py#7448-8530.
- `bot_user` é buscado por `(bot_id, telegram_user_id=customer_user_id)` @bot_manager.py#7891-7934.
- Extrai de `bot_user`: `fbclid`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` @bot_manager.py#7911-7917.
- `Payment` recebe UTMs (prioridade tracking_data_v4 > bot_user): `utm_source`, `utm_campaign`, `utm_content`, `utm_medium` @bot_manager.py#8449-8455.
  - **Lacuna:** `utm_term` não é passado ao `Payment`.
  - **Lacuna criada pelo usuário:** `bot_user_id` e `user_agent` foram removidos da criação do Payment (pagamentos voltam a ficar órfãos e sem user_agent).

### Bibliotecas HTTP
- No topo de `bot_manager.py` não há imports de `requests`/`httpx`/`aiohttp`. Integrações externas usam `GatewayFactory`, `TrackingServiceV4` (Redis) e tasks Celery (`send_meta_event`).

## Resumo de Lacunas / Ajustes Necessários
1) UTMs ignoradas:
   - `utm_term` não é aplicada no `bot_user` (/_handle_start_command) nem no `Payment` (_generate_pix_payment).
2) Campo UTMify:
   - Precisa de migração para adicionar `utmify_token` (ou similar) em `Bot` (ou `RedirectPool`, se preferir nível de pool).
3) Vínculo Payment ↔ BotUser e tracking:
   - `bot_user_id` e `user_agent` foram removidos do `Payment` pelo usuário; restaurar para evitar órfãos e perda de user_agent.

## Pontos sugeridos para integrar UTMify
- post_click_to_utmify(): em `public_redirect` após montar `tracking_payload` e antes/depois do `save_tracking_token` (região @app.py#6723-6869). Dados disponíveis: UTMs, fbclid/fbc/fbp, tracking_token, ip, user_agent.
- post_sale_to_utmify(): em `_generate_pix_payment` logo após criar o `Payment` (antes do commit) @bot_manager.py#8449-8529. Dados disponíveis: payment_id, amount, status, bot_user (UTMs, fbclid), tracking_token, gateway ids.

## Notas finais
- Todas UTMs padrão são capturadas no redirect e salvas em Redis. Falta propagar `utm_term` para BotUser/Payment.
- Sem campo `utmify_token`; requer migração.
- Restaurar `bot_user_id` e `user_agent` no Payment para evitar órfãos e manter matching.

# 🧬 Prompt Mestre: Auditoria para Implementação da UTMify Server-Side (Feature Adicional)

## CONTEXTO
- SaaS de redirecionamento com Cloaker e Bots Telegram.
- Nova feature: enviar eventos para UTMify via API server-side, **sem alterar/remover** Meta Pixel/Cloaker existentes (integração aditiva).

## FASE 1: Redirecionador / Cloaker (app.py `/go/<slug>`)
### Captura de Dados (request.args)
- Capturados: `fbclid`, `utm_source`, `utm_campaign`, `utm_medium`, `utm_content`, `utm_term`, `utm_id`, `grim`, `_fbp_cookie`, `_fbc_cookie` (cookies params), `_fbp`/`_fbc` via cookies, `event_source_url`, `first_page`, `pageview_event_id`, `pageview_ts`, `client_ip`, `client_user_agent`. @app.py#6458-7044
- Lacunas: `src`, `sck` **não** são capturados/salvos; `utm_term` é capturado e salvo no Redis.

### Tracking Payload pronto (Momento do Clique)
- `tracking_payload` montado com IP, UA, UTMs, fbclid/fbp/fbc, event_id, grim, etc. @app.py#6723-6740
- Merge com `pageview_context` após PageView Meta; salvo no Redis via `TrackingServiceV4.save_tracking_token` @app.py#6776-6869.

### Cloaker
- `is_crawler` impede salvar tracking (não salva UTMs/payload para crawlers). Para UTMify server-side, se quiser registrar mesmo bloqueados, precisaria bypassar bloqueio para a chamada da API; hoje não envia nada se crawler.

### Ponto de Injeção 1 (send_click)
- Após montar `tracking_payload` e antes/depois do `save_tracking_token`, região @app.py#6723-6869. Ideal: disparar de forma assíncrona (Celery/task) para não atrasar o redirect.

## FASE 2: Ponte Redis -> Bot (/start em `_handle_start_command`)
### Integridade de Dados
- Ao ler tracking_data V4: atribui `utm_source`, `utm_campaign`, `utm_content`, `utm_medium`, cookies e IP/UA @bot_manager.py#4267-4276.
- Lacuna: `utm_term` **não** é atribuído ao BotUser (perdido nesta etapa).

## FASE 3: Conversão / Pagamento (`_generate_pix_payment`)
### Dados disponíveis
- `bot_user` carregado por (bot_id, telegram_user_id); extrai `fbclid`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` @bot_manager.py#7891-7917.
- Payment recebe UTMs (tracking_data_v4 > bot_user): `utm_source`, `utm_campaign`, `utm_content`, `utm_medium` @bot_manager.py#8449-8455.
- Lacuna: `utm_term` não passa para Payment. `bot_user_id` e `user_agent` foram removidos pelo usuário (pagamentos ficam órfãos / sem UA).

### Tracking existente
- Lógica de Meta (PageView/Purchase) já existe; eventos para Meta são enfileirados (Celery) via `send_meta_event`.

### Ponto de Injeção 2 (send_purchase)
- Após `db.session.commit()` do Payment, região @bot_manager.py#8515-8529, disparar UtmifyService.send_purchase() de forma assíncrona.

## FASE 4: Configuração / Banco (models.py)
- Bot: não há coluna para `utmify_token` ou config JSON. @models.py#209-283
- RedirectPool: só possui `utmify_pixel_id` (client-side). Nenhum token de API.
- Necessário criar coluna (ex.: `utmify_token` ou config JSON) em Bot ou RedirectPool para credenciais da API server-side.

## FASE 5: Frontend (templates)
- `telegram_redirect.html` já carrega scripts Utmify (utms/latest.js + pixel.js) e Meta Pixel bridge. @telegram_redirect.html#102-130
- Se adicionar envio server-side, decidir se mantém híbrido ou remove duplicidade; hoje é só client-side Utmify.

## Checklist de Dados
- Capturamos no redirect: fbclid, fbp, fbc, ip, user_agent, utm_source/campaign/medium/content/term/id, grim, pageview_event_id.
- Perdido na ida para BotUser: `utm_term` (não atribuído no /start).
- Perdido na ida para Payment: `utm_term`; `bot_user_id`/`user_agent` removidos.
- `src`/`sck` não são capturados hoje.

## Infraestrutura
- Banco: falta coluna para token da UTMify (API). Criar em Bot ou RedirectPool.

## Mapa de Injeção
- Click: app.py @app.py#6723-6869 (após montar tracking_payload / salvar tracking_token), disparo assíncrono `send_click`.
- Purchase: bot_manager.py @bot_manager.py#8515-8529 (logo após commit), disparo assíncrono `send_purchase`.

## Análise do Cloaker
- `is_crawler` bloqueia tracking (não salva payload/UTMs) -> impediria envio para UTMify em requisições tratadas como crawler. Para registrar mesmo bloqueados, ajustar lógica de envio server-side.

# Debate 1 — Dois agentes (QI 500) sem acesso ao código

**Agente A (Back/Tracking):**
- Preciso saber pontos exatos de entrada/saída do tracking: rota `/go/<slug>`, payload salvo no Redis, redis key/TTL, e como o `tracking_token` chega ao /start. Sem isso, não consigo plugar UTMify.
- Quero listas completas de parâmetros: todos os `request.args`, cookies, headers (UA/IP), e quais são descartados (crawler). Faltas: `src`, `sck` não capturados; `utm_term` não persiste em BotUser/Payment.
- Saber quando o payload está “pronto” (linhas do merge tracking_payload + pageview_context) para injetar `send_click` sem latência.
- Confirmar se Cloaker corta tracking; se sim, decidir se bypass para UTMify server-side.

**Agente B (Front/UX/Entrega):**
- Preciso do template de bridge (`telegram_redirect.html`): quais scripts carregam (Meta PB, Utmify JS, Pixel), ordem, dwell/timeout e fallback. Confirmado: carrega utms/latest.js + pixel.js; dwell 1.5s; Beacon/Fetch para cookies.
- Saber variáveis passadas ao template: `tracking_token`, UTMs sanitizadas, pixel_id, utmify_pixel_id. Ver se haverá duplicidade se API server-side também disparar (precisa decidir híbrido vs. só server-side).
- Página de entrega (`delivery.html`): como Purchase é disparado? Usa `payment.fbclid` para montar fbc; dependências de payment.fbclid/fbc/fbp.

**Convergência:**
- Plug de click: depois do tracking_payload salvo (app.py ~6723-6869), disparo assíncrono UTMify.
- Plug de purchase: depois do commit do Payment (bot_manager.py ~8515-8529), usando payment_id/amount/UTMs/fbclid.
- Dados faltantes: `utm_term` no BotUser/Payment; `bot_user_id`/`user_agent` removidos do Payment.
- Infra: criar `utmify_token` (Bot ou RedirectPool) para API.

# Debate 2 — Revisão Sênior (checagem de lacunas adicionais)

**Agente Sênior:**
- Segurança/LGPD: Tokens de API UTMify precisam ser cifrados (seguir padrão dos gateways: columns criptografadas). Sugestão: armazenar em RedirectPool (pois tracking é por pool) ou em Bot se arquitetura exigir.
- Concorrência/latência: disparos UTMify devem ser assíncronos (Celery) para não afetar redirect. Reutilizar infra de `send_meta_event`.
- Idempotência: Use `tracking_token` + `payment_id` como chaves de dedupe nos envios UTMify.
- Observabilidade: logar payload enviado/erro por task, mas sem tokens; mascarar credenciais.
- Crawler: hoje payload não é salvo se `is_crawler`; se UTMify quiser logar bloqueados, mover envio antes do filtro ou adicionar exceção específica.
- Client-side Utmify já existe no bridge. Decidir: manter híbrido (JS + server) ou trocar para server-only para evitar duplicidade (documentar comportamento esperado).
- Delivery page depende de `payment.fbclid/fbc/fbp`. Se Payment ficar órfão (bot_user_id removido), front perde matching; restaurar vínculo.

**Checklist final pós-debate:**
- Adicionar `utm_term` na hidratação (/start) e no Payment.
- Restaurar `bot_user_id` e `user_agent` no Payment.
- Criar coluna `utmify_token` (cripto) em RedirectPool ou Bot.
- Implementar `send_click` (app.py pós-tracking_payload) e `send_purchase` (bot_manager pós-commit Payment) via Celery.
- Definir estratégia para coexistência com scripts Utmify JS (evitar duplicidade de eventos).
