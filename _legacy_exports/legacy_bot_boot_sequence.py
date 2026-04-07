# ============================================================================
# LEGACY BOT BOOT SEQUENCE - AUDITORIA DA ROTINA DE AUTO-START
# Arquivo: _legacy_exports/legacy_bot_boot_sequence.py
# Origem: app.py (análise forense do sistema atual)
# ============================================================================
# Este arquivo documenta como o sistema (tentava) garantir que bots fossem
# reiniciados automaticamente após um restart da VPS.
#
# PROBLEMA IDENTIFICADO: Bots 57 e 67 não respondem porque o sistema de
# reinicialização automática existe, mas depende de componentes que estão
# com problemas (BotRunner não encontrado, serviços não implementados).
# ============================================================================


# ============================================================================
# PARTE 1: O "MOTOR DE PARTIDA" (restart_all_active_bots)
# ============================================================================

"""
LOCALIZAÇÃO NO CÓDIGO:
- Arquivo: app.py
- Função: restart_all_active_bots() (linhas ~8371-8444)
- Chamada: linha 14749 (dentro do if __name__ == '__main__')
"""

# ----------------------------------------------------------------------------
# CÓDIGO ATUAL DO SISTEMA DE REINICIALIZAÇÃO AUTOMÁTICA
# Origem: app.py linhas 8371-8444
# ----------------------------------------------------------------------------
"""
def restart_all_active_bots():
    # Reinicia automaticamente todos os bots ativos de todos os usuários no startup da VPS.
    #
    # Política: Considerar `is_active=True` (bot habilitado no painel) como critério de reinício,
    # independentemente do último `is_running`. Evita iniciar duplicado se já estiver ativo em memória.
    
    try:
        logger.info("🔄 INICIANDO REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS...")
        
        # Usar contexto do Flask para acessar banco
        with app.app_context():
            # Buscar todos os bots marcados como ativos no painel
            active_bots = Bot.query.filter_by(is_active=True).all()
            
            if not active_bots:
                logger.info("ℹ️ Nenhum bot rodando encontrado para reiniciar")
                return
            
            logger.info(f"📊 Encontrados {len(active_bots)} bots rodando para reiniciar")
            
            restarted_count = 0
            failed_count = 0
            
            # OTIMIZAÇÃO REDIS: Buscar todos os bots ativos de uma vez (fora do loop)
            active_bots_map = bot_manager.bot_state.get_all_active_bots()
            active_bot_ids = {int(k) for k in active_bots_map.keys() if str(k).isdigit()}
            
            commit_required = False
            for bot in active_bots:
                try:
                    # Buscar configuração do bot
                    config = BotConfig.query.filter_by(bot_id=bot.id).first()
                    if not config:
                        logger.warning(f"⚠️ Configuração não encontrada para bot {bot.id} (@{bot.username})")
                        failed_count += 1
                        continue
                    
                    # INTERSEÇÃO REDIS: Verificar se bot já está ativo no Redis
                    if bot.id in active_bot_ids:
                        logger.info(f"♻️ Bot {bot.id} (@{bot.username}) já está ativo, pulando...")
                        continue
                    
                    # Reiniciar bot
                    logger.info(f"🚀 Reiniciando bot {bot.id} (@{bot.username})...")
                    bot_manager.start_bot(
                        bot_id=bot.id,
                        token=bot.token,
                        config=config.to_dict()
                    )
                    
                    bot.is_running = True
                    bot.last_started = get_brazil_time()
                    commit_required = True
                    
                    restarted_count += 1
                    logger.info(f"✅ Bot {bot.id} (@{bot.username}) reiniciado com sucesso!")
                    
                    # Pequena pausa para evitar sobrecarga
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao reiniciar bot {bot.id} (@{bot.username}): {e}")
                    failed_count += 1
            
            logger.info(f"🎯 REINICIALIZAÇÃO CONCLUÍDA!")
            logger.info(f"✅ Sucessos: {restarted_count}")
            logger.info(f"❌ Falhas: {failed_count}")
            logger.info(f"📊 Total: {len(active_bots)}")
            
            if commit_required:
                db.session.commit()
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na reinicialização automática: {e}", exc_info=True)
"""

"""
ANÁLISE FORENSE DA FUNÇÃO restart_all_active_bots():

1. CRITÉRIO DE BUSCA: `Bot.query.filter_by(is_active=True).all()`
   - Busca bots onde is_active=True (habilitado no painel)
   - NÃO verifica is_running (estado anterior)
   - Isso significa: mesmo que o bot tenha parado antes do restart, ele será reiniciado

2. VERIFICAÇÃO DE DUPLICAÇÃO: `bot.id in active_bot_ids`
   - Checa se bot já existe no Redis (já está "ativo" em memória)
   - Se sim, pula para evitar duplicação
   - Isso é importante para evitar iniciar o mesmo bot 2x

3. DEPENDÊNCIA CRÍTICA: `bot_manager.start_bot()`
   - Esta função DEVE registrar o webhook no Telegram
   - Mas ela depende do BotRunner (que não foi encontrado)

4. PAUSA ENTRE BOTS: `time.sleep(0.5)`
   - Evita sobrecarga ao reiniciar muitos bots
   - 139 bots = ~70 segundos para reiniciar todos
"""


# ============================================================================
# PARTE 2: PONTO DE EXECUÇÃO NO BOOT DA APLICAÇÃO
# ============================================================================

"""
LOCALIZAÇÃO NO CÓDIGO:
- Arquivo: app.py
- Local: Final do arquivo, dentro do bloco `if __name__ == '__main__':`
- Linha: ~14749
"""

# ----------------------------------------------------------------------------
# CÓDIGO DE INICIALIZAÇÃO NO BOOT
# Origem: app.py linhas 14745-14750
# ----------------------------------------------------------------------------
"""
if __name__ == '__main__':
    init_db()
    
    # 🔄 REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS APÓS DEPLOY
    restart_all_active_bots()
    
    # Modo de desenvolvimento
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    # ... resto do app.run()
"""

"""
ANÁLISE FORENSE DO PONTO DE EXECUÇÃO:

1. QUANDO EXECUTA:
   - Apenas quando `app.py` é executado diretamente (não via import)
   - Ou seja: `python app.py` ou `flask run` com __name__ == '__main__'

2. ORDEM DE EXECUÇÃO:
   - 1. init_db() - Cria/atualiza tabelas
   - 2. restart_all_active_bots() - Reinicia todos os bots ativos
   - 3. app.run() - Inicia o servidor web

3. PROBLEMA DE PRODUÇÃO:
   - Em produção com Gunicorn/uWSGI, cada worker pode executar isso
   - Isso pode causar múltiplas tentativas de reinicialização
   - Precisa de lock distribuído (Redis) para evitar isso

4. API MANUAL:
   - Também existe endpoint: POST /api/admin/restart-all-bots
   - Permite reinicialização manual via API
"""


# ============================================================================
# PARTE 3: A CADEIA DE DEPENDÊNCIAS (Onde está o BotRunner?)
# ============================================================================

"""
CADEIA DE CHAMADAS:

1. restart_all_active_bots() (app.py:8371)
   └── 2. bot_manager.start_bot() (botmanager.py:1053-1064)
        └── 3. self.runner.start_bot() (botmanager.py:1064)
             └── 4. ??? BotRunner ???

PROBLEMA IDENTIFICADO:
- BotRunner é importado de: `internal_logic.services.bot_runner`
- Mas o diretório `internal_logic/services/` está VAZIO
- Ou seja: BotRunner NÃO EXISTE ou não foi implementado/migrado

CÓDIGO QUE TENTA IMPORTAR (botmanager.py:25):
"""
# from internal_logic.services.bot_runner import BotRunner

"""
ISSO EXPLICA POR QUE BOTS 57 E 67 NÃO RESPONDEM:

1. A função restart_all_active_bots() é chamada no boot
2. Ela tenta chamar bot_manager.start_bot()
3. start_bot() delega para self.runner.start_bot()
4. Mas self.runner (BotRunner) não existe ou falha
5. Webhook NUNCA é registrado no Telegram
6. Telegram não sabe para onde enviar os POSTs
7. Mensagens dos usuários são perdidas
"""


# ============================================================================
# PARTE 4: COMO DEVERIA FUNCIONAR (Setup do Webhook)
# ============================================================================

"""
O QUE A FUNÇÃO start_bot DEVE FAZER (esperado):

1. Criar instância do bot (TeleBot ou similar)
2. Registrar estado no Redis (opcional)
3. CONFIGURAR WEBHOOK NO TELEGRAM:
   - URL: https://meuservidor.com/webhook/telegram/{bot_id}
   - Chamada API: setWebhook
4. Ou iniciar POLLING (alternativa)
5. Marcar bot como "running" no banco
"""

# ----------------------------------------------------------------------------
# CÓDIGO ESPERADO/LEGADO DO SETUP DE WEBHOOK
# ----------------------------------------------------------------------------
"""
# Versão esperada do que start_bot deveria fazer:

def start_bot_expected(bot_id, token, config):
    # 1. Criar bot
    import telebot
    bot = telebot.TeleBot(token)
    
    # 2. Configurar webhook (produção)
    import os
    webhook_base = os.environ.get('WEBHOOK_URL', '')
    if webhook_base:
        webhook_url = f"{webhook_base}/webhook/telegram/{bot_id}"
        
        # Chamar API do Telegram
        import requests
        setwebhook_url = f"https://api.telegram.org/bot{token}/setWebhook"
        response = requests.post(
            setwebhook_url,
            json={'url': webhook_url},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Webhook configurado: {webhook_url}")
        else:
            logger.error(f"❌ Falha ao configurar webhook: {response.text}")
    else:
        # Modo desenvolvimento: usar polling
        logger.info("⚠️ WEBHOOK_URL não configurado, usando polling")
        # Iniciar thread de polling
        import threading
        polling_thread = threading.Thread(
            target=bot.polling,
            kwargs={'none_stop': True}
        )
        polling_thread.daemon = True
        polling_thread.start()
    
    # 3. Registrar no Redis (opcional)
    # bot_state.register_bot(bot_id, token, config)
    
    # 4. Atualizar banco
    bot_db = Bot.query.get(bot_id)
    bot_db.is_running = True
    bot_db.last_started = datetime.utcnow()
    db.session.commit()
"""


# ============================================================================
# PARTE 5: WEBHOOK VS POLLING
# ============================================================================

"""
ANÁLISE FORENSE: O QUE O SISTEMA USAVA?

EVIDÊNCIAS DE WEBHOOK:
1. Existe rota: /webhook/telegram/<int:bot_id> (app.py:12570)
2. Código comenta "setWebhook" e "getWebhookInfo" (botmanager.py:1211-1236)
3. Variável de ambiente: WEBHOOK_URL

EVIDÊNCIAS DE POLLING:
1. Código de failover: se webhook retorna 502, muda para polling (botmanager.py:1238-1269)
2. Threads de polling são criadas como fallback

CONCLUSÃO:
- Sistema primariamente usa WEBHOOK (produção)
- POLLING é usado como fallback ou em desenvolvimento
- Bot deveria configurar webhook no boot via setWebhook
"""


# ============================================================================
# PARTE 6: CONFIRMAÇÃO DA AUSÊNCIA NO NOVO SISTEMA
# ============================================================================

"""
CONFIRMAÇÃO: O QUE ESTÁ FALTANDO NO SISTEMA NOVO

1. ❌ BotRunner NÃO EXISTE (diretório internal_logic/services/ vazio)
2. ❌ start_bot() chama self.runner.start_bot() que não existe
3. ❌ Webhook NUNCA é configurado no Telegram após restart
4. ❌ Telegram não sabe para onde enviar mensagens
5. ❌ Bots "existem" no banco mas não recebem mensagens

O SISTEMA TEM A INTENÇÃO (código existe):
- restart_all_active_bots() existe e é chamada no boot
- Loop por todos os bots ativos existe
- Mas a IMPLEMENTAÇÃO (BotRunner) está faltando

ISSO EXPLICA:
- Bot 57: NÃO reiniciado corretamente após deploy
- Bot 67: NÃO reiniciado corretamente após deploy
- Bots que funcionam: Provavelmente foram iniciados manualmente via API
"""


# ============================================================================
# PARTE 7: CÓDIGO LEGADO/ESPERADO DO BOT RUNNER
# ============================================================================

"""
O QUE DEVERIA EXISTIR EM internal_logic/services/bot_runner.py:
"""

BOT_RUNNER_EXPECTED_IMPLEMENTATION = """
# internal_logic/services/bot_runner.py
# Código que deveria existir mas não existe

import logging
import threading
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BotRunner:
    # Gerencia o ciclo de vida dos bots (start, stop, webhook)
    
    def __init__(self, bot_state, scheduler=None, on_update_received=None):
        self.bot_state = bot_state
        self.scheduler = scheduler
        self.on_update_received = on_update_received
        self.running_bots = {}  # bot_id -> thread
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]):
        # Inicia um bot Telegram configurando webhook
        
        try:
            # 1. Validar token
            validation_url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(validation_url, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Token inválido: {response.text}")
            
            bot_info = response.json()
            logger.info(f"✅ Token válido: @{bot_info['result'].get('username')}")
            
            # 2. Configurar webhook
            import os
            webhook_base = os.environ.get('WEBHOOK_URL', '')
            
            if webhook_base:
                webhook_url = f"{webhook_base}/webhook/telegram/{bot_id}"
                
                setwebhook_url = f"https://api.telegram.org/bot{token}/setWebhook"
                response = requests.post(
                    setwebhook_url,
                    json={'url': webhook_url},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Webhook configurado: {webhook_url}")
                else:
                    logger.error(f"❌ Falha ao configurar webhook: {response.text}")
                    # Fallback para polling
                    self._start_polling(bot_id, token)
            else:
                logger.warning("⚠️ WEBHOOK_URL não configurado")
                self._start_polling(bot_id, token)
            
            # 3. Registrar no estado
            self.bot_state.register_bot(bot_id, token, config)
            
            logger.info(f"✅ Bot {bot_id} iniciado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar bot {bot_id}: {e}")
            raise
    
    def stop_bot(self, bot_id: int):
        # Para um bot (remove webhook)
        try:
            bot_data = self.bot_state.get_bot_data(bot_id)
            if bot_data:
                token = bot_data['token']
                
                # Remover webhook
                delete_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
                requests.post(delete_url, timeout=10)
                
                logger.info(f"🛑 Bot {bot_id} parado")
            
            # Remover do estado
            self.bot_state.unregister_bot(bot_id)
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar bot {bot_id}: {e}")
    
    def _start_polling(self, bot_id: int, token: str):
        # Inicia polling em thread separada (fallback)
        import telebot
        
        bot = telebot.TeleBot(token)
        
        def polling_loop():
            logger.info(f"🔄 Iniciando polling para bot {bot_id}")
            bot.polling(none_stop=True, interval=1)
        
        thread = threading.Thread(target=polling_loop, name=f"bot_polling_{bot_id}")
        thread.daemon = True
        thread.start()
        
        self.running_bots[bot_id] = thread
        logger.info(f"✅ Polling iniciado para bot {bot_id}")
"""


# ============================================================================
# RESUMO EXECUTIVO
# ============================================================================

"""
================================================================================
CONCLUSÃO DA AUDITORIA FORENSE: BOOT SEQUENCE
================================================================================

PROBLEMA IDENTIFICADO:
Bots 57 e 67 não respondem porque o sistema de reinicialização automática
está INCOMPLETO. O código existe, mas depende de componentes que não foram
implementados.

CADEIA DE FALHA:
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. VPS reinicia ou deploy ocorre                                           │
│ 2. `restart_all_active_bots()` é chamada (linha 14749)                      │
│ 3. Loop por todos os bots `is_active=True`                                 │
│ 4. Chama `bot_manager.start_bot(bot_id, token, config)`                    │
│ 5. `start_bot` delega para `self.runner.start_bot()` (linha 1064)         │
│ 6. `self.runner` é `BotRunner` importado de `internal_logic.services`      │
│ 7. MAS `internal_logic/services/` está VAZIO                             │
│ 8. BotRunner NÃO EXISTE → falha silenciosa ou erro                         │
│ 9. Webhook NUNCA é configurado no Telegram                                │
│ 10. Telegram não sabe para onde enviar POSTs                               │
│ 11. Mensagens de usuários são perdidas                                    │
└─────────────────────────────────────────────────────────────────────────────┘

SOLUÇÃO IMEDIATA NECESSÁRIA:
1. Implementar a classe BotRunner em internal_logic/services/bot_runner.py
2. Garantir que setWebhook seja chamado no start_bot
3. Adicionar logging detalhado para rastrear falhas
4. Criar mecanismo de retry para bots que falham ao iniciar

ARQUIVOS AFETADOS:
- app.py: restart_all_active_bots() existe mas não funciona completamente
- botmanager.py: Depende de BotRunner que não existe
- internal_logic/services/bot_runner.py: ARQUIVO INEXISTENTE
"""


# ============================================================================
# CHECKLIST PARA REIMPLEMENTAÇÃO
# ============================================================================

"""
✅ PARA RESTAURAR O BOOT SEQUENCE:

[ ] Criar internal_logic/services/bot_runner.py
[ ] Implementar classe BotRunner com:
    [ ] Método start_bot(bot_id, token, config)
    [ ] Método stop_bot(bot_id)
    [ ] Configuração de webhook via setWebhook
    [ ] Fallback para polling se webhook falhar
[ ] Garantir que restart_all_active_bots() funcione:
    [ ] Loop por todos os bots is_active=True
    [ ] Chamar bot_manager.start_bot() para cada um
    [ ] Log de sucesso/falha
    [ ] Commit no banco
[ ] Testar reinicialização após restart
[ ] Verificar que bots 57 e 67 recebam mensagens após fix
"""
