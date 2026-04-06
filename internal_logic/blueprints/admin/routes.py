"""
Admin Blueprint - Rotas Administrativas
======================================
Painel administrativo para gerenciamento de usuários e sistema
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user
from functools import wraps
from internal_logic.core.extensions import db, csrf
from internal_logic.core.models import User, Bot, Payment, BotUser, AuditLog
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator para verificar se usuário é admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash('Acesso negado. Permissões de administrador necessárias.', 'error')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

@admin_bp.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Painel administrativo principal"""
    # Estatísticas gerais do sistema
    total_users = User.query.count()
    total_bots = Bot.query.count()
    total_payments = Payment.query.filter_by(status='paid').count()
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # Usuários recentes
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Pagamentos recentes
    recent_payments = Payment.query.filter_by(status='paid').order_by(
        Payment.paid_at.desc()
    ).limit(10).all()
    
    return render_template(
        'admin/dashboard.html',
        stats={
            'total_users': total_users,
            'total_bots': total_bots,
            'total_payments': total_payments,
            'total_revenue': float(total_revenue)
        },
        recent_users=recent_users,
        recent_payments=recent_payments
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@admin_bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Lista de usuários para admin"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    search = request.args.get('search', '').strip()
    
    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.full_name.ilike(f'%{search}%')
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users, search=search)


@admin_bp.route('/admin/users/<int:user_id>')
@login_required
@admin_required
def admin_user_detail(user_id):
    """Detalhes de um usuário específico"""
    user = User.query.get_or_404(user_id)
    
    # Estatísticas do usuário
    user_bots = Bot.query.filter_by(user_id=user_id).all()
    user_payments = Payment.query.join(Bot).filter(
        Bot.user_id == user_id,
        Payment.status == 'paid'
    ).order_by(Payment.paid_at.desc()).limit(50).all()
    
    # Total de vendas do usuário
    total_sales = db.session.query(func.sum(Bot.total_sales)).filter(
        Bot.user_id == user_id
    ).scalar() or 0
    
    total_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
        Bot.user_id == user_id,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    return render_template(
        'admin/user_detail.html',
        user=user,
        bots=user_bots,
        payments=user_payments,
        stats={
            'total_sales': total_sales,
            'total_revenue': float(total_revenue),
            'bots_count': len(user_bots)
        }
    )


@admin_bp.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
@csrf.exempt
def admin_ban_user(user_id):
    """Bane ou desbane um usuário"""
    user = User.query.get_or_404(user_id)
    
    # Não permitir banir a si mesmo
    if user.id == current_user.id:
        return jsonify({'error': 'Você não pode banir a si mesmo'}), 400
    
    data = request.get_json()
    is_banned = data.get('is_banned', False)
    
    try:
        user.is_banned = is_banned
        user.banned_at = datetime.utcnow() if is_banned else None
        user.banned_by = current_user.id if is_banned else None
        
        db.session.commit()
        
        action = 'banido' if is_banned else 'desbanido'
        logger.warning(f"Usuário {user.email} {action} por {current_user.email}")
        
        return jsonify({
            'success': True,
            'message': f'Usuário {action} com sucesso',
            'is_banned': is_banned
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao banir usuário: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/users/<int:user_id>/admin', methods=['POST'])
@login_required
@admin_required
@csrf.exempt
def admin_toggle_admin(user_id):
    """Concede ou revoga privilégios de admin"""
    user = User.query.get_or_404(user_id)
    
    # Não permitir alterar a si mesmo
    if user.id == current_user.id:
        return jsonify({'error': 'Você não pode alterar seus próprios privilégios'}), 400
    
    data = request.get_json()
    is_admin = data.get('is_admin', False)
    
    try:
        user.is_admin = is_admin
        db.session.commit()
        
        action = 'concedidos' if is_admin else 'revogados'
        logger.warning(f"Privilégios de admin {action} para {user.email} por {current_user.email}")
        
        return jsonify({
            'success': True,
            'message': f'Privilégios de administrador {action}',
            'is_admin': is_admin
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao alterar privilégios: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# IMPERSONATE
# ============================================================================

@admin_bp.route('/admin/impersonate/<int:user_id>', methods=['POST'])
@login_required
@admin_required
@csrf.exempt
def admin_impersonate(user_id):
    """Inicia impersonate de um usuário"""
    user = User.query.get_or_404(user_id)
    
    # Não permitir impersonar a si mesmo
    if user.id == current_user.id:
        return jsonify({'error': 'Você não pode impersonar a si mesmo'}), 400
    
    # Salvar ID do admin original na sessão
    session['impersonate_admin_id'] = current_user.id
    session['impersonate_admin_email'] = current_user.email
    
    # Fazer login como o usuário
    from flask_login import login_user
    login_user(user, remember=False)
    
    logger.warning(f"Admin {session.get('impersonate_admin_email')} impersonando {user.email}")
    
    return jsonify({
        'success': True,
        'message': f'Agora você está logado como {user.email}',
        'redirect': url_for('dashboard.dashboard')
    })


@admin_bp.route('/admin/stop-impersonate')
@login_required
def admin_stop_impersonate():
    """Para o impersonate e volta ao admin original"""
    admin_id = session.get('impersonate_admin_id')
    admin_email = session.get('impersonate_admin_email')
    
    if not admin_id:
        flash('Nenhuma sessão de impersonate ativa', 'warning')
        return redirect(url_for('dashboard.dashboard'))
    
    admin_user = User.query.get(admin_id)
    if not admin_user:
        flash('Admin original não encontrado', 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    # Remover dados de impersonate da sessão
    session.pop('impersonate_admin_id', None)
    session.pop('impersonate_admin_email', None)
    
    # Fazer login como admin novamente
    from flask_login import login_user
    login_user(admin_user, remember=True)
    
    logger.info(f"Impersonate finalizado por {admin_email}, retornando ao admin")
    flash(f'Você retornou à sua conta de administrador ({admin_email})', 'success')
    
    return redirect(url_for('admin.admin_dashboard'))


# ============================================================================
# REVENUE & ANALYTICS
# ============================================================================

@admin_bp.route('/admin/revenue')
@login_required
@admin_required
def admin_revenue():
    """Relatório de receita do sistema"""
    # Receita por dia (últimos 30 dias)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    daily_revenue = db.session.query(
        func.date(Payment.paid_at).label('date'),
        func.count(Payment.id).label('count'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.status == 'paid',
        Payment.paid_at >= thirty_days_ago
    ).group_by(
        func.date(Payment.paid_at)
    ).order_by(
        func.date(Payment.paid_at).desc()
    ).all()
    
    # Top usuários por receita
    top_users = db.session.query(
        User.id,
        User.username,
        User.email,
        func.sum(Payment.amount).label('total_revenue'),
        func.count(Payment.id).label('total_sales')
    ).join(Bot).join(Payment).filter(
        Payment.status == 'paid'
    ).group_by(
        User.id
    ).order_by(
        func.sum(Payment.amount).desc()
    ).limit(20).all()
    
    return render_template(
        'admin/revenue.html',
        daily_revenue=daily_revenue,
        top_users=top_users
    )


@admin_bp.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    """Analytics e estatísticas do sistema"""
    # Métricas gerais
    total_users = User.query.count()
    active_users_7d = User.query.filter(
        User.last_login_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    total_bots = Bot.query.count()
    active_bots = Bot.query.filter_by(is_active=True).count()
    
    total_payments = Payment.query.filter_by(status='paid').count()
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # Crescimento (últimos 7 dias vs 7 dias anteriores)
    last_7d_start = datetime.utcnow() - timedelta(days=7)
    prev_7d_start = datetime.utcnow() - timedelta(days=14)
    
    new_users_last_7d = User.query.filter(User.created_at >= last_7d_start).count()
    new_users_prev_7d = User.query.filter(
        User.created_at >= prev_7d_start,
        User.created_at < last_7d_start
    ).count()
    
    user_growth = ((new_users_last_7d - new_users_prev_7d) / max(new_users_prev_7d, 1)) * 100
    
    return render_template(
        'admin/analytics.html',
        metrics={
            'total_users': total_users,
            'active_users_7d': active_users_7d,
            'total_bots': total_bots,
            'active_bots': active_bots,
            'total_payments': total_payments,
            'total_revenue': float(total_revenue),
            'user_growth': round(user_growth, 2),
            'new_users_last_7d': new_users_last_7d
        }
    )


# ============================================================================
# AUDIT LOGS
# ============================================================================

@admin_bp.route('/admin/audit-logs')
@login_required
@admin_required
def admin_audit_logs():
    """Logs de auditoria do sistema"""
    page = request.args.get('page', 1, type=int)
    per_page = 100
    
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/audit_logs.html', logs=logs)


# ============================================================================
# EXPORTS
# ============================================================================

@admin_bp.route('/admin/exports')
@login_required
@admin_required
def admin_exports():
    """Página de exportação de dados"""
    return render_template('admin/exports.html')


@admin_bp.route('/admin/api/export/users')
@login_required
@admin_required
def admin_export_users():
    """API para exportar usuários (CSV/JSON)"""
    import json
    from flask import Response
    
    users = User.query.all()
    users_data = []
    
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'is_active': user.is_active,
            'is_admin': getattr(user, 'is_admin', False),
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
            'total_revenue': float(user.total_revenue) if hasattr(user, 'total_revenue') else 0.0,
            'total_sales': user.total_sales if hasattr(user, 'total_sales') else 0
        })
    
    format_type = request.args.get('format', 'json')
    
    if format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=users_data[0].keys() if users_data else [])
        writer.writeheader()
        writer.writerows(users_data)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=users_export.csv'
            }
        )
    else:
        return Response(
            json.dumps(users_data, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': 'attachment; filename=users_export.json'
            }
        )


@admin_bp.route('/admin/api/export/payments')
@login_required
@admin_required
def admin_export_payments():
    """API para exportar pagamentos (CSV/JSON)"""
    import json
    from flask import Response
    
    payments = Payment.query.filter_by(status='paid').order_by(
        Payment.paid_at.desc()
    ).limit(10000).all()
    
    payments_data = []
    for payment in payments:
        payments_data.append({
            'id': payment.id,
            'payment_id': payment.payment_id,
            'bot_id': payment.bot_id,
            'user_id': payment.bot.user_id if payment.bot else None,
            'customer_name': payment.customer_name,
            'customer_email': payment.customer_email,
            'amount': float(payment.amount),
            'status': payment.status,
            'gateway_type': payment.gateway_type,
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
            'product_name': payment.product_name
        })
    
    format_type = request.args.get('format', 'json')
    
    if format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=payments_data[0].keys() if payments_data else [])
        writer.writeheader()
        writer.writerows(payments_data)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=payments_export.csv'
            }
        )
    else:
        return Response(
            json.dumps(payments_data, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': 'attachment; filename=payments_export.json'
            }
        )
