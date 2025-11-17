# 🔍 GUIA COMPLETO DE VERIFICAÇÃO - TRACKING DE VENDAS

**Data:** 2025-11-17  
**Objetivo:** Verificar se o sistema está trackeando vendas corretamente no Meta Pixel

---

## 📋 CHECKLIST DE VERIFICAÇÃO

### ✅ **1. VERIFICAR SE PIXEL ESTÁ DISPARANDO (PageView)**

**Onde verificar:**
- Logs do Gunicorn: `tail -f logs/gunicorn.log | grep "META PAGEVIEW"`
- Redis: Verificar se `tracking:{token}` existe
- Meta Events Manager: Verificar se PageView aparece

**Comandos:**
```bash
# Ver logs de PageView recentes
tail -n 100 logs/gunicorn.log | grep "META PAGEVIEW"

# Verificar tracking tokens no Redis
redis-cli KEYS "tracking:*" | head -20
```

**O que procurar:**
- ✅ Logs com `[META PAGEVIEW]` e `event_id`
- ✅ `tracking_token` (32 chars) salvo no Redis
- ✅ `fbp`, `fbc`, `fbclid`, `pageview_event_id` presentes

---

### ✅ **2. VERIFICAR SE VIEWCONTENT ESTÁ DISPARANDO**

**Onde verificar:**
- Logs do Gunicorn: `tail -f logs/gunicorn.log | grep "META VIEWCONTENT"`
- Meta Events Manager: Verificar se ViewContent aparece

**Comandos:**
```bash
# Ver logs de ViewContent recentes
tail -n 100 logs/gunicorn.log | grep "META VIEWCONTENT"
```

**O que procurar:**
- ✅ Logs com `[META VIEWCONTENT]` e `event_id`
- ✅ `content_ids` e `content_type` presentes

---

### ✅ **3. VERIFICAR SE PURCHASE ESTÁ DISPARANDO**

**Onde verificar:**
- Logs do Gunicorn: `tail -f logs/gunicorn.log | grep "META PURCHASE"`
- Meta Events Manager: Verificar se Purchase aparece
- Redis: Verificar se tracking data foi recuperado

**Comandos:**
```bash
# Ver logs de Purchase recentes
tail -n 100 logs/gunicorn.log | grep "META PURCHASE"

# Verificar último Purchase enviado
tail -n 200 logs/gunicorn.log | grep -A 20 "META PURCHASE" | tail -30
```

**O que procurar:**
- ✅ Logs com `[META PURCHASE]` e `event_id`
- ✅ `pageview_event_id` sendo reutilizado (deduplicação)
- ✅ `fbp`, `fbc`, `fbclid` presentes
- ✅ `user_data` completo (email, phone, ip, user_agent)

---

### ✅ **4. VERIFICAR TRACKING_TOKEN NO PAYMENT**

**Onde verificar:**
- Banco de dados: Tabela `payments`
- Logs: Verificar se `tracking_token` foi salvo

**Comandos:**
```bash
# Verificar últimos payments com tracking_token
python3 -c "
from app import app
from models import Payment, db
with app.app_context():
    payments = Payment.query.filter(Payment.tracking_token.isnot(None)).order_by(Payment.id.desc()).limit(10).all()
    for p in payments:
        print(f'Payment {p.id}: tracking_token={p.tracking_token[:20] if p.tracking_token else None}... status={p.status}')
"
```

**O que procurar:**
- ✅ Payments com `tracking_token` (32 chars, UUID)
- ✅ `tracking_token` NÃO começa com `tracking_` (não é gerado)
- ✅ Payments `paid` têm `tracking_token`

---

### ✅ **5. VERIFICAR TRACKING DATA NO REDIS**

**Onde verificar:**
- Redis: Chaves `tracking:{token}`

**Comandos:**
```bash
# Verificar tracking data de um token específico
redis-cli GET "tracking:SEU_TOKEN_AQUI"

# Verificar todos os tracking tokens recentes
redis-cli KEYS "tracking:*" | head -10 | xargs -I {} redis-cli GET {}
```

**O que procurar:**
- ✅ `fbp`, `fbc`, `fbclid` presentes
- ✅ `pageview_event_id` presente
- ✅ `client_ip`, `client_user_agent` presentes
- ✅ TTL ainda válido (não expirado)

---

### ✅ **6. VERIFICAR WEBHOOKS RECEBIDOS**

**Onde verificar:**
- Logs do Celery: `tail -f logs/celery.log | grep "WEBHOOK"`
- Banco de dados: Verificar se Payments foram atualizados

**Comandos:**
```bash
# Ver logs de webhooks recentes
tail -n 100 logs/celery.log | grep "WEBHOOK"

# Verificar payments atualizados recentemente
python3 -c "
from app import app
from models import Payment, db
from datetime import datetime, timedelta
with app.app_context():
    recent = Payment.query.filter(Payment.updated_at >= datetime.now() - timedelta(hours=1)).order_by(Payment.id.desc()).limit(10).all()
    for p in recent:
        print(f'Payment {p.id}: status={p.status} updated_at={p.updated_at}')
"
```

**O que procurar:**
- ✅ Webhooks sendo recebidos e processados
- ✅ Payments sendo atualizados de `pending` para `paid`
- ✅ Purchase event sendo disparado após webhook `paid`

---

### ✅ **7. VERIFICAR EVENTOS NO META EVENTS MANAGER**

**Onde verificar:**
- Meta Events Manager: https://business.facebook.com/events_manager2

**Passos:**
1. Acessar Meta Events Manager
2. Selecionar o Pixel ID correto
3. Verificar eventos recentes:
   - PageView (deve aparecer imediatamente após redirect)
   - ViewContent (deve aparecer após /start)
   - Purchase (deve aparecer após pagamento confirmado)

**O que procurar:**
- ✅ PageView aparece com `event_id` único
- ✅ ViewContent aparece com `content_ids`
- ✅ Purchase aparece com `event_id` = `pageview_event_id` (deduplicação)
- ✅ Match Quality: 7/10 ou superior
- ✅ `fbp`, `fbc` presentes nos eventos

---

### ✅ **8. VERIFICAR VENDAS ATRIBUÍDAS NO META ADS MANAGER**

**Onde verificar:**
- Meta Ads Manager: https://business.facebook.com/adsmanager

**Passos:**
1. Acessar Meta Ads Manager
2. Selecionar a campanha
3. Verificar "Vendas" ou "Conversões"
4. Comparar com vendas reais do sistema

**O que procurar:**
- ✅ Vendas aparecem no Ads Manager
- ✅ Número de vendas corresponde ao sistema
- ✅ ROI calculado corretamente
- ✅ Custo por venda (CPA) calculado

---

## 🔧 SCRIPT DE VERIFICAÇÃO AUTOMÁTICA

Crie o arquivo `scripts/verificar_tracking_vendas.py`:

```python
#!/usr/bin/env python3
"""
Script de Verificação Completa - Tracking de Vendas
Verifica se o sistema está trackeando vendas corretamente
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import Payment, BotUser, db
from datetime import datetime, timedelta
import redis
import json

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def verificar_tracking_vendas():
    """Verificação completa do tracking de vendas"""
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO COMPLETA - TRACKING DE VENDAS")
    print("=" * 80)
    print()
    
    with app.app_context():
        # 1. VERIFICAR PAYMENTS RECENTES
        print("📊 1. VERIFICANDO PAYMENTS RECENTES (últimas 24h)")
        print("-" * 80)
        
        recent_payments = Payment.query.filter(
            Payment.created_at >= datetime.now() - timedelta(hours=24)
        ).order_by(Payment.id.desc()).limit(20).all()
        
        print(f"   Total de payments nas últimas 24h: {len(recent_payments)}")
        
        payments_com_tracking = 0
        payments_paid = 0
        payments_paid_com_tracking = 0
        
        for payment in recent_payments:
            if payment.tracking_token:
                payments_com_tracking += 1
                if payment.status == 'paid':
                    payments_paid_com_tracking += 1
            
            if payment.status == 'paid':
                payments_paid += 1
        
        print(f"   ✅ Payments com tracking_token: {payments_com_tracking}/{len(recent_payments)}")
        print(f"   ✅ Payments pagos: {payments_paid}/{len(recent_payments)}")
        print(f"   ✅ Payments pagos COM tracking: {payments_paid_com_tracking}/{payments_paid}")
        
        if payments_paid > 0 and payments_paid_com_tracking < payments_paid:
            print(f"   ⚠️  ATENÇÃO: {payments_paid - payments_paid_com_tracking} vendas pagas SEM tracking_token!")
        
        print()
        
        # 2. VERIFICAR TRACKING TOKENS NO REDIS
        print("📊 2. VERIFICANDO TRACKING TOKENS NO REDIS")
        print("-" * 80)
        
        tracking_keys = redis_client.keys("tracking:*")
        tracking_tokens = [k for k in tracking_keys if not k.startswith("tracking:fbclid:") and not k.startswith("tracking:chat:") and not k.startswith("tracking:last_token:")]
        
        print(f"   Total de tracking tokens no Redis: {len(tracking_tokens)}")
        
        if tracking_tokens:
            # Verificar alguns tokens
            sample_tokens = tracking_tokens[:5]
            tokens_com_dados_completos = 0
            
            for key in sample_tokens:
                data = redis_client.get(key)
                if data:
                    try:
                        payload = json.loads(data)
                        has_fbp = bool(payload.get('fbp'))
                        has_fbc = bool(payload.get('fbc'))
                        has_fbclid = bool(payload.get('fbclid'))
                        has_pageview_event_id = bool(payload.get('pageview_event_id'))
                        has_client_ip = bool(payload.get('client_ip'))
                        has_client_user_agent = bool(payload.get('client_user_agent'))
                        
                        if has_fbp and has_fbclid and has_pageview_event_id and has_client_ip:
                            tokens_com_dados_completos += 1
                    except:
                        pass
            
            print(f"   ✅ Tokens com dados completos (amostra): {tokens_com_dados_completos}/{len(sample_tokens)}")
        else:
            print("   ⚠️  NENHUM tracking token encontrado no Redis!")
        
        print()
        
        # 3. VERIFICAR ÚLTIMOS PAYMENTS PAGOS
        print("📊 3. VERIFICANDO ÚLTIMOS PAYMENTS PAGOS")
        print("-" * 80)
        
        paid_payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.updated_at >= datetime.now() - timedelta(hours=24)
        ).order_by(Payment.id.desc()).limit(10).all()
        
        print(f"   Total de payments pagos nas últimas 24h: {len(paid_payments)}")
        print()
        
        for payment in paid_payments:
            tracking_status = "✅" if payment.tracking_token else "❌"
            tracking_preview = payment.tracking_token[:20] + "..." if payment.tracking_token else "N/A"
            
            # Verificar se tracking data existe no Redis
            redis_status = "❌"
            if payment.tracking_token:
                redis_data = redis_client.get(f"tracking:{payment.tracking_token}")
                if redis_data:
                    redis_status = "✅"
            
            print(f"   Payment {payment.id}:")
            print(f"      Status: {payment.status}")
            print(f"      Tracking Token: {tracking_status} {tracking_preview}")
            print(f"      Redis Data: {redis_status}")
            print(f"      Valor: R$ {payment.amount:.2f}")
            print(f"      Atualizado: {payment.updated_at}")
            print()
        
        # 4. VERIFICAR LOGS RECENTES
        print("📊 4. VERIFICANDO LOGS RECENTES")
        print("-" * 80)
        print("   Execute os seguintes comandos para verificar logs:")
        print()
        print("   # PageView events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META PAGEVIEW'")
        print()
        print("   # ViewContent events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META VIEWCONTENT'")
        print()
        print("   # Purchase events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META PURCHASE'")
        print()
        print("   # Webhooks:")
        print("   tail -n 100 logs/celery.log | grep 'WEBHOOK'")
        print()
        
        # 5. RESUMO FINAL
        print("=" * 80)
        print("📋 RESUMO FINAL")
        print("=" * 80)
        print()
        
        if payments_paid > 0:
            tracking_percentage = (payments_paid_com_tracking / payments_paid) * 100
            print(f"   ✅ Taxa de tracking: {tracking_percentage:.1f}% ({payments_paid_com_tracking}/{payments_paid})")
            
            if tracking_percentage < 90:
                print(f"   ⚠️  ATENÇÃO: Taxa de tracking abaixo de 90%!")
            else:
                print(f"   ✅ Taxa de tracking OK!")
        else:
            print("   ⚠️  Nenhuma venda paga nas últimas 24h para verificar")
        
        print()
        print("=" * 80)
        print("✅ VERIFICAÇÃO CONCLUÍDA")
        print("=" * 80)

if __name__ == "__main__":
    verificar_tracking_vendas()
```

---

## 🚀 COMANDOS RÁPIDOS PARA EXECUTAR

### **Verificar Tracking de Uma Venda Específica:**

```bash
# 1. Encontrar o Payment ID da venda
python3 -c "
from app import app
from models import Payment, db
with app.app_context():
    payment = Payment.query.filter_by(id=SEU_PAYMENT_ID).first()
    if payment:
        print(f'Payment {payment.id}:')
        print(f'  Status: {payment.status}')
        print(f'  Tracking Token: {payment.tracking_token}')
        print(f'  Gateway: {payment.gateway_type}')
        print(f'  Valor: R$ {payment.amount:.2f}')
"

# 2. Verificar tracking data no Redis
redis-cli GET "tracking:SEU_TRACKING_TOKEN_AQUI"

# 3. Verificar logs do Purchase event
grep "META PURCHASE.*payment_id.*SEU_PAYMENT_ID" logs/gunicorn.log | tail -5
```

### **Verificar Últimas Vendas:**

```bash
# Executar script de verificação
python3 scripts/verificar_tracking_vendas.py
```

### **Monitorar Logs em Tempo Real:**

```bash
# PageView + Purchase
tail -f logs/gunicorn.log | grep -E "META PAGEVIEW|META PURCHASE"

# Webhooks
tail -f logs/celery.log | grep "WEBHOOK"
```

---

## ⚠️ PROBLEMAS COMUNS E SOLUÇÕES

### **Problema 1: Purchase não está sendo enviado**

**Sintomas:**
- Payment está `paid` mas não há log de Purchase
- Meta Events Manager não mostra Purchase

**Verificações:**
1. Verificar se webhook foi recebido: `grep "WEBHOOK.*paid" logs/celery.log`
2. Verificar se `tracking_token` existe no Payment
3. Verificar se tracking data existe no Redis

**Solução:**
- Verificar logs de erro: `grep "ERROR.*PURCHASE" logs/gunicorn.log`
- Verificar se Celery está rodando: `ps aux | grep celery`

---

### **Problema 2: Tracking Token está vazio**

**Sintomas:**
- Payment tem `tracking_token = None`
- Purchase não consegue recuperar dados

**Verificações:**
1. Verificar se redirect foi feito: `grep "public_redirect" logs/gunicorn.log`
2. Verificar se `bot_user.tracking_session_id` está preenchido
3. Verificar se Redis está funcionando: `redis-cli PING`

**Solução:**
- Verificar se `/go/{slug}` está sendo acessado
- Verificar se cookies `_fbp` e `_fbc` estão sendo capturados

---

### **Problema 3: Purchase não faz match com PageView**

**Sintomas:**
- PageView e Purchase aparecem separados no Meta Events Manager
- Match Quality baixo (< 7/10)

**Verificações:**
1. Verificar se `pageview_event_id` está sendo reutilizado
2. Verificar se `fbp` e `fbc` são os mesmos em PageView e Purchase
3. Verificar se `external_id` (fbclid) é o mesmo

**Solução:**
- Verificar logs: `grep "pageview_event_id" logs/gunicorn.log`
- Verificar se `tracking_token` é o mesmo do redirect

---

## 📊 DASHBOARD DE MONITORAMENTO

Para monitoramento contínuo, execute:

```bash
# Criar script de monitoramento
cat > scripts/monitorar_tracking.sh << 'EOF'
#!/bin/bash
while true; do
    clear
    echo "=== MONITORAMENTO TRACKING - $(date) ==="
    echo ""
    echo "📊 Últimas 5 vendas pagas:"
    python3 scripts/verificar_tracking_vendas.py | head -30
    echo ""
    echo "📊 Últimos eventos Purchase:"
    tail -n 5 logs/gunicorn.log | grep "META PURCHASE"
    echo ""
    sleep 30
done
EOF

chmod +x scripts/monitorar_tracking.sh
```

---

**GUIA DE VERIFICAÇÃO COMPLETO! ✅**

**Execute o script de verificação para uma análise completa do sistema.**

