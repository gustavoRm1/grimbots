"""
Remarketing Blueprint - Rotas de Gestão de Campanhas
================================================
Blueprint para gerenciar campanhas de remarketing com
controle de cadência e histórico detalhado.
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from internal_logic.core.extensions import db, csrf
from internal_logic.core.models import (
    Bot, RemarketingCampaign, RemarketingBlacklist, BotUser, Payment
)
from internal_logic.services.remarketing_service import get_remarketing_service
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

# Criar Blueprint
remarketing_bp = Blueprint('remarketing', __name__)


# ============================================================================
# PÁGINAS PRINCIPAIS
# ============================================================================

@remarketing_bp.route('/bots/<int:bot_id>/remarketing')
@login_required
def bot_remarketing_page(bot_id):
    """Página de remarketing do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Buscar campanhas do bot
    campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    
    # Converter para dicionários
    campaigns_list = [c.to_dict() for c in campaigns]
    
    return render_template('bot_remarketing.html', bot=bot, campaigns=campaigns_list)


@remarketing_bp.route('/history')
@login_required
def remarketing_history_page():
    """Página de histórico de todas as campanhas"""
    # Buscar todas as campanhas do usuário (agrupadas por bot)
    campaigns = db.session.query(RemarketingCampaign, Bot).join(
        Bot, RemarketingCampaign.bot_id == Bot.id
    ).filter(
        Bot.user_id == current_user.id
    ).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    
    # Agrupar por bot para exibição
    history_by_bot = {}
    for campaign, bot in campaigns:
        bot_id = bot.id
        
        # Adicionar group_id aos dados da campanha para o template
        campaign_dict = campaign.to_dict()
        if 'group_id' not in campaign_dict:
            campaign_dict['group_id'] = str(campaign.id) if campaign.id else 'N/A'
        
        # Garantir chaves obrigatórias para o template
        # RemarketingCampaign não tem updated_at, usar created_at ou completed_at
        campaign_dict['last_activity'] = campaign.completed_at or campaign.started_at or campaign.created_at
        campaign_dict['status'] = campaign.status or 'unknown'
        campaign_dict['total_sent'] = campaign.total_sent or 0
        campaign_dict['success_count'] = campaign.total_sent or 0  # success_count = total_sent para compatibilidade
        campaign_dict['bot_name'] = bot.name
        campaign_dict['bot_count'] = 1  # Por enquanto, cada campanha representa 1 bot
        
        history_by_bot[bot_id] = campaign_dict  # Usar a campanha mais recente como representante do bot
    
    # Converter para lista para template
    history_list = list(history_by_bot.values())
    
    return render_template('remarketing_history.html', history=history_list)


# ============================================================================
# APIs DE GESTÃO DE CAMPANHAS
# ============================================================================

@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['GET'])
@login_required
def get_remarketing_campaigns(bot_id):
    """Lista campanhas de remarketing de um bot"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
            RemarketingCampaign.created_at.desc()
        ).all()
        
        campaigns_data = [c.to_dict() for c in campaigns]
        
        logger.info(f"📋 Retornando {len(campaigns_data)} campanhas para bot {bot_id}")
        
        return jsonify(campaigns_data)
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar campanhas do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao listar campanhas: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['POST'])
@login_required
@csrf.exempt
def create_remarketing_campaign(bot_id):
    """Cria nova campanha de remarketing"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
        if not bot:
            logger.error(f"[REMARKETING] Bot não encontrado ou sem permissão. BotID recebido: {bot_id}, UserID logado: {current_user.id}")
            return jsonify({"error": "Bot não encontrado ou você não tem permissão", "bot_id": bot_id}), 404
        
        data = request.get_json() or {}
        
        # Processar agendamento
        scheduled_at = None
        status = 'draft'
        
        if data.get('scheduled_at'):
            try:
                scheduled_at_str = data.get('scheduled_at')
                scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                
                # Validar se está no futuro
                if scheduled_at <= datetime.utcnow():
                    return jsonify({'error': 'A data e hora devem ser no futuro'}), 400
                
                status = 'scheduled'
                logger.info(f"📅 Campanha agendada para: {scheduled_at}")
            except Exception as e:
                logger.error(f"❌ Erro ao processar scheduled_at: {e}")
                return jsonify({'error': f'Data/hora inválida: {str(e)}'}), 400
        
        # Criar campanha
        campaign = RemarketingCampaign(
            bot_id=bot_id,
            name=data.get('name'),
            message=data.get('message'),
            media_url=data.get('media_url'),
            media_type=data.get('media_type'),
            audio_enabled=data.get('audio_enabled', False),
            audio_url=data.get('audio_url', ''),
            buttons=data.get('buttons', []),
            target_audience=data.get('target_audience', 'non_buyers'),
            days_since_last_contact=data.get('days_since_last_contact', 3),
            exclude_buyers=data.get('exclude_buyers', True),
            cooldown_hours=data.get('cooldown_hours', 24),
            scheduled_at=scheduled_at,
            status=status,
            group_id=data.get('group_id')  # Para campanhas multi-bot
        )
        
        db.session.add(campaign)
        db.session.commit()
        db.session.refresh(campaign)
        
        logger.info(f"✅ Campanha criada: {campaign.name} (ID: {campaign.id})")
        
        return jsonify(campaign.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar campanha para bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao criar campanha: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_remarketing_campaign(bot_id, campaign_id):
    """Atualiza campanha existente"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
        data = request.get_json() or {}
        
        # Atualizar campos permitidos
        if 'name' in data:
            campaign.name = data['name']
        if 'message' in data:
            campaign.message = data['message']
        if 'media_url' in data:
            campaign.media_url = data['media_url']
        if 'media_type' in data:
            campaign.media_type = data['media_type']
        if 'audio_enabled' in data:
            campaign.audio_enabled = bool(data['audio_enabled'])
        if 'audio_url' in data:
            campaign.audio_url = data['audio_url']
        if 'buttons' in data:
            campaign.buttons = data['buttons']
        if 'target_audience' in data:
            campaign.target_audience = data['target_audience']
        if 'days_since_last_contact' in data:
            campaign.days_since_last_contact = int(data['days_since_last_contact'])
        if 'exclude_buyers' in data:
            campaign.exclude_buyers = bool(data['exclude_buyers'])
        if 'cooldown_hours' in data:
            campaign.cooldown_hours = int(data['cooldown_hours'])
        
        # Processar agendamento
        if 'scheduled_at' in data:
            try:
                scheduled_at_str = data.get('scheduled_at')
                if scheduled_at_str:
                    scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
                    
                    if scheduled_at <= datetime.utcnow():
                        return jsonify({'error': 'A data e hora devem ser no futuro'}), 400
                    
                    campaign.scheduled_at = scheduled_at
                    campaign.status = 'scheduled'
                else:
                    campaign.scheduled_at = None
                    campaign.status = 'draft'
            except Exception as e:
                return jsonify({'error': f'Data/hora inválida: {str(e)}'}), 400
        
        db.session.commit()
        
        logger.info(f"✅ Campanha {campaign_id} atualizada")
        
        return jsonify(campaign.to_dict())
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar campanha {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao atualizar campanha: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_remarketing_campaign(bot_id, campaign_id):
    """Exclui campanha"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
        
        # Verificar se está em andamento
        service = get_remarketing_service()
        status = service.get_campaign_status(campaign_id)
        if status.get('is_running'):
            return jsonify({'error': 'Não é possível excluir campanha em andamento'}), 400
        
        db.session.delete(campaign)
        db.session.commit()
        
        logger.info(f"✅ Campanha {campaign_id} excluída")
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir campanha {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao excluir campanha: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>/send', methods=['POST'])
@login_required
@csrf.exempt
def send_remarketing_campaign(bot_id, campaign_id):
    """Dispara campanha imediatamente"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
        if not bot:
            logger.error(f"[REMARKETING] Bot não encontrado ou sem permissão. BotID recebido: {bot_id}, UserID logado: {current_user.id}")
            return jsonify({"error": "Bot não encontrado ou você não tem permissão", "bot_id": bot_id}), 404

        campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first()
        if not campaign:
            logger.error(f"[REMARKETING] Campanha não encontrada. CampID recebido: {campaign_id}, BotID: {bot_id}")
            return jsonify({"error": "Campanha não encontrada no banco", "campaign_id": campaign_id}), 404
        
        # Verificar se já está em andamento
        if campaign.status == 'sending':
            return jsonify({'error': 'Campanha já está em andamento'}), 400
        
        # Iniciar envio assíncrono
        service = get_remarketing_service()
        service.send_campaign_async(campaign_id, current_user.id)
        
        logger.info(f"🚀 Campanha {campaign_id} disparada para bot {bot_id}")
        
        return jsonify({
            'success': True,
            'message': 'Campanha iniciada com sucesso',
            'campaign_id': campaign_id
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao disparar campanha {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao disparar campanha: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
@csrf.exempt
def stop_remarketing_campaign(bot_id, campaign_id):
    """Para campanha em andamento"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
        
        service = get_remarketing_service()
        success = service.stop_campaign(campaign_id)
        
        if success:
            logger.info(f"⏹️ Campanha {campaign_id} parada com sucesso")
            return jsonify({'success': True, 'message': 'Campanha parada'})
        else:
            return jsonify({'error': 'Campanha não está em andamento'}), 400
        
    except Exception as e:
        logger.error(f"❌ Erro ao parar campanha {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao parar campanha: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>/status', methods=['GET'])
@login_required
def get_campaign_status(bot_id, campaign_id):
    """Retorna status detalhado da campanha"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
        
        service = get_remarketing_service()
        status_data = service.get_campaign_status(campaign_id)
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter status da campanha {campaign_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao obter status: {str(e)}'}), 500


# ============================================================================
# APIs DE BLACKLIST
# ============================================================================

@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/blacklist', methods=['GET'])
@login_required
def get_remarketing_blacklist(bot_id):
    """Lista usuários na blacklist"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        blacklist = RemarketingBlacklist.query.filter_by(bot_id=bot_id).order_by(
            RemarketingBlacklist.created_at.desc()
        ).all()
        
        blacklist_data = []
        for entry in blacklist:
            # Buscar nome do usuário
            user = BotUser.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=entry.telegram_user_id
            ).first()
            
            blacklist_data.append({
                'id': entry.id,
                'telegram_user_id': entry.telegram_user_id,
                'name': user.full_name if user else 'Desconhecido',
                'reason': entry.reason,
                'created_at': entry.created_at.isoformat() if entry.created_at else None
            })
        
        return jsonify(blacklist_data)
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar blacklist do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao listar blacklist: {str(e)}'}), 500


@remarketing_bp.route('/api/bots/<int:bot_id>/remarketing/blacklist/<int:entry_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def remove_from_blacklist(bot_id, entry_id):
    """Remove usuário da blacklist"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        entry = RemarketingBlacklist.query.filter_by(id=entry_id, bot_id=bot_id).first_or_404()
        
        db.session.delete(entry)
        db.session.commit()
        
        logger.info(f"✅ Usuário {entry.telegram_user_id} removido da blacklist do bot {bot_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao remover da blacklist: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao remover da blacklist: {str(e)}'}), 500


# ============================================================================
# REMARKETING MULTI-BOT (GERAL)
# ============================================================================

@remarketing_bp.route('/api/general', methods=['POST'])
@login_required
@csrf.exempt
def create_general_remarketing():
    """Cria campanhas de remarketing em massa para múltiplos bots"""
    try:
        data = request.get_json() or {}
        bot_ids = data.get('bot_ids', [])
        
        if not bot_ids:
            return jsonify({'error': 'Nenhum bot selecionado'}), 400
        
        # Dados da campanha (mesmos para todos os bots)
        campaign_data = {
            'name': data.get('name', 'Campanha Geral'),
            'message': data.get('message'),
            'media_url': data.get('media_url'),
            'media_type': data.get('media_type'),
            'audio_enabled': data.get('audio_enabled', False),
            'audio_url': data.get('audio_url', ''),
            'buttons': json.dumps(data.get('buttons', [])),  # Serializar para string JSON
            'target_audience': data.get('audience_segment', 'all_users'),
            'days_since_last_contact': data.get('days_since_last_contact', 0),
            'exclude_buyers': data.get('exclude_buyers', False),
            'cooldown_hours': data.get('cooldown_hours', 24),
            'status': 'sending',  # Mudar para 'sending' para iniciar imediatamente
            'group_id': data.get('group_id')  # Para identificar campanhas multi-bot
        }
        
        created_campaigns = []
        errors = []
        
        # Criar campanha para cada bot
        for bot_id in bot_ids:
            try:
                # Validar se bot pertence ao usuário
                bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
                if not bot:
                    errors.append(f"Bot {bot_id} não encontrado ou sem permissão")
                    continue
                
                # Criar campanha individual
                campaign = RemarketingCampaign(
                    bot_id=bot_id,
                    **campaign_data
                )
                
                db.session.add(campaign)
                created_campaigns.append({
                    'bot_id': bot_id,
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name
                })
                
                logger.info(f"✅ Campanha geral criada: {campaign.name} (ID: {campaign.id}) para bot {bot_id}")
                
            except Exception as e:
                errors.append(f"Erro ao criar campanha para bot {bot_id}: {str(e)}")
                logger.error(f"❌ Erro ao criar campanha geral para bot {bot_id}: {e}", exc_info=True)
        
        # Commit apenas se todas as campanhas foram criadas sem erros
        if created_campaigns and not errors:
            db.session.commit()
            
            # Disparar campanhas criadas SEMPRE (não verificar scheduled_at)
            service = get_remarketing_service()
            for campaign_info in created_campaigns:
                try:
                    service.send_campaign_async(campaign_info['campaign_id'], current_user.id)
                    logger.info(f" Campanha geral {campaign_info['campaign_id']} disparada para bot {campaign_info['bot_id']}")
                except Exception as e:
                    logger.error(f" Erro ao disparar campanha {campaign_info['campaign_id']}: {e}")
            
            return jsonify({
                'success': True,
                'status': 'success',  # Adicionar compatibilidade com frontend
                'message': 'Campanhas criadas e em processamento',
                'campaigns': created_campaigns,
                'errors': errors
            })
        
        elif created_campaigns:
            # Commit parcial (algumas criadas, outras com erro)
            db.session.commit()
            return jsonify({
                'success': False,
                'status': 'partial_error',  # Adicionar compatibilidade com frontend
                'message': 'Algumas campanhas criadas com erros',
                'campaigns': created_campaigns,
                'errors': errors
            }), 400
        
        else:
            # Nenhuma campanha criada
            db.session.rollback()
            return jsonify({
                'success': False,
                'status': 'error',  # Adicionar compatibilidade com frontend
                'message': 'Nenhuma campanha foi criada',
                'campaigns': [],
                'errors': errors
            }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar campanha geral: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'status': 'error',  # Adicionar compatibilidade com frontend
            'error': f'Erro ao criar campanha geral: {str(e)}'
        }), 500
