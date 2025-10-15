"""
Models - Sistema SaaS de Gerenciamento de Bots
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json

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
    
    # Modelo de comissão (sem planos fixos)
    commission_rate = db.Column(db.Float, default=0.75)  # R$ 0.75 por venda
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
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin da plataforma
    is_banned = db.Column(db.Boolean, default=False)  # Usuário banido
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
    
    def add_commission(self, amount):
        """Adiciona comissão à conta do usuário"""
        commission = self.commission_rate
        self.total_commission_owed += commission
        return commission
    
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
        from datetime import date, timedelta
        
        sale_date_obj = sale_date if isinstance(sale_date, date) else sale_date.date()
        
        if not self.last_sale_date:
            # Primeira venda
            self.current_streak = 1
            self.best_streak = 1
            self.last_sale_date = sale_date_obj
        else:
            days_diff = (sale_date_obj - self.last_sale_date).days
            
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
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100))
    bot_id = db.Column(db.String(50))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_running = db.Column(db.Boolean, default=False)
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
    
    # Relacionamentos
    config = db.relationship('BotConfig', backref='bot', uselist=False, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='bot', lazy='dynamic', cascade='all, delete-orphan')
    pool_associations = db.relationship('PoolBot', backref='bot', lazy='dynamic', cascade='all, delete-orphan')  # ✅ DELETE CASCADE
    
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
    
    # Botões principais (JSON) - CADA BOTÃO TEM SEU ORDER BUMP
    # [{"text": "...", "price": 19.97, "description": "...", 
    #   "order_bump": {"enabled": true, "message": "...", "price": 5, "description": "..."}}]
    main_buttons = db.Column(db.Text)
    
    # Botões de redirecionamento (JSON) - SEM PAGAMENTO
    # [{"text": "...", "url": "https://..."}]
    redirect_buttons = db.Column(db.Text)
    
    # Downsells (JSON)
    downsells = db.Column(db.Text)  # [{"delay_minutes": 5, "message": "...", "media_url": "...", "buttons": [...]}]
    downsells_enabled = db.Column(db.Boolean, default=False)
    
    # Link de acesso após pagamento
    access_link = db.Column(db.String(500))
    
    # Datas
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    def get_main_buttons(self):
        """Retorna botões principais parseados"""
        if self.main_buttons:
            try:
                return json.loads(self.main_buttons)
            except:
                return []
        return []
    
    def set_main_buttons(self, buttons):
        """Define botões principais"""
        self.main_buttons = json.dumps(buttons)
    
    def get_downsells(self):
        """Retorna downsells parseados"""
        if self.downsells:
            try:
                return json.loads(self.downsells)
            except:
                return []
        return []
    
    def set_downsells(self, downsells):
        """Define downsells"""
        self.downsells = json.dumps(downsells)
    
    def get_redirect_buttons(self):
        """Retorna botões de redirecionamento parseados"""
        if self.redirect_buttons:
            try:
                return json.loads(self.redirect_buttons)
            except:
                return []
        return []
    
    def set_redirect_buttons(self, buttons):
        """Define botões de redirecionamento"""
        self.redirect_buttons = json.dumps(buttons)
    
    def to_dict(self):
        """Retorna configuração em formato dict"""
        return {
            'id': self.id,
            'welcome_message': self.welcome_message,
            'welcome_media_url': self.welcome_media_url,
            'welcome_media_type': self.welcome_media_type,
            'main_buttons': self.get_main_buttons(),
            'redirect_buttons': self.get_redirect_buttons(),
            'downsells_enabled': self.downsells_enabled,
            'downsells': self.get_downsells(),
            'access_link': self.access_link
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
            'created_at': self.created_at.isoformat() if self.created_at else None
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
    bot = db.relationship('Bot', backref='pool_associations')
    
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
    
    # Credenciais (criptografadas)
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    api_key = db.Column(db.String(255))
    
    # Campos específicos Paradise
    product_hash = db.Column(db.String(255))  # prod_... (código do produto)
    offer_hash = db.Column(db.String(255))    # ID da oferta (extraído da URL)
    store_id = db.Column(db.String(50))       # ID da conta no Paradise para split
    
    # Campos específicos HooPay
    organization_id = db.Column(db.String(255))  # UUID da organização para split
    
    # Split configuration (padrão 4%)
    split_percentage = db.Column(db.Float, default=4.0)
    
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
    
    def to_dict(self):
        """Retorna dados do gateway em formato dict"""
        return {
            'id': self.id,
            'gateway_type': self.gateway_type,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'total_transactions': self.total_transactions,
            'successful_transactions': self.successful_transactions,
            'success_rate': (self.successful_transactions / self.total_transactions * 100) if self.total_transactions > 0 else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Payment(db.Model):
    """Pagamento"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Dados do pagamento
    payment_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    gateway_type = db.Column(db.String(30))
    gateway_transaction_id = db.Column(db.String(100))
    
    # Valores
    amount = db.Column(db.Float, nullable=False)
    net_amount = db.Column(db.Float)
    
    # Dados do cliente
    customer_user_id = db.Column(db.String(50))
    customer_name = db.Column(db.String(100))
    customer_username = db.Column(db.String(100))
    
    # Produto
    product_name = db.Column(db.String(100))
    product_description = db.Column(db.Text)
    
    # Analytics - Tracking de conversão
    order_bump_shown = db.Column(db.Boolean, default=False)
    order_bump_accepted = db.Column(db.Boolean, default=False)
    order_bump_value = db.Column(db.Float, default=0.0)
    is_downsell = db.Column(db.Boolean, default=False)
    downsell_index = db.Column(db.Integer)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, paid, failed, cancelled
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
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
    telegram_user_id = db.Column(db.String(50), nullable=False, index=True)
    first_name = db.Column(db.String(100))
    username = db.Column(db.String(100))
    
    # Datas
    first_interaction = db.Column(db.DateTime, default=get_brazil_time)
    last_interaction = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)
    
    # Índice único para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('bot_id', 'telegram_user_id', name='unique_bot_user'),
    )


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
        """Retorna dados da campanha em formato dict"""
        return {
            'id': self.id,
            'bot_id': self.bot_id,
            'name': self.name,
            'message': self.message,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'buttons': self.buttons,
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
    telegram_user_id = db.Column(db.String(50), nullable=False, index=True)
    reason = db.Column(db.String(50))  # user_request, bot_blocked, spam_report
    created_at = db.Column(db.DateTime, default=get_brazil_time)
    
    # Índice único
    __table_args__ = (
        db.UniqueConstraint('bot_id', 'telegram_user_id', name='unique_blacklist'),
    )

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
