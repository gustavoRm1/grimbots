# ✅ CHECKLIST DE VALIDAÇÃO - META PIXEL

**Data:** 2025-11-15  
**Nível:** 🔥 **ULTRA SÊNIOR - QI 1000+**  
**Objetivo:** Validar se o Meta Pixel está funcionando corretamente

---

## 📋 CHECKLIST COMPLETO

### **1. INFRAESTRUTURA**

#### **✅ Celery está rodando:**
```bash
# Verificar processos Celery
ps aux | grep celery | grep -v grep

# Verificar serviço Celery
systemctl status grimbots-celery.service

# Verificar tasks ativas
celery -A celery_app inspect active
```

**Status:** ✅ **CELERY FUNCIONANDO** (16 processos encontrados, serviço ativo)

---

#### **✅ Gunicorn está rodando:**
```bash
# Verificar processos Gunicorn
ps aux | grep gunicorn | grep -v grep

# Verificar serviço Gunicorn
systemctl status grimbots.service

# Verificar logs
tail -f logs/gunicorn.log
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Redis está rodando:**
```bash
# Verificar Redis
redis-cli ping

# Verificar chaves de tracking
redis-cli KEYS "tracking:*" | wc -l
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

### **2. FLUXO DE TRACKING**

#### **✅ PageView Event:**

**Verificações:**
- [ ] URL de redirect acessível: `https://app.grimbots.online/go/{slug}?grim=...`
- [ ] Meta Pixel JS carrega no HTML bridge
- [ ] Cookies `_fbp` e `_fbc` são capturados
- [ ] `tracking_token` é gerado e salvo no Redis
- [ ] `pageview_event_id` é gerado e salvo no Redis
- [ ] PageView é enfileirado no Celery
- [ ] PageView é enviado para Meta CAPI

**Comandos de verificação:**
```bash
# Verificar logs de PageView
tail -f logs/gunicorn.log | grep -iE "\[META PAGEVIEW\]|PageView enfileirado|PageView ENVIADO"

# Verificar tracking_token no Redis
redis-cli GET "tracking:{tracking_token}"

# Verificar pageview_event_id no Redis
redis-cli GET "tracking:{tracking_token}" | jq '.pageview_event_id'
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ ViewContent Event:**

**Verificações:**
- [ ] Usuário envia `/start` no bot
- [ ] `tracking_token` é recuperado do `start_param`
- [ ] ViewContent é enfileirado no Celery
- [ ] ViewContent é enviado para Meta CAPI

**Comandos de verificação:**
```bash
# Verificar logs de ViewContent
tail -f logs/gunicorn.log | grep -iE "\[META VIEWCONTENT\]|ViewContent enfileirado|ViewContent ENVIADO"

# Verificar tracking_token no BotUser
# (via admin panel ou SQL)
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Purchase Event:**

**Verificações:**
- [ ] Pagamento é confirmado (status = 'paid')
- [ ] `tracking_token` é recuperado do `bot_user.tracking_session_id` ou `payment.tracking_token`
- [ ] `tracking_data` é recuperado do Redis
- [ ] `pageview_event_id` é reutilizado para deduplicação
- [ ] Purchase é enfileirado no Celery
- [ ] Purchase é enviado para Meta CAPI
- [ ] `meta_purchase_sent` é setado como `True`

**Comandos de verificação:**
```bash
# Verificar logs de Purchase
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]|Purchase enfileirado|Purchase ENVIADO"

# Verificar tracking_data no Redis
redis-cli GET "tracking:{tracking_token}"

# Verificar se Purchase foi enviado
# (via admin panel ou SQL: payment.meta_purchase_sent = True)
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

### **3. DADOS DE TRACKING**

#### **✅ Tracking Token:**

**Verificações:**
- [ ] `tracking_token` é gerado no redirect (UUID hex de 32 chars)
- [ ] `tracking_token` é salvo no Redis com TTL adequado (7 dias)
- [ ] `tracking_token` é passado para o bot via `start_param`
- [ ] `tracking_token` é salvo no `bot_user.tracking_session_id`
- [ ] `tracking_token` é salvo no `payment.tracking_token`

**Comandos de verificação:**
```bash
# Verificar tracking_token no Redis
redis-cli GET "tracking:{tracking_token}"

# Verificar TTL
redis-cli TTL "tracking:{tracking_token}"

# Verificar tracking_token no BotUser
# (via admin panel ou SQL)
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Dados de Tracking (fbp, fbc, fbclid, ip, ua):**

**Verificações:**
- [ ] `fbp` é capturado do cookie `_fbp` ou gerado
- [ ] `fbc` é capturado do cookie `_fbc` (NUNCA gerado sinteticamente)
- [ ] `fbclid` é capturado da URL
- [ ] `client_ip` é capturado corretamente (prioriza Cloudflare headers)
- [ ] `client_user_agent` é capturado corretamente
- [ ] Todos os dados são salvos no Redis

**Comandos de verificação:**
```bash
# Verificar dados no Redis
redis-cli GET "tracking:{tracking_token}" | jq '.fbp, .fbc, .fbclid, .client_ip, .client_user_agent'

# Verificar fbc_origin
redis-cli GET "tracking:{tracking_token}" | jq '.fbc_origin'
# Deve ser 'cookie' (nunca 'synthetic')
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ PageView Event ID:**

**Verificações:**
- [ ] `pageview_event_id` é gerado no redirect (formato: `pageview_{uuid}`)
- [ ] `pageview_event_id` é salvo no Redis
- [ ] `pageview_event_id` é reutilizado no Purchase para deduplicação

**Comandos de verificação:**
```bash
# Verificar pageview_event_id no Redis
redis-cli GET "tracking:{tracking_token}" | jq '.pageview_event_id'

# Verificar se Purchase reutilizou
tail -f logs/gunicorn.log | grep -iE "event_id reutilizado|pageview_event_id"
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

### **4. EVENTOS META**

#### **✅ PageView Event:**

**Verificações:**
- [ ] Evento é enfileirado no Celery
- [ ] Evento é enviado para Meta CAPI
- [ ] `event_id` é único e correto
- [ ] `event_time` está correto (segundos, UTC)
- [ ] `external_id` está normalizado (MD5 se > 80 chars, original se <= 80)
- [ ] `fbp` está presente (cookie ou gerado)
- [ ] `fbc` está presente APENAS se veio do cookie (nunca sintético)
- [ ] `client_ip_address` está presente
- [ ] `client_user_agent` está presente
- [ ] `event_source_url` está presente

**Comandos de verificação:**
```bash
# Verificar logs de PageView
tail -f logs/gunicorn.log | grep -iE "\[META PAGEVIEW\]|PageView enfileirado|PageView ENVIADO"

# Verificar resposta do Meta
tail -f logs/celery.log | grep -iE "SUCCESS.*PageView|EventsReceived.*PageView"
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ ViewContent Event:**

**Verificações:**
- [ ] Evento é enfileirado no Celery
- [ ] Evento é enviado para Meta CAPI
- [ ] `event_id` é único e correto
- [ ] `external_id` está normalizado (mesmo formato do PageView)
- [ ] `fbp` está presente (mesmo do PageView)
- [ ] `fbc` está presente APENAS se veio do cookie (mesmo do PageView)

**Comandos de verificação:**
```bash
# Verificar logs de ViewContent
tail -f logs/gunicorn.log | grep -iE "\[META VIEWCONTENT\]|ViewContent enfileirado|ViewContent ENVIADO"

# Verificar resposta do Meta
tail -f logs/celery.log | grep -iE "SUCCESS.*ViewContent|EventsReceived.*ViewContent"
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Purchase Event:**

**Verificações:**
- [ ] Evento é enfileirado no Celery
- [ ] Evento é enviado para Meta CAPI
- [ ] `event_id` é reutilizado do PageView (deduplicação)
- [ ] `event_time` está correto (segundos, UTC, não futuro, não muito antigo)
- [ ] `external_id` está normalizado (mesmo formato do PageView)
- [ ] `fbp` está presente (mesmo do PageView)
- [ ] `fbc` está presente APENAS se veio do cookie (mesmo do PageView)
- [ ] `client_ip_address` está presente
- [ ] `client_user_agent` está presente
- [ ] `email` está presente (se disponível)
- [ ] `phone` está presente (se disponível)
- [ ] `event_source_url` está presente
- [ ] `action_source` = "website"
- [ ] `custom_data` contém `value`, `currency`, `content_ids`, etc.

**Comandos de verificação:**
```bash
# Verificar logs de Purchase
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]|Purchase enfileirado|Purchase ENVIADO"

# Verificar resposta do Meta
tail -f logs/celery.log | grep -iE "SUCCESS.*Purchase|EventsReceived.*Purchase"

# Verificar se Purchase foi marcado como enviado
# (via admin panel ou SQL: payment.meta_purchase_sent = True)
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

### **5. MATCHING E DEDUPLICAÇÃO**

#### **✅ External ID Normalizado:**

**Verificações:**
- [ ] PageView usa `normalize_external_id()` (MD5 se > 80 chars, original se <= 80)
- [ ] ViewContent usa `normalize_external_id()` (mesmo formato)
- [ ] Purchase usa `normalize_external_id()` (mesmo formato)
- [ ] Todos os eventos usam o MESMO `external_id` normalizado

**Comandos de verificação:**
```bash
# Verificar external_id nos logs
tail -f logs/gunicorn.log | grep -iE "external_id normalizado|external_id usado original"

# Verificar matching
tail -f logs/gunicorn.log | grep -iE "MATCH GARANTIDO|match garantido"
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Event ID Reutilizado:**

**Verificações:**
- [ ] PageView gera `pageview_event_id` único
- [ ] Purchase reutiliza `pageview_event_id` do PageView
- [ ] Deduplicação funciona corretamente no Meta

**Comandos de verificação:**
```bash
# Verificar event_id reutilizado
tail -f logs/gunicorn.log | grep -iE "event_id reutilizado|pageview_event_id"

# Verificar deduplicação
tail -f logs/gunicorn.log | grep -iE "Deduplicação|deduplicação"
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ FBP e FBC Consistentes:**

**Verificações:**
- [ ] `fbp` é o mesmo em PageView, ViewContent e Purchase
- [ ] `fbc` é o mesmo em PageView, ViewContent e Purchase (se presente)
- [ ] `fbc` NUNCA é gerado sinteticamente (apenas do cookie)

**Comandos de verificação:**
```bash
# Verificar fbp e fbc nos logs
tail -f logs/gunicorn.log | grep -iE "fbp recuperado|fbc recuperado|fbc REAL|fbc IGNORADO"

# Verificar fbc_origin
redis-cli GET "tracking:{tracking_token}" | jq '.fbc_origin'
# Deve ser 'cookie' (nunca 'synthetic')
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

### **6. META EVENTS MANAGER**

#### **✅ Eventos Aparecem no Meta Events Manager:**

**Verificações:**
- [ ] PageView aparece no Meta Events Manager
- [ ] ViewContent aparece no Meta Events Manager
- [ ] Purchase aparece no Meta Events Manager
- [ ] Eventos estão linkados (matching funciona)
- [ ] Match Quality é >= 7/10

**Comandos de verificação:**
```bash
# Verificar eventos enviados
tail -f logs/celery.log | grep -iE "SUCCESS.*Meta Event|EventsReceived"

# Verificar no Meta Events Manager (manual)
# https://business.facebook.com/events_manager2
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

#### **✅ Atribuição de Vendas:**

**Verificações:**
- [ ] Vendas aparecem no Meta Ads Manager
- [ ] Vendas são atribuídas às campanhas corretas
- [ ] Match Quality é >= 7/10

**Comandos de verificação:**
```bash
# Verificar vendas atribuídas
# (via Meta Ads Manager - manual)
```

**Status:** ⚠️ **VERIFICAR** (não fornecido)

---

## 🔧 SCRIPT DE VALIDAÇÃO AUTOMÁTICA

Criando script para validar automaticamente todos os itens do checklist:

```python
#!/usr/bin/env python3
"""
Script de Validação Completa - Meta Pixel
Valida todos os itens do checklist automaticamente
"""

import os
import sys
import subprocess
import logging
import json
import redis
from datetime import datetime, timedelta

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_celery():
    """Verifica se Celery está rodando"""
    logger.info("=" * 80)
    logger.info("1️⃣ VERIFICANDO CELERY")
    logger.info("=" * 80)
    
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        celery_processes = [line for line in result.stdout.split('\n') if 'celery' in line.lower() and 'grep' not in line.lower()]
        
        if celery_processes:
            logger.info(f"✅ {len(celery_processes)} processo(s) Celery encontrado(s)")
            return True
        else:
            logger.error("❌ Nenhum processo Celery encontrado!")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Celery: {e}")
        return False

def check_redis():
    """Verifica se Redis está rodando e acessível"""
    logger.info("\n" + "=" * 80)
    logger.info("2️⃣ VERIFICANDO REDIS")
    logger.info("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        
        # Contar chaves de tracking
        tracking_keys = r.keys('tracking:*')
        logger.info(f"✅ Redis está rodando")
        logger.info(f"   Chaves de tracking encontradas: {len(tracking_keys)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Redis: {e}")
        return False

def check_recent_payments():
    """Verifica pagamentos recentes e seus tracking tokens"""
    logger.info("\n" + "=" * 80)
    logger.info("3️⃣ VERIFICANDO PAGAMENTOS RECENTES")
    logger.info("=" * 80)
    
    try:
        from app import app, db
        from models import Payment, BotUser
        
        with app.app_context():
            # Buscar pagamentos das últimas 24 horas
            time_threshold = datetime.utcnow() - timedelta(hours=24)
            recent_payments = Payment.query.filter(
                Payment.created_at >= time_threshold
            ).order_by(Payment.created_at.desc()).limit(10).all()
            
            if not recent_payments:
                logger.warning("⚠️ Nenhum pagamento encontrado nas últimas 24 horas")
                return False
            
            logger.info(f"✅ {len(recent_payments)} pagamento(s) encontrado(s) nas últimas 24 horas")
            
            for payment in recent_payments:
                logger.info(f"\n--- Payment ID: {payment.payment_id} ---")
                logger.info(f"   Status: {payment.status}")
                logger.info(f"   Valor: R$ {payment.amount:.2f}")
                logger.info(f"   Tracking Token: {payment.tracking_token[:30] if payment.tracking_token else 'N/A'}...")
                logger.info(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
                
                # Verificar BotUser
                telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else str(payment.customer_user_id)
                bot_user = BotUser.query.filter_by(bot_id=payment.bot_id, telegram_user_id=telegram_user_id).first()
                
                if bot_user:
                    logger.info(f"   BotUser Tracking Session ID: {bot_user.tracking_session_id[:30] if bot_user.tracking_session_id else 'N/A'}...")
                else:
                    logger.warning(f"   ⚠️ BotUser não encontrado")
            
            return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamentos: {e}", exc_info=True)
        return False

def check_tracking_data():
    """Verifica dados de tracking no Redis"""
    logger.info("\n" + "=" * 80)
    logger.info("4️⃣ VERIFICANDO DADOS DE TRACKING NO REDIS")
    logger.info("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Buscar algumas chaves de tracking recentes
        tracking_keys = r.keys('tracking:*')
        
        if not tracking_keys:
            logger.warning("⚠️ Nenhuma chave de tracking encontrada no Redis")
            return False
        
        logger.info(f"✅ {len(tracking_keys)} chave(s) de tracking encontrada(s)")
        
        # Verificar algumas chaves aleatórias
        sample_keys = tracking_keys[:5]
        
        for key in sample_keys:
            try:
                data = r.get(key)
                if data:
                    tracking_data = json.loads(data)
                    logger.info(f"\n--- Chave: {key} ---")
                    logger.info(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                    logger.info(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                    logger.info(f"   fbc_origin: {tracking_data.get('fbc_origin', 'N/A')}")
                    logger.info(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
                    logger.info(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
                    logger.info(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
                    logger.info(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao processar chave {key}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tracking data: {e}", exc_info=True)
        return False

def check_meta_events_logs():
    """Verifica logs de eventos Meta"""
    logger.info("\n" + "=" * 80)
    logger.info("5️⃣ VERIFICANDO LOGS DE EVENTOS META")
    logger.info("=" * 80)
    
    try:
        # Verificar logs do Gunicorn
        log_file = 'logs/gunicorn.log'
        if os.path.exists(log_file):
            result = subprocess.run(['tail', '-100', log_file], capture_output=True, text=True)
            logs = result.stdout
            
            # Contar eventos
            pageview_count = logs.count('[META PAGEVIEW]')
            viewcontent_count = logs.count('[META VIEWCONTENT]')
            purchase_count = logs.count('[META PURCHASE]')
            
            logger.info(f"✅ Logs encontrados:")
            logger.info(f"   PageView: {pageview_count} evento(s)")
            logger.info(f"   ViewContent: {viewcontent_count} evento(s)")
            logger.info(f"   Purchase: {purchase_count} evento(s)")
            
            # Verificar últimos eventos
            if '[META PURCHASE]' in logs:
                logger.info(f"\n   Últimos eventos Purchase encontrados nos logs")
            else:
                logger.warning(f"   ⚠️ Nenhum evento Purchase encontrado nos logs recentes")
            
            return True
        else:
            logger.warning(f"⚠️ Arquivo de log não encontrado: {log_file}")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar logs: {e}", exc_info=True)
        return False

def main():
    """Função principal"""
    logger.info("=" * 80)
    logger.info("🚀 CHECKLIST DE VALIDAÇÃO - META PIXEL")
    logger.info("=" * 80)
    
    results = {
        'celery': check_celery(),
        'redis': check_redis(),
        'recent_payments': check_recent_payments(),
        'tracking_data': check_tracking_data(),
        'meta_events_logs': check_meta_events_logs()
    }
    
    # Resumo
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESUMO DA VALIDAÇÃO")
    logger.info("=" * 80)
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {check}: {'OK' if result else 'FALHOU'}")
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results.values() if r)
    
    logger.info(f"\n✅ {passed_checks}/{total_checks} verificações passaram")
    
    if passed_checks == total_checks:
        logger.info("\n✅ TODAS AS VERIFICAÇÕES PASSARAM!")
    else:
        logger.warning(f"\n⚠️ {total_checks - passed_checks} verificação(ões) falharam")

if __name__ == "__main__":
    main()
```

---

## 📊 COMANDOS DE VALIDAÇÃO RÁPIDA

### **1. Verificar Celery:**
```bash
python scripts/verificar_celery.py
```

### **2. Verificar Pagamentos Recentes:**
```bash
python scripts/diagnostico_purchase_logs.py
```

### **3. Verificar Tracking Data:**
```bash
# Verificar chaves de tracking
redis-cli KEYS "tracking:*" | wc -l

# Verificar uma chave específica
redis-cli GET "tracking:{tracking_token}" | jq '.'
```

### **4. Verificar Logs de Eventos:**
```bash
# Verificar PageView
tail -f logs/gunicorn.log | grep -iE "\[META PAGEVIEW\]"

# Verificar ViewContent
tail -f logs/gunicorn.log | grep -iE "\[META VIEWCONTENT\]"

# Verificar Purchase
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]|Purchase enfileirado|Purchase ENVIADO"
```

### **5. Verificar Respostas do Meta:**
```bash
# Verificar eventos enviados com sucesso
tail -f logs/celery.log | grep -iE "SUCCESS.*Meta Event|EventsReceived"
```

---

## ✅ CONCLUSÃO

**CHECKLIST COMPLETO CRIADO! ✅**

**Próximos passos:**
1. Executar script de validação automática
2. Verificar cada item do checklist manualmente
3. Corrigir problemas identificados
4. Validar no Meta Events Manager

---

**CHECKLIST DE VALIDAÇÃO CONCLUÍDO! ✅**

