"""
Auth Blueprint - Rotas de Autenticação
======================================
Login, Logout, Register, Forgot Password
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from internal_logic.core.extensions import db, limiter
from internal_logic.core.models import User
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
auth_bp = Blueprint('auth', __name__)


def get_user_ip():
    """Obtém o IP real do usuário considerando proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


@auth_bp.route('/')
def index():
    """Página inicial"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")  # ✅ PROTEÇÃO: Spam de registro
def register():
    """Registro de novo usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
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
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar usuário: {e}")
            flash('Erro ao criar conta. Tente novamente.', 'error')
    
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # ✅ PROTEÇÃO: Brute-force login
def login():
    """Login de usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        data = request.form
        user = User.query.filter_by(email=data.get('email')).first()
        
        if user and user.check_password(data.get('password')):
            # Verificar se usuário está banido
            if user.is_banned:
                flash(f'Sua conta foi suspensa. Motivo: {user.ban_reason or "Violação dos termos de uso"}', 'error')
                return render_template('login.html')
            
            login_user(user, remember=data.get('remember') == 'on')
            user.last_login = user.get_brazil_time()  # Assumindo método no model
            user.last_ip = get_user_ip()
            db.session.commit()
            
            logger.info(f"Login bem-sucedido: {user.email}")
            
            # Redirecionar admin para painel admin
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.dashboard'))
        
        flash('Email ou senha incorretos!', 'error')
    
    return render_template('login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Página de recuperação de senha"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
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


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """Logout de usuário"""
    logger.info(f"Logout: {current_user.email}")
    logger.debug(f"Cookies recebidos no logout: {request.cookies}")
    
    # Encerrar sessão Flask-Login
    logout_user()
    
    # Limpar sessão e cookies
    session.clear()
    
    response = redirect(url_for('auth.login'))
    
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    session_cookie_domain = current_app.config.get('SESSION_COOKIE_DOMAIN')
    session_cookie_path = current_app.config.get('SESSION_COOKIE_PATH', '/')
    
    host_domain = request.host.split(':')[0]
    domain_candidates = {
        session_cookie_domain,
        current_app.config.get('SERVER_NAME'),
        host_domain,
        f".{host_domain}" if not host_domain.startswith('.') else host_domain
    }

    for domain in domain_candidates:
        response.delete_cookie(
            session_cookie_name,
            domain=domain or None,
            path=session_cookie_path,
        )

    response.set_cookie(
        session_cookie_name,
        value='',
        expires=0,
        max_age=0,
        domain=session_cookie_domain or None,
        path=session_cookie_path,
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
        httponly=True,
        samesite=current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
    )
    
    logger.info("✅ Logout completo: cookies limpos, sessão encerrada")
    return response
