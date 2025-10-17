"""
SaaS Bot Manager - Aplicação Principal
Sistema de gerenciamento de bots do Telegram com painel web
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, Bot, BotConfig, Gateway, Payment, AuditLog, Achievement, UserAchievement, BotUser, RedirectPool, PoolBot
from bot_manager import BotManager
from datetime import datetime, timedelta
from functools import wraps
import os
import logging
import json
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

# Registrar blueprint de gamificação
if GAMIFICATION_V2_ENABLED:
    from gamification_api import gamification_bp
    app.register_blueprint(gamification_bp)
    logger.info("✅ API de Gamificação V2.0 registrada")

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
    
    # Converter bot_stats para dicionários
    bots_list = [{
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
    } for b in bot_stats]
    
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
    return jsonify([bot.to_dict() for bot in bots])

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
def update_bot_token(bot_id):
    """
    Atualiza o token de um bot (CRÍTICO para recuperação de bot banido)
    
    REQUISITOS:
    - Bot deve estar parado
    - Token novo obrigatório
    - Validação do token com Telegram
    - Token deve ser único no sistema
    - Atualiza bot_id e username automaticamente
    - Mantém TODAS as configurações do fluxo
    """
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    new_token = data.get('token', '').strip()
    
    # VALIDAÇÃO 1: Token obrigatório
    if not new_token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    
    # VALIDAÇÃO 2: Bot deve estar parado
    if bot.is_running:
        return jsonify({'error': 'Pare o bot antes de trocar o token'}), 400
    
    # VALIDAÇÃO 3: Token diferente do atual
    if new_token == bot.token:
        return jsonify({'error': 'Este token já está em uso neste bot'}), 400
    
    # VALIDAÇÃO 4: Token único no sistema (exceto o bot atual)
    existing_bot = Bot.query.filter(Bot.token == new_token, Bot.id != bot_id).first()
    if existing_bot:
        return jsonify({'error': 'Este token já está cadastrado em outro bot'}), 400
    
    try:
        # VALIDAÇÃO 5: Token válido no Telegram
        bot_info = bot_manager.validate_token(new_token)
        
        # Armazenar dados antigos para log
        old_token_preview = bot.token[:10] + '...'
        old_username = bot.username
        old_bot_id = bot.bot_id
        
        # ATUALIZAR BOT (mantém todas as configurações)
        bot.token = new_token
        bot.username = bot_info.get('username')
        bot.bot_id = str(bot_info.get('id'))
        
        db.session.commit()
        
        logger.info(f"Token atualizado: Bot {bot.name} | @{old_username} → @{bot.username} | ID {old_bot_id} → {bot.bot_id} | por {current_user.email}")
        
        return jsonify({
            'message': 'Token atualizado com sucesso!',
            'bot': bot.to_dict(),
            'changes': {
                'old_username': old_username,
                'new_username': bot.username,
                'old_bot_id': old_bot_id,
                'new_bot_id': bot.bot_id,
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
                        bot_id=bot.id,
                        campaign_id=campaign.id
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

@app.route('/api/bots/<int:bot_id>/stats', methods=['GET'])
@login_required
def get_bot_stats(bot_id):
    """API para estatísticas detalhadas de um bot específico"""
    from sqlalchemy import func, extract, case
    from models import BotUser
    from datetime import datetime, timedelta
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # 1. ESTATÍSTICAS GERAIS
    total_users = BotUser.query.filter_by(bot_id=bot_id).count()
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

@app.route('/api/bots/<int:bot_id>/config', methods=['GET'])
@login_required
def get_bot_config(bot_id):
    """Obtém configuração de um bot"""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        if not bot.config:
            logger.warning(f"⚠️ Bot {bot_id} não tem config, criando nova...")
            config = BotConfig(bot_id=bot.id)
            db.session.add(config)
            db.session.commit()
            db.session.refresh(config)
        
        config_dict = bot.config.to_dict()
        logger.info(f"📦 Retornando config do bot {bot_id}: {config_dict}")
        
        return jsonify(config_dict)
    except Exception as e:
        logger.error(f"❌ Erro ao buscar config do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao buscar configuração: {str(e)}'}), 500

@app.route('/api/bots/<int:bot_id>/config', methods=['PUT'])
@login_required
@csrf.exempt
def update_bot_config(bot_id):
    """Atualiza configuração de um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    data = request.json
    
    if not bot.config:
        config = BotConfig(bot_id=bot.id)
        db.session.add(config)
    else:
        config = bot.config
    
    try:
        # Atualizar campos
        if 'welcome_message' in data:
            config.welcome_message = data['welcome_message']
        if 'welcome_media_url' in data:
            config.welcome_media_url = data['welcome_media_url']
        if 'welcome_media_type' in data:
            config.welcome_media_type = data['welcome_media_type']
        
        # Botões principais
        if 'main_buttons' in data:
            config.set_main_buttons(data['main_buttons'])
        
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
        
        db.session.commit()
        
        # Se bot está rodando, atualizar configuração em tempo real
        if bot.is_running:
            bot_manager.update_bot_config(bot.id, config.to_dict())
        
        logger.info(f"Configuração do bot {bot.name} atualizada por {current_user.email}")
        return jsonify(config.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar configuração: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== LOAD BALANCER / REDIRECT POOLS ====================

@app.route('/go/<slug>')
def public_redirect(slug):
    """
    Endpoint PÚBLICO de redirecionamento com Load Balancing
    
    URL: /go/{slug} (ex: /go/red1)
    
    FUNCIONALIDADES:
    - Busca pool pelo slug
    - Seleciona bot online (estratégia configurada)
    - Health check em cache (não valida em tempo real)
    - Failover automático
    - Circuit breaker
    - Métricas de uso
    """
    from datetime import datetime
    
    # Buscar pool ativo
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    if not pool:
        abort(404, f'Pool "{slug}" não encontrado ou inativo')
    
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
    
    # Emitir evento WebSocket para o dono do pool
    socketio.emit('pool_redirect', {
        'pool_id': pool.id,
        'pool_name': pool.name,
        'bot_username': pool_bot.bot.username,
        'total_redirects': pool.total_redirects
    }, room=f'user_{pool.user_id}')
    
    # Redirect 302 para Telegram
    redirect_url = f"https://t.me/{pool_bot.bot.username}?start=acesso"
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


# ==================== GATEWAYS DE PAGAMENTO ====================

@app.route('/api/gateways', methods=['GET'])
@login_required
def get_gateways():
    """Lista gateways do usuário"""
    gateways = current_user.gateways.all()
    return jsonify([g.to_dict() for g in gateways])

@app.route('/api/gateways', methods=['POST'])
@login_required
def create_gateway():
    """Cria/atualiza gateway"""
    data = request.json
    gateway_type = data.get('gateway_type')
    
    # ✅ CORREÇÃO: Adicionar wiinpay aos tipos válidos
    if gateway_type not in ['syncpay', 'pushynpay', 'paradise', 'hoopay', 'wiinpay']:
        return jsonify({'error': 'Tipo de gateway inválido'}), 400
    
    # Verificar se já existe gateway deste tipo
    gateway = Gateway.query.filter_by(
        user_id=current_user.id,
        gateway_type=gateway_type
    ).first()
    
    if not gateway:
        gateway = Gateway(
            user_id=current_user.id,
            gateway_type=gateway_type
        )
        db.session.add(gateway)
    
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
    
    elif gateway_type == 'hoopay':
        gateway.api_key = data.get('api_key')
        # Organization ID configurado automaticamente para splits (você é o dono do sistema)
        gateway.organization_id = '5547db08-12c5-4de5-9592-90d38479745c'
    
    elif gateway_type == 'wiinpay':
        # ✅ WIINPAY
        gateway.api_key = data.get('api_key')
        # Split User ID da plataforma (4% de comissão pelos serviços de automação)
        # Fallback para o ID da plataforma se não fornecido
        gateway.split_user_id = data.get('split_user_id', '6877edeba3c39f8451ba5bdd')
    
    # ✅ Split percentage (comum a todos)
    gateway.split_percentage = float(data.get('split_percentage', 4.0))
    
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
        logger.error(f"Erro ao verificar gateway: {e}")
    
    db.session.commit()
    
    return jsonify(gateway.to_dict())

@app.route('/api/gateways/<int:gateway_id>/toggle', methods=['POST'])
@login_required
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

@app.route('/api/gateways/<int:gateway_id>', methods=['DELETE'])
@login_required
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
    
    return render_template('ranking.html',
                         ranking=ranking_data,
                         my_position=my_position_number,
                         next_user=next_user,
                         period=period)

@app.route('/settings')
@login_required
def settings():
    """Página de configurações"""
    return render_template('settings.html')

@app.route('/api/user/profile', methods=['PUT'])
@login_required
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
                    
                    # REGISTRAR COMISSÃO
                    from models import Commission
                    
                    # Verificar se já existe comissão para este pagamento
                    existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
                    
                    if not existing_commission:
                        # Calcular e registrar receita da plataforma (split payment automático)
                        commission_amount = payment.bot.owner.calculate_commission(payment.amount)
                        
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
            
            # Registrar comissão
            from models import Commission
            existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
            
            if not existing_commission:
                commission_amount = payment.bot.owner.calculate_commission(payment.amount)
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

