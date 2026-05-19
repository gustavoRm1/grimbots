# 🔥 ARQUITETURA BACKEND - FLOW ENGINE V∞

## 📋 SUMÁRIO EXECUTIVO

Este documento descreve **EXATAMENTE** como o backend processa o fluxo visual, desde o salvamento até a execução, incluindo todas as decisões de roteamento e interpretação de connections.

---

## 1. 📦 ESTRUTURA DE DADOS - COMO O BACKEND ESPERA RECEBER

### 1.1 Formato de `flow_steps` (JSON Array)

```json
[
  {
    "id": "node-123",
    "type": "message",
    "order": 1,
    "position": { "x": 120, "y": 40 },
    "title": "Mensagem de Boas-vindas",
    "config": {
      "message": "Olá! Bem-vindo ao nosso bot.",
      "media_url": "https://...",
      "media_type": "video",
      "custom_buttons": [
        {
          "text": "Quero comprar",
          "target_step": "node-456"
        }
      ]
    },
    "connections": {
      "next": "node-456",
      "pending": null,
      "retry": null
    },
    "conditions": [],
    "delay_seconds": 0
  },
  {
    "id": "node-456",
    "type": "payment",
    "order": 2,
    "position": { "x": 400, "y": 40 },
    "title": "Pagamento PIX",
    "config": {
      "product_name": "Produto Premium",
      "price": 97.00,
      "amount": 97.00
    },
    "connections": {
      "next": "node-789",
      "pending": "node-999"
    },
    "conditions": [],
    "delay_seconds": 0
  }
]
```

### 1.2 Campos Obrigatórios

- `id` (string): ID único do step (ex: "node-123", "step_abc")
- `type` (string): Tipo do step (`message`, `payment`, `access`, `button`, `condition`, `delay`, `end`)
- `order` (number): Ordem do step (opcional, usado para fallback de step inicial)

### 1.3 Campos Opcionais

- `title` (string): Título do step (exibido no front-end)
- `position` (object): `{x: number, y: number}` (usado apenas no front-end)
- `config` (object): Configuração específica do step
- `connections` (object): Conexões para próximos steps
- `conditions` (array): Condições para branches condicionais
- `delay_seconds` (number): Delay antes de executar o step

### 1.4 Estrutura de `connections`

```json
{
  "next": "node-456",        // Próximo step (execução sequencial)
  "pending": "node-999",     // Step se pagamento pendente (apenas para type=payment)
  "retry": "node-456"        // Step de retry (comportamento antigo, mantido para compatibilidade)
}
```

**IMPORTANTE:**
- `next`: Usado para continuar fluxo após step normal (message, access, etc)
- `pending`: Usado APENAS para steps `payment` quando pagamento não foi aprovado
- `retry`: Comportamento legado, mantido para compatibilidade

### 1.5 Estrutura de `config` por Tipo

#### `type: "message"`
```json
{
  "message": "Texto da mensagem",
  "media_url": "https://...",
  "media_type": "video|photo",
  "audio_url": "https://...",
  "custom_buttons": [
    {
      "text": "Botão 1",
      "target_step": "node-456"
    }
  ]
}
```

#### `type: "payment"`
```json
{
  "product_name": "Nome do Produto",
  "price": 97.00,
  "amount": 97.00,
  "description": "Descrição do produto"
}
```

#### `type: "access"`
```json
{
  "link": "https://...",
  "message": "Acesso liberado!"
}
```

---

## 2. 💾 SALVAMENTO - Como o Backend Salva `flow_steps`

### 2.1 Endpoint: `PUT /api/bots/<bot_id>/config`

**Arquivo:** `app.py` (linha ~5659)

**Fluxo de Salvamento:**

```python
# 1. Recebe dados do front-end
data = request.get_json()

# 2. Validação de estrutura
if 'flow_steps' in data:
    flow_steps = data['flow_steps']
    
    if isinstance(flow_steps, list):
        # Validar cada step
        for step in flow_steps:
            # Validar campos obrigatórios
            if not step.get('id') or not step.get('type'):
                # Erro: step inválido
            
            # Validar connections para payment steps
            if step.get('type') == 'payment':
                connections = step.get('connections', {})
                if not connections.get('next') and not connections.get('pending'):
                    # Erro: payment step sem conexões
        
        # Salvar via model
        config.set_flow_steps(flow_steps)
    else:
        config.flow_steps = None
```

### 2.2 Model: `BotConfig.set_flow_steps()`

**Arquivo:** `models.py` (linha ~380)

```python
def set_flow_steps(self, steps):
    """Define flow_steps"""
    try:
        if steps:
            # Serializa para JSON string
            self.flow_steps = json.dumps(steps, ensure_ascii=False)
        else:
            self.flow_steps = None
    except (TypeError, ValueError) as e:
        logger.error(f"Erro ao serializar flow_steps: {e}")
        raise ValueError(f"Erro ao salvar flow_steps: {e}")
```

**IMPORTANTE:**
- `flow_steps` é salvo como **JSON string** no banco (coluna `Text`)
- Front-end pode enviar como array ou string JSON
- Backend sempre converte para string antes de salvar

### 2.3 Campo `flow_start_step_id`

```python
if 'flow_start_step_id' in data:
    flow_start_step_id = data.get('flow_start_step_id')
    if flow_start_step_id:
        # Validar se step existe
        flow_steps = config.get_flow_steps()
        step_exists = any(step.get('id') == flow_start_step_id for step in flow_steps)
        if step_exists:
            config.flow_start_step_id = flow_start_step_id
        else:
            config.flow_start_step_id = None
```

**Auto-definição:**
- Se `flow_enabled=True` e não tem `flow_start_step_id`, o backend auto-define:
  1. Primeiro step com `order=1`
  2. Se não encontrar, primeiro step da lista (menor order)

---

## 3. 📖 LEITURA - Como o Backend Lê `flow_steps`

### 3.1 Endpoint: `GET /api/bots/<bot_id>/config`

**Arquivo:** `app.py` (linha ~5565)

```python
config_dict = bot.config.to_dict()
return jsonify(config_dict)
```

### 3.2 Model: `BotConfig.to_dict()`

**Arquivo:** `models.py` (linha ~391)

```python
def to_dict(self):
    return {
        # ... outros campos ...
        'flow_enabled': self.flow_enabled or False,
        'flow_steps': self.get_flow_steps(),  # Retorna array parseado
        'flow_start_step_id': self.flow_start_step_id
    }
```

### 3.3 Model: `BotConfig.get_flow_steps()`

**Arquivo:** `models.py` (linha ~370)

```python
def get_flow_steps(self):
    """Retorna flow_steps parseados"""
    if self.flow_steps:
        try:
            return json.loads(self.flow_steps)  # Parse de JSON string para array
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Erro ao parsear flow_steps: {e}")
            return []
    return []
```

**IMPORTANTE:**
- Backend sempre retorna `flow_steps` como **array** para o front-end
- Se houver erro no parse, retorna array vazio `[]`

---

## 4. 🎯 ROTEAMENTO - Como Decide Entre Flow vs Traditional

### 4.1 MessageRouter V8 - Ponto de Entrada Único

**Arquivo:** `flow_engine_router_v8.py` (linha ~197)

**Fluxo de Decisão:**

```python
def process_message(...):
    # 1. Adquirir lock atômico (Redis)
    lock_key = f"bot:{bot_id}:chat:{chat_id}"
    if not self.acquire_lock(lock_key):
        return {'processed': False, 'reason': 'lock_not_acquired'}
    
    try:
        # 2. Verificar se flow está ativo
        is_flow_active = self.check_flow_active_atomic(bot_id, config)
        
        if is_flow_active:
            # 🔥 FLOW ENGINE ATIVO
            return self._process_via_flow_engine(...)
        else:
            # 🔥 TRADITIONAL ENGINE ATIVO
            return self._process_via_traditional_engine(...)
    finally:
        # 3. Liberar lock
        self.release_lock(lock_key)
```

### 4.2 Verificação de Flow Ativo

**Arquivo:** `flow_engine_router_v8.py` (linha ~145)

```python
def check_flow_active_atomic(self, bot_id, config):
    """Verifica se flow está ativo de forma atômica"""
    
    # Parsear flow_enabled (pode vir como string ou boolean)
    flow_enabled_raw = config.get('flow_enabled', False)
    if isinstance(flow_enabled_raw, str):
        flow_enabled = flow_enabled_raw.lower().strip() in ('true', '1', 'yes', 'on', 'enabled')
    elif isinstance(flow_enabled_raw, bool):
        flow_enabled = flow_enabled_raw
    else:
        flow_enabled = False
    
    # Verificar se tem steps
    flow_steps = config.get('flow_steps', [])
    if isinstance(flow_steps, str):
        import json
        flow_steps = json.loads(flow_steps)
    
    # Flow está ativo SE:
    # 1. flow_enabled = True
    # 2. flow_steps existe e não está vazio
    is_active = flow_enabled is True and flow_steps and isinstance(flow_steps, list) and len(flow_steps) > 0
    
    return is_active
```

**REGRA CRÍTICA:**
- Se `flow_enabled=True` E `flow_steps` não está vazio → **FLOW ENGINE**
- Caso contrário → **TRADITIONAL ENGINE**

### 4.3 Processamento via Flow Engine

**Arquivo:** `flow_engine_router_v8.py` (linha ~268)

```python
def _process_via_flow_engine(...):
    """Processa mensagem via Flow Engine - BLOQUEIA 100% do sistema tradicional"""
    
    if message_type == "start":
        # Comando /start: reiniciar flow do início
        self.bot_manager._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
        return {'processed': True, 'engine': 'flow', 'action': 'flow_restarted'}
    
    elif message_type == "callback":
        # Callback query: processar botão/clique
        # O Flow Engine já processa callbacks internamente
        return {'processed': True, 'engine': 'flow', 'action': 'callback_processed', 'blocked_traditional': True}
    
    elif message_type == "text":
        # Mensagem de texto: buscar step atual e processar
        current_step_id = redis.get(f"flow_current_step:{bot_id}:{telegram_user_id}")
        if current_step_id:
            # Processar no contexto do step atual
            return {'processed': True, 'engine': 'flow', 'current_step': current_step_id}
        else:
            # Iniciar flow do início
            self.bot_manager._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
            return {'processed': True, 'engine': 'flow', 'action': 'flow_started'}
```

### 4.4 Processamento via Traditional Engine

**Arquivo:** `flow_engine_router_v8.py` (linha ~355)

```python
def _process_via_traditional_engine(...):
    """Processa mensagem via sistema tradicional"""
    
    if message_type == "start":
        # Comando /start: enviar welcome_message
        self.bot_manager._handle_start_command(...)
        return {'processed': True, 'engine': 'traditional', 'action': 'welcome_sent'}
    
    elif message_type == "callback":
        # Callback query: processar botões tradicionais (buy_, verify_, etc)
        self.bot_manager._handle_callback_query(...)
        return {'processed': True, 'engine': 'traditional', 'action': 'callback_processed'}
    
    elif message_type == "text":
        # Mensagem de texto: processar normalmente
        self.bot_manager._handle_text_message(...)
        return {'processed': True, 'engine': 'traditional', 'action': 'text_processed'}
```

---

## 5. 🚀 EXECUÇÃO DO FLUXO - Como o Backend Executa Steps

### 5.1 Inicialização do Fluxo: `_execute_flow()`

**Arquivo:** `bot_manager.py` (linha ~3039)

**Fluxo:**

```python
def _execute_flow(bot_id, token, config, chat_id, telegram_user_id):
    """Executa fluxo visual configurado"""
    
    # 1. Parsear flow_steps (pode vir como string JSON ou array)
    flow_steps_raw = config.get('flow_steps', [])
    if isinstance(flow_steps_raw, str):
        flow_steps = json.loads(flow_steps_raw)
    else:
        flow_steps = flow_steps_raw
    
    # 2. Criar snapshot da config (evita mudanças durante execução)
    flow_snapshot = {
        'flow_steps': json.dumps(flow_steps),
        'flow_start_step_id': config.get('flow_start_step_id'),
        'flow_enabled': config.get('flow_enabled', False),
        'main_buttons': json.dumps(config.get('main_buttons', [])),
        'redirect_buttons': json.dumps(config.get('redirect_buttons', [])),
        'snapshot_timestamp': int(time.time())
    }
    
    # Salvar snapshot no Redis (expira em 24h)
    redis.set(f"flow_snapshot:{bot_id}:{telegram_user_id}", json.dumps(flow_snapshot), ex=86400)
    
    # 3. Identificar step inicial
    start_step_id = config.get('flow_start_step_id')
    if not start_step_id:
        # Fallback: step com order=1 ou primeiro step
        sorted_steps = sorted(flow_steps, key=lambda x: x.get('order', 0))
        start_step = sorted_steps[0] if sorted_steps else None
        start_step_id = start_step.get('id') if start_step else None
    
    # 4. Executar recursivamente a partir do step inicial
    self._execute_flow_recursive(
        bot_id, token, config, chat_id, telegram_user_id,
        str(start_step_id),
        recursion_depth=0,
        visited_steps=set(),
        flow_snapshot=flow_snapshot
    )
```

### 5.2 Execução Recursiva: `_execute_flow_recursive()`

**Arquivo:** `bot_manager.py` (linha ~3181)

**Fluxo Completo:**

```python
def _execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, step_id, 
                           recursion_depth=0, visited_steps=None, flow_snapshot=None):
    """Executa step recursivamente"""
    
    # 1. Proteção contra loops infinitos
    if recursion_depth >= 50:
        return  # Máximo 50 steps
    
    # 2. Detectar loops circulares
    if step_id in visited_steps:
        logger.error(f"Loop circular detectado: {step_id}")
        return
    
    visited_steps.add(step_id)
    
    # 3. Buscar step no fluxo
    flow_steps = config.get('flow_steps', [])
    if isinstance(flow_steps, str):
        flow_steps = json.loads(flow_steps)
    
    step = self._find_step_by_id(flow_steps, step_id)
    if not step:
        logger.error(f"Step {step_id} não encontrado")
        return
    
    # 4. Extrair dados do step
    step_type = step.get('type')
    step_config = step.get('config', {})
    delay = step.get('delay_seconds', 0)
    connections = step.get('connections', {})
    
    # 5. Executar step baseado no tipo
    if step_type == 'payment':
        # Gerar PIX e pausar fluxo (aguarda callback verify_)
        pix_data = self._generate_pix_payment(...)
        payment.flow_step_id = step_id  # Salvar referência
        return  # Para aqui, aguarda callback
    
    elif step_type == 'access':
        # Enviar link de acesso e finalizar
        self.send_telegram_message(...)
        return  # Fim do fluxo
    
    else:
        # Executar step normalmente (message, audio, video, etc)
        self._execute_step(step, token, chat_id, delay, config=config)
        
        # 6. Verificar condições (se houver)
        conditions = step.get('conditions', [])
        if conditions:
            # Aguardar input do usuário (não continuar automaticamente)
            # Salvar step atual no Redis
            redis.setex(f"flow_current_step:{bot_id}:{telegram_user_id}", 7200, step_id)
            return  # Pausa aqui
    
        # 7. Continuar para próximo step (se houver conexão 'next')
        next_step_id = connections.get('next')
        if next_step_id:
            self._execute_flow_recursive(
                bot_id, token, config, chat_id, telegram_user_id,
                next_step_id,
                recursion_depth=recursion_depth + 1,
                visited_steps=visited_steps.copy(),
                flow_snapshot=flow_snapshot
            )
        else:
            # Sem próximo step - fim do fluxo
            # Limpar estado do Redis
            redis.delete(f"flow_current_step:{bot_id}:{telegram_user_id}")
    
    # 8. Salvar estado do flow no Redis após cada step (24h TTL)
    redis.setex(f"flow_current_step:{bot_id}:{telegram_user_id}", 86400, step_id)
    
    # 9. Remover step dos visitados (permite revisitar em branches diferentes)
    visited_steps.discard(step_id)
```

### 5.3 Interpretação de `connections`

**Arquivo:** `bot_manager.py` (linha ~3281)

```python
connections = step.get('connections', {})

# Para steps normais (message, access, etc):
next_step_id = connections.get('next')
if next_step_id:
    # Continuar para próximo step
    self._execute_flow_recursive(..., next_step_id, ...)

# Para steps payment:
if step_type == 'payment':
    # Após verificar pagamento:
    if payment.status == 'paid':
        next_step_id = connections.get('next')
    else:
        next_step_id = connections.get('pending')
    
    if next_step_id:
        self._execute_flow_recursive(..., next_step_id, ...)
```

**IMPORTANTE:**
- `connections.next`: Próximo step após execução normal
- `connections.pending`: Próximo step se pagamento não aprovado (apenas para `type=payment`)
- `connections.retry`: Comportamento legado (mantido para compatibilidade)

---

## 6. 💳 PROCESSAMENTO DE PAGAMENTO - Integração com Flow

### 6.1 Geração de PIX no Flow

**Arquivo:** `bot_manager.py` (linha ~3294)

```python
if step_type == 'payment':
    # Gerar PIX
    pix_data = self._generate_pix_payment(...)
    
    # Salvar flow_step_id no payment
    payment_id = pix_data.get('payment_id')
    payment.flow_step_id = step_id  # CRÍTICO: vincular payment ao step
    
    # Enviar mensagem de PIX
    self.send_telegram_message(...)
    
    return  # Para aqui, aguarda callback verify_
```

### 6.2 Verificação de Pagamento: `_handle_verify_payment()`

**Arquivo:** `bot_manager.py` (linha ~2595)

```python
def _handle_verify_payment(self, bot, payment, chat_id, telegram_user_id):
    """Handler final para pagamentos integrados ao Flow Engine"""
    
    # 1. Verificar status do pagamento
    status = self._verify_payment_gateway(payment)
    paid = (status == "paid")
    
    # 2. Atualizar payment
    payment.status = status
    db.session.commit()
    
    # 3. INTEGRAÇÃO COM FLOW ENGINE
    if payment.flow_step_id:
        config = bot.config.to_dict()
        flow_enabled = config.get("flow_enabled", False)
        steps = json.loads(config.get("flow_steps", "[]"))
        
        if flow_enabled and steps:
            # Encontrar step onde o payment foi iniciado
            step = next((s for s in steps if s["id"] == payment.flow_step_id), None)
            
            if step:
                connections = step.get("connections", {})
                
                # Se pagamento aprovado → seguir para next
                if paid:
                    next_step = connections.get("next")
                # Se pagamento pendente → seguir para pending
                else:
                    next_step = connections.get("pending")
                
                # EXECUTAR PRÓXIMO STEP
                if next_step:
                    return self._execute_flow_recursive(
                        bot.id, bot.token, config,
                        chat_id, telegram_user_id,
                        next_step,
                        recursion_depth=0,
                        visited_steps=set(),
                        flow_snapshot=None
                    )
    
    # 4. FALLBACK → LÓGICA TRADICIONAL
    if paid:
        return self._send_access(bot, payment, chat_id)
    else:
        return self._send_pending_message(bot, payment, chat_id)
```

---

## 7. 🔘 PROCESSAMENTO DE CALLBACKS - Botões Customizados

### 7.1 Callback de Botão Customizado: `flow_{stepId}_{index}`

**Arquivo:** `bot_manager.py` (linha ~4095)

```python
def _handle_callback_query(self, bot_id, token, config, callback):
    callback_data = callback.get('data', '')
    
    # ✅ V∞: Callback de Botão Customizado do Flow
    if callback_data.startswith('flow_') and not callback_data.startswith('flow_step_'):
        # Parse: flow_{stepId}_{index}
        parts = callback_data.split('_', 2)  # ['flow', '{stepId}', '{index}']
        step_id = parts[1]
        btn_index = int(parts[2])
        
        # Buscar step e botão
        flow_steps = config.get('flow_steps', [])
        step = self._find_step_by_id(flow_steps, step_id)
        custom_buttons = step.get('config', {}).get('custom_buttons', [])
        target_step = custom_buttons[btn_index].get('target_step')
        
        # Executar step destino
        self._execute_flow_recursive(
            bot_id, token, config,
            chat_id, telegram_user_id,
            target_step,
            recursion_depth=0,
            visited_steps=set(),
            flow_snapshot=None
        )
        return
```

**Formato do Callback:**
- `flow_{stepId}_{index}`: Exemplo: `flow_node-123_0`
- `stepId`: ID do step que contém o botão
- `index`: Índice do botão no array `custom_buttons`

### 7.2 Callback Compatibilidade: `flow_step_{step_id}_btn_{idx}`

**Arquivo:** `bot_manager.py` (linha ~4167)

```python
if callback_data.startswith('flow_step_'):
    # Formato: flow_step_{step_id}_btn_{idx}
    callback_without_prefix = callback_data.replace('flow_step_', '')
    
    if '_btn_' in callback_without_prefix:
        parts = callback_without_prefix.rsplit('_btn_', 1)
        source_step_id = parts[0]
        btn_idx = int(parts[1])
        
        # Buscar target_step do botão
        step = self._find_step_by_id(flow_steps, source_step_id)
        custom_buttons = step.get('config', {}).get('custom_buttons', [])
        target_step_id = custom_buttons[btn_idx].get('target_step')
        
        # Executar step destino
        self._execute_flow_recursive(..., target_step_id, ...)
```

---

## 8. 📝 SISTEMA TRADICIONAL - Como Funciona

### 8.1 Comando `/start` (Traditional)

**Arquivo:** `bot_manager.py` (linha ~3766)

```python
def _handle_start_command(self, bot_id, token, config, chat_id, message, start_param):
    """Processa comando /start"""
    
    # 1. Resetar funil do usuário
    self._reset_user_funnel(bot_id, chat_id, telegram_user_id)
    
    # 2. Verificar se flow está ativo
    is_flow_active = checkActiveFlow(config)
    
    if is_flow_active:
        # 🔥 FLUXO VISUAL ATIVO - Executar fluxo
        self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
        should_send_welcome = False  # BLOQUEAR welcome_message
    else:
        # 🔥 TRADITIONAL ENGINE - Enviar welcome_message
        welcome_message = config.get('welcome_message', '')
        welcome_media_url = config.get('welcome_media_url', '')
        main_buttons = config.get('main_buttons', [])
        
        self.send_funnel_step_sequential(
            text=welcome_message,
            media_url=welcome_media_url,
            buttons=main_buttons
        )
        should_send_welcome = True
```

**REGRA CRÍTICA:**
- Se `flow_enabled=True` → **NUNCA** envia `welcome_message`
- Se `flow_enabled=False` → Envia `welcome_message` normalmente

### 8.2 Mensagem de Texto (Traditional)

**Arquivo:** `bot_manager.py` (linha ~1421)

```python
def _handle_text_message(self, bot_id, token, config, chat_id, message):
    """Processa mensagem de texto"""
    
    text = message.get('text', '').strip()
    
    # Verificar se há conversa ativa
    has_active_conversation = ...
    
    if has_active_conversation:
        # Verificar se há step com condições aguardando resposta
        current_step_id = self._get_current_step_atomic(bot_id, telegram_user_id)
        
        if current_step_id:
            # Avaliar condições do step atual
            next_step_id = self._evaluate_conditions(current_step, user_input=text, ...)
            
            if next_step_id:
                # Continuar fluxo no próximo step
                self._execute_flow_recursive(..., next_step_id, ...)
                return
    else:
        # Sem conversa ativa - reiniciar funil
        self._send_welcome_message_only(...)
```

---

## 9. 🔄 PERSISTÊNCIA DE ESTADO - Redis

### 9.1 Estado Atual do Flow

**Chave Redis:** `flow_current_step:{bot_id}:{telegram_user_id}`

**Valor:** `step_id` (string)

**TTL:** 24 horas (86400 segundos)

**Salvamento:**
```python
# Após cada step executado
redis.setex(f"flow_current_step:{bot_id}:{telegram_user_id}", 86400, step_id)
```

**Leitura:**
```python
# Para continuar fluxo
step_id = redis.get(f"flow_current_step:{bot_id}:{telegram_user_id}")
if step_id:
    # Continuar fluxo do step atual
    self._execute_flow_recursive(..., step_id.decode(), ...)
```

### 9.2 Snapshot da Config

**Chave Redis:** `flow_snapshot:{bot_id}:{telegram_user_id}`

**Valor:** JSON string com snapshot da config

**TTL:** 24 horas

**Estrutura:**
```json
{
  "flow_steps": "[{...}]",
  "flow_start_step_id": "node-123",
  "flow_enabled": true,
  "main_buttons": "[{...}]",
  "redirect_buttons": "[{...}]",
  "snapshot_timestamp": 1234567890
}
```

**Uso:**
- Evita mudanças na config durante execução do fluxo
- Garante consistência mesmo se config for alterada no meio do fluxo

---

## 10. ✅ VALIDAÇÕES E REGRAS CRÍTICAS

### 10.1 Validações no Salvamento

1. **Step deve ter `id` e `type`**
2. **Payment step deve ter conexões obrigatórias:**
   - `connections.next` OU `connections.pending` (pelo menos uma)
3. **Conexões devem apontar para steps existentes** (aviso, não bloqueia)
4. **IDs de steps devem ser únicos**

### 10.2 Regras de Execução

1. **Máximo 50 steps** (proteção contra loops infinitos)
2. **Detecção de loops circulares** (via `visited_steps`)
3. **Payment pausa fluxo** (aguarda callback `verify_`)
4. **Condições pausam fluxo** (aguardam input do usuário)
5. **Access finaliza fluxo** (limpa estado do Redis)

### 10.3 Regras de Roteamento

1. **Se `flow_enabled=True` E `flow_steps` não vazio → FLOW ENGINE**
2. **Caso contrário → TRADITIONAL ENGINE**
3. **Flow Engine BLOQUEIA 100% do sistema tradicional**
4. **Traditional Engine funciona normalmente quando flow está desativado**

---

## 11. 📊 EXEMPLO COMPLETO DE FLUXO

### 11.1 Estrutura de Steps

```json
[
  {
    "id": "step_1",
    "type": "message",
    "order": 1,
    "config": {
      "message": "Bem-vindo! Escolha uma opção:",
      "custom_buttons": [
        {"text": "Quero comprar", "target_step": "step_2"},
        {"text": "Ver mais", "target_step": "step_3"}
      ]
    },
    "connections": {},
    "conditions": []
  },
  {
    "id": "step_2",
    "type": "payment",
    "order": 2,
    "config": {
      "product_name": "Produto Premium",
      "price": 97.00
    },
    "connections": {
      "next": "step_4",
      "pending": "step_5"
    }
  },
  {
    "id": "step_4",
    "type": "access",
    "order": 3,
    "config": {
      "link": "https://...",
      "message": "Acesso liberado!"
    },
    "connections": {}
  }
]
```

### 11.2 Fluxo de Execução

1. **Usuário envia `/start`**
   - Router verifica: `flow_enabled=True` → Flow Engine
   - `_execute_flow()` identifica `step_1` como inicial
   - `_execute_flow_recursive()` executa `step_1`
   - Envia mensagem com botões customizados
   - Salva estado: `flow_current_step:bot:user = "step_1"`

2. **Usuário clica em "Quero comprar"**
   - Callback: `flow_step_1_btn_0`
   - `_handle_callback_query()` processa
   - `_execute_flow_recursive()` executa `step_2` (payment)
   - Gera PIX e pausa fluxo
   - Salva `payment.flow_step_id = "step_2"`

3. **Usuário clica em "Verificar Pagamento"**
   - Callback: `verify_{payment_id}`
   - `_handle_verify_payment()` verifica status
   - Se pago → `connections.next = "step_4"`
   - Se pendente → `connections.pending = "step_5"`
   - `_execute_flow_recursive()` continua no step apropriado

4. **Fluxo finaliza em `step_4` (access)**
   - Envia link de acesso
   - Limpa estado do Redis
   - Fim do fluxo

---

## 12. 🔥 PONTOS CRÍTICOS PARA INTEGRAÇÃO

### 12.1 Formato Esperado pelo Backend

**Front-end deve enviar:**
```json
{
  "flow_steps": [
    {
      "id": "node-123",
      "type": "message",
      "order": 1,
      "position": {"x": 120, "y": 40},
      "title": "Mensagem",
      "config": {...},
      "connections": {
        "next": "node-456"
      }
    }
  ],
  "flow_start_step_id": "node-123",
  "flow_enabled": true
}
```

### 12.2 Mapeamento Front-end → Backend

| Front-end (FlowBuilderV2) | Backend (BotConfig) |
|---------------------------|---------------------|
| `node.id` | `step.id` |
| `node.type` | `step.type` |
| `node.x, node.y` | `step.position.x, step.position.y` |
| `node.label` | `step.title` |
| `node.config` | `step.config` |
| `node.connections` | `step.connections` |
| - | `step.order` (gerado automaticamente) |

### 12.3 Conexões jsPlumb → Backend

**jsPlumb cria conexões visuais, mas backend precisa de:**

```json
{
  "connections": {
    "next": "target_step_id",
    "pending": "target_step_id",  // Apenas para payment
    "retry": "target_step_id"     // Opcional, legado
  }
}
```

**Front-end deve:**
1. Detectar conexões criadas no jsPlumb
2. Mapear para formato `connections` do backend
3. Salvar junto com o step

---

## 13. 🎯 CONCLUSÃO

### Resumo da Arquitetura:

1. **Salvamento:** Front-end envia array → Backend salva como JSON string
2. **Leitura:** Backend lê JSON string → Retorna array para front-end
3. **Roteamento:** Router V8 decide entre Flow vs Traditional baseado em `flow_enabled` + `flow_steps`
4. **Execução:** `_execute_flow()` → `_execute_flow_recursive()` processa steps recursivamente
5. **Connections:** Interpretados como `next`, `pending`, `retry` no objeto `connections`
6. **Estado:** Salvo no Redis com TTL de 24h
7. **Pagamentos:** Vinculados ao step via `payment.flow_step_id`
8. **Callbacks:** Formatos `flow_{stepId}_{index}` e `flow_step_{step_id}_btn_{idx}`

### Próximos Passos:

1. **Front-end deve mapear conexões jsPlumb para formato `connections`**
2. **Front-end deve salvar `flow_start_step_id` quando step inicial é definido**
3. **Front-end deve garantir que `order` seja gerado automaticamente**
4. **Front-end deve validar estrutura antes de salvar**

---

**Documento gerado em:** 2025-01-18  
**Versão:** V∞ FINAL  
**Status:** ✅ COMPLETO E FUNCIONAL

