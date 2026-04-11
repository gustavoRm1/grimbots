"""
Remarketing Service - Motor de Envio de Campanhas
============================================
Serviço responsável pelo envio de campanhas de remarketing
com controle de cadência, blacklist automática e placeholders.

✅ TRANSPLANTED: Lógica completa do legado com rate limiting
"""

import logging
import time
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from internal_logic.core.extensions import db, socketio
from internal_logic.core.models import (
    Bot, BotUser, RemarketingCampaign, RemarketingBlacklist, 
    Payment, get_brazil_time
)
from bot_manager import BotManager

logger = logging.getLogger(__name__)


class RemarketingService:
    """Serviço de envio de campanhas de remarketing com controle inteligente"""
    
    def __init__(self, bot_manager: Optional[BotManager] = None):
        self.bot_manager = bot_manager
        self.worker_threads = {}  # thread_id -> campaign_id
        self.stop_events = {}    # stop_event_id -> threading.Event
        
    def send_campaign_async(self, campaign_id: int, user_id: int):
        """
        Envia campanha de forma assíncrona usando thread dedicada
        (similar ao legado que usava RQ worker)
        """
        try:
            campaign = RemarketingCampaign.query.filter_by(id=campaign_id).first()
            if not campaign:
                logger.error(f"❌ Campanha {campaign_id} não encontrada")
                return
            
            # Verificar se já está rodando
            if campaign.status == 'sending':
                logger.warning(f"⚠️ Campanha {campaign_id} já está em andamento")
                return
            
            # Atualizar status
            campaign.status = 'sending'
            campaign.started_at = get_brazil_time()
            campaign.total_targets = 0
            campaign.total_sent = 0
            campaign.total_failed = 0
            campaign.total_blocked = 0
            db.session.commit()
            
            # Criar thread dedicada
            stop_event = threading.Event()
            thread_id = f"remarketing_{campaign_id}_{int(time.time())}"
            self.stop_events[thread_id] = stop_event
            
            worker_thread = threading.Thread(
                target=self._campaign_worker,
                args=(campaign, user_id, stop_event, thread_id),
                name=f"RemarketingWorker-{campaign_id}"
            )
            
            self.worker_threads[thread_id] = worker_thread
            worker_thread.daemon = True
            worker_thread.start()
            
            logger.info(f"🚀 Campanha {campaign_id} iniciada em thread {thread_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar campanha {campaign_id}: {e}", exc_info=True)
            if campaign:
                campaign.status = 'failed'
                campaign.error_message = str(e)
                db.session.commit()
    
    def _campaign_worker(self, campaign: RemarketingCampaign, user_id: int, 
                     stop_event: threading.Event, thread_id: str):
        """
        Worker que processa o envio da campanha com rate limiting
        """
        try:
            logger.info(f"🔄 Worker {thread_id} iniciado para campanha {campaign.id}")
            
            # Buscar alvos da campanha
            targets = self._get_campaign_targets(campaign)
            campaign.total_targets = len(targets)
            db.session.commit()
            
            logger.info(f"🎯 Campanha {campaign.id}: {len(targets)} alvos encontrados")
            
            # Enviar mensagens com rate limiting
            for i, target in enumerate(targets):
                # Verificar se deve parar
                if stop_event.is_set():
                    logger.info(f"⏹️ Worker {thread_id} interrompido")
                    break
                
                try:
                    # ✅ RATE LIMITING CRÍTICO: 1.2s-2.5s entre mensagens
                    # Isso é a segurança do sistema contra ban do Telegram
                    delay = 1.2 + (i % 2) * 0.8  # Varia entre 1.2s e 2.0s
                    
                    # Verificar se usuário está na blacklist
                    if self._is_blacklisted(campaign.bot_id, target['telegram_user_id']):
                        logger.info(f"🚫 Usuário {target['telegram_user_id']} está na blacklist - pulando")
                        campaign.total_blocked += 1
                        continue
                    
                    # Processar placeholders
                    message = self._process_placeholders(
                        campaign.message, 
                        target.get('first_name', 'Cliente'),
                        target.get('name', target.get('first_name', 'Cliente'))
                    )
                    
                    # Enviar mensagem
                    success = self._send_message(
                        campaign.bot,
                        target['telegram_user_id'],
                        message,
                        campaign.media_url,
                        campaign.media_type,
                        campaign.audio_url if campaign.audio_enabled else None,
                        campaign.get_buttons() if campaign.buttons else []
                    )
                    
                    if success:
                        campaign.total_sent += 1
                        logger.info(f"✅ [{i+1}/{len(targets)}] Enviado para {target['telegram_user_id']}")
                        
                        # Emitir progresso via WebSocket
                        socketio.emit('remarketing_progress', {
                            'campaign_id': campaign.id,
                            'current': i + 1,
                            'total': len(targets),
                            'sent': campaign.total_sent,
                            'failed': campaign.total_failed,
                            'blocked': campaign.total_blocked
                        }, room=f"user_{user_id}")
                    else:
                        campaign.total_failed += 1
                        logger.warning(f"❌ [{i+1}/{len(targets)}] Falha para {target['telegram_user_id']}")
                    
                    # ✅ RATE LIMITING: Pausa entre mensagens
                    time.sleep(delay)
                    
                except Exception as e:
                    campaign.total_failed += 1
                    logger.error(f"❌ Erro ao enviar para {target['telegram_user_id']}: {e}")
            
            # Finalizar campanha
            campaign.status = 'completed'
            campaign.completed_at = get_brazil_time()
            db.session.commit()
            
            logger.info(f"🏁 Campanha {campaign.id} finalizada:")
            logger.info(f"   - Total: {campaign.total_targets}")
            logger.info(f"   - Enviados: {campaign.total_sent}")
            logger.info(f"   - Falhas: {campaign.total_failed}")
            logger.info(f"   - Bloqueados: {campaign.total_blocked}")
            
            # Emitir evento de conclusão
            socketio.emit('remarketing_completed', {
                'campaign_id': campaign.id,
                'status': 'completed',
                'total_targets': campaign.total_targets,
                'total_sent': campaign.total_sent,
                'total_failed': campaign.total_failed,
                'total_blocked': campaign.total_blocked
            }, room=f"user_{user_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro no worker {thread_id}: {e}", exc_info=True)
            campaign.status = 'failed'
            campaign.error_message = str(e)
            campaign.completed_at = get_brazil_time()
            db.session.commit()
        
        finally:
            # Limpar recursos
            self.worker_threads.pop(thread_id, None)
            self.stop_events.pop(thread_id, None)
            logger.info(f"🧹 Worker {thread_id} finalizado e recursos limpos")
    
    def _get_campaign_targets(self, campaign: RemarketingCampaign) -> List[Dict[str, Any]]:
        """
        Busca usuários alvo baseado na segmentação da campanha
        """
        from internal_logic.core.models import PoolBot
        
        try:
            # Base query
            query = BotUser.query.filter_by(bot_id=campaign.bot_id)
            
            # Aplicar filtros de segmentação
            if campaign.target_audience == 'all':
                pass  # Todos os usuários
            elif campaign.target_audience == 'non_buyers':
                # Nunca compraram
                paid_users = Payment.query.filter_by(
                    bot_id=campaign.bot_id, 
                    status='paid'
                ).with_entities(Payment.customer_user_id).distinct().subquery()
                query = query.filter(~BotUser.telegram_user_id.in_(paid_users))
            elif campaign.target_audience == 'buyers':
                # Já compraram
                paid_users = Payment.query.filter_by(
                    bot_id=campaign.bot_id, 
                    status='paid'
                ).with_entities(Payment.customer_user_id).distinct().subquery()
                query = query.filter(BotUser.telegram_user_id.in_(paid_users))
            elif campaign.target_audience == 'abandoned_cart':
                # Carrinho abandonado (pending)
                pending_users = Payment.query.filter_by(
                    bot_id=campaign.bot_id, 
                    status='pending'
                ).with_entities(Payment.customer_user_id).distinct().subquery()
                query = query.filter(BotUser.telegram_user_id.in_(pending_users))
            elif campaign.target_audience == 'inactive':
                # Inativos há 7+ dias
                cutoff_date = get_brazil_time() - timedelta(days=7)
                query = query.filter(BotUser.last_message_at < cutoff_date)
            
            # Filtro de cooldown (último contato)
            if campaign.days_since_last_contact:
                cutoff_date = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                query = query.filter(
                    (BotUser.last_message_at < cutoff_date) | 
                    (BotUser.last_message_at.is_(None))
                )
            
            # Excluir compradores (legado)
            if campaign.exclude_buyers:
                paid_users = Payment.query.filter_by(
                    bot_id=campaign.bot_id, 
                    status='paid'
                ).with_entities(Payment.customer_user_id).distinct().subquery()
                query = query.filter(~BotUser.telegram_user_id.in_(paid_users))
            
            # Executar query
            users = query.all()
            
            # Converter para dicionários
            targets = []
            for user in users:
                # Extrair primeiro nome do full_name se disponível
                first_name = user.full_name.split()[0] if user.full_name else user.first_name or "Cliente"
                
                targets.append({
                    'telegram_user_id': user.telegram_user_id,
                    'name': user.full_name or user.first_name or "Cliente",
                    'first_name': first_name
                })
            
            return targets
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar alvos da campanha {campaign.id}: {e}", exc_info=True)
            return []
    
    def _is_blacklisted(self, bot_id: int, telegram_user_id: str) -> bool:
        """Verifica se usuário está na blacklist"""
        try:
            blacklist = RemarketingBlacklist.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id
            ).first()
            return blacklist is not None
        except Exception as e:
            logger.error(f"❌ Erro ao verificar blacklist: {e}")
            return False
    
    def _process_placeholders(self, message: str, first_name: str, name: str) -> str:
        """
        Substitui placeholders {nome} e {primeiro_nome} na mensagem
        """
        try:
            if not message:
                return ""
            
            # Substituir {primeiro_nome} primeiro para não quebrar {nome}
            if '{primeiro_nome}' in message:
                message = message.replace('{primeiro_nome}', first_name)
            
            # Substituir {nome} pelo nome completo
            if '{nome}' in message:
                message = message.replace('{nome}', name)
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar placeholders: {e}")
            return message or ""
    
    def _send_message(self, bot: Bot, telegram_user_id: str, message: str, 
                   media_url: Optional[str] = None, media_type: Optional[str] = None,
                   audio_url: Optional[str] = None, buttons: Optional[List[Dict]] = None) -> bool:
        """
        Envia mensagem via BotManager com tratamento de blacklist automática
        """
        try:
            if not self.bot_manager:
                # Criar BotManager localmente
                from internal_logic.core.extensions import socketio
                self.bot_manager = BotManager(
                    socketio=socketio, 
                    scheduler=None, 
                    user_id=bot.user_id
                )
            
            # Enviar mensagem
            result = self.bot_manager.send_telegram_message(
                token=bot.token,
                chat_id=telegram_user_id,
                message=message.strip(),
                media_url=media_url,
                media_type=media_type,
                audio_url=audio_url,
                buttons=buttons or []
            )
            
            if result:
                return True
            else:
                # ✅ BLACKLIST AUTOMÁTICA: Se falhar, verificar se foi bloqueio
                # O BotManager já adiciona à blacklist automaticamente em caso de 403
                logger.warning(f"⚠️ Falha ao enviar para {telegram_user_id} - possível bloqueio")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return False
    
    def stop_campaign(self, campaign_id: int) -> bool:
        """
        Para campanha em andamento
        """
        try:
            # Encontrar thread da campanha
            for thread_id, thread in self.worker_threads.items():
                if thread.is_alive() and f"remarketing_{campaign_id}_" in thread_id:
                    # Sinalizar para parar
                    stop_event = self.stop_events.get(thread_id)
                    if stop_event:
                        stop_event.set()
                        logger.info(f"🛑 Sinalizado stop para campanha {campaign_id}")
                        return True
            
            # Se não encontrou thread, atualizar status no banco
            campaign = RemarketingCampaign.query.filter_by(id=campaign_id).first()
            if campaign and campaign.status == 'sending':
                campaign.status = 'paused'
                db.session.commit()
                logger.info(f"⏸️ Campanha {campaign_id} pausada no banco")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar campanha {campaign_id}: {e}")
            return False
    
    def get_campaign_status(self, campaign_id: int) -> Dict[str, Any]:
        """
        Retorna status atual da campanha
        """
        try:
            campaign = RemarketingCampaign.query.filter_by(id=campaign_id).first()
            if not campaign:
                return {'error': 'Campanha não encontrada'}
            
            # Verificar se está rodando em thread
            is_running = any(
                thread.is_alive() and f"remarketing_{campaign_id}_" in thread_id
                for thread_id, thread in self.worker_threads.items()
            )
            
            return {
                'campaign': campaign.to_dict(),
                'is_running': is_running,
                'progress_percentage': (
                    (campaign.total_sent / campaign.total_targets * 100) 
                    if campaign.total_targets > 0 else 0
                )
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter status da campanha {campaign_id}: {e}")
            return {'error': str(e)}


# BOMBA GLOBAL DESARMADA - Isolamento por usuário para prevenir contaminação
# TODO: Implementar arquitetura multitenancy completa com user_id como chave
_user_services = {}  # user_id -> RemarketingService isolado

def get_remarketing_service(bot_manager: Optional[BotManager] = None, user_id: Optional[int] = None) -> RemarketingService:
    """
    Retorna instância ISOLADA por usuário para prevenir vazamento de dados
    
    CRITICAL: Singleton global foi removido para impedir contaminação cruzada
    entre sessões de diferentes usuários (Herança Maldita)
    """
    from flask_login import current_user
    
    # Usar user_id explícito ou current_user.id
    effective_user_id = user_id or (current_user.id if current_user else None)
    
    if not effective_user_id:
        # Fallback para modo legado (sem isolamento) - LOGAR COMO RISCO
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("[SECURITY] get_remarketing_service chamado sem user_id - RISCO DE CONTAMINAÇÃO")
        return RemarketingService(bot_manager)
    
    # Isolar instância por usuário
    if effective_user_id not in _user_services:
        _user_services[effective_user_id] = RemarketingService(bot_manager)
    
    return _user_services[effective_user_id]
