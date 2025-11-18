# 🔍 ANÁLISE SÊNIOR: Editor de Fluxograma Visual

**Status:** 📋 Análise Técnica Completa  
**Data:** 2025-01-18  
**Objetivo:** Implementar editor visual de fluxograma (como na imagem) SEM quebrar sistema atual

---

## 📊 1. ANÁLISE DO SISTEMA ATUAL

### 1.1 Arquitetura Atual de Boas-vindas

**Modelo (`BotConfig`):**
```python
welcome_message = db.Column(db.Text)
welcome_media_url = db.Column(db.String(500))
welcome_media_type = db.Column(db.String(20), default='video')
welcome_audio_enabled = db.Column(db.Boolean, default=False)
welcome_audio_url = db.Column(db.String(500))
```

**Processamento (`bot_manager.py` - `_handle_start_command`):**
```python
def _handle_start_command(...):
    # 1. Resetar funil do usuário
    self._reset_user_funnel(...)
    
    # 2. Buscar config do banco
    config = bot.config.to_dict()
    
    # 3. Enviar mensagem sequencial:
    self.send_funnel_step_sequential(
        text=welcome_message,
        media_url=welcome_media_url,
        media_type=welcome_media_type,
        buttons=main_buttons + redirect_buttons,
        delay_between=0.2
    )
    
    # 4. Se audio_enabled, enviar áudio adicional
    if welcome_audio_enabled:
        self.send_audio(...)
    
    # 5. Marcar welcome_sent = True
    bot_user.welcome_sent = True
```

**Fluxo Atual:**
```
/start → Reset Funil → Envia Welcome (mídia + texto + botões) → Envia Áudio (opcional) → Fim
```

### 1.2 Pontos Críticos do Sistema

**✅ O que NÃO pode quebrar:**
1. ✅ `/start` sempre reinicia funil (regra absoluta)
2. ✅ `welcome_sent` flag para anti-duplicação
3. ✅ Processamento assíncrono (RQ) para tarefas pesadas
4. ✅ Sistema de botões (`buy_`, `verify_`, `bump_yes_`, `rmkt_`)
5. ✅ Integração com Meta Pixel (viewcontent no /start)
6. ✅ Sistema de tracking (tracking_token, pageview_event_id)
7. ✅ Downsells/Upsells (funcionam independente de welcome)
8. ✅ Remarketing (fluxo separado)

**⚠️ Dependências Críticas:**
- `BotConfig.to_dict()` - usado em vários lugares
- `bot_manager.update_bot_config()` - atualiza config em tempo real
- `_handle_start_command()` - entry point crítico
- `_handle_callback_query()` - processa botões (buy, verify, bump, rmkt)
- `_handle_verify_payment()` - verifica pagamento e libera acesso

---

## 🎯 2. REQUISITOS DO EDITOR DE FLUXOGRAMAS

### 2.1 Conceito (Baseado na Imagem)

**Editor Visual de Fluxograma com Conexões:**

```
┌─────────────┐
│ [Bloco 1]   │───┐
│ Conteúdo    │   │
└─────────────┘   │
                  ▼
┌─────────────┐   │   ┌─────────────┐
│ [Bloco 2]   │◄──┘   │ [Bloco 3]   │
│ Pix Pagar   │       │ Não Pago    │
└─────────────┘       └─────────────┘
      │                      │
      │                      │
      ▼                      ▼
┌─────────────┐       ┌─────────────┐
│ [Bloco 4]   │       │ [Bloco 4]   │
│ Acesso OK   │       │ Acesso OK   │
└─────────────┘       └─────────────┘
```

**Características:**
- ✅ **Canvas Visual** - área de desenho infinita
- ✅ **Blocos Posicionáveis** - arrastar e soltar em qualquer posição
- ✅ **Conexões com Linhas** - arrastar de um bloco para outro cria conexão
- ✅ **Múltiplas Saídas** - um bloco pode ter várias conexões
- ✅ **Execução por Conexões** - sistema segue as linhas, não ordem linear
- ✅ **Tipos de Blocos:** Foto, Vídeo, Texto, Áudio, Botões, Pagamento, Verificação, Acesso

### 2.2 Fluxo Exemplo da Imagem

**Nó 1: Conteúdo Inicial**
- Tipo: `content` (foto + texto)
- Config: `{media_url: "...", message: "Aquele CONTEUDO PESADO..."}`
- Botões: `[{text: "❌❌CONHEÇA O VIP ❌❌ por R$9.90", callback: "buy_0"}]`
- Conexão → Nó 2 (Pix Pagar)

**Nó 2: Pix Pagamento**
- Tipo: `payment`
- Config: `{message: "Pague via Pix...", pix_key: "{{pix}}"}` 
- Botões: `[{text: "Verificar Pagamento", callback: "verify_{payment_id}"}]`
- Conexões:
  - → Nó 3 (se `status == 'pending'`)
  - → Nó 4 (se `status == 'paid'`)

**Nó 3: Pagamento Não Identificado**
- Tipo: `message`
- Config: `{message: "Não foi identificado seu pagamento..."}`
- Botões: `[{text: "Verificar Novamente", callback: "verify_{payment_id}"}]`
- Conexão → Nó 2 (loop de verificação)

**Nó 4: Acesso Liberado**
- Tipo: `access`
- Config: `{message: "Seja Bem vindo acesse o grupo 👇", link: "https://seusacessos.shop/..."}`
- Conexões: Fim do fluxo

---

## 🔧 3. DEBATE TÉCNICO: Opções de Implementação

### **OPÇÃO 1: Fluxo Condicional Completo** ⭐ (RECOMENDADA)

#### Conceito
Editor de fluxograma visual onde usuário monta fluxo com blocos e conexões, incluindo **lógica condicional** (ex: "se pago" → Acesso, "se não pago" → Verificar Novamente).

#### Estrutura de Dados

```json
{
  "flow_enabled": true,
  "flow_nodes": [
    {
      "id": "node_1",
      "type": "content",
      "x": 100,
      "y": 100,
      "config": {
        "media_url": "https://t.me/canal/32",
        "message": "Aquele CONTEUDO PESADO...",
        "buttons": [{"text": "CONHEÇA O VIP", "price": 9.90}]
      },
      "connections": ["node_2"]
    },
    {
      "id": "node_2",
      "type": "payment",
      "x": 400,
      "y": 100,
      "config": {
        "message": "Pague via Pix...",
        "amount": 9.90
      },
      "connections": [
        {"target": "node_3", "condition": "payment_pending"},
        {"target": "node_4", "condition": "payment_paid"}
      ]
    },
    {
      "id": "node_3",
      "type": "message",
      "x": 700,
      "y": 50,
      "config": {
        "message": "Não foi identificado seu pagamento..."
      },
      "connections": ["node_2"]
    },
    {
      "id": "node_4",
      "type": "access",
      "x": 700,
      "y": 150,
      "config": {
        "message": "Seja Bem vindo...",
        "link": "https://seusacessos.shop/..."
      },
      "connections": []
    }
  ],
  "start_node_id": "node_1"
}
```

#### Vantagens ✅
- ✅ **Fluxo condicional completo** - suporta "se pago", "se não pago", etc
- ✅ **Máxima flexibilidade** - qualquer tipo de funil
- ✅ **Lógica de negócio visual** - usuário vê todo o fluxo
- ✅ **Reutilização de blocos** - mesmo bloco pode ter múltiplas entradas
- ✅ **Suporta loops** - ex: Verificar Novamente → Pix

#### Desvantagens ❌
- ⚠️ **Complexidade ALTA** - processamento de condições
- ⚠️ **Frontend MUITO complexo** - editor de fluxograma completo
- ⚠️ **Backend complexo** - executor de fluxo condicional
- ⚠️ **Estado do fluxo** - precisa rastrear em qual nó o usuário está
- ⚠️ **Callbacks condicionais** - `verify_` precisa saber qual nó executar depois

#### Complexidade
- **Frontend:** 🔴 **MUITO ALTA** (5-7 dias)
  - Editor de fluxograma visual (jsPlumb, React Flow, ou similar)
  - Canvas com zoom/pan
  - Drag-and-drop de blocos
  - Criação de conexões
  - Validação de fluxo (ciclos, nós órfãos, etc)
- **Backend:** 🔴 **ALTA** (3-5 dias)
  - Executor de fluxo condicional
  - Gerenciamento de estado por usuário
  - Processamento de condições (payment_status, etc)
  - Integração com callbacks existentes
- **Testes:** 🔴 **ALTA** (2-3 dias)
  - Testar fluxos complexos
  - Testar condições
  - Testar loops
  - Testar edge cases

#### Estimativa: **10-15 dias**

---

### **OPÇÃO 2: Fluxo Sequencial com Conexões Visuais** 🟡 (BALANCEADO)

#### Conceito
Editor visual similar, mas **execução sequencial** (não condicional). Conexões visuais apenas para organização, mas sistema executa na ordem definida.

#### Estrutura de Dados

```json
{
  "flow_enabled": true,
  "flow_steps": [
    {
      "id": "step_1",
      "type": "content",
      "order": 1,
      "config": {
        "media_url": "https://t.me/canal/32",
        "message": "Aquele CONTEUDO PESADO...",
        "buttons": [{"text": "CONHEÇA O VIP", "price": 9.90}]
      },
      "delay_seconds": 0
    },
    {
      "id": "step_2",
      "type": "payment",
      "order": 2,
      "config": {
        "message": "Pague via Pix...",
        "amount": 9.90
      },
      "delay_seconds": 1
    },
    {
      "id": "step_3",
      "type": "message",
      "order": 3,
      "config": {
        "message": "Não foi identificado..."
      },
      "delay_seconds": 0,
      "conditional": false  // Sempre executa após step_2
    }
  ]
}
```

**Mas com visualização de conexões:**
- Interface mostra blocos conectados visualmente
- Mas execução é sequencial (ordem 1, 2, 3...)
- Usuário vê conexões, mas sistema ignora condições

#### Vantagens ✅
- ✅ **Interface visual** - usuário vê conexões
- ✅ **Backend simples** - execução sequencial (como Opção 1 do doc anterior)
- ✅ **Sem estado complexo** - não precisa rastrear nó atual
- ✅ **Compatível com sistema atual** - callbacks funcionam normalmente

#### Desvantagens ❌
- ❌ **Não suporta condições reais** - conexões são apenas visuais
- ❌ **Não suporta loops** - fluxo linear
- ❌ **Não suporta múltiplas saídas** - apenas sequência
- ❌ **Não resolve caso da imagem** - verificar pagamento não funciona como esperado

#### Complexidade
- **Frontend:** 🟡 **MÉDIA-ALTA** (3-4 dias)
  - Editor visual simplificado
  - Conexões visuais (sem lógica)
  - Validação básica
- **Backend:** 🟢 **BAIXA** (1-2 dias)
  - Mesmo código da Opção 1 (sequencial)
  - Apenas ignorar conexões visuais na execução
- **Testes:** 🟢 **BAIXA** (1 dia)

#### Estimativa: **5-7 dias**

**⚠️ PROBLEMA:** Esta opção **NÃO resolve** o caso da imagem (verificar pagamento com retry).

---

### **OPÇÃO 3: Híbrida - Sequencial + Condições Limitadas** 🟡 (RECOMENDADA PARA MVP)

#### Conceito
Fluxo sequencial, mas com **condições limitadas** em tipos específicos de blocos (ex: blocos de "verificação" podem ter 2 saídas: sucesso/falha).

#### Tipos de Blocos com Condições

**1. Bloco "Pagamento" (type: `payment`):**
- Sempre gera PIX
- Sempre mostra botão "Verificar Pagamento"
- **Condições limitadas:**
  - Se `callback = verify_` → Verifica pagamento
  - Se `status == 'paid'` → Executa próximo step
  - Se `status == 'pending'` → Executa step de "Não Pago" (se configurado)

**2. Bloco "Verificação" (type: `verify`):**
- Aguarda callback `verify_{payment_id}`
- **Condições:**
  - Se `payment.status == 'paid'` → Próximo step
  - Se `payment.status == 'pending'` → Step de retry (se configurado)

**3. Bloco "Mensagem" (type: `message`):**
- Sem condições - sempre executa

**4. Bloco "Acesso" (type: `access`):**
- Sem condições - sempre executa (fim do fluxo)

#### Estrutura de Dados

```json
{
  "flow_enabled": true,
  "flow_steps": [
    {
      "id": "step_1",
      "type": "content",
      "order": 1,
      "config": {...},
      "next_step_id": "step_2"
    },
    {
      "id": "step_2",
      "type": "payment",
      "order": 2,
      "config": {
        "amount": 9.90,
        "verify_button": true
      },
      "next_step_id": "step_4",  // Se pago
      "pending_step_id": "step_3"  // Se não pago
    },
    {
      "id": "step_3",
      "type": "message",
      "order": 3,
      "config": {
        "message": "Não foi identificado..."
      },
      "retry_step_id": "step_2"  // Verificar novamente
    },
    {
      "id": "step_4",
      "type": "access",
      "order": 4,
      "config": {
        "link": "https://..."
      }
    }
  ],
  "start_step_id": "step_1"
}
```

#### Processamento

**No `/start`:**
```python
def _handle_start_command(...):
    if config.get('flow_enabled'):
        # Executar fluxo sequencialmente
        self._execute_flow_sequential(
            bot_id, token, config, chat_id, telegram_user_id,
            start_step_id=config['flow_steps'][0]['id']
        )
    else:
        # Usar welcome_message normal
        self._send_welcome_message(...)
```

**No callback `verify_`:**
```python
def _handle_verify_payment(...):
    # Verificar pagamento (código atual)
    if payment.status == 'paid':
        # ✅ Se fluxo ativo, executar próximo step
        if config.get('flow_enabled'):
            step = self._find_step_by_id(config, 'step_4')  # next_step_id
            self._execute_step(step, ...)
        else:
            # Comportamento atual (enviar access_link)
            self._send_access(...)
    else:
        # ✅ Se fluxo ativo, executar pending_step
        if config.get('flow_enabled'):
            step = self._find_step_by_id(config, 'step_3')  # pending_step_id
            self._execute_step(step, ...)
        else:
            # Mensagem de "não identificado"
            self._send_pending_message(...)
```

#### Vantagens ✅
- ✅ **Suporta caso da imagem** - verificar pagamento com retry
- ✅ **Backend moderado** - condições limitadas a tipos específicos
- ✅ **Frontend moderado** - editor visual simplificado
- ✅ **Compatível com sistema atual** - callbacks funcionam
- ✅ **Sem estado complexo** - não precisa rastrear nó atual em cada callback

#### Desvantagens ❌
- ⚠️ **Condições limitadas** - apenas tipos específicos suportam condições
- ⚠️ **Não suporta loops infinitos** - apenas retry de verificação
- ⚠️ **Validação necessária** - garantir que pending_step_id existe

#### Complexidade
- **Frontend:** 🟡 **MÉDIA** (3-4 dias)
  - Editor visual com conexões
  - Tipos especiais para blocos com condições
  - Validação de fluxo
- **Backend:** 🟡 **MÉDIA** (2-3 dias)
  - Executor sequencial
  - Processamento de condições limitadas
  - Integração com callbacks
- **Testes:** 🟡 **MÉDIA** (2 dias)

#### Estimativa: **7-9 dias**

---

## ⚠️ 4. ANÁLISE DE RISCOS

### 4.1 Riscos de Quebrar Sistema Atual

#### 🔴 **RISCO CRÍTICO: Callbacks Existentes**

**Problema:**
- Sistema atual processa callbacks em `_handle_callback_query()`:
  - `verify_` → `_handle_verify_payment()`
  - `buy_` → Gera PIX
  - `bump_yes_` → Gera PIX com order bump
  - `rmkt_` → Gera PIX de remarketing

**Solução:**
- ✅ **Manter callbacks existentes** - não alterar formato
- ✅ **Adicionar lógica condicional** - verificar se `flow_enabled` e decidir próximo step
- ✅ **Fallback para comportamento atual** - se `flow_enabled = False`, usar lógica antiga

**Código Seguro:**
```python
def _handle_verify_payment(...):
    # Código atual (verificar pagamento)
    if payment.status == 'paid':
        # ✅ NOVO: Verificar se fluxo está ativo
        if config.get('flow_enabled') and config.get('flow_steps'):
            # Executar próximo step do fluxo
            next_step = self._get_next_step_for_verify(config, payment)
            if next_step:
                self._execute_step(next_step, ...)
                return
        # ✅ FALLBACK: Comportamento atual (não quebra nada)
        self._send_access(config['access_link'], ...)
    else:
        # ✅ NOVO: Se fluxo ativo, executar pending_step
        if config.get('flow_enabled') and config.get('flow_steps'):
            pending_step = self._get_pending_step_for_verify(config)
            if pending_step:
                self._execute_step(pending_step, ...)
                return
        # ✅ FALLBACK: Comportamento atual
        self._send_pending_message(config['pending_message'], ...)
```

#### 🟡 **RISCO MÉDIO: Estado do Fluxo**

**Problema:**
- Fluxo condicional precisa saber em qual nó o usuário está
- Callback `verify_` precisa saber qual step executar depois

**Soluções:**

**Solução A: Estado no BotUser** (Recomendada)
```python
# Adicionar campo em BotUser
current_flow_step_id = db.Column(db.String(50), nullable=True)

# No callback verify_:
bot_user.current_flow_step_id = 'step_2'
# Próximo step baseado em payment.status
if payment.status == 'paid':
    next_step_id = config['flow_steps'][step_2]['next_step_id']
else:
    next_step_id = config['flow_steps'][step_2]['pending_step_id']
```

**Solução B: Estado no Payment** (Alternativa)
```python
# Adicionar campo em Payment
flow_step_id = db.Column(db.String(50), nullable=True)

# Ao gerar PIX:
payment.flow_step_id = 'step_2'
# No callback verify_, buscar step do payment
```

**Solução C: Sem Estado** (Simplificada - Híbrida)
- ✅ Fluxo sequencial no `/start`
- ✅ Callbacks processam próximo step baseado em `payment.status`
- ✅ Não precisa rastrear estado (mais simples)

**Recomendação:** Solução C (Híbrida) - menos estado, mais robusto

#### 🟡 **RISCO MÉDIO: Backward Compatibility**

**Problema:**
- Bots antigos não têm `flow_enabled`
- Bots antigos não têm `flow_steps`
- Sistema atual precisa funcionar normalmente

**Solução:**
```python
def _handle_start_command(...):
    config = bot.config.to_dict()
    
    # ✅ CHECK: Fluxo ativo?
    flow_enabled = config.get('flow_enabled', False)
    flow_steps = config.get('flow_steps', [])
    
    if flow_enabled and flow_steps and len(flow_steps) > 0:
        # ✅ NOVO: Executar fluxo
        self._execute_flow(...)
    else:
        # ✅ FALLBACK: Comportamento atual (não quebra nada)
        welcome_message = config.get('welcome_message', '')
        if welcome_message:
            self._send_welcome_message(...)
```

**Garantias:**
- ✅ Se `flow_enabled = False` → comportamento atual
- ✅ Se `flow_enabled = True` mas `flow_steps` vazio → comportamento atual
- ✅ Se `welcome_message` existe → sempre funciona (mesmo com fluxo ativo)

#### 🟢 **RISCO BAIXO: Performance**

**Problema:**
- Editor visual pode ser pesado no frontend
- Processamento de fluxo condicional pode adicionar latência

**Soluções:**
- ✅ **Frontend:** Carregar editor apenas quando aba "Fluxo" aberta
- ✅ **Backend:** Processamento sequencial (já otimizado)
- ✅ **Cache:** Não necessário (config já vem do banco)

#### 🟢 **RISCO BAIXO: Validação**

**Problema:**
- Fluxo pode ter conexões inválidas
- Nós órfãos (sem conexões)
- Ciclos infinitos

**Soluções:**
- ✅ **Validação Frontend:** Verificar antes de salvar
- ✅ **Validação Backend:** Validar estrutura JSON
- ✅ **Fallback:** Se fluxo inválido, usar `welcome_message`

---

## 🎯 5. RECOMENDAÇÃO FINAL

### **OPÇÃO 3 (Híbrida)** é a recomendação porque:

1. ✅ **Suporta caso da imagem** - verificar pagamento com retry funciona
2. ✅ **Backend moderado** - condições limitadas a tipos específicos
3. ✅ **Não quebra nada** - fallback para comportamento atual sempre funciona
4. ✅ **Compatível com callbacks** - integração segura com `verify_`, `buy_`, etc
5. ✅ **Sem estado complexo** - não precisa rastrear nó atual em cada callback
6. ✅ **Implementação faseada** - pode começar simples e evoluir

### **Arquitetura Proposta (Opção 3)**

#### Tipos de Blocos Suportados

| Tipo | Ícone | Condições | Descrição |
|------|-------|-----------|-----------|
| **content** | 📸 | Não | Conteúdo inicial (foto, texto, botões) |
| **payment** | 💰 | Sim | Gera PIX (next_step_id se pago, pending_step_id se não pago) |
| **message** | 💬 | Não | Mensagem simples |
| **audio** | 🎵 | Não | Áudio |
| **video** | 🎥 | Não | Vídeo |
| **buttons** | 🔘 | Não | Botões inline |
| **access** | ✅ | Não | Liberar acesso (link final) |

#### Estrutura de Dados (Simplificada)

```json
{
  "flow_enabled": true,
  "flow_steps": [
    {
      "id": "step_1",
      "type": "content",
      "order": 1,
      "config": {
        "media_url": "...",
        "message": "...",
        "buttons": [...]
      },
      "delay_seconds": 0,
      "next_step_id": "step_2"
    },
    {
      "id": "step_2",
      "type": "payment",
      "order": 2,
      "config": {
        "amount": 9.90,
        "message": "Pague via Pix..."
      },
      "delay_seconds": 1,
      "next_step_id": "step_4",      // Se pago
      "pending_step_id": "step_3"    // Se não pago
    },
    {
      "id": "step_3",
      "type": "message",
      "order": 3,
      "config": {
        "message": "Não foi identificado..."
      },
      "delay_seconds": 0,
      "retry_step_id": "step_2"      // Verificar novamente
    },
    {
      "id": "step_4",
      "type": "access",
      "order": 4,
      "config": {
        "message": "Seja Bem vindo...",
        "link": "https://..."
      },
      "delay_seconds": 0
    }
  ]
}
```

#### Processamento

**1. No `/start`:**
```python
if flow_enabled and flow_steps:
    start_step = flow_steps[0]  # Primeiro step
    current_step_id = start_step['id']
    
    # Executar steps sequencialmente até encontrar:
    # - Step tipo "payment" → Para e aguarda callback
    # - Step tipo "access" → Fim do fluxo
    
    for step in sorted(flow_steps, key=lambda x: x['order']):
        if step['type'] == 'payment':
            # Gerar PIX e parar (aguarda callback verify_)
            self._generate_pix(...)
            # Salvar step_id no payment para saber qual step processar depois
            payment.flow_step_id = step['id']
            break
        else:
            # Executar step normalmente
            self._execute_step(step, ...)
```

**2. No callback `verify_`:**
```python
payment = Payment.query.filter_by(payment_id=payment_id).first()
step_id = payment.flow_step_id or None

if step_id and flow_enabled:
    current_step = self._find_step_by_id(flow_steps, step_id)
    
    if payment.status == 'paid':
        # Executar next_step_id
        next_step_id = current_step.get('next_step_id')
        if next_step_id:
            next_step = self._find_step_by_id(flow_steps, next_step_id)
            self._execute_step(next_step, ...)
    else:
        # Executar pending_step_id
        pending_step_id = current_step.get('pending_step_id')
        if pending_step_id:
            pending_step = self._find_step_by_id(flow_steps, pending_step_id)
            self._execute_step(pending_step, ...)
            # Se retry_step_id, aguardar novo callback verify_
```

---

## 📝 6. PLANO DE IMPLEMENTAÇÃO SEGURO

### **FASE 1: Backend - Modelo e Estrutura** ⏱️ 2-3 horas

#### 1.1 Adicionar Campos no Modelo (`models.py`)

```python
# Em BotConfig:
flow_enabled = db.Column(db.Boolean, default=False, index=True)
flow_steps = db.Column(db.Text, nullable=True)  # JSON array

# Em Payment:
flow_step_id = db.Column(db.String(50), nullable=True, index=True)  # Para rastrear step atual
```

**⚠️ CRÍTICO:**
- ✅ Campos **nullable=True** - não quebra bots antigos
- ✅ **default=False** - fluxo desativado por padrão
- ✅ **index=True** - performance em queries

#### 1.2 Migration (`migrations/add_flow_fields.py`)

```python
def migrate():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            
            # Adicionar flow_enabled
            if 'flow_enabled' not in [col['name'] for col in inspector.get_columns('bot_configs')]:
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN flow_enabled BOOLEAN DEFAULT FALSE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled 
                    ON bot_configs(flow_enabled)
                """))
            
            # Adicionar flow_steps
            if 'flow_steps' not in [col['name'] for col in inspector.get_columns('bot_configs')]:
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN flow_steps TEXT
                """))
            
            # Adicionar flow_step_id em payments
            if 'flow_step_id' not in [col['name'] for col in inspector.get_columns('payments')]:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN flow_step_id VARCHAR(50)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id 
                    ON payments(flow_step_id)
                """))
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro: {e}")
            return False
```

#### 1.3 Atualizar `to_dict()` (`models.py`)

```python
def to_dict(self):
    result = {
        # ... campos existentes ...
        'flow_enabled': self.flow_enabled or False,
        'flow_steps': self.get_flow_steps() or []
    }
    return result

def get_flow_steps(self):
    """Retorna flow_steps parseados"""
    if self.flow_steps:
        try:
            return json.loads(self.flow_steps)
        except:
            return []
    return []

def set_flow_steps(self, steps):
    """Define flow_steps"""
    self.flow_steps = json.dumps(steps, ensure_ascii=False)
```

**⚠️ CRÍTICO:**
- ✅ **Retornar sempre** `flow_enabled` e `flow_steps` no `to_dict()`
- ✅ **Valores padrão** - `False` e `[]` se não existirem
- ✅ **Não quebra** - bots antigos continuam funcionando

---

### **FASE 2: Backend - Executor de Fluxo** ⏱️ 4-6 horas

#### 2.1 Nova Função `_execute_flow()` (`bot_manager.py`)

```python
def _execute_flow(self, bot_id: int, token: str, config: Dict[str, Any], 
                  chat_id: int, telegram_user_id: str):
    """
    Executa fluxo visual configurado
    
    ✅ SEGURO: Fallback para welcome_message se fluxo inválido
    """
    try:
        flow_steps = config.get('flow_steps', [])
        if not flow_steps or len(flow_steps) == 0:
            logger.warning("⚠️ Fluxo vazio - usando welcome_message")
            return self._send_welcome_message(...)  # ✅ FALLBACK
        
        # Ordenar steps por order
        sorted_steps = sorted(flow_steps, key=lambda x: x.get('order', 0))
        start_step = sorted_steps[0]
        
        # Executar steps sequencialmente até encontrar payment ou access
        for step in sorted_steps:
            step_type = step.get('type')
            step_config = step.get('config', {})
            delay = step.get('delay_seconds', 0)
            
            if step_type == 'payment':
                # ✅ Gerar PIX e parar (aguarda callback verify_)
                payment_id = self._generate_pix_from_flow(bot_id, token, chat_id, step, telegram_user_id)
                if payment_id:
                    # Salvar flow_step_id no payment
                    from app import app, db
                    from models import Payment
                    with app.app_context():
                        payment = Payment.query.filter_by(payment_id=payment_id).first()
                        if payment:
                            payment.flow_step_id = step.get('id')
                            db.session.commit()
                break  # Para de executar - aguarda callback
            
            elif step_type == 'access':
                # ✅ Liberar acesso e finalizar
                link = step_config.get('link') or config.get('access_link', '')
                message = step_config.get('message', 'Acesso liberado!')
                self.send_telegram_message(token, chat_id, message, buttons=[{
                    'text': 'Acessar',
                    'url': link
                }])
                break  # Fim do fluxo
            
            else:
                # ✅ Executar step normalmente (content, message, audio, video, buttons)
                self._execute_step(step, token, chat_id, delay)
        
    except Exception as e:
        logger.error(f"❌ Erro ao executar fluxo: {e}", exc_info=True)
        # ✅ FALLBACK: Usar welcome_message se fluxo falhar
        return self._send_welcome_message(...)
```

#### 2.2 Função `_execute_step()` (`bot_manager.py`)

```python
def _execute_step(self, step: Dict[str, Any], token: str, chat_id: int, delay: float = 0):
    """Executa um step do fluxo"""
    step_type = step.get('type')
    step_config = step.get('config', {})
    
    if step_type == 'content':
        self.send_funnel_step_sequential(
            token=token,
            chat_id=str(chat_id),
            text=step_config.get('message', ''),
            media_url=step_config.get('media_url'),
            media_type=step_config.get('media_type', 'video'),
            buttons=step_config.get('buttons', []),
            delay_between=delay
        )
    
    elif step_type == 'message':
        self.send_telegram_message(
            token=token,
            chat_id=str(chat_id),
            message=step_config.get('message', ''),
            buttons=step_config.get('buttons', [])
        )
    
    elif step_type == 'audio':
        self.send_audio(token, chat_id, step_config.get('audio_url'))
    
    elif step_type == 'video':
        self.send_video(token, chat_id, step_config.get('media_url'))
    
    elif step_type == 'buttons':
        self.send_buttons(token, chat_id, step_config.get('buttons', []))
    
    # Delay antes do próximo step
    if delay > 0:
        time.sleep(delay)
```

#### 2.3 Modificar `_handle_start_command()` (`bot_manager.py`)

```python
def _handle_start_command(...):
    # ... código existente de reset ...
    
    config = bot.config.to_dict()
    
    # ✅ CHECK: Fluxo ativo?
    flow_enabled = config.get('flow_enabled', False)
    flow_steps = config.get('flow_steps', [])
    
    if flow_enabled and flow_steps and len(flow_steps) > 0:
        # ✅ NOVO: Executar fluxo
        logger.info(f"🎯 Executando fluxo visual ({len(flow_steps)} steps)")
        self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
    else:
        # ✅ FALLBACK: Comportamento atual (não quebra nada)
        logger.info(f"📝 Usando welcome_message (fluxo não ativo)")
        welcome_message = config.get('welcome_message', '')
        if welcome_message:
            self._send_welcome_message(...)
```

**⚠️ CRÍTICO:**
- ✅ **Fallback sempre presente** - se fluxo falhar, usa welcome_message
- ✅ **Validação antes de executar** - verifica se fluxo é válido
- ✅ **Não altera código existente** - apenas adiciona check condicional

#### 2.4 Modificar `_handle_verify_payment()` (`bot_manager.py`)

```python
def _handle_verify_payment(self, bot_id, token, chat_id, payment_id, user_info):
    # ... código existente de verificação ...
    
    # ✅ NOVO: Verificar se fluxo está ativo
    with app.app_context():
        bot = Bot.query.get(bot_id)
        if bot and bot.config:
            config = bot.config.to_dict()
            flow_enabled = config.get('flow_enabled', False)
            flow_steps = config.get('flow_steps', [])
            
            if flow_enabled and flow_steps and payment.flow_step_id:
                # ✅ Buscar step atual do fluxo
                current_step = self._find_step_by_id(flow_steps, payment.flow_step_id)
                
                if payment.status == 'paid' and current_step:
                    # ✅ Executar next_step_id
                    next_step_id = current_step.get('next_step_id')
                    if next_step_id:
                        next_step = self._find_step_by_id(flow_steps, next_step_id)
                        if next_step:
                            self._execute_step(next_step, token, chat_id)
                            return  # ✅ Sair sem executar código antigo
                
                elif payment.status == 'pending' and current_step:
                    # ✅ Executar pending_step_id
                    pending_step_id = current_step.get('pending_step_id')
                    if pending_step_id:
                        pending_step = self._find_step_by_id(flow_steps, pending_step_id)
                        if pending_step:
                            self._execute_step(pending_step, token, chat_id)
                            return  # ✅ Sair sem executar código antigo
    
    # ✅ FALLBACK: Comportamento atual (não quebra nada)
    if payment.status == 'paid':
        self._send_access(config.get('access_link'), ...)
    else:
        self._send_pending_message(config.get('pending_message'), ...)
```

**⚠️ CRÍTICO:**
- ✅ **Fallback sempre presente** - se fluxo não processar, usa código atual
- ✅ **Não altera lógica existente** - apenas adiciona check condicional no início
- ✅ **Compatível com callbacks** - funciona com `verify_` existente

#### 2.5 Função Auxiliar `_find_step_by_id()`

```python
def _find_step_by_id(self, flow_steps: list, step_id: str) -> Dict[str, Any]:
    """Busca step por ID no fluxo"""
    for step in flow_steps:
        if step.get('id') == step_id:
            return step
    return None
```

---

### **FASE 3: Backend - API** ⏱️ 1-2 horas

#### 3.1 Atualizar `GET /api/bots/<id>/config` (`app.py`)

```python
@app.route('/api/bots/<int:bot_id>/config', methods=['GET'])
@login_required
def get_bot_config(bot_id):
    # ... código existente ...
    
    config_dict = bot.config.to_dict()
    
    # ✅ Adicionar flow_enabled e flow_steps (já está no to_dict())
    # Não precisa mudar nada - to_dict() já retorna
    
    return jsonify(config_dict)
```

**⚠️ CRÍTICO:**
- ✅ **Não precisa alterar** - `to_dict()` já retorna novos campos
- ✅ **Backward compatible** - campos vazios se não existirem

#### 3.2 Atualizar `PUT /api/bots/<id>/config` (`app.py`)

```python
@app.route('/api/bots/<int:bot_id>/config', methods=['PUT'])
@login_required
@csrf.exempt
def update_bot_config(bot_id):
    # ... código existente ...
    
    # ✅ NOVO: Salvar flow_enabled e flow_steps
    if 'flow_enabled' in data:
        config.flow_enabled = bool(data['flow_enabled'])
    
    if 'flow_steps' in data:
        flow_steps = data['flow_steps']
        # ✅ Validação básica
        if isinstance(flow_steps, list):
            # Validar estrutura mínima
            for step in flow_steps:
                if not step.get('id') or not step.get('type'):
                    logger.warning(f"⚠️ Step inválido: {step}")
                    continue
            config.set_flow_steps(flow_steps)
        else:
            config.flow_steps = None
    
    # ✅ CRÍTICO: Se flow_enabled=True, desabilitar welcome_message
    if config.flow_enabled and config.flow_steps:
        # Não limpar welcome_message - apenas não usar (fallback se fluxo falhar)
        logger.info("✅ Fluxo ativo - welcome_message será ignorado no /start")
    
    # ... resto do código existente ...
    db.session.commit()
    return jsonify(config.to_dict())
```

**⚠️ CRÍTICO:**
- ✅ **Não limpar welcome_message** - manter como fallback
- ✅ **Validação básica** - evitar fluxos inválidos
- ✅ **Campos opcionais** - não obrigatórios

---

### **FASE 4: Frontend - Editor Visual** ⏱️ 5-7 dias

#### 4.1 Biblioteca Drag-and-Drop

**Opções:**

**Opção A: jsPlumb Community** (Recomendada)
- ✅ Gratuita e open-source
- ✅ Compatível com Alpine.js (Vanilla JS)
- ✅ Suporta conexões entre elementos
- ✅ Suporta múltiplas conexões
- ⚠️ Requer configuração manual

**Opção B: React Flow** (Alternativa)
- ✅ Biblioteca moderna e completa
- ✅ Documentação excelente
- ❌ Requer migração para React (não é Alpine.js)
- ❌ Mais pesada

**Opção C: GoJS** (Alternativa)
- ✅ Biblioteca profissional
- ✅ Suporte comercial
- ❌ Licença paga para comercial
- ❌ Mais pesada

**Recomendação:** jsPlumb Community (gratuita, compatível, suficiente)

#### 4.2 Estrutura do Editor (`templates/bot_config.html`)

**Nova Aba "Fluxo":**
```html
<!-- Tab: Fluxo -->
<button @click="activeTab = 'flow'" 
        :class="{'active': activeTab === 'flow'}"
        class="tab-button">
    <i class="fas fa-project-diagram mr-2"></i>Fluxo
</button>

<div x-show="activeTab === 'flow'" x-cloak>
    <!-- Toggle Ativar Fluxo -->
    <div class="form-group">
        <label class="flex items-center gap-2">
            <input type="checkbox" 
                   x-model="config.flow_enabled"
                   @change="onFlowToggle()"
                   class="toggle">
            <span>Ativar Fluxo Visual</span>
        </label>
        <p class="text-xs text-gray-500 mt-1">
            Quando ativado, desativa automaticamente Boas-vindas
        </p>
    </div>
    
    <!-- Editor Visual -->
    <div x-show="config.flow_enabled" x-cloak>
        <!-- Canvas do Fluxograma -->
        <div id="flow-canvas" 
             class="flow-canvas"
             style="width: 100%; height: 600px; border: 1px solid #333; position: relative;">
            <!-- Blocos serão adicionados aqui dinamicamente -->
        </div>
        
        <!-- Paleta de Blocos -->
        <div class="flow-palette">
            <div class="flow-block-type" data-type="content">📸 Conteúdo</div>
            <div class="flow-block-type" data-type="payment">💰 Pagamento</div>
            <div class="flow-block-type" data-type="message">💬 Mensagem</div>
            <div class="flow-block-type" data-type="audio">🎵 Áudio</div>
            <div class="flow-block-type" data-type="access">✅ Acesso</div>
        </div>
    </div>
</div>
```

#### 4.3 Integração jsPlumb (Alpine.js)

```javascript
// No Alpine.js app:
initFlowEditor() {
    if (typeof jsPlumb === 'undefined') {
        console.error('jsPlumb não carregado');
        return;
    }
    
    const canvas = document.getElementById('flow-canvas');
    const instance = jsPlumb.newInstance({
        container: canvas,
        paintStyle: { stroke: '#ffb800', strokeWidth: 2 },
        endpointStyle: { fill: '#ffb800', radius: 5 },
        connector: ['Bezier', { curviness: 50 }],
        anchors: ['Right', 'Left']
    });
    
    // Carregar steps existentes
    this.config.flow_steps.forEach(step => {
        this.addFlowNode(step, instance);
    });
    
    // Salvar referência do instance
    this.jsPlumbInstance = instance;
},

addFlowNode(step, instance) {
    const node = document.createElement('div');
    node.id = step.id;
    node.className = 'flow-node';
    node.innerHTML = `
        <div class="flow-node-header">
            <span class="flow-node-icon">${this.getNodeIcon(step.type)}</span>
            <span class="flow-node-title">${this.getNodeTitle(step.type)}</span>
            <button @click="removeFlowNode('${step.id}')" class="flow-node-remove">×</button>
        </div>
        <div class="flow-node-content">
            ${this.getNodePreview(step)}
        </div>
    `;
    
    // Posicionar no canvas
    node.style.left = `${step.x || 100}px`;
    node.style.top = `${step.y || 100}px`;
    
    document.getElementById('flow-canvas').appendChild(node);
    
    // Configurar jsPlumb
    instance.makeSource(node, {
        filter: '.flow-node-connection-source',
        endpoint: ['Dot', { radius: 5 }],
        connector: ['Bezier', { curviness: 50 }]
    });
    
    instance.makeTarget(node, {
        dropOptions: { hoverClass: 'flow-node-hover' },
        endpoint: ['Dot', { radius: 5 }]
    });
    
    // Restaurar conexões
    if (step.next_step_id) {
        instance.connect({
            source: node.id,
            target: step.next_step_id
        });
    }
    if (step.pending_step_id) {
        instance.connect({
            source: node.id,
            target: step.pending_step_id,
            paintStyle: { stroke: '#ef4444', strokeWidth: 2 }  // Vermelho para "não pago"
        });
    }
}
```

---

### **FASE 5: Testes** ⏱️ 2-3 dias

#### 5.1 Testes de Backward Compatibility

1. ✅ **Bot sem fluxo** → Deve usar welcome_message normalmente
2. ✅ **Bot com flow_enabled=False** → Deve usar welcome_message normalmente
3. ✅ **Bot com flow_enabled=True mas flow_steps vazio** → Deve usar welcome_message
4. ✅ **Bot com fluxo inválido** → Deve usar welcome_message (fallback)

#### 5.2 Testes de Fluxo Visual

1. ✅ **Fluxo simples:** Conteúdo → Pagamento → Acesso
2. ✅ **Fluxo com retry:** Conteúdo → Pagamento → Não Pago → Verificar Novamente
3. ✅ **Fluxo múltiplos áudios:** Conteúdo → Áudio 1 → Áudio 2 → Áudio 3 → Pagamento
4. ✅ **Fluxo condicional:** Pagamento → (Pago → Acesso) | (Não Pago → Retry)

#### 5.3 Testes de Callbacks

1. ✅ **verify_ com fluxo ativo** → Deve executar próximo step do fluxo
2. ✅ **verify_ sem fluxo** → Deve usar comportamento atual
3. ✅ **buy_ com fluxo ativo** → Deve gerar PIX e salvar flow_step_id
4. ✅ **buy_ sem fluxo** → Deve usar comportamento atual

---

## ⚠️ 7. GARANTIAS DE SEGURANÇA

### 7.1 Checklist de Não-Quebrar

- [x] ✅ **Fallback sempre presente** - se fluxo falhar, usa welcome_message
- [x] ✅ **Campos nullable** - não quebra bots antigos
- [x] ✅ **Valores padrão** - `flow_enabled=False`, `flow_steps=[]`
- [x] ✅ **Validação antes de executar** - verifica se fluxo é válido
- [x] ✅ **Não altera código existente** - apenas adiciona checks condicionais
- [x] ✅ **Callbacks compatíveis** - funciona com callbacks existentes
- [x] ✅ **Backward compatible** - bots antigos continuam funcionando
- [x] ✅ **Error handling** - try/catch com fallback em todas as funções

### 7.2 Pontos de Teste Críticos

**Antes de fazer deploy:**

1. ✅ Testar bot antigo (sem fluxo) - deve funcionar normalmente
2. ✅ Testar bot novo (com fluxo) - deve executar fluxo
3. ✅ Testar callback `verify_` sem fluxo - deve usar código atual
4. ✅ Testar callback `verify_` com fluxo - deve executar próximo step
5. ✅ Testar fluxo inválido - deve usar fallback
6. ✅ Testar fluxo vazio - deve usar fallback
7. ✅ Testar migration - não deve quebrar dados existentes

---

## 📊 8. ESTIMATIVA FINAL

### **Opção 3 (Híbrida) - Recomendada**

| Fase | Tarefa | Tempo Estimado |
|------|--------|----------------|
| **FASE 1** | Backend - Modelo e Migration | 2-3 horas |
| **FASE 2** | Backend - Executor de Fluxo | 4-6 horas |
| **FASE 3** | Backend - API | 1-2 horas |
| **FASE 4** | Frontend - Editor Visual | 5-7 dias |
| **FASE 5** | Testes | 2-3 dias |
| **TOTAL** | | **8-12 dias** |

### **Opção 1 (Condicional Completo) - Alternativa**

| Fase | Tarefa | Tempo Estimado |
|------|--------|----------------|
| **FASE 1** | Backend - Modelo e Migration | 2-3 horas |
| **FASE 2** | Backend - Executor Condicional | 5-7 dias |
| **FASE 3** | Backend - API | 1-2 horas |
| **FASE 4** | Frontend - Editor Completo | 5-7 dias |
| **FASE 5** | Testes | 2-3 dias |
| **TOTAL** | | **12-17 dias** |

---

## ✅ 9. CONCLUSÃO E RECOMENDAÇÃO

### **RECOMENDAÇÃO FINAL: OPÇÃO 3 (Híbrida)**

**Por quê:**

1. ✅ **Suporta caso da imagem** - verificar pagamento com retry funciona
2. ✅ **Não quebra sistema atual** - fallback sempre presente
3. ✅ **Implementação moderada** - 8-12 dias vs 12-17 dias da Opção 1
4. ✅ **Backend simplificado** - condições limitadas a tipos específicos
5. ✅ **Frontend moderado** - editor visual simplificado
6. ✅ **Extensível** - pode evoluir para Opção 1 depois

### **Próximos Passos:**

1. ✅ **Aprovar Opção 3** (Híbrida)
2. ✅ **Criar issues detalhadas** no projeto
3. ✅ **Iniciar FASE 1** (Backend - Modelo)
4. ✅ **Testar backward compatibility** antes de continuar
5. ✅ **Implementar FASE 2-5** sequencialmente
6. ✅ **Testes completos** antes de deploy

---

**Última atualização:** 2025-01-18  
**Status:** ✅ Aguardando aprovação para iniciar implementação

