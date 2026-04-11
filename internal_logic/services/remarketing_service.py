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
            # Capturar app Flask ANTES da thread para App Context
            from flask import current_app
            app = current_app._get_current_object()
            
            campaign = RemarketingCampaign.query.filter_by(id=campaign_id).first()
            if not campaign:
                logger.error(f" Campanha {campaign_id} não encontrada")
                return
            
            # Verificar se já está rodando
            if campaign.status == 'sending':
                logger.warning(f" Campanha {campaign_id} já está em andamento")
                return
            
            # Atualizar status - Web server APENAS enfileira, não inicia disparo
            campaign.status = 'queued'
            campaign.started_at = get_brazil_time()
            campaign.total_targets = 0
            campaign.total_sent = 0
            campaign.total_failed = 0
            campaign.total_blocked = 0
            db.session.commit()
            
            logger.info(f" Campanha {campaign_id} enfileirada para processamento assíncrono")
            
        except Exception as e:
            logger.error(f" Erro ao iniciar campanha {campaign_id}: {e}", exc_info=True)
            if campaign:
                campaign.status = 'failed'
                campaign.error_message = str(e)
                db.session.commit()
    
    def _campaign_worker(self, app, campaign_id: int, user_id: int, 
                     stop_event: threading.Event, thread_id: str):
        """
        Worker que processa o envio da campanha com rate limiting
        """
        import traceback
        
        # CAIXA PRETA - Try/Except GLOBAL para capturar morte súbita
        try:
            # INJETAR APP CONTEXT - O DESFIBRILADOR
            with app.app_context():
                logger.info(f" Worker {thread_id} iniciado para campanha {campaign_id}")
                
                # Buscar campanha FRESCA do banco (evitar DetachedInstanceError)
                campaign = db.session.get(RemarketingCampaign, campaign_id)
                if not campaign:
                    logger.error(f" Campanha {campaign_id} não encontrada no worker")
                    return
                
                # Buscar alvos da campanha
                targets = self._get_campaign_targets(campaign, user_id)
                
                # VALIDAÇÃO DO TOTAL_TARGETS - Impedir campanha com 0 leads
                if not targets:
                    raise ValueError("Nenhum lead encontrado para os filtros selecionados.")
                
                campaign.total_targets = len(targets)
                db.session.commit()
                
                logger.info(f"AUDIT: total_targets atualizado para {campaign.total_targets} e commitado")
                logger.info(f" Campanha {campaign_id}: {len(targets)} alvos encontrados")
            
            # Enviar mensagens com rate limiting
            for i, target in enumerate(targets):
                # Verificar se deve parar
                if stop_event.is_set():
                    logger.info(f" Worker {thread_id} interrompido")
                    logger.info(f" Worker {thread_id} interrompido")
                    break
                
                try:
                    # RATE LIMITING CRÍTICO: 1.2s-2.5s entre mensagens
                    # Isso é a segurança do sistema contra ban do Telegram
                    delay = 1.2 + (i % 2) * 0.8  # Varia entre 1.2s e 2.0s
                    
                    # Verificar se usuário está na blacklist
                    if self._is_blacklisted(campaign.bot_id, target['telegram_user_id']):
                        logger.info(f" Usuário {target['telegram_user_id']} está na blacklist - pulando")
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
                        logger.info(f" Mensagem {i+1}/{len(targets)} enviada para {target['telegram_user_id']}")
                    else:
                        campaign.total_failed += 1
                        logger.error(f" Falha ao enviar mensagem {i+1}/{len(targets)} para {target['telegram_user_id']}")
                    
                    # Commit progresso
                    db.session.commit()
                    
                    # Rate limiting
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f" Erro ao enviar mensagem para {target['telegram_user_id']}: {e}")
                    campaign.total_failed += 1
                    db.session.commit()
            
            # Finalizar campanha
            campaign.status = 'completed'
            campaign.completed_at = get_brazil_time()
            db.session.commit()
            logger.info(f" Campanha {campaign_id} concluída com sucesso!")
            
        except Exception as e:
            # AUDIT_CRITICAL - Morte Súbita na Thread!
            logger.error(f"AUDIT_CRITICAL: Morte Súbita na Thread! Erro: {str(e)}\n{traceback.format_exc()}")
            
            # Tentar atualizar status da campanha para failed
            try:
                with app.app_context():
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if campaign:
                        campaign.status = 'failed'
                        campaign.error_message = f"Thread Death: {str(e)}"
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        logger.error(f"AUDIT_CRITICAL: Campanha {campaign_id} marcada como failed")
            except Exception as commit_error:
                logger.error(f"AUDIT_CRITICAL: Falha ao marcar campanha como failed: {commit_error}")
        
        finally:
            # Limpar recursos
            self.worker_threads.pop(thread_id, None)
            self.stop_events.pop(thread_id, None)
            logger.info(f" Worker {thread_id} finalizado e recursos limpos")
            logger.info(f"🧹 Worker {thread_id} finalizado e recursos limpos")
    
    def _get_campaign_targets(self, campaign: RemarketingCampaign, user_id: int) -> List[Dict[str, Any]]:
        """
        Busca usuários alvo baseado na segmentação da campanha
        THREAD SAFE: user_id explícito para evitar current_user em threads
        """
        from internal_logic.core.models import BotUser, Payment
        
        try:
            # LOGS DE AUDITORIA INTERNA - RAIO-X DA QUERY
            logger.info(f"AUDIT: Buscando leads para Bot {campaign.bot_id} do Usuário {user_id}")
            logger.info(f"AUDIT: Segmento: {campaign.target_audience}")
            logger.info(f"AUDIT: Cooldown: {campaign.days_since_last_contact} dias")
            logger.info(f"AUDIT: Excluir compradores: {campaign.exclude_buyers}")
            
            # Base query com filtro de segurança (multitenancy) e usuários não bloqueados
            # ARMADILHA DO NULL: Leads antigos têm archived=NULL, não False
            query = BotUser.query.filter(BotUser.bot_id == campaign.bot_id).filter(
                (BotUser.archived.is_(False)) | (BotUser.archived.is_(None))
            )
            
            # Aplicar filtros de segmentação
            if campaign.target_audience in ['all', 'all_users']:
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
                query = query.filter(BotUser.last_interaction < cutoff_date)
            
            # Filtro de cooldown (último contato)
            if campaign.days_since_last_contact:
                cutoff_date = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                query = query.filter(
                    (BotUser.last_interaction < cutoff_date) | 
                    (BotUser.last_interaction.is_(None))
                )
            
            # Excluir compradores (legado)
            if campaign.exclude_buyers:
                paid_users = Payment.query.filter_by(
                    bot_id=campaign.bot_id, 
                    status='paid'
                ).with_entities(Payment.customer_user_id).distinct().subquery()
                query = query.filter(~BotUser.telegram_user_id.in_(paid_users))
            
            # LOG DE CONTAGEM ANTES DA EXECUÇÃO
            leads_count = query.count()
            logger.info(f"AUDIT: Encontrados {leads_count} leads no banco (antes da execução)")
            
            # Executar query
            users = query.all()
            logger.info(f"AUDIT: Query executada - {len(users)} usuários retornados")
            
            # LOG SQL GERADO (para debug avançado)
            try:
                from sqlalchemy.dialects import postgresql
                compiled_query = query.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
                logger.info(f"AUDIT: SQL Gerado: {compiled_query}")
            except:
                logger.info(f"AUDIT: SQL Query: {str(query)}")
            
            # Converter para dicionários
            targets = []
            for user in users:
                # CORREÇÃO: BotUser não tem campo full_name - usar apenas first_name
                first_name = user.first_name or "Cliente"
                
                targets.append({
                    'telegram_user_id': user.telegram_user_id,
                    'name': user.first_name or "Cliente",
                    'first_name': first_name
                })
            
            logger.info(f"AUDIT: Convertidos {len(targets)} targets para dicionários")
            return targets
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar alvos da campanha {campaign.id}: {e}", exc_info=True)
            raise e  # Erro sobe para o worker em vez de ser engolido
    
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
    
    THREAD SAFE: Para chamadas dentro de threads, user_id é OBRIGATÓRIO
    """
    # Para threads, user_id é OBRIGATÓRIO (current_user não existe em background)
    if user_id is None:
        # Tentar obter da requisição web (fallback apenas para contexto web)
        try:
            from flask_login import current_user
            effective_user_id = current_user.id if current_user else None
        except:
            # Fora de contexto web/Flask - CRÍTICO!
            import logging
            logger = logging.getLogger(__name__)
            logger.error("[SECURITY] get_remarketing_service chamado sem user_id em thread - IMPOSSÍVEL CONTINUAR")
            raise RuntimeError("user_id é obrigatório para chamadas em background threads")
    else:
        effective_user_id = user_id
    
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
