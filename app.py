"""
SaaS Bot Manager - Aplicação Principal
Sistema de gerenciamento de bots do Telegram com painel web
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, Bot, BotConfig, Gateway, Payment, AuditLog, Achievement, UserAchievement, BotUser, RedirectPool, PoolBot, RemarketingCampaign, RemarketingBlacklist
from bot_manager import BotManager
from datetime import datetime, timedelta
from functools import wraps
import os
import logging
import json
import time
from dotenv import load_dotenv

# ============================================================================
# CARREGAR VARIÁVEIS DE AMBIENTE (.env)
# ============================================================================
load_dotenv()
logger_dotenv = logging.getLogger(__name__)
logger_dotenv.info("✅ Variáveis de ambiente carregadas")

# Configuração de logging LIMPO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Silenciar logs desnecessários
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)
logging.getLogger('apscheduler.executors').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# ============================================================================
# GAMIFICAÇÃO V2.0 - IMPORTS
# ============================================================================
try:
    from ranking_engine_v2 import RankingEngine
    from achievement_checker_v2 import AchievementChecker
    from gamification_websocket import register_gamification_events
    GAMIFICATION_V2_ENABLED = True
    logger.info("✅ Gamificação V2.0 carregada")
except ImportError as e:
    GAMIFICATION_V2_ENABLED = False
    logger.warning(f"⚠️ Gamificação V2.0 não disponível: {e}")

# Inicializar Flask
app = Flask(__name__)

# ============================================================================
# CORREÇÃO #4: SECRET_KEY OBRIGATÓRIA E FORTE
# ============================================================================
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    raise RuntimeError(
        "\n❌ ERRO CRÍTICO: SECRET_KEY não configurada!\n\n"
        "Execute:\n"
        "  python -c \"import secrets; print('SECRET_KEY=' + secrets.token_hex(32))\" >> .env\n"
    )

if SECRET_KEY == 'dev-secret-key-change-in-production':
    raise RuntimeError(
        "\n❌ ERRO CRÍTICO: SECRET_KEY padrão detectada!\n"
        "Gere uma nova: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
    )

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        f"\n❌ ERRO CRÍTICO: SECRET_KEY muito curta ({len(SECRET_KEY)} caracteres)!\n"
        "Mínimo: 32 caracteres. Gere uma nova: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
    )

app.config['SECRET_KEY'] = SECRET_KEY
logger.info("✅ SECRET_KEY validada (forte e única)")

# ✅ CORREÇÃO: Usar caminho ABSOLUTO para SQLite (compatível com threads)
import os
from pathlib import Path

# Diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent

# Caminho absoluto para o banco de dados
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'

# Criar pasta instance se não existir
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# URI com caminho absoluto
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    f'sqlite:///{DB_PATH}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 20,  # ✅ Pool maior para múltiplos usuários simultâneos
    'max_overflow': 10,  # ✅ Permitir até 30 conexões totais (20 + 10)
    'connect_args': {
        'check_same_thread': False,  # ✅ Permitir acesso de múltiplas threads
        'timeout': 30  # ✅ Timeout maior para evitar lock em alta carga
    }
}

# Inicializar extensões
db.init_app(app)

# ============================================================================
# CORREÇÃO #1: CORS RESTRITO (não aceitar *)
# ============================================================================
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
socketio = SocketIO(app, 
    cors_allowed_origins=ALLOWED_ORIGINS,  # ✅ CORRIGIDO: Lista específica
    async_mode='threading'
)
logger.info(f"✅ CORS configurado: {ALLOWED_ORIGINS}")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'warning'

# ============================================================================
# CORREÇÃO #2: CSRF PROTECTION
# ============================================================================
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
logger.info("✅ CSRF Protection ativada")

# ============================================================================
# CORREÇÃO #6: RATE LIMITING
# ============================================================================
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://",  # Em produção: redis://localhost:6379
    headers_enabled=True
)
logger.info("✅ Rate Limiting configurado")

# Inicializar scheduler para polling
from flask_apscheduler import APScheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Inicializar gerenciador de bots
bot_manager = BotManager(socketio, scheduler)

# Registrar eventos WebSocket de gamificação
if GAMIFICATION_V2_ENABLED:
    register_gamification_events(socketio)

# Registrar blueprint de gamificação (se existir)
if GAMIFICATION_V2_ENABLED:
    try:
        from gamification_api import gamification_bp
        app.register_blueprint(gamification_bp)
        logger.info("✅ API de Gamificação V2.0 registrada")
    except ImportError:
        logger.info("⚠️ gamification_api não encontrado (opcional)")

# User loader para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ==================== DECORATORS E HELPERS ====================

def admin_required(f):
    """Decorator para proteger rotas que requerem permissão de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar logado para acessar esta página.', 'error')
            return redirect(url_for('login'))
        
        if not current_user.is_admin:
            flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def log_admin_action(action, description, target_user_id=None, data_before=None, data_after=None):
    """Registra ação do admin no log de auditoria"""
    try:
        audit_log = AuditLog(
            admin_id=current_user.id,
            target_user_id=target_user_id,
            action=action,
            description=description,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            data_before=json.dumps(data_before) if data_before else None,
            data_after=json.dumps(data_after) if data_after else None
        )
        db.session.add(audit_log)
        db.session.commit()
        logger.info(f"🔒 ADMIN ACTION: {action} by {current_user.email} - {description}")
    except Exception as e:
        logger.error(f"❌ Erro ao registrar log de auditoria: {e}")
        db.session.rollback()

def get_user_ip():
    """Obtém o IP real do usuário (considerando proxies)"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def check_and_unlock_achievements(user):
    """Verifica e desbloqueia conquistas automaticamente"""
    from models import Achievement, UserAchievement, BotUser
    from sqlalchemy import func
    
    try:
        # Calcular estatísticas do usuário
        total_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == user.id,
            Payment.status == 'paid'
        ).scalar() or 0
        
        revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == user.id,
            Payment.status == 'paid'
        ).scalar() or 0.0
        
        total_bot_users = db.session.query(func.count(BotUser.id)).join(Bot).filter(
            Bot.user_id == user.id
        ).scalar() or 0
        
        conversion_rate = (total_sales / total_bot_users * 100) if total_bot_users > 0 else 0
        
        # Buscar conquistas desbloqueáveis
        all_achievements = Achievement.query.all()
        new_badges = []
        
        for achievement in all_achievements:
            # Verificar se já tem
            already_has = UserAchievement.query.filter_by(
                user_id=user.id,
                achievement_id=achievement.id
            ).first()
            
            if already_has:
                continue
            
            # Verificar se cumpre requisito
            unlocked = False
            
            if achievement.requirement_type == 'revenue':
                unlocked = revenue >= achievement.requirement_value
            elif achievement.requirement_type == 'sales':
                unlocked = total_sales >= achievement.requirement_value
            elif achievement.requirement_type == 'conversion':
                unlocked = conversion_rate >= achievement.requirement_value
            elif achievement.requirement_type == 'streak':
                unlocked = user.current_streak >= achievement.requirement_value
            
            if unlocked:
                # Desbloquear
                user_achievement = UserAchievement(
                    user_id=user.id,
                    achievement_id=achievement.id,
                    notified=False
                )
                db.session.add(user_achievement)
                new_badges.append(achievement)
                logger.info(f"🏆 BADGE DESBLOQUEADO: {achievement.name} para {user.email}")
        
        db.session.commit()
        return new_badges
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar conquistas: {e}")
        db.session.rollback()
        return []

# ==================== ROTAS DE AUTENTICAÇÃO ====================

@app.route('/')
def index():
    """Página inicial"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")  # ✅ PROTEÇÃO: Spam de registro
def register():
    """Registro de novo usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.form
        
        # Validações
        if not data.get('email') or not data.get('username') or not data.get('password'):
            flash('Preencha todos os campos obrigatórios!', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=data.get('email')).first():
            flash('Email já cadastrado!', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=data.get('username')).first():
            flash('Username já cadastrado!', 'error')
            return render_template('register.html')
        
        try:
            # Criar usuário
            user = User(
                email=data.get('email'),
                username=data.get('username'),
                full_name=data.get('full_name', '')
            )
            user.set_password(data.get('password'))
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"Novo usuário cadastrado: {user.email}")
            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar usuário: {e}")
            flash('Erro ao criar conta. Tente novamente.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # ✅ PROTEÇÃO: Brute-force login
def login():
    """Login de usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.form
        user = User.query.filter_by(email=data.get('email')).first()
        
        if user and user.check_password(data.get('password')):
            # Verificar se usuário está banido
            if user.is_banned:
                flash(f'Sua conta foi suspensa. Motivo: {user.ban_reason or "Violação dos termos de uso"}', 'error')
                return render_template('login.html')
            
            login_user(user, remember=data.get('remember') == 'on')
            user.last_login = datetime.now()
            user.last_ip = get_user_ip()
            db.session.commit()
            
            logger.info(f"Login bem-sucedido: {user.email}")
            
            # Redirecionar admin para painel admin
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        
        flash('Email ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Página de recuperação de senha"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # TODO: Implementar envio de email de recuperação
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Aqui você implementaria o envio do email
            logger.info(f"Recuperação de senha solicitada: {email}")
            flash('Se o email existir, você receberá as instruções em breve.', 'info')
        else:
            # Não revelar se o email existe ou não (segurança)
            flash('Se o email existir, você receberá as instruções em breve.', 'info')
        
        return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/logout')
@login_required
def logout():
    """Logout de usuário"""
    logger.info(f"Logout: {current_user.email}")
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('login'))

# ==================== DOCUMENTOS JURÍDICOS ====================

@app.route('/termos-de-uso')
def termos_de_uso():
    """Página de Termos de Uso"""
    return render_template('termos_de_uso.html')

@app.route('/politica-privacidade')
def politica_privacidade():
    """Página de Política de Privacidade"""
    return render_template('politica_privacidade.html')

# ==================== DASHBOARD ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com modo simples/avançado"""
    from sqlalchemy import func, case
    from models import BotUser
    
    # Query única otimizada para todas as estatísticas dos bots
    # ✅ CORREÇÃO: Usar os campos já calculados do modelo Bot ao invés de JOIN
    # Isso evita produto cartesiano quando há múltiplos BotUsers e Payments
    bot_stats = db.session.query(
        Bot.id,
        Bot.name,
        Bot.username,
        Bot.is_running,
        Bot.is_active,
        Bot.created_at,
        Bot.total_sales,  # ✅ Campo já calculado corretamente
        Bot.total_revenue,  # ✅ Campo já calculado corretamente
        func.count(func.distinct(BotUser.telegram_user_id)).label('total_users'),
        func.count(func.distinct(case((Payment.status == 'pending', Payment.id)))).label('pending_sales')
    ).outerjoin(BotUser, Bot.id == BotUser.bot_id)\
     .outerjoin(Payment, Bot.id == Payment.bot_id)\
     .filter(Bot.user_id == current_user.id)\
     .group_by(Bot.id, Bot.name, Bot.username, Bot.is_running, Bot.is_active, Bot.created_at, Bot.total_sales, Bot.total_revenue)\
     .order_by(Bot.created_at.desc())\
     .all()
    
    # Estatísticas gerais (calculadas a partir dos bot_stats)
    total_users = sum(b.total_users for b in bot_stats)
    total_sales = sum(b.total_sales for b in bot_stats)
    total_revenue = sum(float(b.total_revenue) for b in bot_stats)
    running_bots = sum(1 for b in bot_stats if b.is_running)
    
    stats = {
        'total_bots': len(bot_stats),
        'active_bots': sum(1 for b in bot_stats if b.is_active),
        'running_bots': running_bots,
        'total_users': total_users,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'pending_sales': sum(b.pending_sales for b in bot_stats),
        'can_add_bot': current_user.can_add_bot(),
        'commission_percentage': current_user.commission_percentage,
        'commission_balance': current_user.get_commission_balance(),
        'total_commission_owed': current_user.total_commission_owed,
        'total_commission_paid': current_user.total_commission_paid
    }
    
    # Últimos pagamentos (query otimizada com limit 20)
    recent_payments = db.session.query(Payment).join(Bot).filter(
        Bot.user_id == current_user.id
    ).order_by(Payment.id.desc()).limit(20).all()
    
    # Buscar configs de todos os bots de uma vez (otimizado)
    bot_ids = [b.id for b in bot_stats]
    configs_dict = {}
    if bot_ids:
        configs = db.session.query(BotConfig).filter(BotConfig.bot_id.in_(bot_ids)).all()
        configs_dict = {c.bot_id: c for c in configs}
    
    # Converter bot_stats para dicionários
    bots_list = []
    for b in bot_stats:
        bot_dict = {
            'id': b.id,
            'name': b.name,
            'username': b.username,
            'is_running': b.is_running,
            'is_active': b.is_active,
            'total_users': b.total_users,
            'total_sales': b.total_sales,
            'total_revenue': float(b.total_revenue),
            'pending_sales': b.pending_sales,
            'created_at': b.created_at.isoformat()
        }
        
        # Adicionar config se existir (busca no dicionário pré-carregado)
        config = configs_dict.get(b.id)
        if config:
            bot_dict['config'] = {
                'welcome_message': config.welcome_message or ''
            }
        else:
            bot_dict['config'] = None
        
        bots_list.append(bot_dict)
    
    # Converter payments para dicionários
    payments_list = [{
        'id': p.id,
        'customer_name': p.customer_name,
        'product_name': p.product_name,
        'amount': float(p.amount),
        'status': p.status,
        'created_at': p.created_at.isoformat()
    } for p in recent_payments]
    
    return render_template('dashboard.html', stats=stats, recent_payments=payments_list, bots=bots_list)


# ==================== API DE ESTATÍSTICAS ====================

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API para estatísticas em tempo real"""
    from sqlalchemy import func, case
    from models import BotUser
    
    # Query otimizada
    # ✅ CORREÇÃO: Usar campos calculados do modelo para evitar produto cartesiano
    bot_stats = db.session.query(
        Bot.id,
        Bot.name,
        Bot.is_running,
        Bot.total_sales,  # ✅ Campo já calculado
        Bot.total_revenue,  # ✅ Campo já calculado
        func.count(func.distinct(BotUser.telegram_user_id)).label('total_users'),
        func.count(func.distinct(case((Payment.status == 'pending', Payment.id)))).label('pending_sales')
    ).outerjoin(BotUser, Bot.id == BotUser.bot_id)\
     .outerjoin(Payment, Bot.id == Payment.bot_id)\
     .filter(Bot.user_id == current_user.id)\
     .group_by(Bot.id, Bot.name, Bot.is_running, Bot.total_sales, Bot.total_revenue)\
     .all()
    
    return jsonify({
        'total_users': sum(b.total_users for b in bot_stats),
        'total_sales': sum(b.total_sales for b in bot_stats),
        'total_revenue': float(sum(b.total_revenue for b in bot_stats)),
        'pending_sales': sum(b.pending_sales for b in bot_stats),
        'running_bots': sum(1 for b in bot_stats if b.is_running),
        'bots': [{
            'id': b.id,
            'name': b.name,
            'is_running': b.is_running,
            'total_users': b.total_users,
            'total_sales': b.total_sales,
            'total_revenue': float(b.total_revenue),
            'pending_sales': b.pending_sales
        } for b in bot_stats]
    })

@app.route('/api/dashboard/sales-chart')
@login_required
def api_sales_chart():
    """API para dados do gráfico de vendas (últimos 7 dias)"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Últimos 7 dias
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    # Query para vendas por dia
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).join(Bot).filter(
        Bot.user_id == current_user.id,
        Payment.created_at >= seven_days_ago,
        Payment.status == 'paid'
    ).group_by(func.date(Payment.created_at))\
     .order_by(func.date(Payment.created_at))\
     .all()
    
    # Preencher dias sem vendas
    result = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).date()
        day_data = next((s for s in sales_by_day if str(s.date) == str(date)), None)
        result.append({
            'date': date.strftime('%d/%m'),
            'sales': day_data.sales if day_data else 0,
            'revenue': float(day_data.revenue) if day_data else 0.0
        })
    
    return jsonify(result)

@app.route('/api/dashboard/analytics')
@login_required
def api_dashboard_analytics():
    """API para métricas avançadas e analytics"""
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    from models import BotUser, Commission
    
    # IDs dos bots do usuário
    user_bot_ids = [bot.id for bot in current_user.bots]
    
    if not user_bot_ids:
        return jsonify({
            'conversion_rate': 0,
            'avg_ticket': 0,
            'order_bump_stats': {},
            'downsell_stats': {},
            'peak_hours': [],
            'commission_data': {}
        })
    
    # 1. TAXA DE CONVERSÃO (cliques vs compras)
    total_clicks = BotUser.query.filter(BotUser.bot_id.in_(user_bot_ids)).count()
    total_purchases = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).count()
    conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
    
    # 2. TICKET MÉDIO
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).scalar() or 0.0
    avg_ticket = (total_revenue / total_purchases) if total_purchases > 0 else 0
    
    # 2.1. VENDAS HOJE
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).count()
    
    # 3. PERFORMANCE DE ORDER BUMPS
    order_bump_shown_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_shown == True
    ).count()
    
    order_bump_accepted_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_accepted == True
    ).count()
    
    order_bump_revenue = db.session.query(func.sum(Payment.order_bump_value)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_accepted == True,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    order_bump_acceptance_rate = (order_bump_accepted_count / order_bump_shown_count * 100) if order_bump_shown_count > 0 else 0
    
    # 4. PERFORMANCE DE DOWNSELLS
    downsell_sent_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True
    ).count()
    
    downsell_paid_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True,
        Payment.status == 'paid'
    ).count()
    
    downsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    downsell_conversion_rate = (downsell_paid_count / downsell_sent_count * 100) if downsell_sent_count > 0 else 0
    
    # 5. HORÁRIOS DE PICO (vendas por hora)
    peak_hours_data = db.session.query(
        extract('hour', Payment.created_at).label('hour'),
        func.count(Payment.id).label('sales')
    ).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).group_by(extract('hour', Payment.created_at))\
     .order_by(func.count(Payment.id).desc())\
     .limit(5)\
     .all()
    
    peak_hours = [{
        'hour': f"{int(h.hour):02d}:00",
        'sales': h.sales
    } for h in peak_hours_data]
    
    # 6. COMISSÕES
    total_commission_owed = current_user.total_commission_owed
    total_commission_paid = current_user.total_commission_paid
    commission_balance = current_user.get_commission_balance()
    commission_percentage = current_user.commission_percentage
    
    # Últimas comissões
    recent_commissions = Commission.query.filter_by(
        user_id=current_user.id
    ).order_by(Commission.created_at.desc()).limit(5).all()
    
    return jsonify({
        'conversion_rate': round(conversion_rate, 2),
        'avg_ticket': round(float(avg_ticket), 2),
        'today_sales': today_sales,
        'order_bump_stats': {
            'shown': order_bump_shown_count,
            'accepted': order_bump_accepted_count,
            'acceptance_rate': round(order_bump_acceptance_rate, 2),
            'total_revenue': round(float(order_bump_revenue), 2)
        },
        'downsell_stats': {
            'sent': downsell_sent_count,
            'converted': downsell_paid_count,
            'conversion_rate': round(downsell_conversion_rate, 2),
            'total_revenue': round(float(downsell_revenue), 2)
        },
        'peak_hours': peak_hours
    })

# ==================== GERENCIAMENTO DE BOTS ====================

@app.route('/api/bots', methods=['GET'])
@login_required
def get_bots():
    """Lista todos os bots do usuário"""
    bots = current_user.bots.all()
    bots_data = []
    for bot in bots:
        bot_dict = bot.to_dict()
        # Incluir dados da configuração para verificar se está configurado
        if bot.config:
            bot_dict['config'] = {
                'welcome_message': bot.config.welcome_message,
                'has_welcome_message': bool(bot.config.welcome_message)
            }
        else:
            bot_dict['config'] = None
        bots_data.append(bot_dict)
    return jsonify(bots_data)

@app.route('/bot/create')
@login_required
def bot_create_page():
    """Página de criação de bot com wizard"""
    return render_template('bot_create_wizard.html')

@app.route('/api/bots', methods=['POST'])
@login_required
@csrf.exempt
def create_bot():
    """Cria novo bot (API endpoint)"""
    if not current_user.can_add_bot():
        return jsonify({'error': 'Limite de bots atingido! Faça upgrade do seu plano.'}), 403
    
    data = request.json
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    
    # Verificar se token já existe
    if Bot.query.filter_by(token=token).first():
        return jsonify({'error': 'Bot já cadastrado no sistema'}), 400
    
    try:
        # Validar token com a API do Telegram
        bot_info = bot_manager.validate_token(token)
        
        # Criar bot
        bot = Bot(
            user_id=current_user.id,
            token=token,
            name=data.get('name', bot_info.get('first_name', 'Meu Bot')),
            username=bot_info.get('username'),
            bot_id=str(bot_info.get('id'))
        )
        
        db.session.add(bot)
        db.session.commit()
        
        # Criar configuração padrão
        config = BotConfig(bot_id=bot.id)
        db.session.add(config)
        db.session.commit()
        
        logger.info(f"Bot criado: {bot.name} (@{bot.username}) por {current_user.email}")
        return jsonify(bot.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar bot: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/bots/<int:bot_id>', methods=['GET'])
@login_required
def get_bot(bot_id):
    """Obtém detalhes de um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return jsonify(bot.to_dict())

@app.route('/api/bots/<int:bot_id>/token', methods=['PUT'])
@login_required
@csrf.exempt
def update_bot_token(bot_id):
    """
    Atualiza o token de um bot (V2 - AUTO-STOP)
    
    FUNCIONALIDADES:
    ✅ Para automaticamente o bot se estiver rodando (limpa cache)
    ✅ Valida novo token com Telegram API
    ✅ Atualiza bot_id, username e nome automaticamente
    ✅ Reseta status para offline
    ✅ Limpa erros antigos
    ✅ Mantém TODAS as configurações (BotConfig, pagamentos, usuários, stats)
    
    VALIDAÇÕES:
    - Token novo obrigatório
    - Token diferente do atual
    - Token único no sistema
    - Token válido no Telegram
    """
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    new_token = data.get('token', '').strip()
    
    # VALIDAÇÃO 1: Token obrigatório
    if not new_token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    
    # VALIDAÇÃO 2: Token diferente do atual
    if new_token == bot.token:
        return jsonify({'error': 'Este token já está em uso neste bot'}), 400
    
    # VALIDAÇÃO 3: Token único no sistema (exceto o bot atual)
    existing_bot = Bot.query.filter(Bot.token == new_token, Bot.id != bot_id).first()
    if existing_bot:
        return jsonify({'error': 'Este token já está cadastrado em outro bot'}), 400
    
    try:
        # ✅ AUTO-STOP: Parar bot se estiver rodando (limpeza completa do cache)
        was_running = bot.is_running
        if was_running:
            logger.info(f"🛑 Auto-stop: Parando bot {bot_id} antes de trocar token...")
            try:
                bot_manager.stop_bot(bot_id)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao parar bot (pode já estar parado): {e}")
            
            # Força atualização no banco
            bot.is_running = False
            bot.last_stopped = datetime.now()
            db.session.commit()
            logger.info(f"✅ Bot {bot_id} parado e cache limpo")
        
        # VALIDAÇÃO 4: Token válido no Telegram
        bot_info = bot_manager.validate_token(new_token)
        
        # Armazenar dados antigos para log
        old_token_preview = bot.token[:10] + '...'
        old_username = bot.username
        old_bot_id = bot.bot_id
        
        # ✅ ATUALIZAR BOT (mantém todas as configurações)
        bot.token = new_token
        bot.username = bot_info.get('username')
        bot.name = bot_info.get('first_name', bot.name)  # Atualiza nome também
        bot.bot_id = str(bot_info.get('id'))
        bot.is_running = False  # ✅ Garantir que está offline
        bot.last_error = None  # Limpar erros antigos
        
        # ✅ ARQUIVAR USUÁRIOS DO TOKEN ANTIGO
        from models import BotUser
        archived_count = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
        if archived_count > 0:
            BotUser.query.filter_by(bot_id=bot_id, archived=False).update({
                'archived': True,
                'archived_reason': 'token_changed',
                'archived_at': datetime.now()
            })
            logger.info(f"📦 {archived_count} usuários do token antigo arquivados")
        
        # ✅ RESETAR CONTADOR DE USUÁRIOS
        bot.total_users = 0
        logger.info(f"🔄 Contador total_users resetado para 0")
        
        db.session.commit()
        
        logger.info(f"✅ Token atualizado: Bot {bot.name} | @{old_username} → @{bot.username} | ID {old_bot_id} → {bot.bot_id} | por {current_user.email}")
        
        return jsonify({
            'message': f'Token atualizado! {archived_count} usuários antigos arquivados. Contador resetado.' if archived_count > 0 else 'Token atualizado com sucesso!',
            'bot': bot.to_dict(),
            'changes': {
                'old_username': old_username,
                'new_username': bot.username,
                'old_bot_id': old_bot_id,
                'new_bot_id': bot.bot_id,
                'users_archived': archived_count,
                'was_auto_stopped': was_running,
                'cache_cleared': was_running,
                'configurations_preserved': True,
                'can_start': True
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar token do bot {bot_id}: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/bots/<int:bot_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_bot(bot_id):
    """Deleta um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Parar bot se estiver rodando
    if bot.is_running:
        bot_manager.stop_bot(bot.id)
    
    bot_name = bot.name
    db.session.delete(bot)
    db.session.commit()
    
    logger.info(f"Bot deletado: {bot_name} por {current_user.email}")
    return jsonify({'message': 'Bot deletado com sucesso'})

@app.route('/api/bots/<int:bot_id>/duplicate', methods=['POST'])
@login_required
@csrf.exempt
def duplicate_bot(bot_id):
    """
    Duplica um bot com todas as configurações
    
    REQUISITOS:
    - Token novo obrigatório
    - Validação do token com Telegram
    - Verificação de token único
    - Copia todo o fluxo (mensagens, Order Bumps, Downsells, Remarketing)
    """
    bot_original = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    new_token = data.get('token', '').strip()
    new_name = data.get('name', '').strip()
    
    # VALIDAÇÃO 1: Token obrigatório
    if not new_token:
        return jsonify({'error': 'Token do novo bot é obrigatório'}), 400
    
    # VALIDAÇÃO 2: Token diferente do original
    if new_token == bot_original.token:
        return jsonify({'error': 'O novo token deve ser diferente do bot original'}), 400
    
    # VALIDAÇÃO 3: Token único no sistema
    if Bot.query.filter_by(token=new_token).first():
        return jsonify({'error': 'Este token já está cadastrado no sistema'}), 400
    
    try:
        # VALIDAÇÃO 4: Token válido no Telegram
        bot_info = bot_manager.validate_token(new_token)
        
        # Criar nome automático se não fornecido
        if not new_name:
            new_name = f"{bot_original.name} (Cópia)"
        
        # CRIAR NOVO BOT
        new_bot = Bot(
            user_id=current_user.id,
            token=new_token,
            name=new_name,
            username=bot_info.get('username'),
            bot_id=str(bot_info.get('id')),
            is_active=True,
            is_running=False  # Não iniciar automaticamente
        )
        
        db.session.add(new_bot)
        db.session.flush()  # Garante que new_bot.id esteja disponível
        
        # DUPLICAR CONFIGURAÇÕES
        if bot_original.config:
            config_original = bot_original.config
            
            new_config = BotConfig(
                bot_id=new_bot.id,
                welcome_message=config_original.welcome_message,
                welcome_media_url=config_original.welcome_media_url,
                welcome_media_type=config_original.welcome_media_type,
                main_buttons=config_original.main_buttons,  # JSON com Order Bumps
                downsells=config_original.downsells,  # JSON
                downsells_enabled=config_original.downsells_enabled,
                access_link=config_original.access_link
            )
            
            db.session.add(new_config)
        else:
            # Criar config padrão se original não tiver
            new_config = BotConfig(bot_id=new_bot.id)
            db.session.add(new_config)
        
        db.session.commit()
        
        logger.info(f"Bot duplicado: {bot_original.name} → {new_bot.name} (@{new_bot.username}) por {current_user.email}")
        
        return jsonify({
            'message': 'Bot duplicado com sucesso!',
            'bot': new_bot.to_dict(),
            'copied_features': {
                'welcome_message': bool(bot_original.config and bot_original.config.welcome_message),
                'welcome_media': bool(bot_original.config and bot_original.config.welcome_media_url),
                'main_buttons': len(bot_original.config.get_main_buttons()) if bot_original.config else 0,
                'order_bumps': sum(1 for btn in (bot_original.config.get_main_buttons() if bot_original.config else []) 
                                  if btn.get('order_bump', {}).get('enabled')),
                'downsells': len(bot_original.config.get_downsells()) if bot_original.config else 0,
                'access_link': bool(bot_original.config and bot_original.config.access_link)
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao duplicar bot {bot_id}: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/bots/<int:bot_id>/start', methods=['POST'])
@login_required
@csrf.exempt
def start_bot(bot_id):
    """Inicia um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Verificar se tem gateway configurado
    if not current_user.gateways.filter_by(is_active=True, is_verified=True).first():
        return jsonify({'error': 'Configure um gateway de pagamento verificado primeiro'}), 400
    
    # Verificar se tem configuração
    if not bot.config or not bot.config.welcome_message:
        return jsonify({'error': 'Configure a mensagem de boas-vindas antes de iniciar'}), 400
    
    try:
        bot_manager.start_bot(bot.id, bot.token, bot.config.to_dict())
        bot.is_running = True
        bot.last_started = datetime.now()
        db.session.commit()
        
        logger.info(f"Bot iniciado: {bot.name} por {current_user.email}")
        
        # Notificar via WebSocket
        socketio.emit('bot_status_update', {
            'bot_id': bot.id,
            'is_running': True
        }, room=f'user_{current_user.id}')
        
        return jsonify({'message': 'Bot iniciado com sucesso'})
    except Exception as e:
        logger.error(f"Erro ao iniciar bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bots/<int:bot_id>/stop', methods=['POST'])
@login_required
@csrf.exempt
def stop_bot(bot_id):
    """Para um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        bot_manager.stop_bot(bot.id)
        bot.is_running = False
        bot.last_stopped = datetime.now()
        db.session.commit()
        
        logger.info(f"Bot parado: {bot.name} por {current_user.email}")
        
        # Notificar via WebSocket
        socketio.emit('bot_status_update', {
            'bot_id': bot.id,
            'is_running': False
        }, room=f'user_{current_user.id}')
        
        return jsonify({'message': 'Bot parado com sucesso'})
    except Exception as e:
        logger.error(f"Erro ao parar bot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bots/<int:bot_id>/debug', methods=['GET'])
@login_required
def debug_bot(bot_id):
    """Debug do status do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    import threading
    
    debug_info = {
        'bot_id': bot.id,
        'is_running_db': bot.is_running,
        'is_in_active_bots': bot.id in bot_manager.active_bots,
        'active_bots_count': len(bot_manager.active_bots),
        'active_threads': threading.active_count(),
        'thread_names': [t.name for t in threading.enumerate()],
    }
    
    if bot.id in bot_manager.active_bots:
        debug_info['bot_status'] = bot_manager.active_bots[bot.id]['status']
        debug_info['bot_started_at'] = bot_manager.active_bots[bot.id]['started_at'].isoformat()
    
    return jsonify(debug_info)

# ==================== REMARKETING ====================

@app.route('/bots/<int:bot_id>/remarketing')
@login_required
def bot_remarketing_page(bot_id):
    """Página de remarketing do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    
    # Converter para dicionários (serializável)
    campaigns_list = [c.to_dict() for c in campaigns]
    
    return render_template('bot_remarketing.html', bot=bot, campaigns=campaigns_list)

@app.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['GET'])
@login_required
def get_remarketing_campaigns(bot_id):
    """Lista campanhas de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(
        RemarketingCampaign.created_at.desc()
    ).all()
    return jsonify([c.to_dict() for c in campaigns])

@app.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['POST'])
@login_required
@csrf.exempt
def create_remarketing_campaign(bot_id):
    """Cria nova campanha de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.json
    from models import RemarketingCampaign
    
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
        cooldown_hours=data.get('cooldown_hours', 24)
    )
    
    db.session.add(campaign)
    db.session.commit()
    
    logger.info(f"📢 Campanha de remarketing criada: {campaign.name} (Bot {bot.name})")
    
    return jsonify(campaign.to_dict()), 201

@app.route('/api/bots/<int:bot_id>/remarketing/campaigns/<int:campaign_id>/send', methods=['POST'])
@login_required
@csrf.exempt
def send_remarketing_campaign(bot_id, campaign_id):
    """Envia campanha de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    from models import RemarketingCampaign
    
    campaign = RemarketingCampaign.query.filter_by(id=campaign_id, bot_id=bot_id).first_or_404()
    
    if campaign.status == 'sending':
        return jsonify({'error': 'Campanha já está sendo enviada'}), 400
    
    # Iniciar envio em background (usar instância global)
    bot_manager.send_remarketing_campaign(campaign_id, bot.token)
    
    return jsonify({'message': 'Envio iniciado', 'campaign': campaign.to_dict()})

@app.route('/api/bots/<int:bot_id>/remarketing/eligible-leads', methods=['POST'])
@login_required
@csrf.exempt
def count_eligible_leads(bot_id):
    """Conta quantos leads são elegíveis para remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.json
    
    # Usar a instância global do bot_manager
    count = bot_manager.count_eligible_leads(
        bot_id=bot_id,
        target_audience=data.get('target_audience', 'non_buyers'),
        days_since_last_contact=data.get('days_since_last_contact', 3),
        exclude_buyers=data.get('exclude_buyers', True)
    )
    
    return jsonify({'count': count})

@app.route('/api/remarketing/general', methods=['POST'])
@login_required
@csrf.exempt
def general_remarketing():
    """
    API: Remarketing Geral (Multi-Bot)
    Envia uma campanha de remarketing para múltiplos bots simultaneamente
    """
    try:
        data = request.json
        
        # Validações
        bot_ids = data.get('bot_ids', [])
        message = data.get('message', '').strip()
        
        if not bot_ids or len(bot_ids) == 0:
            return jsonify({'error': 'Selecione pelo menos 1 bot'}), 400
        
        if not message:
            return jsonify({'error': 'Mensagem é obrigatória'}), 400
        
        # Verificar se todos os bots pertencem ao usuário
        bots = Bot.query.filter(
            Bot.id.in_(bot_ids),
            Bot.user_id == current_user.id
        ).all()
        
        if len(bots) != len(bot_ids):
            return jsonify({'error': 'Um ou mais bots não pertencem a você'}), 403
        
        # Parâmetros da campanha
        media_url = data.get('media_url')
        media_type = data.get('media_type', 'video')
        audio_enabled = data.get('audio_enabled', False)
        audio_url = data.get('audio_url', '')
        buttons = data.get('buttons', [])
        days_since_last_contact = int(data.get('days_since_last_contact', 7))
        exclude_buyers = data.get('exclude_buyers', False)
        
        # Validar botões (se fornecidos)
        if buttons:
            for btn in buttons:
                if not btn.get('text') or not btn.get('price'):
                    return jsonify({'error': 'Todos os botões precisam ter texto e preço'}), 400
        
        # Converter botões para JSON
        buttons_json = json.dumps(buttons) if buttons else None
        
        # Contador de usuários impactados
        total_users = 0
        bots_affected = 0
        
        # Criar campanha para cada bot
        for bot in bots:
            # Contar usuários elegíveis
            eligible_count = bot_manager.count_eligible_leads(
                bot_id=bot.id,
                target_audience='non_buyers' if exclude_buyers else 'all',
                days_since_last_contact=days_since_last_contact,
                exclude_buyers=exclude_buyers
            )
            
            if eligible_count > 0:
                # Criar campanha no banco
                from models import RemarketingCampaign
                
                campaign = RemarketingCampaign(
                    bot_id=bot.id,
                    name=f"Remarketing Geral - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    message=message,
                    media_url=media_url,
                    media_type=media_type,
                    audio_enabled=audio_enabled,
                    audio_url=audio_url,
                    buttons=buttons_json,
                    target_audience='non_buyers' if exclude_buyers else 'all',
                    days_since_last_contact=days_since_last_contact,
                    exclude_buyers=exclude_buyers,
                    cooldown_hours=6,  # Fixo em 6 horas
                    status='active'
                )
                
                db.session.add(campaign)
                db.session.commit()
                
                # Enviar campanha via bot_manager
                try:
                    bot_manager.send_remarketing_campaign(
                        campaign_id=campaign.id,
                        bot_token=bot.token
                    )
                    
                    total_users += eligible_count
                    bots_affected += 1
                    
                    logger.info(f"✅ Remarketing geral enviado para bot {bot.name} ({eligible_count} usuários)")
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar remarketing para bot {bot.id}: {e}")
        
        return jsonify({
            'success': True,
            'total_users': total_users,
            'bots_affected': bots_affected,
            'message': f'Remarketing enviado para {bots_affected} bot(s) com sucesso!'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no remarketing geral: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/remarketing/<int:bot_id>/stats', methods=['GET'])
@login_required
def get_remarketing_stats(bot_id):
    """
    API: Estatísticas gerais de remarketing por bot
    Retorna métricas agregadas de todas as campanhas
    """
    try:
        from models import RemarketingCampaign
        
        # Verificar se o bot pertence ao usuário
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        # Buscar todas as campanhas do bot
        campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).all()
        
        # Calcular métricas agregadas
        total_campaigns = len(campaigns)
        total_sent = sum(c.total_sent for c in campaigns)
        total_clicks = sum(c.total_clicks for c in campaigns)
        total_failed = sum(c.total_failed for c in campaigns)
        total_blocked = sum(c.total_blocked for c in campaigns)
        total_revenue = sum(c.revenue_generated or 0 for c in campaigns)
        
        # Taxas
        delivery_rate = (total_sent / sum(c.total_targets for c in campaigns) * 100) if sum(c.total_targets for c in campaigns) > 0 else 0
        click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
        
        return jsonify({
            'total_campaigns': total_campaigns,
            'total_sent': total_sent,
            'total_clicks': total_clicks,
            'total_failed': total_failed,
            'total_blocked': total_blocked,
            'total_revenue': float(total_revenue),
            'delivery_rate': round(delivery_rate, 2),
            'click_rate': round(click_rate, 2)
        })
    except Exception as e:
        logger.error(f"❌ Erro ao buscar stats de remarketing: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/remarketing/<int:bot_id>/timeline', methods=['GET'])
@login_required
def get_remarketing_timeline(bot_id):
    """
    API: Timeline de performance de remarketing
    Retorna dados diários dos últimos 30 dias
    """
    try:
        from models import RemarketingCampaign
        from datetime import date, timedelta
        from sqlalchemy import func
        
        # Verificar se o bot pertence ao usuário
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        # Últimos 30 dias
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Buscar campanhas concluídas no período
        campaigns = RemarketingCampaign.query.filter(
            RemarketingCampaign.bot_id == bot_id,
            RemarketingCampaign.completed_at.isnot(None),
            func.date(RemarketingCampaign.completed_at) >= start_date
        ).order_by(RemarketingCampaign.completed_at).all()
        
        # Agrupar por data
        timeline = {}
        for campaign in campaigns:
            date_key = campaign.completed_at.strftime('%Y-%m-%d')
            if date_key not in timeline:
                timeline[date_key] = {'date': campaign.completed_at.strftime('%d/%m'), 'sent': 0, 'clicks': 0}
            
            timeline[date_key]['sent'] += campaign.total_sent
            timeline[date_key]['clicks'] += campaign.total_clicks
        
        # Converter para lista ordenada
        timeline_list = [v for k, v in sorted(timeline.items())]
        
        return jsonify(timeline_list)
    except Exception as e:
        logger.error(f"❌ Erro ao buscar timeline de remarketing: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ==================== PAINEL DE ADMINISTRAÇÃO ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Dashboard principal do admin"""
    from sqlalchemy import func
    from models import BotUser
    from datetime import timedelta
    
    # Métricas globais
    total_users = User.query.filter_by(is_admin=False).count()
    active_users = User.query.filter_by(is_active=True, is_admin=False, is_banned=False).count()
    banned_users = User.query.filter_by(is_banned=True).count()
    
    total_bots = Bot.query.count()
    running_bots = Bot.query.filter_by(is_running=True).count()
    
    total_bot_users = BotUser.query.count()
    total_payments = Payment.query.count()
    paid_payments = Payment.query.filter_by(status='paid').count()
    
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # Receita da plataforma (via split payment)
    from models import Commission
    platform_revenue_total = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid'
    ).scalar() or 0.0
    
    platform_revenue_month = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid',
        Commission.created_at >= datetime.now() - timedelta(days=30)
    ).scalar() or 0.0
    
    # Novos usuários (últimos 30 dias)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    new_users = User.query.filter(User.created_at >= thirty_days_ago).count()
    
    # Top 10 usuários por receita
    top_users = db.session.query(
        User,
        func.sum(Payment.amount).label('revenue')
    ).join(Bot, Bot.user_id == User.id)\
     .join(Payment, Payment.bot_id == Bot.id)\
     .filter(Payment.status == 'paid')\
     .group_by(User.id)\
     .order_by(func.sum(Payment.amount).desc())\
     .limit(10)\
     .all()
    
    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'banned_users': banned_users,
        'new_users_30d': new_users,
        'total_bots': total_bots,
        'running_bots': running_bots,
        'total_bot_users': total_bot_users,
        'total_payments': total_payments,
        'paid_payments': paid_payments,
        'total_revenue': float(total_revenue),
        'platform_revenue_total': float(platform_revenue_total),
        'platform_revenue_month': float(platform_revenue_month)
    }
    
    top_users_list = [{
        'user': u.User,
        'revenue': float(u.revenue)
    } for u in top_users]
    
    log_admin_action('view_dashboard', 'Acessou dashboard admin')
    
    return render_template('admin/dashboard.html', stats=stats, top_users=top_users_list)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Página de gerenciamento de usuários"""
    from sqlalchemy import func
    
    # Filtros
    status_filter = request.args.get('status', 'all')  # all, active, banned, inactive
    search = request.args.get('search', '')
    
    # Query base
    query = User.query.filter_by(is_admin=False)
    
    # Aplicar filtros
    if status_filter == 'active':
        query = query.filter_by(is_active=True, is_banned=False)
    elif status_filter == 'banned':
        query = query.filter_by(is_banned=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    if search:
        query = query.filter(
            (User.email.like(f'%{search}%')) |
            (User.username.like(f'%{search}%')) |
            (User.full_name.like(f'%{search}%'))
        )
    
    # Adicionar contagens de bots e vendas
    users = query.order_by(User.created_at.desc()).all()
    
    # Enriquecer dados dos usuários
    users_data = []
    for user in users:
        bots_count = Bot.query.filter_by(user_id=user.id).count()
        sales_count = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == user.id, Payment.status == 'paid'
        ).scalar() or 0
        revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == user.id, Payment.status == 'paid'
        ).scalar() or 0.0
        
        users_data.append({
            'user': user,
            'bots_count': bots_count,
            'sales_count': sales_count,
            'revenue': float(revenue)
        })
    
    log_admin_action('view_users', f'Visualizou lista de usuários (filtro: {status_filter})')
    
    return render_template('admin/users.html', users=users_data, status_filter=status_filter, search=search)

@app.route('/admin/users/<int:user_id>')
@login_required
@admin_required
def admin_user_detail(user_id):
    """Perfil detalhado 360° do usuário"""
    from sqlalchemy import func
    from models import BotUser, RemarketingCampaign
    
    user = User.query.get_or_404(user_id)
    
    # Bots do usuário (com configurações completas)
    bots = Bot.query.filter_by(user_id=user_id).all()
    bots_data = []
    
    for bot in bots:
        # Stats do bot
        bot_users = BotUser.query.filter_by(bot_id=bot.id).count()
        sales = Payment.query.filter_by(bot_id=bot.id, status='paid').count()
        revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot.id, Payment.status == 'paid'
        ).scalar() or 0.0
        
        # Configurações
        config = bot.config
        remarketing_count = RemarketingCampaign.query.filter_by(bot_id=bot.id).count()
        
        bots_data.append({
            'bot': bot,
            'users': bot_users,
            'sales': sales,
            'revenue': float(revenue),
            'config': config,
            'remarketing_campaigns': remarketing_count
        })
    
    # Gateways
    gateways = Gateway.query.filter_by(user_id=user_id).all()
    
    # Últimas vendas
    recent_sales = db.session.query(Payment).join(Bot).filter(
        Bot.user_id == user_id
    ).order_by(Payment.id.desc()).limit(20).all()
    
    # Últimos logins (últimos 10 audit logs de login)
    login_logs = AuditLog.query.filter_by(
        target_user_id=user_id,
        action='login'
    ).order_by(AuditLog.created_at.desc()).limit(10).all()
    
    # Stats financeiros
    financial_stats = {
        'total_revenue': float(db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == user_id, Payment.status == 'paid'
        ).scalar() or 0.0),
        'total_sales': db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == user_id, Payment.status == 'paid'
        ).scalar() or 0,
        'commission_paid': user.total_commission_paid  # Split payment - sempre pago automaticamente
    }
    
    log_admin_action('view_user_detail', f'Visualizou perfil completo do usuário {user.email}', target_user_id=user_id)
    
    return render_template('admin/user_detail.html', 
                         user=user, 
                         bots=bots_data, 
                         gateways=gateways,
                         recent_sales=recent_sales,
                         login_logs=login_logs,
                         financial_stats=financial_stats)

@app.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def admin_ban_user(user_id):
    """Banir usuário"""
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        return jsonify({'error': 'Não é possível banir um administrador'}), 403
    
    data = request.json
    reason = data.get('reason', 'Violação dos termos de uso')
    
    # Salvar estado anterior
    data_before = {'is_banned': user.is_banned, 'ban_reason': user.ban_reason}
    
    # Banir usuário
    user.is_banned = True
    user.ban_reason = reason
    user.banned_at = datetime.now()
    
    # Parar todos os bots do usuário
    for bot in user.bots:
        if bot.is_running:
            bot_manager.stop_bot(bot.id)
    
    db.session.commit()
    
    # Registrar no log
    log_admin_action('ban_user', f'Baniu usuário {user.email}. Motivo: {reason}', 
                    target_user_id=user_id,
                    data_before=data_before,
                    data_after={'is_banned': True, 'ban_reason': reason})
    
    return jsonify({'message': f'Usuário {user.email} banido com sucesso'})

@app.route('/admin/users/<int:user_id>/unban', methods=['POST'])
@login_required
@admin_required
def admin_unban_user(user_id):
    """Desbanir usuário"""
    user = User.query.get_or_404(user_id)
    
    data_before = {'is_banned': user.is_banned, 'ban_reason': user.ban_reason}
    
    user.is_banned = False
    user.ban_reason = None
    user.banned_at = None
    db.session.commit()
    
    log_admin_action('unban_user', f'Desbaniu usuário {user.email}', 
                    target_user_id=user_id,
                    data_before=data_before,
                    data_after={'is_banned': False})
    
    return jsonify({'message': f'Usuário {user.email} desbanido com sucesso'})

@app.route('/admin/users/<int:user_id>/edit', methods=['PUT'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Editar informações do usuário"""
    user = User.query.get_or_404(user_id)
    data = request.json
    
    data_before = {
        'full_name': user.full_name,
        'phone': user.phone,
        'cpf_cnpj': user.cpf_cnpj,
        'is_active': user.is_active
    }
    
    # Atualizar campos permitidos
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'cpf_cnpj' in data:
        user.cpf_cnpj = data['cpf_cnpj']
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    db.session.commit()
    
    data_after = {
        'full_name': user.full_name,
        'phone': user.phone,
        'cpf_cnpj': user.cpf_cnpj,
        'is_active': user.is_active
    }
    
    log_admin_action('edit_user', f'Editou dados do usuário {user.email}', 
                    target_user_id=user_id,
                    data_before=data_before,
                    data_after=data_after)
    
    return jsonify({'message': 'Usuário atualizado com sucesso', 'user': user.to_dict()})

@app.route('/admin/users/<int:user_id>/impersonate', methods=['POST'])
@login_required
@admin_required
def admin_impersonate(user_id):
    """Logar como outro usuário (impersonate)"""
    target_user = User.query.get_or_404(user_id)
    
    if target_user.is_admin:
        return jsonify({'error': 'Não é possível impersonar outro administrador'}), 403
    
    # Salvar ID do admin original na sessão
    session['impersonate_admin_id'] = current_user.id
    session['impersonate_admin_email'] = current_user.email
    
    # Fazer logout do admin e login como usuário
    logout_user()
    login_user(target_user)
    
    log_admin_action('impersonate', f'Admin logou como usuário {target_user.email}', target_user_id=user_id)
    
    flash(f'Você está logado como {target_user.email}. Clique em "Voltar ao Admin" para retornar.', 'warning')
    
    return jsonify({'message': 'Impersonate ativado', 'redirect': '/dashboard'})

@app.route('/admin/stop-impersonate')
@login_required
def admin_stop_impersonate():
    """Parar impersonate e voltar ao admin original"""
    if 'impersonate_admin_id' not in session:
        flash('Você não está em modo impersonate.', 'error')
        return redirect(url_for('dashboard'))
    
    admin_id = session.pop('impersonate_admin_id')
    admin_email = session.pop('impersonate_admin_email', None)
    
    # Voltar ao admin
    admin_user = db.session.get(User, admin_id)
    if admin_user:
        logout_user()
        login_user(admin_user)
        flash(f'Voltou ao modo administrador.', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return redirect(url_for('login'))

@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    """Página de logs de auditoria"""
    # Filtros
    action_filter = request.args.get('action', 'all')
    admin_filter = request.args.get('admin', 'all')
    limit = int(request.args.get('limit', 100))
    
    # Query base
    query = AuditLog.query
    
    # Aplicar filtros
    if action_filter != 'all':
        query = query.filter_by(action=action_filter)
    
    if admin_filter != 'all':
        query = query.filter_by(admin_id=int(admin_filter))
    
    # Buscar logs
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    # Lista de admins para filtro
    admins = User.query.filter_by(is_admin=True).all()
    
    # Lista de ações únicas
    actions = db.session.query(AuditLog.action).distinct().all()
    actions_list = [a[0] for a in actions]
    
    return render_template('admin/logs.html', 
                         logs=logs, 
                         admins=admins,
                         actions=actions_list,
                         action_filter=action_filter,
                         admin_filter=admin_filter,
                         limit=limit)

@app.route('/admin/revenue')
@login_required
@admin_required
def admin_revenue():
    """Página de receita da plataforma (via split payment)"""
    from sqlalchemy import func
    from models import Commission
    from datetime import timedelta
    
    # Receita total da plataforma (via split payment - sempre "paid")
    total_revenue = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid'
    ).scalar() or 0.0
    
    # Receita por período
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    revenue_today = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid',
        Commission.created_at >= today
    ).scalar() or 0.0
    
    revenue_week = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid',
        Commission.created_at >= today - timedelta(days=7)
    ).scalar() or 0.0
    
    revenue_month = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.status == 'paid',
        Commission.created_at >= today - timedelta(days=30)
    ).scalar() or 0.0
    
    # Total de transações
    total_transactions = Commission.query.filter_by(status='paid').count()
    
    # Receita por usuário (últimos 30 dias)
    revenue_by_user = db.session.query(
        User,
        func.count(Commission.id).label('total_transactions'),
        func.sum(Commission.commission_amount).label('platform_revenue'),
        func.sum(Commission.sale_amount).label('user_revenue')
    ).join(Commission, Commission.user_id == User.id)\
     .filter(
         Commission.status == 'paid',
         Commission.created_at >= today - timedelta(days=30)
     )\
     .group_by(User.id)\
     .order_by(func.sum(Commission.commission_amount).desc())\
     .all()
    
    stats = {
        'total_revenue': float(total_revenue),
        'revenue_today': float(revenue_today),
        'revenue_week': float(revenue_week),
        'revenue_month': float(revenue_month),
        'total_transactions': total_transactions
    }
    
    revenue_list = [{
        'user': item.User,
        'transactions': item.total_transactions,
        'platform_revenue': float(item.platform_revenue or 0),
        'user_revenue': float(item.user_revenue or 0)
    } for item in revenue_by_user]
    
    log_admin_action('view_revenue', 'Visualizou receita da plataforma')
    
    return render_template('admin/revenue.html',
                         stats=stats,
                         revenue_by_user=revenue_list)

@app.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    """Página de analytics global com gráficos"""
    from sqlalchemy import func
    from models import BotUser, Commission
    from datetime import timedelta
    
    # Gráfico 1: Novos usuários (últimos 12 meses)
    twelve_months_ago = datetime.now() - timedelta(days=365)
    new_users_by_month = db.session.query(
        func.strftime('%Y-%m', User.created_at).label('month'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= twelve_months_ago,
        User.is_admin == False
    ).group_by(func.strftime('%Y-%m', User.created_at))\
     .order_by(func.strftime('%Y-%m', User.created_at))\
     .all()
    
    # Gráfico 2: Receita da plataforma (últimos 12 meses)
    revenue_by_month = db.session.query(
        func.strftime('%Y-%m', Commission.created_at).label('month'),
        func.sum(Commission.commission_amount).label('revenue')
    ).filter(
        Commission.created_at >= twelve_months_ago,
        Commission.status == 'paid'
    ).group_by(func.strftime('%Y-%m', Commission.created_at))\
     .order_by(func.strftime('%Y-%m', Commission.created_at))\
     .all()
    
    # Gráfico 3: Vendas totais (últimos 30 dias)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales')
    ).filter(
        Payment.created_at >= thirty_days_ago,
        Payment.status == 'paid'
    ).group_by(func.date(Payment.created_at))\
     .order_by(func.date(Payment.created_at))\
     .all()
    
    # Top 10 produtos mais vendidos
    top_products = db.session.query(
        Payment.product_name,
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.status == 'paid'
    ).group_by(Payment.product_name)\
     .order_by(func.count(Payment.id).desc())\
     .limit(10)\
     .all()
    
    # Conversão média da plataforma
    total_bot_users = BotUser.query.count()
    total_sales = Payment.query.filter_by(status='paid').count()
    conversion_rate = (total_sales / total_bot_users * 100) if total_bot_users > 0 else 0
    
    # Ticket médio
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'paid'
    ).scalar() or 0.0
    avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0
    
    data = {
        'new_users_chart': [{'month': m.month, 'count': m.count} for m in new_users_by_month],
        'revenue_chart': [{'month': m.month, 'revenue': float(m.revenue or 0)} for m in revenue_by_month],
        'sales_chart': [{'date': str(s.date), 'sales': s.sales} for s in sales_by_day],
        'top_products': [{'product': p.product_name or 'Sem nome', 'sales': p.sales, 'revenue': float(p.revenue or 0)} for p in top_products],
        'conversion_rate': round(conversion_rate, 2),
        'avg_ticket': round(float(avg_ticket), 2)
    }
    
    log_admin_action('view_analytics', 'Visualizou analytics global')
    
    return render_template('admin/analytics.html', data=data)

# ==================== CONFIGURAÇÃO DE BOTS ====================

@app.route('/bots/<int:bot_id>/stats')
@login_required
def bot_stats_page(bot_id):
    """Página de estatísticas detalhadas do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return render_template('bot_stats.html', bot=bot)

@app.route('/api/bots/<int:bot_id>/analytics-v2', methods=['GET'])
@login_required
def get_bot_analytics_v2(bot_id):
    """
    Analytics V2.0 - Dashboard Inteligente e Acionável
    
    FOCO: Decisões claras em 5 segundos
    - Lucro/Prejuízo HOJE (apenas para bots em POOLS)
    - Problemas que precisam ação AGORA
    - Oportunidades para escalar AGORA
    
    ⚠️ FIX QI 540: Apenas para bots que estão em redirecionadores (tráfego pago)
    Bot orgânico não tem gasto/ROI, então Analytics V2 não faz sentido.
    
    Implementado por: QI 540
    """
    from sqlalchemy import func, extract, case
    from models import BotUser, PoolBot
    from datetime import datetime, timedelta
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # ============================================================================
    # ✅ VERIFICAR SE BOT ESTÁ EM ALGUM POOL (REDIRECIONADOR)
    # ============================================================================
    is_in_pool = PoolBot.query.filter_by(bot_id=bot_id).count() > 0
    
    if not is_in_pool:
        # Bot orgânico (sem pool) - Analytics V2 não se aplica
        return jsonify({
            'is_organic': True,
            'message': 'Analytics V2.0 é exclusivo para bots em redirecionadores (tráfego pago)',
            'summary': None,
            'problems': [],
            'opportunities': [],
            'utm_performance': [],
            'conversion_funnel': {
                'pageviews': 0,
                'viewcontents': 0,
                'purchases': 0,
                'pageview_to_viewcontent': 0,
                'viewcontent_to_purchase': 0
            }
        })
    
    # ============================================================================
    # 💰 CARD 1: LUCRO/PREJUÍZO HOJE (APENAS PARA BOTS EM POOLS)
    # ============================================================================
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Vendas de hoje
    today_payments = Payment.query.filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).all()
    
    today_sales_count = len(today_payments)
    today_revenue = sum(p.amount for p in today_payments)
    
    # Acessos de hoje (PageView)
    today_pageviews = BotUser.query.filter(
        BotUser.bot_id == bot_id,
        BotUser.meta_pageview_sent == True,
        BotUser.meta_pageview_sent_at >= today_start
    ).count()
    
    # Estimativa de gasto (CPC médio R$ 2,00)
    cpc_medio = 2.0
    today_spend = today_pageviews * cpc_medio
    
    # Lucro/Prejuízo
    today_profit = today_revenue - today_spend
    today_roi = ((today_revenue / today_spend) - 1) * 100 if today_spend > 0 else 0
    
    # Comparação com ontem
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_start
    
    yesterday_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= yesterday_start,
        Payment.created_at < yesterday_end
    ).scalar() or 0.0
    
    revenue_change = ((today_revenue / yesterday_revenue) - 1) * 100 if yesterday_revenue > 0 else 0
    
    # ============================================================================
    # ⚠️ CARD 2: PROBLEMAS (AÇÃO IMEDIATA)
    # ============================================================================
    problems = []
    
    # Problema 1: ROI negativo
    if today_roi < 0:
        problems.append({
            'severity': 'CRITICAL',
            'title': f'ROI negativo: {today_roi:.1f}%',
            'description': f'Gastando R$ {today_spend:.2f}, faturando R$ {today_revenue:.2f}',
            'action': 'Pausar bot ou trocar campanha',
            'action_button': 'Pausar Bot'
        })
    
    # Problema 2: Conversão baixa (< 5%)
    total_users = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
    total_sales = Payment.query.filter_by(bot_id=bot_id, status='paid').count()
    conversion_rate = (total_sales / total_users * 100) if total_users > 0 else 0
    
    if conversion_rate < 5 and total_users > 20:
        problems.append({
            'severity': 'HIGH',
            'title': f'Conversão muito baixa: {conversion_rate:.1f}%',
            'description': f'{total_users} usuários mas apenas {total_sales} compraram',
            'action': 'Melhorar oferta ou copy do bot',
            'action_button': 'Ver Funil'
        })
    
    # Problema 3: Funil vazando
    pageview_count = BotUser.query.filter_by(bot_id=bot_id, meta_pageview_sent=True).count()
    viewcontent_count = BotUser.query.filter_by(bot_id=bot_id, meta_viewcontent_sent=True).count()
    
    if pageview_count > 0:
        pageview_to_viewcontent_rate = (viewcontent_count / pageview_count) * 100
        
        if pageview_to_viewcontent_rate < 30 and pageview_count > 50:
            problems.append({
                'severity': 'HIGH',
                'title': f'{100 - pageview_to_viewcontent_rate:.0f}% desistem antes de conversar',
                'description': f'{pageview_count} acessos, apenas {viewcontent_count} iniciaram conversa',
                'action': 'Copy do anúncio não está atraindo público certo',
                'action_button': 'Melhorar Copy'
            })
    
    # Problema 4: Zero vendas hoje
    if today_sales_count == 0 and today_pageviews > 20:
        problems.append({
            'severity': 'CRITICAL',
            'title': 'Zero vendas hoje!',
            'description': f'{today_pageviews} acessos mas nenhuma conversão',
            'action': 'Verificar bot, PIX ou oferta',
            'action_button': 'Verificar Bot'
        })
    
    # ============================================================================
    # 🚀 CARD 3: OPORTUNIDADES (ESCALAR)
    # ============================================================================
    opportunities = []
    
    # Oportunidade 1: ROI muito alto
    if today_roi > 200 and today_sales_count >= 3:
        opportunities.append({
            'type': 'SCALE',
            'title': f'ROI excelente: +{today_roi:.0f}%',
            'description': f'{today_sales_count} vendas com ticket médio R$ {today_revenue/today_sales_count:.2f}',
            'action': 'Dobrar budget dessa campanha',
            'action_button': 'Escalar +100%'
        })
    
    # Oportunidade 2: Alta taxa de recompra
    repeat_customers = db.session.query(
        Payment.customer_user_id,
        func.count(Payment.id).label('purchases')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid'
    ).group_by(Payment.customer_user_id)\
     .having(func.count(Payment.id) > 1)\
     .count()
    
    if total_sales > 0:
        repeat_rate = (repeat_customers / total_sales) * 100
        
        if repeat_rate > 25:
            opportunities.append({
                'type': 'UPSELL',
                'title': f'{repeat_rate:.0f}% dos clientes compram 2+ vezes',
                'description': f'{repeat_customers} clientes recorrentes',
                'action': 'Criar sequência de upsells',
                'action_button': 'Criar Upsell'
            })
    
    # Oportunidade 3: Horário quente
    best_hour = db.session.query(
        extract('hour', Payment.created_at).label('hour'),
        func.count(Payment.id).label('sales')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid'
    ).group_by(extract('hour', Payment.created_at))\
     .order_by(func.count(Payment.id).desc())\
     .first()
    
    if best_hour and best_hour.sales >= 5:
        opportunities.append({
            'type': 'TIMING',
            'title': f'Horário quente: {int(best_hour.hour):02d}h-{int(best_hour.hour)+1:02d}h',
            'description': f'{best_hour.sales} vendas nesse horário',
            'action': 'Concentrar budget nesse período',
            'action_button': 'Ajustar Horários'
        })
    
    # ============================================================================
    # 📊 DADOS COMPLEMENTARES (PARA EXPANSÃO)
    # ============================================================================
    
    # UTM Performance (top 3)
    utm_performance = db.session.query(
        Payment.utm_source,
        Payment.utm_campaign,
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.utm_source.isnot(None)
    ).group_by(Payment.utm_source, Payment.utm_campaign)\
     .order_by(func.sum(Payment.amount).desc())\
     .limit(3)\
     .all()
    
    utm_stats = [{
        'source': u.utm_source or 'Direto',
        'campaign': u.utm_campaign or 'Sem campanha',
        'sales': u.sales,
        'revenue': float(u.revenue or 0)
    } for u in utm_performance]
    
    return jsonify({
        'summary': {
            'today_revenue': float(today_revenue),
            'today_spend': float(today_spend),
            'today_profit': float(today_profit),
            'today_roi': round(today_roi, 1),
            'today_sales': today_sales_count,
            'revenue_change': round(revenue_change, 1),
            'status': 'profit' if today_profit > 0 else 'loss'
        },
        'problems': problems,
        'opportunities': opportunities,
        'utm_performance': utm_stats,
        'conversion_funnel': {
            'pageviews': pageview_count,
            'viewcontents': viewcontent_count,
            'purchases': total_sales,
            'pageview_to_viewcontent': round(pageview_to_viewcontent_rate, 1) if pageview_count > 0 else 0,
            'viewcontent_to_purchase': round((total_sales / viewcontent_count * 100), 1) if viewcontent_count > 0 else 0
        }
    })


@app.route('/api/bots/<int:bot_id>/stats', methods=['GET'])
@login_required
def get_bot_stats(bot_id):
    """API para estatísticas detalhadas de um bot específico"""
    from sqlalchemy import func, extract, case
    from models import BotUser
    from datetime import datetime, timedelta
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # 1. ESTATÍSTICAS GERAIS
    # ✅ Contar apenas usuários ativos (não arquivados)
    total_users = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
    # ✅ Usuários arquivados (histórico de tokens antigos)
    archived_users = BotUser.query.filter_by(bot_id=bot_id, archived=True).count()
    
    total_sales = Payment.query.filter_by(bot_id=bot_id, status='paid').count()
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id, Payment.status == 'paid'
    ).scalar() or 0.0
    pending_sales = Payment.query.filter_by(bot_id=bot_id, status='pending').count()
    
    # Taxa de conversão
    conversion_rate = (total_sales / total_users * 100) if total_users > 0 else 0
    avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0
    
    # 2. VENDAS POR PRODUTO (últimos 30 dias)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    sales_by_product = db.session.query(
        Payment.product_name,
        func.count(Payment.id).label('total_sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= thirty_days_ago
    ).group_by(Payment.product_name)\
     .order_by(func.count(Payment.id).desc())\
     .limit(10)\
     .all()
    
    products_stats = [{
        'product': p.product_name or 'Sem nome',
        'sales': p.total_sales,
        'revenue': float(p.revenue or 0)
    } for p in sales_by_product]
    
    # 3. ORDER BUMPS
    order_bump_shown = Payment.query.filter_by(
        bot_id=bot_id, order_bump_shown=True
    ).count()
    order_bump_accepted = Payment.query.filter_by(
        bot_id=bot_id, order_bump_accepted=True
    ).count()
    order_bump_revenue = db.session.query(func.sum(Payment.order_bump_value)).filter(
        Payment.bot_id == bot_id, Payment.order_bump_accepted == True, Payment.status == 'paid'
    ).scalar() or 0.0
    order_bump_rate = (order_bump_accepted / order_bump_shown * 100) if order_bump_shown > 0 else 0
    
    # 4. DOWNSELLS
    downsell_sent = Payment.query.filter_by(
        bot_id=bot_id, is_downsell=True
    ).count()
    downsell_paid = Payment.query.filter_by(
        bot_id=bot_id, is_downsell=True, status='paid'
    ).count()
    downsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id, Payment.is_downsell == True, Payment.status == 'paid'
    ).scalar() or 0.0
    downsell_rate = (downsell_paid / downsell_sent * 100) if downsell_sent > 0 else 0
    
    # 5. VENDAS POR DIA (últimos 7 dias)
    seven_days_ago = datetime.now() - timedelta(days=7)
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= seven_days_ago
    ).group_by(func.date(Payment.created_at))\
     .order_by(func.date(Payment.created_at))\
     .all()
    
    # Preencher dias sem vendas
    daily_stats = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).date()
        day_data = next((s for s in sales_by_day if str(s.date) == str(date)), None)
        daily_stats.append({
            'date': date.strftime('%d/%m'),
            'sales': day_data.sales if day_data else 0,
            'revenue': float(day_data.revenue) if day_data else 0.0
        })
    
    # 6. HORÁRIOS DE PICO
    peak_hours = db.session.query(
        extract('hour', Payment.created_at).label('hour'),
        func.count(Payment.id).label('sales')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid'
    ).group_by(extract('hour', Payment.created_at))\
     .order_by(func.count(Payment.id).desc())\
     .limit(5)\
     .all()
    
    hours_stats = [{'hour': f"{int(h.hour):02d}:00", 'sales': h.sales} for h in peak_hours]
    
    # 7. ÚLTIMAS VENDAS
    recent_sales = db.session.query(Payment).filter(
        Payment.bot_id == bot_id
    ).order_by(Payment.id.desc()).limit(20).all()
    
    sales_list = [{
        'id': p.id,
        'customer_name': p.customer_name,
        'product_name': p.product_name,
        'amount': float(p.amount),
        'status': p.status,
        'is_downsell': p.is_downsell,
        'order_bump_accepted': p.order_bump_accepted,
        'created_at': p.created_at.isoformat()
    } for p in recent_sales]
    
    return jsonify({
        'general': {
            'total_users': total_users,
            'archived_users': archived_users,  # ✅ Histórico de tokens antigos
            'total_sales': total_sales,
            'total_revenue': float(total_revenue),
            'pending_sales': pending_sales,
            'conversion_rate': round(conversion_rate, 2),
            'avg_ticket': round(float(avg_ticket), 2)
        },
        'products': products_stats,
        'order_bumps': {
            'shown': order_bump_shown,
            'accepted': order_bump_accepted,
            'acceptance_rate': round(order_bump_rate, 2),
            'revenue': float(order_bump_revenue)
        },
        'downsells': {
            'sent': downsell_sent,
            'converted': downsell_paid,
            'conversion_rate': round(downsell_rate, 2),
            'revenue': float(downsell_revenue)
        },
        'daily_chart': daily_stats,
        'peak_hours': hours_stats,
        'recent_sales': sales_list
    })

@app.route('/bots/<int:bot_id>/config')
@login_required
def bot_config_page(bot_id):
    """Página de configuração do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return render_template('bot_config.html', bot=bot)

@app.route('/remarketing/analytics/<int:bot_id>')
@login_required
def remarketing_analytics(bot_id):
    """Página de analytics de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return render_template('remarketing_analytics.html', bot=bot)

@app.route('/api/remarketing/<int:bot_id>/stats')
@login_required
def api_remarketing_stats(bot_id):
    """API: Estatísticas gerais de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    from sqlalchemy import func
    from models import RemarketingCampaign
    
    # Estatísticas agregadas
    total_campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).count()
    completed_campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id, status='completed').count()
    
    totals = db.session.query(
        func.sum(RemarketingCampaign.total_sent).label('total_sent'),
        func.sum(RemarketingCampaign.total_clicks).label('total_clicks'),
        func.sum(RemarketingCampaign.total_failed).label('total_failed')
    ).filter(RemarketingCampaign.bot_id == bot_id).first()
    
    total_sent = int(totals.total_sent or 0)
    total_clicks = int(totals.total_clicks or 0)
    total_failed = int(totals.total_failed or 0)
    
    click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
    success_rate = ((total_sent - total_failed) / total_sent * 100) if total_sent > 0 else 0
    
    return jsonify({
        'total_campaigns': total_campaigns,
        'completed_campaigns': completed_campaigns,
        'total_sent': total_sent,
        'total_clicks': total_clicks,
        'total_failed': total_failed,
        'click_rate': round(click_rate, 2),
        'success_rate': round(success_rate, 2)
    })

@app.route('/api/remarketing/<int:bot_id>/timeline')
@login_required
def api_remarketing_timeline(bot_id):
    """API: Timeline de envios de remarketing (últimos 7 dias)"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    from sqlalchemy import func
    from models import RemarketingCampaign
    from datetime import datetime, timedelta
    
    # Últimos 7 dias
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    # Agrupar por data
    timeline_data = db.session.query(
        func.date(RemarketingCampaign.started_at).label('date'),
        func.sum(RemarketingCampaign.total_sent).label('sent'),
        func.sum(RemarketingCampaign.total_clicks).label('clicks')
    ).filter(
        RemarketingCampaign.bot_id == bot_id,
        RemarketingCampaign.started_at >= seven_days_ago,
        RemarketingCampaign.status == 'completed'
    ).group_by(func.date(RemarketingCampaign.started_at)).all()
    
    # Preencher dias sem dados
    result = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).date()
        day_data = next((t for t in timeline_data if str(t.date) == str(date)), None)
        result.append({
            'date': date.strftime('%d/%m'),
            'sent': int(day_data.sent) if day_data else 0,
            'clicks': int(day_data.clicks) if day_data else 0
        })
    
    return jsonify(result)

@app.route('/api/bots/<int:bot_id>/config', methods=['GET'])
@login_required
def get_bot_config(bot_id):
    """Obtém configuração de um bot"""
    try:
        logger.info(f"🔍 Buscando config do bot {bot_id}...")
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        logger.info(f"✅ Bot encontrado: {bot.name}")
        
        if not bot.config:
            logger.warning(f"⚠️ Bot {bot_id} não tem config, criando nova...")
            config = BotConfig(bot_id=bot.id)
            db.session.add(config)
            db.session.commit()
            db.session.refresh(config)
            logger.info(f"✅ Config nova criada para bot {bot_id}")
        else:
            logger.info(f"✅ Config existente encontrada (ID: {bot.config.id})")
        
        config_dict = bot.config.to_dict()
        logger.info(f"📦 Config serializado com sucesso")
        logger.info(f"   - welcome_message: {len(config_dict.get('welcome_message', ''))} chars")
        logger.info(f"   - main_buttons: {len(config_dict.get('main_buttons', []))} botões")
        logger.info(f"   - downsells: {len(config_dict.get('downsells', []))} downsells")
        logger.info(f"   - upsells: {len(config_dict.get('upsells', []))} upsells")
        
        return jsonify(config_dict)
    except Exception as e:
        logger.error(f"❌ Erro ao buscar config do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao buscar configuração: {str(e)}'}), 500

@app.route('/api/bots/<int:bot_id>/config', methods=['PUT'])
@login_required
@csrf.exempt
def update_bot_config(bot_id):
    """Atualiza configuração de um bot"""
    logger.info(f"🔄 Iniciando atualização de config para bot {bot_id}")
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    data = request.json
    
    logger.info(f"📊 Dados recebidos: {list(data.keys())}")
    
    if not bot.config:
        logger.info(f"📝 Criando nova configuração para bot {bot_id}")
        config = BotConfig(bot_id=bot.id)
        db.session.add(config)
    else:
        logger.info(f"📝 Atualizando configuração existente para bot {bot_id}")
        config = bot.config
    
    try:
        # Atualizar campos
        if 'welcome_message' in data:
            config.welcome_message = data['welcome_message']
        if 'welcome_media_url' in data:
            config.welcome_media_url = data['welcome_media_url']
        if 'welcome_media_type' in data:
            config.welcome_media_type = data['welcome_media_type']
        if 'welcome_audio_enabled' in data:
            config.welcome_audio_enabled = data['welcome_audio_enabled']
        if 'welcome_audio_url' in data:
            config.welcome_audio_url = data['welcome_audio_url']
        
        # Botões principais
        if 'main_buttons' in data:
            logger.info(f"🔘 Salvando {len(data['main_buttons'])} botões principais")
            config.set_main_buttons(data['main_buttons'])
            logger.info(f"✅ Botões principais salvos com sucesso")
        
        # Botões de redirecionamento
        if 'redirect_buttons' in data:
            config.set_redirect_buttons(data['redirect_buttons'])
        
        # Order bump
        if 'order_bump_enabled' in data:
            config.order_bump_enabled = data['order_bump_enabled']
        if 'order_bump_message' in data:
            config.order_bump_message = data['order_bump_message']
        if 'order_bump_media_url' in data:
            config.order_bump_media_url = data['order_bump_media_url']
        if 'order_bump_price' in data:
            config.order_bump_price = data['order_bump_price']
        if 'order_bump_description' in data:
            config.order_bump_description = data['order_bump_description']
        
        # Downsells
        if 'downsells_enabled' in data:
            config.downsells_enabled = data['downsells_enabled']
        if 'downsells' in data:
            config.set_downsells(data['downsells'])
        
        # ✅ UPSELLS
        if 'upsells_enabled' in data:
            config.upsells_enabled = data['upsells_enabled']
        if 'upsells' in data:
            config.set_upsells(data['upsells'])
        
        # Link de acesso
        if 'access_link' in data:
            config.access_link = data['access_link']
        
        # Mensagens personalizadas
        if 'success_message' in data:
            config.success_message = data['success_message']
        if 'pending_message' in data:
            config.pending_message = data['pending_message']
        
        logger.info(f"💾 Fazendo commit no banco de dados...")
        db.session.commit()
        logger.info(f"✅ Commit realizado com sucesso")
        
        # Se bot está rodando, atualizar configuração em tempo real
        if bot.is_running:
            logger.info(f"🔄 Bot está rodando, atualizando configuração em tempo real...")
            bot_manager.update_bot_config(bot.id, config.to_dict())
            logger.info(f"✅ Configuração atualizada em tempo real")
        
        logger.info(f"✅ Configuração do bot {bot.name} atualizada por {current_user.email}")
        return jsonify(config.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar configuração: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== LOAD BALANCER / REDIRECT POOLS ====================

def validate_cloaker_access(request, pool, slug):
    """
    ✅ QI 540 + QI 300 #2: Validação MULTICAMADAS do cloaker
    
    CAMADA 1: Parâmetro obrigatório
    CAMADA 2: User-Agent (bot detection)
    CAMADA 3: Header consistency
    CAMADA 4: Timing analysis
    """
    import redis
    import time
    
    score = 100
    details = {}
    
    # CAMADA 1: Parâmetro
    param_name = pool.meta_cloaker_param_name or 'grim'
    expected_value = pool.meta_cloaker_param_value
    
    if not expected_value or not expected_value.strip():
        return {'allowed': False, 'reason': 'cloaker_misconfigured', 'score': 0, 'details': {}}
    
    expected_value = expected_value.strip()
    actual_value = (request.args.get(param_name) or '').strip()
    
    if actual_value != expected_value:
        return {'allowed': False, 'reason': 'invalid_parameter', 'score': 0, 'details': {'param_match': False}}
    
    details['param_match'] = True
    
    # CAMADA 2: Bot Detection
    user_agent = request.headers.get('User-Agent', '').lower()
    bot_patterns = [
        'facebookexternalhit', 'facebot', 'twitterbot', 'linkedinbot', 'googlebot', 'bingbot',
        'bot', 'crawler', 'spider', 'scraper', 'python-requests', 'curl', 'wget', 'scrapy'
    ]
    
    for pattern in bot_patterns:
        if pattern in user_agent:
            return {'allowed': False, 'reason': 'bot_detected_ua', 'score': 0, 
                   'details': {'pattern': pattern, 'user_agent': user_agent[:200]}}
    
    # CAMADA 3: Header Consistency
    if 'mozilla' in user_agent or 'chrome' in user_agent:
        if not request.headers.get('Accept'):
            score -= 30
        if not request.headers.get('Accept-Language'):
            score -= 10
    
    # CAMADA 4: Timing (Redis)
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)
        ip = request.remote_addr
        last_access_key = f"cloaker:timing:{ip}"
        last_access = r.get(last_access_key)
        
        if last_access:
            time_diff = time.time() - float(last_access)
            if time_diff < 0.1:
                score -= 40
        
        r.setex(last_access_key, 60, str(time.time()))
    except:
        pass
    
    return {'allowed': score >= 40, 'reason': 'authorized' if score >= 40 else 'suspicious_behavior', 
           'score': score, 'details': details}


def log_cloaker_event_json(event_type, slug, validation_result, request, pool, latency_ms=0):
    """✅ QI 540: Log estruturado em JSONL"""
    import json
    import uuid
    from datetime import datetime
    
    ip_parts = request.remote_addr.split('.')
    ip_short = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.x" if len(ip_parts) == 4 else request.remote_addr
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request_id': str(uuid.uuid4()),
        'event_type': event_type,
        'slug': slug,
        'pool_id': pool.id,
        'result': 'ALLOW' if validation_result['allowed'] else 'BLOCK',
        'reason': validation_result['reason'],
        'score': validation_result['score'],
        'ip_short': ip_short,
        'user_agent': request.headers.get('User-Agent', '')[:200],
        'param_name': pool.meta_cloaker_param_name,
        'param_provided': bool(request.args.get(pool.meta_cloaker_param_name or 'grim')),
        'http_method': request.method,
        'code': 403 if not validation_result['allowed'] else 302,
        'latency_ms': round(latency_ms, 2)
    }
    
    logger.info(f"CLOAKER_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")


@app.route('/go/<slug>')
def public_redirect(slug):
    """
    Endpoint PÚBLICO de redirecionamento com Load Balancing + Meta Pixel Tracking + Cloaker
    
    URL: /go/{slug} (ex: /go/red1)
    
    FUNCIONALIDADES:
    - Busca pool pelo slug
    - ✅ CLOAKER: Validação MULTICAMADAS (parâmetro + UA + headers + timing)
    - Seleciona bot online (estratégia configurada)
    - Health check em cache (não valida em tempo real)
    - Failover automático
    - Circuit breaker
    - Métricas de uso
    - ✅ META PIXEL: PageView tracking
    """
    from datetime import datetime
    import time
    
    start_time = time.time()
    
    # Buscar pool ativo
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    if not pool:
        abort(404, f'Pool "{slug}" não encontrado ou inativo')
    
    # ============================================================================
    # ✅ CLOAKER + ANTICLONE: VALIDAÇÃO MULTICAMADAS (PATCH_001 APLICADO)
    # ============================================================================
    
    if pool.meta_cloaker_enabled:
        # Validação multicamadas
        validation_result = validate_cloaker_access(request, pool, slug)
        
        # Latência da validação
        validation_latency = (time.time() - start_time) * 1000
        
        # Log estruturado JSON
        log_cloaker_event_json(
            event_type='cloaker_validation',
            slug=slug,
            validation_result=validation_result,
            request=request,
            pool=pool,
            latency_ms=validation_latency
        )
        
        # Se bloqueado
        if not validation_result['allowed']:
            logger.warning(
                f"🛡️ BLOCK | Slug: {slug} | Reason: {validation_result['reason']} | "
                f"Score: {validation_result['score']}/100"
            )
            return render_template('cloaker_block.html', pool_name=pool.name, slug=slug), 403
        
        # Se autorizado
        logger.info(f"✅ ALLOW | Slug: {slug} | Score: {validation_result['score']}/100")
    
    # Selecionar bot usando estratégia configurada
    pool_bot = pool.select_bot()
    
    if not pool_bot:
        # Nenhum bot online - tentar bot degradado como fallback
        degraded = pool.pool_bots.filter_by(
            is_enabled=True,
            status='degraded'
        ).order_by(PoolBot.consecutive_failures.asc()).first()
        
        if degraded:
            pool_bot = degraded
            logger.warning(f"Pool {slug}: Usando bot degradado @{pool_bot.bot.username}")
        else:
            abort(503, 'Nenhum bot disponível no momento. Tente novamente em instantes.')
    
    # Incrementar métricas
    pool_bot.total_redirects += 1
    pool.total_redirects += 1
    db.session.commit()
    
    # Log
    logger.info(f"Redirect: /go/{slug} → @{pool_bot.bot.username} | Estratégia: {pool.distribution_strategy} | Total: {pool_bot.total_redirects}")
    
    # ============================================================================
    # ✅ META PIXEL: PAGEVIEW TRACKING + UTM CAPTURE (NÍVEL DE POOL)
    # ============================================================================
    # CRÍTICO: Captura UTM e External ID para vincular eventos posteriores
    # ============================================================================
    external_id = None
    utm_data = {}
    
    try:
        external_id, utm_data = send_meta_pixel_pageview_event(pool, request)
    except Exception as e:
        logger.error(f"Erro ao enviar PageView para Meta Pixel: {e}")
        # Não impedir o redirect se Meta falhar
    
    # Emitir evento WebSocket para o dono do pool
    socketio.emit('pool_redirect', {
        'pool_id': pool.id,
        'pool_name': pool.name,
        'bot_username': pool_bot.bot.username,
        'total_redirects': pool.total_redirects
    }, room=f'user_{pool.user_id}')
    
    # ============================================================================
    # ✅ REDIRECT PARA TELEGRAM COM TRACKING DATA
    # ============================================================================
    # Passar pool_id, external_id e UTMs no parâmetro start
    # Formato: start=p{pool_id}_e{external_id}_s{utm_source}_c{utm_campaign}
    # Limitado a 64 caracteres pelo Telegram
    # ============================================================================
    import base64
    import json
    
    # Construir payload de tracking
    tracking_data = {
        'p': pool.id,  # pool_id
    }
    
    if external_id:
        tracking_data['e'] = external_id[:12]  # Primeiros 12 chars do external_id
    
    if utm_data:
        if utm_data.get('utm_source'):
            tracking_data['s'] = utm_data['utm_source'][:10]
        if utm_data.get('utm_campaign'):
            tracking_data['c'] = utm_data['utm_campaign'][:10]
        if utm_data.get('campaign_code'):
            tracking_data['cc'] = utm_data['campaign_code'][:8]
        if utm_data.get('fbclid'):
            tracking_data['f'] = utm_data['fbclid'][:15]
    
    # Serializar e encodar (base64 para reduzir tamanho)
    try:
        tracking_json = json.dumps(tracking_data, separators=(',', ':'))
        tracking_base64 = base64.urlsafe_b64encode(tracking_json.encode()).decode()
        
        # Telegram limita start param a 64 chars
        # Se exceder, usar apenas pool_id
        if len(tracking_base64) + 1 > 64:  # +1 para o 't' inicial
            # Fallback: apenas pool_id
            tracking_param = f"p{pool.id}"
            logger.warning(f"Tracking param muito longo ({len(tracking_base64)} chars), usando fallback: {tracking_param}")
        else:
            tracking_param = f"t{tracking_base64}"
    except Exception as e:
        # Fallback simples se encoding falhar
        logger.error(f"Erro ao encodar tracking: {e}")
        tracking_param = f"p{pool.id}"
    
    redirect_url = f"https://t.me/{pool_bot.bot.username}?start={tracking_param}"
    return redirect(redirect_url, code=302)


@app.route('/redirect-pools')
@login_required
def redirect_pools_page():
    """Página de gerenciamento de pools"""
    return render_template('redirect_pools.html')


@app.route('/api/redirect-pools', methods=['GET'])
@login_required
def get_redirect_pools():
    """Lista todos os pools do usuário"""
    pools = RedirectPool.query.filter_by(user_id=current_user.id).all()
    return jsonify([pool.to_dict() for pool in pools])


@app.route('/api/redirect-pools', methods=['POST'])
@login_required
@csrf.exempt
def create_redirect_pool():
    """
    Cria novo pool de redirecionamento
    
    VALIDAÇÕES:
    - Nome obrigatório
    - Slug único por usuário
    - Slug alfanumérico (a-z, 0-9, -, _)
    """
    data = request.get_json()
    
    name = data.get('name', '').strip()
    slug = data.get('slug', '').strip().lower()
    description = data.get('description', '').strip()
    strategy = data.get('distribution_strategy', 'round_robin')
    
    # VALIDAÇÃO 1: Nome obrigatório
    if not name:
        return jsonify({'error': 'Nome do pool é obrigatório'}), 400
    
    # VALIDAÇÃO 2: Slug obrigatório
    if not slug:
        return jsonify({'error': 'Slug é obrigatório (ex: red1, red2)'}), 400
    
    # VALIDAÇÃO 3: Slug alfanumérico
    import re
    if not re.match(r'^[a-z0-9_-]+$', slug):
        return jsonify({'error': 'Slug deve conter apenas letras minúsculas, números, - e _'}), 400
    
    # VALIDAÇÃO 4: Slug único para este usuário
    existing = RedirectPool.query.filter_by(user_id=current_user.id, slug=slug).first()
    if existing:
        return jsonify({'error': f'Você já tem um pool com slug "{slug}"'}), 400
    
    # VALIDAÇÃO 5: Estratégia válida
    valid_strategies = ['round_robin', 'least_connections', 'random', 'weighted']
    if strategy not in valid_strategies:
        return jsonify({'error': f'Estratégia inválida. Use: {", ".join(valid_strategies)}'}), 400
    
    try:
        pool = RedirectPool(
            user_id=current_user.id,
            name=name,
            slug=slug,
            description=description,
            distribution_strategy=strategy
        )
        
        db.session.add(pool)
        db.session.commit()
        
        logger.info(f"Pool criado: {name} ({slug}) por {current_user.email}")
        
        return jsonify({
            'message': 'Pool criado com sucesso!',
            'pool': pool.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar pool: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/redirect-pools/<int:pool_id>', methods=['GET'])
@login_required
def get_redirect_pool(pool_id):
    """Obtém detalhes de um pool"""
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    # Incluir lista de bots
    pool_data = pool.to_dict()
    pool_data['bots'] = [pb.to_dict() for pb in pool.pool_bots.all()]
    
    return jsonify(pool_data)


@app.route('/api/redirect-pools/<int:pool_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_redirect_pool(pool_id):
    """Atualiza configurações do pool"""
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    if 'name' in data:
        pool.name = data['name'].strip()
    
    if 'description' in data:
        pool.description = data['description'].strip()
    
    if 'distribution_strategy' in data:
        valid_strategies = ['round_robin', 'least_connections', 'random', 'weighted']
        if data['distribution_strategy'] in valid_strategies:
            pool.distribution_strategy = data['distribution_strategy']
    
    if 'is_active' in data:
        pool.is_active = data['is_active']
    
    db.session.commit()
    
    logger.info(f"Pool atualizado: {pool.name} por {current_user.email}")
    
    return jsonify({
        'message': 'Pool atualizado com sucesso!',
        'pool': pool.to_dict()
    })


@app.route('/api/redirect-pools/<int:pool_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_redirect_pool(pool_id):
    """Deleta um pool"""
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    pool_name = pool.name
    db.session.delete(pool)
    db.session.commit()
    
    logger.info(f"Pool deletado: {pool_name} por {current_user.email}")
    
    return jsonify({'message': 'Pool deletado com sucesso'})


@app.route('/api/redirect-pools/<int:pool_id>/bots', methods=['POST'])
@login_required
@csrf.exempt
def add_bot_to_pool(pool_id):
    """
    Adiciona bot ao pool
    
    VALIDAÇÕES:
    - Bot pertence ao usuário
    - Bot não está em outro pool do mesmo usuário (opcional)
    - Weight e priority válidos
    """
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    bot_id = data.get('bot_id')
    weight = data.get('weight', 1)
    priority = data.get('priority', 0)
    
    # VALIDAÇÃO 1: Bot ID obrigatório
    if not bot_id:
        return jsonify({'error': 'Bot ID é obrigatório'}), 400
    
    # VALIDAÇÃO 2: Bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
    if not bot:
        return jsonify({'error': 'Bot não encontrado ou não pertence a você'}), 404
    
    # VALIDAÇÃO 3: Bot já está neste pool?
    existing = PoolBot.query.filter_by(pool_id=pool_id, bot_id=bot_id).first()
    if existing:
        return jsonify({'error': 'Bot já está neste pool'}), 400
    
    try:
        pool_bot = PoolBot(
            pool_id=pool_id,
            bot_id=bot_id,
            weight=max(1, int(weight)),
            priority=int(priority)
        )
        
        db.session.add(pool_bot)
        db.session.commit()
        
        # Atualizar saúde do pool
        pool.update_health()
        db.session.commit()
        
        logger.info(f"Bot @{bot.username} adicionado ao pool {pool.name} por {current_user.email}")
        
        return jsonify({
            'message': 'Bot adicionado ao pool!',
            'pool_bot': pool_bot.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao adicionar bot ao pool: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/redirect-pools/<int:pool_id>/bots/<int:pool_bot_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def remove_bot_from_pool(pool_id, pool_bot_id):
    """Remove bot do pool"""
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    pool_bot = PoolBot.query.filter_by(id=pool_bot_id, pool_id=pool_id).first_or_404()
    
    bot_username = pool_bot.bot.username
    db.session.delete(pool_bot)
    db.session.commit()
    
    # Atualizar saúde do pool
    pool.update_health()
    db.session.commit()
    
    logger.info(f"Bot @{bot_username} removido do pool {pool.name} por {current_user.email}")
    
    return jsonify({'message': 'Bot removido do pool'})


@app.route('/api/redirect-pools/<int:pool_id>/bots/<int:pool_bot_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_pool_bot_config(pool_id, pool_bot_id):
    """Atualiza configurações do bot no pool (weight, priority, enabled)"""
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    pool_bot = PoolBot.query.filter_by(id=pool_bot_id, pool_id=pool_id).first_or_404()
    
    data = request.get_json()
    
    if 'weight' in data:
        pool_bot.weight = max(1, int(data['weight']))
    
    if 'priority' in data:
        pool_bot.priority = int(data['priority'])
    
    if 'is_enabled' in data:
        pool_bot.is_enabled = data['is_enabled']
    
    db.session.commit()
    
    logger.info(f"Configurações do bot @{pool_bot.bot.username} no pool {pool.name} atualizadas")
    
    return jsonify({
        'message': 'Configurações atualizadas!',
        'pool_bot': pool_bot.to_dict()
    })


# ==================== META PIXEL (CONFIGURAÇÃO POR POOL) ====================

@app.route('/api/redirect-pools/<int:pool_id>/meta-pixel', methods=['GET'])
@login_required
def get_pool_meta_pixel_config(pool_id):
    """
    Obtém configuração do Meta Pixel do pool
    
    ARQUITETURA V2.0: Pixel configurado no POOL (não no bot)
    """
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    from utils.encryption import decrypt
    
    # Descriptografar access_token para exibição (mascarado)
    access_token_display = None
    if pool.meta_access_token:
        try:
            access_token_decrypted = decrypt(pool.meta_access_token)
            # Mostrar apenas primeiros e últimos caracteres
            access_token_display = access_token_decrypted[:10] + '...' + access_token_decrypted[-4:]
        except:
            access_token_display = '***erro_descriptografia***'
    
    return jsonify({
        'pool_id': pool.id,
        'pool_name': pool.name,
        'meta_pixel_id': pool.meta_pixel_id,
        'meta_access_token': access_token_display,
        'meta_tracking_enabled': pool.meta_tracking_enabled,
        'meta_test_event_code': pool.meta_test_event_code,
        'meta_events_pageview': pool.meta_events_pageview,
        'meta_events_viewcontent': pool.meta_events_viewcontent,
        'meta_events_purchase': pool.meta_events_purchase,
        'meta_cloaker_enabled': pool.meta_cloaker_enabled,
        'meta_cloaker_param_name': pool.meta_cloaker_param_name or 'grim',
        'meta_cloaker_param_value': pool.meta_cloaker_param_value
    })


@app.route('/api/redirect-pools/<int:pool_id>/meta-pixel', methods=['PUT'])
@login_required
@csrf.exempt
def update_pool_meta_pixel_config(pool_id):
    """
    Atualiza configuração do Meta Pixel do pool
    
    VALIDAÇÕES:
    - Pixel ID deve ser numérico (15-16 dígitos)
    - Access Token deve ter pelo menos 50 caracteres
    - Testa conexão antes de salvar (se fornecido)
    """
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    from utils.meta_pixel import MetaPixelHelper, MetaPixelAPI
    from utils.encryption import encrypt
    
    try:
        # Validar Pixel ID
        pixel_id = data.get('meta_pixel_id', '').strip()
        if pixel_id and not MetaPixelHelper.is_valid_pixel_id(pixel_id):
            return jsonify({'error': 'Pixel ID inválido (deve ter 15-16 dígitos numéricos)'}), 400
        
        # Validar Access Token
        access_token = data.get('meta_access_token', '').strip()
        if access_token:
            # Se começar com "..." significa que não foi alterado (campo mascarado)
            if not access_token.startswith('...'):
                if not MetaPixelHelper.is_valid_access_token(access_token):
                    return jsonify({'error': 'Access Token inválido (mínimo 50 caracteres)'}), 400
                
                # Testar conexão antes de salvar
                test_result = MetaPixelAPI.test_connection(pixel_id, access_token)
                if not test_result['success']:
                    return jsonify({'error': f'Falha ao conectar: {test_result["error"]}'}), 400
                
                # Criptografar antes de salvar
                pool.meta_access_token = encrypt(access_token)
        
        # Atualizar campos
        if pixel_id:
            pool.meta_pixel_id = pixel_id
        
        if 'meta_tracking_enabled' in data:
            pool.meta_tracking_enabled = bool(data['meta_tracking_enabled'])
        
        if 'meta_test_event_code' in data:
            pool.meta_test_event_code = data['meta_test_event_code'].strip() or None
        
        if 'meta_events_pageview' in data:
            pool.meta_events_pageview = bool(data['meta_events_pageview'])
        
        if 'meta_events_viewcontent' in data:
            pool.meta_events_viewcontent = bool(data['meta_events_viewcontent'])
        
        if 'meta_events_purchase' in data:
            pool.meta_events_purchase = bool(data['meta_events_purchase'])
        
        if 'meta_cloaker_enabled' in data:
            pool.meta_cloaker_enabled = bool(data['meta_cloaker_enabled'])
        
        if 'meta_cloaker_param_name' in data:
            pool.meta_cloaker_param_name = data['meta_cloaker_param_name'].strip() or 'grim'
        
        if 'meta_cloaker_param_value' in data:
            # ✅ FIX BUG: Strip e validar valor antes de salvar
            cloaker_value = data['meta_cloaker_param_value']
            if cloaker_value:
                cloaker_value = cloaker_value.strip()
                if not cloaker_value:  # String vazia após strip
                    cloaker_value = None
            pool.meta_cloaker_param_value = cloaker_value
        
        db.session.commit()
        
        logger.info(f"Meta Pixel configurado para pool {pool.name} por {current_user.email}")
        
        return jsonify({
            'message': 'Meta Pixel configurado com sucesso!',
            'pool_id': pool.id,
            'meta_tracking_enabled': pool.meta_tracking_enabled
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao configurar Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/redirect-pools/<int:pool_id>/meta-pixel/test', methods=['POST'])
@login_required
@csrf.exempt
def test_pool_meta_pixel_connection(pool_id):
    """
    Testa conexão com Meta Pixel API
    
    Usado para validar credenciais antes de salvar
    """
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    pixel_id = data.get('pixel_id', '').strip()
    access_token = data.get('access_token', '').strip()
    
    if not pixel_id or not access_token:
        return jsonify({'error': 'Pixel ID e Access Token são obrigatórios'}), 400
    
    from utils.meta_pixel import MetaPixelAPI
    
    try:
        result = MetaPixelAPI.test_connection(pixel_id, access_token)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Conexão com Meta Pixel estabelecida com sucesso!',
                'pixel_info': result['pixel_info']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Erro ao testar Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== GATEWAYS DE PAGAMENTO ====================

@app.route('/api/gateways', methods=['GET'])
@login_required
def get_gateways():
    """Lista gateways do usuário"""
    gateways = current_user.gateways.all()
    return jsonify([g.to_dict() for g in gateways])

@app.route('/api/gateways', methods=['POST'])
@login_required
@csrf.exempt
def create_gateway():
    """Cria/atualiza gateway"""
    try:
        logger.info(f"📡 Recebendo requisição para salvar gateway...")
        data = request.json
        logger.info(f"📦 Dados recebidos: gateway_type={data.get('gateway_type')}")
        
        gateway_type = data.get('gateway_type')
    
        # ✅ Validar tipo de gateway
        if gateway_type not in ['syncpay', 'pushynpay', 'paradise', 'wiinpay']:
            logger.error(f"❌ Tipo de gateway inválido: {gateway_type}")
            return jsonify({'error': 'Tipo de gateway inválido'}), 400
        
        # Verificar se já existe gateway deste tipo
        gateway = Gateway.query.filter_by(
            user_id=current_user.id,
            gateway_type=gateway_type
        ).first()
        
        if not gateway:
            logger.info(f"➕ Criando novo gateway {gateway_type} para usuário {current_user.id}")
            gateway = Gateway(
                user_id=current_user.id,
                gateway_type=gateway_type
            )
            db.session.add(gateway)
        else:
            logger.info(f"♻️ Atualizando gateway {gateway_type} existente (ID: {gateway.id})")
        
        # ✅ CORREÇÃO: Atualizar credenciais específicas de cada gateway
        if gateway_type == 'syncpay':
            gateway.client_id = data.get('client_id')
            gateway.client_secret = data.get('client_secret')
        
        elif gateway_type == 'pushynpay':
            gateway.api_key = data.get('api_key')
        
        elif gateway_type == 'paradise':
            gateway.api_key = data.get('api_key')
            gateway.product_hash = data.get('product_hash')
            gateway.offer_hash = data.get('offer_hash')
            # Store ID configurado automaticamente para splits (você é o dono do sistema)
            gateway.store_id = '177'
        
        elif gateway_type == 'wiinpay':
            # ✅ WIINPAY
            gateway.api_key = data.get('api_key')
            # Split User ID da plataforma (4% de comissão pelos serviços de automação)
            # Fallback para o ID da plataforma se não fornecido
            gateway.split_user_id = data.get('split_user_id', '6877edeba3c39f8451ba5bdd')
        
        # ✅ Split percentage (comum a todos)
        gateway.split_percentage = float(data.get('split_percentage', 2.0))  # 2% PADRÃO
        
        # IMPORTANTE: Desativar outros gateways do usuário antes de ativar este
        # Regra de negócio: Apenas 1 gateway ativo por usuário
        if data.get('is_active', True):  # Se requisição pede para ativar
            # Desativar todos outros gateways do usuário
            Gateway.query.filter(
                Gateway.user_id == current_user.id,
                Gateway.id != gateway.id  # Exceto o atual
            ).update({'is_active': False})
            
            gateway.is_active = True
            logger.info(f"✅ Gateway {gateway_type} ativado para {current_user.email} (outros desativados)")
        else:
            gateway.is_active = data.get('is_active', False)
        
        # Verificar credenciais
        try:
            # Montar credenciais conforme o gateway
            credentials = {
                'client_id': gateway.client_id,
                'client_secret': gateway.client_secret,
                'api_key': gateway.api_key,
                'product_hash': gateway.product_hash,  # Paradise
                'offer_hash': gateway.offer_hash,      # Paradise
                'store_id': gateway.store_id,          # Paradise
                'organization_id': gateway.organization_id,  # HooPay
                'split_user_id': gateway.split_user_id  # WiinPay
            }
            
            is_valid = bot_manager.verify_gateway(gateway_type, credentials)
            
            if is_valid:
                gateway.is_verified = True
                gateway.verified_at = datetime.now()
                gateway.last_error = None
                logger.info(f"Gateway {gateway_type} verificado para {current_user.email}")
            else:
                gateway.is_verified = False
                gateway.last_error = 'Credenciais inválidas'
        except Exception as e:
            gateway.is_verified = False
            gateway.last_error = str(e)
            logger.error(f"❌ Erro ao verificar gateway: {e}")
        
        db.session.commit()
        logger.info(f"✅ Gateway {gateway_type} salvo com sucesso!")
        
        # 🔄 RECARREGAR CONFIGURAÇÃO DOS BOTS ATIVOS DO USUÁRIO
        _reload_user_bots_config(current_user.id)
        
        return jsonify(gateway.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ ERRO CRÍTICO ao salvar gateway: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao salvar gateway: {str(e)}'}), 500

@app.route('/api/admin/restart-all-bots', methods=['POST'])
@login_required
@csrf.exempt
def api_restart_all_bots():
    """API para reinicializar todos os bots manualmente (admin)"""
    try:
        logger.info(f"🔄 Reinicialização manual solicitada por {current_user.email}")
        restart_all_active_bots()
        return jsonify({'success': True, 'message': 'Todos os bots foram reiniciados com sucesso!'})
    except Exception as e:
        logger.error(f"❌ Erro na reinicialização manual: {e}")
        return jsonify({'error': f'Erro ao reiniciar bots: {str(e)}'}), 500

@app.route('/api/admin/check-bots-status', methods=['GET'])
@login_required
@csrf.exempt
def api_check_bots_status():
    """API para verificar status dos bots (debug)"""
    try:
        with app.app_context():
            # Bots no banco
            db_bots = Bot.query.filter_by(is_active=True).all()
            
            # Bots ativos no bot_manager
            active_bots = list(bot_manager.active_bots.keys())
            
            result = {
                'db_bots': [
                    {
                        'id': bot.id,
                        'username': bot.username,
                        'is_active': bot.is_active
                    } for bot in db_bots
                ],
                'active_bots': active_bots,
                'total_db': len(db_bots),
                'total_active': len(active_bots),
                'missing': [bot.id for bot in db_bots if bot.id not in active_bots]
            }
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status dos bots: {e}")
        return jsonify({'error': f'Erro ao verificar bots: {str(e)}'}), 500

def _reload_user_bots_config(user_id: int):
    """Recarrega configuração dos bots ativos quando gateway muda"""
    try:
        from models import Bot
        
        # Buscar bots ativos do usuário
        active_bots = Bot.query.filter_by(user_id=user_id, is_active=True).all()
        
        for bot in active_bots:
            if bot.id in bot_manager.active_bots:
                logger.info(f"🔄 Recarregando configuração do bot {bot.id} (gateway mudou)")
                
                # Buscar configuração atualizada
                config = BotConfig.query.filter_by(bot_id=bot.id).first()
                if config:
                    # Atualizar configuração em memória
                    bot_manager.active_bots[bot.id]['config'] = config.to_dict()
                    logger.info(f"✅ Bot {bot.id} recarregado com novo gateway")
                else:
                    logger.warning(f"⚠️ Configuração não encontrada para bot {bot.id}")
                    
    except Exception as e:
        logger.error(f"❌ Erro ao recarregar bots do usuário {user_id}: {e}")

def restart_all_active_bots():
    """Reinicia automaticamente todos os bots ativos após deploy/restart do serviço"""
    try:
        logger.info("🔄 INICIANDO REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS...")
        
        # ✅ CORREÇÃO: Usar contexto do Flask para acessar banco
        with app.app_context():
            # Buscar todos os bots ativos
            active_bots = Bot.query.filter_by(is_active=True).all()
            
            if not active_bots:
                logger.info("ℹ️ Nenhum bot ativo encontrado para reiniciar")
                return
            
            logger.info(f"📊 Encontrados {len(active_bots)} bots ativos para reiniciar")
            
            restarted_count = 0
            failed_count = 0
            
            for bot in active_bots:
                try:
                    # Buscar configuração do bot
                    config = BotConfig.query.filter_by(bot_id=bot.id).first()
                    if not config:
                        logger.warning(f"⚠️ Configuração não encontrada para bot {bot.id} (@{bot.username})")
                        failed_count += 1
                        continue
                    
                    # Verificar se bot já está ativo no bot_manager
                    if bot.id in bot_manager.active_bots:
                        logger.info(f"♻️ Bot {bot.id} (@{bot.username}) já está ativo, pulando...")
                        continue
                    
                    # Reiniciar bot
                    logger.info(f"🚀 Reiniciando bot {bot.id} (@{bot.username})...")
                    bot_manager.start_bot(
                        bot_id=bot.id,
                        token=bot.token,
                        config=config.to_dict()
                    )
                    
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
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na reinicialização automática: {e}", exc_info=True)

@app.route('/api/gateways/<int:gateway_id>/toggle', methods=['POST'])
@login_required
@csrf.exempt
def toggle_gateway(gateway_id):
    """Ativa/desativa um gateway"""
    gateway = Gateway.query.filter_by(
        id=gateway_id,
        user_id=current_user.id
    ).first()
    
    if not gateway:
        return jsonify({'error': 'Gateway não encontrado'}), 404
    
    if not gateway.is_verified:
        return jsonify({'error': 'Gateway precisa estar verificado para ser ativado'}), 400
    
    # Se está ativando, desativar todos os outros
    if not gateway.is_active:
        Gateway.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).update({'is_active': False})
        
        gateway.is_active = True
        message = f'Gateway {gateway.gateway_type} ativado'
    else:
        gateway.is_active = False
        message = f'Gateway {gateway.gateway_type} desativado'
    
    db.session.commit()
    
    logger.info(f"Gateway {gateway.gateway_type} {'ativado' if gateway.is_active else 'desativado'} por {current_user.email}")
    
    return jsonify({
        'success': True,
        'message': message,
        'is_active': gateway.is_active
    })

@app.route('/api/gateways/<int:gateway_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_gateway(gateway_id):
    """Atualiza credenciais de um gateway"""
    try:
        gateway = Gateway.query.filter_by(id=gateway_id, user_id=current_user.id).first_or_404()
        data = request.json
        
        gateway_type = gateway.gateway_type
        
        # Atualizar campos conforme o tipo
        if gateway_type == 'syncpay':
            if data.get('client_id'):
                gateway.client_id = data['client_id']
            if data.get('client_secret'):
                gateway.client_secret = data['client_secret']
        
        elif gateway_type == 'pushynpay':
            if data.get('api_key'):
                gateway.api_key = data['api_key']
        
        elif gateway_type == 'paradise':
            if data.get('api_key'):
                gateway.api_key = data['api_key']
            if data.get('offer_hash'):
                gateway.offer_hash = data['offer_hash']
            if data.get('product_hash'):
                gateway.product_hash = data['product_hash']
        
        elif gateway_type == 'wiinpay':
            if data.get('api_key'):
                gateway.api_key = data['api_key']
            if data.get('split_user_id'):
                gateway.split_user_id = data['split_user_id']
        
        db.session.commit()
        
        logger.info(f"✅ Gateway {gateway_type} atualizado por {current_user.email}")
        
        return jsonify({
            'success': True,
            'message': f'Gateway {gateway_type} atualizado com sucesso'
        })
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar gateway: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gateways/<int:gateway_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_gateway(gateway_id):
    """Deleta um gateway"""
    gateway = Gateway.query.filter_by(id=gateway_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(gateway)
    db.session.commit()
    
    logger.info(f"Gateway {gateway.gateway_type} deletado por {current_user.email}")
    return jsonify({'message': 'Gateway deletado com sucesso'})

# ==================== CONFIGURAÇÕES ====================

@app.route('/gamification/profile')
@login_required
def gamification_profile():
    """Perfil de gamificação do usuário"""
    return render_template('gamification_profile.html')


@app.route('/ranking')
@login_required
def ranking():
    """Hall da Fama - Ranking público (otimizado)"""
    from sqlalchemy import func
    from models import BotUser, UserAchievement, Achievement
    from datetime import timedelta
    
    # Filtro de período (simplificado)
    period = request.args.get('period', 'month')  # month (padrão) ou all
    
    # ✅ CORREÇÃO CRÍTICA: NÃO recalcular em cada pageview
    # Usar pontos já calculados (atualizado por job em background ou webhook)
    # Cache seria ideal, mas por ora usar dados existentes
    
    # Definir período
    date_filter = None
    if period == 'today':
        date_filter = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        date_filter = datetime.now() - timedelta(days=7)
    elif period == 'month':
        date_filter = datetime.now() - timedelta(days=30)
    
    # ✅ CORREÇÃO: Adicionar desempate no ranking
    # Calcular ranking baseado no período
    if period == 'all':
        # Ranking all-time (ordenar por pontos + desempate)
        users_query = User.query.filter_by(is_admin=False, is_banned=False)\
                               .order_by(
                                   User.ranking_points.desc(),
                                   User.total_sales.desc(),  # Desempate 1: Mais vendas
                                   User.created_at.asc()      # Desempate 2: Mais antigo
                               )
    else:
        # Ranking do mês (período fixo)
        date_filter = datetime.now() - timedelta(days=30)
        
        # Calcular receita no mês
        if True:
            # Ranking por receita no período (mês)
                subquery = db.session.query(
                    Bot.user_id,
                func.sum(Payment.amount).label('period_revenue'),
                    func.count(Payment.id).label('period_sales')
                ).join(Payment)\
                 .filter(Payment.status == 'paid', Payment.created_at >= date_filter)\
                 .group_by(Bot.user_id)\
                 .subquery()
                
                users_query = User.query.join(subquery, User.id == subquery.c.user_id)\
                                       .filter(User.is_admin == False, User.is_banned == False)\
                                   .order_by(
                                       subquery.c.period_revenue.desc(),
                                       subquery.c.period_sales.desc(),
                                       User.created_at.asc()
                                   )
    
    # Top 100
    top_users = users_query.limit(100).all()
    
    # Enriquecer dados
    ranking_data = []
    for idx, user in enumerate(top_users, 1):
        # Estatísticas do usuário
        bots_count = Bot.query.filter_by(user_id=user.id).count()
        
        # Conquistas do usuário
        user_achievements = UserAchievement.query.filter_by(user_id=user.id).all()
        badges = [ua.achievement for ua in user_achievements]
        
        # Calcular stats do período
        if date_filter:
            period_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter
            ).scalar() or 0
            
            period_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter
            ).scalar() or 0.0
        else:
            # All-time
            period_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0
            
            period_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0.0
        
        ranking_data.append({
            'position': idx,
            'user': user,
            'bots_count': bots_count,
            'sales': period_sales,
            'revenue': float(period_revenue),
            'points': user.ranking_points,
            'badges': badges[:5],  # Top 5 badges
            'total_badges': len(badges),
            'streak': user.current_streak
        })
    
    # Encontrar posição do usuário atual
    my_position = next((item for item in ranking_data if item['user'].id == current_user.id), None)
    if not my_position:
        # Usuário não está no top 100, calcular posição real
        my_position_number = users_query.filter(User.ranking_points > current_user.ranking_points).count() + 1
    else:
        my_position_number = my_position['position']
    
    # Diferença para próxima posição
    next_user = None
    if my_position_number > 1:
        next_position_idx = my_position_number - 2  # -1 para índice, -1 para posição anterior
        if next_position_idx < len(ranking_data):
            next_user = ranking_data[next_position_idx]
    
    # ✅ AUTO-VERIFICAÇÃO: Checar achievements automaticamente quando acessar ranking
    try:
        # Verificar se achievements existem no banco
        total_achievements_db = Achievement.query.count()
        
        # Se não existir, criar achievements básicos
        if total_achievements_db == 0:
            logger.warning("⚠️ Criando achievements básicos...")
            basic_achievements = [
                {'name': 'Primeira Venda', 'description': 'Realize sua primeira venda', 'icon': '🎯', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 1, 'points': 50, 'rarity': 'common'},
                {'name': 'Vendedor Iniciante', 'description': 'Realize 10 vendas', 'icon': '📈', 'badge_color': 'blue', 'requirement_type': 'sales', 'requirement_value': 10, 'points': 100, 'rarity': 'common'},
                {'name': 'Vendedor Profissional', 'description': 'Realize 50 vendas', 'icon': '💼', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 50, 'points': 500, 'rarity': 'rare'},
                {'name': 'Primeiro R$ 100', 'description': 'Fature R$ 100 em vendas', 'icon': '💰', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 100, 'points': 100, 'rarity': 'common'},
                {'name': 'R$ 1.000 Faturados', 'description': 'Fature R$ 1.000 em vendas', 'icon': '💸', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 1000, 'points': 500, 'rarity': 'rare'},
                {'name': 'Consistência', 'description': 'Venda por 3 dias consecutivos', 'icon': '🔥', 'badge_color': 'orange', 'requirement_type': 'streak', 'requirement_value': 3, 'points': 200, 'rarity': 'common'},
                {'name': 'Taxa de Ouro', 'description': 'Atinja 50% de conversão', 'icon': '🎖️', 'badge_color': 'gold', 'requirement_type': 'conversion_rate', 'requirement_value': 50, 'points': 1000, 'rarity': 'epic'},
            ]
            for ach_data in basic_achievements:
                db.session.add(Achievement(**ach_data))
            db.session.commit()
            logger.info(f"✅ {len(basic_achievements)} achievements criados")
        
        # Verificar conquistas do usuário (leve, sem bloquear)
        if GAMIFICATION_V2_ENABLED:
            newly_unlocked = AchievementChecker.check_all_achievements(current_user)
            if newly_unlocked:
                logger.info(f"🎉 {len(newly_unlocked)} conquista(s) auto-desbloqueada(s) para {current_user.username}")
                
                # Recalcular pontos
                total_points = db.session.query(func.sum(Achievement.points))\
                    .join(UserAchievement)\
                    .filter(UserAchievement.user_id == current_user.id)\
                    .scalar() or 0
                current_user.ranking_points = int(total_points)
                db.session.commit()
    except Exception as e:
        logger.error(f"⚠️ Erro na auto-verificação de achievements: {e}")
    
    # Buscar conquistas do usuário
    my_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
    logger.info(f"📊 Ranking - Usuario {current_user.username} tem {len(my_achievements)} conquista(s)")
    
    return render_template('ranking.html',
                         ranking=ranking_data,
                         my_position=my_position_number,
                         next_user=next_user,
                         period=period,
                         my_achievements=my_achievements)

@app.route('/api/debug-achievements', methods=['GET'])
@login_required
def debug_achievements():
    """Debug completo do sistema de achievements"""
    from sqlalchemy import func
    
    try:
        # 1. Verificar tabelas
        total_achievements_db = Achievement.query.count()
        
        # 2. Stats do usuário
        total_sales = db.session.query(func.count(Payment.id))\
            .join(Bot).filter(
                Bot.user_id == current_user.id,
                Payment.status == 'paid'
            ).scalar() or 0
        
        total_revenue = db.session.query(func.sum(Payment.amount))\
            .join(Bot).filter(
                Bot.user_id == current_user.id,
                Payment.status == 'paid'
            ).scalar() or 0.0
        
        # 3. UserAchievements do usuário
        user_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
        
        # 4. Usar relationship
        achievements_via_rel = current_user.achievements
        
        return jsonify({
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'total_sales': total_sales,
                'total_revenue': float(total_revenue),
                'ranking_points': current_user.ranking_points
            },
            'database': {
                'total_achievements': total_achievements_db,
                'user_achievements_count': len(user_achievements),
                'relationship_count': len(achievements_via_rel)
            },
            'achievements': [
                {
                    'id': ua.id,
                    'achievement_name': ua.achievement.name,
                    'points': ua.achievement.points,
                    'unlocked_at': ua.unlocked_at.isoformat()
                } for ua in user_achievements
            ]
        })
    except Exception as e:
        logger.error(f"Erro no debug: {e}", exc_info=True)
        return jsonify({'error': str(e), 'traceback': str(e)}), 500

@app.route('/api/force-check-achievements', methods=['POST'])
@login_required
@csrf.exempt
def force_check_achievements():
    """Força verificação de achievements do usuário atual"""
    from sqlalchemy import func
    
    try:
        logger.info(f"🔍 Forçando verificação de achievements para {current_user.username}")
        
        # PRIMEIRO: Garantir que achievements existem no banco
        total_achievements_db = Achievement.query.count()
        if total_achievements_db == 0:
            logger.warning("⚠️ Nenhum achievement cadastrado! Criando agora...")
            
            # Criar achievements básicos
            basic_achievements = [
                {'name': 'Primeira Venda', 'description': 'Realize sua primeira venda', 'icon': '🎯', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 1, 'points': 50, 'rarity': 'common'},
                {'name': 'Vendedor Iniciante', 'description': 'Realize 10 vendas', 'icon': '📈', 'badge_color': 'blue', 'requirement_type': 'sales', 'requirement_value': 10, 'points': 100, 'rarity': 'common'},
                {'name': 'Vendedor Profissional', 'description': 'Realize 50 vendas', 'icon': '💼', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 50, 'points': 500, 'rarity': 'rare'},
                {'name': 'Primeiro R$ 100', 'description': 'Fature R$ 100 em vendas', 'icon': '💰', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 100, 'points': 100, 'rarity': 'common'},
                {'name': 'R$ 1.000 Faturados', 'description': 'Fature R$ 1.000 em vendas', 'icon': '💸', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 1000, 'points': 500, 'rarity': 'rare'},
                {'name': 'Consistência', 'description': 'Venda por 3 dias consecutivos', 'icon': '🔥', 'badge_color': 'orange', 'requirement_type': 'streak', 'requirement_value': 3, 'points': 200, 'rarity': 'common'},
                {'name': 'Taxa de Ouro', 'description': 'Atinja 50% de conversão', 'icon': '🎖️', 'badge_color': 'gold', 'requirement_type': 'conversion_rate', 'requirement_value': 50, 'points': 1000, 'rarity': 'epic'},
            ]
            
            for ach_data in basic_achievements:
                achievement = Achievement(**ach_data)
                db.session.add(achievement)
            
            db.session.commit()
            logger.info(f"✅ {len(basic_achievements)} achievements criados!")
        
        # SEGUNDO: Verificar conquistas
        newly_unlocked = AchievementChecker.check_all_achievements(current_user)
        
        # TERCEIRO: Recalcular pontos
        total_points = db.session.query(func.sum(Achievement.points))\
            .join(UserAchievement)\
            .filter(UserAchievement.user_id == current_user.id)\
            .scalar() or 0
        
        current_user.ranking_points = int(total_points)
        db.session.commit()
        
        total_achievements = UserAchievement.query.filter_by(user_id=current_user.id).count()
        
        logger.info(f"✅ Verificação concluída: {len(newly_unlocked)} novas | Total: {total_achievements}")
        
        return jsonify({
            'success': True,
            'newly_unlocked': len(newly_unlocked),
            'total_achievements': total_achievements,
            'ranking_points': current_user.ranking_points
        })
    except Exception as e:
        logger.error(f"❌ Erro ao forçar verificação: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/settings')
@login_required
def settings():
    """Página de configurações"""
    return render_template('settings.html')

@app.route('/api/user/profile', methods=['PUT'])
@login_required
@csrf.exempt
def update_profile():
    """Atualiza perfil do usuário"""
    data = request.json
    
    try:
        if 'full_name' in data:
            current_user.full_name = data['full_name']
        
        if 'email' in data and data['email'] != current_user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já cadastrado'}), 400
            current_user.email = data['email']
        
        db.session.commit()
        logger.info(f"Perfil atualizado: {current_user.email}")
        return jsonify(current_user.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar perfil: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/password', methods=['PUT'])
@login_required
@csrf.exempt
def update_password():
    """Atualiza senha do usuário"""
    data = request.json
    
    if not current_user.check_password(data.get('current_password')):
        return jsonify({'error': 'Senha atual incorreta'}), 400
    
    try:
        current_user.set_password(data.get('new_password'))
        db.session.commit()
        logger.info(f"Senha atualizada: {current_user.email}")
        return jsonify({'message': 'Senha atualizada com sucesso'})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar senha: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/bots/<int:bot_id>/meta-pixel')
@login_required
def meta_pixel_config_page(bot_id):
    """Página de configuração do Meta Pixel"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        return render_template('meta_pixel_config.html', bot=bot)
    except Exception as e:
        logger.error(f"Erro ao carregar página Meta Pixel: {e}")
        return redirect('/dashboard')

# ==================== META PIXEL INTEGRATION (DEPRECATED - MOVIDO PARA POOLS) ====================
# ❌ ATENÇÃO: Estas rotas foram DEPRECATED na V2.0
# Meta Pixel agora é configurado POR POOL (não por bot)
# Use as rotas /api/redirect-pools/<pool_id>/meta-pixel ao invés
# Estas rotas antigas permanecem apenas para retrocompatibilidade temporária

@app.route('/api/bots/<int:bot_id>/meta-pixel', methods=['GET'])
@login_required
def get_meta_pixel_config(bot_id):
    """
    [DEPRECATED] Retorna configuração atual do Meta Pixel do bot
    
    ATENÇÃO: Esta rota foi deprecated. Use /api/redirect-pools/<pool_id>/meta-pixel
    """
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        return jsonify({
            'meta_pixel_id': bot.meta_pixel_id,
            'meta_tracking_enabled': bot.meta_tracking_enabled,
            'meta_test_event_code': bot.meta_test_event_code,
            'meta_events_pageview': bot.meta_events_pageview,
            'meta_events_viewcontent': bot.meta_events_viewcontent,
            'meta_events_purchase': bot.meta_events_purchase,
            'meta_cloaker_enabled': bot.meta_cloaker_enabled,
            'meta_cloaker_param_name': bot.meta_cloaker_param_name,
            'meta_cloaker_param_value': bot.meta_cloaker_param_value,
            'has_access_token': bool(bot.meta_access_token)
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar configuração Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bots/<int:bot_id>/meta-pixel', methods=['PUT'])
@login_required
@csrf.exempt
def update_meta_pixel_config(bot_id):
    """Atualiza configuração do Meta Pixel do bot"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        data = request.get_json()
        
        # Validar dados obrigatórios se tracking estiver ativo
        if data.get('meta_tracking_enabled'):
            pixel_id = data.get('meta_pixel_id', '').strip()
            access_token = data.get('meta_access_token', '').strip()
            
            if not pixel_id:
                return jsonify({'error': 'Pixel ID é obrigatório quando tracking está ativo'}), 400
            
            if not access_token:
                return jsonify({'error': 'Access Token é obrigatório quando tracking está ativo'}), 400
            
            # Validar formato do Pixel ID
            from utils.meta_pixel import MetaPixelHelper
            if not MetaPixelHelper.is_valid_pixel_id(pixel_id):
                return jsonify({'error': 'Pixel ID deve ter 15-16 dígitos numéricos'}), 400
            
            # Validar formato do Access Token
            if not MetaPixelHelper.is_valid_access_token(access_token):
                return jsonify({'error': 'Access Token deve ter pelo menos 50 caracteres'}), 400
            
            # Testar conexão com Meta API
            from utils.meta_pixel import MetaPixelAPI
            test_result = MetaPixelAPI.test_connection(pixel_id, access_token)
            
            if not test_result['success']:
                return jsonify({'error': f'Falha na conexão com Meta API: {test_result["error"]}'}), 400
            
            # Criptografar access token
            from utils.encryption import encrypt
            bot.meta_access_token = encrypt(access_token)
            bot.meta_pixel_id = pixel_id
            
            logger.info(f"✅ Meta Pixel configurado para bot {bot_id}: Pixel {pixel_id}")
        
        # Atualizar configurações
        bot.meta_tracking_enabled = data.get('meta_tracking_enabled', False)
        bot.meta_test_event_code = data.get('meta_test_event_code', '').strip()
        bot.meta_events_pageview = data.get('meta_events_pageview', True)
        bot.meta_events_viewcontent = data.get('meta_events_viewcontent', True)
        bot.meta_events_purchase = data.get('meta_events_purchase', True)
        bot.meta_cloaker_enabled = data.get('meta_cloaker_enabled', False)
        bot.meta_cloaker_param_name = data.get('meta_cloaker_param_name', 'grim')
        
        # Gerar valor único para cloaker se ativado
        if bot.meta_cloaker_enabled and not bot.meta_cloaker_param_value:
            import uuid
            bot.meta_cloaker_param_value = uuid.uuid4().hex[:8]
        
        db.session.commit()
        
        return jsonify({
            'message': 'Configuração Meta Pixel atualizada com sucesso',
            'config': {
                'meta_pixel_id': bot.meta_pixel_id,
                'meta_tracking_enabled': bot.meta_tracking_enabled,
                'meta_events_pageview': bot.meta_events_pageview,
                'meta_events_viewcontent': bot.meta_events_viewcontent,
                'meta_events_purchase': bot.meta_events_purchase,
                'meta_cloaker_enabled': bot.meta_cloaker_enabled,
                'meta_cloaker_param_name': bot.meta_cloaker_param_name,
                'meta_cloaker_param_value': bot.meta_cloaker_param_value
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar configuração Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bots/<int:bot_id>/meta-pixel/test', methods=['POST'])
@login_required
@csrf.exempt
def test_meta_pixel_connection(bot_id):
    """Testa conexão com Meta Pixel"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        if not bot.meta_pixel_id or not bot.meta_access_token:
            return jsonify({'error': 'Pixel ID e Access Token são obrigatórios'}), 400
        
        # Descriptografar access token
        from utils.encryption import decrypt
        from utils.meta_pixel import MetaPixelAPI
        
        access_token = decrypt(bot.meta_access_token)
        
        # Testar conexão
        result = MetaPixelAPI.test_connection(bot.meta_pixel_id, access_token)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Conexão com Meta Pixel bem-sucedida',
                'pixel_info': result['pixel_info']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        logger.error(f"Erro ao testar Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500

def send_meta_pixel_pageview_event(pool, request):
    """
    Enfileira evento PageView para Meta Pixel (ASSÍNCRONO - MVP DIA 2)
    
    ARQUITETURA V4.0 - ASYNC (QI 540):
    - NÃO BLOQUEIA o redirect (< 5ms)
    - Enfileira evento no Celery
    - Worker processa em background
    - Retry persistente se falhar
    - ✅ RETORNA external_id e utm_data IMEDIATAMENTE
    
    CRÍTICO: Não espera resposta da Meta API
    
    Returns:
        tuple: (external_id, utm_data) para vincular eventos posteriores
    """
    try:
        # ✅ VERIFICAÇÃO 1: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return None, {}
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return None, {}
        
        # ✅ VERIFICAÇÃO 2: Evento PageView está habilitado?
        if not pool.meta_events_pageview:
            logger.info(f"Evento PageView desabilitado para pool {pool.id}")
            return None, {}
        
        # Importar helpers
        from utils.meta_pixel import MetaPixelHelper
        from utils.encryption import decrypt
        import time
        
        # Gerar external_id único
        external_id = MetaPixelHelper.generate_external_id()
        event_id = f"pageview_{pool.id}_{int(time.time())}_{external_id[:8]}"
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return None, {}
        
        # Extrair UTM parameters e cookies
        utm_params = MetaPixelHelper.extract_utm_params(request)
        cookies = MetaPixelHelper.extract_cookies(request)
        
        # ✅ CAPTURAR DADOS PARA RETORNAR
        utm_data = {
            'utm_source': utm_params.get('utm_source'),
            'utm_campaign': utm_params.get('utm_campaign'),
            'utm_content': utm_params.get('utm_content'),
            'utm_medium': utm_params.get('utm_medium'),
            'utm_term': utm_params.get('utm_term'),
            'fbclid': utm_params.get('fbclid'),
            'campaign_code': utm_params.get('code')
        }
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO (ASSÍNCRONO - NÃO BLOQUEIA!)
        # ============================================================================
        from celery_app import send_meta_event
        
        event_data = {
            'event_name': 'PageView',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'user_data': {
                'external_id': external_id,
                'client_ip_address': request.remote_addr,
                'client_user_agent': request.headers.get('User-Agent', ''),
                'fbp': cookies.get('_fbp'),
                'fbc': cookies.get('_fbc')
            },
            'custom_data': {
                'pool_id': pool.id,
                'pool_name': pool.name,
                'utm_source': utm_data['utm_source'],
                'utm_campaign': utm_data['utm_campaign'],
                'utm_content': utm_data['utm_content'],
                'utm_medium': utm_data['utm_medium'],
                'utm_term': utm_data['utm_term'],
                'fbclid': utm_data['fbclid'],
                'campaign_code': utm_data['campaign_code']
            }
        }
        
        # ✅ ENFILEIRAR (NÃO ESPERA RESPOSTA)
        task = send_meta_event.delay(
            pixel_id=pool.meta_pixel_id,
            access_token=access_token,
            event_data=event_data,
            test_code=pool.meta_test_event_code
        )
        
        logger.info(f"📤 PageView enfileirado: Pool {pool.id} | Event ID: {event_id} | Task: {task.id}")
        
        # ✅ RETORNAR IMEDIATAMENTE (não espera envio!)
        return external_id, utm_data
    
    except Exception as e:
        logger.error(f"💥 Erro ao enfileirar Meta PageView: {e}")
        # Não impedir o redirect se Meta falhar
        return None, {}

def send_meta_pixel_purchase_event(payment):
    """
    Envia evento Purchase para Meta Pixel quando pagamento é confirmado
    
    ARQUITETURA V2.0 (QI 240):
    - Busca pixel do POOL associado ao bot (não do bot diretamente)
    - Alta disponibilidade: dados consolidados no pool
    - Tracking preciso mesmo com múltiplos bots
    
    CRÍTICO: Zero duplicação garantida via meta_purchase_sent flag
    """
    try:
        # ✅ VERIFICAÇÃO 1: Buscar pool associado ao bot
        from models import PoolBot
        
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        
        if not pool_bot:
            logger.info(f"Bot {payment.bot_id} não está associado a nenhum pool - Meta Pixel ignorado")
            return
        
        pool = pool_bot.pool
        
        # ✅ VERIFICAÇÃO 2: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return
        
        # ✅ VERIFICAÇÃO 3: Evento Purchase está habilitado?
        if not pool.meta_events_purchase:
            logger.info(f"Evento Purchase desabilitado para pool {pool.id}")
            return
        
        # ✅ VERIFICAÇÃO 4: Já enviou este pagamento? (ANTI-DUPLICAÇÃO)
        if payment.meta_purchase_sent:
            logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando: {payment.payment_id}")
            return
        
        logger.info(f"📊 Preparando envio Meta Purchase: {payment.payment_id} | Pool: {pool.name}")
        
        # Importar Meta Pixel API
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        
        # Gerar event_id único para deduplicação
        event_id = MetaPixelAPI._generate_event_id(
            event_type='purchase',
            unique_id=payment.payment_id
        )
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return
        
        # Determinar tipo de venda (QI 540 - FIX BUG)
        is_downsell = payment.is_downsell or False
        is_upsell = payment.is_upsell or False
        is_remarketing = payment.is_remarketing or False
        
        # Buscar BotUser para pegar IP e User-Agent
        from models import BotUser
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=int(payment.customer_user_id.replace('user_', '')) if payment.customer_user_id and payment.customer_user_id.startswith('user_') else None
        ).first()
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO PURCHASE (ASSÍNCRONO - MVP DIA 2)
        # ============================================================================
        from celery_app import send_meta_event
        import time
        
        event_data = {
            'event_name': 'Purchase',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'user_data': {
                'external_id': bot_user.external_id if bot_user else f'payment_{payment.id}',
                'client_ip_address': bot_user.ip_address if bot_user else None,
                'client_user_agent': bot_user.user_agent if bot_user else None
            },
            'custom_data': {
                'currency': 'BRL',
                'value': float(payment.amount),
                'content_id': str(pool.id),
                'content_name': payment.product_name or payment.bot.name,
                'content_type': 'product',
                'payment_id': payment.payment_id,
                'is_downsell': is_downsell,
                'is_upsell': is_upsell,
                'is_remarketing': is_remarketing,
                'utm_source': payment.utm_source,
                'utm_campaign': payment.utm_campaign,
                'campaign_code': payment.campaign_code
            }
        }
        
        # ✅ ENFILEIRAR COM PRIORIDADE ALTA (Purchase é crítico!)
        task = send_meta_event.apply_async(
            args=[
                pool.meta_pixel_id,
                access_token,
                event_data,
                pool.meta_test_event_code
            ],
            priority=1  # Alta prioridade
        )
        
        # Marcar como enviado IMEDIATAMENTE (flag otimista)
        payment.meta_purchase_sent = True
        payment.meta_purchase_sent_at = datetime.now()
        payment.meta_event_id = event_id
        
        logger.info(f"📤 Purchase enfileirado: R$ {payment.amount} | " +
                   f"Pool: {pool.name} | " +
                   f"Event ID: {event_id} | " +
                   f"Task: {task.id} | " +
                   f"Type: {'Downsell' if is_downsell else 'Upsell' if is_upsell else 'Remarketing' if is_remarketing else 'Normal'}")
    
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta Purchase: {e}")
        # Não impedir o commit do pagamento se Meta falhar

# ==================== WEBHOOKS E NOTIFICAÇÕES EM TEMPO REAL ====================

@app.route('/webhook/telegram/<int:bot_id>', methods=['POST'])
@limiter.limit("1000 per minute")  # ✅ PROTEÇÃO: Webhooks legítimos mas limitados
@csrf.exempt  # ✅ Webhooks externos não enviam CSRF token
def telegram_webhook(bot_id):
    """Webhook para receber updates do Telegram"""
    try:
        update = request.json
        
        # ✅ SEGURANÇA: Validar que bot_id existe e pertence a algum usuário
        bot = Bot.query.get(bot_id)
        if not bot:
            logger.warning(f"⚠️ Webhook recebido para bot inexistente: {bot_id}")
            return jsonify({'status': 'ok'}), 200  # Retornar 200 para não revelar estrutura
        
        logger.info(f"Update recebido do Telegram para bot {bot_id}")
        
        # Processar update
        bot_manager._process_telegram_update(bot_id, update)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook Telegram: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")  # ✅ PROTEÇÃO: Webhooks de pagamento
@csrf.exempt  # ✅ Webhooks externos não enviam CSRF token
def payment_webhook(gateway_type):
    """Webhook para confirmação de pagamento"""
    data = request.json
    logger.info(f"Webhook recebido de {gateway_type}: {data}")
    
    try:
        # Processar webhook do gateway
        result = bot_manager.process_payment_webhook(gateway_type, data)
        
        if result:
            payment_id = result.get('payment_id')
            status = result.get('status')
            
            # Buscar pagamento no banco (pode vir pelo payment_id ou gateway_transaction_id)
            payment = (Payment.query.filter_by(payment_id=payment_id).first() or
                      Payment.query.filter_by(gateway_transaction_id=payment_id).first())
            
            if payment:
                # Verificar se já foi processado (idempotência)
                if payment.status == 'paid':
                    logger.info(f"⚠️ Webhook duplicado ignorado: {payment_id} já está pago")
                    return jsonify({'status': 'already_processed'}), 200
                
                payment.status = status
                if status == 'paid':
                    payment.paid_at = datetime.now()
                    payment.bot.total_sales += 1
                    payment.bot.total_revenue += payment.amount
                    payment.bot.owner.total_sales += payment.amount
                    payment.bot.owner.total_revenue += payment.amount
                    
                    # ✅ ATUALIZAR ESTATÍSTICAS DO GATEWAY
                    if payment.gateway_type:
                        gateway = Gateway.query.filter_by(
                            user_id=payment.bot.user_id,
                            gateway_type=payment.gateway_type
                        ).first()
                        if gateway:
                            gateway.total_transactions += 1
                            gateway.successful_transactions += 1
                            logger.info(f"✅ Estatísticas do gateway {gateway.gateway_type} atualizadas: {gateway.total_transactions} transações, {gateway.successful_transactions} bem-sucedidas")
                    
                    # REGISTRAR COMISSÃO
                    from models import Commission
                    
                    # Verificar se já existe comissão para este pagamento
                    existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
                    
                    if not existing_commission:
                        # Calcular e registrar receita da plataforma (split payment automático)
                        commission_amount = payment.bot.owner.add_commission(payment.amount)  # ✅ CORRIGIDO: add_commission() atualiza total_commission_owed
                        
                        commission = Commission(
                            user_id=payment.bot.owner.id,
                            payment_id=payment.id,
                            bot_id=payment.bot.id,
                            sale_amount=payment.amount,
                            commission_amount=commission_amount,
                            commission_rate=payment.bot.owner.commission_percentage,
                            status='paid',  # Split payment cai automaticamente
                            paid_at=datetime.now()  # Pago no mesmo momento da venda
                        )
                        db.session.add(commission)
                        
                        # Atualizar receita já paga (split automático via SyncPay)
                        payment.bot.owner.total_commission_paid += commission_amount
                        
                        logger.info(f"💰 Receita da plataforma: R$ {commission_amount:.2f} (split automático) - Usuário: {payment.bot.owner.email}")
                    
                    # ============================================================================
                    # ✅ META PIXEL: ENVIAR PURCHASE EVENT
                    # ============================================================================
                    send_meta_pixel_purchase_event(payment)
                    
                    # ============================================================================
                    # GAMIFICAÇÃO V2.0 - ATUALIZAR STREAK, RANKING E CONQUISTAS
                    # ============================================================================
                    if GAMIFICATION_V2_ENABLED:
                        try:
                            # Atualizar streak
                            payment.bot.owner.update_streak(payment.created_at)
                            
                            # Recalcular ranking com algoritmo V2
                            old_points = payment.bot.owner.ranking_points or 0
                            payment.bot.owner.ranking_points = RankingEngine.calculate_points(payment.bot.owner)
                            new_points = payment.bot.owner.ranking_points
                            
                            # Verificar conquistas V2
                            new_achievements = AchievementChecker.check_all_achievements(payment.bot.owner)
                            
                            if new_achievements:
                                logger.info(f"🎉 {len(new_achievements)} conquista(s) V2 desbloqueada(s)!")
                                
                                # Notificar via WebSocket
                                from gamification_websocket import notify_achievement_unlocked
                                for ach in new_achievements:
                                    notify_achievement_unlocked(socketio, payment.bot.owner.id, ach)
                            
                            # Atualizar ligas (pode ser async em produção)
                            RankingEngine.update_leagues()
                            
                            logger.info(f"📊 Gamificação V2: {old_points:,} → {new_points:,} pts")
                            
                        except Exception as e:
                            logger.error(f"❌ Erro na gamificação V2: {e}")
                    else:
                        # Fallback para sistema V1 (antigo)
                        payment.bot.owner.update_streak(payment.created_at)
                        payment.bot.owner.ranking_points = payment.bot.owner.calculate_ranking_points()
                        new_badges = check_and_unlock_achievements(payment.bot.owner)
                        
                        if new_badges:
                            logger.info(f"🎉 {len(new_badges)} nova(s) conquista(s) desbloqueada(s)!")
                    
                    # ENVIAR LINK DE ACESSO AUTOMATICAMENTE
                    if payment.bot.config and payment.bot.config.access_link:
                        access_link = payment.bot.config.access_link
                        
                        # Montar mensagem de acesso
                        access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

Aproveite! 🚀
                        """
                        
                        # Enviar via bot manager
                        try:
                            bot_manager.send_telegram_message(
                                token=payment.bot.token,
                                chat_id=payment.customer_user_id,
                                message=access_message.strip()
                            )
                            logger.info(f"✅ Link de acesso enviado para {payment.customer_name}")
                        except Exception as e:
                            logger.error(f"Erro ao enviar link de acesso: {e}")
                    
                    # ============================================================================
                    # ✅ UPSELLS AUTOMÁTICOS - APÓS COMPRA APROVADA
                    # ============================================================================
                    if payment.bot.config and payment.bot.config.upsells_enabled:
                        try:
                            upsells = payment.bot.config.get_upsells()
                            
                            if upsells:
                                logger.info(f"🎯 Verificando upsells para produto: {payment.product_name}")
                                
                                # Filtrar upsells que fazem match com o produto comprado
                                matched_upsells = []
                                for upsell in upsells:
                                    trigger_product = upsell.get('trigger_product', '')
                                    
                                    # Match: trigger vazio (todas compras) OU produto específico
                                    if not trigger_product or trigger_product == payment.product_name:
                                        matched_upsells.append(upsell)
                                
                                if matched_upsells:
                                    logger.info(f"✅ {len(matched_upsells)} upsell(s) encontrado(s)")
                                    
                                    # ✅ REUTILIZAR função de downsell (mesma lógica, só muda o nome)
                                    bot_manager.schedule_downsells(
                                        bot_id=payment.bot_id,
                                        payment_id=payment.payment_id,
                                        chat_id=int(payment.customer_user_id),
                                        downsells=matched_upsells,  # Formato idêntico ao downsell
                                        original_price=payment.amount,
                                        original_button_index=-1
                                    )
                                    
                                    logger.info(f"📅 Upsells agendados com sucesso!")
                                else:
                                    logger.info(f"ℹ️ Nenhum upsell configurado para '{payment.product_name}'")
                            else:
                                logger.info(f"ℹ️ Lista de upsells vazia")
                                
                        except Exception as e:
                            logger.error(f"❌ Erro ao processar upsells: {e}")
                            import traceback
                            traceback.print_exc()
                
                db.session.commit()
                
                # Notificar em tempo real via WebSocket
                socketio.emit('payment_update', {
                    'payment_id': payment_id,
                    'status': status,
                    'bot_id': payment.bot_id,
                    'amount': payment.amount,
                    'customer_name': payment.customer_name
                }, room=f'user_{payment.bot.user_id}')
                
                logger.info(f"💰 Pagamento atualizado: {payment_id} - {status}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect(auth=None):
    """Cliente conectado via WebSocket"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        emit('connected', {'user_id': current_user.id})
        logger.info(f"User {current_user.id} conectado via WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado via WebSocket"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        logger.info(f"User {current_user.id} desconectado via WebSocket")

@socketio.on('subscribe_bot')
def handle_subscribe_bot(data):
    """Inscrever em atualizações de um bot específico"""
    if not current_user.is_authenticated:
        return
    
    bot_id = data.get('bot_id')
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
    
    if bot:
        join_room(f'bot_{bot_id}')
        emit('subscribed', {'bot_id': bot_id})
        logger.info(f"User {current_user.id} inscrito em bot {bot_id}")

# ==================== TRATAMENTO DE ERROS ====================

@app.errorhandler(404)
def not_found(error):
    """Página não encontrada"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Recurso não encontrado'}), 404
    
    # Usar template seguro para evitar loop de erros
    try:
        return render_template('404.html'), 404
    except:
        return render_template('404_safe.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Erro interno do servidor"""
    db.session.rollback()
    logger.error(f"Erro 500: {error}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erro interno do servidor'}), 500
    
    # Usar template seguro para evitar loop de erros
    try:
        return render_template('500.html'), 500
    except:
        return '<h1>500 - Erro Interno</h1><a href="/">Voltar</a>', 500

# ==================== INICIALIZAÇÃO ====================

@app.route('/api/dashboard/check-updates', methods=['GET'])
@login_required
def check_dashboard_updates():
    """API para verificar se há novos pagamentos"""
    try:
        last_check_timestamp = request.args.get('last_check', type=float)
        
        # Buscar pagamentos dos bots do usuário
        user_bot_ids = [bot.id for bot in current_user.bots]
        
        if not user_bot_ids:
            return jsonify({'has_new_payments': False, 'new_count': 0, 'latest_payment_id': 0})
        
        # Se não tem timestamp, retornar o ID do último pagamento sem notificar
        if not last_check_timestamp:
            latest_payment = Payment.query.filter(
                Payment.bot_id.in_(user_bot_ids)
            ).order_by(Payment.id.desc()).first()
            
            return jsonify({
                'has_new_payments': False,
                'new_count': 0,
                'latest_payment_id': latest_payment.id if latest_payment else 0
            })
        
        # Converter timestamp para datetime
        from datetime import datetime
        last_check_dt = datetime.fromtimestamp(last_check_timestamp)
        
        # Buscar pagamentos criados após o último check
        new_payments_query = Payment.query.filter(
            Payment.bot_id.in_(user_bot_ids),
            Payment.created_at > last_check_dt
        )
        
        new_count = new_payments_query.count()
        has_new = new_count > 0
        
        if has_new:
            logger.info(f"📊 Dashboard: {new_count} novo(s) pagamento(s) para user {current_user.id}")
        
        # Pegar o ID do último pagamento
        latest_payment = Payment.query.filter(
            Payment.bot_id.in_(user_bot_ids)
        ).order_by(Payment.id.desc()).first()
        
        return jsonify({
            'has_new_payments': has_new,
            'new_count': new_count,
            'latest_payment_id': latest_payment.id if latest_payment else 0
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar atualizações do dashboard: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/simulate-payment/<int:payment_id>', methods=['POST'])
@login_required
def simulate_payment(payment_id):
    """Simular confirmação de pagamento para testes"""
    try:
        payment = db.session.get(Payment, payment_id)
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        if payment.bot.owner.id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Simular webhook da SyncPay
        webhook_data = {
            'identifier': payment.gateway_transaction_id,
            'status': 'paid',
            'amount': payment.amount
        }
        
        # Processar webhook
        result = bot_manager.process_payment_webhook('syncpay', webhook_data)
        
        if result:
            payment.status = 'paid'
            payment.paid_at = datetime.now()
            payment.bot.total_sales += 1
            payment.bot.total_revenue += payment.amount
            
            # ✅ ATUALIZAR ESTATÍSTICAS DO GATEWAY
            if payment.gateway_type:
                gateway = Gateway.query.filter_by(
                    user_id=payment.bot.user_id,
                    gateway_type=payment.gateway_type
                ).first()
                if gateway:
                    gateway.total_transactions += 1
                    gateway.successful_transactions += 1
                    logger.info(f"✅ [SIMULAR] Estatísticas do gateway {gateway.gateway_type} atualizadas")
            
            # Registrar comissão
            from models import Commission
            existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
            
            if not existing_commission:
                commission_amount = payment.bot.owner.add_commission(payment.amount)  # ✅ CORRIGIDO: add_commission() atualiza total_commission_owed
                commission = Commission(
                    user_id=payment.bot.owner.id,
                    payment_id=payment.id,
                    bot_id=payment.bot.id,
                    sale_amount=payment.amount,
                    commission_amount=commission_amount,
                    commission_rate=payment.bot.owner.commission_percentage,
                    status='paid',  # Split payment cai automaticamente
                    paid_at=datetime.now()  # Pago no mesmo momento
                )
                db.session.add(commission)
                # Split payment - receita já caiu automaticamente via SyncPay
                payment.bot.owner.total_commission_paid += commission_amount
            
            # ============================================================================
            # ✅ META PIXEL: ENVIAR PURCHASE EVENT (SIMULAÇÃO)
            # ============================================================================
            send_meta_pixel_purchase_event(payment)
            
            # ============================================================================
            # GAMIFICAÇÃO V2.0 - SIMULAR PAGAMENTO
            # ============================================================================
            if GAMIFICATION_V2_ENABLED:
                try:
                    # Atualizar streak
                    payment.bot.owner.update_streak(payment.created_at)
                    
                    # Recalcular ranking
                    payment.bot.owner.ranking_points = RankingEngine.calculate_points(payment.bot.owner)
                    
                    # Verificar conquistas
                    new_achievements = AchievementChecker.check_all_achievements(payment.bot.owner)
                    
                    if new_achievements:
                        logger.info(f"🎉 {len(new_achievements)} conquista(s) V2 desbloqueada(s) (simulação)!")
                        
                        from gamification_websocket import notify_achievement_unlocked
                        for ach in new_achievements:
                            notify_achievement_unlocked(socketio, payment.bot.owner.id, ach)
                    
                    # Atualizar ligas
                    RankingEngine.update_leagues()
                    
                except Exception as e:
                    logger.error(f"❌ Erro na gamificação V2 (simulação): {e}")
            
            db.session.commit()
            
            logger.info(f"🎯 Pagamento {payment_id} simulado como PAGO")
            
            return jsonify({'status': 'success', 'message': 'Pagamento simulado com sucesso'}), 200
        else:
            return jsonify({'error': 'Erro ao processar webhook'}), 500
            
    except Exception as e:
        logger.error(f"Erro ao simular pagamento: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def init_db():
    """Inicializa o banco de dados"""
    with app.app_context():
        db.create_all()
        logger.info("Banco de dados inicializado")


# ==================== HEALTH CHECK DE POOLS (Background Job) ====================

def health_check_all_pools():
    """
    Health Check de todos os bots em todos os pools ativos
    
    Executa a cada 15 segundos via APScheduler
    
    FUNCIONALIDADES:
    - Valida token com Telegram API
    - Atualiza status (online, offline, degraded)
    - Circuit Breaker (3 falhas = bloqueio 2min)
    - Atualiza métricas do pool
    - Notifica usuário se pool ficar crítico
    """
    with app.app_context():
        try:
            pools = RedirectPool.query.filter_by(is_active=True).all()
            
            for pool in pools:
                for pool_bot in pool.pool_bots.filter_by(is_enabled=True).all():
                    try:
                        # Verificar circuit breaker
                        if pool_bot.circuit_breaker_until:
                            if pool_bot.circuit_breaker_until > datetime.now():
                                continue  # Ainda bloqueado
                            else:
                                pool_bot.circuit_breaker_until = None  # Liberado
                        
                        # Health check no Telegram
                        health = bot_manager.validate_token(pool_bot.bot.token)
                        
                        # Bot está saudável
                        pool_bot.status = 'online'
                        pool_bot.consecutive_failures = 0
                        pool_bot.last_error = None
                        pool_bot.last_health_check = datetime.now()
                        
                    except Exception as e:
                        # Bot falhou
                        pool_bot.consecutive_failures += 1
                        pool_bot.last_error = str(e)
                        pool_bot.last_health_check = datetime.now()
                        
                        if pool_bot.consecutive_failures >= 3:
                            # 3 falhas = offline + circuit breaker
                            pool_bot.status = 'offline'
                            pool_bot.circuit_breaker_until = datetime.now() + timedelta(minutes=2)
                            
                            logger.error(f"Bot @{pool_bot.bot.username} no pool {pool.name} OFFLINE (3 falhas)")
                            
                            # Emitir evento WebSocket
                            socketio.emit('pool_bot_down', {
                                'pool_id': pool.id,
                                'pool_name': pool.name,
                                'bot_username': pool_bot.bot.username,
                                'error': str(e)
                            }, room=f'user_{pool.user_id}')
                        else:
                            pool_bot.status = 'degraded'
                
                # Atualizar saúde geral do pool
                pool.update_health()
                
                # Alerta se pool crítico (< 50% saúde)
                if pool.health_percentage < 50 and pool.total_bots_count > 0:
                    logger.warning(f"Pool {pool.name} CRÍTICO: {pool.health_percentage}% saúde")
                    
                    socketio.emit('pool_critical', {
                        'pool_id': pool.id,
                        'pool_name': pool.name,
                        'health': pool.health_percentage,
                        'online_bots': pool.healthy_bots_count,
                        'total_bots': pool.total_bots_count
                    }, room=f'user_{pool.user_id}')
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Erro no health check de pools: {e}")
            db.session.rollback()


# Agendar health check a cada 15 segundos
scheduler.add_job(
    id='health_check_pools',
    func=health_check_all_pools,
    trigger='interval',
    seconds=15,
    replace_existing=True
)


if __name__ == '__main__':
    init_db()
    
    # 🔄 REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS APÓS DEPLOY
    restart_all_active_bots()
    
    # Modo de desenvolvimento
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("\n" + "="*60)
    print("BOT MANAGER SAAS - SERVIDOR INICIADO")
    print("="*60)
    print(f"Servidor: http://localhost:{port}")
    print(f"Polling: APScheduler (ativo)")
    print(f"WebSocket: Socket.IO (ativo)")
    print(f"Geracao de PIX: SyncPay (integrado)")
    print("="*60)
    print("Aguardando acoes...\n")
    
    socketio.run(app, debug=debug, host='0.0.0.0', port=port, log_output=False, allow_unsafe_werkzeug=True)

