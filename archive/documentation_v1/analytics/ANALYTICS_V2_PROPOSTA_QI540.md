# 📊 **ANALYTICS V2.0 - PROPOSTA COMPLETA (QI 540)**

## 🔍 **ANÁLISE DO SISTEMA ATUAL**

### **O QUE JÁ TEMOS (BOM):**

✅ **Métricas Gerais:**
- Total de usuários, vendas, receita
- Taxa de conversão (users → sales)
- Ticket médio
- Vendas pendentes

✅ **Order Bumps:**
- Taxa de aceite
- Receita gerada
- Shown vs Accepted

✅ **Downsells:**
- Taxa de conversão
- Receita recuperada

✅ **Gráficos:**
- Vendas por dia (7 dias)
- Horários de pico (top 5)
- Produtos mais vendidos

✅ **Design System:**
- Paleta profissional (#FFB800, #10B981, #3B82F6)
- Cards com hover elegante
- Gráficos Chart.js
- CSS consistente

---

## ❌ **LIMITAÇÕES CRÍTICAS IDENTIFICADAS**

### **QI 300:**
```
"Analytics atual é BÁSICO. Falta inteligência:

1. ❌ Zero análise de UTM/Origem
   → Não sabemos qual campanha vende mais
   → Não sabemos ROI por canal
   → Desperdício de verba

2. ❌ Zero análise de Meta Pixel
   → Temos dados de PageView, ViewContent, Purchase
   → MAS não mostramos no analytics!
   → Perdendo insights valiosos

3. ❌ Zero análise de funil
   → PageView → ViewContent → Purchase
   → Onde estão perdendo leads?

4. ❌ Zero análise geográfica
   → customer_user_id é Telegram ID
   → Não temos cidade/país

5. ❌ Zero análise temporal avançada
   → Apenas horários de pico
   → Falta: dias da semana, comparação mensal

6. ❌ Zero análise de pools
   → Pools existem mas sem analytics
   → Qual pool converte mais?

7. ❌ Zero previsões
   → Apenas dados históricos
   → Falta: projeção de vendas, LTV

8. ❌ Zero comparação
   → Não compara com período anterior
   → Cresceu ou caiu?"
```

### **QI 240:**
```
"CONCORDO! Sistema atual mostra O QUE aconteceu,
mas não mostra POR QUE ou COMO MELHORAR.

Analytics V2.0 precisa ser INTELIGENTE."
```

---

## 🎯 **ANALYTICS V2.0 - PROPOSTA**

### **NOVOS MÓDULOS:**

### **1. 📊 UTM & ORIGEM TRACKING**

```sql
-- Ranking de UTM por ROI
SELECT 
    utm_source,
    utm_campaign,
    COUNT(*) as vendas,
    SUM(amount) as receita,
    AVG(amount) as ticket_medio,
    (SUM(amount) / COUNT(DISTINCT utm_campaign)) as roi_estimado
FROM payments
WHERE status = 'paid' AND utm_source IS NOT NULL
GROUP BY utm_source, utm_campaign
ORDER BY receita DESC
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  📊 PERFORMANCE POR ORIGEM                       ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Origem         | Vendas | Receita  | Ticket    ║
║  ─────────────────────────────────────────────── ║
║  🔵 Facebook    |   45   | R$ 4.275 | R$ 95     ║
║  🔴 Google      |   23   | R$ 2.185 | R$ 95     ║
║  🟢 Orgânico    |   12   | R$ 1.140 | R$ 95     ║
║                                                  ║
║  [Gráfico Pizza: % de Receita por Origem]       ║
╚══════════════════════════════════════════════════╝
```

---

### **2. 🎯 FUNIL DE CONVERSÃO (META PIXEL)**

```sql
-- Funil completo
SELECT 
    COUNT(DISTINCT CASE WHEN meta_pageview_sent THEN telegram_user_id END) as pageviews,
    COUNT(DISTINCT CASE WHEN meta_viewcontent_sent THEN telegram_user_id END) as viewcontents,
    COUNT(DISTINCT customer_user_id) as purchases
FROM bot_users
LEFT JOIN payments ON bot_users.telegram_user_id = payments.customer_user_id
WHERE bot_users.bot_id = ?
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  🎯 FUNIL DE CONVERSÃO                           ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  PageView (acessos)                              ║
║  ██████████████████████████ 1.000 (100%)         ║
║                ↓ 60% drop                        ║
║  ViewContent (/start)                            ║
║  ████████████ 400 (40%)                          ║
║                ↓ 75% drop                        ║
║  Purchase (compras)                              ║
║  ███ 100 (10%)                                   ║
║                                                  ║
║  🔴 PROBLEMA: 60% desistem antes de /start!     ║
║  💡 AÇÃO: Melhorar copy do anúncio               ║
╚══════════════════════════════════════════════════╝
```

---

### **3. 💰 ROI POR CAMPANHA**

```sql
-- ROI detalhado
SELECT 
    utm_campaign,
    COUNT(*) as vendas,
    SUM(amount) as receita,
    AVG(amount) as ticket,
    -- Assumindo CPC médio de R$ 2
    (SUM(amount) - (COUNT(DISTINCT bot_users.telegram_user_id) * 2)) as lucro_estimado,
    ((SUM(amount) / (COUNT(DISTINCT bot_users.telegram_user_id) * 2)) * 100) as roi_percent
FROM payments
JOIN bot_users ON payments.customer_user_id = bot_users.telegram_user_id
WHERE payments.status = 'paid'
GROUP BY utm_campaign
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  💰 ROI POR CAMPANHA                             ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Campanha        | Gasto | Receita | ROI        ║
║  ─────────────────────────────────────────────── ║
║  Black Friday    | R$ 500| R$ 2.500| +400% 🚀  ║
║  Cyber Monday    | R$ 300| R$   900| +200% ✅  ║
║  Teste A         | R$ 100| R$    80| -20%  ❌  ║
║                                                  ║
║  💡 Pausar "Teste A" e escalar "Black Friday"   ║
╚══════════════════════════════════════════════════╝
```

---

### **4. 📅 ANÁLISE TEMPORAL AVANÇADA**

```sql
-- Vendas por dia da semana
SELECT 
    CASE strftime('%w', created_at)
        WHEN '0' THEN 'Domingo'
        WHEN '1' THEN 'Segunda'
        ...
    END as dia_semana,
    COUNT(*) as vendas,
    AVG(amount) as ticket_medio
FROM payments
WHERE status = 'paid'
GROUP BY strftime('%w', created_at)
ORDER BY vendas DESC
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  📅 VENDAS POR DIA DA SEMANA                     ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Domingo    ████████████████ 45 vendas 🔥       ║
║  Segunda    ██████████ 28 vendas                 ║
║  Terça      ████████ 22 vendas                   ║
║  Quarta     ██████ 18 vendas                     ║
║  Quinta     ████████ 21 vendas                   ║
║  Sexta      ████████████ 32 vendas               ║
║  Sábado     ██████████████ 38 vendas             ║
║                                                  ║
║  💡 Domingo e Sábado = Melhores dias             ║
║  ⚡ Aumentar budget no fim de semana!            ║
╚══════════════════════════════════════════════════╝
```

---

### **5. 🏆 RANKING DE BOTS POR PERFORMANCE**

```sql
-- Bots ordenados por múltiplos critérios
SELECT 
    bot.name,
    COUNT(DISTINCT bot_users.id) as usuarios,
    COUNT(DISTINCT CASE WHEN payments.status = 'paid' THEN payments.id END) as vendas,
    SUM(CASE WHEN payments.status = 'paid' THEN payments.amount ELSE 0 END) as receita,
    (COUNT(DISTINCT CASE WHEN payments.status = 'paid' THEN payments.id END) / 
     COUNT(DISTINCT bot_users.id) * 100) as taxa_conversao
FROM bots
LEFT JOIN bot_users ON bots.id = bot_users.bot_id
LEFT JOIN payments ON bots.id = payments.bot_id
GROUP BY bots.id
ORDER BY receita DESC
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  🏆 RANKING DE BOTS (RECEITA)                    ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  #1 Bot Netflix    R$ 5.450  (50 vendas) 12.5%  ║
║  #2 Bot INSS       R$ 3.200  (32 vendas) 10.0%  ║
║  #3 Bot Curso      R$ 1.980  (18 vendas)  9.0%  ║
║                                                  ║
║  [Gráfico: Receita | Conversão | Usuários]      ║
╚══════════════════════════════════════════════════╝
```

---

### **6. 🔥 HOTSPOTS E DEAD ZONES**

```
Horários: Quando vendem MAIS vs MENOS
Dias: Melhores dias da semana
Produtos: Qual produto está "morto"
Campanhas: Qual UTM não converte
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  🔥 HOTSPOTS vs ❄️ DEAD ZONES                   ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  🔥 HOTSPOTS (Focar aqui):                       ║
║  • Domingo 18h-22h (35 vendas)                   ║
║  • Campanha "BlackFriday" (ROI +400%)            ║
║  • Produto "Netflix Premium" (60% conversão)     ║
║                                                  ║
║  ❄️ DEAD ZONES (Evitar):                        ║
║  • Segunda 03h-07h (0 vendas)                    ║
║  • Campanha "TesteA" (ROI -20%)                  ║
║  • Produto "Curso X" (2% conversão)              ║
║                                                  ║
║  💡 Pausar anúncios em dead zones!               ║
╚══════════════════════════════════════════════════╝
```

---

### **7. 📈 COMPARAÇÃO COM PERÍODO ANTERIOR**

```sql
-- Crescimento mês a mês
SELECT 
    strftime('%Y-%m', created_at) as mes,
    COUNT(*) as vendas,
    SUM(amount) as receita
FROM payments
WHERE status = 'paid'
GROUP BY mes
ORDER BY mes DESC
LIMIT 2
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  📈 COMPARAÇÃO MENSAL                            ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Outubro 2025                                    ║
║  • Vendas: 125 (+38% vs Set) 🚀                 ║
║  • Receita: R$ 11.875 (+42% vs Set) 🚀          ║
║  • Ticket: R$ 95 (+3% vs Set) ✅                 ║
║                                                  ║
║  Setembro 2025                                   ║
║  • Vendas: 90                                    ║
║  • Receita: R$ 8.370                             ║
║  • Ticket: R$ 93                                 ║
║                                                  ║
║  [Gráfico de Linha: Evolução Mensal]            ║
╚══════════════════════════════════════════════════╝
```

---

### **8. 💎 LTV (LIFETIME VALUE)**

```sql
-- LTV por cliente
SELECT 
    customer_user_id,
    COUNT(*) as compras_totais,
    SUM(amount) as ltv,
    MIN(created_at) as primeira_compra,
    MAX(created_at) as ultima_compra
FROM payments
WHERE status = 'paid'
GROUP BY customer_user_id
HAVING COUNT(*) > 1
ORDER BY ltv DESC
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  💎 LIFETIME VALUE (LTV)                         ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Média de Compras por Cliente: 1.8x              ║
║  LTV Médio: R$ 171                               ║
║  Taxa de Recompra: 35%                           ║
║                                                  ║
║  Top Clientes:                                   ║
║  • Cliente #123 → R$ 485 (5 compras)             ║
║  • Cliente #456 → R$ 380 (4 compras)             ║
║  • Cliente #789 → R$ 285 (3 compras)             ║
║                                                  ║
║  💡 35% dos clientes compram novamente!          ║
║  ⚡ Criar remarketing para inativos              ║
╚══════════════════════════════════════════════════╝
```

---

### **9. 🎯 PERFORMANCE DE POOLS**

```sql
-- Analytics por pool
SELECT 
    pools.name,
    pools.total_redirects,
    COUNT(DISTINCT bot_users.id) as usuarios,
    COUNT(DISTINCT CASE WHEN payments.status = 'paid' THEN payments.id END) as vendas,
    SUM(CASE WHEN payments.status = 'paid' THEN payments.amount ELSE 0 END) as receita
FROM redirect_pools
LEFT JOIN pool_bots ON redirect_pools.id = pool_bots.pool_id
LEFT JOIN bot_users ON pool_bots.bot_id = bot_users.bot_id
LEFT JOIN payments ON bot_users.telegram_user_id = payments.customer_user_id
GROUP BY redirect_pools.id
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  🎯 PERFORMANCE DE POOLS                         ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Pool         | Acessos | Conv. | Receita       ║
║  ───────────────────────────────────────────────  ║
║  Facebook Ads |  1.250  | 12%   | R$ 14.250 🔥  ║
║  Google Ads   |    890  |  8%   | R$  6.764 ✅  ║
║  Orgânico     |    340  |  15%  | R$  4.845 💎  ║
║                                                  ║
║  💡 Pool orgânico tem MELHOR conversão!          ║
║  ⚡ Investir mais em tráfego orgânico            ║
╚══════════════════════════════════════════════════╝
```

---

### **10. ⚡ INSIGHTS AUTOMÁTICOS (IA)**

```python
# Algoritmo de insights
def gerar_insights(bot_stats):
    insights = []
    
    # Insight 1: Campanha com ROI negativo
    if utm_roi < 0:
        insights.append({
            'tipo': 'URGENTE',
            'mensagem': f'Campanha "{utm_campaign}" com ROI negativo! Pausar AGORA!',
            'acao': 'Pausar campanha no Meta Ads'
        })
    
    # Insight 2: Horário morto com budget ativo
    if hour_sales == 0 and hour_spend > 0:
        insights.append({
            'tipo': 'ECONOMIA',
            'mensagem': f'Zero vendas das 03h-07h mas anúncios ativos',
            'acao': 'Pausar anúncios nesse horário'
        })
    
    # Insight 3: Produto com alta conversão
    if product_conversion > 20:
        insights.append({
            'tipo': 'OPORTUNIDADE',
            'mensagem': f'{product_name} com {product_conversion}% de conversão!',
            'acao': 'Criar upsell para esse produto'
        })
    
    return insights
```

**Visualização:**
```
╔══════════════════════════════════════════════════╗
║  ⚡ INSIGHTS AUTOMÁTICOS                         ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  🔴 URGENTE                                       ║
║  Campanha "TesteA" com ROI -20%                  ║
║  💡 Pausar AGORA no Meta Ads                     ║
║  [Pausar Campanha]                               ║
║                                                  ║
║  💰 OPORTUNIDADE                                  ║
║  Produto "Netflix Premium" → 60% conversão!      ║
║  💡 Aumentar budget dessa oferta                 ║
║  [Escalar Campanha]                              ║
║                                                  ║
║  💎 DESCOBERTA                                    ║
║  35% dos clientes compram 2+ vezes               ║
║  💡 Criar sequência de upsells                   ║
║  [Ver Estratégia]                                ║
╚══════════════════════════════════════════════════╝
```

---

## 🎨 **WIREFRAME - ANALYTICS V2.0**

### **Seguindo Padrão Visual do Sistema:**

```html
<!-- PALETA OFICIAL -->
Dourado Principal: #FFB800
Verde Sucesso: #10B981
Azul Info: #3B82F6
Vermelho Alerta: #EF4444

Background: #0A0A0A
Cards: rgba(255, 255, 255, 0.03) com border rgba(255, 184, 0, 0.08)
Hover: translateY(-2px) + glow dourado

Fonte: Inter, -apple-system
Border Radius: 12px (cards), 16px (sections)
```

```
╔════════════════════════════════════════════════════════════╗
║  📊 Analytics - @seu_bot                                   ║
║  [Última atualização: há 2 minutos]                        ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ┌──────────────────────────────────────────────────────┐ ║
║  │ ⚡ INSIGHTS AUTOMÁTICOS                              │ ║
║  ├──────────────────────────────────────────────────────┤ ║
║  │ 🔴 [Campanha X com ROI -20%] [Pausar Agora]         │ ║
║  │ 🚀 [Domingo converte 2x mais] [Escalar Budget]      │ ║
║  └──────────────────────────────────────────────────────┘ ║
║                                                            ║
║  ┌───────────┬───────────┬───────────┬───────────────────┐ ║
║  │ 📊 FUNIL DE CONVERSÃO                                │ ║
║  ├───────────┴───────────┴───────────┴───────────────────┤ ║
║  │ PageView: 1.000 ████████████████████ 100%            │ ║
║  │ ViewContent: 400 ████████ 40% (-60%)                 │ ║
║  │ Purchase: 100 ██ 10% (-75%)                          │ ║
║  └──────────────────────────────────────────────────────┘ ║
║                                                            ║
║  ┌────────────┬─────────────┬────────────┬──────────────┐ ║
║  │ 💰 RECEITA POR ORIGEM                                │ ║
║  ├────────────┴─────────────┴────────────┴──────────────┤ ║
║  │ Facebook:  R$ 4.275 (45 vendas)  Ticket: R$ 95       │ ║
║  │ Google:    R$ 2.185 (23 vendas)  Ticket: R$ 95       │ ║
║  │ Orgânico:  R$ 1.140 (12 vendas)  Ticket: R$ 95       │ ║
║  │ [Gráfico Pizza]                                       │ ║
║  └──────────────────────────────────────────────────────┘ ║
║                                                            ║
║  ┌───────────────────────┬────────────────────────────────┐ ║
║  │ 📅 TEMPORAL           │ 💎 LTV                         │ ║
║  ├───────────────────────┼────────────────────────────────┤ ║
║  │ Domingo:   45 vendas  │ Média: R$ 171                  │ ║
║  │ Sábado:    38 vendas  │ Recompra: 35%                  │ ║
║  │ Sexta:     32 vendas  │ Top Cliente: R$ 485            │ ║
║  │ [Ver Mais]            │ [Ver Top 10]                   │ ║
║  └───────────────────────┴────────────────────────────────┘ ║
║                                                            ║
║  ┌──────────────────────────────────────────────────────┐ ║
║  │ 🎯 ROI POR CAMPANHA                                  │ ║
║  ├──────────────────────────────────────────────────────┤ ║
║  │ Black Friday  | Gasto: R$ 500 | ROI: +400% 🚀       │ ║
║  │ Cyber Monday  | Gasto: R$ 300 | ROI: +200% ✅       │ ║
║  │ Teste A       | Gasto: R$ 100 | ROI: -20%  ❌       │ ║
║  └──────────────────────────────────────────────────────┘ ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

## 🏗️ **ARQUITETURA PROPOSTA**

### **Backend (API):**

```python
@app.route('/api/bots/<int:bot_id>/analytics-v2', methods=['GET'])
@login_required
def get_bot_analytics_v2(bot_id):
    """
    Analytics V2.0 - Inteligente e Completo
    
    Returns:
        {
            'funil': {...},
            'utm_performance': [...],
            'roi_campaigns': [...],
            'temporal': {...},
            'ltv': {...},
            'insights': [...],
            'pools': [...]
        }
    """
```

### **Frontend (Componentes):**

```html
<!-- Seguindo padrão EXATO do sistema -->
<div class="config-section">  <!-- Classe existente -->
    <div class="config-section-header">
        <i class="fas fa-chart-line" style="color: #FFB800;"></i>
        <div>
            <h3 class="config-section-title">Funil de Conversão</h3>
            <p class="config-section-description">PageView → ViewContent → Purchase</p>
        </div>
    </div>
    
    <!-- Conteúdo usando classes existentes -->
</div>
```

---

## 📋 **CAMPOS NOVOS NECESSÁRIOS**

### **NÃO PRECISA ADICIONAR CAMPOS!**

Todos os dados JÁ EXISTEM:
- ✅ `bot_users.utm_source, utm_campaign` 
- ✅ `bot_users.meta_pageview_sent, meta_viewcontent_sent`
- ✅ `payments.utm_source, utm_campaign`
- ✅ `payments.is_downsell, is_upsell, is_remarketing`
- ✅ `redirect_pools.total_redirects`

**APENAS precisamos fazer QUERIES inteligentes!**

---

## ✅ **PRÓXIMOS PASSOS**

### **1. Implementar API `/api/bots/<bot_id>/analytics-v2`**
```
Tempo: 30min
Complexidade: Queries SQL avançadas
```

### **2. Criar Frontend seguindo padrão visual**
```
Tempo: 40min
Complexidade: Alpine.js + Chart.js
CSS: Usar classes existentes (config-section, stat-box, etc)
```

### **3. Testes com dados reais**
```
Tempo: 15min
Complexidade: Validar queries, performance
```

---

## 🎯 **SCORE ESTIMADO V2.0**

| Aspecto | V1.0 | V2.0 |
|---------|------|------|
| Insights | 30% | 95% |
| UTM Tracking | 0% | 100% |
| Funil | 0% | 100% |
| ROI | 0% | 90% |
| Comparação | 0% | 100% |
| LTV | 0% | 100% |
| Pools | 0% | 100% |
| Actionable | 20% | 95% |

**MÉDIA: V1.0 = 7% | V2.0 = 97%**

---

## 💪 **DECISÃO QI 540**

### **QI 240:**
```
"Proposta sólida. Vamos implementar seguindo 
padrão visual RIGOROSAMENTE."
```

### **QI 300:**
```
"Concordo. Analytics V2.0 vai ser INTELIGENTE,
não apenas bonito.

Começamos AGORA!"
```

**Quer que implementemos Analytics V2.0 completo?** 🚀

---

*Proposta: QI 240 + QI 300*
*Data: 2025-10-20*
*Estimativa: 90 minutos*
*Score Esperado: 97%*

