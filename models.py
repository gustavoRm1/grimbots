"""
Models - Sistema SaaS de Gerenciamento de Bots
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date, timezone
import json
import logging

# Logger
logger = logging.getLogger(__name__)

# Timezone do Brasil (UTC-3)
BRAZIL_TZ_OFFSET = timedelta(hours=-3)

def get_brazil_time():
    """Retorna o horário atual do Brasil (UTC-3)"""
    return datetime.utcnow() + BRAZIL_TZ_OFFSET

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Modelo de Usuário"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    
    # Modelo de comissão (percentual sobre vendas)
    commission_percentage = db.Column(db.Float, default=2.0)  # 2% sobre cada venda (PADRÃO)
    total_commission_owed = db.Column(db.Float, default=0.0)  # Total a pagar
    total_commission_paid = db.Column(db.Float, default=0.0)  # Total já pago
    
    # Dados financeiros (vendas dos bots do usuário)
    total_sales = db.Column(db.Float, default=0.0)
    total_revenue = db.Column(db.Float, default=0.0)
    
    # Gamificação
    ranking_points = db.Column(db.Integer, default=0)  # Pontos calculados
    current_streak = db.Column(db.Integer, default=0)  # Dias consecutivos com vendas
    best_streak = db.Column(db.Integer, default=0)  # Maior streak já alcançado
    last_sale_date = db.Column(db.Date)  # Última venda (para calcular streak)
    
    # ✅ RANKING - Nome de exibição (LGPD compliant)
    ranking_display_name = db.Column(db.String(50), nullable=True)  # Nome escolhido pelo usuário para aparecer no ranking
    ranking_first_visit_handled = db.Column(db.Boolean, default=False)  # Se já escolheu o nome na primeira visita
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin da plataforma
    is_banned = db.Column(db.Boolean, default=False, index=True)  # Usuário banido (indexado para queries de listagem)
    ban_reason = db.Column(db.String(500))  # Motivo do banimento
    banned_at = db.Column(db.DateTime)  # Data do banimento
    
    # Dados adicionais para admin
    phone = db.Column(db.String(20))
    cpf_cnpj = db.Column(db.String(20))
    last_ip = db.Column(db.String(45))  # IPv4 ou IPv6
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    last_login = db.Column(db.DateTime)
    
    # Relacionamentos
    bots = db.relationship('Bot', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    gateways = db.relationship('Gateway', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    push_subscriptions = db.relationship('PushSubscription', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Define senha com hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica senha"""
        return check_password_hash(self.password_hash, password)
    
    def can_add_bot(self):
        """Verifica se pode adicionar mais bots (ilimitado no modelo de comissão)"""
        return True  # Sem limite de bots no modelo de comissão
    
    def get_commission_balance(self):
        """Retorna saldo de comissões a pagar"""
        return self.total_commission_owed - self.total_commission_paid
    
    def add_commission(self, sale_amount):
        """Adiciona comissão baseada no percentual sobre o valor da venda"""
        commission = sale_amount * (self.commission_percentage / 100)
        self.total_commission_owed += commission
        return commission
    
    def calculate_commission(self, sale_amount):
        """Calcula a comissão sem adicionar ao total (apenas retorna o valor)"""
        return sale_amount * (self.commission_percentage / 100)
    
    def calculate_ranking_points(self):
        """Calcula pontos de ranking baseado em performance"""
        # Buscar estatísticas do usuário
        from sqlalchemy import func
        
        # Total de vendas confirmadas
        total_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == self.id,
            Payment.status == 'paid'
        ).scalar() or 0
        
        # Receita total
        revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == self.id,
            Payment.status == 'paid'
        ).scalar() or 0.0
        
        # Taxa de conversão
        total_bot_users = db.session.query(func.count(BotUser.id)).join(Bot).filter(
            Bot.user_id == self.id
        ).scalar() or 0
        
        conversion_rate = (total_sales / total_bot_users * 100) if total_bot_users > 0 else 0
        
        # Fórmula de pontos (balanceada)
        points = int(
            (revenue * 1) +           # 1 ponto por R$ 1,00
            (total_sales * 10) +      # 10 pontos por venda
            (conversion_rate * 50) +  # 50 pontos por % de conversão
            (self.current_streak * 100)  # 100 pontos por dia de streak
        )
        
        return points
    
    def update_streak(self, sale_date):
        """Atualiza streak de vendas consecutivas"""
        if isinstance(sale_date, datetime):
            sale_date_obj = sale_date.date()
        elif isinstance(sale_date, date):
            sale_date_obj = sale_date
        else:
            sale_date_obj = datetime.utcnow().date()
        
        last_date = self.last_sale_date
        if isinstance(last_date, datetime):
            last_date = last_date.date()
        
        if not last_date:
            # Primeira venda
            self.current_streak = 1
            self.best_streak = 1
            self.last_sale_date = sale_date_obj
        else:
            days_diff = (sale_date_obj - last_date).days
            
            if days_diff == 1:
                # Dia consecutivo
                self.current_streak += 1
                if self.current_streak > self.best_streak:
                    self.best_streak = self.current_streak
            elif days_diff == 0:
                # Mesmo dia - mantém streak
                pass
            else:
                # Quebrou o streak
                self.current_streak = 1
            
            self.last_sale_date = sale_date_obj
    
    def to_dict(self):
        """Retorna dados do usuário em formato dict"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'commission_rate': self.commission_rate,
            'commission_balance': self.get_commission_balance(),
            'total_commission_owed': self.total_commission_owed,
            'total_commission_paid': self.total_commission_paid,
            'active_bots': self.bots.filter_by(is_active=True).count(),
            'total_sales': self.total_sales,
            'total_revenue': self.total_revenue,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Bot(db.Model):
    """Modelo de Bot"""
    __tablename__ = 'bots'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Configurações básicas
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100))
    bot_id = db.Column(db.String(50))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_running = db.Column(db.Boolean, default=False, index=True)  # Indexado para filtrar bots em execução
    last_error = db.Column(db.Text)
    
    # Estatísticas
    total_users = db.Column(db.Integer, default=0)
    total_messages = db.Column(db.Integer, default=0)
    total_sales = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0.0)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    last_started = db.Column(db.DateTime)
    last_stopped = db.Column(db.DateTime)
    
    # ============================================================================
    # ❌ META PIXEL (DEPRECATED - MOVIDO PARA REDIRECT_POOLS)
    # ============================================================================
    # ATENÇÃO: Estes campos foram MOVIDOS para RedirectPool (arquitetura correta)
    # SQLite não suporta DROP COLUMN, então eles permanecem no banco mas são IGNORADOS
    # Meta Pixel agora é configurado POR POOL (não por bot) para:
    # - Rastreamento centralizado (1 campanha = 1 pool = 1 pixel)
    # - Alta disponibilidade (bot cai, pool continua tracking)
    # - Dados consolidados (todos eventos no mesmo pixel)
    # NÃO USE ESTES CAMPOS - USE RedirectPool.meta_* ao invés
    # ============================================================================
    # meta_pixel_id = db.Column(db.String(50), nullable=True)
    # meta_access_token = db.Column(db.String(255), nullable=True)
    # meta_tracking_enabled = db.Column(db.Boolean, default=False)
    # meta_test_event_code = db.Column(db.String(100), nullable=True)
    # meta_events_pageview = db.Column(db.Boolean, default=True)
    # meta_events_viewcontent = db.Column(db.Boolean, default=True)
    # meta_events_purchase = db.Column(db.Boolean, default=True)
    # meta_cloaker_enabled = db.Column(db.Boolean, default=False)
    # meta_cloaker_param_name = db.Column(db.String(20), default='apx')
    # meta_cloaker_param_value = db.Column(db.String(50), nullable=True)
    
    # Relacionamentos
    config = db.relationship('BotConfig', backref='bot', uselist=False, cascade='all, delete-orphan')
    # ✅ CRÍTICO: NÃO usar cascade em payments para preservar faturamento quando bot é deletado
    # O faturamento deve ser mantido para ranking, contabilidade e estatísticas do usuário
    payments = db.relationship('Payment', backref='bot', lazy='dynamic')  # Sem cascade - preserva faturamento
    bot_users = db.relationship('BotUser', backref='bot', lazy='dynamic', cascade='all, delete-orphan')
    pool_associations = db.relationship('PoolBot', backref='associated_bot', lazy='dynamic', cascade='all, delete-orphan')  # ✅ DELETE CASCADE
    
    def to_dict(self):
        """Retorna dados do bot em formato dict"""
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'token': self.token[:20] + '...' if self.token else None,
            'is_active': self.is_active,
            'is_running': self.is_running,
            'total_users': self.total_users,
            'total_sales': self.total_sales,
            'total_revenue': self.total_revenue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'has_config': self.config is not None
        }


class BotConfig(db.Model):
    """Configuração do Bot"""
    __tablename__ = 'bot_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, unique=True, index=True)
    
    # Mensagem inicial
    welcome_message = db.Column(db.Text)
    welcome_media_url = db.Column(db.String(500))  # Link do Telegram
    welcome_media_type = db.Column(db.String(20), default='video')  # video, photo
    welcome_audio_enabled = db.Column(db.Boolean, default=False)  # ✅ Áudio complementar
    welcome_audio_url = db.Column(db.String(500))  # ✅ URL do áudio adicional
    
    # Botões principais (JSON) - CADA BOTÃO TEM SEU ORDER BUMP
    # [{"text": "...", "price": 19.97, "description": "...", 
    #   "order_bump": {"enabled": true, "message": "...", "price": 5, "description": "...", 
    #                   "audio_enabled": false, "audio_url": ""}}]
    main_buttons = db.Column(db.Text)
    
    # Botões de redirecionamento (JSON) - SEM PAGAMENTO
    # [{"text": "...", "url": "https://..."}]
    redirect_buttons = db.Column(db.Text)
    
    # Downsells (JSON) - Enviados quando PIX gerado mas não pago
    downsells = db.Column(db.Text)  # [{"delay_minutes": 5, "message": "...", "media_url": "...", "buttons": [...]}]
    downsells_enabled = db.Column(db.Boolean, default=False)
    
    # ✅ UPSELLS (JSON) - Enviados APÓS compra aprovada
    upsells = db.Column(db.Text)  # [{"trigger_product": "INSS Básico", "delay_minutes": 0, "message": "...", "price": 97, ...}]
    upsells_enabled = db.Column(db.Boolean, default=False)
    
    # Link de acesso após pagamento
    access_link = db.Column(db.String(500))
    
    # Mensagens personalizadas
    success_message = db.Column(db.Text)  # Mensagem quando pagamento é aprovado
    pending_message = db.Column(db.Text)  # Mensagem quando pagamento está pendente
    
    # ✅ FLUXO VISUAL (Editor de Fluxograma)
    flow_enabled = db.Column(db.Boolean, default=False, index=True)  # Ativar fluxo visual
    flow_steps = db.Column(db.Text, nullable=True)  # JSON array de steps do fluxo
    flow_start_step_id = db.Column(db.String(50), nullable=True, index=True)  # ID do step inicial do fluxo (/start inicia aqui)
    
    # Datas
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    def get_main_buttons(self):
        """Retorna botões principais parseados"""
        if self.main_buttons:
            try:
                return json.loads(self.main_buttons)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Erro ao parsear main_buttons: {e}")
                return []
        return []
    
    def set_main_buttons(self, buttons):
        """Define botões principais"""
        try:
            self.main_buttons = json.dumps(buttons, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"Erro ao serializar main_buttons: {e}")
            logger.error(f"Dados recebidos: {buttons}")
            raise ValueError(f"Erro ao salvar botões: {e}")
    
    def get_downsells(self):
        """Retorna downsells parseados"""
        if self.downsells:
            try:
                return json.loads(self.downsells)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Erro ao parsear downsells: {e}")
                return []
        return []
    
    def set_downsells(self, downsells):
        """Define downsells"""
        self.downsells = json.dumps(downsells)
    
    def get_upsells(self):
        """Retorna upsells parseados"""
        if self.upsells:
            try:
                return json.loads(self.upsells)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Erro ao parsear upsells: {e}")
                return []
        return []
    
    def set_upsells(self, upsells):
        """Define upsells"""
        self.upsells = json.dumps(upsells)
    
    def get_redirect_buttons(self):
        """Retorna botões de redirecionamento parseados"""
        if self.redirect_buttons:
            try:
                return json.loads(self.redirect_buttons)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Erro ao parsear redirect_buttons: {e}")
                return []
        return []
    
    def set_redirect_buttons(self, buttons):
        """Define botões de redirecionamento"""
        self.redirect_buttons = json.dumps(buttons)
    
    def get_flow_steps(self):
        """Retorna flow_steps parseados"""
        if self.flow_steps:
            try:
                return json.loads(self.flow_steps)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Erro ao parsear flow_steps: {e}")
                return []
        return []
    
    def set_flow_steps(self, steps):
        """Define flow_steps"""
        try:
            if steps:
                self.flow_steps = json.dumps(steps, ensure_ascii=False)
            else:
                self.flow_steps = None
        except (TypeError, ValueError) as e:
            logger.error(f"Erro ao serializar flow_steps: {e}")
            raise ValueError(f"Erro ao salvar flow_steps: {e}")
    
    def to_dict(self):
        """Retorna configuração em formato dict"""
        try:
            # ✅ VALIDAÇÃO CRÍTICA: Garantir que self.id existe
            config_id = getattr(self, 'id', None)
            if config_id is None:
                logger.error(f"❌ BotConfig.to_dict() chamado sem id - config pode não estar salvo no banco")
                # Retornar config mínimo com id None
                return {
                    'id': None,
                    'welcome_message': '',
                    'welcome_media_url': '',
                    'welcome_media_type': 'video',
                    'welcome_audio_enabled': False,
                    'welcome_audio_url': '',
                    'main_buttons': [],
                    'redirect_buttons': [],
                    'downsells_enabled': False,
                    'downsells': [],
                    'upsells_enabled': False,
                    'upsells': [],
                    'access_link': '',
                    'success_message': '',
                    'pending_message': '',
                    'flow_enabled': False,
                    'flow_steps': [],
                    'flow_start_step_id': None
                }
            
            # ✅ VALIDAÇÃO: Tentar obter métodos get_* com tratamento de erro individual
            try:
                main_buttons = self.get_main_buttons()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao obter main_buttons: {e}")
                main_buttons = []
            
            try:
                redirect_buttons = self.get_redirect_buttons()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao obter redirect_buttons: {e}")
                redirect_buttons = []
            
            try:
                downsells = self.get_downsells()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao obter downsells: {e}")
                downsells = []
            
            try:
                upsells = self.get_upsells()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao obter upsells: {e}")
                upsells = []
            
            try:
                flow_steps = self.get_flow_steps()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao obter flow_steps: {e}")
                flow_steps = []
            
            return {
                'id': config_id,
                'welcome_message': getattr(self, 'welcome_message', None) or '',
                'welcome_media_url': getattr(self, 'welcome_media_url', None) or '',
                'welcome_media_type': getattr(self, 'welcome_media_type', None) or 'video',
                'welcome_audio_enabled': getattr(self, 'welcome_audio_enabled', False) or False,
                'welcome_audio_url': getattr(self, 'welcome_audio_url', None) or '',
                'main_buttons': main_buttons,
                'redirect_buttons': redirect_buttons,
                'downsells_enabled': getattr(self, 'downsells_enabled', False) or False,
                'downsells': downsells,
                'upsells_enabled': getattr(self, 'upsells_enabled', False) or False,
                'upsells': upsells,
                'access_link': getattr(self, 'access_link', None) or '',
                'success_message': getattr(self, 'success_message', None) or '',
                'pending_message': getattr(self, 'pending_message', None) or '',
                'flow_enabled': getattr(self, 'flow_enabled', False) or False,
                'flow_steps': flow_steps,
                'flow_start_step_id': getattr(self, 'flow_start_step_id', None) or None
            }
        except Exception as e:
            logger.error(f"❌ Erro ao serializar BotConfig: {e}", exc_info=True)
            # Retornar config mínimo em caso de erro
            return {
                'id': getattr(self, 'id', None),
                'welcome_message': '',
                'welcome_media_url': '',
                'welcome_media_type': 'video',
                'welcome_audio_enabled': False,
                'welcome_audio_url': '',
                'main_buttons': [],
                'redirect_buttons': [],
                'downsells_enabled': False,
                'downsells': [],
                'upsells_enabled': False,
                'upsells': [],
                'access_link': '',
                'success_message': '',
                'pending_message': '',
                'flow_enabled': False,
                'flow_steps': [],
                'flow_start_step_id': None
            }


class RedirectPool(db.Model):
    """Pool de redirecionamento (grupo de bots com load balancing)"""
    __tablename__ = 'redirect_pools'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Identificação
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), nullable=False, index=True)  # "red1", "red2", etc
    description = db.Column(db.Text)
    
    # Configuração
    is_active = db.Column(db.Boolean, default=True, index=True)
    distribution_strategy = db.Column(db.String(20), default='round_robin')
    # Estratégias: round_robin, least_connections, random, weighted
    
    # Controle round robin
    last_bot_index = db.Column(db.Integer, default=0)
    
    # Métricas agregadas (cache)
    total_redirects = db.Column(db.Integer, default=0)
    healthy_bots_count = db.Column(db.Integer, default=0)
    total_bots_count = db.Column(db.Integer, default=0)
    
    # Health do pool (0-100)
    health_percentage = db.Column(db.Integer, default=0)
    last_health_check = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    # ============================================================================
    # ✅ META PIXEL INTEGRATION (NÍVEL DE POOL - ARQUITETURA CORRETA)
    # ============================================================================
    # Pixel configurado POR POOL (não por bot) para:
    # - Rastreamento centralizado (1 campanha = 1 pool = 1 pixel)
    # - Alta disponibilidade (bot cai, pool continua tracking)
    # - Dados consolidados (todos eventos no mesmo pixel)
    # - Configuração simplificada (1 vez por pool vs N vezes por bot)
    # ============================================================================
    meta_pixel_id = db.Column(db.String(50), nullable=True)
    meta_access_token = db.Column(db.Text, nullable=True)  # Criptografado
    meta_tracking_enabled = db.Column(db.Boolean, default=False)
    meta_test_event_code = db.Column(db.String(255), nullable=True)
    meta_events_pageview = db.Column(db.Boolean, default=True)
    meta_events_viewcontent = db.Column(db.Boolean, default=True)
    meta_events_purchase = db.Column(db.Boolean, default=True)
    meta_cloaker_enabled = db.Column(db.Boolean, default=False)
    meta_cloaker_param_name = db.Column(db.String(20), default='grim')
    meta_cloaker_param_value = db.Column(db.String(50), nullable=True)
    
    # ✅ Utmify Integration
    utmify_pixel_id = db.Column(db.String(100), nullable=True)  # Pixel ID da Utmify
    
    # Relacionamentos
    pool_bots = db.relationship('PoolBot', backref='pool', lazy='dynamic', cascade='all, delete-orphan')
    
    # Constraint único: slug por usuário
    __table_args__ = (
        db.UniqueConstraint('user_id', 'slug', name='unique_user_pool_slug'),
    )
    
    def get_online_bots(self):
        """Retorna bots online deste pool"""
        from datetime import datetime
        now = datetime.now()
        
        return self.pool_bots.join(Bot).filter(
            PoolBot.is_enabled == True,
            PoolBot.status == 'online',
            db.or_(
                PoolBot.circuit_breaker_until.is_(None),
                PoolBot.circuit_breaker_until < now
            )
        ).all()
    
    def select_bot(self):
        """Seleciona bot baseado na estratégia configurada"""
        online_bots = self.get_online_bots()
        
        if not online_bots:
            return None
        
        if self.distribution_strategy == 'round_robin':
            # Round robin circular
            self.last_bot_index = (self.last_bot_index + 1) % len(online_bots)
            return online_bots[self.last_bot_index]
        
        elif self.distribution_strategy == 'least_connections':
            # Bot com menos redirects
            return min(online_bots, key=lambda x: x.total_redirects)
        
        elif self.distribution_strategy == 'random':
            # Aleatório
            import random
            return random.choice(online_bots)
        
        elif self.distribution_strategy == 'weighted':
            # Weighted random
            import random
            total_weight = sum(pb.weight for pb in online_bots)
            r = random.uniform(0, total_weight)
            upto = 0
            for pb in online_bots:
                if upto + pb.weight >= r:
                    return pb
                upto += pb.weight
            return online_bots[-1]
        
        return online_bots[0]
    
    def update_health(self):
        """Atualiza métricas de saúde do pool"""
        total = self.pool_bots.count()
        online = self.pool_bots.filter_by(status='online', is_enabled=True).count()
        
        self.total_bots_count = total
        self.healthy_bots_count = online
        self.health_percentage = int((online / total * 100)) if total > 0 else 0
        self.last_health_check = get_brazil_time()
    
    def to_dict(self):
        """Retorna dados do pool em formato dict"""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'is_active': self.is_active,
            'distribution_strategy': self.distribution_strategy,
            'total_redirects': self.total_redirects,
            'healthy_bots': self.healthy_bots_count,
            'total_bots': self.total_bots_count,
            'health_percentage': self.health_percentage,
            'public_url': f'/go/{self.slug}',
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # ✅ CRÍTICO: Retornar configurações do Meta Pixel
            'meta_pixel_id': self.meta_pixel_id,
            'meta_access_token': self.meta_access_token,  # ⚠️ Retornar token (frontend precisa)
            'meta_tracking_enabled': self.meta_tracking_enabled,
            'meta_test_event_code': self.meta_test_event_code,
            'meta_events_pageview': self.meta_events_pageview,
            'meta_events_viewcontent': self.meta_events_viewcontent,
            'meta_events_purchase': self.meta_events_purchase,
            'meta_cloaker_enabled': self.meta_cloaker_enabled,
            'meta_cloaker_param_name': self.meta_cloaker_param_name,
            'meta_cloaker_param_value': self.meta_cloaker_param_value,
            'utmify_pixel_id': self.utmify_pixel_id
        }


class PoolBot(db.Model):
    """Associação entre Pool e Bot (many-to-many com configurações)"""
    __tablename__ = 'pool_bots'
    
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.Integer, db.ForeignKey('redirect_pools.id', ondelete='CASCADE'), nullable=False, index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Configuração específica
    weight = db.Column(db.Integer, default=1)  # Para weighted load balancing
    priority = db.Column(db.Integer, default=0)  # 1=preferencial, 0=normal, -1=backup
    is_enabled = db.Column(db.Boolean, default=True, index=True)
    
    # Health check
    status = db.Column(db.String(20), default='checking', index=True)  # online, offline, degraded, checking
    last_health_check = db.Column(db.DateTime)
    consecutive_failures = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    
    # Circuit breaker
    circuit_breaker_until = db.Column(db.DateTime, index=True)
    
    # Métricas
    total_redirects = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Integer, default=0)  # ms
    
    # Timestamps
    added_at = db.Column(db.DateTime, default=get_brazil_time)
    
    # Relacionamentos
    # ✅ Definir relationship explicitamente sem backref (Bot.pool_associations já existe)
    bot = db.relationship('Bot', overlaps="associated_bot,pool_associations")
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('pool_id', 'bot_id', name='unique_pool_bot'),
    )
    
    def to_dict(self):
        """Retorna dados do pool_bot em formato dict"""
        return {
            'id': self.id,
            'bot': self.bot.to_dict() if self.bot else None,
            'weight': self.weight,
            'priority': self.priority,
            'is_enabled': self.is_enabled,
            'status': self.status,
            'consecutive_failures': self.consecutive_failures,
            'total_redirects': self.total_redirects,
            'avg_response_time': self.avg_response_time,
            'circuit_breaker_active': self.circuit_breaker_until and self.circuit_breaker_until > get_brazil_time(),
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None
        }


class Gateway(db.Model):
    """Gateway de Pagamento"""
    __tablename__ = 'gateways'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Tipo de gateway
    gateway_type = db.Column(db.String(30), nullable=False)  # syncpay, pushynpay, paradise, hoopay
    
    # ============================================================================
    # CORREÇÃO #5: CREDENCIAIS CRIPTOGRAFADAS
    # ============================================================================
    # Armazenamento interno (prefixo _ = privado)
    client_id = db.Column(db.String(255))
    _client_secret = db.Column('client_secret', db.String(1000))  # Criptografado
    _api_key = db.Column('api_key', db.String(1000))  # Criptografado
    
    # Campos específicos Paradise (criptografados)
    _product_hash = db.Column('product_hash', db.String(1000))  # Criptografado
    _offer_hash = db.Column('offer_hash', db.String(1000))  # Criptografado
    store_id = db.Column(db.String(50))  # ID da conta (não sensível)
    
    # Campos específicos HooPay (criptografado)
    _organization_id = db.Column('organization_id', db.String(1000))  # Criptografado
    
    # Campos específicos WiinPay (criptografado)
    _split_user_id = db.Column('split_user_id', db.String(1000))  # Criptografado
    
    # ✅ Campos específicos Átomo Pay (não criptografado - apenas identificador)
    producer_hash = db.Column(db.String(100), nullable=True, index=True)  # Hash do producer (identifica conta do usuário)
    
    # Split configuration (padrão 2%)
    split_percentage = db.Column(db.Float, default=2.0)  # 2% PADRÃO
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_error = db.Column(db.Text)
    
    # Estatísticas
    total_transactions = db.Column(db.Integer, default=0)
    successful_transactions = db.Column(db.Integer, default=0)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    verified_at = db.Column(db.DateTime)
    
    # ============================================================================
    # PROPERTIES: CRIPTOGRAFIA AUTOMÁTICA
    # ============================================================================
    
    @property
    def client_secret(self):
        """Descriptografa client_secret ao acessar"""
        if not self._client_secret:
            return None
        try:
            from utils.encryption import decrypt
            decrypted = decrypt(self._client_secret)
            # ✅ VALIDAÇÃO: Verificar se descriptografia retornou None (indica erro)
            if decrypted is None:
                logger.error(f"❌ Erro ao descriptografar client_secret gateway {self.id}: decrypt retornou None")
                logger.error(f"   Campo interno existe mas descriptografia falhou!")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return decrypted
        except RuntimeError as e:
            # ✅ RuntimeError indica erro de descriptografia (ENCRYPTION_KEY incorreta)
            logger.error(f"❌ ERRO CRÍTICO ao descriptografar client_secret gateway {self.id}: {e}")
            logger.error(f"   Campo interno existe: {self._client_secret[:30] if self._client_secret else 'None'}...")
            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
            logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return None
        except Exception as e:
            # ✅ Outros erros (ex: encoding, formato inválido)
            logger.error(f"❌ Erro inesperado ao descriptografar client_secret gateway {self.id}: {type(e).__name__}: {e}")
            logger.error(f"   Campo interno existe: {self._client_secret[:30] if self._client_secret else 'None'}...")
            return None
    
    @client_secret.setter
    def client_secret(self, value):
        """Criptografa client_secret ao armazenar"""
        if not value:
            self._client_secret = None
        else:
            from utils.encryption import encrypt
            self._client_secret = encrypt(value)
    
    @property
    def api_key(self):
        """Descriptografa api_key ao acessar"""
        if not self._api_key:
            return None
        try:
            from utils.encryption import decrypt
            decrypted = decrypt(self._api_key)
            # ✅ VALIDAÇÃO: Verificar se descriptografia retornou None (indica erro)
            if decrypted is None:
                logger.error(f"❌ Erro ao descriptografar api_key gateway {self.id}: decrypt retornou None")
                logger.error(f"   Campo interno existe mas descriptografia falhou!")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return decrypted
        except RuntimeError as e:
            # ✅ RuntimeError indica erro de descriptografia (ENCRYPTION_KEY incorreta)
            logger.error(f"❌ ERRO CRÍTICO ao descriptografar api_key gateway {self.id}: {e}")
            logger.error(f"   Campo interno existe: {self._api_key[:30] if self._api_key else 'None'}...")
            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
            logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return None
        except Exception as e:
            # ✅ Outros erros (ex: encoding, formato inválido)
            logger.error(f"❌ Erro inesperado ao descriptografar api_key gateway {self.id}: {type(e).__name__}: {e}")
            logger.error(f"   Campo interno existe: {self._api_key[:30] if self._api_key else 'None'}...")
            return None
    
    @api_key.setter
    def api_key(self, value):
        """Criptografa api_key ao armazenar"""
        if not value:
            self._api_key = None
        else:
            from utils.encryption import encrypt
            self._api_key = encrypt(value)
    
    @property
    def product_hash(self):
        """Descriptografa product_hash ao acessar"""
        if not self._product_hash:
            return None
        try:
            from utils.encryption import decrypt
            decrypted = decrypt(self._product_hash)
            # ✅ VALIDAÇÃO: Verificar se descriptografia retornou None (indica erro)
            if decrypted is None:
                logger.error(f"❌ Erro ao descriptografar product_hash gateway {self.id}: decrypt retornou None")
                logger.error(f"   Campo interno existe mas descriptografia falhou!")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return decrypted
        except RuntimeError as e:
            # ✅ RuntimeError indica erro de descriptografia (ENCRYPTION_KEY incorreta)
            logger.error(f"❌ ERRO CRÍTICO ao descriptografar product_hash gateway {self.id}: {e}")
            logger.error(f"   Campo interno existe: {self._product_hash[:30] if self._product_hash else 'None'}...")
            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
            logger.error(f"   SOLUÇÃO: Reconfigure o gateway {self.gateway_type} (ID: {self.id}) em /settings")
            return None
        except Exception as e:
            # ✅ Outros erros (ex: encoding, formato inválido)
            logger.error(f"❌ Erro inesperado ao descriptografar product_hash gateway {self.id}: {type(e).__name__}: {e}")
            logger.error(f"   Campo interno existe: {self._product_hash[:30] if self._product_hash else 'None'}...")
            return None
    
    @product_hash.setter
    def product_hash(self, value):
        """Criptografa product_hash ao armazenar"""
        if not value:
            self._product_hash = None
        else:
            from utils.encryption import encrypt
            self._product_hash = encrypt(value)
    
    @property
    def offer_hash(self):
        """Descriptografa offer_hash ao acessar"""
        if not self._offer_hash:
            return None
        try:
            from utils.encryption import decrypt
            return decrypt(self._offer_hash)
        except Exception as e:
            logger.error(f"Erro ao descriptografar offer_hash gateway {self.id}: {e}")
            return None
    
    @offer_hash.setter
    def offer_hash(self, value):
        """Criptografa offer_hash ao armazenar"""
        if not value:
            self._offer_hash = None
        else:
            from utils.encryption import encrypt
            self._offer_hash = encrypt(value)
    
    @property
    def organization_id(self):
        """Descriptografa organization_id ao acessar"""
        if not self._organization_id:
            return None
        try:
            from utils.encryption import decrypt
            return decrypt(self._organization_id)
        except Exception as e:
            logger.error(f"Erro ao descriptografar organization_id gateway {self.id}: {e}")
            return None
    
    @organization_id.setter
    def organization_id(self, value):
        """Criptografa organization_id ao armazenar"""
        if not value:
            self._organization_id = None
        else:
            from utils.encryption import encrypt
            self._organization_id = encrypt(value)
    
    @property
    def split_user_id(self):
        """Descriptografa split_user_id ao acessar"""
        if not self._split_user_id:
            return None
        try:
            from utils.encryption import decrypt
            return decrypt(self._split_user_id)
        except Exception as e:
            logger.error(f"Erro ao descriptografar split_user_id gateway {self.id}: {e}")
            return None
    
    @split_user_id.setter
    def split_user_id(self, value):
        """Criptografa split_user_id ao armazenar"""
        if not value:
            self._split_user_id = None
        else:
            from utils.encryption import encrypt
            self._split_user_id = encrypt(value)
    
    def to_dict(self):
        """Retorna dados do gateway em formato dict"""
        result = {
            'id': self.id,
            'gateway_type': self.gateway_type,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'total_transactions': self.total_transactions,
            'successful_transactions': self.successful_transactions,
            'success_rate': (self.successful_transactions / self.total_transactions * 100) if self.total_transactions > 0 else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        # ✅ Adicionar credenciais para edição (descriptografadas)
        # Isso permite que o frontend preencha os formulários de edição
        if self.gateway_type == 'syncpay':
            result['client_id'] = self.client_id
            result['client_secret'] = self.client_secret
        elif self.gateway_type in ['pushynpay', 'paradise', 'wiinpay', 'orionpay', 'umbrellapag']:
            result['api_key'] = self.api_key
            if self.gateway_type == 'paradise':
                result['product_hash'] = self.product_hash
                result['offer_hash'] = self.offer_hash
            elif self.gateway_type == 'wiinpay':
                result['split_user_id'] = self.split_user_id
            elif self.gateway_type == 'umbrellapag':
                result['product_hash'] = self.product_hash
            # OrionPay só precisa de api_key (sem campos adicionais)
        elif self.gateway_type == 'atomopay':
            result['api_token'] = self.api_key  # Átomo Pay usa api_token (mesmo valor de api_key)
            result['product_hash'] = self.product_hash
            # ✅ REMOVIDO: offer_hash não é mais necessário (ofertas são criadas dinamicamente)
            # result['offer_hash'] = self.offer_hash
        elif self.gateway_type == 'babylon':
            result['api_key'] = self.api_key  # Secret Key (criptografada)
            result['company_id'] = self.client_id  # Company ID (não criptografado - armazenado em client_id)
        elif self.gateway_type == 'bolt':
            result['api_key'] = self.api_key  # Secret Key (criptografada)
            result['company_id'] = self.client_id  # Company ID (armazenado em client_id)
        
        return result


class Payment(db.Model):
    """Pagamento"""
    __tablename__ = 'payments'
    __table_args__ = (
        db.UniqueConstraint('gateway_type', 'gateway_transaction_hash', name='uq_payment_gateway_hash'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Dados do pagamento
    payment_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    gateway_type = db.Column(db.String(30))
    gateway_transaction_id = db.Column(db.String(100))
    gateway_transaction_hash = db.Column(db.String(100))  # ✅ Hash para consulta de status (Paradise)

    payment_method = db.Column(db.String(20), nullable=True, index=True)
    
    # Valores
    amount = db.Column(db.Float, nullable=False)
    net_amount = db.Column(db.Float)
    
    # Dados do cliente
    customer_user_id = db.Column(db.String(255))
    customer_name = db.Column(db.String(255))
    customer_username = db.Column(db.String(255))
    # ✅ CRÍTICO: Email, phone e document do cliente (para Meta Pixel Purchase)
    customer_email = db.Column(db.String(255), nullable=True, index=True)
    customer_phone = db.Column(db.String(50), nullable=True, index=True)
    customer_document = db.Column(db.String(50), nullable=True)  # CPF/CNPJ
    
    # Produto
    product_name = db.Column(db.String(100))
    product_description = db.Column(db.Text)
    
    # Analytics - Tracking de conversão
    order_bump_shown = db.Column(db.Boolean, default=False)
    order_bump_accepted = db.Column(db.Boolean, default=False)
    order_bump_value = db.Column(db.Float, default=0.0)
    is_downsell = db.Column(db.Boolean, default=False)
    downsell_index = db.Column(db.Integer)
    is_upsell = db.Column(db.Boolean, default=False)
    upsell_index = db.Column(db.Integer)
    is_remarketing = db.Column(db.Boolean, default=False)
    remarketing_campaign_id = db.Column(db.Integer)
    
    # ✅ SISTEMA DE ASSINATURAS - Campos adicionais
    button_index = db.Column(db.Integer, nullable=True, index=True)  # Índice do botão clicado
    button_config = db.Column(db.Text, nullable=True)  # JSON completo do botão no momento da compra
    has_subscription = db.Column(db.Boolean, default=False, index=True)  # Flag rápida para filtrar
    
    # Status
    status = db.Column(db.String(20), default='pending', index=True)  # pending, paid, failed, cancelled (indexado para queries frequentes)
    
    # ✅ META PIXEL INTEGRATION
    meta_purchase_sent = db.Column(db.Boolean, default=False)
    meta_purchase_sent_at = db.Column(db.DateTime, nullable=True)
    meta_event_id = db.Column(db.String(100), nullable=True)
    meta_viewcontent_sent = db.Column(db.Boolean, default=False)
    meta_viewcontent_sent_at = db.Column(db.DateTime, nullable=True)
    
    # ✅ DELIVERY TRACKING - Purchase disparado na página de entrega
    delivery_token = db.Column(db.String(64), unique=True, nullable=True, index=True)  # Token único para acesso à página de entrega
    purchase_sent_from_delivery = db.Column(db.Boolean, default=False)  # Flag se Purchase foi disparado da página de entrega
    
    # ✅ FLUXO VISUAL - Rastreamento de step atual
    flow_step_id = db.Column(db.String(50), nullable=True, index=True)  # ID do step do fluxo que gerou este payment
    # ✅ UTM TRACKING
    utm_source = db.Column(db.String(255), nullable=True)
    utm_campaign = db.Column(db.String(255), nullable=True)
    utm_content = db.Column(db.String(255), nullable=True)
    utm_medium = db.Column(db.String(255), nullable=True)
    utm_term = db.Column(db.String(255), nullable=True)
    fbclid = db.Column(db.String(255), nullable=True)
    campaign_code = db.Column(db.String(255), nullable=True)
    # ✅ CONTEXTO ORIGINAL DO CLIQUE (persistente para remarketing / expiração do Redis)
    click_context_url = db.Column(db.Text, nullable=True)
    
    # ✅ TRACKING V4 - Tracking Token Universal
    tracking_token = db.Column(db.String(200), nullable=True, index=True)  # Tracking V4 - QI 500 (aumentado para 200 para garantir compatibilidade)
    # ✅ CRÍTICO: pageview_event_id para deduplicação Meta Pixel (fallback se Redis expirar)
    pageview_event_id = db.Column(db.String(256), nullable=True, index=True)  # Event ID do PageView para reutilizar no Purchase
    # ✅ META PIXEL COOKIES (para fallback no Purchase se Redis expirar)
    fbp = db.Column(db.String(255), nullable=True)  # Facebook Browser ID (_fbp cookie)
    fbc = db.Column(db.String(255), nullable=True)  # Facebook Click ID (_fbc cookie)
    
    # ✅ DEMOGRAPHIC DATA (Para Analytics Avançado)
    customer_age = db.Column(db.Integer, nullable=True)
    customer_city = db.Column(db.String(100), nullable=True)
    customer_state = db.Column(db.String(255), nullable=True)
    customer_country = db.Column(db.String(255), nullable=True, default='BR')
    customer_gender = db.Column(db.String(50), nullable=True)
    
    # ✅ DEVICE DATA
    device_type = db.Column(db.String(50), nullable=True)  # mobile/desktop
    os_type = db.Column(db.String(255), nullable=True)  # iOS/Android/Windows/Linux/macOS
    browser = db.Column(db.String(255), nullable=True)  # Chrome/Safari/Firefox
    device_model = db.Column(db.String(255), nullable=True)  # iPhone 14 Pro, Galaxy S23, etc.
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)  # ✅ Campo para debounce no sync
    paid_at = db.Column(db.DateTime)
    
    def to_dict(self):
        """Retorna dados do pagamento em formato dict"""
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'amount': self.amount,
            'net_amount': self.net_amount,
            'customer_name': self.customer_name,
            'customer_username': self.customer_username,
            'product_name': self.product_name,
            'status': self.status,
            'gateway_type': self.gateway_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None
        }


class BotUser(db.Model):
    """Usuário que interagiu com o bot"""
    __tablename__ = 'bot_users'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Dados do usuário do Telegram
    telegram_user_id = db.Column(db.String(255), nullable=False, index=True)
    first_name = db.Column(db.String(255))
    username = db.Column(db.String(255))
    
    # Arquivamento (quando bot troca de token)
    archived = db.Column(db.Boolean, default=False, index=True)  # Usuario de token antigo
    archived_reason = db.Column(db.String(100))  # Ex: "token_changed"
    archived_at = db.Column(db.DateTime)  # Quando foi arquivado
    
    # ✅ WELCOME MESSAGE TRACKING (recuperação automática de crashes)
    welcome_sent = db.Column(db.Boolean, default=False, index=True)  # Se já recebeu boas-vindas
    welcome_sent_at = db.Column(db.DateTime, nullable=True)  # Quando recebeu
    
    # ✅ META PIXEL INTEGRATION
    meta_pageview_sent = db.Column(db.Boolean, default=False)
    meta_pageview_sent_at = db.Column(db.DateTime, nullable=True)
    meta_viewcontent_sent = db.Column(db.Boolean, default=False)
    meta_viewcontent_sent_at = db.Column(db.DateTime, nullable=True)
    
    # ✅ UTM TRACKING
    utm_source = db.Column(db.String(255), nullable=True)
    utm_campaign = db.Column(db.String(255), nullable=True)
    utm_content = db.Column(db.String(255), nullable=True)
    utm_medium = db.Column(db.String(255), nullable=True)
    utm_term = db.Column(db.String(255), nullable=True)
    fbclid = db.Column(db.String(255), nullable=True)
    campaign_code = db.Column(db.String(255), nullable=True)
    external_id = db.Column(db.String(255), nullable=True)  # Para tracking de cliques
    
    # ✅ META PIXEL COOKIES (para matching Purchase com PageView)
    fbp = db.Column(db.String(255), nullable=True)  # Facebook Browser ID (_fbp cookie)
    fbc = db.Column(db.String(255), nullable=True)  # Facebook Click ID (_fbc cookie)
    
    # ✅ TRACKING ELITE (IP/User-Agent capturados no redirect)
    ip_address = db.Column(db.String(255), nullable=True)  # IP do primeiro click
    user_agent = db.Column(db.Text, nullable=True)  # User-Agent completo
    tracking_session_id = db.Column(db.String(255), nullable=True)  # UUID para correlação
    click_timestamp = db.Column(db.DateTime, nullable=True)  # Timestamp do click
    
    # ✅ DEMOGRAPHIC DATA (Para Analytics Avançado)
    customer_age = db.Column(db.Integer, nullable=True)
    customer_city = db.Column(db.String(100), nullable=True)
    customer_state = db.Column(db.String(50), nullable=True)
    customer_country = db.Column(db.String(50), nullable=True, default='BR')
    customer_gender = db.Column(db.String(20), nullable=True)
    
    # ✅ DEVICE DATA
    device_type = db.Column(db.String(20), nullable=True)  # mobile/desktop
    os_type = db.Column(db.String(50), nullable=True)  # iOS/Android/Windows/Linux/macOS
    browser = db.Column(db.String(50), nullable=True)  # Chrome/Safari/Firefox
    device_model = db.Column(db.String(255), nullable=True)  # iPhone 14 Pro, Galaxy S23, etc.
    
    # Datas
    first_interaction = db.Column(db.DateTime, default=get_brazil_time)
    last_interaction = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    # Índice único para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('bot_id', 'telegram_user_id', name='unique_bot_user'),
    )
    
    def to_dict(self):
        """Retorna dados do bot user em formato dict"""
        return {
            'id': self.id,
            'bot_id': self.bot_id,
            'telegram_user_id': self.telegram_user_id,
            'first_name': self.first_name,
            'username': self.username,
            'archived': self.archived,
            'first_interaction': self.first_interaction.isoformat() if self.first_interaction else None,
            'last_interaction': self.last_interaction.isoformat() if self.last_interaction else None
        }


class BotMessage(db.Model):
    """Mensagens trocadas entre bot e usuário do Telegram"""
    __tablename__ = 'bot_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    bot_user_id = db.Column(db.Integer, db.ForeignKey('bot_users.id'), nullable=False, index=True)
    telegram_user_id = db.Column(db.String(255), nullable=False, index=True)
    
    # Dados da mensagem
    message_id = db.Column(db.String(100), nullable=False, index=True)  # ID da mensagem no Telegram
    message_text = db.Column(db.Text, nullable=True)  # Texto da mensagem
    message_type = db.Column(db.String(20), default='text')  # text, photo, video, document, etc
    media_url = db.Column(db.String(500), nullable=True)  # URL da mídia (se houver)
    
    # Direção da mensagem
    direction = db.Column(db.String(20), nullable=False, index=True)  # 'incoming' (usuário -> bot) ou 'outgoing' (bot -> usuário)
    
    # Metadata
    is_read = db.Column(db.Boolean, default=False, index=True)  # Se foi lida pelo dono do bot
    raw_data = db.Column(db.Text, nullable=True)  # Dados brutos do Telegram (JSON)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    
    # Relacionamentos
    bot = db.relationship('Bot', backref='messages')
    bot_user = db.relationship('BotUser', backref='messages')
    

class WebhookEvent(db.Model):
    """Registro bruto de webhooks recebidos para auditoria e replay."""
    __tablename__ = 'webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    gateway_type = db.Column(db.String(50), nullable=False, index=True)
    dedup_key = db.Column(db.String(200), nullable=False, unique=True)
    transaction_id = db.Column(db.String(150), index=True)
    transaction_hash = db.Column(db.String(150), index=True)
    status = db.Column(db.String(30), index=True)
    payload = db.Column(db.JSON, nullable=False)
    received_at = db.Column(db.DateTime, default=get_brazil_time, index=True)


class WebhookPendingMatch(db.Model):
    """Webhooks que ainda não puderam ser aplicados a um Payment existente."""
    __tablename__ = 'webhook_pending_matches'

    id = db.Column(db.Integer, primary_key=True)
    gateway_type = db.Column(db.String(50), nullable=False, index=True)
    dedup_key = db.Column(db.String(200), nullable=False, unique=True)
    transaction_id = db.Column(db.String(150), index=True)
    transaction_hash = db.Column(db.String(150), index=True)
    status = db.Column(db.String(30), index=True)
    payload = db.Column(db.JSON, nullable=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Retorna dados do pending match em formato dict"""
        return {
            'id': self.id,
            'gateway_type': self.gateway_type,
            'transaction_id': self.transaction_id,
            'transaction_hash': self.transaction_hash,
            'status': self.status,
            'attempts': self.attempts,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_attempt_at': self.last_attempt_at.isoformat() if self.last_attempt_at else None,
        }


class RemarketingCampaign(db.Model):
    """Campanha de Remarketing"""
    __tablename__ = 'remarketing_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Configuração
    name = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(500))
    media_type = db.Column(db.String(20))  # photo, video
    audio_enabled = db.Column(db.Boolean, default=False)  # ✅ Áudio complementar
    audio_url = db.Column(db.String(500))  # ✅ URL do áudio adicional
    buttons = db.Column(db.JSON)  # [{text, url/callback_data}]
    
    # Segmentação
    target_audience = db.Column(db.String(50), default='non_buyers')  # all, non_buyers, abandoned_cart, inactive
    days_since_last_contact = db.Column(db.Integer, default=3)  # Mínimo de dias sem contato
    exclude_buyers = db.Column(db.Boolean, default=True)
    
    # Rate Limiting
    cooldown_hours = db.Column(db.Integer, default=24)
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, sending, completed, paused, failed
    
    # Resultados
    total_targets = db.Column(db.Integer, default=0)  # Quantos devem receber
    total_sent = db.Column(db.Integer, default=0)  # Quantos receberam
    total_failed = db.Column(db.Integer, default=0)  # Quantos falharam
    total_blocked = db.Column(db.Integer, default=0)  # Quantos bloquearam
    total_clicks = db.Column(db.Integer, default=0)  # Quantos clicaram (rastreado via callback)
    total_sales = db.Column(db.Integer, default=0)  # Vendas geradas
    revenue_generated = db.Column(db.Float, default=0.0)  # Receita gerada
    
    # Datas
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    
    # Relacionamentos
    bot = db.relationship('Bot', backref='remarketing_campaigns')
    
    def to_dict(self):
        """Retorna dados da campanha em formato dict com validação robusta"""
        import json
        
        # ✅ SOLUÇÃO CRÍTICA #3: TRATAMENTO ROBUSTO DE SERIALIZAÇÃO
        buttons_value = self.buttons
        
        # ✅ CORREÇÃO CRÍTICA: Se for None, retornar array vazio (não None)
        # Isso garante que o frontend sempre recebe um array, facilitando o processamento
        if buttons_value is None:
            buttons_final = []
        # Se for string JSON, parsear
        elif isinstance(buttons_value, str):
            try:
                parsed = json.loads(buttons_value)
                buttons_final = parsed if isinstance(parsed, list) else ([] if parsed is None else [parsed])
            except Exception as e:
                # Se falhar o parse, retornar None e logar erro
                import logging
                logging.getLogger(__name__).error(f"❌ Erro ao parsear buttons JSON da campanha {self.id}: {e}")
                buttons_final = None
        # Se for array, usar direto
        elif isinstance(buttons_value, list):
            buttons_final = buttons_value
        # Se for dict (único botão), converter para array
        elif isinstance(buttons_value, dict):
            buttons_final = [buttons_value]
        # Qualquer outro tipo, usar None (preservar original)
        else:
            import logging
            logging.getLogger(__name__).warning(f"⚠️ Tipo inesperado de buttons na campanha {self.id}: {type(buttons_value)}")
            buttons_final = None
        
        return {
            'id': self.id,
            'bot_id': self.bot_id,
            'name': self.name,
            'message': self.message,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'audio_enabled': self.audio_enabled or False,
            'audio_url': self.audio_url or '',
            'buttons': buttons_final if buttons_final is not None else [],  # ✅ Sempre array (nunca None ou tipo inesperado)
            'target_audience': self.target_audience,
            'days_since_last_contact': self.days_since_last_contact,
            'exclude_buyers': self.exclude_buyers,
            'cooldown_hours': self.cooldown_hours,
            'status': self.status,
            'total_targets': self.total_targets,
            'total_sent': self.total_sent,
            'total_failed': self.total_failed,
            'total_blocked': self.total_blocked,
            'total_clicks': self.total_clicks,
            'total_sales': self.total_sales,
            'revenue_generated': float(self.revenue_generated) if self.revenue_generated else 0.0,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class RemarketingBlacklist(db.Model):
    """Usuários que não querem receber remarketing"""
    __tablename__ = 'remarketing_blacklist'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    telegram_user_id = db.Column(db.String(255), nullable=False, index=True)
    reason = db.Column(db.String(50))  # user_request, bot_blocked, spam_report
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    
    # Índice único
    __table_args__ = (
        db.UniqueConstraint('bot_id', 'telegram_user_id', name='unique_blacklist'),
    )

class Subscription(db.Model):
    """Assinatura de acesso a grupo VIP"""
    __tablename__ = 'subscriptions'
    __table_args__ = (
        db.UniqueConstraint('payment_id', name='uq_subscription_payment'),  # ✅ IDEMPOTÊNCIA
        db.Index('idx_subscription_status_expires', 'status', 'expires_at'),  # ✅ PERFORMANCE
        db.Index('idx_subscription_vip_chat', 'vip_chat_id', 'status'),  # ✅ PERFORMANCE
    )
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos (CASCADE para integridade referencial)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    # ✅ CORREÇÃO 2 (ROBUSTA): CASCADE garante que subscriptions sejam deletadas quando bot é deletado
    # Previne subscriptions órfãs e erros em cascata quando bot é removido
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Dados do usuário
    telegram_user_id = db.Column(db.String(255), nullable=False, index=True)
    customer_name = db.Column(db.String(255))
    
    # Configuração da assinatura
    duration_type = db.Column(db.String(20), nullable=False)  # 'hours', 'days', 'weeks', 'months'
    duration_value = db.Column(db.Integer, nullable=False)  # Ex: 30 (para 30 dias)
    
    # Grupo VIP (Chat ID direto - mais confiável)
    vip_chat_id = db.Column(db.String(100), nullable=False, index=True)  # Chat ID do grupo (ex: -1001234567890)
    vip_group_link = db.Column(db.String(500), nullable=True)  # Link original (opcional, para referência)
    
    # Datas (SEMPRE UTC para compatibilidade com APScheduler)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Quando começou (QUANDO ENTROU NO GRUPO - NULL se ainda não entrou)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)  # Quando expira (calculado quando started_at é definido)
    removed_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Quando foi removido do grupo
    
    # Status
    status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'active', 'expired', 'removed', 'cancelled', 'error'
    # 'pending' = Pagamento confirmado mas ainda não entrou no grupo
    # 'active' = Entrou no grupo, contagem iniciada
    # 'expired' = Tempo expirado mas ainda não removido (aguardando remoção)
    # 'removed' = Removido do grupo automaticamente
    # 'cancelled' = Cancelado (payment failed/refunded)
    # 'error' = Erro ao remover (aguardando retry)
    
    # Metadata
    removed_by = db.Column(db.String(50), default='system')  # 'system', 'manual', 'renewed'
    error_count = db.Column(db.Integer, default=0)  # Contador de tentativas de remoção falhadas
    last_error = db.Column(db.Text, nullable=True)  # Última mensagem de erro
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    payment = db.relationship('Payment', backref='subscription')
    bot = db.relationship('Bot', backref='subscriptions')
    
    def is_expired(self):
        """Verifica se assinatura está expirada"""
        if self.status != 'active' or not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def days_remaining(self):
        """Retorna dias restantes"""
        if self.status != 'active' or not self.expires_at:
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)
    
    def to_dict(self):
        """Retorna dict com dados da subscription"""
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'bot_id': self.bot_id,
            'telegram_user_id': self.telegram_user_id,
            'customer_name': self.customer_name,
            'duration_type': self.duration_type,
            'duration_value': self.duration_value,
            'vip_chat_id': self.vip_chat_id,
            'vip_group_link': self.vip_group_link,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'removed_at': self.removed_at.isoformat() if self.removed_at else None,
            'status': self.status,
            'removed_by': self.removed_by,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_expired': self.is_expired(),
            'days_remaining': self.days_remaining()
        }

class AuditLog(db.Model):
    """Log de auditoria para ações dos admins"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    
    # Dados da ação
    action = db.Column(db.String(50), nullable=False, index=True)  # ban, unban, edit, delete, impersonate, etc
    description = db.Column(db.Text)  # Detalhes da ação
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Dados antes/depois (JSON)
    data_before = db.Column(db.Text)  # Estado antes da mudança
    data_after = db.Column(db.Text)  # Estado depois da mudança
    
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    
    # Relacionamentos
    admin = db.relationship('User', foreign_keys=[admin_id], backref='admin_actions')
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='audit_logs_received')
    
    def to_dict(self):
        return {
            'id': self.id,
            'admin': self.admin.email if self.admin else None,
            'target_user': self.target_user.email if self.target_user else None,
            'action': self.action,
            'description': self.description,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Commission(db.Model):
    """Comissão gerada por venda"""
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False, index=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Valores
    sale_amount = db.Column(db.Float, nullable=False)  # Valor da venda
    commission_amount = db.Column(db.Float, nullable=False)  # Valor da comissão (R$ 0.75)
    commission_rate = db.Column(db.Float, nullable=False)  # Taxa aplicada
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    paid_at = db.Column(db.DateTime)
    
    # Relacionamentos
    user = db.relationship('User', backref='commissions')
    payment = db.relationship('Payment', backref='commission_record', uselist=False)
    bot = db.relationship('Bot', backref='commissions')
    
    def to_dict(self):
        """Retorna dados da comissão em formato dict"""
        return {
            'id': self.id,
            'sale_amount': self.sale_amount,
            'commission_amount': self.commission_amount,
            'commission_rate': self.commission_rate,
            'status': self.status,
            'bot_name': self.bot.name if self.bot else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None
        }

class Achievement(db.Model):
    """Conquistas/Badges disponíveis na plataforma"""
    __tablename__ = 'achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados da conquista
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    icon = db.Column(db.String(50))  # Emoji ou classe do ícone
    badge_color = db.Column(db.String(20))  # gold, silver, bronze, blue, etc
    
    # Condições para desbloquear
    requirement_type = db.Column(db.String(50), nullable=False)  # revenue, sales, conversion, streak, speed
    requirement_value = db.Column(db.Float, nullable=False)  # Valor mínimo
    
    # Pontos que a conquista dá
    points = db.Column(db.Integer, default=0)
    
    # Raridade
    rarity = db.Column(db.String(20), default='common')  # common, rare, epic, legendary
    
    created_at = db.Column(db.DateTime, default=get_brazil_time)

class UserAchievement(db.Model):
    """Conquistas desbloqueadas pelos usuários"""
    __tablename__ = 'user_achievements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievements.id'), nullable=False, index=True)
    
    unlocked_at = db.Column(db.DateTime, default=get_brazil_time)
    notified = db.Column(db.Boolean, default=False)  # Se o usuário já foi notificado
    
    # Relacionamentos
    user = db.relationship('User', backref='achievements')
    achievement = db.relationship('Achievement')
    
    # Índice único
    __table_args__ = (
        db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),
    )


class PushSubscription(db.Model):
    """Subscription de Push Notification do usuário"""
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Dados da subscription (JSON)
    endpoint = db.Column(db.Text, nullable=False, unique=True, index=True)
    p256dh = db.Column(db.Text, nullable=False)  # Chave pública do cliente
    auth = db.Column(db.Text, nullable=False)    # Auth secret
    
    # Metadata
    user_agent = db.Column(db.String(500))
    device_info = db.Column(db.String(200))  # "mobile", "desktop", etc
    
    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_used_at = db.Column(db.DateTime)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    def to_dict(self):
        """Converte para dict (formato Web Push API)"""
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh,
                'auth': self.auth
            }
        }
    
    def __repr__(self):
        return f'<PushSubscription {self.id} user={self.user_id}>'


class NotificationSettings(db.Model):
    """Configurações de notificações do usuário (simples)"""
    __tablename__ = 'notification_settings'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    
    # Toggles simples (sem filtros, sem cooldown, sem limites)
    notify_approved_sales = db.Column(db.Boolean, default=True, nullable=False)  # Vendas aprovadas
    notify_pending_sales = db.Column(db.Boolean, default=False, nullable=False)  # Vendas pendentes (default: off)
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    # Relacionamento
    user = db.relationship('User', backref='notification_settings')
    
    @classmethod
    def get_or_create(cls, user_id):
        """Busca ou cria settings para o usuário"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def to_dict(self):
        """Converte para dict"""
        return {
            'notify_approved_sales': self.notify_approved_sales,
            'notify_pending_sales': self.notify_pending_sales
        }
    
    def __repr__(self):
        return f'<NotificationSettings user={self.user_id} approved={self.notify_approved_sales} pending={self.notify_pending_sales}>'
