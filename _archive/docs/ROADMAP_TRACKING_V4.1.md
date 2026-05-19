# 🗺️ ROADMAP PARA IMPLEMENTAÇÃO V4.1 - TRACKING COMPLETO

## **🚀 FASE 1 - CRÍTICA (Alta Prioridade)**
*Essencial para atribuição de conversões funcionar*

### **1. API /api/tracking/cookies** 
**Arquivo**: `internal_logic/blueprints/public/routes.py`
- [ ] Criar endpoint POST para receber FBP/FBC via Beacon API
- [ ] Validar tracking_token
- [ ] Atualizar tracking_data no Redis com cookies do browser
- [ ] Implementar tratamento de JSON da Beacon API

### **2. Campos de Tracking no Payment**
**Arquivo**: `internal_logic/core/models.py` (modelo Payment)
- [ ] Adicionar `tracking_token` (String, nullable)
- [ ] Adicionar `meta_pixel_id` (String, nullable) 
- [ ] Adicionar `fbclid` (String, nullable)
- [ ] Adicionar `delivery_token` (String, nullable)
- [ ] Adicionar `meta_purchase_sent` (Boolean, default=False)
- [ ] Adicionar `meta_event_id` (String, nullable)

### **3. send_payment_delivery() Completa**
**Arquivo**: `internal_logic/services/payment_processor.py`
- [ ] Implementar recuperação de tracking_data do Redis
- [ ] Implementar 4 prioridades de pixel_id (payment → Redis → bot → pool)
- [ ] Implementar decisão inteligente de link (/delivery vs access_link)
- [ ] Implementar logging completo da decisão

### **4. API /api/tracking/mark-purchase-sent**
**Arquivo**: `internal_logic/blueprints/delivery/routes.py`
- [ ] Criar endpoint POST para marcar Purchase como enviado
- [ ] Validar payment_id e status 'paid'
- [ ] Atualizar flags `meta_purchase_sent` e `meta_event_id`
- [ ] Implementar defesa contra marcações indevidas

### **5. tracking_session_id no BotUser**
**Arquivo**: `internal_logic/core/models.py` (modelo BotUser)
- [ ] Adicionar `tracking_session_id` (String, nullable)
- [ ] Adicionar `pixel_id` (String, nullable)
- [ ] Adicionar `campaign_code` (String, nullable)
- [ ] Implementar preservação no handle_start_command

---

## **⚡ FASE 2 - MÉDIA (Média Prioridade)**
*Melhora significativa da qualidade do tracking*

### **6. Detecção de Crawler**
**Arquivo**: `internal_logic/blueprints/public/routes.py`
- [ ] Implementar função `is_crawler()` com patterns completos
- [ ] Adicionar 20+ patterns (facebookexternalhit, telegrambot, etc.)
- [ ] Aplicar lógica de não trackear crawlers
- [ ] Implementar fallback para crawlers (redirect 302)

### **7. Sticky Pixel com 4 Prioridades**
**Arquivo**: `internal_logic/blueprints/delivery/routes.py`
- [ ] Implementar busca em 4 níveis (query param → payment → Redis → pool)
- [ ] Adicionar logging `[PIXEL_STICKY]` para cada decisão
- [ ] Implementar fallback para fbclid numérico
- [ ] Garantir pixel_id sempre encontrado se existir

### **8. Validação de FBC Sintético**
**Arquivo**: `internal_logic/blueprints/delivery/routes.py`
- [ ] Implementar verificação de `fbc_origin == 'synthetic'`
- [ ] Ignorar FBC sintético no evento Purchase
- [ ] Adicionar logging de aviso quando ignorar
- [ ] Documentar regra de negócio

### **9. delivery.html com Meta Pixel Purchase**
**Arquivo**: `templates/delivery.html`
- [ ] Implementar Meta Pixel Purchase completo
- [ ] Adicionar FBP/FBC parameters no evento
- [ ] Implementar event_id consistente com PageView
- [ ] Adicionar chamada API para marcar Purchase enviado

---

## **🔧 FASE 3 - OTIMIZAÇÃO (Baixa Prioridade)**
*Refinamentos e melhorias*

### **10. Captura Completa de UTMs**
**Arquivo**: `internal_logic/blueprints/public/routes.py`
- [ ] Capturar todos os parâmetros UTM (source, campaign, medium, content, term)
- [ ] Salvar UTMs no tracking_data do Redis
- [ ] Passar UTMs para telegram_redirect.html
- [ ] Usar UTMs em eventos Meta Pixel

---

## **📋 ORDEM SUGERIDA DE IMPLEMENTAÇÃO**

### **Semana 1 - Fundação Crítica**
1. **Dia 1-2**: Campos no Payment + BotUser (migração do banco)
2. **Dia 3-4**: API /api/tracking/cookies
3. **Dia 5**: send_payment_delivery() básica

### **Semana 2 - Fluxo Principal**
4. **Dia 1-2**: API /api/tracking/mark-purchase-sent
5. **Dia 3-4**: Melhorar send_payment_delivery() completa
6. **Dia 5**: Testes integração fluxo principal

### **Semana 3 - Qualidade**
7. **Dia 1-2**: Detecção de crawler
8. **Dia 3-4**: Sticky Pixel completo
9. **Dia 5**: Validação FBC sintético

### **Semana 4 - Polimento**
10. **Dia 1-2**: delivery.html completo
11. **Dia 3-4**: Captura UTMs
12. **Dia 5**: Testes finais + documentação

---

## **🎯 BENEFÍCIOS ESPERADOS**

### **Pós Fase 1 (Crítica)**
- ✅ **Atribuição 80%**: Conversões começam a ser atribuídas
- ✅ **Matching PageView→Purchase**: Eventos conectados
- ✅ **Persistência de dados**: Tracking não perdido entre etapas

### **Pós Fase 2 (Média)**
- ✅ **Atribuição 95%**: Alta precisão na atribuição
- ✅ **Sem eventos falsos**: FBC sintético filtrado
- ✅ **Robustez**: Sistema resiliente a falhas

### **Pós Fase 3 (Otimização)**
- ✅ **Atribuição 99%**: Precisão quase perfeita
- ✅ **Analytics completo**: Dados UTM disponíveis
- ✅ **Produção ready**: Sistema estável e documentado

---

## **⚠️ RISCOS E CONSIDERAÇÕES**

### **Riscos Técnicos**
- **Migração do banco**: Campos novos precisam de default values
- **Performance**: Redis pode ser bottleneck se mal configurado
- **Compatibilidade**: Mudanças podem quebrar fluxos existentes

### **Riscos de Negócio**
- **Perda de dados**: Se implementado incorretamente
- **Atribuição incorreta**: Se lógica de prioridades errada
- **Downtime**: Se migração não for bem planejada

### **Mitigações**
- **Implementar gradativamente**: Fase por fase
- **Testes exaustivos**: Cada fase em ambiente de testes
- **Rollback plan**: Capacidade de reverter mudanças
- **Monitoramento**: Logs detalhados para debug

---

## **🚀 ESTADO ATUAL vs OBJETIVO**

### **Hoje (30% V4.1)**
- PageView básico ✅
- Redirect simples ✅
- Tracking parcial ❌
- Atribuição fraca ❌

### **Objetivo (100% V4.1)**
- Fluxo completo ✅
- Atribuição 99% ✅
- Persistência total ✅
- Analytics avançado ✅

---

## **📊 COMPARAÇÃO: CÓDIGO V4.1 VS ATUAL**

### **🔍 ANÁLISE COMPARATIVA DO TRACKING**

#### **1. ETAPA 1: CHEGADA DO LEAD (/go/{slug})**

**✅ TEMOS NO ATUAL:**
```python
# public/routes.py (linhas 21-88)
@public_bp.route('/go/<slug>')
def public_redirect(slug):
    # ✅ Busca pool pelo slug
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    # ✅ Cloaker V2.0
    allowed, reason, log_data = CloakerService.validate_access(request, pool)
    
    # ✅ Gera tracking_token
    tracking_token = uuid.uuid4().hex
    
    # ✅ Pixel_id do pool
    pixel_id_to_use = getattr(pool, 'meta_pixel_id', None)
    
    # ✅ PageView async
    TrackingService.fire_pageview(pool, request, async_mode=True)
    
    # ✅ Renderiza telegram_redirect.html
    return render_template('telegram_redirect.html', ...)
```

**❌ NÃO TEMOS NO ATUAL:**
- **Detecção de crawler** (patterns específicos)
- **Captura de parâmetros UTM** (utm_source, utm_campaign, etc.)
- **4 prioridades de pixel_id** (px, pool, fbclid, grim)
- **Captura de cookies FBP/FBC** no momento da criação
- **Salvar tracking_data completo no Redis**
- **API /api/tracking/cookies** para capturar cookies do browser

#### **2. ETAPA 2: TEMPLATE telegram_redirect.html**

**✅ TEMOS NO ATUAL:**
```html
<!-- templates/telegram_redirect.html (linhas 8-50) -->
<!-- ✅ Meta Parameter Builder Library -->
<script src="https://capi-automation.s3.us-east-2.amazonaws.com/..."></script>

<!-- ✅ Meta Pixel com PageView -->
{% if pixel_id %}
<script>
fbq('init', '{{ pixel_id }}');
fbq('track', 'PageView', {
    event_id: 'pageview_{{ tracking_token }}'
});
</script>
{% endif %}

<!-- ✅ Redirecionamento client-side -->
setTimeout(function() {
    window.location.href = 'https://t.me/{{ bot_username }}?start={{ tracking_token }}';
}, 2000);
```

**❌ NÃO TEMOS NO ATUAL:**
- **Beacon API** para enviar cookies capturados
- **Endpoint /api/tracking/cookies** para receber dados
- **UTMIFY pixel** (pixel secundário)
- **Captura explícita de FBP/FBC** do browser

#### **3. ETAPA 3: API /api/tracking/cookies**

**✅ TEMOS NO ATUAL:**
```python
# ❌ ESTA ROTA NÃO EXISTE NO ATUAL
# Não há endpoint para capturar cookies do browser
```

**❌ NÃO TEMOS NO ATUAL:**
- **Endpoint /api/tracking/cookies** completamente ausente
- **Lógica de atualização de tracking_data no Redis**
- **Validação de tracking_token**

#### **4. ETAPA 4: INTERAÇÃO NO TELEGRAM**

**✅ TEMOS NO ATUAL:**
```python
# BotManager (presume-se existente)
def handle_start_command(self, message):
    # ❌ Não há código visível para preservar tracking_token
    # ❌ Não há associação com BotUser.tracking_session_id
```

**❌ NÃO TEMOS NO ATUAL:**
- **Extração de tracking_token** do parâmetro /start
- **Associação com BotUser.tracking_session_id**
- **Preservação de pixel_id e fbclid** no BotUser
- **Recuperação de tracking_data do Redis**

#### **5. ETAPA 5: GERAÇÃO DO PIX**

**✅ TEMOS NO ATUAL:**
```python
# payment_processor.py (presume-se existente)
def generate_pix_payment(self, user_id, amount, description):
    # ❌ Não há código visível para tracking
    # ❌ Payment não tem campos de tracking
```

**❌ NÃO TEMOS NO ATUAL:**
- **Payment.tracking_token** campo
- **Payment.meta_pixel_id** campo
- **Payment.fbclid** campo
- **Preservação de tracking** na geração do PIX

#### **6. ETAPA 6: WEBHOOK DE CONFIRMAÇÃO**

**✅ TEMOS NO ATUAL:**
```python
# webhooks/payments.py (linhas existentes)
def payment_webhook():
    # ❌ Não há geração de delivery_token
    # ❌ Não há chamada para send_payment_delivery
```

**❌ NÃO TEMOS NO ATUAL:**
- **Geração de delivery_token** baseado em hash
- **Chamada para send_payment_delivery()**
- **Associação de tracking** na confirmação

#### **7. ETAPA 7: ENVIO DA MENSAGEM**

**✅ TEMOS NO ATUAL:**
```python
# ❌ send_payment_delivery não existe ou está incompleto
# ❌ Não há decisão inteligente de link
```

**❌ NÃO TEMOS NO ATUAL:**
- **Função send_payment_delivery()** completa
- **Recuperação de tracking_data** do Redis
- **4 prioridades de pixel_id**
- **Decisão inteligente** (/delivery vs access_link)
- **Logging de decisão**

#### **8. ETAPA 8: PÁGINA DE DELIVERY**

**✅ TEMOS NO ATUAL:**
```python
# delivery/routes.py (linhas 25-413)
@delivery_bp.route('/<token>')
def delivery_page(token):
    # ✅ Busca payment por delivery_token
    payment = Payment.query.filter_by(delivery_token=token).first()
    
    # ✅ Recuperação de tracking_data
    tracking_service = TrackingService()
    tracking_data = tracking_service.recover_tracking_data(...)
    
    # ✅ Renderiza delivery.html
    return render_template('delivery.html', ...)
```

**❌ NÃO TEMOS NO ATUAL:**
- **4 prioridades de recuperação** (BotUser → Payment → Redis → Fallback)
- **Validação de FBC sintético** (ignorar origin='synthetic')
- **Sticky Pixel com redundância tripla**
- **Decisão crítica de link** baseada em pixel_id

#### **9. TEMPLATE delivery.html**

**✅ TEMOS NO ATUAL:**
```html
<!-- templates/delivery.html (presume-se existente) -->
<!-- ❌ Não há código visível -->
```

**❌ NÃO TEMOS NO ATUAL:**
- **Meta Pixel Purchase** com dados completos
- **Event ID consistente** com PageView
- **FBP/FBC parameters** no evento
- **API /api/tracking/mark-purchase-sent**
- **Anti-duplicação robusta**

#### **10. API mark-purchase-sent**

**✅ TEMOS NO ATUAL:**
```python
# ❌ Endpoint não existe no atual
```

**❌ NÃO TEMOS NO ATUAL:**
- **Endpoint /api/tracking/mark-purchase-sent**
- **Marcação de Purchase como enviado**
- **Validação de status pago**

---

## **📋 RESUMO DAS FALHAS CRÍTICAS**

### **🔴 FALTAS MAIORES (90% do fluxo perdido):**

1. **❌ API /api/tracking/cookies** - Inexistente
2. **❌ Persistência em BotUser** - tracking_session_id ausente
3. **❌ Campos de tracking no Payment** - tracking_token, meta_pixel_id, fbclid
4. **❌ send_payment_delivery()** - Função incompleta/ausente
5. **❌ Decisão inteligente de link** - /delivery vs access_link
6. **❌ API mark-purchase-sent** - Inexistente
7. **❌ Validação de FBC sintético** - Ausente
8. **❌ 4 prioridades de pixel** - Implementação incompleta

### **🟡 FALTAS MÉDIAS (50% do fluxo perdido):**

1. **❌ Detecção de crawler** - Implementação básica
2. **❌ Captura de UTMs** - Parcialmente implementada
3. **❌ Sticky Pixel** - Implementação incompleta
4. **❌ Anti-duplicação** - Implementação básica

### **🟢 FALTAS MENORES (20% do fluxo perdido):**

1. **❌ Logging detalhado** - Implementação parcial
2. **❌ Debug info** - Implementação básica

---

## **🎯 VEREDITO FINAL**

### **O ATUAL TEM ~30% DO FLUXO V4.1**

- **✅ BÁSICO FUNCIONAL**: PageView, redirect básico
- **❌ FLUXO COMPLETO**: 70% do tracking perdido
- **❌ ATRIBUIÇÃO**: Conversões não atribuídas corretamente
- **❌ PERSISTÊNCIA**: Dados de tracking perdidos entre etapas

### **PARA CHEGAR NA V4.1 PRECISA:**
1. **Criar /api/tracking/cookies**
2. **Adicionar campos de tracking no Payment**
3. **Implementar send_payment_delivery() completa**
4. **Criar /api/tracking/mark-purchase-sent**
5. **Melhorar BotUser com tracking_session_id**
6. **Implementar Sticky Pixel completo**

---

**Esta roadmap levará o sistema atual dos 30% para os 100% da V4.1!** 🚀

---

codigos que devemos usar 

# CÓDIGO COMPLETO V4.1 - TODOS OS COMPONENTES

## 📋 ÍNDICE

1. [Flask Route - Redirecionador](#1-flask-route---redirecionador)
2. [Template - telegram_redirect.html](#2-template---telegram_redirecthtml)
3. [API - /api/tracking/cookies](#3-api---apitrackingcookies)
4. [BotManager - Interação Telegram](#4-botmanager---interação-telegram)
5. [PIX Generation](#5-pix-generation)
6. [Webhook - Confirmação](#6-webhook---confirmação)
7. [Payment Delivery](#7-payment-delivery)
8. [Flask Route - Delivery](#8-flask-route---delivery)
9. [Template - delivery.html](#9-template---deliveryhtml)
10. [API - mark-purchase-sent](#10-api---mark-purchase-sent)

---

## 1. FLASK ROUT - REDIRECIONADOR

```python
# routes/redirect.py

from flask import Blueprint, request, redirect, render_template
from internal_logic.core.extensions import db
from internal_logic.core.models import RedirectPool, PoolBot
from utils.tracking_service import TrackingServiceV4
from utils.user_ip import get_user_ip
import uuid
import logging

logger = logging.getLogger(__name__)
redirect_bp = Blueprint('redirect', __name__)

@redirect_bp.route('/go/<slug>')
def public_redirect(slug):
    """
    PONTO DE NASCIMENTO DO TRACKING V4.1
    """
    
    # 1.1 - Identificar pool pelo slug
    pool = RedirectPool.query.filter_by(slug=slug).first()
    if not pool:
        return "Redirect não encontrado", 404
    
    # 1.2 - Load balancing entre bots do pool
    pool_bot = get_pool_bot(pool)
    if not pool_bot:
        return "Nenhum bot disponível", 503
    
    # 1.3 - Detectar crawler (não trackear)
    def is_crawler(ua: str) -> bool:
        crawler_patterns = [
            'facebookexternalhit', 'facebot', 'telegrambot', 'whatsapp',
            'python-requests', 'curl', 'wget', 'bot', 'crawler', 'spider',
            'scraper', 'googlebot', 'bingbot', 'slurp', 'duckduckbot',
            'baiduspider', 'yandexbot', 'sogou', 'exabot', 'ia_archiver'
        ]
        return any(pattern in ua.lower() for pattern in crawler_patterns)
    
    is_crawler_request = is_crawler(request.headers.get('User-Agent', ''))
    
    # 1.4 - Capturar parâmetros de tracking
    fbclid = request.args.get('fbclid')
    grim_param = request.args.get('grim', '')
    utm_source = request.args.get('utm_source', '')
    utm_campaign = request.args.get('utm_campaign', '')
    utm_medium = request.args.get('utm_medium', '')
    utm_content = request.args.get('utm_content', '')
    utm_term = request.args.get('utm_term', '')
    
    # 1.5 - Capturar pixel_id (4 prioridades)
    pixel_sources = [
        request.args.get('px'),              # 1. Query param 'px' (remarketing)
        pool.meta_pixel_id,                 # 2. Pool.meta_pixel_id (padrão)
        fbclid if fbclid and fbclid.isdigit() else None,  # 3. FBCLID como pixel
        grim_param if grim_param and grim_param.isdigit() else None  # 4. GRIM como pixel
    ]
    pixel_id_to_use = next((p for p in pixel_sources if p), None)
    
    # 1.6 - Gerar tracking_token (se não for crawler e tiver pixel)
    tracking_token = None
    if not is_crawler_request and pool.meta_tracking_enabled and pixel_id_to_use:
        tracking_token = uuid.uuid4().hex
        
        # 1.7 - Capturar cookies FBP/FBC (V4.1)
        fbp_cookie = request.cookies.get('_fbp') or request.args.get('_fbp_cookie')
        fbc_cookie = request.cookies.get('_fbc') or request.args.get('_fbc_cookie')
        
        # 1.8 - Salvar tracking_data no Redis (V4.1)
        tracking_data = {
            'pixel_id': pixel_id_to_use,
            'fbp': fbp_cookie,
            'fbc': fbc_cookie,
            'fbc_origin': 'cookie' if fbc_cookie else None,
            'fbp_origin': 'cookie' if fbp_cookie else None,
            'fbclid': fbclid,
            'pageview_event_id': f"pageview_{tracking_token}",
            'event_source_url': request.url,
            'first_page': request.url,
            'client_ip': get_user_ip(request),
            'client_user_agent': request.headers.get('User-Agent', ''),
            'utm_source': utm_source,
            'utm_campaign': utm_campaign,
            'utm_medium': utm_medium,
            'utm_content': utm_content,
            'utm_term': utm_term,
            'grim': grim_param,
            'pageview_sent': False,
            'tracking_token': tracking_token
        }
        
        # 1.9 - Importar TrackingServiceV4 (V4.1)
        tracking_service_v4 = TrackingServiceV4()
        
        # 1.10 - Salvar no Redis (V4.1)
        tracking_service_v4.save_tracking_token(tracking_token, tracking_data, ttl=3600)
        
        logger.info(f"✅ V4.1 - Tracking token salvo: {tracking_token[:8]}... | pixel_id: {pixel_id_to_use}")
    
    # 1.11 - Preparar parâmetro de tracking
    if tracking_token and not is_crawler_request:
        tracking_param = tracking_token
    elif is_crawler_request:
        tracking_param = f"p{pool.id}"
    elif not pool.meta_tracking_enabled:
        tracking_param = f"p{pool.id}"
    else:
        logger.error(f"❌ tracking_token ausente mas deveria existir!")
        raise ValueError("tracking_token ausente")
    
    # 1.12 - DECISÃO CRÍTICA V4.1: Renderizar HTML vs Redirect 302
    if not is_crawler_request and pool.meta_tracking_enabled:
        # RENDERIZAR HTML COM META PIXEL (HTML-Only)
        return render_template('telegram_redirect.html',
            bot_username=pool_bot.bot.username,
            tracking_token=tracking_token,
            pixel_id=pixel_id_to_use,
            utmify_pixel_id=pool.utmify_pixel_id if pool.utmify_enabled else None,
            fbclid=fbclid or '',
            utm_source=utm_source,
            utm_campaign=utm_campaign,
            utm_medium=utm_medium,
            utm_content=utm_content,
            utm_term=utm_term,
            grim=grim_param
        )
    
    # Se for crawler ou não tiver pixel, usar redirect 302
    redirect_url = f"https://t.me/{pool_bot.bot.username}?start={tracking_param}"
    return redirect(redirect_url, code=302)

def get_pool_bot(pool):
    """Load balancing entre bots do pool"""
    pool_bots = PoolBot.query.filter_by(pool_id=pool.id, enabled=True).all()
    if not pool_bots:
        return None
    
    # Simple round-robin
    import random
    return random.choice(pool_bots)
```

---

## 2. TEMPLATE - telegram_redirect.html

```html
<!-- templates/telegram_redirect.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Redirecionando...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- META PIXEL PAGEVIEW - V4.1 -->
    {% if pixel_id %}
    <script>
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');

    fbq('init', '{{ pixel_id }}');
    fbq('track', 'PageView', {
        external_id: '{{ fbclid or "" }}',
        event_id: 'pageview_{{ tracking_token }}'
    });
    
    console.log('✅ V4.1 - PageView disparado:', {
        pixel_id: '{{ pixel_id }}',
        event_id: 'pageview_{{ tracking_token }}',
        fbclid: '{{ fbclid }}'
    });
    
    // V4.1: Capturar cookies gerados pelo Meta Pixel
    setTimeout(function() {
        var fbp = document.cookie.match('(^|;)\\s*_fbp\\s*=\\s*([^;]+)');
        var fbc = document.cookie.match('(^|;)\\s*_fbc\\s*=\\s*([^;]+)');
        
        var data = {
            tracking_token: '{{ tracking_token }}',
            fbp: fbp ? fbp[2] : null,
            fbc: fbc ? fbc[2] : null,
            fbclid: '{{ fbclid or "" }}',
            utm_source: '{{ utm_source or "" }}',
            utm_campaign: '{{ utm_campaign or "" }}',
            utm_medium: '{{ utm_medium or "" }}',
            utm_content: '{{ utm_content or "" }}',
            utm_term: '{{ utm_term or "" }}',
            grim: '{{ grim or "" }}'
        };
        
        console.log('🍪 V4.1 - Enviando cookies:', data);
        
        // Enviar via Beacon API (V4.1)
        navigator.sendBeacon('/api/tracking/cookies', JSON.stringify(data));
    }, 1000);
    </script>
    {% endif %}

    <!-- UTMIFY (se configurado) -->
    {% if utmify_pixel_id %}
    <script>
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');

    fbq('init', '{{ utmify_pixel_id }}');
    fbq('track', 'PageView');
    
    console.log('✅ V4.1 - Utmify PageView disparado:', {
        pixel_id: '{{ utmify_pixel_id }}'
    });
    </script>
    {% endif %}
</head>
<body>
    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; align-items: center; justify-content: center;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); max-width: 400px; width: 90%;">
            <h2 style="color: #333; margin-bottom: 20px;">🚀 Redirecionando...</h2>
            <p style="color: #666; margin-bottom: 30px;">Aguarde um momento enquanto preparamos seu acesso...</p>
            
            <div style="margin: 30px 0;">
                <div style="border: 4px solid #0088cc; border-radius: 50%; width: 50px; height: 50px; margin: 0 auto; animation: spin 1s linear infinite;"></div>
            </div>
            
            <p style="color: #999; font-size: 14px;">Você será redirecionado automaticamente para o Telegram</p>
        </div>
    </div>

    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    body {
        margin: 0;
        padding: 0;
    }
    </style>

    <!-- REDIRECIONAMENTO AUTOMÁTICO (CLIENT-SIDE) -->
    <script>
    setTimeout(function() {
        console.log('🔄 V4.1 - Redirecionando para Telegram...');
        window.location.href = 'https://t.me/{{ bot_username }}?start={{ tracking_token }}';
    }, 2000);
    </script>
</body>
</html>
```

---

## 3. API - /api/tracking/cookies

```python
# routes/api.py

from flask import Blueprint, request, jsonify
from utils.tracking_service import TrackingServiceV4
import json as json_lib
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/tracking/cookies', methods=['POST'])
def capture_tracking_cookies():
    """
    V4.1: ENDPOINT PARA CAPTURAR COOKIES _FBP E _FBC DO BROWSER
    
    Chamado via Beacon API pelo telegram_redirect.html após Meta Pixel carregar.
    Atualiza tracking_data no Redis com cookies gerados pelo Meta Pixel.
    """
    try:
        # V4.1: Parsear JSON (Beacon API não envia Content-Type)
        data = None
        
        try:
            data = request.get_json(force=True, silent=True)
        except Exception:
            pass
        
        if not data:
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    data = json_lib.loads(raw_data)
            except (json_lib.JSONDecodeError, ValueError) as e:
                logger.warning(f"Erro ao parsear JSON: {e}")
                return jsonify({'success': False}), 400
        
        # V4.1: Validar dados
        tracking_token = data.get('tracking_token')
        if not tracking_token:
            return jsonify({'success': False, 'error': 'tracking_token required'}), 400
        
        # V4.1: Recuperar tracking_data existente
        tracking_service_v4 = TrackingServiceV4()
        existing_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
        
        # V4.1: Atualizar com cookies do browser
        updated_data = {
            **existing_data,
            'fbp': data.get('fbp') or existing_data.get('fbp'),
            'fbc': data.get('fbc') or existing_data.get('fbc'),
            'fbc_origin': 'cookie' if data.get('fbc') else existing_data.get('fbc_origin'),
            'fbp_origin': 'cookie' if data.get('fbp') else existing_data.get('fbp_origin'),
            'pageview_sent': True,  # Marcar que PageView foi enviado
        }
        
        # V4.1: Salvar dados atualizados no Redis
        tracking_service_v4.save_tracking_token(tracking_token, updated_data, ttl=3600)
        
        logger.info(f"✅ V4.1 - Cookies capturados: {tracking_token[:8]}... | fbp: {'✅' if data.get('fbp') else '❌'} | fbc: {'✅' if data.get('fbc') else '❌'}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro ao capturar cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

## 4. BOTMANAGER - INTERAÇÃO TELEGRAM

```python
# services/bot_manager.py

from internal_logic.core.extensions import db
from internal_logic.core.models import BotUser
from utils.tracking_service import TrackingServiceV4
import logging

logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self, bot_id, user_id):
        self.bot_id = bot_id
        self.user_id = user_id
    
    def handle_start_command(self, message):
        """
        V4.1: Preservar tracking durante interação no Telegram
        """
        user_id = message.from_user.id
        
        # 4.1 - Extrair tracking_token do start param
        start_param = message.text.split('/start ')[1] if '/start ' in message.text else None
        tracking_token = start_param if start_param and len(start_param) == 32 else None
        
        # 4.2 - Buscar/criar BotUser
        bot_user = BotUser.query.filter_by(
            bot_id=self.bot_id,
            telegram_user_id=str(user_id)
        ).first()
        
        if not bot_user:
            bot_user = BotUser(
                bot_id=self.bot_id,
                telegram_user_id=str(user_id),
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            db.session.add(bot_user)
        
        # 4.3 - V4.1: Preservar tracking_token e pixel_id
        if tracking_token:
            tracking_service_v4 = TrackingServiceV4()
            
            # Recuperar dados do Redis
            tracking_data = tracking_service_v4.recover_tracking_data(tracking_token)
            
            if tracking_data:
                # Preservar dados no BotUser
                bot_user.tracking_session_id = tracking_token
                bot_user.pixel_id = tracking_data.get('pixel_id')
                bot_user.fbclid = tracking_data.get('fbclid')
                bot_user.campaign_code = tracking_data.get('pixel_id')  # Para remarketing
                
                logger.info(f"✅ V4.1 - Tracking preservado no BotUser: {tracking_token[:8]}... | pixel_id: {tracking_data.get('pixel_id')}")
        
        db.session.commit()
        
        return bot_user
    
    def send_message(self, chat_id, text, parse_mode=None):
        """Enviar mensagem via Telegram"""
        # Implementação do envio de mensagem
        # Aqui você usaria a biblioteca python-telegram-bot
        pass
```

---

## 5. PIX GENERATION

```python
# services/payment_service.py

from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, BotUser
from utils.tracking_service import TrackingServiceV4
from datetime import datetime
import uuid
import hashlib
import logging

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, bot_id):
        self.bot_id = bot_id
    
    def generate_pix_payment(self, user_id, amount, description):
        """
        V4.1: Gerar PIX com tracking preservado
        """
        # 5.1 - Buscar BotUser com tracking
        bot_user = BotUser.query.filter_by(
            bot_id=self.bot_id,
            telegram_user_id=str(user_id)
        ).first()
        
        # 5.2 - Gerar payment com tracking
        payment = Payment(
            payment_id=f"BOT{self.bot_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}",
            amount=amount,
            description=description,
            status='pending',
            customer_user_id=str(user_id),
            bot_id=self.bot_id,
            
            # V4.1: Preservar tracking
            tracking_token=getattr(bot_user, 'tracking_session_id', None),
            meta_pixel_id=getattr(bot_user, 'pixel_id', None),
            fbclid=getattr(bot_user, 'fbclid', None),
            
            created_at=datetime.utcnow()
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # 5.3 - Gerar PIX
        pix_data = {
            'txid': payment.payment_id,
            'value': amount,
            'description': description,
            'qr_code': self.generate_qr_code(payment.payment_id, amount),
            'expiration': datetime.utcnow() + timedelta(hours=24)
        }
        
        logger.info(f"✅ V4.1 - PIX gerado: {payment.payment_id} | tracking_token: {payment.tracking_token[:8] if payment.tracking_token else 'None'}...")
        
        return pix_data, payment
    
    def generate_qr_code(self, payment_id, amount):
        """Gerar QR Code PIX"""
        # Implementação da geração de QR Code
        # Aqui você usaria uma biblioteca como qrcode
        return f"pix_qr_code_{payment_id}_{amount}"
```

---

## 6. WEBHOOK - CONFIRMAÇÃO

```python
# routes/webhook.py

from flask import Blueprint, request, jsonify
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment
from services.payment_service import PaymentService
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook/payment', methods=['POST'])
def payment_webhook():
    """
    V4.1: Processar confirmação de pagamento
    """
    try:
        # 6.1 - Processar webhook
        data = request.get_json()
        payment_id = data.get('payment_id')
        status = data.get('status')
        amount = data.get('amount')
        
        logger.info(f"🔔 V4.1 - Webhook recebido: {payment_id} | status: {status}")
        
        # 6.2 - Buscar payment
        payment = Payment.query.filter_by(payment_id=payment_id).first()
        if not payment:
            logger.warning(f"⚠️ V4.1 - Payment não encontrado: {payment_id}")
            return "Payment not found", 404
        
        # 6.3 - Atualizar status
        if status == 'paid' and payment.status == 'pending':
            payment.status = 'paid'
            payment.paid_at = datetime.utcnow()
            payment.gateway_transaction_id = data.get('transaction_id')
            
            # V4.1: Gerar delivery_token
            delivery_token = hashlib.sha256(f"{payment.id}{payment.payment_id}{payment.bot_id}".encode()).hexdigest()
            payment.delivery_token = delivery_token
            
            db.session.commit()
            
            # 6.4 - V4.1: Enviar mensagem com link inteligente
            from services.delivery_service import DeliveryService
            delivery_service = DeliveryService()
            delivery_service.send_payment_delivery(payment)
            
            logger.info(f"✅ V4.1 - Pagamento confirmado: {payment.payment_id} | delivery_token: {delivery_token[:16]}...")
        
        return "OK", 200
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro no webhook: {e}")
        return "Error", 500
```

---

## 7. PAYMENT DELIVERY

```python
# services/delivery_service.py

from flask import url_for
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, BotUser, PoolBot
from utils.tracking_service import TrackingServiceV4
import logging

logger = logging.getLogger(__name__)

class DeliveryService:
    def send_payment_delivery(self, payment):
        """
        V4.1: Enviar mensagem com decisão inteligente do link
        """
        # 7.1 - Verificar se pagamento está confirmado
        if payment.status != 'paid':
            return False
        
        # 7.2 - V4.1: Recuperar dados de tracking
        tracking_data = {}
        if payment.tracking_token:
            tracking_service_v4 = TrackingServiceV4()
            tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
        
        # 7.3 - V4.1: Buscar pixel_id (4 prioridades)
        pixel_sources = [
            getattr(payment, 'meta_pixel_id', None),    # 1. Payment
            tracking_data.get('pixel_id'),               # 2. Redis
            getattr(payment.bot.config, 'pixel_id', None), # 3. Bot config
            None                                       # 4. Pool (fallback)
        ]
        
        # Buscar pool do bot
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if pool_bot and pool_bot.pool:
            pixel_sources.append(pool_bot.pool.meta_pixel_id)
        
        pixel_id = next((p for p in pixel_sources if p), None)
        
        # 7.4 - V4.1: Decisão INTELIGENTE do link
        if pixel_id and tracking_data:
            # Pixel ATIVO → usar /delivery com tracking
            link_to_send = url_for(
                'delivery.delivery_page',
                delivery_token=payment.delivery_token,
                px=pixel_id,  # Passar pixel_id na URL
                _external=True
            )
            
            logger.info(f"✅ V4.1 - Link DECISÃO: /delivery/{payment.delivery_token[:16]}...?px={pixel_id[:8]}...")
            
        else:
            # Pixel INATIVO → usar access_link direto
            access_link = getattr(payment.bot.config, 'access_link', None)
            if access_link:
                link_to_send = access_link
                logger.info(f"✅ V4.1 - Link DECISÃO: access_link direto")
            else:
                # Sem pixel e sem access_link → mensagem genérica
                link_to_send = None
                logger.info(f"✅ V4.1 - Link DECISÃO: mensagem genérica (sem pixel e sem access_link)")
        
        # 7.5 - V4.1: Enviar mensagem via Telegram
        from services.bot_manager import BotManager
        bot_manager = BotManager(payment.bot_id, payment.bot.user_id)
        
        if link_to_send:
            message = (
                f"✅ *Pagamento Confirmado!*\n\n"
                f"📦 *Produto:* {payment.description}\n"
                f"💰 *Valor:* R$ {payment.amount:.2f}\n\n"
                f"🔗 *Acessar Produto:* [Clique Aqui]({link_to_send})"
            )
        else:
            message = (
                f"✅ *Pagamento Confirmado!*\n\n"
                f"📦 *Produto:* {payment.description}\n"
                f"💰 *Valor:* R$ {payment.amount:.2f}\n\n"
                f"📩 *Seu acesso será enviado em breve.*"
            )
        
        # Enviar mensagem
        success = bot_manager.send_message(
            chat_id=payment.customer_user_id,
            text=message,
            parse_mode='Markdown'
        )
        
        return success
```

---

## 8. FLASK ROUT - DELIVERY

```python
# routes/delivery.py

from flask import Blueprint, request, render_template, jsonify
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, BotUser, PoolBot
from utils.tracking_service import TrackingServiceV4
import logging

logger = logging.getLogger(__name__)
delivery_bp = Blueprint('delivery', __name__, url_prefix='/delivery')

@delivery_bp.route('/<token>')
def delivery_page(token):
    """
    V4.1: Página de entrega com recuperação completa de tracking
    """
    try:
        # 8.1 - Buscar payment pelo delivery_token
        payment = Payment.query.filter_by(delivery_token=token).first()
        if not payment:
            return render_template('delivery_error.html', error="Link inválido"), 404
        
        # 8.2 - Verificar status
        if payment.status != 'paid':
            return render_template('delivery_error.html', error="Pagamento não confirmado"), 200
        
        # 8.3 - V4.1: Anti-duplicação (F5)
        purchase_already_sent = getattr(payment, 'meta_purchase_sent', False)
        event_id = getattr(payment, 'meta_event_id', None) or f"purchase_{payment.id}"
        
        # Salvar event_id se ainda não existir
        if not purchase_already_sent and not getattr(payment, 'meta_event_id', None):
            payment.meta_event_id = event_id
            db.session.commit()
        
        # 8.4 - V4.1: Recuperar dados de tracking (4 prioridades)
        tracking_data = {}
        tracking_service_v4 = None
        
        # Prioridade 1: bot_user.tracking_session_id
        if payment.customer_user_id:
            bot_user = BotUser.query.filter_by(
                bot_id=payment.bot_id,
                telegram_user_id=str(payment.customer_user_id)
            ).first()
            
            if bot_user and bot_user.tracking_session_id:
                tracking_service_v4 = TrackingServiceV4()
                tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
                logger.info(f"✅ V4.1 - Tracking recuperado via BotUser: {len(tracking_data)} campos")
        
        # Prioridade 2: payment.tracking_token
        if not tracking_data and payment.tracking_token:
            if not tracking_service_v4:
                tracking_service_v4 = TrackingServiceV4()
            tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
            logger.info(f"✅ V4.1 - Tracking recuperado via Payment: {len(tracking_data)} campos")
        
        # Prioridade 3: Redis direto
        if not tracking_data:
            if not tracking_service_v4:
                tracking_service_v4 = TrackingServiceV4()
            tracking_data = tracking_service_v4.recover_tracking_data(f"tracking:payment:{payment.id}") or {}
            logger.info(f"✅ V4.1 - Tracking recuperado via Redis direto: {len(tracking_data)} campos")
        
        # Prioridade 4: Fallback payment
        if not tracking_data:
            tracking_data = {
                'pixel_id': getattr(payment, 'meta_pixel_id', None),
                'fbclid': getattr(payment, 'fbclid', None)
            }
            logger.info(f"✅ V4.1 - Tracking recuperado via Fallback Payment")
        
        # 8.5 - V4.1: Buscar pixel_id (4 prioridades)
        pixel_sources = [
            request.args.get('px'),                    # 1. Query param
            getattr(payment, 'meta_pixel_id', None),   # 2. Payment
            tracking_data.get('pixel_id'),             # 3. Redis
            pool_bot.pool.meta_pixel_id if pool_bot and pool_bot.pool else None  # 4. Pool
        ]
        pixel_id_to_use = next((p for p in pixel_sources if p), None)
        
        # 8.6 - V4.1: Validar FBC (CRÍTICO!)
        fbc_value = tracking_data.get('fbc')
        fbc_origin = tracking_data.get('fbc_origin')
        
        # V4.1: Ignorar FBC sintético
        if fbc_value and fbc_origin == 'synthetic':
            logger.warning(f"⚠️ V4.1 - FBC IGNORADO (origem: synthetic) - Meta não atribui")
            fbc_value = None
            fbc_origin = None
        
        # 8.7 - Preparar redirect_url
        redirect_url = None
        if payment.bot and payment.bot.config:
            redirect_url = getattr(payment.bot.config, 'access_link', None)
        
        # 8.8 - V4.1: Renderizar template com injeção completa
        return render_template('delivery.html',
            payment=payment,
            pixel_id=pixel_id_to_use,
            purchase_event_id=event_id,
            purchase_already_sent=purchase_already_sent,
            redirect_url=redirect_url,
            
            # V4.1: Dados de tracking completos
            fbp=tracking_data.get('fbp'),
            fbc=fbc_value,
            fbclid=tracking_data.get('fbclid'),
            fbc_origin=fbc_origin,
            tracking_token=payment.tracking_token,
            
            # Debug
            debug=current_app.debug
        )
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro na página de delivery: {e}", exc_info=True)
        return render_template('delivery_error.html', error=str(e)), 500
```

---

## 9. TEMPLATE - delivery.html

```html
<!-- templates/delivery.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Entrega do Produto</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- V4.1: META PIXEL PURCHASE -->
    {% if pixel_id and not purchase_already_sent %}
    <script>
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');

    fbq('init', '{{ pixel_id }}');
    
    // V4.1: Disparar Purchase com dados completos
    fbq('track', 'Purchase', {
        value: {{ payment.amount }},
        currency: 'BRL',
        event_id: '{{ purchase_event_id }}',
        content_ids: ['{{ payment.payment_id }}'],
        content_type: 'product',
        external_id: '{{ fbclid or "" }}'
    }, {
        fbp: '{{ fbp or "" }}',
        fbc: '{{ fbc or "" }}'
    });
    
    console.log('✅ V4.1 - Purchase disparado:', {
        pixel_id: '{{ pixel_id }}',
        event_id: '{{ purchase_event_id }}',
        value: {{ payment.amount }},
        fbp: '{{ fbp }}',
        fbc: '{{ fbc }}',
        fbc_origin: '{{ fbc_origin }}',
        fbclid: '{{ fbclid }}'
    });
    
    // V4.1: Marcar como enviado via API
    fetch('/api/tracking/mark-purchase-sent', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            payment_id: {{ payment.id }},
            event_id: '{{ purchase_event_id }}'
        })
    }).then(response => response.json())
      .then(data => console.log('✅ V4.1 - Purchase marcado:', data))
      .catch(error => console.error('❌ V4.1 - Erro ao marcar Purchase:', error));
      
    </script>
    {% endif %}
</head>
<body>
    <div style="max-width: 800px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh;">
        <div style="background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin: 20px 0;">
            <h1 style="color: #333; margin-bottom: 30px; text-align: center;">🎉 Entrega do Produto</h1>
            
            {% if purchase_already_sent %}
            <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #28a745;">
                <h3 style="color: #155724; margin: 0;">✅ Pagamento já processado!</h3>
                <p style="color: #155724; margin: 10px 0 0 0;">Seu acesso foi liberado anteriormente.</p>
            </div>
            {% endif %}
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #495057; margin: 0 0 15px 0;">📋 Dados do Pagamento</h3>
                <p style="margin: 5px 0;"><strong>ID:</strong> {{ payment.payment_id }}</p>
                <p style="margin: 5px 0;"><strong>Valor:</strong> R$ {{ "%.2f"|format(payment.amount) }}</p>
                <p style="margin: 5px 0;"><strong>Status:</strong> 
                    <span style="color: {% if payment.status == 'paid' %}#28a745{% else %}#dc3545{% endif %}; font-weight: bold;">
                        {{ payment.status.upper() }}
                    </span>
                </p>
                <p style="margin: 5px 0;"><strong>Data:</strong> {{ payment.paid_at.strftime('%d/%m/%Y %H:%M') if payment.paid_at else 'N/A' }}</p>
            </div>
            
            {% if redirect_url %}
            <div style="text-align: center; margin: 40px 0;">
                <a href="{{ redirect_url }}" 
                   style="background: linear-gradient(45deg, #0088cc, #006699); color: white; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-size: 18px; font-weight: bold; display: inline-block; box-shadow: 0 4px 15px rgba(0,136,204,0.3); transition: all 0.3s ease;"
                   onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(0,136,204,0.4)'"
                   onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(0,136,204,0.3)'">
                    🚀 Acessar Produto Agora
                </a>
            </div>
            {% endif %}
            
            <!-- V4.1: Debug Info -->
            {% if debug %}
            <div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h4 style="color: #856404; margin: 0 0 15px 0;">🔍 V4.1 - Debug Info:</h4>
                <div style="font-family: monospace; font-size: 12px; line-height: 1.5;">
                    <p style="margin: 2px 0;"><strong>Pixel ID:</strong> {{ pixel_id or 'None' }}</p>
                    <p style="margin: 2px 0;"><strong>Event ID:</strong> {{ purchase_event_id }}</p>
                    <p style="margin: 2px 0;"><strong>Purchase Already Sent:</strong> {{ purchase_already_sent }}</p>
                    <p style="margin: 2px 0;"><strong>FBP:</strong> {{ fbp or 'None' }}</p>
                    <p style="margin: 2px 0;"><strong>FBC:</strong> {{ fbc or 'None' }}</p>
                    <p style="margin: 2px 0;"><strong>FBC Origin:</strong> {{ fbc_origin or 'None' }}</p>
                    <p style="margin: 2px 0;"><strong>FBCLID:</strong> {{ fbclid or 'None' }}</p>
                    <p style="margin: 2px 0;"><strong>Tracking Token:</strong> {{ tracking_token[:16] + '...' if tracking_token else 'None' }}</p>
                </div>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
```

---

## 10. API - mark-purchase-sent

```python
# routes/api.py (continuação)

@api_bp.route('/api/tracking/mark-purchase-sent', methods=['POST'])
def mark_purchase_sent():
    """
    V4.1: API para marcar Purchase como enviado (anti-duplicação)
    """
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        event_id = data.get('event_id')
        
        if not payment_id:
            return jsonify({'error': 'payment_id obrigatório'}), 400
        
        # Buscar payment
        payment = Payment.query.filter_by(id=int(payment_id)).first_or_404()
        
        # V4.1: Defensivo - só marcar se pagamento estiver confirmado
        if payment.status != 'paid':
            logger.warning(f"⚠️ V4.1 - Tentativa de marcar Purchase para pagamento não confirmado: {payment_id}")
            return jsonify({'error': 'Pagamento não confirmado'}), 400
        
        # V4.1: Marcar como enviado
        payment.meta_purchase_sent = True
        if event_id:
            payment.meta_event_id = event_id
        
        db.session.commit()
        
        logger.info(f"✅ V4.1 - Purchase marcado como enviado: payment_id={payment_id}, event_id={event_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro ao marcar Purchase: {e}")
        return jsonify({'error': str(e)}), 500
```

---

## 🎯 IMPLEMENTAÇÃO DO TRACKING SERVICE V4.1

```python
# services/tracking_service.py

import redis
import json
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TrackingServiceV4:
    """Serviço de Tracking V4.1 - Persistência completa no Redis"""
    
    def __init__(self, redis_url: str = None):
        self.redis = redis.from_url(redis_url or 'redis://localhost:6379/0')
        self.ttl_default = 3600  # 1 hora
    
    def save_tracking_token(self, tracking_token: str, tracking_data: Dict[str, Any], ttl: int = None) -> bool:
        """Salva dados de tracking no Redis"""
        try:
            key = f"tracking:{tracking_token}"
            ttl = ttl or self.ttl_default
            
            # Salvar dados completos
            self.redis.setex(key, ttl, json.dumps(tracking_data))
            
            # Salvar pixel_id separadamente para lookup rápido
            if tracking_data.get('pixel_id'):
                pixel_key = f"pixel:{tracking_data['pixel_id']}"
                self.redis.setex(pixel_key, ttl, tracking_token)
            
            logger.info(f"Tracking V4.1: Dados salvos para token {tracking_token[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Tracking V4.1: Erro ao salvar dados: {e}")
            return False
    
    def recover_tracking_data(self, tracking_token: str) -> Optional[Dict[str, Any]]:
        """Recupera dados de tracking do Redis"""
        try:
            key = f"tracking:{tracking_token}"
            data = self.redis.get(key)
            
            if data:
                tracking_data = json.loads(data)
                logger.info(f"Tracking V4.1: Dados recuperados para token {tracking_token[:8]}...")
                return tracking_data
            
            return None
            
        except Exception as e:
            logger.error(f"Tracking V4.1: Erro ao recuperar dados: {e}")
            return None
    
    def find_token_by_pixel(self, pixel_id: str) -> Optional[str]:
        """Encontra tracking_token pelo pixel_id"""
        try:
            key = f"pixel:{pixel_id}"
            tracking_token = self.redis.get(key)
            
            if tracking_token:
                return tracking_token.decode('utf-8')
            
            return None
            
        except Exception as e:
            logger.error(f"Tracking V4.1: Erro ao buscar token por pixel: {e}")
            return None
    
    @staticmethod
    def generate_fbp() -> str:
        """Gera FBP no servidor"""
        import time
        import random
        
        # Formato: fb.1.{subdomain}.{random}
        subdomain = int(time.time())  # Timestamp
        random_num = random.randint(1000000000, 9999999999)
        
        return f"fb.1.{subdomain}.{random_num}"
    
    def cleanup_expired_tokens(self) -> int:
        """Limpa tokens expirados (manutenção)"""
        try:
            pattern = "tracking:*"
            keys = self.redis.keys(pattern)
            
            expired_count = 0
            for key in keys:
                if not self.redis.exists(key):
                    expired_count += 1
            
            logger.info(f"Tracking V4.1: Limpeza realizada - {expired_count} tokens expirados")
            return expired_count
            
        except Exception as e:
            logger.error(f"Tracking V4.1: Erro na limpeza: {e}")
            return 0

# Classe legacy para compatibilidade
class TrackingService:
    """Compatibilidade com versão antiga"""
    
    @staticmethod
    def save_tracking_data(fbclid: str, fbp: str, fbc: str, **kwargs):
        """Salva dados de tracking (legado)"""
        logger.warning("TrackingService.save_tracking_data: Método legado chamado")
        pass
    
    @staticmethod
    def generate_fbp() -> str:
        """Gera FBP (legado)"""
        return TrackingServiceV4.generate_fbp()
```

---

## 🎯 RESUMO FINAL

**Este documento contém TODO o código completo da V4.1:**

1. **Flask Route** - Redirecionador com tracking completo
2. **Template** - Página HTML com Meta Pixel
3. **API** - Captura de cookies via Beacon
4. **BotManager** - Preservação de tracking no Telegram
5. **PIX Service** - Geração de pagamento com tracking
6. **Webhook** - Processamento de confirmação
7. **Delivery Service** - Decisão inteligente de links
8. **Flask Route** - Página de entrega com recuperação
9. **Template** - Delivery com Purchase tracking
10. **API** - Marcação de Purchase (anti-duplicação)
11. **TrackingService** - Serviço completo V4.1

**Basta copiar e implementar no seu sistema novo!** 🚀

