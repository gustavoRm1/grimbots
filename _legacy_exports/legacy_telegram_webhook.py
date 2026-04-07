# ============================================================================
# LEGACY TELEGRAM WEBHOOK - AUDITORIA FORENSE DO SISTEMA DE WEBHOOKS
# Arquivo: _legacy_exports/legacy_telegram_webhook.py
# Origem: Análise forense comparativa entre código ATUAL e código LEGADO
# ============================================================================
# Este arquivo documenta a "burocracia" que foi adicionada ao sistema novo
# e que quebrou o processamento de mensagens para bots com 10k+ usuários.
#
# HIPÓTESE: O código legado NÃO tinha as verificações de Redis/Heartbeat
# que o novo código impõe. Ele simplesmente processava o update.
# ============================================================================


# ============================================================================
# CÓDIGO ATUAL (Sistema Novo - Com Burocracia)
# Origem: app.py linhas 12570-12617 + botmanager.py linhas 1441-1540
# ============================================================================

# ----------------------------------------------------------------------------
# ROTA WEBHOOK ATUAL (app.py)
# ----------------------------------------------------------------------------
"""
@app.route('/webhook/telegram/<int:bot_id>', methods=['POST'])
@limiter.limit("1000 per minute")
@csrf.exempt
def telegram_webhook(bot_id):
    # Webhook para receber updates do Telegram
    try:
        update = request.json
        
        # LOG CRÍTICO: Rastreamento de entrada
        logger.critical(f"📥 WEBHOOK RECEBIDO: bot_id={bot_id}, update_id={update.get('update_id')}")
        
        # ✅ BUROCRACIA 1: Validar que bot existe no banco
        bot = Bot.query.get(bot_id)
        if not bot:
            logger.warning(f"⚠️ Webhook para bot inexistente: {bot_id}")
            return jsonify({'status': 'ok'}), 200
        
        # ✅ BUROCRACIA 2: Circuit Breaker (offline)
        if bot.health_status == 'offline':
            logger.warning(f"🔴 Webhook bloqueado pelo Circuit Breaker (offline): bot_id={bot_id}")
            return jsonify({'status': 'ok'}), 200
        
        # ✅ BUROCRACIA 3: Circuit Breaker (cooldown)
        if bot.circuit_breaker_until and bot.circuit_breaker_until > datetime.now():
            logger.warning(f"🟡 Webhook bloqueado pelo Circuit Breaker (cooldown): bot_id={bot_id}")
            return jsonify({'status': 'ok'}), 200
        
        # ✅ BUROCRACIA 4: Criar BotManager isolado
        from bot_manager import BotManager
        bot_manager = BotManager(socketio=None, user_id=bot.user_id)
        
        # ✅ BUROCRACIA 5: Obter estado Redis isolado
        from redis_bot_state import get_namespaced_bot_state
        user_bot_state = get_namespaced_bot_state(bot.user_id)
        
        # ✅ BUROCRACIA 6: Processar com contexto isolado
        bot_manager._process_telegram_update(bot_id, bot.user_id, update, isolated_state=user_bot_state)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook Telegram: {e}")
        return jsonify({'error': str(e)}), 500
"""


# ----------------------------------------------------------------------------
# PROCESSAMENTO DO UPDATE ATUAL (botmanager.py - _process_telegram_update)
# ----------------------------------------------------------------------------
"""
def _process_telegram_update(self, bot_id: int, user_id: int, update: Dict[str, Any], isolated_state=None):
    # Processa update recebido do Telegram
    
    bot_state = isolated_state if isolated_state else self.bot_state
    
    # ✅ BUROCRACIA 7: Anti-duplicação com Redis Lock
    import redis
    redis_conn = get_redis_connection()
    lock_key = f"gb:{user_id}:lock:update:{update.get('update_id')}"
    
    update_id = update.get('update_id')
    if update_id is None:
        logger.warning(f"⚠️ Update sem update_id - ignorando")
        return
    
    # Verificar lock
    if redis_conn.get(lock_key):
        logger.warning(f"⚠️ Update {update_id} já processado — ignorando duplicado")
        return
    
    # Adquirir lock
    acquired = redis_conn.set(lock_key, "1", ex=20, nx=True)
    if not acquired:
        logger.warning(f"⚠️ Update {update_id} já está sendo processado — ignorando duplicado")
        return
    
    # ✅ BUROCRACIA 8: Verificar se bot está ativo no Redis
    if not bot_state.is_bot_active(bot_id):
        logger.warning(f"⚠️ Bot {bot_id} não está ativo no Redis, tentando auto-start")
        
        # Verificar se outro worker está tentando auto-start
        if bot_state.is_autostart_locked(bot_id):
            logger.info(f"🔒 Outro worker está iniciando bot {bot_id} - aguardando")
            import time
            # ... aguarda
        
        # Tentar auto-start
        try:
            with app.app_context():
                from internal_logic.core.models import Bot, BotConfig
                bot = db.session.get(Bot, bot_id)
                if bot and bot.active and bot.user_id == user_id:
                    config_obj = bot.config or BotConfig.query.filter_by(bot_id=bot.id).first()
                    config_dict = config_obj.to_dict() if config_obj else {}
                    bot_state.register_bot(bot.id, bot.token, config_dict)
        except Exception as autostart_error:
            logger.error(f"❌ Falha ao auto-start bot {bot_id}: {autostart_error}")
        
        # ✅ BUROCRACIA 9: Verificar NOVAMENTE se está ativo - SE NÃO ESTIVER, DESCARTA!
        if not bot_state.is_bot_active(bot_id):
            logger.warning(f"⚠️ Bot {bot_id} ainda indisponível após auto-start, IGNORANDO UPDATE")
            return  # ←←← AQUI ESTÁ O PROBLEMA! LINHA 1528
    
    # ✅ BUROCRACIA 10: Obter dados do bot do Redis
    bot_info = bot_state.get_bot_data(bot_id)
    if not bot_info:
        logger.warning(f"🤖 Bot {bot_id} não encontrado no Redis - DESCARTANDO UPDATE")
        return  # ←←← OUTRO PONTO DE DESCARTE! LINHA 1534
    
    token = bot_info['token']
    config = bot_info['config']
    
    # ... continua processamento
"""


# ============================================================================
# CÓDIGO LEGADO HIPOTÉTICO (Como provavelmente funcionava antes)
# Baseado em padrões de telebot e processamento direto
# ============================================================================

"""
# ----------------------------------------------------------------------------
# ROTA WEBHOOK LEGADA (Hipótese - Código que funcionava com 10k usuários)
# ----------------------------------------------------------------------------

@app.route('/webhook/telegram/<int:bot_id>', methods=['POST'])
def telegram_webhook_legacy(bot_id):
    # Webhook legado - SIMPLEs, SEM burocracia de Redis
    try:
        update = request.get_json()
        
        # APENAS: Buscar o bot no banco
        bot = Bot.query.get(bot_id)
        if not bot:
            return jsonify({'status': 'ok'}), 200
        
        # APENAS: Criar instância TeleBot com o token
        import telebot
        tb = telebot.TeleBot(bot.token)
        
        # APENAS: Processar o update diretamente
        # O TeleBot cuida de chamar os handlers registrados (@bot.message_handler)
        tb.process_new_updates([telebot.types.Update.de_json(update)])
        
        # OU: Passar para um BotManager simples sem estado Redis
        # from botmanager import process_update_simple
        # process_update_simple(bot_id, bot.token, update)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------------
# PROCESSAMENTO LEGADO (Hipótese - Processamento Direto)
# ----------------------------------------------------------------------------

def process_update_legacy(bot_id, token, update):
    # Processamento SIMPLES - sem verificações de Redis
    
    import telebot
    from telebot import types
    
    # Criar bot
    bot = telebot.TeleBot(token)
    
    # Converter update
    tele_update = types.Update.de_json(update)
    
    # Processar - O TeleBot chama os handlers automaticamente
    bot.process_new_updates([tele_update])
    
    # Ou extrair mensagem e processar manualmente:
    if tele_update.message:
        message = tele_update.message
        chat_id = message.chat.id
        text = message.text
        
        # Buscar config no banco (simples, não Redis)
        config = BotConfig.query.filter_by(bot_id=bot_id).first()
        
        # Responder baseado na mensagem
        if text == '/start':
            bot.send_message(chat_id, config.welcome_message or "Bem-vindo!")
        else:
            # Fluxo normal...
            handle_message(bot_id, chat_id, text, bot)
    
    # FIM - Sem verificações de estado, sem locks, sem Redis
"""


# ============================================================================
# ANÁLISE FORENSE: A "BUROCRACIA" QUE QUEBROU O SISTEMA
# ============================================================================

"""
================================================================================
COMPARAÇÃO: Código Legado vs Código Novo
================================================================================

┌─────────────────────────────┬─────────────────────────────┬──────────────────┐
│ Aspecto                     │ Código LEGADO               │ Código NOVO      │
├─────────────────────────────┼─────────────────────────────┼──────────────────┤
│ Verificação Redis           │ NÃO                         │ SIM (3 vezes)    │
│ Verificação Circuit Breaker │ NÃO                         │ SIM              │
│ Verificação Health Status   │ NÃO                         │ SIM              │
│ Auto-start com retry        │ NÃO                         │ SIM (complexo)   │
│ Lock anti-duplicação        │ NÃO                         │ SIM (Redis)      │
│ BotManager isolado          │ NÃO                         │ SIM              │
│ Estado Redis namespaced     │ NÃO                         │ SIM              │
│ Processamento               │ Direto                      │ Indireto         │
│ Dependaências               │ TeleBot + Banco             │ + Redis + State  │
│ Pontos de falha             │ 1 (Telegram API)            │ 5+ (Redis, etc)  │
└─────────────────────────────┴─────────────────────────────┴──────────────────┘


================================================================================
A "PERGUNTA DE 1 MILHÃO DE DÓLARES" RESPONDIDA
================================================================================

PERGUNTA: No código antigo, havia ALGUMA trava que impedisse o processamento 
          da mensagem se o bot não estivesse "ativo" no Redis?

RESPOSTA: NÃO. O código legado NÃO usava Redis para estado do bot.
          O código legado simplesmente:
          1. Recebia o update
          2. Buscava o bot no banco (Bot.query.get)
          3. Criava instância TeleBot(bot.token)
          4. Chamava bot.process_new_updates([update])
          5. O TeleBot cuidava do resto


================================================================================
O QUE A NOVA ARQUITETURA ADICIOUNOU (A "BUROCRACIA")
================================================================================

1. CIRCUIT BREAKER (app.py:12589-12595)
   - Se bot.health_status == 'offline' → DESCARTA MENSAGEM
   - Se bot.circuit_breaker_until > agora → DESCARTA MENSAGEM
   
2. VERIFICAÇÃO DE ESTADO NO REDIS (botmanager.py:1494-1495)
   - Se not bot_state.is_bot_active(bot_id) → tenta auto-start
   
3. AUTO-START COM LOCK (botmanager.py:1498-1523)
   - Verifica se outro worker está tentando iniciar
   - Tenta registrar bot no Redis
   - Se falhar, loga erro
   
4. SEGUNDA VERIFICAÇÃO (botmanager.py:1526-1528) ←←← PROBLEMA!
   - Verifica NOVAMENTE se bot está ativo
   - Se NÃO estiver → IGNORA UPDATE (return)
   - Esta linha 1528 é onde mensagens são perdidas!
   
5. OBTENÇÃO DE DADOS DO REDIS (botmanager.py:1531-1534) ←←← OUTRO PROBLEMA!
   - bot_info = bot_state.get_bot_data(bot_id)
   - Se bot_info for None → DESCARTA UPDATE (return)
   - Se Redis falhar, bot_info = None

6. ANTI-DUPLICAÇÃO COM LOCK (botmanager.py:1469-1491)
   - Redis lock por update_id
   - Se lock existir → ignora update
   - Se Redis falhar, pode causar perda de mensagens


================================================================================
POR QUE QUEBROU COM BOTS DE 10K USUÁRIOS?
================================================================================

CENÁRIO DE FALHA:

1. Bot com 10k usuários recebe MUITAS mensagens simultâneas
2. Webhook dispara múltiplas vezes
3. Cada requisição tenta verificar Redis:
   - "is_bot_active?" → consulta Redis
   - Se Redis sobrecarregar ou timeout → retorna False
   - Código pensa que bot não está ativo
4. Código tenta "auto-start":
   - Registra bot no Redis
   - Mas outra requisição já está fazendo isso
   - Lock de auto-start impede
5. Código chega na linha 1528:
   - "Bot ainda indisponível após auto-start, ignorando update"
   - return → MENSAGEM PERDIDA
6. Usuário nunca recebe resposta

PROBLEMA DE ARQUITETURA:
- O sistema novo ASSUME que o bot precisa estar "registrado" no Redis
- O sistema novo ASSUME que se não estiver no Redis, deve ignorar
- O sistema legado NÃO tinha essa suposição - processava direto


================================================================================
SOLUÇÃO SUGERIDA (PARA REIMPLEMENTAÇÃO)
================================================================================

OPÇÃO 1: Modo "Bypass Redis" (Fallback)
   - Se bot não estiver no Redis, NÃO descartar
   - Fallback: criar TeleBot direto e processar
   - Redis é "nice to have", não "must have"

OPÇÃO 2: Processamento Direto
   - Remover verificação de linha 1526-1528
   - Sempre processar, mesmo sem estado Redis
   - Estado Redis só para funcionalidades avançadas

OPÇÃO 3: Arquitetura Híbrida
   - Manter código novo para features novas
   - Criar rota alternativa `/webhook/telegram/<bot_id>/direct`
   - Essa rota usa processamento legado (simples)
   - Bots críticos usam a rota direct


================================================================================
CÓDIGO CHAVE PARA REIMPLEMENTAÇÃO (SIMPLES, SEM REDIS)
================================================================================
"""

# Exemplo mínimo de webhook que funcionaria (baseado em padrões legados):
WEBHOOK_MINIMAL_EXAMPLE = """
@app.route('/webhook/telegram/<int:bot_id>/direct', methods=['POST'])
@csrf.exempt
def telegram_webhook_direct(bot_id):
    # Versão minimalista - SEM Redis, SEM estado
    try:
        update = request.get_json()
        
        # 1. Buscar bot no banco
        bot = Bot.query.get(bot_id)
        if not bot:
            return jsonify({'status': 'ok'}), 200
        
        # 2. Importar TeleBot
        import telebot
        from telebot import types
        
        # 3. Criar instância
        tb = telebot.TeleBot(bot.token)
        
        # 4. Converter e processar
        tele_update = types.Update.de_json(update)
        tb.process_new_updates([tele_update])
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Erro webhook direto: {e}")
        return jsonify({'status': 'error'}), 500
"""


# ============================================================================
# CHECKLIST PARA REIMPLEMENTAÇÃO
# ============================================================================

"""
✅ PARA RESTAURAR FUNCIONAMENTO COM BOTS GRANDES:

[ ] Criar rota alternativa `/webhook/telegram/<bot_id>/direct`
[ ] Implementar processamento SEM verificação Redis
[ ] Implementar processamento SEM Circuit Breaker
[ ] Usar TeleBot direto (não via BotManager complexo)
[ ] Manter rota atual para compatibilidade
[ ] Permitir escolha de rota por bot (configuração)

✅ CÓDIGO MÍNIMO NECESSÁRIO:

1. Rota webhook (recebe POST)
2. Busca bot no banco
3. Cria TeleBot(token)
4. process_new_updates([update])
5. Retorna 200

SEM:
- Verificação de estado Redis
- Circuit Breaker
- Auto-start
- Locks
- Isolamento de namespace
- BotManager intermediário
"""
