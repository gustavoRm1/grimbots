"""
Flow Engine Service
===================
Motor de processamento de mensagens e regras de funil.
Isola toda a lógica de processamento de updates do Telegram.
"""

import logging
import json
import time
import re
import uuid
import hashlib
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FlowEngine:
    """
    Motor de fluxo para processamento de mensagens Telegram.
    Responsável por: processar updates, executar handlers, gerenciar funil.
    """
    
    def __init__(
        self,
        messenger,
        bot_state,
        on_message_saved: Optional[Callable] = None
    ):
        """
        Inicializa o FlowEngine.
        
        Args:
            messenger: Instância de BotMessenger para envio
            bot_state: Instância do estado do bot (RedisBrain)
            on_message_saved: Callback opcional após salvar mensagem
        """
        self.messenger = messenger
        self.bot_state = bot_state
        self.on_message_saved = on_message_saved
        
        # Cache de rotas de fluxo
        self._flow_cache: Dict[int, Dict[str, Any]] = {}
        
        logger.info("✅ FlowEngine inicializado")
    
    def process_update(self, bot_id: int, telegram_user_id: str, update: Dict[str, Any]) -> bool:
        """
        Processa um update do Telegram - Ponto de entrada principal.
        
        Args:
            bot_id: ID do bot
            telegram_user_id: ID do usuário no Telegram
            update: Dados do update
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            # Extrair dados do bot do Redis
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data:
                logger.warning(f"⚠️ Bot {bot_id} não encontrado no estado")
                return False
            
            token = bot_data.get('token')
            config = bot_data.get('config', {})
            
            if not token:
                logger.error(f"❌ Token não disponível para bot {bot_id}")
                return False
            
            # Processar diferentes tipos de update
            if 'message' in update:
                message = update['message']
                chat_id = message.get('chat', {}).get('id')
                
                # Salvar mensagem recebida
                self._save_incoming_message(bot_id, telegram_user_id, message)
                
                # Verificar se é comando /start
                text = message.get('text', '')
                if text and text.startswith('/start'):
                    start_param = text[7:].strip() if len(text) > 7 else None
                    return self._handle_start_command(bot_id, token, config, chat_id, message, start_param)
                
                # Processar como mensagem de texto normal
                return self._handle_text_message(bot_id, token, config, chat_id, message)
                
            elif 'callback_query' in update:
                callback = update['callback_query']
                return self._handle_callback_query(bot_id, token, config, callback)
            
            logger.debug(f"⚠️ Update tipo não reconhecido para bot {bot_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar update: {e}", exc_info=True)
            return False
    
    def _save_incoming_message(
        self,
        bot_id: int,
        telegram_user_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Salva mensagem recebida no banco de dados.
        
        Args:
            bot_id: ID do bot
            telegram_user_id: ID do usuário
            message: Dados da mensagem
            
        Returns:
            bool: True se salvo com sucesso
        """
        try:
            # Importar modelos localmente para evitar circular imports
            from app import app, db
            from models import BotMessage, BotUser, get_brazil_time
            
            with app.app_context():
                # Buscar ou criar BotUser
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    archived=False
                ).first()
                
                if not bot_user:
                    # Criar novo usuário
                    chat = message.get('chat', {})
                    bot_user = BotUser(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        first_name=message.get('from', {}).get('first_name', ''),
                        last_name=message.get('from', {}).get('last_name', ''),
                        username=message.get('from', {}).get('username', ''),
                        chat_id=str(chat.get('id', '')),
                        language_code=message.get('from', {}).get('language_code', 'pt'),
                        last_interaction=get_brazil_time()
                    )
                    db.session.add(bot_user)
                    db.session.flush()
                    logger.info(f"✅ Novo BotUser criado: {telegram_user_id}")
                
                # Criar registro da mensagem
                text = message.get('text', '')
                telegram_msg_id = str(message.get('message_id', ''))
                
                bot_message = BotMessage(
                    bot_id=bot_id,
                    bot_user_id=bot_user.id,
                    telegram_user_id=telegram_user_id,
                    message_id=telegram_msg_id,
                    message_text=text,
                    message_type='text',
                    direction='incoming',
                    is_read=False,
                    raw_data=json.dumps(message)
                )
                db.session.add(bot_message)
                
                # Atualizar last_interaction
                bot_user.last_interaction = get_brazil_time()
                
                db.session.commit()
                
                # Chamar callback se existir
                if self.on_message_saved:
                    try:
                        self.on_message_saved(bot_id, bot_user, bot_message)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro no callback on_message_saved: {e}")
                
                logger.debug(f"✅ Mensagem salva: '{text[:50]}...' de {telegram_user_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar mensagem: {e}")
            return False
    
    def _handle_start_command(
        self,
        bot_id: int,
        token: str,
        config: Dict[str, Any],
        chat_id: int,
        message: Dict[str, Any],
        start_param: Optional[str] = None
    ) -> bool:
        """
        Processa comando /start.
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            chat_id: ID do chat
            message: Dados da mensagem
            start_param: Parâmetro do deep link
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            logger.info(f"🚀 /start recebido: bot={bot_id}, user={chat_id}, param={start_param}")
            
            # Verificar se flow está ativo
            if self._is_flow_active(config):
                # Usar MessageRouter para processar flow
                return self._route_through_flow_engine(bot_id, token, config, chat_id, message, 'start', start_param)
            
            # Comportamento padrão: enviar mensagem de boas-vindas
            welcome_message = config.get('welcome_message', 'Bem-vindo! 👋')
            
            # Construir botões se houver
            buttons = self._build_start_buttons(config, start_param)
            
            return self.messenger.send_message(
                token=token,
                chat_id=str(chat_id),
                message=welcome_message,
                reply_markup=self.messenger.build_keyboard(buttons) if buttons else None
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar /start: {e}")
            return False
    
    def _handle_text_message(
        self,
        bot_id: int,
        token: str,
        config: Dict[str, Any],
        chat_id: int,
        message: Dict[str, Any]
    ) -> bool:
        """
        Processa mensagens de texto (não comandos).
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            chat_id: ID do chat
            message: Dados da mensagem
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            text = message.get('text', '')
            
            # Verificar se flow está ativo
            if self._is_flow_active(config):
                return self._route_through_flow_engine(bot_id, token, config, chat_id, message, 'text', None)
            
            # Comportamento padrão: ecoar ou responder com mensagem padrão
            fallback_message = config.get('fallback_message', 'Recebi sua mensagem! 📝')
            
            return self.messenger.send_message(
                token=token,
                chat_id=str(chat_id),
                message=fallback_message
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem de texto: {e}")
            return False
    
    def _handle_callback_query(
        self,
        bot_id: int,
        token: str,
        config: Dict[str, Any],
        callback: Dict[str, Any]
    ) -> bool:
        """
        Processa callback query (clique em botão inline).
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            callback: Dados do callback
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            callback_data = callback.get('data', '')
            chat_id = callback.get('message', {}).get('chat', {}).get('id')
            callback_id = callback.get('id')
            
            logger.info(f"🔘 Callback recebido: bot={bot_id}, data={callback_data}")
            
            # Responder callback imediatamente
            self.messenger.answer_callback_query(token, callback_id)
            
            # Verificar se flow está ativo
            if self._is_flow_active(config):
                return self._route_through_flow_engine(
                    bot_id, token, config, chat_id,
                    callback.get('message', {}),
                    'callback',
                    callback_data=callback_data
                )
            
            # Processar callback específico
            if callback_data.startswith('buy_'):
                # Extrair product_id do callback_data
                product_id = callback_data.replace('buy_', '')
                return self._handle_buy_callback(bot_id, token, config, chat_id, product_id)
            
            elif callback_data == 'support':
                support_message = config.get('support_message', 'Entre em contato com o suporte.')
                return self.messenger.send_message(token, str(chat_id), support_message)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar callback: {e}")
            return False
    
    def _handle_buy_callback(
        self,
        bot_id: int,
        token: str,
        config: Dict[str, Any],
        chat_id: int,
        product_id: str
    ) -> bool:
        """
        Processa callback de compra.
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            chat_id: ID do chat
            product_id: ID do produto
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            from app import app, db
            from models import Product, Bot, Payment
            
            with app.app_context():
                # Buscar produto
                product = Product.query.filter_by(id=product_id, bot_id=bot_id).first()
                if not product:
                    logger.warning(f"⚠️ Produto não encontrado: {product_id}")
                    return self.messenger.send_message(
                        token, str(chat_id),
                        "❌ Produto não encontrado."
                    )
                
                # Criar payment
                bot = Bot.query.get(bot_id)
                payment = Payment(
                    bot_id=bot_id,
                    user_id=bot.user_id if bot else None,
                    product_id=product.id,
                    product_name=product.name,
                    amount=product.price,
                    status='pending',
                    customer_user_id=str(chat_id),
                    payment_id=f"PIX_{uuid.uuid4().hex[:12].upper()}"
                )
                db.session.add(payment)
                db.session.commit()
                
                # Gerar PIX (simplificado - integração real seria aqui)
                pix_message = f"""
💰 <b>Pagamento via PIX</b>

Produto: {product.name}
Valor: R$ {product.price:.2f}

⏳ Aguardando pagamento...
Código: <code>{payment.payment_id}</code>
                """
                
                return self.messenger.send_message(token, str(chat_id), pix_message.strip())
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar compra: {e}")
            return False
    
    def _is_flow_active(self, config: Dict[str, Any]) -> bool:
        """
        Verifica se o Flow Editor está ativo.
        
        Args:
            config: Configuração do bot
            
        Returns:
            bool: True se flow está ativo
        """
        flow_enabled = config.get('flow_enabled', False)
        flow_steps = config.get('flow_steps', [])
        
        # Normalizar flow_enabled
        if isinstance(flow_enabled, str):
            flow_enabled = flow_enabled.lower().strip() in ('true', '1', 'yes', 'on')
        
        # Parsear flow_steps se necessário
        if isinstance(flow_steps, str):
            try:
                flow_steps = json.loads(flow_steps)
            except:
                flow_steps = []
        
        return bool(flow_enabled) and isinstance(flow_steps, list) and len(flow_steps) > 0
    
    def _route_through_flow_engine(
        self,
        bot_id: int,
        token: str,
        config: Dict[str, Any],
        chat_id: int,
        message: Dict[str, Any],
        message_type: str,
        start_param: Optional[str] = None,
        callback_data: Optional[str] = None
    ) -> bool:
        """
        Roteia mensagem através do MessageRouter (Flow Engine V8).
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            chat_id: ID do chat
            message: Dados da mensagem
            message_type: Tipo da mensagem (start, text, callback)
            start_param: Parâmetro do deep link
            callback_data: Dados do callback
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            from flow_engine_router_v8 import get_message_router
            
            # Obter router (precisa do BotManager como contexto)
            # Nota: Isso é um workaround - idealmente o router seria injetado
            router = get_message_router(self)
            
            telegram_user_id = str(message.get('from', {}).get('id', chat_id))
            
            router.process_message(
                bot_id=bot_id,
                token=token,
                config=config,
                chat_id=chat_id,
                telegram_user_id=telegram_user_id,
                message=message,
                message_type=message_type,
                start_param=start_param,
                callback_data=callback_data
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no MessageRouter: {e}")
            return False
    
    def _build_start_buttons(
        self,
        config: Dict[str, Any],
        start_param: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Constrói botões para mensagem de /start.
        
        Args:
            config: Configuração do bot
            start_param: Parâmetro do deep link
            
        Returns:
            Lista de botões
        """
        buttons = []
        
        # Botões de produtos
        products = config.get('products', [])
        for product in products[:3]:  # Máximo 3 produtos
            buttons.append({
                'text': f"💰 {product.get('name', 'Produto')}",
                'callback_data': f"buy_{product.get('id')}"
            })
        
        # Botão de suporte
        buttons.append({
            'text': "🎧 Suporte",
            'callback_data': 'support'
        })
        
        return buttons
    
    def get_flow_status(self, bot_id: int) -> Dict[str, Any]:
        """
        Obtém status do flow para um bot.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            Dict com status do flow
        """
        bot_data = self.bot_state.get_bot_data(bot_id)
        if not bot_data:
            return {'active': False, 'error': 'Bot not found'}
        
        config = bot_data.get('config', {})
        return {
            'active': self._is_flow_active(config),
            'steps_count': len(config.get('flow_steps', [])),
            'flow_enabled': config.get('flow_enabled', False)
        }
