"""
Bot Manager - Gerenciador de Bots do Telegram
Responsável por validar tokens, iniciar/parar bots e processar webhooks
"""

import requests
import threading
import time
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import hmac

logger = logging.getLogger(__name__)

# Configurar logging para este módulo
logger.setLevel(logging.INFO)

# Configuração de Split Payment da Plataforma
import os
PLATFORM_SPLIT_USER_ID = os.environ.get('PLATFORM_SPLIT_USER_ID', '')  # Client ID para receber comissões
PLATFORM_SPLIT_PERCENTAGE = 4  # 4% de comissão (aproximadamente R$ 0.75 em vendas de ~R$ 19)


class BotManager:
    """Gerenciador de bots Telegram"""
    
    def __init__(self, socketio, scheduler=None):
        self.socketio = socketio
        self.scheduler = scheduler
        self.active_bots: Dict[int, Dict[str, Any]] = {}
        self.bot_threads: Dict[int, threading.Thread] = {}
        self.polling_jobs: Dict[int, str] = {}  # bot_id -> job_id
        logger.info("BotManager inicializado")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Valida token do Telegram usando getMe
        
        Args:
            token: Token do bot
            
        Returns:
            Informações do bot
            
        Raises:
            Exception: Se token for inválido
        """
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if not data.get('ok'):
                raise Exception(data.get('description', 'Token inválido'))
            
            bot_info = data.get('result', {})
            logger.info(f"Token validado: @{bot_info.get('username')}")
            
            return bot_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao validar token: {e}")
            raise Exception(f"Erro de conexão com API do Telegram: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao validar token: {e}")
            raise
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]):
        """
        Inicia um bot Telegram
        
        Args:
            bot_id: ID do bot no banco
            token: Token do bot
            config: Configuração do bot
        """
        if bot_id in self.active_bots:
            logger.warning(f"Bot {bot_id} já está ativo")
            return
        
        # Configurar webhook para receber mensagens do Telegram
        self._setup_webhook(token, bot_id)
        
        # Armazenar bot ativo
        self.active_bots[bot_id] = {
            'token': token,
            'config': config,
            'started_at': datetime.now(),
            'status': 'running'
        }
        
        # Iniciar thread de monitoramento
        thread = threading.Thread(
            target=self._bot_monitor_thread,
            args=(bot_id,),
            daemon=True
        )
        thread.start()
        self.bot_threads[bot_id] = thread
        
        logger.info(f"Bot {bot_id} iniciado com webhook configurado")
    
    def stop_bot(self, bot_id: int):
        """
        Para um bot Telegram
        
        Args:
            bot_id: ID do bot no banco
        """
        if bot_id not in self.active_bots:
            logger.warning(f"Bot {bot_id} não está ativo")
            return
        
        # Marcar como parado
        self.active_bots[bot_id]['status'] = 'stopped'
        
        # Remover job do scheduler se existir
        if bot_id in self.polling_jobs and self.scheduler:
            try:
                self.scheduler.remove_job(self.polling_jobs[bot_id])
                del self.polling_jobs[bot_id]
                logger.info(f"✅ Polling job removido para bot {bot_id}")
            except Exception as e:
                logger.error(f"Erro ao remover job: {e}")
        
        # Remover da lista de ativos
        del self.active_bots[bot_id]
        
        # Thread será encerrada automaticamente
        if bot_id in self.bot_threads:
            del self.bot_threads[bot_id]
        
        logger.info(f"Bot {bot_id} parado")
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]):
        """
        Atualiza configuração de um bot em tempo real
        
        Args:
            bot_id: ID do bot
            config: Nova configuração
        """
        if bot_id in self.active_bots:
            self.active_bots[bot_id]['config'] = config
            logger.info(f"🔧 Configuração do bot {bot_id} atualizada")
            logger.info(f"🔍 DEBUG Config - downsells_enabled: {config.get('downsells_enabled', False)}")
            logger.info(f"🔍 DEBUG Config - downsells: {config.get('downsells', [])}")
        else:
            logger.warning(f"⚠️ Bot {bot_id} não está ativo para atualizar configuração")
    
    def _bot_monitor_thread(self, bot_id: int):
        """
        Thread de monitoramento de um bot (simulação de atividade)
        
        Args:
            bot_id: ID do bot
        """
        logger.info(f"Monitor do bot {bot_id} iniciado")
        
        while bot_id in self.active_bots and self.active_bots[bot_id]['status'] == 'running':
            try:
                # Simular ping/heartbeat
                self.socketio.emit('bot_heartbeat', {
                    'bot_id': bot_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'online'
                }, room=f'bot_{bot_id}')
                
                # Aguardar próximo ciclo (30 segundos)
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Erro no monitor do bot {bot_id}: {e}")
                break
        
        logger.info(f"Monitor do bot {bot_id} encerrado")
    
    def _setup_webhook(self, token: str, bot_id: int):
        """
        Configura webhook do Telegram
        
        Args:
            token: Token do bot
            bot_id: ID do bot
        """
        try:
            # Para desenvolvimento local, usar ngrok ou similar
            # Para produção, usar domínio real com HTTPS
            
            # IMPORTANTE: Configure WEBHOOK_URL nas variáveis de ambiente
            import os
            webhook_base = os.environ.get('WEBHOOK_URL', '')
            
            if webhook_base:
                # Configurar webhook real
                webhook_url = f"{webhook_base}/webhook/telegram/{bot_id}"
                url = f"https://api.telegram.org/bot{token}/setWebhook"
                response = requests.post(url, json={'url': webhook_url}, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Webhook configurado: {webhook_url}")
                else:
                    logger.error(f"Erro ao configurar webhook: {response.text}")
            else:
                # Modo polling para desenvolvimento local
                logger.warning(f"WEBHOOK_URL não configurado. Bot {bot_id} em modo polling.")
                
                if self.scheduler:
                    # Usar APScheduler (melhor que threads)
                    job_id = f'bot_polling_{bot_id}'
                    self.scheduler.add_job(
                        id=job_id,
                        func=self._polling_cycle,
                        args=[bot_id, token],
                        trigger='interval',
                        seconds=1,
                        max_instances=1,
                        replace_existing=True
                    )
                    self.polling_jobs[bot_id] = job_id
                    logger.info(f"✅ Polling job criado: {job_id}")
                else:
                    # Fallback para thread manual
                    polling_thread = threading.Thread(
                        target=self._polling_mode,
                        args=(bot_id, token),
                        daemon=True
                    )
                    polling_thread.start()
                    logger.info(f"✅ Polling thread iniciada para bot {bot_id}")
                
        except Exception as e:
            logger.error(f"Erro ao configurar webhook: {e}")
    
    def _polling_cycle(self, bot_id: int, token: str):
        """
        Ciclo de polling - chamado pelo scheduler a cada segundo
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        if bot_id not in self.active_bots or self.active_bots[bot_id]['status'] != 'running':
            # Bot não está mais ativo, remover job
            if bot_id in self.polling_jobs:
                try:
                    self.scheduler.remove_job(self.polling_jobs[bot_id])
                    del self.polling_jobs[bot_id]
                    logger.info(f"🛑 Polling job removido para bot {bot_id}")
                except:
                    pass
            return
        
        try:
            # Inicializar offset se não existir
            if 'offset' not in self.active_bots[bot_id]:
                self.active_bots[bot_id]['offset'] = 0
                self.active_bots[bot_id]['poll_count'] = 0
            
            self.active_bots[bot_id]['poll_count'] += 1
            poll_count = self.active_bots[bot_id]['poll_count']
            offset = self.active_bots[bot_id]['offset']
            
            # Log apenas a cada 30 polls (30 segundos)
            if poll_count % 30 == 0:
                logger.info(f"✅ Bot {bot_id} online e aguardando mensagens...")
            
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            response = requests.get(url, params={'offset': offset, 'timeout': 0}, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok'):
                    updates = data.get('result', [])
                    
                    if updates:
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📨 NOVA MENSAGEM RECEBIDA! ({len(updates)} update(s))")
                        logger.info(f"{'='*60}")
                        
                        for update in updates:
                            self.active_bots[bot_id]['offset'] = update['update_id'] + 1
                            self._process_telegram_update(bot_id, update)
        
        except requests.exceptions.Timeout:
            pass  # Timeout é esperado
        except Exception as e:
            logger.error(f"❌ Erro no polling bot {bot_id}: {e}")
    
    def _polling_mode(self, bot_id: int, token: str):
        """
        Modo polling para receber atualizações (desenvolvimento local)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        logger.info(f"🔄 Iniciando polling para bot {bot_id}")
        offset = 0
        poll_count = 0
        
        while bot_id in self.active_bots and self.active_bots[bot_id]['status'] == 'running':
            try:
                poll_count += 1
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                
                # Log a cada 5 polls para mostrar que está funcionando
                if poll_count % 5 == 0:
                    logger.info(f"📡 Bot {bot_id} polling ativo (ciclo {poll_count}) - Thread: {threading.current_thread().name}")
                
                response = requests.get(url, params={'offset': offset, 'timeout': 30}, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        updates = data.get('result', [])
                        
                        if updates:
                            logger.info(f"📨 Bot {bot_id} recebeu {len(updates)} update(s)")
                            
                            for update in updates:
                                offset = update['update_id'] + 1
                                logger.info(f"🔍 Processando update {update['update_id']}")
                                # Processar update
                                self._process_telegram_update(bot_id, update)
                    else:
                        logger.error(f"❌ Resposta não OK do Telegram: {data}")
                else:
                    logger.error(f"❌ Status code {response.status_code}: {response.text}")
                
                time.sleep(1)
                
            except requests.exceptions.Timeout:
                # Timeout é normal, continuar polling
                logger.debug(f"⏱️ Timeout no polling bot {bot_id} (normal)")
                continue
            except Exception as e:
                logger.error(f"❌ Erro no polling do bot {bot_id}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
        
        logger.info(f"🛑 Polling do bot {bot_id} encerrado")
    
    def _process_telegram_update(self, bot_id: int, update: Dict[str, Any]):
        """
        Processa update recebido do Telegram
        
        Args:
            bot_id: ID do bot
            update: Dados do update
        """
        try:
            if bot_id not in self.active_bots:
                logger.warning(f"⚠️ Bot {bot_id} não está mais ativo, ignorando update")
                return
            
            bot_info = self.active_bots[bot_id]
            token = bot_info['token']
            config = bot_info['config']
            
            # Processar mensagem
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                
                logger.info(f"💬 De: {user.get('first_name', 'Usuário')} | Mensagem: '{text}'")
                
                # Comando /start
                if text == '/start':
                    logger.info(f"⭐ COMANDO /START - Enviando mensagem de boas-vindas...")
                    self._handle_start_command(bot_id, token, config, chat_id, message)
            
            # Processar callback (botões)
            elif 'callback_query' in update:
                callback = update['callback_query']
                logger.info(f"🔘 BOTÃO CLICADO: {callback.get('data')}")
                self._handle_callback_query(bot_id, token, config, callback)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar update do bot {bot_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_start_command(self, bot_id: int, token: str, config: Dict[str, Any], 
                             chat_id: int, message: Dict[str, Any]):
        """
        Processa comando /start
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            chat_id: ID do chat
            message: Dados da mensagem
        """
        try:
            # Registrar usuário no banco de dados
            from app import app, db
            from models import BotUser, Bot
            
            user_from = message.get('from', {})
            telegram_user_id = str(user_from.get('id', ''))
            first_name = user_from.get('first_name', 'Usuário')
            username = user_from.get('username', '')
            
            with app.app_context():
                # Verificar se usuário já existe
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                if not bot_user:
                    # Novo usuário - criar registro
                    bot_user = BotUser(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        first_name=first_name,
                        username=username
                    )
                    db.session.add(bot_user)
                    
                    # Atualizar contador do bot
                    bot = Bot.query.get(bot_id)
                    if bot:
                        bot.total_users = BotUser.query.filter_by(bot_id=bot_id).count()
                    
                    db.session.commit()
                    logger.info(f"👤 Novo usuário registrado: {first_name} (@{username})")
                else:
                    # Atualizar last_interaction
                    bot_user.last_interaction = datetime.now()
                    db.session.commit()
                    logger.info(f"👤 Usuário retornou: {first_name} (@{username})")
            
            welcome_message = config.get('welcome_message', 'Olá! Bem-vindo!')
            welcome_media_url = config.get('welcome_media_url')
            welcome_media_type = config.get('welcome_media_type', 'video')
            main_buttons = config.get('main_buttons', [])
            
            # Preparar botões (incluir índice para identificar qual botão tem order bump)
            buttons = []
            for index, btn in enumerate(main_buttons):
                if btn.get('text') and btn.get('price'):
                    buttons.append({
                        'text': btn['text'],
                        'callback_data': f"buy_{btn.get('price')}_{btn.get('description', 'Produto')}_{index}"
                    })
            
            # Verificar se URL de mídia é válida (não pode ser canal privado)
            valid_media = False
            if welcome_media_url:
                # URLs de canais privados começam com /c/ - não funcionam
                if '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                    valid_media = True
                else:
                    logger.info(f"⚠️ Mídia de canal privado detectada - enviando só texto")
            
            if valid_media:
                # Tentar com mídia
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=welcome_message,
                    media_url=welcome_media_url,
                    media_type=welcome_media_type,
                    buttons=buttons
                )
                if not result:
                    logger.warning(f"⚠️ Falha com mídia. Enviando só texto...")
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=welcome_message,
                        media_url=None,
                        media_type=None,
                        buttons=buttons
                    )
            else:
                # Enviar direto sem mídia (mais rápido e confiável)
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=welcome_message,
                    media_url=None,
                    media_type=None,
                    buttons=buttons
                )
            
            if result:
                logger.info(f"✅ Mensagem /start enviada com {len(buttons)} botão(ões)")
            else:
                logger.error(f"❌ Falha ao enviar mensagem")
            
            # Emitir evento via WebSocket
            self.socketio.emit('bot_interaction', {
                'bot_id': bot_id,
                'type': 'start',
                'chat_id': chat_id,
                'user': message.get('from', {}).get('first_name', 'Usuário')
            })
            
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar /start: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_callback_query(self, bot_id: int, token: str, config: Dict[str, Any], 
                               callback: Dict[str, Any]):
        """
        Processa clique em botão e GERA PIX
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            callback: Dados do callback
        """
        try:
            callback_data = callback.get('data', '')
            chat_id = callback['message']['chat']['id']
            user_info = callback.get('from', {})
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔘 CLIQUE NO BOTÃO: {callback_data}")
            logger.info(f"👤 Cliente: {user_info.get('first_name')}")
            logger.info(f"{'='*60}")
            
            callback_id = callback['id']
            url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
            
            # Botão de VERIFICAR PAGAMENTO
            if callback_data.startswith('verify_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔍 Verificando pagamento...'
                }, timeout=3)
                payment_id = callback_data.replace('verify_', '')
                logger.info(f"🔍 Verificando pagamento: {payment_id}")
                
                self._handle_verify_payment(bot_id, token, chat_id, payment_id, user_info)
            
            # Botão de REMARKETING (compra via remarketing)
            elif '_remarketing_' in callback_data:
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando PIX da oferta...'
                }, timeout=3)
                
                # Extrair dados: buy_PRICE|DESCRIPTION|remarketing_CAMPAIGN_ID
                try:
                    # Remove "buy_" e separa por "|remarketing_"
                    data_part = callback_data.replace('buy_', '')
                    if '|remarketing_' in data_part:
                        parts = data_part.split('|remarketing_')
                        # Divide price|description
                        price_and_desc = parts[0].split('|')
                        price = float(price_and_desc[0])
                        description = price_and_desc[1] if len(price_and_desc) > 1 else 'Produto Remarketing'
                        campaign_id = int(parts[1]) if len(parts) > 1 else 0
                    else:
                        # Fallback para formato antigo (compatibilidade)
                        parts = data_part.split('_remarketing_')
                        price_and_desc = parts[0].rsplit('_', 1)
                        price = float(price_and_desc[0])
                        description = price_and_desc[1] if len(price_and_desc) > 1 else 'Produto Remarketing'
                        campaign_id = int(parts[1]) if len(parts) > 1 else 0
                except Exception as e:
                    logger.error(f"❌ Erro ao parsear callback de remarketing: {callback_data} - {e}")
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao processar sua solicitação. Entre em contato com o suporte."
                    )
                    return
                
                logger.info(f"📢 COMPRA VIA REMARKETING | Campanha: {campaign_id} | Produto: {description} | Valor: R$ {price:.2f}")
                
                # Gerar PIX direto (sem order bump em remarketing)
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', ''))
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""
🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📋 <b>PIX Copia e Cola:</b>
<code>{pix_data.get('pix_code')}</code>

⏰ <b>Válido por:</b> 30 minutos

👇 <b>Clique no botão abaixo para verificar o pagamento:</b>
"""
                    
                    verify_button = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f"verify_{pix_data.get('payment_id')}"
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message,
                        buttons=verify_button
                    )
                    
                    logger.info(f"✅ PIX ENVIADO (Remarketing)! ID: {pix_data.get('payment_id')}")
                    
                    # Atualizar stats da campanha
                    from app import app, db
                    from models import RemarketingCampaign
                    with app.app_context():
                        campaign = RemarketingCampaign.query.get(campaign_id)
                        if campaign:
                            campaign.total_clicks += 1
                            db.session.commit()
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            # Resposta do ORDER BUMP - SIM
            elif callback_data.startswith('bump_yes_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '✅ Order bump adicionado! Gerando PIX...'
                }, timeout=3)
                
                parts = callback_data.replace('bump_yes_', '').split('_', 3)
                original_price = float(parts[0])
                bump_price = float(parts[1])
                description = parts[2]
                
                total_price = original_price + bump_price
                final_description = f"{description} + Bônus"
                
                logger.info(f"✅ Cliente ACEITOU order bump! Total: R$ {total_price:.2f}")
                
                # Gerar PIX com valor TOTAL (produto + order bump) + ANALYTICS
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=total_price,
                    description=final_description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=True,
                    order_bump_value=bump_price
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""
🎯 <b>Produto:</b> {final_description}
💰 <b>Valor:</b> R$ {total_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque para copiar o código PIX</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>
                    """
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX gerado COM order bump!")
                    
                    # Agendar downsells se habilitados
                    bot_info = self.active_bots.get(bot_id, {})
                    config = bot_info.get('config', {})
                    
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - list: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells (Order Bump) - downsells encontrados: {len(downsells)}")
                        if downsells:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (Order Bump)")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados (Order Bump)")
            
            # Resposta do ORDER BUMP - NÃO
            elif callback_data.startswith('bump_no_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando PIX do valor original...'
                }, timeout=3)
                
                parts = callback_data.replace('bump_no_', '').split('_', 2)
                price = float(parts[0])
                description = parts[1]
                
                logger.info(f"❌ Cliente RECUSOU order bump. Gerando PIX do valor original...")
                
                # Gerar PIX com valor ORIGINAL (sem order bump) + ANALYTICS
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=False,
                    order_bump_value=0.0
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""
🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque para copiar o código PIX</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>
                    """
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX gerado SEM order bump!")
                    
                    # Agendar downsells se habilitados
                    bot_info = self.active_bots.get(bot_id, {})
                    config = bot_info.get('config', {})
                    
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - list: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells (bump_no) - downsells encontrados: {len(downsells)}")
                        if downsells:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (bump_no)")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados (bump_no)")
            
            # Botão de compra (VERIFICAR SE TEM ORDER BUMP)
            elif callback_data.startswith('buy_'):
                # Verificar se é um downsell (formato: buy_PRICE_PAYMENT_ID_downsell_INDEX)
                if '_downsell_' in callback_data:
                    # Formato: buy_10.0_BOT1_123_downsell_0
                    parts = callback_data.split('_')
                    price = float(parts[1])
                    # O description é o payment_id original (para rastreamento)
                    description = f"Downsell {parts[-1]}"
                    button_index = -1  # Sinalizar que é downsell
                    
                    logger.info(f"💰 DOWNSELL CLICADO | Valor: R$ {price:.2f}")
                else:
                    # Formato normal: buy_PRICE_DESCRIPTION_BUTTON_INDEX
                    parts = callback_data.split('_', 3)
                    price = float(parts[1]) if len(parts) > 1 else 0
                    description = parts[2] if len(parts) > 2 else 'Produto'
                    button_index = int(parts[3]) if len(parts) > 3 else 0
                    
                    logger.info(f"💰 Produto: {description} | Valor: R$ {price:.2f} | Botão: {button_index}")
                
                # VERIFICAR SE TEM ORDER BUMP PARA ESTE BOTÃO (somente se não for downsell)
                main_buttons = config.get('main_buttons', [])
                order_bump = None
                
                if button_index >= 0 and button_index < len(main_buttons):
                    button_data = main_buttons[button_index]
                    order_bump = button_data.get('order_bump', {})
                    
                    if order_bump and order_bump.get('enabled'):
                        # Responder callback - AGUARDANDO order bump
                        requests.post(url, json={
                            'callback_query_id': callback_id,
                            'text': '🎁 Oferta especial para você!'
                        }, timeout=3)
                        
                        logger.info(f"🎁 Order Bump detectado para este botão!")
                        self._show_order_bump(bot_id, token, chat_id, user_info, 
                                             price, description, button_index, order_bump)
                        return  # Aguarda resposta do order bump
                
                # SEM ORDER BUMP - Gerar PIX direto
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Verificar se é downsell
                is_downsell_purchase = '_downsell_' in callback_data
                downsell_idx = None
                if is_downsell_purchase:
                    # Extrair índice do downsell do callback_data
                    parts = callback_data.split('_downsell_')
                    if len(parts) > 1:
                        downsell_idx = int(parts[1])
                
                logger.info(f"📝 {'DOWNSELL' if is_downsell_purchase else 'Sem order bump'} - gerando PIX direto...")
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    is_downsell=is_downsell_purchase,
                    downsell_index=downsell_idx
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # Enviar PIX para o cliente
                    payment_message = f"""
🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque para copiar o código PIX</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>
                    """
                    
                    # Botão para VERIFICAR PAGAMENTO
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX ENVIADO! ID: {pix_data.get('payment_id')}")
                    
                    # Agendar downsells se habilitados
                    bot_info = self.active_bots.get(bot_id, {})
                    config = bot_info.get('config', {})
                    
                    logger.info(f"🔍 DEBUG Downsells - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells - list: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells - downsells encontrados: {len(downsells)}")
                        if downsells:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia!")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados")
                    
                    logger.info(f"{'='*60}\n")
                else:
                    # Erro CRÍTICO ao gerar PIX
                    logger.error(f"❌ FALHA CRÍTICA: Não foi possível gerar PIX!")
                    logger.error(f"Verifique suas credenciais SyncPay no painel!")
                    
                    error_message = """
❌ <b>ERRO AO GERAR PAGAMENTO</b>

Desculpe, não foi possível processar seu pagamento.

<b>Entre em contato com o suporte.</b>
                    """
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message.strip()
                    )
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar callback: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_verify_payment(self, bot_id: int, token: str, chat_id: int, 
                               payment_id: str, user_info: Dict[str, Any]):
        """
        Verifica status do pagamento e libera acesso se pago
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            payment_id: ID do pagamento
            user_info: Informações do usuário
        """
        try:
            from models import Payment, Bot, db
            from app import app
            
            with app.app_context():
                # Buscar pagamento no banco
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                
                if not payment:
                    logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Pagamento não encontrado. Entre em contato com o suporte."
                    )
                    return
                
                logger.info(f"📊 Status do pagamento: {payment.status}")
                
                if payment.status == 'paid':
                    # PAGAMENTO CONFIRMADO! Liberar acesso
                    logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                    
                    # Cancelar downsells agendados
                    self.cancel_downsells(payment.payment_id)
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    access_link = bot_config.get('access_link', '')
                    custom_success_message = bot_config.get('success_message', '').strip()
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_success_message:
                        # Substituir variáveis
                        success_message = custom_success_message
                        success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                        success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                        success_message = success_message.replace('{link}', access_link or 'Link não configurado')
                    elif access_link:
                        success_message = f"""
✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado com sucesso!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor pago:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀
                        """
                    else:
                        success_message = "✅ Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=success_message.strip()
                    )
                    
                    logger.info(f"✅ Acesso liberado para {user_info.get('first_name')}")
                else:
                    # PAGAMENTO AINDA PENDENTE
                    logger.info(f"⏳ Pagamento ainda pendente...")
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    custom_pending_message = bot_config.get('pending_message', '').strip()
                    pix_code = payment.product_description or 'Aguardando...'
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_pending_message:
                        # Substituir variáveis
                        pending_message = custom_pending_message
                        pending_message = pending_message.replace('{pix_code}', f'<code>{pix_code}</code>')
                        pending_message = pending_message.replace('{produto}', payment.product_name or 'Produto')
                        pending_message = pending_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                    else:
                        pending_message = f"""
⏳ <b>Pagamento ainda não identificado</b>

Seu pagamento ainda não foi confirmado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

💡 <b>O que fazer:</b>
1. Verifique se você realmente pagou o PIX
2. Aguarde alguns minutos (pode levar até 5 min)
3. Clique novamente em "Verificar Pagamento"

⏰ Se já pagou, aguarde a confirmação automática!
                        """
                    
                    # Reenviar botão de verificar
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{payment_id}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=pending_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"⏳ Cliente avisado que pagamento ainda está pendente")
        
        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamento: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_order_bump(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                        original_price: float, original_description: str, button_index: int,
                        order_bump: Dict[str, Any]):
        """
        Exibe Order Bump PERSONALIZADO com MÍDIA e BOTÕES CUSTOMIZÁVEIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usuário
            original_price: Preço original
            original_description: Descrição original
            button_index: Índice do botão
            order_bump: Dados completos do order bump
        """
        try:
            bump_message = order_bump.get('message', '')
            bump_price = float(order_bump.get('price', 0))
            bump_description = order_bump.get('description', 'Bônus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            total_price = original_price + bump_price
            
            logger.info(f"🎁 Exibindo Order Bump: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usuário
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padrão
            accept_button_text = accept_text.strip() if accept_text else f'✅ SIM! Quero por R$ {total_price:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'❌ NÃO, continuar com R$ {original_price:.2f}'
            
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'bump_yes_{original_price}_{bump_price}_{original_description}_{button_index}'
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'bump_no_{original_price}_{original_description}_{button_index}'
                }
            ]
            
            # Verificar se mídia é válida
            valid_media = False
            if bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http'):
                valid_media = True
            
            # Enviar com ou sem mídia
            if valid_media:
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    media_url=bump_media_url,
                    media_type=bump_media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=order_bump_message.strip(),
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    buttons=buttons
                )
            
            logger.info(f"✅ Order Bump exibido!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao exibir order bump: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_pix_payment(self, bot_id: int, amount: float, description: str,
                             customer_name: str, customer_username: str, customer_user_id: str,
                             order_bump_shown: bool = False, order_bump_accepted: bool = False, 
                             order_bump_value: float = 0.0, is_downsell: bool = False, 
                             downsell_index: int = None) -> Optional[Dict[str, Any]]:
        """
        Gera pagamento PIX via gateway configurado
        
        Args:
            bot_id: ID do bot
            amount: Valor do pagamento
            description: Descrição do produto
            customer_name: Nome do cliente
            customer_username: Username do Telegram
            customer_user_id: ID do usuário no Telegram
            
        Returns:
            Dados do PIX gerado (pix_code, qr_code_url, payment_id)
        """
        try:
            # Importar models dentro da função para evitar circular import
            from models import Bot, Gateway, Payment, db
            from app import app
            
            with app.app_context():
                # Buscar bot e gateway
                bot = Bot.query.get(bot_id)
                if not bot:
                    logger.error(f"Bot {bot_id} não encontrado")
                    return None
                
                # Buscar gateway ativo e verificado do usuário
                gateway = Gateway.query.filter_by(
                    user_id=bot.user_id,
                    is_active=True,
                    is_verified=True
                ).first()
                
                if not gateway:
                    logger.error(f"Nenhum gateway ativo encontrado para usuário {bot.user_id}")
                    return None
                
                logger.info(f"💳 Gateway: {gateway.gateway_type.upper()}")
                
                # Gerar ID único do pagamento
                import uuid
                payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # Gerar PIX via gateway
                if gateway.gateway_type == 'syncpay':
                    pix_result = self._generate_syncpay_pix(gateway, amount, description, payment_id)
                elif gateway.gateway_type == 'pushynpay':
                    pix_result = self._generate_pushynpay_pix(gateway, amount, description, payment_id)
                elif gateway.gateway_type == 'paradise':
                    pix_result = self._generate_paradise_pix(gateway, amount, description, payment_id)
                else:
                    logger.error(f"Gateway {gateway.gateway_type} não suportado")
                    return None
                
                if pix_result:
                    # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                    payment = Payment(
                        bot_id=bot_id,
                        payment_id=payment_id,
                        gateway_type=gateway.gateway_type,
                        gateway_transaction_id=pix_result.get('transaction_id'),  # Identifier da SyncPay
                        amount=amount,
                        customer_name=customer_name,
                        customer_username=customer_username,
                        customer_user_id=customer_user_id,
                        product_name=description,
                        product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio
                        status='pending',
                        # Analytics tracking
                        order_bump_shown=order_bump_shown,
                        order_bump_accepted=order_bump_accepted,
                        order_bump_value=order_bump_value,
                        is_downsell=is_downsell,
                        downsell_index=downsell_index
                    )
                    db.session.add(payment)
                    db.session.commit()
                    
                    logger.info(f"✅ Pagamento registrado | Nosso ID: {payment_id} | SyncPay ID: {pix_result.get('transaction_id')}")
                    
                    # NOTIFICAR VIA WEBSOCKET (tempo real - BROADCAST para todos do usuário)
                    try:
                        from app import socketio, app
                        from models import Bot
                        
                        with app.app_context():
                            bot = Bot.query.get(bot_id)
                            if bot:
                                # Emitir evento 'new_sale' (BROADCAST - sem room)
                                socketio.emit('new_sale', {
                                    'id': payment.id,
                                    'customer_name': customer_name,
                                    'product_name': description,
                                    'amount': float(amount),
                                    'status': 'pending',
                                    'created_at': payment.created_at.isoformat()
                                })
                                logger.info(f"📡 Evento 'new_sale' emitido - R$ {amount}")
                    except Exception as ws_error:
                        logger.warning(f"⚠️ Erro ao emitir WebSocket: {ws_error}")
                    
                    return {
                        'payment_id': payment_id,
                        'pix_code': pix_result.get('pix_code'),
                        'qr_code_url': pix_result.get('qr_code_url'),
                        'qr_code_base64': pix_result.get('qr_code_base64')
                    }
                else:
                    logger.error("Falha ao gerar PIX no gateway")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_syncpay_bearer_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """
        Gera Bearer Token da SyncPay (válido por 1 hora)
        
        Args:
            client_id: UUID do client_id
            client_secret: UUID do client_secret
            
        Returns:
            Bearer token ou None se falhar
        """
        try:
            auth_url = "https://api.syncpayments.com.br/api/partner/v1/auth-token"
            
            payload = {
                "client_id": client_id,
                "client_secret": client_secret
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔑 Gerando Bearer Token SyncPay...")
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                logger.info(f"✅ Bearer Token gerado com sucesso! Válido por {data.get('expires_in')}s")
                return access_token
            else:
                logger.error(f"❌ Erro ao gerar token: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar Bearer Token: {e}")
            return None
    
    def _generate_syncpay_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via SyncPay - API REAL OFICIAL
        Documentação: https://syncpay.apidog.io/
        Endpoint: POST /api/partner/v1/cash-in
        """
        try:
            # PASSO 1: Gerar Bearer Token
            bearer_token = self._generate_syncpay_bearer_token(
                gateway.client_id,
                gateway.client_secret
            )
            
            if not bearer_token:
                logger.error("❌ Falha ao obter Bearer Token. Verifique Client ID e Secret!")
                return None
            
            # PASSO 2: Criar pagamento PIX via cash-in
            cashin_url = "https://api.syncpayments.com.br/api/partner/v1/cash-in"
            
            # Importar para pegar URL do webhook
            import os
            webhook_base = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
            webhook_url = f"{webhook_base}/webhook/payment/syncpay"
            
            logger.info(f"🔗 Webhook URL configurada: {webhook_url}")
            
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "amount": float(amount),
                "description": description,
                "webhook_url": webhook_url,
                "client": {
                    "name": description,  # Nome do produto como cliente
                    "cpf": "00000000000",  # CPF genérico (adaptar se tiver dados reais)
                    "email": "cliente@bot.com",  # Email genérico
                    "phone": "11999999999"  # Telefone genérico
                },
                "split": [
                    {
                        "percentage": PLATFORM_SPLIT_PERCENTAGE,
                        "user_id": PLATFORM_SPLIT_USER_ID
                    }
                ]
            }
            
            logger.info(f"💰 Split configurado: {PLATFORM_SPLIT_PERCENTAGE}% para plataforma ({PLATFORM_SPLIT_USER_ID[:8]}...)")
            
            logger.info(f"📤 Criando Cash-In SyncPay (R$ {amount:.2f})...")
            
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                pix_code = data.get('pix_code')
                identifier = data.get('identifier')
                
                if pix_code:
                    logger.info(f"🎉 PIX REAL GERADO COM SUCESSO!")
                    logger.info(f"📝 Identifier SyncPay: {identifier}")
                    
                    # Gerar URL do QR Code (pode usar API externa)
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={pix_code}'
                    
                    return {
                        'pix_code': pix_code,
                        'qr_code_url': qr_code_url,
                        'transaction_id': identifier,
                        'payment_id': payment_id
                    }
                else:
                    logger.error(f"❌ Resposta não contém pix_code: {data}")
                    return None
            else:
                logger.error(f"❌ ERRO SYNCPAY: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX SyncPay: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def _generate_pushynpay_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """Gera PIX via PushynPay - IMPLEMENTAR CONFORME DOCUMENTAÇÃO"""
        logger.error("❌ PushynPay não implementado ainda. Configure a API conforme documentação oficial.")
        return None
    
    def _generate_paradise_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """Gera PIX via Paradise - IMPLEMENTAR CONFORME DOCUMENTAÇÃO"""
        logger.error("❌ Paradise não implementado ainda. Configure a API conforme documentação oficial.")
        return None
    
    def verify_gateway(self, gateway_type: str, credentials: Dict[str, Any]) -> bool:
        """
        Verifica credenciais de um gateway de pagamento
        
        Args:
            gateway_type: Tipo do gateway (syncpay, pushynpay, paradise)
            credentials: Credenciais do gateway
            
        Returns:
            True se credenciais forem válidas
        """
        try:
            if gateway_type == 'syncpay':
                return self._verify_syncpay(credentials)
            elif gateway_type == 'pushynpay':
                return self._verify_pushynpay(credentials)
            elif gateway_type == 'paradise':
                return self._verify_paradise(credentials)
            else:
                logger.warning(f"Gateway desconhecido: {gateway_type}")
                return False
        except Exception as e:
            logger.error(f"Erro ao verificar gateway {gateway_type}: {e}")
            return False
    
    def _verify_syncpay(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais SyncPay"""
        client_id = credentials.get('client_id')
        client_secret = credentials.get('client_secret')
        
        if not client_id or not client_secret:
            return False
        
        # Simulação - em produção, fazer requisição real
        # try:
        #     url = "https://api.syncpay.com.br/auth/validate"
        #     response = requests.post(url, json={
        #         'client_id': client_id,
        #         'client_secret': client_secret
        #     }, timeout=10)
        #     return response.status_code == 200
        # except:
        #     return False
        
        # Simulação de validação
        logger.info(f"Verificando SyncPay: {client_id[:10]}...")
        return len(client_id) > 10 and len(client_secret) > 10
    
    def _verify_pushynpay(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais PushynPay"""
        api_key = credentials.get('api_key')
        
        if not api_key:
            return False
        
        # Simulação - em produção, fazer requisição real
        logger.info(f"Verificando PushynPay: {api_key[:10]}...")
        return len(api_key) > 20
    
    def _verify_paradise(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais Paradise"""
        api_key = credentials.get('api_key')
        
        if not api_key:
            return False
        
        # Simulação - em produção, fazer requisição real
        logger.info(f"Verificando Paradise: {api_key[:10]}...")
        return len(api_key) > 20
    
    def process_payment_webhook(self, gateway_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook de pagamento
        
        Args:
            gateway_type: Tipo do gateway
            data: Dados do webhook
            
        Returns:
            Dados processados do pagamento
        """
        try:
            if gateway_type == 'syncpay':
                return self._process_syncpay_webhook(data)
            elif gateway_type == 'pushynpay':
                return self._process_pushynpay_webhook(data)
            elif gateway_type == 'paradise':
                return self._process_paradise_webhook(data)
            else:
                logger.warning(f"Gateway desconhecido no webhook: {gateway_type}")
                return None
        except Exception as e:
            logger.error(f"Erro ao processar webhook {gateway_type}: {e}")
            return None
    
    def _process_syncpay_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa webhook SyncPay conforme documentação oficial
        
        Webhook envia quando pagamento é confirmado
        """
        # Identificador da transação SyncPay
        identifier = data.get('identifier') or data.get('id')
        status = data.get('status', '').lower()
        amount = data.get('amount')
        
        # Mapear status da SyncPay
        mapped_status = 'pending'
        if status in ['paid', 'confirmed', 'approved']:
            mapped_status = 'paid'
        elif status in ['cancelled', 'expired', 'failed']:
            mapped_status = 'failed'
        
        logger.info(f"📥 Webhook SyncPay recebido: {identifier} - Status: {status}")
        
        return {
            'payment_id': identifier,  # Usar identifier da SyncPay
            'status': mapped_status,
            'amount': amount,
            'gateway_transaction_id': identifier
        }
    
    def _process_pushynpay_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa webhook PushynPay"""
        # Adaptar conforme documentação real do PushynPay
        return {
            'payment_id': data.get('external_reference') or data.get('id'),
            'status': self._map_pushynpay_status(data.get('status')),
            'amount': data.get('amount'),
            'gateway_transaction_id': data.get('id')
        }
    
    def _process_paradise_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa webhook Paradise"""
        # Adaptar conforme documentação real do Paradise
        return {
            'payment_id': data.get('reference') or data.get('id'),
            'status': self._map_paradise_status(data.get('status')),
            'amount': data.get('value'),
            'gateway_transaction_id': data.get('id')
        }
    
    def _map_syncpay_status(self, status: str) -> str:
        """Mapeia status do SyncPay para status interno"""
        mapping = {
            'approved': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'rejected': 'failed',
            'cancelled': 'cancelled',
            'refunded': 'refunded'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def _map_pushynpay_status(self, status: str) -> str:
        """Mapeia status do PushynPay para status interno"""
        mapping = {
            'completed': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'failed': 'failed',
            'cancelled': 'cancelled'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def _map_paradise_status(self, status: str) -> str:
        """Mapeia status do Paradise para status interno"""
        mapping = {
            'confirmed': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'expired': 'failed',
            'cancelled': 'cancelled'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def send_telegram_message(self, token: str, chat_id: str, message: str, 
                             media_url: Optional[str] = None, 
                             media_type: str = 'video',
                             buttons: Optional[list] = None):
        """
        Envia mensagem pelo Telegram
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Mensagem de texto
            media_url: URL da mídia (opcional)
            media_type: Tipo da mídia (video ou photo)
            buttons: Lista de botões inline
        """
        try:
            base_url = f"https://api.telegram.org/bot{token}"
            
            # Preparar teclado inline se houver botões
            reply_markup = None
            if buttons:
                inline_keyboard = []
                for button in buttons:
                    inline_keyboard.append([{
                        'text': button.get('text'),
                        'callback_data': button.get('callback_data', 'button_pressed')
                    }])
                reply_markup = {'inline_keyboard': inline_keyboard}
            
            # Enviar mídia + mensagem
            if media_url:
                if media_type == 'video':
                    url = f"{base_url}/sendVideo"
                    payload = {
                        'chat_id': chat_id,
                        'video': media_url,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                else:  # photo
                    url = f"{base_url}/sendPhoto"
                    payload = {
                        'chat_id': chat_id,
                        'photo': media_url,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                
                response = requests.post(url, json=payload, timeout=3)
            else:
                # Enviar apenas mensagem
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                
                response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                logger.info(f"✅ Mensagem enviada para chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Erro ao enviar mensagem: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout ao enviar mensagem para chat {chat_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem Telegram: {e}")
            return False
    
    def get_bot_status(self, bot_id: int) -> Dict[str, Any]:
        """
        Obtém status de um bot
        
        Args:
            bot_id: ID do bot
            
        Returns:
            Informações de status
        """
        if bot_id in self.active_bots:
            bot_info = self.active_bots[bot_id]
            return {
                'is_running': True,
                'status': bot_info['status'],
                'started_at': bot_info['started_at'].isoformat(),
                'uptime': (datetime.now() - bot_info['started_at']).total_seconds()
            }
        else:
            return {
                'is_running': False,
                'status': 'stopped'
            }
    
    def schedule_downsells(self, bot_id: int, payment_id: str, chat_id: int, downsells: list):
        """
        Agenda downsells para um pagamento pendente
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            downsells: Lista de downsells configurados
        """
        logger.info(f"🚨 FUNCAO SCHEDULE_DOWNSELLS CHAMADA! bot_id={bot_id}, payment_id={payment_id}")
        try:
            logger.info(f"🔍 DEBUG Schedule - scheduler existe: {self.scheduler is not None}")
            logger.info(f"🔍 DEBUG Schedule - downsells: {downsells}")
            logger.info(f"🔍 DEBUG Schedule - downsells vazio: {not downsells}")
            
            if not self.scheduler:
                logger.error(f"❌ Scheduler não está disponível!")
                return
            
            if not downsells:
                logger.warning(f"⚠️ Lista de downsells está vazia!")
                return
            
            logger.info(f"📅 Agendando {len(downsells)} downsell(s) para pagamento {payment_id}")
            
            for i, downsell in enumerate(downsells):
                delay_minutes = int(downsell.get('delay_minutes', 5))  # Converter para int
                job_id = f"downsell_{bot_id}_{payment_id}_{i}"
                
                # Calcular data/hora de execução
                run_time = datetime.now() + timedelta(minutes=delay_minutes)
                logger.info(f"🔍 DEBUG Agendamento - Hora atual: {datetime.now()}")
                logger.info(f"🔍 DEBUG Agendamento - Hora execução: {run_time}")
                
                # Agendar downsell
                self.scheduler.add_job(
                    id=job_id,
                    func=self._send_downsell,
                    args=[bot_id, payment_id, chat_id, downsell, i],
                    trigger='date',
                    run_date=run_time,
                    replace_existing=True
                )
                
                logger.info(f"✅ Downsell {i+1} agendado para {delay_minutes} minutos")
                
        except Exception as e:
            logger.error(f"❌ Erro ao agendar downsells: {e}")
    
    def _send_downsell(self, bot_id: int, payment_id: str, chat_id: int, downsell: dict, index: int):
        """
        Envia downsell agendado
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            downsell: Configuração do downsell
            index: Índice do downsell
        """
        logger.info(f"🚨 FUNCAO _SEND_DOWNSELL CHAMADA! bot_id={bot_id}, payment_id={payment_id}, index={index}")
        try:
            logger.info(f"🔍 DEBUG _send_downsell - Verificando pagamento...")
            # Verificar se pagamento ainda está pendente
            if not self._is_payment_pending(payment_id):
                logger.info(f"💰 Pagamento {payment_id} já foi pago, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Pagamento ainda está pendente")
            
            # Verificar se bot ainda está ativo
            logger.info(f"🔍 DEBUG _send_downsell - Verificando bot...")
            if bot_id not in self.active_bots:
                logger.warning(f"🤖 Bot {bot_id} não está mais ativo, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Bot está ativo")
            
            bot_info = self.active_bots[bot_id]
            token = bot_info['token']
            config = bot_info.get('config', {})
            
            # Verificar se downsells ainda estão habilitados
            logger.info(f"🔍 DEBUG _send_downsell - Verificando se downsells estão habilitados...")
            if not config.get('downsells_enabled', False):
                logger.info(f"📵 Downsells desabilitados, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Downsells estão habilitados")
            
            message = downsell.get('message', '')
            media_url = downsell.get('media_url', '')
            media_type = downsell.get('media_type', 'video')
            price = float(downsell.get('price', 0))
            button_text = downsell.get('button_text', '').strip()
            
            # Se não tiver texto personalizado, usar padrão
            if not button_text:
                button_text = f'🛒 Comprar por R$ {price:.2f}'
            
            logger.info(f"🔍 DEBUG _send_downsell - Dados do downsell:")
            logger.info(f"  - message: {message}")
            logger.info(f"  - price: {price}")
            logger.info(f"  - button_text: {button_text}")
            logger.info(f"  - media_url: {media_url}")
            
            # Criar botão de compra para o downsell
            buttons = [{
                'text': button_text,
                'callback_data': f'buy_{price}_{payment_id}_downsell_{index}'
            }]
            
            logger.info(f"📨 Enviando downsell {index+1} para chat {chat_id}")
            
            # Enviar mensagem com ou sem mídia
            if media_url and '/c/' not in media_url and media_url.startswith('http'):
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    buttons=buttons
                )
            
            logger.info(f"✅ Downsell {index+1} enviado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar downsell {index+1}: {e}")
            import traceback
            traceback.print_exc()
    
    def _is_payment_pending(self, payment_id: str) -> bool:
        """
        Verifica se pagamento ainda está pendente
        
        Args:
            payment_id: ID do pagamento
            
        Returns:
            True se ainda está pendente
        """
        try:
            from app import app, db
            from models import Payment
            
            with app.app_context():
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                logger.info(f"🔍 DEBUG _is_payment_pending - payment_id: {payment_id}")
                if payment:
                    logger.info(f"🔍 DEBUG _is_payment_pending - status: {payment.status}")
                    return payment.status == 'pending'
                else:
                    logger.warning(f"⚠️ Pagamento {payment_id} não encontrado no banco!")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status do pagamento {payment_id}: {e}")
            return False
    
    def count_eligible_leads(self, bot_id: int, target_audience: str = 'non_buyers', 
                            days_since_last_contact: int = 3, exclude_buyers: bool = True) -> int:
        """
        Conta quantos leads são elegíveis para remarketing
        
        Args:
            bot_id: ID do bot
            target_audience: Tipo de público (all, non_buyers, abandoned_cart, inactive)
            days_since_last_contact: Dias mínimos sem contato
            exclude_buyers: Excluir quem já comprou
            
        Returns:
            Quantidade de leads elegíveis
        """
        from app import app, db
        from models import BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        
        with app.app_context():
            # Data limite de último contato
            contact_limit = datetime.now() - timedelta(days=days_since_last_contact)
            
            # Query base: usuários do bot
            query = BotUser.query.filter_by(bot_id=bot_id)
            
            # Filtro: último contato há X dias
            if days_since_last_contact > 0:
                query = query.filter(BotUser.last_interaction <= contact_limit)
            
            # Filtro: excluir blacklist
            blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                bot_id=bot_id
            ).all()
            blacklist_ids = [b[0] for b in blacklist_ids]
            if blacklist_ids:
                query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
            
            # Filtro: excluir compradores
            if exclude_buyers:
                buyer_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct().all()
                buyer_ids = [b[0] for b in buyer_ids if b[0]]
                if buyer_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
            
            # Filtro por tipo de público
            if target_audience == 'abandoned_cart':
                # Usuários que geraram PIX mas não pagaram
                abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'pending'
                ).distinct().all()
                abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                if abandoned_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                else:
                    return 0
            
            elif target_audience == 'inactive':
                # Inativos há 7+ dias
                inactive_limit = datetime.now() - timedelta(days=7)
                query = query.filter(BotUser.last_interaction <= inactive_limit)
            
            return query.count()
    
    def send_remarketing_campaign(self, campaign_id: int, bot_token: str):
        """
        Envia campanha de remarketing em background
        
        Args:
            campaign_id: ID da campanha
            bot_token: Token do bot
        """
        from app import app, db, socketio
        from models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        import time
        
        def send_campaign():
            with app.app_context():
                campaign = RemarketingCampaign.query.get(campaign_id)
                if not campaign:
                    return
                
                # Atualizar status
                campaign.status = 'sending'
                campaign.started_at = datetime.now()
                db.session.commit()
                
                logger.info(f"📢 Iniciando envio de remarketing: {campaign.name}")
                
                # Buscar leads elegíveis
                contact_limit = datetime.now() - timedelta(days=campaign.days_since_last_contact)
                
                query = BotUser.query.filter_by(bot_id=campaign.bot_id)
                
                # Filtro de último contato
                if campaign.days_since_last_contact > 0:
                    query = query.filter(BotUser.last_interaction <= contact_limit)
                
                # Excluir blacklist
                blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                    bot_id=campaign.bot_id
                ).all()
                blacklist_ids = [b[0] for b in blacklist_ids]
                if blacklist_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                
                # Excluir compradores
                if campaign.exclude_buyers:
                    buyer_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'paid'
                    ).distinct().all()
                    buyer_ids = [b[0] for b in buyer_ids if b[0]]
                    if buyer_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                
                # Segmentação por público
                if campaign.target_audience == 'abandoned_cart':
                    abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'pending'
                    ).distinct().all()
                    abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                    if abandoned_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                
                elif campaign.target_audience == 'inactive':
                    inactive_limit = datetime.now() - timedelta(days=7)
                    query = query.filter(BotUser.last_interaction <= inactive_limit)
                
                leads = query.all()
                campaign.total_targets = len(leads)
                db.session.commit()
                
                logger.info(f"🎯 {campaign.total_targets} leads elegíveis")
                
                # Enviar em batches (20 msgs/segundo)
                batch_size = 20
                for i in range(0, len(leads), batch_size):
                    batch = leads[i:i+batch_size]
                    
                    for lead in batch:
                        try:
                            # Personalizar mensagem
                            message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                            message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])
                            
                            # Preparar botões (converter para formato de callback_data)
                            remarketing_buttons = []
                            if campaign.buttons:
                                for btn in campaign.buttons:
                                    if btn.get('price') and btn.get('description'):
                                        # Botão de compra - gera PIX
                                        # Formato: buy_PRICE|DESCRIPTION|remarketing_CAMPAIGN_ID
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Comprar'),
                                            'callback_data': f"buy_{btn.get('price')}|{btn.get('description')}|remarketing_{campaign.id}"
                                        })
                                    elif btn.get('url'):
                                        # Botão de URL
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Link'),
                                            'url': btn.get('url')
                                        })
                            
                            # Log dos botões para debug
                            logger.info(f"📤 Enviando para {lead.first_name} com {len(remarketing_buttons)} botão(ões)")
                            for btn in remarketing_buttons:
                                logger.info(f"   🔘 Botão: {btn.get('text')} | callback: {btn.get('callback_data', 'N/A')[:50]}")
                            
                            # Enviar mensagem
                            result = self.send_telegram_message(
                                token=bot_token,
                                chat_id=lead.telegram_user_id,
                                message=message,
                                media_url=campaign.media_url,
                                media_type=campaign.media_type,
                                buttons=remarketing_buttons
                            )
                            
                            if result:
                                campaign.total_sent += 1
                            else:
                                campaign.total_failed += 1
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao enviar para {lead.telegram_user_id}: {e}")
                            if "bot was blocked" in str(e).lower():
                                campaign.total_blocked += 1
                                # Adicionar na blacklist
                                blacklist = RemarketingBlacklist(
                                    bot_id=campaign.bot_id,
                                    telegram_user_id=lead.telegram_user_id,
                                    reason='bot_blocked'
                                )
                                db.session.add(blacklist)
                            else:
                                campaign.total_failed += 1
                    
                    # Commit do batch
                    db.session.commit()
                    
                    # Emitir progresso via WebSocket
                    socketio.emit('remarketing_progress', {
                        'campaign_id': campaign.id,
                        'sent': campaign.total_sent,
                        'failed': campaign.total_failed,
                        'blocked': campaign.total_blocked,
                        'total': campaign.total_targets,
                        'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                    })
                    
                    # Rate limiting (20 msgs/segundo)
                    time.sleep(1)
                
                # Finalizar campanha
                campaign.status = 'completed'
                campaign.completed_at = datetime.now()
                db.session.commit()
                
                logger.info(f"✅ Campanha concluída: {campaign.total_sent}/{campaign.total_targets} enviados")
                
                # Emitir conclusão
                socketio.emit('remarketing_completed', {
                    'campaign_id': campaign.id,
                    'total_sent': campaign.total_sent,
                    'total_failed': campaign.total_failed,
                    'total_blocked': campaign.total_blocked
                })
        
        # Executar em thread separada
        thread = threading.Thread(target=send_campaign)
        thread.daemon = True
        thread.start()
    
    def cancel_downsells(self, payment_id: str):
        """
        Cancela downsells agendados para um pagamento
        
        Args:
            payment_id: ID do pagamento
        """
        try:
            if not self.scheduler:
                return
            
            # Encontrar e remover jobs de downsell para este pagamento
            jobs_to_remove = []
            for job_id in self.scheduler.get_jobs():
                if job_id.id.startswith(f"downsell_") and payment_id in job_id.id:
                    jobs_to_remove.append(job_id.id)
            
            for job_id in jobs_to_remove:
                self.scheduler.remove_job(job_id)
                logger.info(f"🚫 Downsell cancelado: {job_id}")
                
        except Exception as e:
            logger.error(f"Erro ao cancelar downsells para pagamento {payment_id}: {e}")

