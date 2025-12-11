"""
INTEGRAÇÃO V8 ULTRA - bot_manager.py

Este arquivo contém as modificações necessárias para integrar MessageRouter V8
no bot_manager.py existente.

INSTRUÇÕES:
1. Importar MessageRouter V8 no topo do arquivo
2. Modificar _handle_start_command() para usar MessageRouter
3. Modificar _handle_callback_query() para usar MessageRouter
4. Modificar _execute_flow() para usar FlowEngine V8 (opcional, pode manter lógica atual)

⚠️ IMPORTANTE: Estas são modificações que devem ser aplicadas ao bot_manager.py existente.
Não substituir o arquivo completo, apenas aplicar as modificações indicadas.
"""

# ============================================================================
# MODIFICAÇÃO 1: Importar MessageRouter V8 (adicionar no topo do arquivo)
# ============================================================================
# Adicionar após os imports existentes:
#
# try:
#     from static.js.FLOW_ENGINE_ROUTER_V8 import MessageRouterV8
#     from static.js.FLOW_ENGINE_V8 import FlowEngineV8
#     from static.js.TRADITIONAL_ENGINE_V8 import TraditionalEngineV8
#     V8_ROUTER_AVAILABLE = True
# except ImportError:
#     V8_ROUTER_AVAILABLE = False
#     logger.warning("⚠️ MessageRouter V8 não disponível - usando lógica tradicional")

# ============================================================================
# MODIFICAÇÃO 2: Adicionar MessageRouter como atributo do BotManager
# ============================================================================
# No __init__ do BotManager, adicionar:
#
# if V8_ROUTER_AVAILABLE:
#     self.messageRouter = MessageRouterV8(self)
# else:
#     self.messageRouter = None

# ============================================================================
# MODIFICAÇÃO 3: Substituir lógica em _handle_start_command()
# ============================================================================
# Substituir a seção que verifica flow_enabled e decide entre flow/welcome:
#
# # ANTES (linha ~3806-3860):
# is_flow_active = checkActiveFlow(config)
# if is_flow_active:
#     self._execute_flow(...)
# else:
#     self._send_welcome_message_only(...)
#
# # DEPOIS (usar MessageRouter V8):
# if self.messageRouter:
#     # Usar MessageRouter V8
#     user_from = message.get('from', {})
#     telegram_user_id = str(user_from.get('id', ''))
#     user_message = message.get('text', '/start')
#     
#     try:
#         await self.messageRouter.processMessage(
#             userMessage=user_message,
#             botId=bot_id,
#             chatId=chat_id,
#             telegramUserId=telegram_user_id,
#             context={'token': token, 'message': message, 'start_param': start_param}
#         )
#     except Exception as e:
#         logger.error(f"❌ Erro no MessageRouter V8: {e}", exc_info=True)
#         # Fallback para lógica tradicional
#         if checkActiveFlow(config):
#             self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
#         else:
#             self._send_welcome_message_only(bot_id, token, config, chat_id, message)
# else:
#     # Fallback: usar lógica tradicional
#     is_flow_active = checkActiveFlow(config)
#     if is_flow_active:
#         self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
#     else:
#         self._send_welcome_message_only(bot_id, token, config, chat_id, message)

# ============================================================================
# MODIFICAÇÃO 4: Substituir lógica em _handle_callback_query()
# ============================================================================
# Adicionar verificação de flow ativo e usar MessageRouter se disponível:
#
# # No início de _handle_callback_query(), após obter config:
# if self.messageRouter:
#     # Verificar se flow está ativo
#     is_flow_active = await self.messageRouter.checkFlowActiveAtomic(bot_id, chat_id)
#     
#     if is_flow_active:
#         # Processar via FlowEngine V8
#         callback_data = callback.get('data', '')
#         user_from = callback.get('from', {})
#         telegram_user_id = str(user_from.get('id', ''))
#         
#         try:
#             # Extrair contexto do callback (button index, etc)
#             context = {
#                 'isCallback': True,
#                 'callbackData': callback_data,
#                 'buttonIndex': self._extract_button_index(callback_data),
#                 'token': token
#             }
#             
#             await self.messageRouter.processMessage(
#                 userMessage=callback_data,
#                 botId=bot_id,
#                 chatId=chat_id,
#                 telegramUserId=telegram_user_id,
#                 context=context
#             )
#             return  # Sair após processar via router
#         except Exception as e:
#             logger.error(f"❌ Erro no MessageRouter V8 para callback: {e}", exc_info=True)
#             # Continuar com lógica tradicional como fallback
#     
# # Continuar com lógica tradicional de callback se router não processou

# ============================================================================
# MODIFICAÇÃO 5: Helper method para extrair button index
# ============================================================================
# Adicionar método helper:
#
# def _extract_button_index(self, callback_data: str) -> Optional[int]:
#     """Extrai índice do botão do callback_data (ex: 'buy_0' -> 0)"""
#     try:
#         if callback_data.startswith('buy_'):
#             return int(callback_data.split('_')[1])
#         elif callback_data.startswith('verify_'):
#             return int(callback_data.split('_')[1])
#         # Adicionar outros padrões conforme necessário
#     except (ValueError, IndexError):
#         return None
#     return None

# ============================================================================
# NOTAS IMPORTANTES
# ============================================================================
# 1. MessageRouter V8 é JavaScript, mas pode ser chamado via subprocess ou
#    adaptado para Python. Alternativamente, manter lógica atual e apenas
#    adicionar verificações atômicas.
#
# 2. Se MessageRouter V8 não pode ser usado diretamente (JavaScript),
#    implementar lógica equivalente em Python mantendo os mesmos princípios:
#    - Locks atômicos
#    - Verificação atômica de flow ativo
#    - Garantia de que apenas um motor responde
#
# 3. A integração pode ser feita gradualmente:
#    - Fase 1: Adicionar verificações atômicas
#    - Fase 2: Refatorar para usar MessageRouter (se adaptado para Python)
#    - Fase 3: Migrar completamente para arquitetura V8

