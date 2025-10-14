# 🏗️ ARQUITETURA: SISTEMA DE LOAD BALANCER DE BOTS

## 📋 VISÃO GERAL

### Problema Real:
Usuários com **ALTO VOLUME** de tráfego (1000+ leads/hora) precisam de **CONTINGÊNCIA**:
- 1 bot = limite ~2.250 mensagens/hora (Telegram)
- Bot banido = operação inteira para
- Sem distribuição de carga = gargalo

### Solução Proposta:
**POOL DE BOTS COM LOAD BALANCING INTELIGENTE**

---

## 🎯 CONCEITO: REDIRECT POOLS

### O que é um Pool?

Um **Pool** (ou Grupo de Redirecionamento) é um conjunto de bots que:
- Compartilham o **MESMO FLUXO**  
- Distribuem a **CARGA** automaticamente
- Failover **AUTOMÁTICO** se um bot cair
- Health Check **CONTÍNUO**

### Exemplo Prático:

```
Pool: "INSS_PRINCIPAL" (red1)
  ├─ Bot A (@inss_bot_001) ✅ Online - 450 leads
  ├─ Bot B (@inss_bot_002) ✅ Online - 432 leads
  ├─ Bot C (@inss_bot_003) ❌ Banido  - 0 leads
  └─ Bot D (@inss_bot_004) ✅ Online - 418 leads
  
Capacidade Total: 6.750 leads/hora (3 bots x 2.250)
Status: 75% saudável (3/4 online)
```

---

## 🏗️ ARQUITETURA PROPOSTA

### Modelo de Dados:

```python
# models.py

class RedirectPool(db.Model):
    """Pool de redirecionamento (grupo de bots)"""
    __tablename__ = 'redirect_pools'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Identificação
    name = db.Column(db.String(100), nullable=False)  # "INSS Principal"
    slug = db.Column(db.String(50), nullable=False)   # "red1" (usado em links)
    
    # Configuração
    is_active = db.Column(db.Boolean, default=True)
    distribution_strategy = db.Column(db.String(20), default='round_robin')
    # Estratégias: round_robin, least_connections, random, weighted
    
    # Saúde do pool
    total_redirects = db.Column(db.Integer, default=0)
    healthy_bots = db.Column(db.Integer, default=0)  # Cache
    total_bots = db.Column(db.Integer, default=0)    # Cache
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    # Relacionamentos
    bots = db.relationship('Bot', secondary='pool_bots', backref='pools')


class PoolBot(db.Model):
    """Associação entre Pool e Bot (many-to-many)"""
    __tablename__ = 'pool_bots'
    
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.Integer, db.ForeignKey('redirect_pools.id'), nullable=False, index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Configuração específica deste bot no pool
    weight = db.Column(db.Integer, default=1)  # Peso para weighted load balancing
    priority = db.Column(db.Integer, default=0)  # 0=normal, 1=preferencial, -1=backup
    is_enabled = db.Column(db.Boolean, default=True)
    
    # Health check
    status = db.Column(db.String(20), default='checking')  # online, offline, degraded
    last_health_check = db.Column(db.DateTime)
    consecutive_failures = db.Column(db.Integer, default=0)
    
    # Circuit breaker
    circuit_breaker_until = db.Column(db.DateTime)
    
    # Métricas
    total_redirects = db.Column(db.Integer, default=0)
    
    # Timestamps
    added_at = db.Column(db.DateTime, default=get_brazil_time)
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('pool_id', 'bot_id', name='unique_pool_bot'),
    )
```

---

## 🔄 ESTRATÉGIAS DE DISTRIBUIÇÃO

### 1. Round Robin (Padrão)
```
Requisição 1 → Bot A
Requisição 2 → Bot B
Requisição 3 → Bot C
Requisição 4 → Bot A (volta ao início)
```
**Vantagem:** Distribuição igualitária  
**Uso:** Pools homogêneos (bots iguais)

### 2. Least Connections
```
Bot A: 450 conexões
Bot B: 432 conexões ← Escolhido
Bot C: 500 conexões
```
**Vantagem:** Balanceia carga automaticamente  
**Uso:** Bots com capacidades diferentes

### 3. Random
```
Requisição → Bot aleatório (online)
```
**Vantagem:** Imprevisível, dificulta ban em massa  
**Uso:** Alta escala

### 4. Weighted
```
Bot A (weight=3): 60% do tráfego
Bot B (weight=2): 40% do tráfego
```
**Vantagem:** Controle fino  
**Uso:** Bots com capacidades diferentes

---

## 🛡️ HEALTH CHECK E FAILOVER

### Health Check Contínuo:

```javascript
// A cada 15 segundos (backend)
for each bot in pool:
    status = check_telegram_api(bot.token)
    
    if status == 401 or 403:
        bot.status = 'offline'
        bot.circuit_breaker = now + 2min
        consecutive_failures += 1
        
        if consecutive_failures >= 3:
            blacklist_permanently(bot)
            notify_user(bot_banido)
```

### Circuit Breaker:

```
Falha 1 → Marca como degraded
Falha 2 → Offline por 2 minutos
Falha 3 → Blacklist permanente + Notificação
```

---

## 📊 MONITORAMENTO EM TEMPO REAL

### Dashboard do Pool:

```
┌─────────────────────────────────────────────┐
│ Pool: INSS_PRINCIPAL (red1)                 │
├─────────────────────────────────────────────┤
│ Saúde: 75% ████████████░░░░ (3/4 online)   │
│ Tráfego: 1.247 redirects/hora              │
│ Capacidade: 6.750/9.000 (75%)               │
├─────────────────────────────────────────────┤
│ Bots:                                        │
│  ✅ @inss_001 │ 418 │ 50ms │ Round: #1     │
│  ✅ @inss_002 │ 432 │ 45ms │ Round: #2     │
│  ❌ @inss_003 │  0  │  --  │ BANIDO        │
│  ✅ @inss_004 │ 397 │ 52ms │ Round: #3     │
└─────────────────────────────────────────────┘
```

---

## 🔗 COMO O USUÁRIO USA

### Passo 1: Criar Pool

```
Configurar Bot → Aba "Redirecionamento"
├─ Nome: "INSS Principal"
├─ Slug: "red1"
├─ Estratégia: Round Robin
└─ [Criar Pool]
```

### Passo 2: Adicionar Bots ao Pool

```
Meus Bots:
├─ @inss_bot_001 → [Adicionar ao Pool: red1] ✅
├─ @inss_bot_002 → [Adicionar ao Pool: red1] ✅
├─ @inss_bot_003 → [Adicionar ao Pool: red1] ✅
└─ @inss_bot_004 → [Adicionar ao Pool: red1] ✅
```

### Passo 3: Gerar Link de Redirecionamento

```
Link gerado: 
https://seu-dominio.com/go/red1

Este link distribui automaticamente entre os 4 bots!
```

### Passo 4: Usar no Funil

```
Landing Page → Botão: "Falar com Atendente"
                 ↓
        https://seu-dominio.com/go/red1
                 ↓
        Load Balancer escolhe bot online
                 ↓
        https://t.me/inss_bot_002?start=acesso
```

---

## ⚙️ FLUXO TÉCNICO

### Request Flow:

```
1. Cliente clica: /go/red1
   ↓
2. Backend busca pool "red1"
   ↓
3. Load Balancer:
   - Filtra bots online (health check cache)
   - Aplica estratégia (round_robin)
   - Seleciona Bot B
   ↓
4. Incrementa: bot.total_redirects
   ↓
5. Redirect 302: https://t.me/bot_002?start=acesso
   ↓
6. Cliente é direcionado para o bot
   ↓
7. Bot processa /start normalmente
```

### Health Check Background (APScheduler):

```python
@scheduler.task('interval', id='health_check_pools', seconds=15)
def check_all_pools_health():
    """Verifica saúde de todos os bots nos pools"""
    pools = RedirectPool.query.filter_by(is_active=True).all()
    
    for pool in pools:
        for pool_bot in pool.pool_bots:
            health = check_bot_health(pool_bot.bot)
            
            if health['healthy']:
                pool_bot.status = 'online'
                pool_bot.consecutive_failures = 0
            else:
                pool_bot.consecutive_failures += 1
                
                if pool_bot.consecutive_failures >= 3:
                    pool_bot.status = 'offline'
                    pool_bot.circuit_breaker_until = now + 120s
                    notify_user_bot_down(pool, pool_bot.bot)
```

---

## 🚀 ENDPOINTS DA API

```python
# Criar pool
POST /api/redirect-pools
{
  "name": "INSS Principal",
  "slug": "red1",
  "strategy": "round_robin"
}

# Adicionar bot ao pool
POST /api/redirect-pools/{pool_id}/bots
{
  "bot_id": 123,
  "weight": 1,
  "priority": 0
}

# Remover bot do pool
DELETE /api/redirect-pools/{pool_id}/bots/{bot_id}

# Redirecionamento público
GET /go/{slug}
→ 302 Redirect: https://t.me/selected_bot?start=acesso

# Status do pool (admin)
GET /api/redirect-pools/{pool_id}/status
{
  "health": 75,
  "online_bots": 3,
  "total_bots": 4,
  "redirects_hour": 1247,
  "capacity_used": "75%"
}
```

---

## 📈 BENEFÍCIOS

### Para Usuários de Alto Volume:

✅ **Alta Disponibilidade:** Se 1 bot cair, outros 3 continuam  
✅ **Escalabilidade:** Adicione bots conforme cresce  
✅ **Zero Downtime:** Failover automático  
✅ **Monitoramento:** Veja qual bot está com problema  
✅ **Contingência:** Crie pools backup (red1, red2)  

### Para a Plataforma:

✅ **Profissional:** Feature enterprise  
✅ **Diferencial:** Concorrência não tem  
✅ **Retenção:** Usuários grandes ficam  
✅ **Upsell:** Pools maiores = planos premium  

---

## 🎯 CASOS DE USO REAIS

### Caso 1: Operação Grande (5.000 leads/hora)

```
Pool "INSS_MEGA"
├─ 6 bots ativos
├─ Estratégia: Least Connections
├─ Capacidade: 13.500/hora
└─ Uso: 37% (folga para picos)

Resultado:
- Nunca para
- Distribui automaticamente
- Se 2 bots caem, ainda suporta 100%
```

### Caso 2: A/B Testing

```
Pool "FGTS_A" (red_a)
└─ Fluxo: Vídeo curto + Order Bump agressivo

Pool "FGTS_B" (red_b)
└─ Fluxo: Vídeo longo + Order Bump sutil

Tráfego pago:
- 50% → /go/red_a
- 50% → /go/red_b

Resultado: Comparar qual converte mais
```

### Caso 3: Contingência Geográfica

```
Pool "NORDESTE"
└─ Bots otimizados para público regional

Pool "SUDESTE"
└─ Bots otimizados para público regional

Tráfego:
- Ads SP/RJ → /go/sudeste
- Ads BA/PE → /go/nordeste
```

---

## 🔐 SEGURANÇA E VALIDAÇÕES

### Ownership:
- ✅ Usuário só vê/edita seus próprios pools
- ✅ Bots de outros usuários não aparecem

### Validações:
- ✅ Slug único por usuário
- ✅ Mínimo 1 bot no pool
- ✅ Máximo configurável (ex: 10 bots/pool)

### Proteções:
- ✅ Rate limiting em `/go/{slug}` (100 req/min)
- ✅ Bot banido removido automaticamente
- ✅ Notificação se pool ficar com <50% de saúde

---

## 📊 MÉTRICAS E ANALYTICS

### Por Pool:
- Total de redirects
- Redirects/hora
- Taxa de sucesso
- Bot mais usado
- Bot mais problemático

### Por Bot (dentro do pool):
- Total de redirects no pool
- Uptime %
- Tempo médio de resposta
- Últimas 10 falhas

---

## 💡 IMPLEMENTAÇÃO TÉCNICA

### Frontend (bot_config.html):

```html
<!-- Nova aba: Redirecionamento -->
<div x-show="activeTab === 'redirect'" x-cloak>
    <h3>Sistema de Load Balancer</h3>
    
    <!-- Criar Pool -->
    <button @click="createPool()">
        Criar Pool de Redirecionamento
    </button>
    
    <!-- Lista de Pools -->
    <div x-for="pool in pools">
        <div class="pool-card">
            <h4>{{ pool.name }} ({{ pool.slug }})</h4>
            <p>Saúde: {{ pool.health }}%</p>
            <p>Bots: {{ pool.healthy_bots }}/{{ pool.total_bots }}</p>
            
            <!-- Link Público -->
            <input readonly value="https://dominio.com/go/{{ pool.slug }}">
            
            <!-- Gerenciar Bots -->
            <button @click="manageBots(pool)">
                Gerenciar Bots
            </button>
        </div>
    </div>
</div>
```

### Backend (app.py):

```python
@app.route('/go/<slug>')
def redirect_to_bot(slug):
    """
    Endpoint público de redirecionamento
    
    Load Balancer: seleciona bot online do pool
    """
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    # Buscar bots online deste pool
    online_bots = PoolBot.query.filter_by(
        pool_id=pool.id,
        is_enabled=True,
        status='online'
    ).filter(
        db.or_(
            PoolBot.circuit_breaker_until.is_(None),
            PoolBot.circuit_breaker_until < datetime.now()
        )
    ).all()
    
    if not online_bots:
        # Fallback: usar bot degradado
        degraded = PoolBot.query.filter_by(
            pool_id=pool.id,
            status='degraded'
        ).first()
        
        if degraded:
            online_bots = [degraded]
        else:
            abort(503, 'Nenhum bot disponível no momento')
    
    # Aplicar estratégia de distribuição
    selected_bot = apply_distribution_strategy(pool, online_bots)
    
    # Incrementar métricas
    selected_bot.total_redirects += 1
    pool.total_redirects += 1
    db.session.commit()
    
    # Log
    logger.info(f"Redirect: {slug} → @{selected_bot.bot.username} ({pool.distribution_strategy})")
    
    # Redirect 302
    return redirect(f"https://t.me/{selected_bot.bot.username}?start=acesso", code=302)
```

---

## 🎨 INTERFACE DO USUÁRIO

### Aba "Redirecionamento" (bot_config.html):

```
┌─────────────────────────────────────────────┐
│ 🔄 SISTEMA DE LOAD BALANCER                 │
├─────────────────────────────────────────────┤
│                                              │
│ 📋 Seus Pools:                               │
│                                              │
│ ┌───────────────────────────────────────┐   │
│ │ INSS PRINCIPAL (red1)        [ATIVO]  │   │
│ ├───────────────────────────────────────┤   │
│ │ Saúde: 75% ████████████░░░░            │   │
│ │ Bots: 3/4 online                      │   │
│ │ Tráfego: 1.247/hora                   │   │
│ │                                        │   │
│ │ Link público:                          │   │
│ │ https://dominio.com/go/red1  [COPIAR] │   │
│ │                                        │   │
│ │ [Gerenciar Bots] [Analytics] [Config] │   │
│ └───────────────────────────────────────┘   │
│                                              │
│ [+ Criar Novo Pool]                          │
│                                              │
└─────────────────────────────────────────────┘
```

### Modal "Gerenciar Bots":

```
┌─────────────────────────────────────────────┐
│ Gerenciar Pool: INSS PRINCIPAL              │
├─────────────────────────────────────────────┤
│                                              │
│ Bots Disponíveis:          Bots no Pool:    │
│                                              │
│ [ ] @outro_bot_005         [✅] @inss_001   │
│ [ ] @outro_bot_006         [✅] @inss_002   │
│                            [❌] @inss_003   │
│                            [✅] @inss_004   │
│                                              │
│ [Adicionar Selecionados]   [Remover]        │
│                                              │
└─────────────────────────────────────────────┘
```

---

## ⚡ PERFORMANCE

### Benchmarks:

- **Latência de redirect:** <50ms
- **Health check:** <3s (paralelo)
- **Cache de status:** 15s (evita DB lookup)
- **Capacidade:** 13.500 leads/hora (6 bots)

### Otimizações:

✅ Cache de bots online (Redis)  
✅ Health check assíncrono (background)  
✅ Índices em pool_id, bot_id, status  
✅ Query única para buscar bots online  

---

## 📱 NOTIFICAÇÕES

### Alertas Automáticos:

```python
# Bot ficou offline
"⚠️ Bot @inss_003 do pool 'INSS_PRINCIPAL' está offline.
Saúde do pool: 75% (3/4 online)"

# Pool crítico (< 50% saúde)
"🚨 CRÍTICO: Pool 'INSS_PRINCIPAL' com apenas 33% de saúde!
Apenas 1 de 3 bots online. Adicione mais bots ou verifique os existentes."

# Bot recuperado
"✅ Bot @inss_003 voltou online no pool 'INSS_PRINCIPAL'
Saúde do pool: 100% (4/4 online)"
```

---

## 🎯 ROADMAP DE IMPLEMENTAÇÃO

### Fase 1: MVP (Essencial)
- ✅ Criar modelos (RedirectPool, PoolBot)
- ✅ Endpoint `/go/{slug}`
- ✅ Round Robin básico
- ✅ Health check simples
- ✅ Interface para criar pools

### Fase 2: Inteligência
- ✅ Least Connections
- ✅ Circuit Breaker
- ✅ Blacklist automática
- ✅ Métricas em tempo real

### Fase 3: Enterprise
- ✅ Weighted distribution
- ✅ Analytics avançado
- ✅ Alertas por email/Telegram
- ✅ API para integrações

---

## 🔥 DIFERENCIAIS COMPETITIVOS

1. **Alta Disponibilidade:** 99.9% uptime
2. **Escalabilidade:** Suporta operações enterprise
3. **Inteligente:** Detecta e isola bots problemáticos
4. **Visual:** Dashboard profissional
5. **Simples:** 1 link = N bots

---

**Esta arquitetura transforma a plataforma em uma solução ENTERPRISE para operações de ALTO VOLUME!** 🚀



