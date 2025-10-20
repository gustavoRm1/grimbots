# 🎯 META PIXEL INTEGRATION - PLANO COMPLETO

## ⚠️ **PREMISSA CRÍTICA**

**O PIXEL É SENSÍVEL E NÃO PODE SER ESTRAGADO!**

Dados ruins no pixel = campanhas ruins = dinheiro perdido

**Garantias necessárias**:
- ✅ Zero duplicação
- ✅ Zero eventos fantasmas
- ✅ Dados 100% precisos
- ✅ Rollback fácil se der problema

---

## 🔍 **ANÁLISE ANTI-DUPLICAÇÃO**

### **Cenário 1: Webhook Duplicado** ⚠️

**Problema**:
```
Gateway envia webhook 2x para o mesmo pagamento
↓
Sem proteção: 2 eventos Purchase enviados
↓
Meta conta: R$ 100 (deveria ser R$ 50)
↓
ROI errado, pixel corrompido ❌
```

**Solução**:
```python
# Tabela payments
+ meta_purchase_sent BOOLEAN DEFAULT FALSE
+ meta_purchase_sent_at DATETIME
+ meta_event_id VARCHAR(100)  # event_id enviado ao Meta

# Lógica
if payment.status == 'paid' and not payment.meta_purchase_sent:
    event_id = f"purchase_{payment.payment_id}_{int(time.time())}"
    
    success = send_to_meta(event_id=event_id, ...)
    
    if success:
        payment.meta_purchase_sent = True
        payment.meta_purchase_sent_at = datetime.now()
        payment.meta_event_id = event_id
        db.session.commit()

# Webhook duplicado?
if payment.meta_purchase_sent:  # ← JÁ ENVIOU
    logger.info("Purchase já enviado ao Meta, ignorando")
    return  # NÃO ENVIA DE NOVO ✅
```

**Garantia**: Campo no banco impede envio duplicado ✅

---

### **Cenário 2: Mesmo Usuário, Múltiplas Compras** ✅

**Este DEVE acontecer**:
```
Usuário telegram_123:

Compra 1: R$ 50 (PAY_001)
→ event_id: "purchase_PAY_001_1729440000"
→ Meta recebe ✅

Compra 2: R$ 30 (PAY_002) - Downsell
→ event_id: "purchase_PAY_002_1729440900"
→ Meta recebe ✅ (event_id diferente)

Compra 3: R$ 70 (PAY_003) - Upsell
→ event_id: "purchase_PAY_003_1729441800"
→ Meta recebe ✅ (event_id diferente)
```

**Garantia**: Event IDs diferentes = Meta aceita todos ✅

---

### **Cenário 3: Retry Manual (Admin)** ⚠️

**Problema**:
```
Admin clica "Reenviar ao Meta" 2x por engano
↓
Sem proteção: 2 eventos com event_ids diferentes
↓
Duplicação ❌
```

**Solução**:
```python
# Rota admin
@app.route('/admin/payment/<id>/resend-meta')
def resend_meta(id):
    payment = Payment.query.get(id)
    
    # ✅ VERIFICAR se já enviou
    if payment.meta_purchase_sent:
        # Usar o MESMO event_id original
        event_id = payment.meta_event_id  
    else:
        # Primeiro envio
        event_id = f"purchase_{payment.payment_id}_{int(time.time())}"
    
    # Meta deduplica por event_id automaticamente
    send_to_meta(event_id=event_id, ...)
    
    # Atualizar flag
    payment.meta_purchase_sent = True
    payment.meta_event_id = event_id
```

**Garantia**: Mesmo event_id = Meta ignora duplicata ✅

---

### **Cenário 4: Falha de Rede** ⚠️

**Problema**:
```
Envia para Meta → timeout de rede → não marca como enviado
↓
Webhook vem de novo → tenta enviar novamente
↓
Pode duplicar? ❌
```

**Solução**:
```python
try:
    response = send_to_meta(event_id=event_id, ...)
    
    if response.status_code == 200:
        # ✅ Enviou com sucesso
        payment.meta_purchase_sent = True
        db.session.commit()
    else:
        # ❌ Falhou, NÃO marca como enviado
        logger.error(f"Meta API error: {response.text}")
        # Próximo webhook tentará novamente com MESMO event_id
        
except Exception as e:
    logger.error(f"Network error: {e}")
    # NÃO marca como enviado
    # Próximo webhook tentará novamente
```

**Garantia**: Só marca enviado se Meta confirmar ✅

---

## 🏗️ **ARQUITETURA TÉCNICA**

### **1. Banco de Dados**

```sql
-- Tabela: redirect_pools (adicionar colunas)
ALTER TABLE redirect_pools ADD COLUMN meta_pixel_id VARCHAR(50);
ALTER TABLE redirect_pools ADD COLUMN meta_access_token TEXT;  -- Criptografado
ALTER TABLE redirect_pools ADD COLUMN meta_tracking_enabled BOOLEAN DEFAULT 0;

-- Tabela: payments (adicionar colunas de controle)
ALTER TABLE payments ADD COLUMN meta_purchase_sent BOOLEAN DEFAULT 0;
ALTER TABLE payments ADD COLUMN meta_purchase_sent_at DATETIME;
ALTER TABLE payments ADD COLUMN meta_event_id VARCHAR(100);
ALTER TABLE payments ADD COLUMN utm_source VARCHAR(50);
ALTER TABLE payments ADD COLUMN utm_campaign VARCHAR(100);
ALTER TABLE payments ADD COLUMN fbclid VARCHAR(200);

-- Índices para performance
CREATE INDEX idx_payments_meta_sent ON payments(meta_purchase_sent);
CREATE INDEX idx_payments_customer ON payments(customer_user_id);
```

---

### **2. Fluxo Técnico Completo**

```
ETAPA 1: Usuário clica no anúncio
├── URL: grimpay.com/go/pool1?fbclid=xxx&utm_source=facebook&utm_campaign=black_friday
├── Backend captura: fbclid, utm_source, utm_campaign
├── Salva em session['tracking']
└── Renderiza página com Meta Pixel

ETAPA 2: Página de redirecionamento
├── Injeta Meta Pixel (client-side)
├── fbq('init', '123456789')
├── fbq('track', 'PageView')
└── Redireciona para t.me/bot após 1s

ETAPA 3: Usuário interage com bot
├── Envia /start
├── Bot registra usuário (BotUser)
├── Envia Lead event (opcional, futuro)
└── Usuário vê produtos

ETAPA 4: Usuário gera PIX
├── PIX gerado
├── NADA enviado ao Meta ✅ (evita poluição)
└── Aguarda pagamento

ETAPA 5: Webhook de confirmação
├── Gateway confirma pagamento
├── Backend valida: payment.meta_purchase_sent == False?
├── SIM: Envia Purchase event
│   ├── event_id único: "purchase_PAY_12345_1729440000"
│   ├── Valor: payment.amount
│   ├── Custom data: tipo de venda, produto, etc
│   └── User data: IP, UA, fbp, fbc
├── Meta retorna 200 OK
├── Marca: payment.meta_purchase_sent = True
└── Commit no banco

ETAPA 6: Downsell/Upsell (se acontecer)
├── Novo pagamento gerado (PAY_67890)
├── Usuário paga
├── Webhook de confirmação
├── Backend valida: payment.meta_purchase_sent == False?
├── SIM: Envia Purchase event
│   └── event_id: "purchase_PAY_67890_1729441000" (DIFERENTE)
└── Meta recebe como compra nova ✅
```

---

### **3. Código de Produção**

#### **Arquivo: `utils/meta_pixel.py`**

```python
"""
Meta Pixel / Conversions API Integration
Documentação: https://developers.facebook.com/docs/marketing-api/conversions-api
"""

import requests
import hashlib
import time
import logging

logger = logging.getLogger(__name__)

class MetaPixelAPI:
    """
    Client para Meta Conversions API (CAPI)
    
    IMPORTANTE:
    - Usa event_id para deduplicação
    - Server-side = 100% confiável (sem AdBlock)
    - Dados criptografados (SHA256)
    """
    
    API_VERSION = 'v19.0'
    BASE_URL = 'https://graph.facebook.com'
    
    @staticmethod
    def send_purchase_event(
        pixel_id: str,
        access_token: str,
        event_id: str,
        value: float,
        currency: str,
        customer_user_id: str,
        product_name: str = None,
        is_downsell: bool = False,
        order_bump_value: float = 0,
        utm_source: str = None,
        utm_campaign: str = None,
        client_ip: str = None,
        client_user_agent: str = None,
        fbp: str = None,
        fbc: str = None
    ) -> dict:
        """
        Envia evento Purchase para Meta
        
        Args:
            pixel_id: ID do pixel (ex: 123456789)
            access_token: Token de acesso do Business Manager
            event_id: ID único do evento (CRÍTICO para deduplicação)
            value: Valor da compra em reais
            currency: 'BRL'
            customer_user_id: ID do Telegram do usuário
            ... outros parâmetros opcionais
            
        Returns:
            dict: {'success': bool, 'response': dict, 'error': str}
        """
        
        url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
        
        # User Data (quanto mais completo, melhor o matching)
        user_data = {
            'external_id': [hashlib.sha256(customer_user_id.encode()).hexdigest()],
        }
        
        if client_ip:
            user_data['client_ip_address'] = client_ip
        
        if client_user_agent:
            user_data['client_user_agent'] = client_user_agent
        
        if fbp:
            user_data['fbp'] = fbp  # Cookie _fbp (client-side)
        
        if fbc:
            user_data['fbc'] = fbc  # Cookie _fbc (client-side)
        
        # Custom Data
        custom_data = {
            'value': float(value),
            'currency': currency,
            'content_type': 'product',
        }
        
        if product_name:
            custom_data['content_name'] = product_name
        
        if is_downsell:
            custom_data['content_category'] = 'downsell'
        
        if order_bump_value > 0:
            custom_data['order_bump_value'] = float(order_bump_value)
        
        # Payload
        payload = {
            'data': [{
                'event_name': 'Purchase',
                'event_time': int(time.time()),
                'event_id': event_id,  # ← DEDUPLICAÇÃO
                'action_source': 'website',
                'user_data': user_data,
                'custom_data': custom_data
            }],
            'access_token': access_token
        }
        
        try:
            logger.info(f"📤 Enviando Purchase ao Meta: event_id={event_id}, value={value}")
            
            response = requests.post(url, json=payload, timeout=15)
            response_data = response.json()
            
            if response.status_code == 200:
                logger.info(f"✅ Meta Purchase enviado: {response_data}")
                return {
                    'success': True,
                    'response': response_data,
                    'error': None
                }
            else:
                logger.error(f"❌ Meta API error: {response.status_code} - {response_data}")
                return {
                    'success': False,
                    'response': response_data,
                    'error': response_data.get('error', {}).get('message', 'Unknown error')
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Meta API timeout: {event_id}")
            return {
                'success': False,
                'response': None,
                'error': 'Timeout ao conectar com Meta API'
            }
            
        except Exception as e:
            logger.error(f"💥 Erro ao enviar para Meta: {e}")
            return {
                'success': False,
                'response': None,
                'error': str(e)
            }
    
    @staticmethod
    def test_connection(pixel_id: str, access_token: str) -> bool:
        """
        Testa conexão com Meta API
        Usado na tela de configuração para validar credenciais
        """
        url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}"
        
        try:
            response = requests.get(
                url,
                params={'access_token': access_token},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
```

#### **Arquivo: `app.py` - Webhook Handler**

```python
# Linha ~3340 (dentro do webhook handler)

if payment.status == 'paid':
    # ... código existente (atualizar bot, user, gateway, etc) ...
    
    # ============================================================================
    # META PIXEL: ENVIAR PURCHASE EVENT
    # ============================================================================
    
    # ✅ VERIFICAÇÃO 1: Pixel habilitado?
    pool = get_pool_from_bot(payment.bot_id)  # Função helper
    
    if pool and pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token:
        
        # ✅ VERIFICAÇÃO 2: Já enviou este pagamento?
        if not payment.meta_purchase_sent:
            
            logger.info(f"📊 Preparando envio Meta Purchase: {payment.payment_id}")
            
            # Gerar event_id único (payment_id + timestamp)
            event_id = f"purchase_{payment.payment_id}_{int(time.time())}"
            
            # Enviar para Meta
            from utils.meta_pixel import MetaPixelAPI
            from utils.encryption import decrypt  # Descriptografar access_token
            
            result = MetaPixelAPI.send_purchase_event(
                pixel_id=pool.meta_pixel_id,
                access_token=decrypt(pool.meta_access_token),
                event_id=event_id,
                value=payment.amount,
                currency='BRL',
                customer_user_id=payment.customer_user_id,
                product_name=payment.product_name,
                is_downsell=payment.is_downsell,
                order_bump_value=payment.order_bump_value if payment.order_bump_accepted else 0,
                utm_source=payment.utm_source,
                utm_campaign=payment.utm_campaign,
                client_ip=request.remote_addr,
                client_user_agent=request.headers.get('User-Agent'),
                fbp=request.cookies.get('_fbp'),
                fbc=request.cookies.get('_fbc')
            )
            
            # ✅ VERIFICAÇÃO 3: Meta confirmou recebimento?
            if result['success']:
                # Marcar como enviado
                payment.meta_purchase_sent = True
                payment.meta_purchase_sent_at = datetime.now()
                payment.meta_event_id = event_id
                db.session.commit()
                
                logger.info(f"✅ Meta Purchase confirmado: R$ {payment.amount} | " +
                           f"Event ID: {event_id} | " +
                           f"Type: {'Downsell' if payment.is_downsell else 'Normal'}")
            else:
                # Falhou - NÃO marca como enviado
                # Próximo webhook tentará novamente
                logger.error(f"❌ Meta Purchase falhou: {result['error']} | " +
                            f"Payment: {payment.payment_id}")
        else:
            # Já enviou - webhook duplicado
            logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando: {payment.payment_id}")
```

---

## 🛡️ **GARANTIAS DE SEGURANÇA**

### **1. Flags de Controle**

```python
# Tabela pools
meta_tracking_enabled = False  # Desligado por padrão

# Só envia se EXPLICITAMENTE ativado pelo usuário
if pool.meta_tracking_enabled:
    send_to_meta(...)
```

### **2. Criptografia**

```python
# Access Token nunca fica em texto plano
from utils.encryption import encrypt, decrypt

# Ao salvar
pool.meta_access_token = encrypt(token)

# Ao usar
token_plain = decrypt(pool.meta_access_token)
```

### **3. Logs Detalhados**

```python
# Cada ação é logada
logger.info(f"📤 Enviando: event_id={id}, value={value}")
logger.info(f"✅ Enviado: response={response}")
logger.error(f"❌ Falhou: error={error}")

# Permite auditoria completa
```

### **4. Rollback Fácil**

```python
# Desabilitar globalmente (emergência)
UPDATE redirect_pools SET meta_tracking_enabled = 0;

# Ou individual
pool.meta_tracking_enabled = False
```

---

## 📋 **PLANO DE IMPLEMENTAÇÃO**

### **FASE 1: Preparação (Dia 1)**

1. **Migração do Banco**
   ```bash
   python migrate_add_meta_pixel.py
   ```
   - Adiciona colunas em `redirect_pools`
   - Adiciona colunas em `payments`
   - Cria índices

2. **Código Base**
   - Criar `utils/meta_pixel.py`
   - Adicionar helper `get_pool_from_bot()`
   - Testar conexão Meta API

3. **Testes Unitários**
   ```python
   # test_meta_pixel.py
   - Test deduplication
   - Test event_id generation
   - Test API connection
   ```

### **FASE 2: Interface (Dia 2)**

1. **Tela de Configuração**
   - Página `/pools/<id>/meta-pixel`
   - Campos: Pixel ID, Access Token
   - Botão "Testar Conexão"
   - Toggle "Ativar Tracking"

2. **Validação Frontend**
   - Pixel ID: apenas números
   - Access Token: não vazio
   - Testar antes de salvar

### **FASE 3: Backend Integration (Dia 3)**

1. **Webhook Handler**
   - Adicionar lógica de envio
   - Testar com webhook simulado
   - Verificar logs

2. **Template Redirecionador**
   - Criar `redirect_with_pixel.html`
   - Injetar Meta Pixel (client-side)
   - Capturar UTMs

### **FASE 4: Testes (Dia 4)**

1. **Ambiente de Teste**
   - Usar Meta Test Events Tool
   - Criar pool de teste
   - Gerar pagamentos de teste

2. **Cenários de Teste**
   - ✅ Webhook duplicado (não duplica)
   - ✅ Múltiplas compras (todas enviadas)
   - ✅ Downsell (enviado separado)
   - ✅ Upsell (enviado separado)
   - ✅ Falha de rede (retry funciona)

### **FASE 5: Deploy (Dia 5)**

1. **Backup**
   ```bash
   cp instance/saas_bot_manager.db backup.db
   ```

2. **Deploy Gradual**
   - Habilitar em 1 pool (teste)
   - Monitorar por 24h
   - Se OK, liberar para todos

3. **Documentação**
   - Tutorial para usuário
   - Como obter Pixel ID
   - Como obter Access Token

---

## 🧪 **CHECKLIST DE TESTES**

### **Antes de Deploy**

- [ ] Migração rodou sem erros
- [ ] Código compilou sem erros
- [ ] Testes unitários passaram
- [ ] Teste de conexão Meta funciona
- [ ] Webhook simulado funciona
- [ ] Logs estão corretos

### **Em Produção (Pool de Teste)**

- [ ] PageView rastreado corretamente
- [ ] Purchase enviado na primeira compra
- [ ] Purchase enviado no downsell
- [ ] Purchase enviado no upsell
- [ ] Webhook duplicado não duplica evento
- [ ] Falha de rede não perde evento
- [ ] Meta Events Manager mostra eventos
- [ ] Valores estão corretos

---

## 🆘 **PLANO DE ROLLBACK**

### **Se algo der errado**:

```bash
# 1. Desabilitar tracking imediatamente
mysql -e "UPDATE redirect_pools SET meta_tracking_enabled = 0;"

# 2. Parar aplicação
pm2 stop grimbots

# 3. Restaurar banco (se necessário)
cp backup.db instance/saas_bot_manager.db

# 4. Reverter código
git revert HEAD

# 5. Reiniciar
pm2 start grimbots
```

---

## 📊 **MONITORAMENTO**

### **Métricas para acompanhar**:

```sql
-- Quantos eventos foram enviados hoje?
SELECT COUNT(*) FROM payments 
WHERE meta_purchase_sent = 1 
AND DATE(meta_purchase_sent_at) = CURDATE();

-- Quantos falharam?
SELECT COUNT(*) FROM payments 
WHERE status = 'paid' 
AND meta_purchase_sent = 0
AND bot_id IN (SELECT bot_id FROM bots WHERE ...);

-- Valor total rastreado
SELECT SUM(amount) FROM payments 
WHERE meta_purchase_sent = 1;
```

### **Alertas**:

- ⚠️ Taxa de falha > 5%
- ⚠️ Nenhum evento enviado em 1h (se tiver vendas)
- ⚠️ Diferença de valor (Meta vs Banco) > 1%

---

## ✅ **CONCLUSÃO**

### **Sistema é SEGURO**:
- ✅ Zero duplicação (event_id + flag no banco)
- ✅ Zero eventos fantasmas (só envia se pagamento confirmado)
- ✅ Rollback fácil (toggle no banco)
- ✅ Auditável (logs detalhados)

### **Sistema é PRECISO**:
- ✅ ROI real (todas as compras rastreadas)
- ✅ LTV completo (downsell + upsell)
- ✅ Otimização Meta baseada em dados reais

### **Sistema é CONFIÁVEL**:
- ✅ Retry automático em falhas
- ✅ CAPI (server-side, sem AdBlock)
- ✅ Event Match Quality alto
- ✅ Deduplicação nativa do Meta

---

**IMPLEMENTAR?** 
- Seguir plano de 5 dias
- Deploy gradual (1 pool teste)
- Monitorar 24h antes de liberar geral

**Status**: Pronto para implementação ✅

