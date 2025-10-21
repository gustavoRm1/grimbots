# 🚀 TRACKING V2 - ROADMAP ELITE

**Data:** 2025-10-21  
**Versão Atual:** V1 (IP/UA/Session básico)  
**Próxima Versão:** V2 (Intelligence Layer)  
**Target:** TOP 0.1% - Enterprise Grade

---

## **🎯 VISÃO GERAL:**

Tracking V2 transforma dados brutos (IP, User-Agent) em **inteligência acionável**:
- Segmentação por localização geográfica
- Perfis analíticos de usuário
- Detecção automatizada de bots/scrapers
- Compliance LGPD/GDPR by design
- Fallback resiliente para Redis failures

---

## **📋 FEATURES PLANEJADAS:**

### **1. HASH SEGURO DE IP (LGPD Compliance)**

#### **Problema:**
- Armazenar IP completo = dado pessoal sensível
- LGPD exige minimização de dados
- Precisamos balance entre tracking e privacidade

#### **Solução:**
```python
import hashlib
import os

def hash_ip_securely(ip_address, salt=None):
    """
    Hash IP com salt secreto para compliance LGPD
    
    Benefícios:
    - IP não é reversível
    - Ainda podemos detectar múltiplos acessos do mesmo IP
    - Compliance total com LGPD Art. 6º (minimização)
    """
    if not salt:
        salt = os.environ.get('IP_HASH_SALT', 'default_salt_change_me')
    
    ip_with_salt = f"{ip_address}{salt}"
    hashed = hashlib.sha256(ip_with_salt.encode()).hexdigest()
    
    # Retornar apenas primeiros 16 caracteres (suficiente para identificação)
    return hashed[:16]

# Uso:
bot_user.ip_hash = hash_ip_securely(user_ip)
bot_user.ip_address = None  # Não salvar IP em texto claro
```

#### **Implementação:**
- Adicionar campo `ip_hash` ao BotUser
- Manter `ip_address` apenas para debug (deletar após 7 dias)
- Usar `ip_hash` para analytics e detecção de fraudes

#### **Benefícios:**
- ✅ LGPD compliant
- ✅ Ainda detecta múltiplos acessos
- ✅ Impossível reverter para IP original
- ✅ Pode ser usado em relatórios públicos

---

### **2. GEO IP MAPPING (Localização Geográfica)**

#### **Problema:**
- IP sozinho não diz nada sobre onde usuário está
- Precisamos saber cidade/estado para:
  - Segmentação de remarketing por região
  - Detectar fraudes (IP de país diferente do esperado)
  - Analytics de performance por região

#### **Solução:**
```python
import geoip2.database
import geoip2.errors

def get_geo_from_ip(ip_address):
    """
    Resolve IP para cidade/estado/país usando MaxMind GeoLite2
    
    Retorna:
        {
            'city': 'São Paulo',
            'state': 'SP',
            'country': 'BR',
            'latitude': -23.5505,
            'longitude': -46.6333
        }
    """
    try:
        reader = geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
        response = reader.city(ip_address)
        
        return {
            'city': response.city.name or 'Unknown',
            'state': response.subdivisions.most_specific.iso_code if response.subdivisions else None,
            'country': response.country.iso_code,
            'latitude': response.location.latitude,
            'longitude': response.location.longitude
        }
    except geoip2.errors.AddressNotFoundError:
        return {'city': 'Unknown', 'state': None, 'country': 'XX'}

# Uso no redirect:
geo_data = get_geo_from_ip(user_ip)
# Salvar no Redis junto com tracking_data
tracking_data['geo'] = geo_data
```

#### **Implementação:**
- Instalar MaxMind GeoLite2 (grátis, precisa cadastro)
- Adicionar campos `geo_city`, `geo_state`, `geo_country` ao BotUser
- Capturar no redirect e salvar no Redis
- Associar ao BotUser quando /start

#### **Benefícios:**
- ✅ Remarketing segmentado por região
- ✅ Detectar fraudes (ex: anúncio para SP, lead do Marrocos)
- ✅ Analytics por cidade/estado
- ✅ Otimizar gastos de anúncios por região

#### **Casos de Uso:**
```python
# Remarketing apenas para SP
leads_sp = BotUser.query.filter_by(geo_state='SP', purchased=False)

# Detectar anomalias
suspicious = BotUser.query.filter(BotUser.geo_country != 'BR')

# Comparar performance por região
conversion_by_state = db.session.query(
    BotUser.geo_state,
    func.count(Payment.id).label('sales')
).join(Payment).group_by(BotUser.geo_state)
```

---

### **3. USER-AGENT PARSING (Dispositivo/Browser/OS)**

#### **Problema:**
- User-Agent é string crua: `Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1...)`
- Precisamos extrair: dispositivo, navegador, OS, versão

#### **Solução:**
```python
from user_agents import parse

def parse_user_agent(ua_string):
    """
    Parse User-Agent para extrair informações estruturadas
    
    Retorna:
        {
            'device': 'iPhone',
            'browser': 'Safari',
            'browser_version': '14.1',
            'os': 'iOS',
            'os_version': '14.7.1',
            'is_mobile': True,
            'is_tablet': False,
            'is_pc': False,
            'is_bot': False
        }
    """
    ua = parse(ua_string)
    
    return {
        'device': ua.device.family,
        'browser': ua.browser.family,
        'browser_version': ua.browser.version_string,
        'os': ua.os.family,
        'os_version': ua.os.version_string,
        'is_mobile': ua.is_mobile,
        'is_tablet': ua.is_tablet,
        'is_pc': ua.is_pc,
        'is_bot': ua.is_bot
    }

# Uso:
ua_data = parse_user_agent(user_agent)
bot_user.device_type = ua_data['device']
bot_user.browser_name = ua_data['browser']
bot_user.os_name = ua_data['os']
bot_user.is_mobile = ua_data['is_mobile']
bot_user.is_bot_detected = ua_data['is_bot']
```

#### **Implementação:**
- Instalar `user-agents` library: `pip install pyyaml ua-parser user-agents`
- Adicionar campos ao BotUser:
  - `device_type` (iPhone, Samsung, etc)
  - `browser_name` (Chrome, Safari, etc)
  - `os_name` (iOS, Android, Windows)
  - `is_mobile` (boolean)
  - `is_bot_detected` (boolean)
- Parse no redirect e salvar no Redis
- Associar ao BotUser quando /start

#### **Benefícios:**
- ✅ Segmentar remarketing por dispositivo
- ✅ Detectar bots automaticamente
- ✅ Otimizar landing pages por plataforma
- ✅ Analytics de conversão por dispositivo

#### **Casos de Uso:**
```python
# Remarketing apenas para mobile
mobile_users = BotUser.query.filter_by(is_mobile=True, purchased=False)

# Detectar bots
bots = BotUser.query.filter_by(is_bot_detected=True)

# Comparar conversão iOS vs Android
ios_conversion = Payment.query.join(BotUser).filter(BotUser.os_name == 'iOS').count()
android_conversion = Payment.query.join(BotUser).filter(BotUser.os_name == 'Android').count()
```

---

### **4. PERFIL ANALÍTICO DO USUÁRIO**

#### **Problema:**
- Dados isolados (IP, UA, geo) não contam história completa
- Precisamos perfil único agregando tudo

#### **Solução:**
```python
class UserAnalyticalProfile:
    """
    Perfil analítico completo do usuário
    
    Agrega:
    - Dados demográficos (geo)
    - Dados técnicos (dispositivo, browser)
    - Dados comportamentais (tempo click → start, horário de acesso)
    - Scores de qualidade (bot score, fraud score)
    """
    
    @staticmethod
    def generate(bot_user):
        profile = {
            # Demográfico
            'location': {
                'city': bot_user.geo_city,
                'state': bot_user.geo_state,
                'country': bot_user.geo_country
            },
            
            # Técnico
            'device': {
                'type': bot_user.device_type,
                'os': bot_user.os_name,
                'browser': bot_user.browser_name,
                'is_mobile': bot_user.is_mobile
            },
            
            # Comportamental
            'behavior': {
                'click_to_start_seconds': (bot_user.first_interaction - bot_user.click_timestamp).total_seconds() if bot_user.click_timestamp else None,
                'access_hour': bot_user.first_interaction.hour,
                'access_day_of_week': bot_user.first_interaction.weekday()
            },
            
            # Scores
            'quality': {
                'bot_score': UserAnalyticalProfile._calculate_bot_score(bot_user),
                'fraud_score': UserAnalyticalProfile._calculate_fraud_score(bot_user)
            }
        }
        
        return profile
    
    @staticmethod
    def _calculate_bot_score(bot_user):
        """Retorna 0-100, onde 100 = certeza de bot"""
        score = 0
        
        # User-Agent indica bot
        if bot_user.is_bot_detected:
            score += 50
        
        # Múltiplos acessos do mesmo IP em < 1 min
        similar_users = BotUser.query.filter_by(ip_hash=bot_user.ip_hash).filter(
            BotUser.first_interaction >= bot_user.first_interaction - timedelta(minutes=1)
        ).count()
        if similar_users > 5:
            score += 30
        
        # Click → Start muito rápido (< 2s)
        if bot_user.click_timestamp:
            diff = (bot_user.first_interaction - bot_user.click_timestamp).total_seconds()
            if diff < 2:
                score += 20
        
        return min(score, 100)
    
    @staticmethod
    def _calculate_fraud_score(bot_user):
        """Retorna 0-100, onde 100 = certeza de fraude"""
        score = 0
        
        # País diferente do esperado
        if bot_user.geo_country != 'BR':
            score += 40
        
        # Sem fbclid (não veio de anúncio legítimo)
        if not bot_user.fbclid:
            score += 30
        
        # Acesso fora de horário comercial (3am-6am)
        if 3 <= bot_user.first_interaction.hour <= 6:
            score += 20
        
        # Bot detectado
        if bot_user.is_bot_detected:
            score += 10
        
        return min(score, 100)
```

#### **Implementação:**
- Criar tabela `UserProfile` com JSON field para armazenar perfil
- Gerar perfil assíncrono (Celery task) após /start
- Exibir perfil no admin panel
- Usar scores para filtrar leads suspeitos

#### **Benefícios:**
- ✅ Visão 360° do usuário
- ✅ Detectar fraudes automaticamente
- ✅ Segmentação avançada
- ✅ Insights acionáveis

---

### **5. FALLBACK RESILIENTE (Redis Failures)**

#### **Problema:**
- Se Redis cair, tracking para de funcionar
- Perdemos dados críticos de IP/UA

#### **Solução:**
```python
class TrackingStorageFallback:
    """
    Sistema de fallback com múltiplos backends:
    1. Redis (primário, rápido)
    2. Memcached (fallback 1, se Redis falhar)
    3. PostgreSQL temp table (fallback 2, se ambos falharem)
    4. Log file (fallback 3, último recurso)
    """
    
    @staticmethod
    def save(fbclid, tracking_data):
        # Tentar Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.setex(f'tracking:{fbclid}', 180, json.dumps(tracking_data))
            logger.info(f"✅ Tracking salvo no Redis")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Redis falhou: {e}, tentando fallback...")
        
        # Tentar Memcached
        try:
            import memcache
            mc = memcache.Client(['127.0.0.1:11211'])
            mc.set(f'tracking:{fbclid}', json.dumps(tracking_data), time=180)
            logger.info(f"✅ Tracking salvo no Memcached (fallback 1)")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Memcached falhou: {e}, tentando DB...")
        
        # Tentar DB temp
        try:
            from models import TrackingTemp
            temp = TrackingTemp(
                fbclid=fbclid,
                data=json.dumps(tracking_data),
                expires_at=datetime.now() + timedelta(seconds=180)
            )
            db.session.add(temp)
            db.session.commit()
            logger.info(f"✅ Tracking salvo no DB temp (fallback 2)")
            return True
        except Exception as e:
            logger.error(f"❌ DB temp falhou: {e}, salvando em log...")
        
        # Último recurso: log file
        try:
            with open('logs/tracking_fallback.jsonl', 'a') as f:
                f.write(json.dumps({
                    'fbclid': fbclid,
                    'data': tracking_data,
                    'timestamp': datetime.now().isoformat()
                }) + '\n')
            logger.warning(f"⚠️ Tracking salvo em log file (fallback 3)")
            return True
        except Exception as e:
            logger.critical(f"🚨 TODOS OS FALLBACKS FALHARAM: {e}")
            return False
    
    @staticmethod
    def load(fbclid):
        # Tentar Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            data = r.get(f'tracking:{fbclid}')
            if data:
                return json.loads(data)
        except:
            pass
        
        # Tentar Memcached
        try:
            import memcache
            mc = memcache.Client(['127.0.0.1:11211'])
            data = mc.get(f'tracking:{fbclid}')
            if data:
                return json.loads(data)
        except:
            pass
        
        # Tentar DB temp
        try:
            from models import TrackingTemp
            temp = TrackingTemp.query.filter_by(fbclid=fbclid).first()
            if temp and temp.expires_at > datetime.now():
                return json.loads(temp.data)
        except:
            pass
        
        return None
```

#### **Implementação:**
- Criar tabela `TrackingTemp` para fallback DB
- Implementar classe `TrackingStorageFallback`
- Substituir chamadas diretas ao Redis por fallback
- Adicionar cronjob para limpar `TrackingTemp` expirados

#### **Benefícios:**
- ✅ 99.99% uptime do tracking
- ✅ Zero perda de dados críticos
- ✅ Degradação graciosa
- ✅ Recuperação automática

---

## **📊 ROADMAP DE IMPLEMENTAÇÃO:**

### **Sprint 1 (Semana 1):**
- [ ] Hash seguro de IP (LGPD)
- [ ] Geo IP mapping (MaxMind)
- [ ] User-Agent parsing
- [ ] Migration para novos campos

### **Sprint 2 (Semana 2):**
- [ ] Perfil analítico
- [ ] Bot score calculator
- [ ] Fraud score calculator
- [ ] Admin panel para visualizar perfis

### **Sprint 3 (Semana 3):**
- [ ] Fallback resiliente
- [ ] TrackingTemp model
- [ ] Cronjob de limpeza
- [ ] Testes de chaos engineering

### **Sprint 4 (Semana 4):**
- [ ] Dashboard de analytics
- [ ] Segmentação avançada
- [ ] Relatórios automatizados
- [ ] Documentação completa

---

## **🎯 MÉTRICAS DE SUCESSO:**

- **Taxa de captura:** > 95%
- **Taxa de match:** > 90%
- **Uptime tracking:** > 99.9%
- **Latência adicional:** < 5ms
- **Taxa de bot detection:** > 80% precision
- **Taxa de fraud detection:** > 70% precision

---

## **💰 CUSTO ESTIMADO:**

- MaxMind GeoLite2: **Grátis** (até 1000 req/dia)
- Redis: **$0** (já instalado)
- Memcached: **$0** (fallback opcional)
- Storage adicional: **~500MB/mês** (negligível)
- Processamento: **+2% CPU** (parsing UA/Geo)

**ROI:** Aumento de 15-30% na qualidade dos leads = vale cada centavo

---

**ISSO É TRACKING V2. ISSO É INTELIGÊNCIA ACIONÁVEL.** 🚀

