# ============================================================================
# LEGACY REMARKETING LOGIC - EXTRAÇÃO DO SISTEMA DE RECUPERAÇÃO DE VENDAS
# Arquivo: _legacy_exports/legacy_remarketing_logic.py
# Origem: app.py, app_legacy.py, botmanager.py
# ============================================================================
# Este arquivo contém a "assinatura" exata do motor de remarketing:
# - Models: RemarketingCampaign, RemarketingBlacklist
# - Rotas: Listagem, Criação, Atualização, Histórico
# - BotManager: Envio de campanhas em background
# - Worker: Processamento assíncrono via Redis
# NÃO MODIFICAR - Apenas para referência durante migração
# ============================================================================


# ============================================================================
# ALVO 1: MODELS DO SISTEMA DE REMARKETING
# ============================================================================

# ----------------------------------------------------------------------------
# MODEL: RemarketingCampaign
# Origem: app.py (models legado)
# ----------------------------------------------------------------------------
"""
class RemarketingCampaign(db.Model):
    __tablename__ = 'remarketing_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Identificação
    name = db.Column(db.String(255), nullable=False)
    
    # Conteúdo da mensagem
    message = db.Column(db.Text)  # Texto da mensagem (com placeholders {nome}, {primeiro_nome})
    media_url = db.Column(db.String(500))  # URL de imagem/video
    media_type = db.Column(db.String(20))  # 'image', 'video', 'audio'
    
    # Áudio adicional
    audio_enabled = db.Column(db.Boolean, default=False)
    audio_url = db.Column(db.String(500))
    
    # Botões (JSON array)
    buttons = db.Column(db.Text)  # [{"text": "Comprar", "price": 97.0, "description": "..."}]
    
    # Segmentação (target_audience v2.0)
    target_audience = db.Column(db.String(50), default='non_buyers')
    # Valores possíveis:
    # - 'all': Todos os usuários
    # - 'buyers': Quem comprou (status='paid')
    # - 'downsell_buyers': Quem comprou downsell
    # - 'order_bump_buyers': Quem aceitou order bump
    # - 'upsell_buyers': Quem comprou upsell
    # - 'remarketing_buyers': Quem comprou via remarketing
    # - 'abandoned_cart': Carrinho abandonado (status='pending')
    # - 'inactive': Inativos há 7+ dias
    # - 'non_buyers': Nunca compraram (legado - usa exclude_buyers)
    
    # Filtros adicionais (legado)
    days_since_last_contact = db.Column(db.Integer, default=3)
    exclude_buyers = db.Column(db.Boolean, default=True)  # Legado - excluir compradores
    cooldown_hours = db.Column(db.Integer, default=24)
    
    # Agendamento
    scheduled_at = db.Column(db.DateTime)  # Quando agendado para enviar
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, sending, completed, failed, paused
    
    # Contadores
    total_targets = db.Column(db.Integer, default=0)  # Total de leads elegíveis
    total_sent = db.Column(db.Integer, default=0)   # Enviados com sucesso
    total_failed = db.Column(db.Integer, default=0)  # Falhas
    total_blocked = db.Column(db.Integer, default=0) # Bloqueados (usuário bloqueou bot)
    
    # Timestamps de execução
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Multi-bot (campanhas em grupo)
    group_id = db.Column(db.String(50), index=True)  # UUID para agrupar campanhas multi-bot
    
    # Metadados
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    bot = db.relationship('Bot', backref='remarketing_campaigns')
    
    def to_dict(self):
        return {
            'id': self.id,
            'bot_id': self.bot_id,
            'name': self.name,
            'message': self.message or '',
            'media_url': self.media_url or '',
            'media_type': self.media_type or '',
            'audio_enabled': self.audio_enabled or False,
            'audio_url': self.audio_url or '',
            'buttons': self.get_buttons() or [],
            'target_audience': self.target_audience or 'non_buyers',
            'days_since_last_contact': self.days_since_last_contact or 3,
            'exclude_buyers': self.exclude_buyers or False,
            'cooldown_hours': self.cooldown_hours or 24,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'status': self.status or 'draft',
            'total_targets': self.total_targets or 0,
            'total_sent': self.total_sent or 0,
            'total_failed': self.total_failed or 0,
            'total_blocked': self.total_blocked or 0,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'group_id': self.group_id or None,
            'error_message': self.error_message or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def get_buttons(self):
        if not self.buttons:
            return []
        try:
            import json
            return json.loads(self.buttons) if isinstance(self.buttons, str) else self.buttons
        except:
            return []
    
    def set_buttons(self, buttons):
        import json
        if buttons is None:
            self.buttons = None
        else:
            self.buttons = json.dumps(buttons) if not isinstance(buttons, str) else buttons


# ----------------------------------------------------------------------------
# MODEL: RemarketingBlacklist
# Origem: botmanager.py e app.py
# ----------------------------------------------------------------------------
"""
class RemarketingBlacklist(db.Model):
    __tablename__ = 'remarketing_blacklist'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    telegram_user_id = db.Column(db.String(50), nullable=False, index=True)
    reason = db.Column(db.String(50), default='bot_blocked')  # 'bot_blocked', 'opt_out', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: um usuário só pode estar na blacklist uma vez por bot
    __table_args__ = (
        db.UniqueConstraint('bot_id', 'telegram_user_id', name='uq_blacklist_bot_user'),
    )
"""


# ============================================================================
# ALVO 2: ROTAS DE GESTÃO DE CAMPANHAS
# ============================================================================

# ----------------------------------------------------------------------------
# ROTA: Página de Remarketing do Bot
# Origem: app_legacy.py - Linhas 3479-3492
# ----------------------------------------------------------------------------
"""
@app.route('/bots/<int:bot_id>/remarketing')
@login_required
def bot_remarketing_page(bot_id):
    # Página de remarketing do bot
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    
    # Converter para dicionários (serializável)
    campaigns_list = [c.to_dict() for c in campaigns]
    
    return render_template('bot_remarketing.html', bot=bot, campaigns=campaigns_list)
"""

# ----------------------------------------------------------------------------
# API: Listar Campanhas
# Origem: app_legacy.py - Linhas 3494-3515
# ----------------------------------------------------------------------------
"""
@app.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['GET'])
@login_required
def get_remarketing_campaigns(bot_id):
    # Lista campanhas de remarketing
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    import json
    import hashlib
    campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    
    # LOG: Verificar botões antes de retornar
    campaigns_dicts = []
    for c in campaigns:
        campaign_dict = c.to_dict()
        logger.info(f"📤 Retornando campanha {c.id} ({c.name}): buttons = {campaign_dict.get('buttons')}")
        campaigns_dicts.append(campaign_dict)
    
    return jsonify(campaigns_dicts)
"""

# ----------------------------------------------------------------------------
# API: Criar Campanha
# Origem: app_legacy.py - Linhas 3519-3592
# ----------------------------------------------------------------------------
"""
@app.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['POST'])
@login_required
@csrf.exempt
def create_remarketing_campaign(bot_id):
    # V2.0: Cria nova campanha de remarketing com suporte a agendamento
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.json
    from models import RemarketingCampaign
    from datetime import datetime
    
    # V2.0: Processar scheduled_at se fornecido
    scheduled_at = None
    status = 'draft'  # Padrão: rascunho
    
    if data.get('scheduled_at'):
        try:
            # Converter string ISO para datetime
            scheduled_at_str = data.get('scheduled_at')
            scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            
            # Validar se data está no futuro
            now = get_brazil_time()
            if scheduled_at <= now:
                return jsonify({'error': 'A data e hora devem ser no futuro'}), 400
            
            # Se agendado, status será 'scheduled'
            status = 'scheduled'
            logger.info(f"📅 Campanha agendada para: {scheduled_at}")
        except Exception as e:
            logger.error(f"❌ Erro ao processar scheduled_at: {e}")
            return jsonify({'error': f'Data/hora inválida: {str(e)}'}), 400
    
    # LOG: Verificar botões antes de salvar
    buttons_data = data.get('buttons', [])
    logger.info(f"📝 Criando campanha: {data.get('name', 'Sem nome')}")
    logger.info(f"📋 Botões recebidos: {len(buttons_data) if isinstance(buttons_data, list) else 'N/A'}")
    
    campaign = RemarketingCampaign(
        bot_id=bot_id,
        name=data.get('name'),
        message=data.get('message'),
        media_url=data.get('media_url'),
        media_type=data.get('media_type'),
        audio_enabled=data.get('audio_enabled', False),
        audio_url=data.get('audio_url', ''),
        buttons=buttons_data if buttons_data else None,  # Salvar como None se vazio
        target_audience=data.get('target_audience', 'non_buyers'),
        days_since_last_contact=data.get('days_since_last_contact', 3),
        exclude_buyers=data.get('exclude_buyers', True),
        cooldown_hours=data.get('cooldown_hours', 24),
        scheduled_at=scheduled_at,  # V2.0
        status=status  # V2.0: 'draft' ou 'scheduled'
    )
    
    db.session.add(campaign)
    db.session.commit()
    db.session.refresh(campaign)
    
    return jsonify(campaign.to_dict()), 201
"""

# ----------------------------------------------------------------------------
# API: Atualizar Campanha
# Origem: app_legacy.py - Linhas 3594-3690
# ----------------------------------------------------------------------------
"""
@app.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_remarketing_campaign(bot_id, campaign_id):
    # Atualiza campanha de remarketing existente
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    from datetime import datetime
    
    campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
    data = request.json
    
    # Atualizar campos básicos
    if 'name' in data:
        campaign.name = data['name']
    if 'message' in data:
        campaign.message = data['message']
    if 'media_url' in data:
        campaign.media_url = data['media_url']
    if 'media_type' in data:
        campaign.media_type = data['media_type']
    if 'audio_enabled' in data:
        campaign.audio_enabled = data['audio_enabled']
    if 'audio_url' in data:
        campaign.audio_url = data['audio_url']
    if 'buttons' in data:
        campaign.set_buttons(data['buttons'])
    if 'target_audience' in data:
        campaign.target_audience = data['target_audience']
    if 'days_since_last_contact' in data:
        campaign.days_since_last_contact = data['days_since_last_contact']
    if 'exclude_buyers' in data:
        campaign.exclude_buyers = data['exclude_buyers']
    if 'cooldown_hours' in data:
        campaign.cooldown_hours = data['cooldown_hours']
    
    # Atualizar agendamento
    if 'scheduled_at' in data:
        if data['scheduled_at']:
            try:
                scheduled_at = datetime.fromisoformat(data['scheduled_at'].replace('Z', '+00:00'))
                now = get_brazil_time()
                if scheduled_at <= now:
                    return jsonify({'error': 'A data deve ser no futuro'}), 400
                campaign.scheduled_at = scheduled_at
                campaign.status = 'scheduled'
            except Exception as e:
                return jsonify({'error': f'Data inválida: {str(e)}'}), 400
        else:
            campaign.scheduled_at = None
            campaign.status = 'draft'
    
    db.session.commit()
    return jsonify(campaign.to_dict())
"""


# ============================================================================
# ALVO 3: ROTA DE HISTÓRICO
# ============================================================================

# ----------------------------------------------------------------------------
# ROTA: Histórico de Remarketing Multi-Bot
# Origem: app_legacy.py - Linhas 5953-5989
# ----------------------------------------------------------------------------
"""
@app.route('/remarketing/history')
@login_required
def remarketing_history():
    # View: Histórico de Remarketing Multi-Bot (Agrupado por group_id)
    # Lista todas as campanhas multi-bot do usuário, agrupadas por group_id
    try:
        from sqlalchemy import func, desc
        from models import RemarketingCampaign, Bot
        
        # Query de agrupamento: group_id, data mais recente, quantidade de bots, total enviado
        history = db.session.query(
            RemarketingCampaign.group_id,
            func.max(RemarketingCampaign.created_at).label('last_activity'),
            func.count(RemarketingCampaign.id).label('bot_count'),
            func.sum(RemarketingCampaign.total_sent).label('total_sent'),
            func.sum(RemarketingCampaign.total_targets).label('total_targets')
        ).join(
            Bot, RemarketingCampaign.bot_id == Bot.id
        ).filter(
            Bot.user_id == current_user.id,
            RemarketingCampaign.group_id.isnot(None)
        ).group_by(
            RemarketingCampaign.group_id
        ).order_by(
            desc('last_activity')
        ).all()
        
        logger.info(f"📊 [HISTORY] Usuário {current_user.id} consultou histórico: {len(history)} grupos encontrados")
        
        return render_template('remarketing_history.html', history=history)
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar histórico de remarketing: {e}", exc_info=True)
        flash('Erro ao carregar histórico de campanhas.', 'error')
        return render_template('remarketing_history.html', history=[])
"""

# ----------------------------------------------------------------------------
# API: Disparar Campanha (Iniciar Envio)
# Origem: app.py - API para iniciar envio de campanha
# ----------------------------------------------------------------------------
"""
@app.route('/api/remarketing/campaigns/<int:campaign_id>/send', methods=['POST'])
@login_required
@csrf.exempt
def send_remarketing_campaign_api(campaign_id):
    # Dispara o envio de uma campanha de remarketing
    from models import RemarketingCampaign, Bot
    
    campaign = RemarketingCampaign.query.get_or_404(campaign_id)
    bot = Bot.query.filter_by(id=campaign.bot_id, user_id=current_user.id).first_or_404()
    
    # Verificar se já está enviando
    if campaign.status == 'sending':
        return jsonify({'error': 'Campanha já está em andamento'}), 400
    
    # Verificar se já foi concluída
    if campaign.status == 'completed':
        return jsonify({'error': 'Campanha já foi concluída'}), 400
    
    # Iniciar envio via BotManager
    from botmanager import BotManager
    bot_manager = BotManager(socketio=None, user_id=current_user.id)
    
    # Disparar em background (thread)
    import threading
    thread = threading.Thread(
        target=bot_manager.send_remarketing_campaign,
        args=(campaign.id, bot.token),
        name=f"remarketing-{campaign.id}"
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Campanha iniciada',
        'campaign_id': campaign.id,
        'status': 'sending'
    })
"""


# ============================================================================
# ALVO 4: BOTMANAGER - ENVIO DE CAMPANHAS
# ============================================================================

# ----------------------------------------------------------------------------
# BotManager.send_remarketing_campaign
# Origem: botmanager.py - Linhas 10843-11830
# ----------------------------------------------------------------------------
"""
def send_remarketing_campaign(self, campaign_id: int, bot_token: str):
    # Envia campanha de remarketing em background
    
    try:
        from redis_manager import get_redis_connection
        import json
        from app import app, db, socketio
        from internal_logic.core.models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist, get_brazil_time, Bot
        from datetime import timedelta
        
        # ============================================================
        # MODO NOVO: Queue-based com Redis
        # ============================================================
        def enqueue_jobs():
            with app.app_context():
                campaign = db.session.get(RemarketingCampaign, campaign_id)
                if not campaign:
                    logger.warning(f"❌ Remarketing abortado: campaign_id={campaign_id} não encontrada")
                    return
                
                campaign.status = 'sending'
                campaign.started_at = get_brazil_time()
                db.session.commit()
                
                redis_conn = get_redis_connection()
                queue_key = f"gb:{self.user_id}:remarketing:queue:{campaign.bot_id}"
                sent_set_key = f"remarketing:sent:{campaign.id}"
                stats_key = f"remarketing:stats:{campaign.id}"
                
                # Query base de leads
                contact_limit = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)
                if campaign.days_since_last_contact > 0:
                    query = query.filter(BotUser.last_interaction <= contact_limit)
                
                # Excluir blacklist
                blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                    bot_id=campaign.bot_id
                ).all()
                blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                if blacklist_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                
                # Aplicar segmentação (target_audience)
                target_audience = campaign.target_audience
                
                if target_audience == 'all':
                    pass  # Todos
                elif target_audience == 'buyers':
                    buyer_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'paid'
                    ).distinct().all()
                    buyer_ids = [b[0] for b in buyer_ids if b[0]]
                    if buyer_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                elif target_audience == 'downsell_buyers':
                    downsell_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'paid',
                        Payment.is_downsell == True
                    ).distinct().all()
                    # ... similar para outros segmentos
                elif target_audience == 'non_buyers':
                    buyer_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'paid'
                    ).distinct().all()
                    buyer_ids = [b[0] for b in buyer_ids if b[0]]
                    if buyer_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                
                total_leads = query.count()
                if total_leads == 0:
                    campaign.total_targets = 0
                    campaign.status = 'completed'
                    campaign.completed_at = get_brazil_time()
                    db.session.commit()
                    return
                
                # Processar em batches
                batch_size = 200
                offset = 0
                enqueued = 0
                
                while offset < total_leads:
                    batch = query.offset(offset).limit(batch_size).all()
                    if not batch:
                        break
                    
                    for lead in batch:
                        # Validações de elegibilidade
                        if not getattr(lead, 'telegram_user_id', None):
                            continue
                        
                        # Verificar blacklist Redis
                        blk_key = f"remarketing:blacklist:{campaign.bot_id}"
                        if redis_conn.sismember(blk_key, str(lead.telegram_user_id)):
                            continue
                        
                        # Verificar se já recebeu
                        if redis_conn.sismember(sent_set_key, str(lead.telegram_user_id)):
                            continue
                        
                        # Verificar opt_out/unsubscribed/inactive
                        if getattr(lead, 'opt_out', False) or getattr(lead, 'unsubscribed', False):
                            continue
                        
                        # Personalizar mensagem com placeholders
                        message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                        message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])
                        
                        # Preparar botões
                        remarketing_buttons = []
                        if campaign.buttons:
                            buttons_list = campaign.buttons
                            if isinstance(campaign.buttons, str):
                                try:
                                    buttons_list = json.loads(campaign.buttons)
                                except:
                                    buttons_list = []
                            for btn_idx, btn in enumerate(buttons_list):
                                if btn.get('price') and btn.get('description'):
                                    remarketing_buttons.append({
                                        'text': btn.get('text', 'Comprar'),
                                        'callback_data': f"rmkt_{campaign.id}_{btn_idx}"  # < 20 bytes
                                    })
                                elif btn.get('url'):
                                    remarketing_buttons.append({
                                        'text': btn.get('text', 'Link'),
                                        'url': btn.get('url')
                                    })
                        
                        # Criar job
                        job = {
                            'type': 'send',
                            'campaign_id': campaign.id,
                            'bot_id': campaign.bot_id,
                            'telegram_user_id': str(lead.telegram_user_id),
                            'message': message,
                            'media_url': campaign.media_url,
                            'media_type': campaign.media_type,
                            'buttons': remarketing_buttons,
                            'audio_enabled': bool(campaign.audio_enabled),
                            'audio_url': campaign.audio_url or '',
                            'bot_token': bot_token
                        }
                        
                        # Enfileirar no Redis
                        redis_conn.rpush(queue_key, json.dumps(job))
                        redis_conn.hincrby(stats_key, 'enqueued', 1)
                        enqueued += 1
                    
                    offset += batch_size
                
                # Atualizar total
                campaign.total_targets = enqueued
                db.session.commit()
                
                # Emitir evento inicial
                try:
                    socketio.emit('remarketing_progress', {
                        'campaign_id': campaign.id,
                        'sent': 0,
                        'failed': 0,
                        'blocked': 0,
                        'total': enqueued,
                        'percentage': 0
                    })
                except:
                    pass
                
                # Sinal de conclusão
                redis_conn.rpush(queue_key, json.dumps({'type': 'campaign_done', 'campaign_id': campaign.id}))
                
                logger.info(f"📦 Remarketing jobs enfileirados: campaign_id={campaign.id} total={enqueued}")
        
        # Iniciar thread de enfileiramento
        thread = threading.Thread(target=enqueue_jobs, name=f"remarketing-enqueue-{campaign_id}")
        thread.daemon = True
        thread.start()
        logger.info(f"🚀 Remarketing enqueue thread disparada: campaign_id={campaign_id}")
        return
        
    except Exception as orchestration_error:
        logger.error(f"❌ Falha no remarketing orchestration: {orchestration_error}", exc_info=True)
        # Fallback para modo legado (código omitido para brevidade)
"""


# ============================================================================
# ALVO 5: WORKER THREAD - PROCESSAMENTO DA FILA
# ============================================================================

# ----------------------------------------------------------------------------
# Worker de Remarketing (dentro do BotManager)
# Origem: botmanager.py - Linhas 643-813
# ----------------------------------------------------------------------------
"""
def _remarketing_worker(self, bot_id: int, queue_key: str, stop_event: threading.Event):
    # Worker thread que processa a fila de remarketing
    
    import time
    import random
    import json
    from redis_manager import get_redis_connection
    
    logger.info(f"🚀 Remarketing worker iniciado: bot_id={bot_id} queue={queue_key}")
    
    msg_counter = 0
    while not stop_event.is_set():
        try:
            redis_conn = get_redis_connection()
            item = redis_conn.blpop(queue_key, timeout=5)
            if not item:
                continue
            
            _, raw = item
            try:
                job = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
            except Exception:
                logger.warning(f"⚠️ Remarketing job inválido: bot_id={bot_id}")
                continue
            
            job_type = job.get('type')
            
            # Sinal de campanha concluída
            if job_type == 'campaign_done':
                campaign_id = job.get('campaign_id')
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db, socketio
                    from internal_logic.core.models import RemarketingCampaign, get_brazil_time
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, int(campaign_id))
                        if campaign:
                            db.session.refresh(campaign)
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            
                            socketio.emit('remarketing_completed', {
                                'campaign_id': campaign.id,
                                'total_sent': campaign.total_sent,
                                'total_failed': campaign.total_failed,
                                'total_blocked': campaign.total_blocked
                            })
                            logger.info(f"✅ Remarketing campaign finalizada: campaign_id={campaign.id}")
                except Exception as e:
                    logger.error(f"❌ Erro ao finalizar campanha: {e}")
                continue
            
            # Job de envio normal
            campaign_id = job.get('campaign_id')
            chat_id = job.get('telegram_user_id')
            message = job.get('message')
            media_url = job.get('media_url')
            media_type = job.get('media_type')
            buttons = job.get('buttons')
            audio_enabled = bool(job.get('audio_enabled'))
            audio_url = job.get('audio_url')
            
            token = self._get_remarketing_worker_token(bot_id)
            if not token:
                token = job.get('bot_token')
            
            if not token:
                logger.error(f"❌ Remarketing worker sem token: bot_id={bot_id}")
                continue
            
            # Enviar mensagem
            send_result = None
            try:
                send_result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons
                )
            except Exception as send_error:
                logger.error(f"❌ ERRO AO ENVIAR REMARKETING: {send_error}")
                send_result = {'error': True, 'error_code': -1, 'description': str(send_error)}
            
            # Processar resultado
            sent_inc = 0
            failed_inc = 0
            blocked_inc = 0
            
            if isinstance(send_result, dict) and send_result.get('error'):
                error_code = int(send_result.get('error_code') or 0)
                desc = (send_result.get('description') or '').lower()
                
                if error_code == 403 and ('bot was blocked' in desc):
                    blocked_inc = 1
                    # Adicionar à blacklist
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import RemarketingBlacklist
                        with current_app.app_context():
                            existing = db.session.query(RemarketingBlacklist).filter_by(
                                bot_id=bot_id,
                                telegram_user_id=str(chat_id)
                            ).first()
                            if not existing:
                                db.session.add(RemarketingBlacklist(
                                    bot_id=bot_id, 
                                    telegram_user_id=str(chat_id), 
                                    reason='bot_blocked'
                                ))
                                db.session.commit()
                    except:
                        pass
                else:
                    failed_inc = 1
            elif send_result:
                sent_inc = 1
                # Enviar áudio adicional se habilitado
                if audio_enabled and audio_url:
                    try:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="",
                            media_url=audio_url,
                            media_type='audio',
                            buttons=None
                        )
                    except:
                        pass
            else:
                failed_inc = 1
            
            # Atualizar contadores da campanha
            try:
                if campaign_id:
                    from flask import current_app
                    from internal_logic.core.extensions import db, socketio
                    from internal_logic.core.models import RemarketingCampaign
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, int(campaign_id))
                        if campaign:
                            db.session.refresh(campaign)
                            campaign.total_sent += sent_inc
                            campaign.total_failed += failed_inc
                            campaign.total_blocked += blocked_inc
                            db.session.commit()
                            
                            socketio.emit('remarketing_progress', {
                                'campaign_id': campaign.id,
                                'sent': campaign.total_sent,
                                'failed': campaign.total_failed,
                                'blocked': campaign.total_blocked,
                                'total': campaign.total_targets,
                                'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                            })
            except Exception as update_error:
                logger.debug(f"⚠️ Falha ao atualizar contadores: {update_error}")
            
            # Rate limiting
            msg_counter += 1
            time.sleep(random.uniform(1.2, 2.5))  # 1.2-2.5s entre mensagens
            
            # Pausa a cada 100 mensagens
            if msg_counter % 100 == 0:
                logger.info(f"⏸️ Micro pause remarketing bot_id={bot_id} msgs={msg_counter}")
                time.sleep(random.uniform(10, 20))
                
        except Exception as e:
            logger.error(f"❌ Erro no remarketing worker: bot_id={bot_id} err={e}")
            try:
                time.sleep(5)
            except:
                pass
"""


# ============================================================================
# ALVO 6: PLACEHOLDERS E TEMPLATE DE MENSAGEM
# ============================================================================

"""
PLACEHOLDERS SUPORTADOS NA MENSAGEM DE REMARKETING:

{nome}           -> lead.first_name ou 'Cliente'
{primeiro_nome}  -> (lead.first_name ou 'Cliente').split()[0]

Exemplo de uso:
message = "Olá {nome}! Vi que você ainda não finalizou sua compra..."
Resultado: "Olá João Silva! Vi que você ainda não finalizou..."

message = "Oi {primeiro_nome}, temos uma oferta especial!"
Resultado: "Oi João, temos uma oferta especial!"


FORMATO DOS BOTÕES:
[
    {
        "text": "Comprar Agora",
        "price": 97.00,
        "description": "Acesso vitalício ao curso"
    },
    {
        "text": "Saiba Mais",
        "url": "https://exemplo.com/info"
    }
]

Quando converte para Telegram:
- Botão com price -> callback_data: "rmkt_{campaign_id}_{btn_index}"
- Botão com url -> url: "https://..."
"""


# ============================================================================
# ALVO 7: KEYS DO REDIS
# ============================================================================

"""
REDIS KEYS UTILIZADAS:

1. Fila de jobs: "gb:{user_id}:remarketing:queue:{bot_id}"
   - Lista (LPUSH/RPOP) de jobs JSON
   
2. Set de enviados: "remarketing:sent:{campaign_id}"
   - Set de telegram_user_id já enviados (evita duplicação)
   
3. Stats: "remarketing:stats:{campaign_id}"
   - Hash com contadores: enqueued, skipped_blacklist, etc.
   
4. Blacklist cache: "remarketing:blacklist:{bot_id}"
   - Set de telegram_user_id bloqueados (performance)
"""


# ============================================================================
# RESUMO DA ARQUITETURA
# ============================================================================

"""
FLUXO DE UMA CAMPANHA DE REMARKETING:

1. CRIAÇÃO (API POST /api/bots/{bot_id}/remarketing/campaigns)
   - Usuário cria campanha com mensagem, segmentação, agendamento opcional
   - Status inicial: 'draft' ou 'scheduled'

2. AGENDAMENTO
   - Se scheduled_at fornecido: campanha fica com status='scheduled'
   - Scheduler periodicamente verifica campanhas agendadas e inicia quando chega a hora

3. DISPARO (API POST /api/remarketing/campaigns/{id}/send)
   - Cria thread de enfileiramento (enqueue_jobs)
   - Thread consulta leads elegíveis baseado na segmentação
   - Enfileira jobs no Redis (gb:{user_id}:remarketing:queue:{bot_id})
   - Atualiza status para 'sending'

4. PROCESSAMENTO (Worker Thread)
   - Worker separado por bot lê da fila Redis (blpop)
   - Envia mensagens via Telegram API
   - Atualiza contadores no banco (total_sent, total_failed, total_blocked)
   - Adiciona à blacklist se usuário bloqueou bot (erro 403)
   - Emite progresso via WebSocket (socketio.emit)

5. FINALIZAÇÃO
   - Job 'campaign_done' sinaliza fim
   - Worker atualiza status para 'completed'
   - Emite evento 'remarketing_completed' via WebSocket


SEGMENTAÇÃO (target_audience):
- 'all': Todos os usuários do bot
- 'buyers': Quem tem payment status='paid'
- 'downsell_buyers': Quem tem is_downsell=True
- 'order_bump_buyers': Quem tem order_bump_accepted=True
- 'upsell_buyers': Quem tem is_upsell=True
- 'remarketing_buyers': Quem tem is_remarketing=True
- 'abandoned_cart': Quem tem payment status='pending'
- 'inactive': last_interaction há 7+ dias
- 'non_buyers': Exclui quem tem payment status='paid'


ESTRUTURA DO JOB NO REDIS:
{
    "type": "send",
    "campaign_id": 123,
    "bot_id": 456,
    "telegram_user_id": "789012345",
    "message": "Olá João! Temos uma oferta...",
    "media_url": "https://...",
    "media_type": "image",
    "buttons": [
        {"text": "Comprar", "callback_data": "rmkt_123_0"}
    ],
    "audio_enabled": false,
    "audio_url": "",
    "bot_token": "123456:ABC..."
}
"""


# ============================================================================
# CHECKLIST DE REIMPLEMENTAÇÃO
# ============================================================================

"""
✅ MODELS:
   [ ] RemarketingCampaign com todas as colunas
   [ ] RemarketingBlacklist para usuários que bloquearam
   [ ] Relacionamento Bot -> RemarketingCampaign
   [ ] Métodos to_dict(), get_buttons(), set_buttons()

✅ ROTAS API:
   [ ] GET /api/bots/{bot_id}/remarketing/campaigns (listar)
   [ ] POST /api/bots/{bot_id}/remarketing/campaigns (criar)
   [ ] PUT /api/bots/{bot_id}/remarketing/campaigns/{id} (atualizar)
   [ ] POST /api/remarketing/campaigns/{id}/send (disparar)
   [ ] GET /remarketing/history (página de histórico)

✅ BOTMANAGER:
   [ ] send_remarketing_campaign() - enfileiramento
   [ ] _remarketing_worker() - processamento da fila
   [ ] send_telegram_message() - já existe, reutilizar

✅ REDIS:
   [ ] get_redis_connection() - já existe
   [ ] Queue keys: "gb:{user_id}:remarketing:queue:{bot_id}"
   [ ] Sent set: "remarketing:sent:{campaign_id}"
   [ ] Blacklist cache: "remarketing:blacklist:{bot_id}"

✅ WEBSOCKET:
   [ ] socketio.emit('remarketing_progress', {...})
   [ ] socketio.emit('remarketing_completed', {...})

✅ PLACEHOLDERS:
   [ ] {nome} -> lead.first_name
   [ ] {primeiro_nome} -> split()[0]

✅ SEGMENTAÇÃO:
   [ ] all, buyers, downsell_buyers, order_bump_buyers
   [ ] upsell_buyers, remarketing_buyers, abandoned_cart
   [ ] inactive, non_buyers

✅ RATE LIMITING:
   [ ] 1.2-2.5s entre mensagens
   [ ] Pausa 10-20s a cada 100 mensagens
   [ ] Batch size adaptativo baseado em campanhas ativas
"""
