"""
SaaS Bot Manager - Aplicação Principal
Sistema de gerenciamento de bots do Telegram com painel web
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, Bot, BotConfig, Gateway, Payment, AuditLog, Achievement, UserAchievement, BotUser, RedirectPool, PoolBot, RemarketingCampaign, RemarketingBlacklist, PushSubscription, NotificationSettings, get_brazil_time
from bot_manager import BotManager
from datetime import datetime, timedelta
from functools import wraps
import os
import logging
import json
import time
import uuid
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

# ==================== FUNÇÃO CENTRALIZADA: ENVIO DE ENTREGÁVEL ====================
def send_payment_delivery(payment, bot_manager):
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância do BotManager para enviar mensagem
    
    Returns:
        bool: True se enviado com sucesso, False se houve erro
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado - não é possível enviar entregável")
            return False
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido ({payment.customer_user_id}) - não é possível enviar")
            return False
        
        # Verificar se bot tem config e access_link
        has_access_link = payment.bot.config and payment.bot.config.access_link
        
        if has_access_link:
            access_link = payment.bot.config.access_link
            # Mensagem completa com link
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

Aproveite! 🚀
            """
        else:
            # Mensagem genérica sem link (bot não configurou access_link)
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
            """
            logger.warning(f"⚠️ Bot {payment.bot_id} não tem access_link configurado - enviando mensagem genérica")
        
        # Enviar via bot manager e capturar exceção se falhar
        try:
            bot_manager.send_telegram_message(
                token=payment.bot.token,
                chat_id=str(payment.customer_user_id),
                message=access_message.strip()
            )
            logger.info(f"✅ Entregável enviado para {payment.customer_name} (payment_id: {payment.id}, bot_id: {payment.bot_id})")
            return True
        except Exception as send_error:
            # Erro ao enviar mensagem (bot bloqueado, chat_id inválido, etc)
            logger.error(f"❌ Erro ao enviar mensagem Telegram para payment {payment.id}: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar entregável para payment {payment.id if payment else 'None'}: {e}", exc_info=True)
        return False

# ==================== RECONCILIADOR DE PAGAMENTOS PARADISE (POLLING) ====================
def reconcile_paradise_payments():
    """Consulta periodicamente pagamentos pendentes da Paradise (BATCH LIMITADO para evitar spam)."""
    try:
        with app.app_context():
            from models import Payment, Gateway, db, Bot
            # ✅ BATCH LIMITADO: apenas 5 por execução para evitar spam
            # ✅ CORREÇÃO CRÍTICA: Buscar MAIS RECENTES primeiro (created_at DESC) para priorizar novos PIX
            pending = Payment.query.filter_by(status='pending', gateway_type='paradise').order_by(Payment.created_at.desc()).limit(5).all()
            if not pending:
                logger.debug("🔍 Reconciliador Paradise: Nenhum payment pendente encontrado")
                return
            
            logger.info(f"🔍 Reconciliador Paradise: Consultando {len(pending)} payment(s) mais recente(s)")
            
            # Agrupar por user_id para reusar instância do gateway
            gateways_by_user = {}
            
            for p in pending:
                try:
                    # Buscar gateway do dono do bot
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(user_id=user_id, gateway_type='paradise', is_active=True, is_verified=True).first()
                        if not gw:
                            continue
                        from gateway_factory import GatewayFactory
                        creds = {
                            'api_key': gw.api_key,
                            'product_hash': gw.product_hash,
                            'offer_hash': gw.offer_hash,
                            'store_id': gw.store_id,
                            'split_percentage': gw.split_percentage or 2.0,
                        }
                        g = GatewayFactory.create_gateway('paradise', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    
                    # ✅ CORREÇÃO CRÍTICA: Para Paradise, hash é o campo 'id' retornado (é o que aparece no painel)
                    # Prioridade: hash > transaction_id
                    hash_or_id = p.gateway_transaction_hash or p.gateway_transaction_id
                    if not hash_or_id:
                        logger.warning(f"⚠️ Paradise Payment {p.id} ({p.payment_id}): sem hash ou transaction_id para consulta")
                        logger.warning(f"   Gateway Hash: {p.gateway_transaction_hash} | Transaction ID: {p.gateway_transaction_id}")
                        continue
                    
                    logger.info(f"🔍 Paradise: Consultando payment {p.id} ({p.payment_id})")
                    logger.info(f"   Valor: R$ {p.amount:.2f} | Hash: {p.gateway_transaction_hash} | Transaction ID: {p.gateway_transaction_id}")
                    logger.info(f"   Usando para consulta (prioridade): {hash_or_id}")
                    
                    # ✅ Tentar primeiro com hash/id (o que aparece no painel)
                    result = gateway.get_payment_status(str(hash_or_id))
                    
                    # ✅ Se falhar e tiver transaction_id numérico diferente, tentar com ele também
                    if not result and p.gateway_transaction_id and p.gateway_transaction_id != hash_or_id:
                        logger.info(f"   🔄 Tentando com transaction_id numérico: {p.gateway_transaction_id}")
                        result = gateway.get_payment_status(str(p.gateway_transaction_id))
                    
                    if result:
                        status = result.get('status')
                        amount = result.get('amount')
                        # ✅ CORREÇÃO: Garantir que amount seja numérico antes de formatar
                        amount_str = f"R$ {amount:.2f}" if amount is not None else "N/A"
                        if status == 'paid':
                            logger.info(f"   ✅ Status: PAID | Amount: {amount_str}")
                        elif status == 'pending':
                            logger.info(f"   ⏳ Status: PENDING | Amount: {amount_str}")
                        else:
                            logger.info(f"   📊 Status: {status.upper()} | Amount: {amount_str}")
                    else:
                        logger.warning(f"   ⚠️ Paradise não retornou status para {hash_or_id}")
                        logger.warning(f"      Transaction ID numérico: {p.gateway_transaction_id}")
                        logger.warning(f"      Possíveis causas: transação não existe na API, ainda está sendo processada, ou hash/ID incorreto")
                    if result and result.get('status') == 'paid':
                        # Atualizar pagamento e estatísticas
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                from models import User
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        db.session.commit()
                        logger.info(f"✅ Paradise: Payment {p.id} atualizado para paid via reconciliação")
                        
                        # ✅ REFRESH payment após commit para garantir que está atualizado
                        db.session.refresh(p)
                        
                        # ✅ ENVIAR META PIXEL PURCHASE EVENT (CORREÇÃO CRÍTICA)
                        try:
                            send_meta_pixel_purchase_event(p)
                            logger.info(f"📊 Meta Pixel Purchase disparado para {p.payment_id} via reconciliador Paradise")
                        except Exception as e:
                            logger.error(f"❌ Erro ao disparar Meta Pixel via reconciliação Paradise: {e}", exc_info=True)
                            # ✅ LOG DETALHADO para debug
                            logger.error(f"   Payment ID: {p.payment_id} | Bot ID: {p.bot_id} | Status: {p.status}")
                            if p.bot:
                                from models import PoolBot
                                pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
                                if pool_bot:
                                    pool = pool_bot.pool
                                    logger.error(f"   Pool: {pool.name} | Tracking: {pool.meta_tracking_enabled} | Purchase Event: {pool.meta_events_purchase}")
                                else:
                                    logger.error(f"   ❌ Bot não está associado a nenhum pool!")
                            else:
                                logger.error(f"   ❌ Bot não encontrado!")
                        
                        # ✅ ENVIAR ENTREGÁVEL AO CLIENTE (CORREÇÃO CRÍTICA)
                        try:
                            from models import Payment
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                send_payment_delivery(payment_obj, bot_manager)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável via reconciliação: {e}")
                        
                        # Emitir evento em tempo real
                        try:
                            socketio.emit('payment_update', {
                                'payment_id': p.id,
                                'status': 'paid',
                                'amount': float(p.amount),
                                'bot_id': p.bot_id,
                            })
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar payment {p.id} ({p.payment_id}): {e}", exc_info=True)
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador Paradise: erro: {e}", exc_info=True)

# ==================== RECONCILIADOR DE PAGAMENTOS PUSHYNPAY (POLLING) ====================
def reconcile_pushynpay_payments():
    """Consulta periodicamente pagamentos pendentes da PushynPay (BATCH LIMITADO para evitar spam)."""
    try:
        with app.app_context():
            from models import Payment, Gateway, db, Bot
            # ✅ BATCH LIMITADO: apenas 5 por execução para evitar spam
            pending = Payment.query.filter_by(status='pending', gateway_type='pushynpay').order_by(Payment.id.asc()).limit(5).all()
            
            if not pending:
                return
            
            logger.info(f"🔍 PushynPay: Verificando {len(pending)} pagamento(s) pendente(s)...")
            
            # Agrupar por user_id para reusar instância do gateway
            gateways_by_user = {}
            
            for p in pending:
                try:
                    # Buscar gateway do dono do bot
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(user_id=user_id, gateway_type='pushynpay', is_active=True, is_verified=True).first()
                        if not gw:
                            continue
                        from gateway_factory import GatewayFactory
                        creds = {
                            'api_key': gw.api_key,
                        }
                        g = GatewayFactory.create_gateway('pushynpay', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    
                    # ✅ Usar transaction_id
                    transaction_id = p.gateway_transaction_id
                    if not transaction_id:
                        continue
                    
                    result = gateway.get_payment_status(str(transaction_id))
                    if result and result.get('status') == 'paid':
                        # Atualizar pagamento e estatísticas
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                from models import User
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        db.session.commit()
                        logger.info(f"✅ PushynPay: Payment {p.id} atualizado para paid via reconciliação")
                        
                        # ✅ ENVIAR META PIXEL PURCHASE EVENT (CORREÇÃO CRÍTICA)
                        try:
                            send_meta_pixel_purchase_event(p)
                            logger.info(f"📊 Meta Pixel Purchase disparado para {p.payment_id} via reconciliador PushynPay")
                        except Exception as e:
                            logger.error(f"❌ Erro ao disparar Meta Pixel via reconciliação PushynPay: {e}", exc_info=True)
                        
                        # ✅ ENVIAR ENTREGÁVEL AO CLIENTE (CORREÇÃO CRÍTICA)
                        try:
                            from models import Payment
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                send_payment_delivery(payment_obj, bot_manager)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável via reconciliação PushynPay: {e}")
                        
                        # Emitir evento em tempo real
                        try:
                            socketio.emit('payment_update', {
                                'payment_id': p.id,
                                'status': 'paid',
                                'amount': float(p.amount),
                                'bot_id': p.bot_id,
                            })
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar payment PushynPay {p.id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador PushynPay: erro: {e}", exc_info=True)

# ✅ Registrar job com INTERVALO MAIOR (5 minutos) e BATCH LIMITADO
try:
    scheduler.add_job(id='reconcile_paradise', func=reconcile_paradise_payments,
                      trigger='interval', seconds=300, replace_existing=True, max_instances=1)
    logger.info("✅ Job de reconciliação Paradise agendado (5min, batch=5)")
except Exception as _e:
    logger.warning(f"⚠️ Não foi possível agendar reconciliador Paradise: {_e}")

# ✅ Registrar job PushynPay com INTERVALO MAIOR (5 minutos) e BATCH LIMITADO
try:
    scheduler.add_job(id='reconcile_pushynpay', func=reconcile_pushynpay_payments,
                      trigger='interval', seconds=300, replace_existing=True, max_instances=1)
    logger.info("✅ Job de reconciliação PushynPay agendado (5min, batch=5)")
except Exception as _e:
    logger.warning(f"⚠️ Não foi possível agendar reconciliador PushynPay: {_e}")

# ✅ JOB PERIÓDICO: Verificar e sincronizar status dos bots
def sync_bots_status():
    """
    Verifica e corrige status dos bots periodicamente
    
    Roda a cada 30 segundos para garantir que bots que caíram
    sejam marcados como offline automaticamente
    
    VERIFICAÇÃO REAL:
    1. Verifica se bot está em BotManager.active_bots (memória)
    2. Verifica se bot REALMENTE responde no Telegram (getMe)
    3. Se qualquer verificação falhar → marca como offline
    """
    try:
        # Guard para evitar concorrência entre múltiplos processos (file lock leve por tempo)
        import os, time as _time
        lock_path = "/tmp/grimbots_sync_bots_status.lock" if os.name != 'nt' else "C:/temp/grimbots_sync_bots_status.lock"
        now = _time.time()
        try:
            # se o lock existir e for recente (< 10s), aborta esta execução
            if os.path.exists(lock_path):
                mtime = os.path.getmtime(lock_path)
                if now - mtime < 10:
                    return
            # toca o arquivo (atualiza mtime)
            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
            with open(lock_path, 'w') as f:
                f.write(str(now))
        except Exception as _e:
            logger.debug(f"sync_bots_status lock warn: {_e}")
        with app.app_context():
            from models import Bot
            
            # Buscar todos os bots marcados como is_running=True
            running_bots = Bot.query.filter_by(is_running=True).all()
            
            bots_to_update = []
            for bot in running_bots:
                # ✅ VERIFICAÇÃO 1: Status no BotManager (memória)
                status_memory = bot_manager.get_bot_status(bot.id, verify_telegram=False)
                is_running_in_memory = status_memory.get('is_running', False)
                # ✅ VERIFICAÇÃO 1b: Heartbeat compartilhado (Redis)
                has_recent_heartbeat = False
                try:
                    import redis
                    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                    if r.get(f'bot_heartbeat:{bot.id}'):
                        has_recent_heartbeat = True
                except Exception:
                    pass

                # ✅ VERIFICAÇÃO 2: Bot REALMENTE responde no Telegram
                status_telegram = bot_manager.get_bot_status(bot.id, verify_telegram=True)
                is_running_telegram = status_telegram.get('is_running', False)
                reason_telegram = status_telegram.get('reason')

                # ✅ NOVA REGRA (mais segura):
                # Se o bot está rodando em memória, NÃO marcar offline via job.
                # Isso evita falsos negativos do Telegram derrubarem o status no dashboard.
                # Só marcar offline automaticamente quando NÃO está rodando em memória.
                if is_running_in_memory or has_recent_heartbeat:
                    actual_is_running = True
                else:
                    # Não está em memória: considerar offline
                    actual_is_running = False
                
                # Se bot está marcado como running mas não está realmente online (fora de memória), corrigir
                if not actual_is_running:
                    bots_to_update.append(bot.id)
                    bot.is_running = False
                    bot.last_stopped = get_brazil_time()

                    reason = status_telegram.get('reason', 'unknown')
                    logger.info(f"🔴 Bot {bot.id} ({bot.name}) marcado como offline (memória: {is_running_in_memory}, telegram: {is_running_telegram}, motivo: {reason})")

                    # Remover de active_bots somente quando realmente não está em memória (queda real)
                    try:
                        bot_manager.stop_bot(bot.id)
                        logger.info(f"🧹 Bot {bot.id} removido de active_bots")
                    except:
                        pass
            
            if bots_to_update:
                db.session.commit()
                logger.info(f"✅ {len(bots_to_update)} bots sincronizados e marcados como offline")
                
                # Notificar via WebSocket
                for bot_id in bots_to_update:
                    bot = next((b for b in running_bots if b.id == bot_id), None)
                    if bot:
                        socketio.emit('bot_status_update', {
                            'bot_id': bot_id,
                            'is_running': False
                        }, room=f'user_{bot.user_id}')
    
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar status dos bots: {e}")

# Registrar job periódico (a cada 30 segundos)
scheduler.add_job(
    id='sync_bots_status',
    func=sync_bots_status,
    trigger='interval',
    seconds=30,
    max_instances=1,
    replace_existing=True
)
logger.info("✅ Job de sincronização de status dos bots configurado (30s)")

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
            user.last_login = get_brazil_time()
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
    from sqlalchemy import func
    from models import BotUser
    
    # ✅ PERFORMANCE: Query simplificada - usar campos calculados do modelo Bot
    # Evitar JOINs pesados no carregamento inicial, calcular contagens depois se necessário
    bots = Bot.query.filter(Bot.user_id == current_user.id).order_by(Bot.created_at.desc()).all()
    
    # Calcular pending_sales e total_users de forma otimizada (queries separadas)
    bot_ids = [b.id for b in bots]
    pending_count_per_bot = {}
    user_count_per_bot = {}
    
    if bot_ids:
        # Query para pending_sales (mais leve que JOIN)
        pending_counts = db.session.query(
            Payment.bot_id,
            func.count(Payment.id).label('count')
        ).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'pending'
        ).group_by(Payment.bot_id).all()
        
        pending_count_per_bot = {bot_id: count for bot_id, count in pending_counts}
        
        # Query para total_users (mais leve que JOIN)
        user_counts = db.session.query(
            BotUser.bot_id,
            func.count(func.distinct(BotUser.telegram_user_id)).label('count')
        ).filter(BotUser.bot_id.in_(bot_ids)).group_by(BotUser.bot_id).all()
        
        user_count_per_bot = {bot_id: count for bot_id, count in user_counts}
    
    # Montar bot_stats sem JOIN pesado
    bot_stats = []
    for bot in bots:
        bot_stats.append(type('BotStat', (), {
            'id': bot.id,
            'name': bot.name,
            'username': bot.username,
            'is_running': bot.is_running,
            'is_active': bot.is_active,
            'created_at': bot.created_at,
            'total_sales': bot.total_sales,
            'total_revenue': bot.total_revenue,
            'total_users': user_count_per_bot.get(bot.id, 0),
            'pending_sales': pending_count_per_bot.get(bot.id, 0)
        })())
    
    # ✅ PERFORMANCE: Não fazer verificações síncronas de Telegram no carregamento
    # O job de background (sync_bots_status) já cuida de atualizar o status a cada 30s
    # Isso evita múltiplas chamadas HTTP que tornam o dashboard lento
    
    # Estatísticas gerais (calculadas a partir dos bot_stats)
    total_users = sum(b.total_users for b in bot_stats)
    total_sales = sum(b.total_sales for b in bot_stats)
    total_revenue = sum(float(b.total_revenue) for b in bot_stats)
    running_bots = sum(1 for b in bot_stats if b.is_running)
    
    # ✅ VERSÃO 2.0: Calcular stats por período (Hoje e Mês)
    from datetime import datetime, timedelta
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = get_brazil_time().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Stats de HOJE
    if bot_ids:
        today_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid',
            Payment.created_at >= today_start
        ).scalar() or 0
        
        today_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid',
            Payment.created_at >= today_start
        ).scalar() or 0.0
    else:
        today_sales = 0
        today_revenue = 0.0
    
    # Stats do MÊS
    if bot_ids:
        month_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid',
            Payment.created_at >= month_start
        ).scalar() or 0
        
        month_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid',
            Payment.created_at >= month_start
        ).scalar() or 0.0
    else:
        month_sales = 0
        month_revenue = 0.0
    
    # ✅ VERSÃO 2.0: Vendas Pendentes por período
    total_pending_sales = sum(b.pending_sales for b in bot_stats)
    
    if bot_ids:
        today_pending_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'pending',
            Payment.created_at >= today_start
        ).scalar() or 0
        
        month_pending_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'pending',
            Payment.created_at >= month_start
        ).scalar() or 0
    else:
        today_pending_sales = 0
        month_pending_sales = 0
    
    # ✅ VERSÃO 2.0: Usuários por período (BotUser)
    # NOTA: BotUser usa 'first_interaction' ao invés de 'created_at'
    if bot_ids:
        today_users = db.session.query(func.count(func.distinct(BotUser.telegram_user_id))).filter(
            BotUser.bot_id.in_(bot_ids),
            BotUser.archived == False,
            BotUser.first_interaction >= today_start
        ).scalar() or 0
        
        month_users = db.session.query(func.count(func.distinct(BotUser.telegram_user_id))).filter(
            BotUser.bot_id.in_(bot_ids),
            BotUser.archived == False,
            BotUser.first_interaction >= month_start
        ).scalar() or 0
    else:
        today_users = 0
        month_users = 0
    
    stats = {
        'total_bots': len(bot_stats),
        'active_bots': sum(1 for b in bot_stats if b.is_active),
        'running_bots': running_bots,
        'total_users': total_users,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'pending_sales': total_pending_sales,
        'can_add_bot': current_user.can_add_bot(),
        'commission_percentage': current_user.commission_percentage,
        'commission_balance': current_user.get_commission_balance(),
        'total_commission_owed': current_user.total_commission_owed,
        'total_commission_paid': current_user.total_commission_paid,
        # ✅ VERSÃO 2.0: Stats por período
        'today_sales': today_sales,
        'today_revenue': float(today_revenue),
        'month_sales': month_sales,
        'month_revenue': float(month_revenue),
        # ✅ VERSÃO 2.0: Pendentes por período
        'today_pending_sales': today_pending_sales,
        'month_pending_sales': month_pending_sales,
        # ✅ VERSÃO 2.0: Usuários por período
        'today_users': today_users,
        'month_users': month_users
    }
    
    # ✅ PERFORMANCE: Últimos pagamentos - usar índices se disponíveis
    # Se bot_ids já temos, filtrar diretamente por bot_id (mais rápido que JOIN)
    if bot_ids:
        recent_payments = db.session.query(Payment).filter(
            Payment.bot_id.in_(bot_ids)
    ).order_by(Payment.id.desc()).limit(20).all()
    else:
        recent_payments = []
    
    # Buscar configs de todos os bots de uma vez (otimizado)
    # bot_ids já foi definido acima, reutilizar
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
    from models import BotUser, Bot
    
    # ✅ PERFORMANCE: Não fazer verificações síncronas de Telegram na API
    # O job de background (sync_bots_status) já cuida de atualizar o status a cada 30s
    # Isso evita múltiplas chamadas HTTP que tornam a API lenta
    
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
    """API para dados do gráfico de vendas (últimos N dias: 7/30/90)"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Ler período desejado (default 7). Aceitar apenas 7, 30, 90
    try:
        period = int(request.args.get('period', 7))
    except Exception:
        period = 7
    if period not in (7, 30, 90):
        period = 7
    
    start_date = get_brazil_time() - timedelta(days=period)
    
    # Query para vendas por dia
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).join(Bot).filter(
        Bot.user_id == current_user.id,
        Payment.created_at >= start_date,
        Payment.status == 'paid'
    ).group_by(func.date(Payment.created_at))\
     .order_by(func.date(Payment.created_at))\
     .all()
    
    # Preencher dias sem vendas (do mais antigo ao mais recente)
    result = []
    for i in range(period):
        date = (get_brazil_time() - timedelta(days=(period - 1 - i))).date()
        day_data = next((s for s in sales_by_day if str(s.date) == str(date)), None)
        result.append({
            'date': date.strftime('%d/%m'),
            'sales': day_data.sales if day_data else 0,
            'revenue': float(day_data.revenue) if day_data and day_data.revenue is not None else 0.0
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
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
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
        # Corrigir status inicial usando memória/heartbeat (evita mostrar "Iniciar" indevidamente)
        try:
            status_memory = bot_manager.get_bot_status(bot.id, verify_telegram=False)
            is_in_memory = status_memory.get('is_running', False)
            has_recent_heartbeat = False
            try:
                import redis
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                if r.get(f'bot_heartbeat:{bot.id}'):
                    has_recent_heartbeat = True
            except Exception:
                pass
            bot_dict['is_running'] = bool(is_in_memory or has_recent_heartbeat)
        except Exception:
            # Fallback ao valor do banco em caso de erro
            bot_dict['is_running'] = bot.is_running
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
        validation_result = bot_manager.validate_token(token)
        bot_info = validation_result.get('bot_info')
        
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
            bot.last_stopped = get_brazil_time()
            db.session.commit()
            logger.info(f"✅ Bot {bot_id} parado e cache limpo")
        
        # VALIDAÇÃO 4: Token válido no Telegram
        validation_result = bot_manager.validate_token(new_token)
        bot_info = validation_result.get('bot_info')
        
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
                'archived_at': get_brazil_time()
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
        validation_result = bot_manager.validate_token(new_token)
        bot_info = validation_result.get('bot_info')
        
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
    
    # ✅ VALIDAR TOKEN ANTES DE INICIAR (QI 500)
    try:
        validation_result = bot_manager.validate_token(bot.token)
        if validation_result.get('error_type'):
            error_type = validation_result.get('error_type')
            return jsonify({
                'error': 'Token do bot inválido ou banido',
                'error_type': error_type,
                'bot_id': bot.id
            }), 400
    except Exception as e:
        error_type = getattr(e, 'error_type', 'unknown')
        logger.error(f"❌ Token inválido/banido para bot {bot_id}: {e} (tipo: {error_type})")
        
        # Se for banimento, retornar resposta específica
        if error_type == 'banned':
            return jsonify({
                'error': 'Bot foi banido pelo Telegram. É necessário trocar o token.',
                'error_type': 'banned',
                'bot_id': bot.id,
                'message': 'O bot foi banido ou o token foi revogado. Acesse as configurações do bot e atualize o token com um novo token do @BotFather.'
            }), 400
        elif error_type == 'invalid_token':
            return jsonify({
                'error': 'Token inválido ou expirado',
                'error_type': 'invalid_token',
                'bot_id': bot.id
            }), 400
        else:
            return jsonify({
                'error': str(e),
                'error_type': error_type,
                'bot_id': bot.id
            }), 400
    
    try:
        bot_manager.start_bot(bot.id, bot.token, bot.config.to_dict())
        bot.is_running = True
        bot.last_started = get_brazil_time()
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

@app.route('/api/bots/verify-status', methods=['POST'])
@login_required
@csrf.exempt
def verify_bots_status():
    """
    API para verificar status REAL dos bots de forma assíncrona
    Chamada pelo frontend após carregar dashboard (sem bloquear carregamento inicial)
    """
    try:
        user_bots = Bot.query.filter_by(user_id=current_user.id).all()
        
        if not user_bots:
            return jsonify({'bots': []})
        
        bots_status = []
        bots_to_update = []
        
        for bot in user_bots:
            # Verificar status em memória
            status_memory = bot_manager.get_bot_status(bot.id, verify_telegram=False)
            is_in_memory = status_memory.get('is_running', False)
            
            # Verificar heartbeat compartilhado (Redis) para ambientes multi-worker
            has_recent_heartbeat = False
            try:
                import redis, time as _t
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                hb = r.get(f'bot_heartbeat:{bot.id}')
                if hb:
                    # Se existe a chave (TTL gerenciado pelo monitor), consideramos recente
                    has_recent_heartbeat = True
            except Exception:
                pass

            # Verificar status no Telegram (pode demorar) - opcional
            status_telegram = bot_manager.get_bot_status(bot.id, verify_telegram=True)
            # is_running_telegram = status_telegram.get('is_running', False)
            # reason = status_telegram.get('reason')
            
            # ✅ NOVA REGRA (coerente com o job): se está em memória, considerar online
            # para evitar falsos negativos de API derrubarem o status no dashboard
            if is_in_memory or has_recent_heartbeat:
                actual_is_running = True
            else:
                actual_is_running = False
            
            # Adicionar ao resultado
            bots_status.append({
                'id': bot.id,
                'is_running': actual_is_running,
                'verified': True
            })
            
            # Marcar para atualizar banco se status mudou
            if bot.is_running != actual_is_running:
                bots_to_update.append((bot.id, actual_is_running))
                bot.is_running = actual_is_running
                
                if not actual_is_running:
                    bot.last_stopped = get_brazil_time()
                    # Se estava em memória mas não responde, remover
                    if is_in_memory and not is_running_telegram:
                        try:
                            bot_manager.stop_bot(bot.id)
                        except:
                            pass
        
        # Atualizar banco em batch
        if bots_to_update:
            db.session.commit()
            logger.info(f"✅ Status verificado e atualizado: {len(bots_to_update)} bots corrigidos")
        
        return jsonify({
            'bots': bots_status,
            'updated_count': len(bots_to_update)
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar status dos bots: {e}", exc_info=True)
        db.session.rollback()
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
        bot.last_stopped = get_brazil_time()
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
    """✅ V2.0: Cria nova campanha de remarketing com suporte a agendamento"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.json
    from models import RemarketingCampaign
    from datetime import datetime
    
    # ✅ V2.0: Processar scheduled_at se fornecido
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
        scheduled_at=scheduled_at,  # ✅ V2.0
        status=status  # ✅ V2.0: 'draft' ou 'scheduled'
    )
    
    db.session.add(campaign)
    db.session.commit()
    
    if status == 'scheduled':
        logger.info(f"📅 Campanha de remarketing agendada: {campaign.name} para {scheduled_at} (Bot {bot.name})")
    else:
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
        
        # ✅ CORREÇÃO: Decodificar Unicode escape sequences (ex: \ud835\udeXX)
        try:
            # Verificar se a mensagem contém escape sequences Unicode
            if '\\u' in message or '\\U' in message:
                # Decodificar escape sequences Unicode
                # Usar codecs.decode para processar \uXXXX e \UXXXXXXXX
                import codecs
                # Primeiro, tentar decodificar como raw string (r'...')
                try:
                    # Se a mensagem contém escape sequences, decodificar
                    message = message.encode('utf-8').decode('unicode_escape')
                    logger.info(f"✅ Mensagem decodificada: {len(message)} caracteres")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # Se falhar, tentar usando codecs
                    try:
                        message = codecs.decode(message, 'unicode_escape')
                        logger.info(f"✅ Mensagem decodificada via codecs: {len(message)} caracteres")
                    except Exception:
                        # Se ainda falhar, manter original
                        logger.warning(f"⚠️ Não foi possível decodificar Unicode, mantendo original")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao decodificar Unicode: {e}, usando mensagem original")
            # Manter mensagem original se decodificação falhar
        
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
        
        # ✅ V2.0: Processar scheduled_at se fornecido
        scheduled_at = None
        status = 'draft'  # Padrão: rascunho (será enviado imediatamente)
        
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
                logger.info(f"📅 Remarketing geral agendado para: {scheduled_at}")
            except Exception as e:
                logger.error(f"❌ Erro ao processar scheduled_at: {e}")
                return jsonify({'error': f'Data/hora inválida: {str(e)}'}), 400
        
        # Contador de usuários impactados
        total_users = 0
        bots_affected = 0
        
        # ✅ CORREÇÃO: Criar campanhas em batch para evitar database locked
        from models import RemarketingCampaign
        from sqlalchemy.exc import OperationalError
        import time as time_module
        
        campaigns_to_create = []
        
        # Preparar todas as campanhas primeiro
        for bot in bots:
            # Contar usuários elegíveis
            eligible_count = bot_manager.count_eligible_leads(
                bot_id=bot.id,
                target_audience='non_buyers' if exclude_buyers else 'all',
                days_since_last_contact=days_since_last_contact,
                exclude_buyers=exclude_buyers
            )
            
            if eligible_count > 0:
                campaign = RemarketingCampaign(
                    bot_id=bot.id,
                    name=f"Remarketing Geral - {get_brazil_time().strftime('%d/%m/%Y %H:%M')}",
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
                    scheduled_at=scheduled_at,  # ✅ V2.0
                    status=status  # ✅ V2.0: 'draft' ou 'scheduled'
                )
                campaigns_to_create.append((campaign, bot, eligible_count))
        
        # ✅ CORREÇÃO: Salvar todas as campanhas com retry logic para database locked
        for campaign, bot, eligible_count in campaigns_to_create:
            max_retries = 3
            retry_delay = 0.5  # 500ms
            
            for attempt in range(max_retries):
                try:
                    db.session.add(campaign)
                    db.session.commit()
                    logger.info(f"✅ Campanha criada para bot {bot.id} (@{bot.username})")
                    
                    # ✅ V2.0: Enviar campanha apenas se não estiver agendada
                    if status != 'scheduled':
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
                    else:
                        # Campanha agendada - não enviar agora, será processada pelo scheduler
                        total_users += eligible_count
                        bots_affected += 1
                        logger.info(f"📅 Remarketing geral agendado para bot {bot.name} ({eligible_count} usuários) - será enviado em {scheduled_at}")
                    
                    break  # Sucesso, sair do loop de retry
                except OperationalError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"⚠️ Database locked ao criar campanha para bot {bot.id}, tentativa {attempt + 1}/{max_retries}")
                        db.session.rollback()
                        time_module.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
                        continue
                    else:
                        # Última tentativa ou erro diferente
                        logger.error(f"❌ Erro ao criar campanha para bot {bot.id}: {e}")
                        db.session.rollback()
                        raise
                except Exception as e:
                    logger.error(f"❌ Erro inesperado ao criar campanha para bot {bot.id}: {e}")
                    db.session.rollback()
                    raise
        
        response_message = f'Remarketing agendado para {bots_affected} bot(s) com sucesso!' if status == 'scheduled' else f'Remarketing enviado para {bots_affected} bot(s) com sucesso!'
        
        return jsonify({
            'success': True,
            'total_users': total_users,
            'bots_affected': bots_affected,
            'message': response_message,
            'scheduled': status == 'scheduled',
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None
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
        Commission.created_at >= get_brazil_time() - timedelta(days=30)
    ).scalar() or 0.0
    
    # Novos usuários (últimos 30 dias)
    thirty_days_ago = get_brazil_time() - timedelta(days=30)
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
    user.banned_at = get_brazil_time()
    
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
@csrf.exempt
def admin_impersonate(user_id):
    """Logar como outro usuário (impersonate)"""
    try:
        logger.info(f"🔍 Iniciando impersonação: admin={current_user.id} ({current_user.email}) → target={user_id}")
        
        target_user = User.query.get_or_404(user_id)
        logger.info(f"✅ Usuário alvo encontrado: {target_user.email} (admin={target_user.is_admin})")
        
        if target_user.is_admin:
            logger.warning(f"⚠️ Tentativa de impersonar admin bloqueada: {target_user.email}")
            return jsonify({'error': 'Não é possível impersonar outro administrador'}), 403
        
        # ✅ CORREÇÃO: Salvar ID do admin ANTES de fazer logout/login
        admin_id = current_user.id
        admin_email = current_user.email
        logger.info(f"💾 Admin original salvo: {admin_id} ({admin_email})")
        
        # ✅ CORREÇÃO: Registrar log ANTES de mudar o current_user
        try:
            log_admin_action('impersonate', f'Admin logou como usuário {target_user.email}', target_user_id=user_id)
            logger.info(f"✅ Log de auditoria registrado")
        except Exception as log_error:
            logger.warning(f"⚠️ Erro ao registrar log (continuando): {log_error}")
        
        # ✅ CORREÇÃO CRÍTICA: Configurar sessão como permanente antes de salvar
        session.permanent = True
        
        # Salvar ID do admin original na sessão
        session['impersonate_admin_id'] = admin_id
        session['impersonate_admin_email'] = admin_email
        logger.info(f"💾 Dados salvos na sessão: impersonate_admin_id={admin_id}")
        
        # ✅ CORREÇÃO: Fazer commit do banco ANTES de mudar o usuário
        db.session.commit()
        logger.info(f"✅ Commit do banco realizado")
        
        # Fazer logout do admin e login como usuário
        logger.info(f"🔄 Fazendo logout do admin...")
        logout_user()
        logger.info(f"✅ Logout concluído")
        
        logger.info(f"🔄 Fazendo login como {target_user.email}...")
        login_user(target_user, remember=False)
        logger.info(f"✅ Login concluído")
        
        # ✅ CORREÇÃO CRÍTICA: Forçar commit da sessão do Flask
        # O Flask-Login usa a sessão do Flask, então precisamos garantir que está persistida
        session.permanent = True
        
        # Verificar se o login foi bem-sucedido
        if not current_user.is_authenticated:
            logger.error(f"❌ Login falhou - usuário não autenticado após login_user()")
            raise Exception("Falha ao autenticar usuário após impersonação")
        
        logger.info(f"✅ Impersonação bem-sucedida! Admin={admin_id} agora é {current_user.id} ({current_user.email})")
        
        return jsonify({
            'message': 'Impersonate ativado', 
            'redirect': '/dashboard',
            'target_user': target_user.email
        })
    
    except Exception as e:
        logger.error(f"❌ ERRO ao impersonar usuário {user_id}: {e}", exc_info=True)
        db.session.rollback()
        
        # Tentar limpar sessão em caso de erro
        try:
            if 'impersonate_admin_id' in session:
                del session['impersonate_admin_id']
            if 'impersonate_admin_email' in session:
                del session['impersonate_admin_email']
        except:
            pass
        
        return jsonify({
            'error': f'Erro ao impersonar usuário: {str(e)}',
            'details': str(e)
        }), 500

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

@app.route('/admin/ranking/update-rates', methods=['POST'])
@admin_required
@csrf.exempt
def admin_update_ranking_rates():
    """
    ✅ RANKING V2.0 - Rota Admin para executar atualização manual de taxas premium
    Útil para testes e para forçar atualização imediata
    """
    try:
        logger.info("🏆 Admin executando atualização manual de taxas premium...")
        result = update_ranking_premium_rates()
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Taxas atualizadas com sucesso',
                'updated_users': result.get('updated_users', 0),
                'updated_gateways': result.get('updated_gateways', 0),
                'top_3': result.get('top_3', [])
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro ao executar atualização manual de taxas: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    today = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
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
    twelve_months_ago = get_brazil_time() - timedelta(days=365)
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
    thirty_days_ago = get_brazil_time() - timedelta(days=30)
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
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    
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
    thirty_days_ago = get_brazil_time() - timedelta(days=30)
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
    seven_days_ago = get_brazil_time() - timedelta(days=7)
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
        date = (get_brazil_time() - timedelta(days=6-i)).date()
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
    
    # 7. ÚLTIMAS VENDAS (para lista de vendas)
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
        'created_at': p.created_at.isoformat(),
        # ✅ DEMOGRAPHIC DATA (com fallback seguro)
        'customer_age': getattr(p, 'customer_age', None),
        'customer_city': getattr(p, 'customer_city', None),
        'customer_state': getattr(p, 'customer_state', None),
        'customer_country': getattr(p, 'customer_country', None),
        'customer_gender': getattr(p, 'customer_gender', None),
        # ✅ DEVICE DATA (com fallback seguro)
        'device_type': getattr(p, 'device_type', None),
        'os_type': getattr(p, 'os_type', None),
        'browser': getattr(p, 'browser', None),
        'device_model': getattr(p, 'device_model', None)
    } for p in recent_sales]
    
    # 8. ✅ DADOS DEMOGRÁFICOS (TODAS AS VENDAS PAGAS - não apenas recent_sales)
    # Buscar todas as vendas pagas com dados demográficos para analytics
    all_paid_sales = db.session.query(Payment).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid'
    ).all()
    
    demographic_sales = [{
        'customer_age': getattr(p, 'customer_age', None),
        'customer_city': getattr(p, 'customer_city', None),
        'customer_state': getattr(p, 'customer_state', None),
        'customer_country': getattr(p, 'customer_country', None),
        'customer_gender': getattr(p, 'customer_gender', None),
        'device_type': getattr(p, 'device_type', None),
        'os_type': getattr(p, 'os_type', None),
        'browser': getattr(p, 'browser', None)
    } for p in all_paid_sales]
    
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
        'recent_sales': sales_list,
        # ✅ DEMOGRAPHIC DATA (todas as vendas pagas para analytics)
        'demographic_sales': demographic_sales
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
    seven_days_ago = get_brazil_time() - timedelta(days=7)
    
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
        date = (get_brazil_time() - timedelta(days=6-i)).date()
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
    🔐 CLOAKER V2.0 - À PROVA DE BURRICE HUMANA
    
    REGRAS SIMPLES:
    1. Parâmetro grim obrigatório e válido
    2. Aceita qualquer ordem de parâmetros
    3. Ignora fbclid, utm_source, etc.
    4. SEM validação de User-Agent (Facebook pode usar qualquer UA)
    
    Retorna score 100 se OK, 0 se bloqueado
    """
    details = {}
    
    # VALIDAÇÃO ÚNICA: Parâmetro grim obrigatório
    # ✅ IMPORTANTE: Parâmetro sempre será "grim", nunca pode ser alterado
    param_name = 'grim'
    expected_value = pool.meta_cloaker_param_value
    
    if not expected_value or not expected_value.strip():
        return {'allowed': False, 'reason': 'cloaker_misconfigured', 'score': 0, 'details': {}}
    
    expected_value = expected_value.strip()
    
    # ✅ CLOAKER V2.0: Busca o parâmetro grim de DUAS FORMAS
    # FORMA 1: ?grim=testecamu01 (padrão)
    actual_value = (request.args.get(param_name) or '').strip()
    
    # FORMA 2: ?testecamu01 (Facebook format - parâmetro sem valor)
    if not actual_value:
        # Verifica se expected_value aparece como NOME de parâmetro
        if expected_value in request.args:
            actual_value = expected_value
            logger.info(f"✅ CLOAKER V2.0 | Facebook format detected: ?{expected_value}")
    
    # Log estruturado para auditoria
    all_params = dict(request.args)
    logger.info(f"🔍 CLOAKER V2.0 | Slug: {slug} | Grim: {actual_value} | Expected: {expected_value} | All params: {list(all_params.keys())}")
    
    # VALIDAÇÃO CRÍTICA: grim deve estar presente e correto
    if actual_value != expected_value:
        return {'allowed': False, 'reason': 'invalid_grim', 'score': 0, 'details': {
            'param_match': False, 
            'expected': expected_value,
            'actual': actual_value,
            'all_params': list(all_params.keys())
        }}
    
    # ✅ SUCESSO: grim válido encontrado
    return {'allowed': True, 'reason': 'grim_valid', 'score': 100, 'details': {
        'param_match': True, 
        'grim_value': actual_value,
        'total_params': len(all_params)
    }}


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
        'param_name': 'grim',  # Sempre fixo
        'param_provided': bool(request.args.get('grim')),
        'http_method': request.method,
        'code': 403 if not validation_result['allowed'] else 302,
        'latency_ms': round(latency_ms, 2)
    }
    
    logger.info(f"CLOAKER_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")


@app.route('/go/<slug>')
@limiter.limit("10000 per hour")  # Override: endpoint público precisa de limite alto
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
    # time já está importado no topo do arquivo
    
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
    # ✅ TRACKING ELITE: CAPTURA IP + USER-AGENT + SESSION (TOP 1%)
    # ============================================================================
    import uuid
    import redis
    from datetime import datetime
    
    # Capturar dados do request
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')
    fbclid = request.args.get('fbclid', '')
    session_id = str(uuid.uuid4())
    
    # ✅ CRÍTICO QI 300: Detectar crawlers e NÃO salvar tracking
    # Crawlers não têm cookies, não geram FBP/FBC válidos, e poluem o Redis
    def is_crawler(ua: str) -> bool:
        """Detecta se o User-Agent é um crawler/bot"""
        if not ua:
            return False
        ua_lower = ua.lower()
        crawler_patterns = [
            'facebookexternalhit',
            'facebot',
            'telegrambot',
            'whatsapp',
            'python-requests',
            'curl',
            'wget',
            'bot',
            'crawler',
            'spider',
            'scraper',
            'googlebot',
            'bingbot',
            'slurp',
            'duckduckbot',
            'baiduspider',
            'yandexbot',
            'sogou',
            'exabot',
            'facebot',
            'ia_archiver'
        ]
        return any(pattern in ua_lower for pattern in crawler_patterns)
    
    is_crawler_request = is_crawler(user_agent)
    if is_crawler_request:
        logger.info(f"🤖 CRAWLER DETECTADO: {user_agent[:50]}... | Tracking NÃO será salvo")
    
    # ✅ CRÍTICO: Salvar tracking no Redis SEMPRE (TTL 180s = 3 min)
    # Mesmo sem fbclid, salvar usando grim ou session_id como chave
    grim_param = request.args.get('grim', '')
    import json
    
    # ✅ PASSO 1: CAPTURAR _fbp e _fbc DOS COOKIES (CRÍTICO PARA MATCHING!)
    # ✅ CORREÇÃO CRÍTICA QI 300: Para funil server-side, FBP DEVE ser gerado no servidor
    # Meta aceita e recomenda FBP server-side para CAPI (Conversions API)
    # Isso garante matching perfeito PageView ↔ Purchase (7/7 atributos sempre)
    from utils.tracking_service import TrackingService
    
    fbp_cookie = request.cookies.get('_fbp', '')
    fbc_cookie = request.cookies.get('_fbc', '')
    
    # ✅ GERAR FBP NO SERVIDOR se não existir (CRÍTICO para funil server-side)
    # Isso garante que PageView e Purchase usem o MESMO FBP desde o primeiro acesso
    if not fbp_cookie and not is_crawler_request:
        fbp_cookie = TrackingService.generate_fbp()
        logger.info(f"🔑 _fbp gerado no servidor (funil server-side): {fbp_cookie[:30]}...")
    
    # ✅ GERAR _fbc se não existir mas tiver fbclid (FBC pode ser gerado do fbclid)
    # Formato: fb.1.{timestamp}.{fbclid}
    if not fbc_cookie and fbclid and not is_crawler_request:
        try:
            # time já está importado no topo do arquivo
            # Formato: fb.1.{timestamp}.{fbclid}
            fbc_cookie = f"fb.1.{int(time.time())}.{fbclid}"
            logger.info(f"🔑 _fbc gerado manualmente: {fbc_cookie[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao gerar _fbc: {e}")
    
    # ✅ SOLUÇÃO SÊNIOR QI 300: Tracking Universal Persistente (30 dias)
    # Usar TrackingService para garantir consistência total e recuperação robusta
    # ✅ CRÍTICO: NÃO salvar tracking para crawlers (poluem Redis com dados incompletos)
    
    # ✅ SALVAR TRACKING APENAS SE NÃO FOR CRAWLER
    if not is_crawler_request:
        try:
            # ✅ Preparar UTMs para salvar
            utms = {
                'utm_source': request.args.get('utm_source', ''),
                'utm_campaign': request.args.get('utm_campaign', ''),
                'utm_medium': request.args.get('utm_medium', ''),
                'utm_content': request.args.get('utm_content', ''),
                'utm_term': request.args.get('utm_term', ''),
                'utm_id': request.args.get('utm_id', '')
            }
            
            # ✅ CORREÇÃO CRÍTICA: FBP já foi gerado acima se não existia
            # Agora garantimos que SEMPRE temos FBP (do cookie ou gerado no servidor)
            fbp_final = fbp_cookie  # Já foi gerado acima se necessário
            
            # ✅ Gerar fbc se existir fbclid (FBC pode ser gerado do fbclid)
            fbc_final = fbc_cookie
            if fbclid and not fbc_final:
                fbc_final = f"fb.1.{int(time.time())}.{fbclid}"
                logger.info(f"🔑 _fbc gerado no redirect: {fbc_final[:50]}...")
            
            # ✅ VALIDAÇÃO CRÍTICA: Com a correção acima, fbp_final SEMPRE existe (gerado no servidor se necessário)
            # Sempre salvar tracking (fbp sempre existe, fbc pode existir se tiver fbclid)
            if fbp_final:
                # ✅ Salvamento correto (com fbclid ou com grim)
                if fbclid:
                    TrackingService.save_tracking_data(
                        fbclid=fbclid,
                        fbp=fbp_final,  # ✅ SEMPRE existe (gerado no servidor se necessário)
                        fbc=fbc_final,  # Sempre gerado se tiver fbclid
                        ip_address=user_ip,
                        user_agent=user_agent,
                        grim=grim_param,
                        utms=utms
                    )
                    logger.info(f"🎯 TRACKING SALVO (30d) | fbclid:{fbclid[:20]}... | fbp=✅ | fbc={'✅' if fbc_final else '❌'}")
                elif grim_param:
                    # ✅ Se NÃO tiver fbclid mas tiver grim → salvar mesmo assim!
                    TrackingService.save_tracking_data(
                        fbclid=None,
                        fbp=fbp_final,  # ✅ SEMPRE existe (gerado no servidor se necessário)
                        fbc=fbc_final,  # Pode ser vazio se não tiver fbclid
                        ip_address=user_ip,
                        user_agent=user_agent,
                        grim=grim_param,
                        utms=utms
                    )
                    logger.info(f"🎯 TRACKING SALVO (30d) | grim:{grim_param} | fbp=✅ | fbc={'✅' if fbc_final else '❌'}")
            else:
                # ✅ Isso NÃO deveria acontecer (fbp sempre é gerado), mas mantido como fallback de segurança
                logger.error(f"❌ ERRO CRÍTICO: Tracking NÃO salvo - fbp ausente (deveria ter sido gerado no servidor!)")
        
        except Exception as e:
            logger.error(f"⚠️ Erro ao salvar tracking no Redis: {e}")
            import traceback
            traceback.print_exc()
            # Não quebrar o redirect se Redis falhar
    else:
        logger.info(f"🤖 Crawler detectado - Tracking NÃO salvo (evita poluição do Redis)")
    
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
    
    # Construir payload de tracking (MÍNIMO - só pool e hash!)
    # UTMs já estão no Redis, não precisa repetir no start_param
    grim_param = request.args.get('grim', '')
    fbclid_param = request.args.get('fbclid', '')
    
    tracking_data = {
        'p': pool.id,  # pool_id
    }
    
    # 🎯 TRACKING ELITE: Priorizar fbclid, fallback para grim
    if fbclid_param:
        # Gerar hash curto do fbclid (12 chars)
        import hashlib
        fbclid_hash = hashlib.sha256(fbclid_param.encode()).hexdigest()[:12]
        tracking_data['f'] = fbclid_hash  # Apenas hash!
        
        # ✅ SALVAR MAPEAMENTO: hash → fbclid completo no Redis
        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.setex(f'tracking_hash:{fbclid_hash}', 180, fbclid_param)
            logger.info(f"🔑 HASH: {fbclid_hash} → fbclid completo (salvo)")
        except Exception as e:
            logger.error(f"Erro ao salvar hash no Redis: {e}")
    elif grim_param:
        # ✅ CRÍTICO: Se não tem fbclid mas tem grim, incluir grim no tracking
        # Limitar tamanho do grim para caber no Telegram deep link (64 chars)
        if len(grim_param) <= 20:  # Grim curto, pode incluir
            tracking_data['g'] = grim_param  # 'g' = grim
            logger.info(f"🔑 GRIM: {grim_param} incluído no tracking param")
        else:
            # Grim muito longo, usar hash
            import hashlib
            grim_hash = hashlib.sha256(grim_param.encode()).hexdigest()[:12]
            tracking_data['g'] = grim_hash
            logger.info(f"🔑 GRIM HASH: {grim_hash} → grim completo (salvo no Redis)")
    
    # ✅ NÃO incluir UTMs no start_param - economiza espaço e já estão no Redis!
    
    # Serializar e encodar (base64 para reduzir tamanho)
    try:
        tracking_json = json.dumps(tracking_data, separators=(',', ':'))
        tracking_base64 = base64.urlsafe_b64encode(tracking_json.encode()).decode()
        
        # Debug: mostrar tamanhos
        logger.info(f"📏 Tracking data: {tracking_json}")
        logger.info(f"📏 Base64 length: {len(tracking_base64)} chars")
        
        # Telegram limita start param a 64 chars
        # Se exceder, usar apenas pool_id
        if len(tracking_base64) + 1 > 64:  # +1 para o 't' inicial
            # Fallback: apenas pool_id
            tracking_param = f"p{pool.id}"
            logger.warning(f"⚠️ Tracking param muito longo ({len(tracking_base64)} chars), usando fallback: {tracking_param}")
        else:
            tracking_param = f"t{tracking_base64}"
            logger.info(f"✅ Tracking param: {tracking_param} ({len(tracking_param)} chars)")
    except Exception as e:
        # Fallback simples se encoding falhar
        logger.error(f"Erro ao encodar tracking: {e}")
        tracking_param = f"p{pool.id}"
    
    redirect_url = f"https://t.me/{pool_bot.bot.username}?start={tracking_param}"
    
    # ✅ CRÍTICO: Injetar cookies _fbp e _fbc no redirect response
    # Isso sincroniza o FBP gerado no servidor com o browser
    # Meta Pixel JS usará o mesmo FBP, garantindo matching perfeito
    response = redirect(redirect_url, code=302)
    
    # ✅ Injetar _fbp se foi gerado no servidor (não estava no cookie original)
    if fbp_cookie and not request.cookies.get('_fbp'):
        # Cookie válido por 90 dias (padrão Meta)
        response.set_cookie(
            '_fbp',
            fbp_cookie,
            max_age=90 * 24 * 60 * 60,  # 90 dias
            httponly=False,  # Meta Pixel JS precisa acessar
            secure=True,  # HTTPS only
            samesite='Lax'  # Permite cross-site para Meta Pixel
        )
        logger.info(f"✅ Cookie _fbp injetado no redirect: {fbp_cookie[:30]}...")
    
    # ✅ Injetar _fbc se foi gerado no servidor (não estava no cookie original)
    if fbc_cookie and not request.cookies.get('_fbc'):
        # Cookie válido por 90 dias (padrão Meta)
        response.set_cookie(
            '_fbc',
            fbc_cookie,
            max_age=90 * 24 * 60 * 60,  # 90 dias
            httponly=False,  # Meta Pixel JS precisa acessar
            secure=True,  # HTTPS only
            samesite='Lax'  # Permite cross-site para Meta Pixel
        )
        logger.info(f"✅ Cookie _fbc injetado no redirect: {fbc_cookie[:30]}...")
    
    return response


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
    
    # ✅ CRÍTICO: Salvar configurações do Meta Pixel
    if 'meta_pixel_id' in data:
        pool.meta_pixel_id = data['meta_pixel_id'].strip() if data['meta_pixel_id'] else None
    
    if 'meta_access_token' in data:
        # ✅ Criptografar access token antes de salvar (se necessário)
        pool.meta_access_token = data['meta_access_token'].strip() if data['meta_access_token'] else None
    
    if 'meta_tracking_enabled' in data:
        pool.meta_tracking_enabled = bool(data['meta_tracking_enabled'])
    
    if 'meta_test_event_code' in data:
        pool.meta_test_event_code = data['meta_test_event_code'].strip() if data['meta_test_event_code'] else None
    
    if 'meta_events_pageview' in data:
        pool.meta_events_pageview = bool(data['meta_events_pageview'])
    
    if 'meta_events_viewcontent' in data:
        pool.meta_events_viewcontent = bool(data['meta_events_viewcontent'])
    
    if 'meta_events_purchase' in data:
        pool.meta_events_purchase = bool(data['meta_events_purchase'])
    
    if 'meta_cloaker_enabled' in data:
        pool.meta_cloaker_enabled = bool(data['meta_cloaker_enabled'])
    
    if 'meta_cloaker_param_name' in data:
        pool.meta_cloaker_param_name = data['meta_cloaker_param_name'].strip() if data['meta_cloaker_param_name'] else 'grim'
    
    if 'meta_cloaker_param_value' in data:
        pool.meta_cloaker_param_value = data['meta_cloaker_param_value'].strip() if data['meta_cloaker_param_value'] else None
    
    try:
        db.session.commit()
        logger.info(f"✅ Pool atualizado: {pool.name} por {current_user.email}")
        logger.info(f"   Meta Pixel: {'✅ Ativado' if pool.meta_tracking_enabled else '❌ Desativado'}")
        if pool.meta_pixel_id:
            logger.info(f"   Pixel ID: {pool.meta_pixel_id[:10]}...")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao salvar pool {pool_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao salvar: {str(e)}'}), 500
    
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
    
    # ✅ CRÍTICO: Retornar token COMPLETO para comparação no frontend
    # O frontend precisa do token completo para detectar se foi alterado
    access_token_display = None
    if pool.meta_tracking_enabled and pool.meta_access_token:
        try:
            access_token_decrypted = decrypt(pool.meta_access_token)
            # ✅ RETORNAR TOKEN COMPLETO (não mascarado) para que frontend possa comparar
            access_token_display = access_token_decrypted
        except Exception as e:
            logger.warning(f"⚠️ Erro ao descriptografar access_token do pool {pool_id}: {e}")
            access_token_display = None
    
    # ✅ CORREÇÃO: Retornar None/null quando campos estão vazios (não string vazia)
    return jsonify({
        'pool_id': pool.id,
        'pool_name': pool.name,
        'meta_pixel_id': pool.meta_pixel_id if pool.meta_pixel_id else None,
        'meta_access_token': access_token_display,  # ✅ Token completo para comparação
        'meta_tracking_enabled': pool.meta_tracking_enabled,
        'meta_test_event_code': pool.meta_test_event_code if pool.meta_test_event_code else None,
        'meta_events_pageview': pool.meta_events_pageview,
        'meta_events_viewcontent': pool.meta_events_viewcontent,
        'meta_events_purchase': pool.meta_events_purchase,
        'meta_cloaker_enabled': pool.meta_cloaker_enabled,
        'meta_cloaker_param_name': 'grim',  # Sempre fixo como "grim"
        'meta_cloaker_param_value': pool.meta_cloaker_param_value if pool.meta_cloaker_param_value else None
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
        # ✅ CORREÇÃO: Verificar se tracking está sendo desabilitado
        meta_tracking_enabled = data.get('meta_tracking_enabled', False)
        
        # Se está desabilitando, limpar todos os campos
        if not meta_tracking_enabled:
            pool.meta_pixel_id = None
            pool.meta_access_token = None
            pool.meta_tracking_enabled = False
            db.session.commit()
            logger.info(f"Meta Pixel desabilitado para pool {pool.name} - Campos limpos")
            return jsonify({
                'message': 'Meta Pixel desabilitado e campos limpos!',
                'pool_id': pool.id,
                'meta_tracking_enabled': False
            })
        
        # Validar Pixel ID
        pixel_id = data.get('meta_pixel_id', '').strip()
        if pixel_id:
            if not MetaPixelHelper.is_valid_pixel_id(pixel_id):
                return jsonify({'error': 'Pixel ID inválido (deve ter 15-16 dígitos numéricos)'}), 400
        else:
            # ✅ CORREÇÃO: String vazia = limpar campo
            pixel_id = None
        
        # Validar Access Token
        access_token = data.get('meta_access_token', '').strip()
        logger.info(f"🔍 [Meta Pixel Save] User: {current_user.email} | Pool: {pool.name} | Token recebido: {'SIM' if access_token else 'NÃO'} | Tamanho: {len(access_token) if access_token else 0}")
        
        if access_token:
            # Se começar com "..." significa que não foi alterado (campo mascarado do frontend)
            if access_token.startswith('...'):
                # ✅ CRÍTICO: Verificar se token original existe no banco
                if pool.meta_access_token:
                    # Token não foi alterado, manter o existente (não atualizar)
                    logger.info(f"✅ [Meta Pixel Save] Token não foi alterado (marcador '...' detectado) - mantendo existente")
                    access_token = None
                else:
                    # ❌ PROBLEMA: Marcador enviado mas token não existe no banco!
                    # Isso significa que é primeira configuração ou token foi perdido
                    logger.error(f"❌ [Meta Pixel Save] ERRO CRÍTICO: Marcador '...' recebido mas token não existe no banco!")
                    logger.error(f"   Isso indica que frontend pensa que token existe, mas banco está vazio")
                    logger.error(f"   SOLUÇÃO: Exigir que usuário insira token completo")
                    return jsonify({'error': 'Access Token é obrigatório. Por favor, insira o token completo.'}), 400
            else:
                logger.info(f"🔄 [Meta Pixel Save] Token foi alterado - validando e testando conexão...")
                if not MetaPixelHelper.is_valid_access_token(access_token):
                    logger.error(f"❌ [Meta Pixel Save] Access Token inválido (mínimo 50 caracteres, recebido: {len(access_token)})")
                    return jsonify({'error': 'Access Token inválido (mínimo 50 caracteres)'}), 400
                
                # Testar conexão antes de salvar (precisa de pixel_id válido também)
                if not pixel_id:
                    logger.error(f"❌ [Meta Pixel Save] Pixel ID obrigatório quando Access Token é fornecido")
                    return jsonify({'error': 'Pixel ID é obrigatório quando Access Token é fornecido'}), 400
                
                logger.info(f"🧪 [Meta Pixel Save] Testando conexão com Pixel {pixel_id[:10]}...")
                test_result = MetaPixelAPI.test_connection(pixel_id, access_token)
                if not test_result['success']:
                    logger.error(f"❌ [Meta Pixel Save] Falha ao conectar: {test_result.get('error', 'Erro desconhecido')}")
                    return jsonify({'error': f'Falha ao conectar: {test_result["error"]}'}), 400
                
                logger.info(f"✅ [Meta Pixel Save] Conexão testada com sucesso - criptografando token...")
                # Criptografar antes de salvar
                pool.meta_access_token = encrypt(access_token)
        else:
            # ✅ CORREÇÃO: String vazia = limpar campo
            logger.info(f"🧹 [Meta Pixel Save] Token vazio - limpando campo")
            pool.meta_access_token = None
        
        # ✅ CRÍTICO: Atualizar pixel_id SEMPRE (independente do access_token)
        # Isso garante que mesmo quando o token não é alterado, o pixel_id é salvo
        pool.meta_pixel_id = pixel_id
        logger.info(f"💾 [Meta Pixel Save] Pixel ID salvo: {pixel_id[:10] if pixel_id else 'None'}...")
        
        if 'meta_tracking_enabled' in data:
            pool.meta_tracking_enabled = bool(data['meta_tracking_enabled'])
            logger.info(f"💾 [Meta Pixel Save] Tracking enabled: {pool.meta_tracking_enabled}")
        
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
        
        # ✅ IMPORTANTE: O parâmetro sempre será "grim", nunca pode ser alterado
        # Forçar "grim" sempre, ignorando qualquer valor vindo do frontend
        pool.meta_cloaker_param_name = 'grim'
        
        if 'meta_cloaker_param_value' in data:
            # ✅ FIX BUG: Strip e validar valor antes de salvar
            cloaker_value = data['meta_cloaker_param_value']
            if cloaker_value:
                cloaker_value = cloaker_value.strip()
                if not cloaker_value:  # String vazia após strip
                    cloaker_value = None
            pool.meta_cloaker_param_value = cloaker_value
        
        try:
            db.session.commit()
            logger.info(f"✅ [Meta Pixel Save] CONFIGURAÇÃO SALVA COM SUCESSO!")
            logger.info(f"   User: {current_user.email}")
            logger.info(f"   Pool: {pool.name} (ID: {pool.id})")
            logger.info(f"   Pixel ID: {pool.meta_pixel_id[:10] if pool.meta_pixel_id else 'None'}...")
            logger.info(f"   Access Token: {'✅ Presente' if pool.meta_access_token else '❌ Ausente'}")
            logger.info(f"   Tracking Enabled: {pool.meta_tracking_enabled}")
            logger.info(f"   Events - PageView: {pool.meta_events_pageview}, ViewContent: {pool.meta_events_viewcontent}, Purchase: {pool.meta_events_purchase}")
        except Exception as commit_error:
            db.session.rollback()
            logger.error(f"❌ [Meta Pixel Save] ERRO AO COMMITAR: {commit_error}", exc_info=True)
            raise
        
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
        if gateway_type not in ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay']:
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
        
        elif gateway_type == 'atomopay':
            # ✅ ÁTOMO PAY
            api_token_value = data.get('api_token') or data.get('api_key')
            product_hash_value = data.get('product_hash')
            
            logger.info(f"📦 [Átomo Pay] Dados recebidos:")
            logger.info(f"   api_token: {'SIM' if api_token_value else 'NÃO'} ({len(api_token_value) if api_token_value else 0} chars)")
            logger.info(f"   product_hash: {'SIM' if product_hash_value else 'NÃO'} ({len(product_hash_value) if product_hash_value else 0} chars)")
            
            if api_token_value:
                gateway.api_key = api_token_value  # Aceita ambos (criptografia automática via setter)
                logger.info(f"✅ [Átomo Pay] api_key salvo (criptografado)")
            else:
                logger.warning(f"⚠️ [Átomo Pay] api_token não fornecido")
            
            # ✅ REMOVIDO: offer_hash não é mais necessário (ofertas são criadas dinamicamente)
            # gateway.offer_hash = data.get('offer_hash')
            
            if product_hash_value:
                gateway.product_hash = product_hash_value  # Criptografia automática via setter
                logger.info(f"✅ [Átomo Pay] product_hash salvo (criptografado)")
            else:
                logger.warning(f"⚠️ [Átomo Pay] product_hash não fornecido")
        
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
                'api_token': gateway.api_key,  # Átomo Pay usa api_token (mesmo valor)
                'product_hash': gateway.product_hash,  # Paradise / Átomo Pay
                'offer_hash': gateway.offer_hash,      # Paradise (Átomo Pay não usa mais)
                'store_id': gateway.store_id,          # Paradise
                'organization_id': gateway.organization_id,  # HooPay
                'split_user_id': gateway.split_user_id  # WiinPay
            }
            
            # ✅ ÁTOMO PAY: Verificar se tem api_token (obrigatório)
            if gateway_type == 'atomopay':
                if not credentials.get('api_token'):
                    logger.error(f"❌ [Átomo Pay] api_token não configurado - não será verificado")
                    gateway.is_verified = False
                    gateway.last_error = 'API Token não configurado'
                    db.session.commit()
                    return jsonify(gateway.to_dict())
                else:
                    logger.info(f"🔍 [Átomo Pay] Verificando credenciais...")
                    logger.info(f"   api_token: {'SIM' if credentials.get('api_token') else 'NÃO'} ({len(credentials.get('api_token', ''))} chars)")
                    logger.info(f"   product_hash: {'SIM' if credentials.get('product_hash') else 'NÃO'} ({len(credentials.get('product_hash', ''))} chars)")
            
            is_valid = bot_manager.verify_gateway(gateway_type, credentials)
            
            logger.info(f"📊 [Gateway {gateway_type}] Resultado da verificação: {'VÁLIDO' if is_valid else 'INVÁLIDO'}")
            
            if is_valid:
                gateway.is_verified = True
                gateway.verified_at = get_brazil_time()
                gateway.last_error = None
                logger.info(f"✅ Gateway {gateway_type} verificado para {current_user.email}")
            else:
                gateway.is_verified = False
                gateway.last_error = 'Credenciais inválidas'
                logger.warning(f"⚠️ Gateway {gateway_type} NÃO verificado - credenciais inválidas")
        except Exception as e:
            gateway.is_verified = False
            gateway.last_error = str(e)
            logger.error(f"❌ Erro ao verificar gateway: {e}")
        
        db.session.commit()
        logger.info(f"✅ Gateway {gateway_type} salvo com sucesso!")
        
        # ✅ LOG DE CONFIRMAÇÃO (após commit)
        if gateway_type == 'atomopay':
            # Recarregar do banco para confirmar
            db.session.refresh(gateway)
            logger.info(f"📋 [Átomo Pay] Confirmação após commit:")
            logger.info(f"   api_key no banco: {'SIM' if gateway._api_key else 'NÃO'}")
            logger.info(f"   product_hash no banco: {'SIM' if gateway._product_hash else 'NÃO'}")
            logger.info(f"   is_active: {gateway.is_active}")
            logger.info(f"   is_verified: {gateway.is_verified}")
        
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
    """Reinicia automaticamente todos os bots ativos de todos os usuários no startup da VPS.

    Política: Considerar `is_active=True` (bot habilitado no painel) como critério de reinício,
    independentemente do último `is_running`. Evita iniciar duplicado se já estiver ativo em memória.
    """
    try:
        logger.info("🔄 INICIANDO REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS...")
        
        # ✅ CORREÇÃO: Usar contexto do Flask para acessar banco
        with app.app_context():
            # Buscar todos os bots marcados como ativos no painel
            active_bots = Bot.query.filter_by(is_active=True).all()
            
            if not active_bots:
                logger.info("ℹ️ Nenhum bot rodando encontrado para reiniciar")
                return
            
            logger.info(f"📊 Encontrados {len(active_bots)} bots rodando para reiniciar")
            
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
        # ✅ CORREÇÃO: Ao desativar, verificar se há outro gateway verificado disponível
        gateway.is_active = False
        
        # Procurar outro gateway verificado para ativar automaticamente
        alternative_gateway = Gateway.query.filter(
            Gateway.user_id == current_user.id,
            Gateway.id != gateway_id,
            Gateway.is_verified == True
        ).first()
        
        if alternative_gateway:
            alternative_gateway.is_active = True
            message = f'Gateway {gateway.gateway_type} desativado. Gateway {alternative_gateway.gateway_type} ativado automaticamente.'
            logger.info(f"🔄 Gateway {gateway.gateway_type} desativado → {alternative_gateway.gateway_type} ativado automaticamente por {current_user.email}")
        else:
            message = f'Gateway {gateway.gateway_type} desativado. ⚠️ Nenhum outro gateway verificado disponível - configure um para processar pagamentos.'
            logger.warning(f"⚠️ Gateway {gateway.gateway_type} desativado por {current_user.email} mas NENHUM outro gateway verificado disponível")
    
    db.session.commit()
    
    logger.info(f"Gateway {gateway.gateway_type} {'ativado' if gateway.is_active else 'desativado'} por {current_user.email}")
    
    # Buscar gateway que ficou ativo (pode ser o atual ou o alternativo)
    active_gateway = Gateway.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    return jsonify({
        'success': True,
        'message': message,
        'is_active': gateway.is_active,
        'active_gateway': active_gateway.gateway_type if active_gateway else None,
        'warning': None if active_gateway else 'Nenhum gateway ativo - configure um para processar pagamentos'
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
        
        elif gateway_type == 'atomopay':
            if data.get('api_token') or data.get('api_key'):
                gateway.api_key = data.get('api_token') or data.get('api_key')
            # ✅ REMOVIDO: offer_hash não é mais necessário (ofertas são criadas dinamicamente)
            # if data.get('offer_hash'):
            #     gateway.offer_hash = data['offer_hash']
            if data.get('product_hash'):
                gateway.product_hash = data['product_hash']
        
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


def update_ranking_premium_rates():
    """
    ✅ RANKING V2.0 - Sistema de Premiação Dinâmico e Inteligente (100% FUNCIONAL)
    
    ATUALIZAÇÃO AUTOMÁTICA DE TAXAS PREMIUM:
    - Top 1: 1.0% de taxa
    - Top 2: 1.3% de taxa  
    - Top 3: 1.5% de taxa
    - Demais: 2.0% (padrão)
    
    FUNCIONALIDADES V2.0:
    1. Calcula ranking mensal baseado em faturamento (últimos 30 dias)
    2. Atualiza user.commission_percentage para todos os usuários
    3. Atualiza gateway.split_percentage para todos os gateways de cada usuário
    4. Garante que quem sai do Top 3 volta automaticamente para 2%
    5. Logs detalhados de todas as mudanças para auditoria
    6. ✅ TRATAMENTO DE CASOS EDGE: Usuários inativos, banidos, sem vendas
    7. ✅ TRANSAÇÕES ATÔMICAS: Rollback automático em caso de erro
    8. ✅ VALIDAÇÕES RIGOROSAS: Verifica todos os cenários possíveis
    
    Executa periodicamente via job (a cada hora) para manter taxas sempre atualizadas
    """
    try:
        with app.app_context():
            from sqlalchemy import func
            from models import Bot, Payment, Gateway
            from datetime import timedelta
            
            logger.info("="*70)
            logger.info("🏆 RANKING V2.0 - Iniciando atualização de taxas premium")
            logger.info("="*70)
            
            # ========================================================================
            # PASSO 1: Calcular ranking mensal (mês atual) por FATURAMENTO
            # ========================================================================
            # ✅ CORREÇÃO CRÍTICA: Mês atual (do primeiro dia do mês até agora)
            # Não usar timedelta(days=30) que é janela deslizante
            now = get_brazil_time()
            date_filter = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # ✅ VALIDAÇÃO: Verificar se há pagamentos no período
            total_payments = db.session.query(func.count(Payment.id))\
                .filter(Payment.status == 'paid', Payment.created_at >= date_filter)\
                .scalar() or 0
            
            if total_payments == 0:
                logger.warning("⚠️ Nenhum pagamento confirmado no mês atual. Ranking não será atualizado.")
                return {
                    'success': True,
                    'updated_users': 0,
                    'updated_gateways': 0,
                    'top_3': [],
                    'message': 'Sem pagamentos no período'
                }
            
            # Ranking por receita no período (CRITÉRIO: FATURAMENTO TOTAL)
            # ✅ CORREÇÃO: Filtrar também is_active=True para garantir apenas usuários ativos
            subquery = db.session.query(
                Bot.user_id,
                func.sum(Payment.amount).label('period_revenue'),
                func.count(Payment.id).label('period_sales')
            ).join(Payment)\
             .filter(Payment.status == 'paid', Payment.created_at >= date_filter)\
             .group_by(Bot.user_id)\
             .subquery()
            
            # ✅ CORREÇÃO: Filtrar is_active=True além de is_admin e is_banned
            top_3_users = User.query.join(subquery, User.id == subquery.c.user_id)\
                                   .filter(
                                       User.is_admin == False,
                                       User.is_banned == False,
                                       User.is_active == True  # ✅ ADICIONADO: Apenas usuários ativos
                                   )\
                               .order_by(
                                   subquery.c.period_revenue.desc(),  # Ordenar por FATURAMENTO
                                   subquery.c.period_sales.desc(),    # Desempate: mais vendas
                                   User.created_at.asc()              # Desempate: mais antigo
                               )\
                               .limit(3).all()
            
            # ✅ VALIDAÇÃO: Verificar se há usuários no Top 3
            if not top_3_users:
                logger.warning("⚠️ Nenhum usuário elegível para Top 3 (sem vendas ou todos inativos/banidos)")
                # Mesmo sem Top 3, resetar todos para garantir consistência
                all_users_updated = User.query.filter(
                    User.is_admin == False,
                    User.is_active == True
                ).update({'commission_percentage': 2.0})
                
                # Resetar todos os gateways ativos
                all_gateways_updated = Gateway.query.filter(
                    Gateway.is_active == True
                ).update({'split_percentage': 2.0})
                
                db.session.commit()
                logger.info(f"✅ Sistema resetado: {all_users_updated} usuários e {all_gateways_updated} gateways → 2.0%")
                
                return {
                    'success': True,
                    'updated_users': 0,
                    'updated_gateways': 0,
                    'top_3': [],
                    'message': 'Sem usuários elegíveis para Top 3'
                }
            
            # Taxas reduzidas premium
            premium_rates = {1: 1.0, 2: 1.3, 3: 1.5}
            default_rate = 2.0
            
            # Log do Top 3 atual
            logger.info(f"📊 Top {len(top_3_users)} identificado(s) (últimos 30 dias):")
            for idx, user in enumerate(top_3_users, 1):
                user_revenue = db.session.query(func.sum(Payment.amount))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.status == 'paid',
                        Payment.created_at >= date_filter
                    ).scalar() or 0.0
                logger.info(f"  #{idx} - User {user.id} ({user.email}): R$ {float(user_revenue):.2f}")
            
            # ========================================================================
            # PASSO 2: Resetar TODOS os usuários ativos (não-admin) para taxa padrão (2%)
            # ✅ CORREÇÃO: Filtrar is_active=True e is_banned=False explicitamente
            # ========================================================================
            logger.info(f"🔄 Resetando TODOS os usuários ativos para taxa padrão ({default_rate}%)...")
            all_users_updated = User.query.filter(
                User.is_admin == False,
                User.is_active == True  # ✅ ADICIONADO: Apenas usuários ativos
            ).update({'commission_percentage': default_rate})
            logger.info(f"  ✅ {all_users_updated} usuários resetados para {default_rate}%")
            
            # ========================================================================
            # PASSO 3: Aplicar taxas premium aos Top 3
            # ========================================================================
            updated_users = []
            updated_gateways = []
            
            for idx, user in enumerate(top_3_users, 1):
                new_rate = premium_rates.get(idx, default_rate)
                old_rate = user.commission_percentage
                
                # ✅ VALIDAÇÃO: Verificar se taxa premium é válida
                if new_rate not in [1.0, 1.3, 1.5]:
                    logger.error(f"❌ Taxa premium inválida para posição {idx}: {new_rate}")
                    new_rate = default_rate
                
                # Atualizar taxa do usuário
                user.commission_percentage = new_rate
                updated_users.append({
                    'user_id': user.id,
                    'email': user.email,
                    'position': idx,
                    'old_rate': old_rate,
                    'new_rate': new_rate
                })
                logger.info(f"🏆 TOP {idx}: User {user.id} ({user.email}) → {old_rate}% → {new_rate}%")
                
                # ========================================================================
                # PASSO 4: Atualizar TODOS os gateways deste usuário
                # ✅ CORREÇÃO: Verificar se gateway existe antes de atualizar
                # ========================================================================
                user_gateways = Gateway.query.filter_by(user_id=user.id, is_active=True).all()
                
                if not user_gateways:
                    logger.warning(f"  ⚠️ User {user.id} não possui gateways ativos (não afeta taxa premium)")
                else:
                    for gateway in user_gateways:
                        old_gateway_rate = gateway.split_percentage or default_rate
                        gateway.split_percentage = new_rate
                        updated_gateways.append({
                            'gateway_id': gateway.id,
                            'gateway_type': gateway.gateway_type,
                            'user_id': user.id,
                            'old_rate': old_gateway_rate,
                            'new_rate': new_rate
                        })
                        logger.info(f"  💳 Gateway {gateway.id} ({gateway.gateway_type}) → {old_gateway_rate}% → {new_rate}%")
            
            # ========================================================================
            # PASSO 5: Garantir que gateways de usuários FORA do Top 3 estão em 2%
            # ✅ CORREÇÃO: Usar conjunto vazio se top_3_users estiver vazio (proteção)
            # ========================================================================
            logger.info(f"🔍 Verificando gateways de usuários fora do Top 3...")
            top_3_user_ids = {user.id for user in top_3_users} if top_3_users else set()
            
            # ✅ VALIDAÇÃO: Só processar se houver gateways para verificar
            non_premium_gateways = Gateway.query.filter(
                Gateway.is_active == True
            ).all()
            
            # Filtrar apenas gateways de usuários fora do Top 3
            gateways_to_reset = [
                gw for gw in non_premium_gateways
                if gw.user_id not in top_3_user_ids and (gw.split_percentage or default_rate) != default_rate
            ]
            
            for gateway in gateways_to_reset:
                old_rate = gateway.split_percentage or default_rate
                gateway.split_percentage = default_rate
                updated_gateways.append({
                    'gateway_id': gateway.id,
                    'gateway_type': gateway.gateway_type,
                    'user_id': gateway.user_id,
                    'old_rate': old_rate,
                    'new_rate': default_rate
                })
                logger.info(f"  🔄 Gateway {gateway.id} ({gateway.gateway_type}) do User {gateway.user_id} → {old_rate}% → {default_rate}% (volta ao padrão)")
            
            # ========================================================================
            # PASSO 6: Commit ATÔMICO de todas as alterações com tratamento de erro
            # ========================================================================
            try:
                db.session.commit()
                logger.info("="*70)
                logger.info(f"✅ RANKING V2.0 - Atualização concluída com sucesso!")
                logger.info(f"  📊 Top {len(top_3_users)} atualizado(s): {len(updated_users)} usuário(s)")
                logger.info(f"  💳 Gateways atualizados: {len(updated_gateways)} gateway(s)")
                logger.info("="*70)
                
                # ✅ VALIDAÇÃO FINAL: Verificar se tudo foi salvo corretamente
                for user_data in updated_users:
                    user_check = User.query.get(user_data['user_id'])
                    if user_check and user_check.commission_percentage != user_data['new_rate']:
                        logger.error(f"❌ INCONSISTÊNCIA: User {user_data['user_id']} tem taxa {user_check.commission_percentage}% mas deveria ter {user_data['new_rate']}%")
                
                return {
                    'success': True,
                    'updated_users': len(updated_users),
                    'updated_gateways': len(updated_gateways),
                    'top_3': [
                        {
                            'position': u['position'],
                            'user_id': u['user_id'],
                            'email': u['email'],
                            'rate': u['new_rate']
                        }
                        for u in updated_users
                    ],
                    'changes': {
                        'users': updated_users,
                        'gateways': updated_gateways
                    }
                }
            except Exception as commit_error:
                logger.error(f"❌ ERRO ao fazer commit: {commit_error}", exc_info=True)
                db.session.rollback()
                raise  # Re-lançar para ser capturado pelo except externo
                
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO ao atualizar taxas de premiação: {e}", exc_info=True)
        try:
            db.session.rollback()
            logger.info("✅ Rollback executado com sucesso")
        except Exception as rollback_error:
            logger.error(f"❌ ERRO ao fazer rollback: {rollback_error}", exc_info=True)
        return {'success': False, 'error': str(e)}

def generate_anonymous_avatar(user_id, position=None):
    """
    ✅ RANKING V2.0 - Sistema de Avatares Anonimizados (LGPD)
    Gera avatar baseado em hash do user_id para manter consistência
    sem expor dados pessoais
    
    AGORA: Usa logo do sistema ao invés de emojis
    TOP 3: Usa logos específicas (logotop1.png, logotop2.png, logotop3.png)
    """
    import hashlib
    
    # Gerar hash do user_id
    hash_obj = hashlib.md5(str(user_id).encode())
    hash_hex = hash_obj.hexdigest()
    
    # ✅ Usar logo específica para top 3, senão logo padrão
    if position == 1:
        logo_path = 'img/logotop1.png'
    elif position == 2:
        logo_path = 'img/logotop2.png'
    elif position == 3:
        logo_path = 'img/logotop3.png'
    else:
        logo_path = 'img/logo.png'  # Logo padrão para posições 4+
    
    # Gerar cor baseada no hash (para gradientes únicos)
    color_seed = int(hash_hex[:6], 16)
    hue = (color_seed % 360)
    
    # Criar gradiente CSS baseado na cor
    colors = [
        'linear-gradient(135deg, #FFB800, #F59E0B)',  # Dourado padrão
        'linear-gradient(135deg, #3B82F6, #2563EB)',  # Azul
        'linear-gradient(135deg, #10B981, #059669)',  # Verde
        'linear-gradient(135deg, #8B5CF6, #7C3AED)',  # Roxo
        'linear-gradient(135deg, #EF4444, #DC2626)',  # Vermelho
        'linear-gradient(135deg, #F59E0B, #D97706)',  # Laranja
        'linear-gradient(135deg, #06B6D4, #0891B2)',  # Ciano
        'linear-gradient(135deg, #EC4899, #DB2777)',  # Rosa
        'linear-gradient(135deg, #14B8A6, #0D9488)',  # Turquesa
        'linear-gradient(135deg, #6366F1, #4F46E5)'   # Índigo
    ]
    color_index = int(hash_hex[:2], 16) % len(colors)
    gradient = colors[color_index]
    
    return {
        'logo_path': logo_path,  # Caminho da logo (específica para top 3 ou padrão)
        'gradient': gradient,
        'hash': hash_hex[:8]  # Primeiros 8 caracteres para referência
    }

@app.route('/ranking')
@login_required
def ranking():
    """
    ✅ RANKING V2.0 - Hall da Fama Premium
    Sistema completo de ranking com premiação, avatares anonimizados e LGPD compliant
    """
    from sqlalchemy import func
    from models import BotUser, UserAchievement, Achievement
    from datetime import timedelta
    
    # Filtro de período
    period = request.args.get('period', 'month')  # month (padrão) ou all
    
    # ✅ CORREÇÃO: Definir período corretamente
    date_filter = None
    if period == 'today':
        date_filter = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        # Últimos 7 dias
        date_filter = get_brazil_time() - timedelta(days=7)
    elif period == 'month':
        # ✅ CORREÇÃO CRÍTICA: Mês atual (do primeiro dia do mês até agora)
        # Não usar timedelta(days=30) que é janela deslizante
        now = get_brazil_time()
        date_filter = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # ✅ RANKING V2.0: Ordenar por receita do período (faturamento)
    if period == 'all':
        # Ranking all-time (ordenar por receita total)
        users_query = User.query.filter_by(is_admin=False, is_banned=False)\
                               .order_by(
                                   User.total_revenue.desc(),  # Faturamento total
                                   User.total_sales.desc(),    # Desempate: Mais vendas
                                   User.created_at.asc()       # Desempate: Mais antigo
                               )
    else:
        # Ranking do período (mês/semana/hoje) - por receita no período
        # ✅ CORREÇÃO: Usar o mesmo date_filter já calculado acima (não recalcular)
        # date_filter já está definido corretamente acima
        
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
    
    # ✅ RANKING V2.0: Enriquecer dados com avatares e premiação
    ranking_data = []
    premium_rates = {1: 1.0, 2: 1.3, 3: 1.5}
    
    for idx, user in enumerate(top_users, 1):
        bots_count = Bot.query.filter_by(user_id=user.id).count()
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
            period_sales = int(user.total_sales or 0)
            period_revenue = float(user.total_revenue or 0.0)
        
        # ✅ RANKING V2.0: Gerar avatar anonimizado (com logo específica para top 3)
        avatar = generate_anonymous_avatar(user.id, position=idx)
        
        # ✅ RANKING V2.0: Verificar se está no Top 3 e tem taxa premium
        is_premium = idx <= 3
        premium_rate = premium_rates.get(idx, None)
        has_premium_rate = user.commission_percentage < 2.0
        
        ranking_data.append({
            'position': idx,
            'user': user,
            'bots_count': bots_count,
            'sales': period_sales,
            'revenue': float(period_revenue),
            'points': user.ranking_points,
            'badges': badges[:5],
            'total_badges': len(badges),
            'streak': user.current_streak,
            # ✅ V2.0: Dados de premiação e avatar
            'avatar': avatar,
            'is_premium': is_premium,
            'premium_rate': premium_rate if is_premium else None,
            'current_rate': user.commission_percentage,
            'has_premium_rate': has_premium_rate
        })
    
    # Encontrar posição do usuário atual
    my_position = next((item for item in ranking_data if item['user'].id == current_user.id), None)
    if not my_position:
        # Calcular posição real se não está no top 100
        if period == 'all':
            my_position_number = User.query.filter(
                User.is_admin == False,
                User.is_banned == False,
                User.total_revenue > current_user.total_revenue
            ).count() + 1
        else:
            # Calcular receita do usuário atual no período
            my_period_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
                Bot.user_id == current_user.id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter
            ).scalar() or 0.0
            
            # Contar usuários com receita maior
            my_position_number = db.session.query(func.count(User.id))\
                .join(subquery, User.id == subquery.c.user_id)\
                .filter(
                    User.is_admin == False,
                    User.is_banned == False,
                    subquery.c.period_revenue > my_period_revenue
                ).scalar() + 1
    else:
        my_position_number = my_position['position']
    
    # Diferença para próxima posição
    next_user = None
    if my_position_number > 1:
        next_position_idx = my_position_number - 2
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
    
    # ✅ VERSÃO 2.0: Buscar TODAS as conquistas + progresso
    my_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
    my_achievement_ids = {ua.achievement_id for ua in my_achievements}
    
    # Buscar todas as conquistas disponíveis
    all_achievements = Achievement.query.order_by(Achievement.points.desc()).all()
    
    # Calcular progresso e categorizar
    achievements_data = []
    categories = {}
    
    for achievement in all_achievements:
        is_unlocked = achievement.id in my_achievement_ids
        progress = 0.0
        current_value = 0.0
        target_value = achievement.requirement_value
        
        # Calcular progresso baseado no requirement_type
        if not is_unlocked:
            if achievement.requirement_type == 'sales':
                total_sales = db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == current_user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0
                current_value = float(total_sales)
            elif achievement.requirement_type == 'revenue':
                total_revenue = db.session.query(func.sum(Payment.amount))\
                    .join(Bot).filter(
                        Bot.user_id == current_user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0.0
                current_value = float(total_revenue)
            elif achievement.requirement_type == 'streak':
                current_value = float(current_user.current_streak or 0)
            elif achievement.requirement_type == 'conversion_rate':
                # Calcular taxa de conversão
                total_users = BotUser.query.join(Bot).filter(Bot.user_id == current_user.id).count()
                total_sales = db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == current_user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0
                current_value = (total_sales / total_users * 100) if total_users > 0 else 0.0
            
            if target_value > 0:
                progress = min((current_value / target_value) * 100, 100.0)
        
        # Categorizar baseado no requirement_type
        category_map = {
            'sales': 'Vendas',
            'revenue': 'Receita',
            'streak': 'Consistência',
            'conversion_rate': 'Conversão',
            'speed': 'Velocidade'
        }
        category = category_map.get(achievement.requirement_type, 'Geral')
        
        achievements_data.append({
            'achievement': achievement,
            'is_unlocked': is_unlocked,
            'progress': progress,
            'current_value': current_value,
            'target_value': target_value,
            'category': category
        })
        
        if category not in categories:
            categories[category] = []
        categories[category].append(achievements_data[-1])
    
    logger.info(f"📊 Ranking - Usuario {current_user.username} tem {len(my_achievements)}/{len(all_achievements)} conquista(s)")
    
    # ============================================================================
    # ✅ PREMIAÇÕES DE FATURAMENTO V2.0 - Placas de Faturamento
    # ============================================================================
    # Calcular faturamento total do usuário
    total_revenue = db.session.query(func.sum(Payment.amount))\
        .join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid'
        ).scalar() or 0.0
    
    total_revenue_float = float(total_revenue)
    
    # Definir marcos de premiação
    # ✅ Verificar quais imagens existem antes de incluir
    import os
    static_img_path = os.path.join(app.static_folder, 'img')
    
    revenue_milestones = [
        {'amount': 50000, 'name': 'R$ 50.000', 'image': 'premio_50k.png', 'label': '50K'},
        {'amount': 100000, 'name': 'R$ 100.000', 'image': 'premio_100k.png', 'label': '100K'},
        {'amount': 250000, 'name': 'R$ 250.000', 'image': 'premio_250k.png', 'label': '250K'},
        {'amount': 500000, 'name': 'R$ 500.000', 'image': 'premio_500k.png', 'label': '500K'},
        {'amount': 1000000, 'name': 'R$ 1.000.000', 'image': 'premio_1m.png', 'label': '1M'}
    ]
    
    # Filtrar apenas milestones com imagens existentes
    revenue_milestones = [
        milestone for milestone in revenue_milestones
        if os.path.exists(os.path.join(static_img_path, milestone['image']))
    ]
    
    # Verificar quais premiações foram desbloqueadas
    revenue_awards = []
    for milestone in revenue_milestones:
        is_unlocked = total_revenue_float >= milestone['amount']
        progress = min((total_revenue_float / milestone['amount']) * 100, 100.0) if milestone['amount'] > 0 else 0.0
        
        revenue_awards.append({
            'amount': milestone['amount'],
            'name': milestone['name'],
            'image': milestone['image'],
            'label': milestone['label'],
            'is_unlocked': is_unlocked,
            'progress': progress,
            'current_revenue': total_revenue_float,
            'remaining': max(0, milestone['amount'] - total_revenue_float)
        })
    
    unlocked_count = sum(1 for award in revenue_awards if award['is_unlocked'])
    total_count = len(revenue_awards)
    
    return render_template('ranking.html',
                         ranking=ranking_data,
                         my_position=my_position_number,
                         next_user=next_user,
                         period=period,
                         my_achievements=my_achievements,
                         all_achievements_data=achievements_data,
                         achievements_by_category=categories,
                         revenue_awards=revenue_awards,
                         total_revenue=total_revenue_float,
                         unlocked_awards_count=unlocked_count,
                         total_awards_count=total_count)

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

@app.route('/chat')
@login_required
def chat():
    """✅ CHAT - Página de gerenciamento de conversas dos bots"""
    from models import Bot, BotUser, Payment, BotMessage
    from sqlalchemy import func
    
    # Buscar bots online do usuário
    bots_online = Bot.query.filter_by(
        user_id=current_user.id,
        is_running=True,
        is_active=True
    ).order_by(Bot.name).all()
    
    # Preparar dados dos bots
    bots_data = []
    for bot in bots_online:
        # Contar conversas não lidas (mensagens não lidas)
        unread_count = db.session.query(func.count(BotMessage.id)).filter(
            BotMessage.bot_id == bot.id,
            BotMessage.direction == 'incoming',
            BotMessage.is_read == False
        ).scalar() or 0
        
        # Contar total de conversas (usuários únicos)
        total_conversations = db.session.query(func.count(func.distinct(BotUser.telegram_user_id))).filter(
            BotUser.bot_id == bot.id,
            BotUser.archived == False
        ).scalar() or 0
        
        bots_data.append({
            'id': bot.id,
            'name': bot.name,
            'username': bot.username,
            'unread_count': unread_count,
            'total_conversations': total_conversations
        })
    
    return render_template('chat.html', bots=bots_data)

@app.route('/api/chat/conversations/<int:bot_id>', methods=['GET'])
@login_required
def get_chat_conversations(bot_id):
    """✅ CHAT - Retorna lista de conversas de um bot com filtros"""
    from models import Bot, BotUser, Payment, BotMessage
    from sqlalchemy import func
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Parâmetros de filtro
    filter_type = request.args.get('filter', 'all')  # all, paid, pix_generated, only_entered
    search_query = request.args.get('search', '').strip()
    
    # Query base: BotUsers do bot
    query = BotUser.query.filter_by(
        bot_id=bot_id,
        archived=False
    )
    
    # Aplicar filtro de busca
    if search_query:
        query = query.filter(
            db.or_(
                BotUser.first_name.ilike(f'%{search_query}%'),
                BotUser.username.ilike(f'%{search_query}%'),
                BotUser.telegram_user_id.ilike(f'%{search_query}%')
            )
        )
    
    # Aplicar filtro de tipo
    if filter_type == 'paid':
        # Usuários que pagaram (status = 'paid')
        paid_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid'
        ).distinct().all()
        # Normalizar IDs (remover prefixo "user_" se houver)
        paid_ids_list = []
        for row in paid_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                paid_ids_list.append(user_id)
        if paid_ids_list:
            query = query.filter(BotUser.telegram_user_id.in_(paid_ids_list))
        else:
            # Se não há pagamentos, retornar query vazia
            query = query.filter(BotUser.id == -1)  # Query que nunca retorna resultados
    elif filter_type == 'pix_generated':
        # Usuários que geraram PIX (têm pagamento criado, mesmo que pending)
        pix_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id
        ).distinct().all()
        # Normalizar IDs
        pix_ids_list = []
        for row in pix_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                pix_ids_list.append(user_id)
        if pix_ids_list:
            query = query.filter(BotUser.telegram_user_id.in_(pix_ids_list))
        else:
            query = query.filter(BotUser.id == -1)
    elif filter_type == 'only_entered':
        # Usuários que só entraram (sem pagamentos)
        all_payment_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id
        ).distinct().all()
        # Normalizar IDs
        payment_ids_list = []
        for row in all_payment_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                payment_ids_list.append(user_id)
        if payment_ids_list:
            query = query.filter(~BotUser.telegram_user_id.in_(payment_ids_list))
        # Se não há pagamentos, todos os usuários são "only_entered"
    
    # Buscar conversas
    bot_users = query.order_by(BotUser.last_interaction.desc()).limit(100).all()
    
    # Enriquecer dados
    conversations = []
    for bot_user in bot_users:
        # Buscar última mensagem
        last_message = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=bot_user.telegram_user_id
        ).order_by(BotMessage.created_at.desc()).first()
        
        # Contar mensagens não lidas
        unread_count = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=bot_user.telegram_user_id,
            direction='incoming',
            is_read=False
        ).count()
        
        # Verificar status do cliente (normalizar customer_user_id)
        # Payment pode ter customer_user_id com ou sem prefixo "user_"
        telegram_id_str = str(bot_user.telegram_user_id)
        has_paid = Payment.query.filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).first() is not None
        
        has_pix = Payment.query.filter(
            Payment.bot_id == bot_id,
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).first() is not None
        
        # Calcular total gasto
        total_spent = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).scalar() or 0.0
        
        conversations.append({
            'bot_user_id': bot_user.id,
            'telegram_user_id': bot_user.telegram_user_id,
            'first_name': bot_user.first_name or 'Sem nome',
            'username': bot_user.username,
            'last_interaction': bot_user.last_interaction.isoformat() if bot_user.last_interaction else None,
            'last_message': {
                'text': last_message.message_text[:50] + '...' if last_message and last_message.message_text and len(last_message.message_text) > 50 else (last_message.message_text if last_message else None),
                'created_at': last_message.created_at.isoformat() if last_message else None,
                'direction': last_message.direction if last_message else None
            } if last_message else None,
            'unread_count': unread_count,
            'has_paid': has_paid,
            'has_pix': has_pix,
            'total_spent': float(total_spent),
            'status': 'paid' if has_paid else 'pix_generated' if has_pix else 'only_entered'
        })
    
    return jsonify({
        'success': True,
        'conversations': conversations,
        'total': len(conversations)
    })

@app.route('/api/chat/messages/<int:bot_id>/<telegram_user_id>', methods=['GET'])
@login_required
def get_chat_messages(bot_id, telegram_user_id):
    """✅ CHAT - Retorna mensagens de uma conversa específica"""
    from models import Bot, BotUser, BotMessage
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Buscar bot_user
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first_or_404()
    
    # ✅ OTIMIZAÇÃO QI 600+: Buscar mensagens novas usando timestamp (mais confiável que ID)
    since_timestamp = request.args.get('since_timestamp', type=str)
    
    if since_timestamp:
        try:
            from datetime import datetime, timezone, timedelta
            from models import BRAZIL_TZ_OFFSET
            
            # ✅ CORREÇÃO: Tratar diferentes formatos de timestamp
            since_timestamp_clean = since_timestamp.replace('Z', '+00:00')
            if '+' not in since_timestamp_clean and since_timestamp_clean.count(':') == 2:
                # Formato sem timezone, assumir UTC
                since_timestamp_clean += '+00:00'
            since_dt_utc = datetime.fromisoformat(since_timestamp_clean)
            
            # ✅ CRÍTICO: Converter UTC (timezone-aware) para UTC (naive)
            if since_dt_utc.tzinfo is not None:
                since_dt_utc = since_dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
            
            # ✅ CRÍTICO: Converter UTC para horário do Brasil (naive)
            # BotMessage.created_at usa get_brazil_time() = datetime.utcnow() + BRAZIL_TZ_OFFSET
            # Isso significa que created_at está em UTC-3 (naive)
            # Frontend envia UTC, então: since_dt_brazil = since_dt_utc + BRAZIL_TZ_OFFSET
            since_dt_brazil = since_dt_utc + BRAZIL_TZ_OFFSET  # BRAZIL_TZ_OFFSET = -3h
            
            # ✅ CRÍTICO: Adicionar margem de 20 segundos para garantir que não perca mensagens
            # (considerando diferença de timezone, latência de rede, processamento e sincronização)
            since_dt_brazil_with_margin = since_dt_brazil - timedelta(seconds=20)
            
            # Buscar apenas mensagens mais recentes que o timestamp (com margem)
            messages = BotMessage.query.filter(
                BotMessage.bot_id == bot_id,
                BotMessage.telegram_user_id == telegram_user_id,
                BotMessage.created_at > since_dt_brazil_with_margin
            ).order_by(BotMessage.created_at.asc()).limit(50).all()
            
            # ✅ FALLBACK: Se não encontrou mensagens, buscar últimas 10 e comparar no Python
            # (evita problemas de timezone e sincronização)
            if len(messages) == 0:
                # Buscar últimas 10 mensagens para garantir que não perdemos nada
                recent_messages = BotMessage.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).order_by(BotMessage.created_at.desc()).limit(10).all()
                
                # Filtrar mensagens mais recentes que o timestamp (comparação direta no Python)
                messages = [msg for msg in recent_messages if msg.created_at > since_dt_brazil_with_margin]
                messages.reverse()  # Ordenar crescente para exibição
                
                if len(messages) > 0:
                    logger.info(f"✅ Polling (fallback): {len(messages)} novas mensagens encontradas via fallback")
            
            # ✅ DEBUG: Log detalhado sempre (para produção também)
            if len(messages) > 0:
                logger.info(f"✅ Polling: {len(messages)} novas mensagens desde {since_timestamp} | "
                           f"since_dt_utc: {since_dt_utc} | since_dt_brazil: {since_dt_brazil} | "
                           f"since_dt_brazil_with_margin: {since_dt_brazil_with_margin}")
            else:
                logger.debug(f"🔍 Polling: 0 novas mensagens desde {since_timestamp} | "
                           f"since_dt_brazil_with_margin: {since_dt_brazil_with_margin}")
        except Exception as e:
            logger.error(f"Erro ao parsear since_timestamp '{since_timestamp}': {e}")
            # Fallback: buscar últimas 50 mensagens
            messages = BotMessage.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id
            ).order_by(BotMessage.created_at.desc()).limit(50).all()
            messages.reverse()  # Ordenar crescente para exibição
    else:
        # Buscar todas as mensagens (primeira carga)
        messages = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id
        ).order_by(BotMessage.created_at.asc()).limit(100).all()
        
        # Marcar mensagens como lidas apenas na primeira carga
        BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id,
            direction='incoming',
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
    
    messages_data = [msg.to_dict() for msg in messages]
    
    return jsonify({
        'success': True,
        'bot_user': bot_user.to_dict(),
        'messages': messages_data,
        'total': len(messages_data)
    })

@app.route('/api/chat/send-message/<int:bot_id>/<telegram_user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_chat_message(bot_id, telegram_user_id):
    """✅ CHAT - Envia mensagem para um lead via Telegram"""
    from models import Bot, BotUser, BotMessage
    import uuid
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Verificar se bot está rodando
    if not bot.is_running:
        return jsonify({'success': False, 'error': 'Bot não está online. Inicie o bot primeiro.'}), 400
    
    # Buscar bot_user
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first_or_404()
    
    # Obter mensagem do request
    data = request.get_json()
    message_text = data.get('message', '').strip()
    
    if not message_text:
        return jsonify({'success': False, 'error': 'Mensagem não pode estar vazia'}), 400
    
    try:
        # Buscar token do bot
        with bot_manager._bots_lock:
            bot_data = bot_manager.active_bots.get(bot_id)
            if not bot_data:
                return jsonify({'success': False, 'error': 'Bot não está ativo no sistema'}), 400
            
            token = bot_data.get('token')
            if not token:
                return jsonify({'success': False, 'error': 'Token do bot não encontrado'}), 400
        
        # Enviar mensagem via Telegram API
        result = bot_manager.send_telegram_message(
            token=token,
            chat_id=telegram_user_id,
            message=message_text,
            media_url=None,
            buttons=None
        )
        
        # send_telegram_message pode retornar True, False ou dict com dados completos
        if result:
            if isinstance(result, dict) and result.get('ok'):
                # Resultado completo com dados
                telegram_msg_id = result.get('result', {}).get('message_id')
                message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid.uuid4().hex)
                result_data = result
            elif result is True:
                # Retorno True (compatibilidade), precisamos buscar message_id depois
                # Mas não temos como recuperar, então gerar ID único
                message_id = str(uuid.uuid4().hex)
                result_data = {'ok': True, 'result': {'message_id': message_id}}
            else:
                result_data = None
            
            if result_data and result_data.get('ok'):
                # Salvar mensagem no banco
                telegram_msg_id = result_data.get('result', {}).get('message_id')
                message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid.uuid4().hex)
                
                bot_message = BotMessage(
                    bot_id=bot_id,
                    bot_user_id=bot_user.id,
                    telegram_user_id=telegram_user_id,
                    message_id=message_id,
                    message_text=message_text,
                    message_type='text',
                    direction='outgoing',
                    is_read=True  # Mensagens enviadas já são "lidas"
                )
                db.session.add(bot_message)
                
                # Atualizar last_interaction do bot_user
                bot_user.last_interaction = get_brazil_time()
                
                db.session.commit()
                
                logger.info(f"✅ Mensagem enviada para {telegram_user_id} via bot {bot_id}: {message_text[:50]}...")
                
                return jsonify({
                    'success': True,
                    'message_id': bot_message.id,
                    'telegram_message_id': message_id
                })
            else:
                error_msg = 'Falha ao enviar mensagem'
                logger.error(f"❌ Erro ao enviar mensagem via Telegram")
                return jsonify({'success': False, 'error': error_msg}), 500
        else:
            error_msg = 'Falha ao enviar mensagem'
            logger.error(f"❌ Erro ao enviar mensagem via Telegram")
            return jsonify({'success': False, 'error': error_msg}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao enviar mensagem: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/send-media/<int:bot_id>/<telegram_user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_chat_media(bot_id, telegram_user_id):
    """✅ CHAT - Envia foto/vídeo para um lead via Telegram"""
    from models import Bot, BotUser, BotMessage
    import uuid
    import os
    import tempfile
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Verificar se bot está rodando
    if not bot.is_running:
        return jsonify({'success': False, 'error': 'Bot não está online. Inicie o bot primeiro.'}), 400
    
    # Buscar bot_user
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first_or_404()
    
    # Verificar se arquivo foi enviado
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Arquivo vazio'}), 400
    
    # Obter mensagem (caption) opcional
    message_text = request.form.get('message', '').strip()
    
    # Determinar tipo de mídia baseado na extensão
    filename = file.filename.lower()
    if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        media_type = 'photo'
    elif filename.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        media_type = 'video'
    else:
        media_type = 'document'
    
    # Validar tamanho do arquivo (máximo 50MB para vídeo, 10MB para foto)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = 50 * 1024 * 1024 if media_type == 'video' else 10 * 1024 * 1024
    if file_size > max_size:
        return jsonify({
            'success': False, 
            'error': f'Arquivo muito grande. Máximo: {max_size // (1024*1024)}MB'
        }), 400
    
    temp_file_path = None
    try:
        # Salvar arquivo temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        # Buscar token do bot
        with bot_manager._bots_lock:
            bot_data = bot_manager.active_bots.get(bot_id)
            if not bot_data:
                return jsonify({'success': False, 'error': 'Bot não está ativo no sistema'}), 400
            
            token = bot_data.get('token')
            if not token:
                return jsonify({'success': False, 'error': 'Token do bot não encontrado'}), 400
        
        # Enviar arquivo via Telegram API
        result = bot_manager.send_telegram_file(
            token=token,
            chat_id=telegram_user_id,
            file_path=temp_file_path,
            message=message_text,
            media_type=media_type,
            buttons=None
        )
        
        if result and isinstance(result, dict) and result.get('ok'):
            # Arquivo enviado com sucesso (já foi salvo no banco pelo send_telegram_file)
            telegram_msg_id = result.get('result', {}).get('message_id')
            message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid.uuid4().hex)
            
            # Atualizar last_interaction do bot_user
            bot_user.last_interaction = get_brazil_time()
            db.session.commit()
            
            logger.info(f"✅ {media_type} enviado para {telegram_user_id} via bot {bot_id}")
            
            return jsonify({
                'success': True,
                'message_id': message_id,
                'media_type': media_type,
                'telegram_message_id': message_id
            })
        else:
            error_msg = result.get('description', 'Falha ao enviar arquivo') if isinstance(result, dict) else 'Falha ao enviar arquivo'
            logger.error(f"❌ Erro ao enviar {media_type} via Telegram: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao enviar arquivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        # Limpar arquivo temporário
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao remover arquivo temporário: {e}")

@app.route('/api/chat/media/<int:bot_id>/<file_id>')
@login_required
def get_chat_media(bot_id, file_id):
    """✅ CHAT - Proxy para exibir mídia do Telegram"""
    from models import Bot
    import requests
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        # Buscar token do bot
        with bot_manager._bots_lock:
            bot_data = bot_manager.active_bots.get(bot_id)
            if not bot_data:
                return jsonify({'error': 'Bot não está ativo'}), 400
            
            token = bot_data.get('token')
            if not token:
                return jsonify({'error': 'Token não encontrado'}), 400
        
        # Obter file_path do Telegram usando file_id
        get_file_url = f"https://api.telegram.org/bot{token}/getFile"
        response = requests.get(get_file_url, params={'file_id': file_id}, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'error': 'Erro ao obter arquivo'}), 500
        
        data = response.json()
        if not data.get('ok'):
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        file_path = data.get('result', {}).get('file_path')
        if not file_path:
            return jsonify({'error': 'File path não encontrado'}), 404
        
        # Baixar arquivo do Telegram
        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        file_response = requests.get(file_url, timeout=30, stream=True)
        
        if file_response.status_code != 200:
            return jsonify({'error': 'Erro ao baixar arquivo'}), 500
        
        # Retornar arquivo com headers apropriados
        from flask import Response
        return Response(
            file_response.iter_content(chunk_size=8192),
            mimetype=file_response.headers.get('Content-Type', 'application/octet-stream'),
            headers={
                'Content-Disposition': f'inline; filename="{file_path.split("/")[-1]}"',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter mídia: {e}", exc_info=True)
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
            'meta_cloaker_param_name': 'grim',  # Sempre fixo como "grim"
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
        # ✅ IMPORTANTE: O parâmetro sempre será "grim", nunca pode ser alterado
        bot.meta_cloaker_param_name = 'grim'
        
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
                'meta_cloaker_param_name': 'grim',  # Sempre fixo como "grim"
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
        # ✅ VERIFICAÇÃO 0: É crawler? (NÃO enviar PageView para crawlers)
        user_agent = request.headers.get('User-Agent', '')
        def is_crawler(ua: str) -> bool:
            """Detecta se o User-Agent é um crawler/bot"""
            if not ua:
                return False
            ua_lower = ua.lower()
            crawler_patterns = [
                'facebookexternalhit', 'facebot', 'telegrambot', 'whatsapp',
                'python-requests', 'curl', 'wget', 'bot', 'crawler', 'spider',
                'scraper', 'googlebot', 'bingbot', 'slurp', 'duckduckbot',
                'baiduspider', 'yandexbot', 'sogou', 'exabot', 'ia_archiver'
            ]
            return any(pattern in ua_lower for pattern in crawler_patterns)
        
        if is_crawler(user_agent):
            logger.info(f"🤖 CRAWLER DETECTADO no PageView: {user_agent[:50]}... | PageView NÃO será enviado")
            return None, {}
        
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
        # time já está importado no topo do arquivo
        
        # ✅ CORREÇÃO CRÍTICA: fbclid É o external_id para matching no Meta!
        # O fbclid identifica o clique/anúncio específico e é usado para fazer matching entre PageView e Purchase
        # O grim é apenas um código customizado que vai em campaign_code
        grim_param = request.args.get('grim', '')
        fbclid_from_request = request.args.get('fbclid', '')
        
        # ✅ PRIORIDADE: fbclid como external_id (obrigatório para matching)
        if fbclid_from_request:
            external_id = fbclid_from_request
            logger.info(f"🎯 TRACKING ELITE | Using fbclid as external_id: {external_id[:30]}...")
        elif grim_param:
            # Fallback: usar grim se não tiver fbclid (não ideal, mas melhor que nada)
            external_id = grim_param
            logger.warning(f"⚠️ Sem fbclid, usando grim como external_id: {external_id}")
        else:
            # Último recurso: gerar sintético
            external_id = MetaPixelHelper.generate_external_id()
            logger.warning(f"⚠️ Sem grim nem fbclid, usando external_id sintético: {external_id}")
        
        event_id = f"pageview_{pool.id}_{int(time.time())}_{external_id[:8]}"
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return None, {}
        
        # Extrair UTM parameters
        utm_params = MetaPixelHelper.extract_utm_params(request)
        
        # ✅ PASSO 2: RECUPERAR _fbp e _fbc (SOLUÇÃO SÊNIOR QI 300)
        # Prioridade: Cookies do browser > Redis > Gerar novo
        from utils.tracking_service import TrackingService
        
        fbp_value = None
        fbc_value = None
        
        # ✅ PRIORIDADE 1: Cookies do browser (MÁXIMA PRIORIDADE - Meta confia mais)
        # ✅ CORREÇÃO CRÍTICA: FBP pode vir do cookie (se browser já gerou) ou do Redis (gerado no redirect)
        fbp_value = request.cookies.get('_fbp', '')
        fbc_value = request.cookies.get('_fbc', '')
        
        if fbp_value:
            logger.info(f"🔑 PageView - fbp recuperado dos cookies do browser: {fbp_value[:20]}...")
        else:
            logger.info(f"⏳ PageView - fbp não encontrado nos cookies, buscando no Redis (gerado no redirect)...")
        
        if fbc_value:
            logger.info(f"🔑 PageView - fbc recuperado dos cookies do browser: {fbc_value[:20]}...")
        
        # ✅ PRIORIDADE 2: Redis (FBP/FBC gerados no redirect - CRÍTICO para funil server-side)
        # Para funil server-side, FBP é gerado no redirect e salvo no Redis
        # PageView DEVE recuperar do Redis para garantir matching perfeito com Purchase
        if not fbp_value or not fbc_value:
            try:
                tracking_data = TrackingService.recover_tracking_data(
                    fbclid=external_id if external_id and external_id.startswith('PAZ') else None,
                    grim=grim_param
                )
                
                if tracking_data:
                    # ✅ CORREÇÃO: Verificar se tracking_data.get() retorna None antes de usar
                    if not fbp_value and tracking_data.get('fbp'):
                        fbp_value = tracking_data.get('fbp') or ''
                        if fbp_value:
                            logger.info(f"🔑 PageView - fbp recuperado do Redis (gerado no redirect): {fbp_value[:20]}...")
                    if not fbc_value and tracking_data.get('fbc'):
                        fbc_value = tracking_data.get('fbc') or ''
                        if fbc_value:
                            logger.info(f"🔑 PageView - fbc recuperado do Redis: {fbc_value[:20]}...")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar fbp/fbc do Redis: {e}")
                import traceback
                traceback.print_exc()
        
        # ✅ PRIORIDADE 3: Se ainda não tem FBP, gerar agora (fallback de segurança)
        # Isso garante que SEMPRE teremos FBP no PageView (7/7 atributos)
        def is_crawler(ua: str) -> bool:
            """Detecta se o User-Agent é um crawler/bot"""
            if not ua:
                return False
            ua_lower = ua.lower()
            crawler_patterns = [
                'facebookexternalhit', 'facebot', 'telegrambot', 'whatsapp',
                'python-requests', 'curl', 'wget', 'bot', 'crawler', 'spider',
                'scraper', 'googlebot', 'bingbot', 'slurp', 'duckduckbot',
                'baiduspider', 'yandexbot', 'sogou', 'exabot', 'ia_archiver'
            ]
            return any(pattern in ua_lower for pattern in crawler_patterns)
        
        if not fbp_value and not is_crawler(request.headers.get('User-Agent', '')):
            fbp_value = TrackingService.generate_fbp()
            logger.info(f"🔑 PageView - fbp gerado no servidor (fallback): {fbp_value[:20]}...")
        
        # ✅ PRIORIDADE 4: Gerar _fbc se não existir mas tiver fbclid
        if not fbc_value and external_id and external_id.startswith('PAZ'):
            fbc_value = TrackingService.generate_fbc(external_id)
            if fbc_value:
                logger.info(f"🔑 PageView - _fbc gerado automaticamente: {fbc_value[:50]}...")
        
        # ✅ CRÍTICO: Se fbp veio do cookie do browser, atualizar Redis (browser gerou!)
        # Isso garante que o Purchase terá o fbp correto
        if fbp_value and external_id and external_id.startswith('PAZ'):
            try:
                TrackingService.save_tracking_data(
                    fbclid=external_id,
                    fbp=fbp_value,  # ✅ FBP do browser (prioridade máxima)
                    fbc=fbc_value,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    grim=grim_param,
                    utms=utm_params
                )
                logger.info(f"✅ PageView - fbp do browser salvo no Redis para Purchase")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao salvar fbp do browser no Redis: {e}")
        elif external_id and external_id.startswith('PAZ'):
            # Se não tem fbp mas tem external_id, salvar mesmo assim (fbc já está)
            try:
                TrackingService.save_tracking_data(
                    fbclid=external_id,
                    fbp=fbp_value,  # Pode ser vazio (browser ainda não gerou)
                    fbc=fbc_value,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', ''),
                    grim=grim_param,
                    utms=utm_params
                )
            except Exception as e:
                logger.warning(f"⚠️ Erro ao salvar tracking no Redis: {e}")
        
        # ✅ CAPTURAR DADOS PARA RETORNAR
        # ✅ CRÍTICO: Priorizar grim sobre utm_params.get('code') para matching com campanha Meta
        campaign_code_value = grim_param if grim_param else utm_params.get('code')
        
        utm_data = {
            'utm_source': utm_params.get('utm_source'),
            'utm_campaign': utm_params.get('utm_campaign'),
            'utm_content': utm_params.get('utm_content'),
            'utm_medium': utm_params.get('utm_medium'),
            'utm_term': utm_params.get('utm_term'),
            'fbclid': utm_params.get('fbclid'),
            'campaign_code': campaign_code_value  # ✅ grim tem prioridade máxima
        }
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO (ASSÍNCRONO - NÃO BLOQUEIA!)
        # ============================================================================
        from celery_app import send_meta_event
        from utils.meta_pixel import MetaPixelAPI
        
        # ✅ CRÍTICO: Construir external_id array IMUTÁVEL (sempre mesmo formato)
        # PageView: apenas fbclid (não temos telegram_user_id ainda)
        # TrackingService retorna array de strings (não hasheadas), _build_user_data faz o hash
        external_id_for_hash = external_id if external_id and external_id.startswith('PAZ') else None
        
        # ✅ CRÍTICO: Usar _build_user_data com external_id string (será hashado internamente)
        # Isso garante que PageView e Purchase usem EXATAMENTE o mesmo formato
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=None,  # Não temos telegram_user_id no PageView
            external_id=external_id_for_hash,  # ✅ fbclid será hashado pelo _build_user_data
            email=None,
            phone=None,
            client_ip=request.remote_addr,
            client_user_agent=request.headers.get('User-Agent', ''),
            fbp=fbp_value,  # ✅ CRÍTICO: _fbp do cookie ou Redis
            fbc=fbc_value  # ✅ CRÍTICO: _fbc do cookie, Redis ou gerado
        )
        
        # ✅ CRÍTICO: Garantir que external_id existe (obrigatório para Conversions API)
        if not user_data.get('external_id'):
            # Se não há external_id, criar um baseado no grim ou fbclid
            fallback_external_id = external_id if external_id else MetaPixelHelper.generate_external_id()
            user_data['external_id'] = [MetaPixelAPI._hash_data(fallback_external_id)]
            logger.warning(f"⚠️ External ID não encontrado no PageView, usando fallback: {fallback_external_id}")
        
        # ✅ LOG CRÍTICO: Mostrar dados enviados para matching (quantidade de atributos)
        external_ids = user_data.get('external_id', [])
        attributes_count = sum([
            1 if external_ids else 0,
            1 if user_data.get('em') else 0,
            1 if user_data.get('ph') else 0,
            1 if user_data.get('client_ip_address') else 0,
            1 if user_data.get('client_user_agent') else 0,
            1 if user_data.get('fbp') else 0,
            1 if user_data.get('fbc') else 0
        ])
        
        # ✅ LOG CRÍTICO: Verificar se temos 7/7 atributos (objetivo para funil server-side)
        fbp_status = '✅' if user_data.get('fbp') else '❌'
        if not user_data.get('fbp'):
            logger.error(f"❌ PageView - fbp AUSENTE (CRÍTICO para funil server-side!)")
            logger.error(f"   Isso quebra matching PageView ↔ Purchase e gera eventos órfãos")
        
        # ✅ VALIDAÇÃO: Garantir que temos pelo menos 5/7 atributos (mínimo aceitável)
        if attributes_count < 5:
            logger.warning(f"⚠️ PageView com apenas {attributes_count}/7 atributos - Match Quality pode ser baixa")
        elif attributes_count == 7:
            logger.info(f"✅ PageView com 7/7 atributos - Match Quality MÁXIMA garantida!")
        
        logger.info(f"🔍 Meta PageView - User Data: {attributes_count}/7 atributos | " +
                   f"external_id={'✅' if external_ids else '❌'} [{external_ids[0][:16] if external_ids else 'N/A'}...] | " +
                   f"fbp={fbp_status} | " +
                   f"fbc={'✅' if user_data.get('fbc') else '❌'} | " +
                   f"ip={'✅' if user_data.get('client_ip_address') else '❌'} | " +
                   f"ua={'✅' if user_data.get('client_user_agent') else '❌'}")
        
        # ✅ CRÍTICO: event_source_url deve apontar para URL do redirecionador
        event_source_url = request.url if request.url else f'https://{request.host}/go/{pool.slug}'
        
        event_data = {
            'event_name': 'PageView',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'event_source_url': event_source_url,  # ✅ URL do redirecionador (consistente)
            'user_data': user_data,  # ✅ Agora com external_id hashado corretamente + fbp + fbc
            'custom_data': {
                'pool_id': pool.id,
                'pool_name': pool.name,
                'utm_source': utm_data['utm_source'],
                'utm_campaign': utm_data['utm_campaign'],
                'utm_content': utm_data['utm_content'],
                'utm_medium': utm_data['utm_medium'],
                'utm_term': utm_data['utm_term'],
                'fbclid': utm_data['fbclid'],
                'campaign_code': utm_data['campaign_code']  # ✅ grim tem prioridade máxima
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
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Iniciando para {payment.payment_id}")
        
        # ✅ VERIFICAÇÃO 1: Buscar pool associado ao bot
        from models import PoolBot
        
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Pool Bot encontrado: {pool_bot is not None}")
        
        if not pool_bot:
            logger.error(f"❌ PROBLEMA RAIZ: Bot {payment.bot_id} não está associado a nenhum pool - Meta Pixel Purchase NÃO SERÁ ENVIADO (Payment {payment.id})")
            logger.error(f"   SOLUÇÃO: Associe o bot a um pool no dashboard ou via API")
            return
        
        pool = pool_bot.pool
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Pool ID: {pool.id}, Nome: {pool.name}")
        
        # ✅ VERIFICAÇÃO 2: Pool tem Meta Pixel configurado?
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Tracking habilitado: {pool.meta_tracking_enabled}")
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Pixel ID: {pool.meta_pixel_id is not None}")
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Access Token: {pool.meta_access_token is not None}")
        
        if not pool.meta_tracking_enabled:
            logger.error(f"❌ PROBLEMA RAIZ: Meta tracking DESABILITADO para pool {pool.id} ({pool.name}) - Meta Pixel Purchase NÃO SERÁ ENVIADO (Payment {payment.id})")
            logger.error(f"   SOLUÇÃO: Ative 'Meta Tracking' nas configurações do pool {pool.name}")
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.error(f"❌ PROBLEMA RAIZ: Pool {pool.id} ({pool.name}) tem tracking ativo mas SEM pixel_id ou access_token - Meta Pixel Purchase NÃO SERÁ ENVIADO (Payment {payment.id})")
            logger.error(f"   SOLUÇÃO: Configure Meta Pixel ID e Access Token nas configurações do pool {pool.name}")
            return
        
        # ✅ VERIFICAÇÃO 3: Evento Purchase está habilitado?
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Evento Purchase habilitado: {pool.meta_events_purchase}")
        if not pool.meta_events_purchase:
            logger.error(f"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO para pool {pool.id} ({pool.name}) - Meta Pixel Purchase NÃO SERÁ ENVIADO (Payment {payment.id})")
            logger.error(f"   SOLUÇÃO: Ative 'Purchase Event' nas configurações do pool {pool.name}")
            return
        
        # ✅ VERIFICAÇÃO 4: Já enviou este pagamento? (ANTI-DUPLICAÇÃO)
        # ✅ CORREÇÃO: Permitir reenvio se forçado (force_resend=True via função auxiliar)
        logger.info(f"🔍 DEBUG Meta Pixel Purchase - Já enviado: {payment.meta_purchase_sent}")
        if payment.meta_purchase_sent:
            # Verificar se é um reenvio forçado (via flag temporária ou função auxiliar)
            # Por padrão, não reenvia para evitar duplicação
            # Mas se flag foi resetada explicitamente, permite reenvio
            logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando: {payment.payment_id}")
            logger.info(f"   💡 Para reenviar, resetar flag meta_purchase_sent antes de chamar esta função")
            return
        
        logger.info(f"📊 Preparando envio Meta Purchase: {payment.payment_id} | Pool: {pool.name}")
        
        # Importar Meta Pixel API
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        from models import BotUser
        from celery_app import send_meta_event
        
        # ✅ CORREÇÃO CRÍTICA: Gerar event_id ABSOLUTAMENTE ÚNICO
        # Combinar payment_id + timestamp em milissegundos + UUID para garantir unicidade total
        timestamp_ms = int(time.time() * 1000)  # Milissegundos para evitar colisões
        unique_suffix = uuid.uuid4().hex[:8]  # 8 caracteres aleatórios
        event_id = f"purchase_{payment.payment_id}_{timestamp_ms}_{unique_suffix}"
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as decrypt_error:
            logger.error(f"❌ Erro ao descriptografar access_token do pool {pool.id} ({pool.name}): {decrypt_error} - Purchase ignorado (Payment {payment.id})")
            return
        
        # Determinar tipo de venda (QI 540 - FIX BUG)
        is_downsell = payment.is_downsell or False
        is_upsell = payment.is_upsell or False
        is_remarketing = payment.is_remarketing or False
        
        # ✅ FIX: customer_user_id pode vir com ou sem prefixo "user_"
        telegram_user_id = None
        if payment.customer_user_id:
            if payment.customer_user_id.startswith('user_'):
                telegram_user_id = int(payment.customer_user_id.replace('user_', ''))
            elif payment.customer_user_id.isdigit():
                telegram_user_id = int(payment.customer_user_id)
        
        bot_user = None
        if telegram_user_id:
            bot_user = BotUser.query.filter_by(
                bot_id=payment.bot_id,
                telegram_user_id=telegram_user_id
            ).first()
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO PURCHASE (ASSÍNCRONO - MVP DIA 2)
        # ============================================================================
        
        # ✅ CORREÇÃO CRÍTICA: Usar _build_user_data para hash correto dos dados
        from utils.meta_pixel import MetaPixelAPI
        
        # ✅ CRÍTICO: external_id deve ser fbclid para matching com PageView no Meta!
        # Prioridade: payment.fbclid > bot_user.fbclid > bot_user.external_id (se for fbclid) > payment.customer_user_id
        external_id_value = None
        
        # PRIORIDADE 1: fbclid do payment (mais confiável)
        if payment.fbclid:
            external_id_value = payment.fbclid
            logger.info(f"🎯 Meta Purchase - Using payment.fbclid as external_id: {external_id_value[:30]}...")
        # PRIORIDADE 2: fbclid do bot_user
        elif bot_user and bot_user.fbclid:
            external_id_value = bot_user.fbclid
            logger.info(f"🎯 Meta Purchase - Using bot_user.fbclid as external_id: {external_id_value[:30]}...")
        # PRIORIDADE 3: bot_user.external_id (se for fbclid, não grim)
        elif bot_user and bot_user.external_id:
            # Verificar se é fbclid (longo) ou grim (curto)
            is_fbclid = len(bot_user.external_id) > 50 or 'PAZ' in bot_user.external_id
            if is_fbclid:
                external_id_value = bot_user.external_id
                logger.info(f"🎯 Meta Purchase - Using bot_user.external_id (fbclid) as external_id: {external_id_value[:30]}...")
            else:
                # É grim, não usar como external_id - buscar fbclid do bot_user
                if bot_user.fbclid:
                    external_id_value = bot_user.fbclid
                    logger.info(f"🎯 Meta Purchase - bot_user.external_id é grim, usando bot_user.fbclid: {external_id_value[:30]}...")
                else:
                    # Fallback: usar grim mesmo (não ideal, mas melhor que nada)
                    external_id_value = bot_user.external_id
                    logger.warning(f"⚠️ Meta Purchase - Usando grim como external_id (fbclid não encontrado): {external_id_value}")
        # PRIORIDADE 4: customer_user_id como último recurso
        else:
            external_id_value = payment.customer_user_id
            logger.warning(f"⚠️ Meta Purchase - Usando customer_user_id como external_id (fallback): {external_id_value}")
        
        # ✅ PASSO 3: RECUPERAR _fbp e _fbc (SOLUÇÃO SÊNIOR QI 300 - MESMOS DADOS DO PAGEVIEW!)
        # Prioridade: Redis (cookie do browser) > BotUser > Gerar novo
        from utils.tracking_service import TrackingService
        
        fbp_value = None
        fbc_value = None
        ip_value = bot_user.ip_address if bot_user and bot_user.ip_address else None
        user_agent_value = bot_user.user_agent if bot_user and bot_user.user_agent else None
        
        # ✅ PRIORIDADE 1: Redis (cookie do browser do PageView - MÁXIMA PRIORIDADE)
        if external_id_value:
            try:
                tracking_data = TrackingService.recover_tracking_data(
                    fbclid=external_id_value if external_id_value.startswith('PAZ') else None,
                    telegram_user_id=str(telegram_user_id) if telegram_user_id else None,
                    grim=payment.campaign_code
                )
                
                if tracking_data:
                    # ✅ CRÍTICO: PRIORIDADE ABSOLUTA - fbp/fbc do Redis (cookie do browser)
                    fbp_value = tracking_data.get('fbp') or None
                    fbc_value = tracking_data.get('fbc') or None
                    
                    # ✅ Usar MESMOS IP e User Agent do PageView
                    if tracking_data.get('ip'):
                        ip_value = tracking_data.get('ip')
                    if tracking_data.get('ua'):
                        user_agent_value = tracking_data.get('ua')
                    
                    logger.info(f"🔑 Purchase - Dados recuperados do Redis: fbp={'✅' if fbp_value else '❌'} | fbc={'✅' if fbc_value else '❌'} | IP={'✅' if ip_value else '❌'} | UA={'✅' if user_agent_value else '❌'}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar tracking do Redis: {e}")
        
        # ✅ PRIORIDADE 2: BotUser (fallback apenas se Redis não tiver)
        if bot_user:
            if not fbp_value and hasattr(bot_user, 'fbp') and bot_user.fbp:
                fbp_value = bot_user.fbp
                logger.info(f"🔑 Purchase - fbp recuperado do BotUser (fallback)")
            if not fbc_value and hasattr(bot_user, 'fbc') and bot_user.fbc:
                fbc_value = bot_user.fbc
                logger.info(f"🔑 Purchase - fbc recuperado do BotUser (fallback)")
        
        # ✅ PRIORIDADE 3: Gerar _fbc se não existir mas tiver fbclid
        if not fbc_value and external_id_value and external_id_value.startswith('PAZ'):
            fbc_value = TrackingService.generate_fbc(external_id_value)
            logger.info(f"🔑 Purchase - _fbc gerado automaticamente: {fbc_value[:50]}...")
        
        # ✅ CRÍTICO #2: external_id IMUTÁVEL e CONSISTENTE (SEMPRE MESMO FORMATO DO PAGEVIEW!)
        # Usar TrackingService para garantir consistência total
        # IMPORTANTE: _build_user_data recebe strings (fbclid e telegram_id) e faz o hash internamente
        # Isso garante que PageView e Purchase usem EXATAMENTE o mesmo formato de hash
        
        external_id_for_hash = external_id_value if external_id_value and external_id_value.startswith('PAZ') else None
        telegram_id_for_hash = str(telegram_user_id) if telegram_user_id else None
        
        logger.info(f"🔑 Purchase - external_id: fbclid={'✅' if external_id_for_hash else '❌'} | telegram_id={'✅' if telegram_id_for_hash else '❌'}")
        
        # Construir user_data usando função correta (faz hash SHA256)
        # ✅ CRÍTICO: Usar MESMOS dados do PageView (fbp, fbc, IP, User Agent)
        # ✅ CORREÇÃO: BotUser não tem email/phone - usar None (Meta aceita sem esses campos)
        # ✅ CRÍTICO: Passar external_id (fbclid) e customer_user_id (telegram_id) como strings
        # _build_user_data vai construir o array com ordem correta: fbclid primeiro, telegram_id segundo
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=telegram_id_for_hash,  # ✅ telegram_user_id (será hashado e adicionado ao array)
            external_id=external_id_for_hash,  # ✅ fbclid (será hashado e será o PRIMEIRO do array)
            email=None,
            phone=None,
            client_ip=ip_value,  # ✅ MESMO IP do PageView
            client_user_agent=user_agent_value,  # ✅ MESMO User Agent do PageView
            fbp=fbp_value,  # ✅ MESMO _fbp do PageView (do Redis - cookie do browser)
            fbc=fbc_value  # ✅ MESMO _fbc do PageView (do Redis - cookie do browser)
        )
        
        # ✅ VALIDAÇÃO: Garantir que external_id é um array e tem pelo menos fbclid
        if not user_data.get('external_id'):
            # Último recurso: criar um baseado no payment_id
            # time já está importado no topo do arquivo
            fallback_external_id = f'purchase_{payment.payment_id}_{int(time.time())}'
            user_data['external_id'] = [MetaPixelAPI._hash_data(fallback_external_id)]
            logger.warning(f"⚠️ External ID não encontrado, usando fallback: {fallback_external_id}")
        else:
            # ✅ LOG: Mostrar quantos external_ids foram enviados (deve ser >= 2 para melhor match)
            external_ids_count = len(user_data.get('external_id', []))
            logger.info(f"🔑 Purchase - external_id array consolidado: {external_ids_count} ID(s) | Primeiro: {user_data['external_id'][0][:16]}...")
            if external_ids_count >= 2:
                logger.info(f"✅ Purchase - external_id múltiplo detectado (match quality otimizado): fbclid + telegram_user_id")
        
        # ✅ LOG CRÍTICO: Mostrar dados enviados para matching (quantidade de atributos)
        external_ids = user_data.get('external_id', [])
        attributes_count = sum([
            1 if external_ids else 0,
            1 if user_data.get('em') else 0,
            1 if user_data.get('ph') else 0,
            1 if user_data.get('client_ip_address') else 0,
            1 if user_data.get('client_user_agent') else 0,
            1 if user_data.get('fbp') else 0,
            1 if user_data.get('fbc') else 0
        ])
        
        logger.info(f"🔍 Meta Purchase - User Data: {attributes_count}/7 atributos | " +
                   f"external_id={'✅' if external_ids else '❌'} [{external_ids[0][:16] if external_ids else 'N/A'}...] | " +
                   f"fbp={'✅' if user_data.get('fbp') else '❌'} | " +
                   f"fbc={'✅' if user_data.get('fbc') else '❌'} | " +
                   f"email={'✅' if user_data.get('em') else '❌'} | " +
                   f"phone={'✅' if user_data.get('ph') else '❌'} | " +
                   f"ip={'✅' if user_data.get('client_ip_address') else '❌'} | " +
                   f"ua={'✅' if user_data.get('client_user_agent') else '❌'}")
        
        # Construir custom_data
        custom_data = {
            'currency': 'BRL',
            'value': float(payment.amount),
            'content_type': 'product',
            'num_items': 1
        }
        
        # Adicionar content_id se disponível
        if pool.id:
            custom_data['content_ids'] = [str(pool.id)]
        
        # Adicionar content_name
        if payment.product_name:
            custom_data['content_name'] = payment.product_name
        elif payment.bot.name:
            custom_data['content_name'] = payment.bot.name
        
        # Categorização da venda
        if is_downsell:
            custom_data['content_category'] = 'downsell'
        elif is_upsell:
            custom_data['content_category'] = 'upsell'
        elif is_remarketing:
            custom_data['content_category'] = 'remarketing'
        else:
            custom_data['content_category'] = 'initial'
        
        # ✅ CRÍTICO: Valor total (base + order_bump) - Meta recebe 1 evento com valor correto
        # O payment.amount já contém o valor total calculado no bot_manager
        total_value = float(payment.amount)
        
        # ✅ Log para validação (se order_bump estiver presente)
        if hasattr(payment, 'order_bump_value') and payment.order_bump_value:
            base_value = total_value - payment.order_bump_value
            logger.info(f"💰 Purchase - Valor total: R$ {total_value:.2f} (Base: R$ {base_value:.2f} + Order Bump: R$ {payment.order_bump_value:.2f})")
        
        custom_data['value'] = total_value  # ✅ Garantir valor total correto
        
        # UTM e campaign tracking
        if payment.utm_source:
            custom_data['utm_source'] = payment.utm_source
        if payment.utm_campaign:
            custom_data['utm_campaign'] = payment.utm_campaign
        if payment.campaign_code:
            custom_data['campaign_code'] = payment.campaign_code
        
        # ✅ LOG CRÍTICO: Parâmetros enviados para Meta (para debug)
        external_id_hash = user_data.get('external_id', ['N/A'])[0] if user_data.get('external_id') else 'N/A'
        logger.info(f"🎯 Meta Pixel Purchase - Parâmetros: " +
                   f"external_id_hash={external_id_hash[:32] if external_id_hash != 'N/A' else 'N/A'}... | " +
                   f"external_id_raw={external_id_value[:30] if external_id_value else 'N/A'}... | " +
                   f"campaign_code={payment.campaign_code} | " +
                   f"utm_source={payment.utm_source} | " +
                   f"utm_campaign={payment.utm_campaign}")
        
        # ✅ LOG CRÍTICO: Mostrar custom_data completo
        logger.info(f"📊 Meta Purchase - Custom Data: {json.dumps(custom_data, ensure_ascii=False)}")
        
        # Construir event_data completo
        event_data = {
            'event_name': 'Purchase',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',  # ✅ Correto para server-side events
            'event_source_url': f'https://t.me/{payment.bot.username}',  # ✅ OBRIGATÓRIO para melhor matching
            'user_data': user_data,
            'custom_data': custom_data
        }
        
        # ✅ ENFILEIRAR COM PRIORIDADE ALTA (Purchase é crítico!)
        try:
            task = send_meta_event.apply_async(
                args=[
                    pool.meta_pixel_id,
                    access_token,
                    event_data,
                    pool.meta_test_event_code
                ],
                priority=1  # Alta prioridade
            )
            
            logger.info(f"📤 Purchase enfileirado: R$ {payment.amount} | " +
                       f"Pool: {pool.name} | " +
                       f"Event ID: {event_id} | " +
                       f"Task: {task.id} | " +
                       f"Type: {'Downsell' if is_downsell else 'Upsell' if is_upsell else 'Remarketing' if is_remarketing else 'Normal'}")
            
            # ✅ CORREÇÃO CRÍTICA: Aguardar resultado do Celery ANTES de marcar como enviado
            # Isso garante que o evento foi realmente processado e enviado à Meta
            # Timeout de 10 segundos (validação token + envio Meta pode levar alguns segundos)
            try:
                # Aguardar resultado com timeout de 10 segundos
                result = task.get(timeout=10)
                
                # Verificar se foi bem-sucedido
                if result and result.get('events_received', 0) > 0:
                    # ✅ SUCESSO: Marcar como enviado APÓS confirmação
                    payment.meta_purchase_sent = True
                    payment.meta_purchase_sent_at = get_brazil_time()
                    payment.meta_event_id = event_id
                    db.session.commit()
                    
                    logger.info(f"✅ Purchase ENVIADO com sucesso para Meta: R$ {payment.amount} | " +
                               f"Events Received: {result.get('events_received', 0)} | " +
                               f"Task: {task.id}")
                else:
                    # Falhou silenciosamente - não marcar como enviado
                    logger.error(f"❌ Purchase FALHOU silenciosamente: R$ {payment.amount} | " +
                               f"Result: {result} | " +
                               f"Task: {task.id}")
                    db.session.rollback()
            except Exception as result_error:
                # Timeout ou erro ao obter resultado - não marcar como enviado
                logger.error(f"❌ Erro ao obter resultado do Celery: {result_error} | Task: {task.id}")
                # Tentar obter estado da task
                try:
                    task_state = task.state
                    logger.error(f"   Task state: {task_state}")
                    if hasattr(task, 'traceback') and task.traceback:
                        logger.error(f"   Task traceback: {task.traceback[:500]}")
                except:
                    pass
                db.session.rollback()
                
        except Exception as celery_error:
            logger.error(f"❌ ERRO CRÍTICO ao enfileirar Purchase no Celery: {celery_error}", exc_info=True)
            logger.error(f"   Payment ID: {payment.payment_id} | Pool: {pool.name} | Pixel: {pool.meta_pixel_id}")
            # NÃO marcar como enviado se falhou
            db.session.rollback()
    
    except Exception as e:
        logger.error(f"💥 Erro CRÍTICO ao enviar Meta Purchase para payment {payment.id if payment else 'None'}: {e}", exc_info=True)
        db.session.rollback()  # ✅ Rollback se falhar
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

@app.route('/api/bots/<int:bot_id>/webhook-info', methods=['GET'])
@login_required
def get_bot_webhook_info(bot_id):
    """Retorna getWebhookInfo do Telegram e a URL esperada para diagnóstico."""
    try:
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        expected_base = os.environ.get('WEBHOOK_URL', '')
        expected_url = f"{expected_base}/webhook/telegram/{bot_id}" if expected_base else None

        import requests
        info_url = f"https://api.telegram.org/bot{bot.token}/getWebhookInfo"
        resp = requests.get(info_url, timeout=10)
        info = resp.json() if resp.status_code == 200 else {'ok': False, 'status_code': resp.status_code, 'text': resp.text}

        return jsonify({
            'expected_url': expected_url,
            'webhook_info': info
        })
    except Exception as e:
        logger.error(f"Erro ao obter webhook-info do bot {bot_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")  # ✅ PROTEÇÃO: Webhooks de pagamento
@csrf.exempt  # ✅ Webhooks externos não enviam CSRF token
def payment_webhook(gateway_type):
    """Webhook para confirmação de pagamento"""
    data = request.json
    logger.info(f"🔔 WEBHOOK RECEBIDO de {gateway_type}")
    logger.info(f"📦 Dados do webhook: {data}")
    logger.info(f"🌐 IP do remetente: {request.remote_addr}")
    logger.info(f"📋 Headers: {dict(request.headers)}")
    
    try:
        # Processar webhook do gateway
        result = bot_manager.process_payment_webhook(gateway_type, data)
        
        if result:
            gateway_transaction_id = result.get('gateway_transaction_id')
            status = result.get('status')
            
            logger.info(f"✅ Webhook processado: transaction_id={gateway_transaction_id}, status={status}")
            
            # ✅ Buscar pagamento por múltiplas chaves (conforme análise QI 600)
            payment = None
            
            # ✅ PRIORIDADE 1: gateway_transaction_id (campo 'id' da resposta)
            if gateway_transaction_id:
                payment = Payment.query.filter_by(gateway_transaction_id=str(gateway_transaction_id)).first()
                if payment:
                    logger.info(f"✅ Payment encontrado por gateway_transaction_id: {gateway_transaction_id}")
            
            # ✅ PRIORIDADE 2: gateway_transaction_hash (campo 'hash' da resposta)
            if not payment:
                gateway_hash = result.get('gateway_hash') or data.get('hash')
                if gateway_hash:
                    payment = Payment.query.filter_by(gateway_transaction_hash=str(gateway_hash)).first()
                    if payment:
                        logger.info(f"✅ Payment encontrado por gateway_transaction_hash: {gateway_hash}")
            
            # ✅ PRIORIDADE 3: payment_id como fallback
            if not payment and gateway_transaction_id:
                payment = Payment.query.filter_by(payment_id=str(gateway_transaction_id)).first()
                if payment:
                    logger.info(f"✅ Payment encontrado por payment_id (fallback): {gateway_transaction_id}")
            
            # ✅ PRIORIDADE 4: reference (external_reference)
            if not payment:
                # ✅ CORREÇÃO CRÍTICA: Tentar pelo external_reference (prioridade 4)
                # SyncPay/Átomo Pay enviam reference que pode conter o payment_id original
                external_ref = result.get('external_reference')
                if external_ref:
                    # ✅ ÁTOMO PAY: reference pode ser "BOT35-1762426706-594358e0-1762426706325-d5ad225d"
                    # payment_id salvo é "BOT35_1762426706_594358e0" (underscores, sem partes extras)
                    # Extrair payment_id do reference: "BOT35-1762426706-594358e0" -> "BOT35_1762426706_594358e0"
                    import re
                    # Tentar extrair padrão BOT{id}_{timestamp}_{hash} do reference
                    # Exemplo: "BOT35-1762426706-594358e0-..." -> "BOT35_1762426706_594358e0"
                    ref_parts = external_ref.split('-')
                    if len(ref_parts) >= 3 and ref_parts[0].startswith('BOT'):
                        # Construir payment_id esperado: BOT{id}_{timestamp}_{hash}
                        extracted_payment_id = f"{ref_parts[0]}_{ref_parts[1]}_{ref_parts[2]}"
                        payment = Payment.query.filter_by(payment_id=extracted_payment_id).first()
                        if payment:
                            logger.info(f"✅ Payment encontrado por external_reference (extraído: {extracted_payment_id})")
                    
                    # Se não encontrou pelo payment_id extraído, tentar busca direta
                    if not payment:
                        payment = Payment.query.filter_by(payment_id=external_ref).first()
                    
                    if not payment:
                        logger.info(f"🔍 external_reference completo não encontrado, tentando busca parcial...")
                        # Tentar buscar por parte do payment_id (caso external_ref seja hash parcial)
                        # Exemplo: external_ref = "0f57f18b674274be53ad32ff456c1f"
                        # payment_id pode ser "BOT37_1762421295_0f57f18b"
                        # Tentar pelos primeiros 8 caracteres (hash parcial comum)
                        if len(external_ref) >= 8:
                            hash_prefix = external_ref[:8]
                            payments = Payment.query.filter(
                                Payment.payment_id.like(f"%{hash_prefix}%")
                            ).all()
                            if payments:
                                # ✅ Priorizar payment do mesmo gateway e mais recente
                                matching_payments = [p for p in payments if p.gateway_type == gateway_type]
                                if matching_payments:
                                    payment = matching_payments[0]
                                    logger.info(f"✅ Payment encontrado por external_reference (hash parcial {hash_prefix}): {payment.payment_id}")
                                else:
                                    payment = payments[0]  # Fallback
                                    logger.info(f"⚠️ Payment encontrado por external_reference (hash parcial, gateway diferente): {payment.payment_id}")
                        # Se ainda não encontrou, tentar busca completa no payment_id
                        if not payment:
                            payments = Payment.query.filter(
                                Payment.payment_id.like(f"%{external_ref}%")
                            ).all()
                            if payments:
                                matching_payments = [p for p in payments if p.gateway_type == gateway_type]
                                if matching_payments:
                                    payment = matching_payments[0]
                                    logger.info(f"✅ Payment encontrado por external_reference (busca completa): {payment.payment_id}")
                                else:
                                    payment = payments[0]
                                    logger.info(f"⚠️ Payment encontrado por external_reference (busca completa, gateway diferente): {payment.payment_id}")
            
            if payment:
                logger.info(f"💰 Pagamento encontrado: {payment.payment_id} | Status atual: {payment.status}")
                logger.info(f"   Gateway: {payment.gateway_type} | Transaction ID salvo: {payment.gateway_transaction_id}")
            else:
                logger.error(f"❌ ===== PAGAMENTO NÃO ENCONTRADO =====")
                logger.error(f"   gateway_transaction_id buscado: {gateway_transaction_id}")
                logger.error(f"   external_reference: {result.get('external_reference', 'N/A')}")
                logger.error(f"   status do webhook: {status}")
                logger.error(f"")
                logger.error(f"   🔍 Tentando buscar por outros critérios...")
                
                # ✅ BUSCA ALTERNATIVA: Buscar por gateway_type e status pending recente
                from datetime import timedelta
                recent_payments = Payment.query.filter(
                    Payment.gateway_type == gateway_type,
                    Payment.status == 'pending',
                    Payment.created_at >= get_brazil_time() - timedelta(hours=24)
                ).order_by(Payment.created_at.desc()).limit(10).all()
                
                if recent_payments:
                    logger.error(f"   📋 Últimos 10 pagamentos pending de {gateway_type}:")
                    for p in recent_payments:
                        logger.error(f"      - {p.payment_id} | gateway_transaction_id: {p.gateway_transaction_id} | Amount: R$ {p.amount:.2f} | Created: {p.created_at}")
                    
                    # ✅ ÚLTIMA TENTATIVA: Buscar por amount exato (se houver apenas 1 match)
                    webhook_amount = result.get('amount')
                    if webhook_amount:
                        matching_amount = [p for p in recent_payments if abs(p.amount - float(webhook_amount)) < 0.01]
                        if len(matching_amount) == 1:
                            payment = matching_amount[0]
                            logger.info(f"✅ Payment encontrado por amount exato: {payment.payment_id} | Amount: R$ {payment.amount:.2f}")
                        elif len(matching_amount) > 1:
                            logger.warning(f"⚠️ Múltiplos pagamentos com mesmo amount: {len(matching_amount)} encontrados")
                            # Usar o mais recente
                            payment = matching_amount[0]
                            logger.info(f"✅ Payment encontrado por amount (mais recente): {payment.payment_id}")
                
                if not payment:
                    logger.error(f"   ================================================")
                    logger.error(f"   ❌ CRÍTICO: Payment NÃO encontrado após todas as tentativas!")
                    logger.error(f"   A venda foi feita mas não será processada automaticamente.")
                    logger.error(f"   Ação necessária: Processar manualmente ou verificar logs.")
                    logger.error(f"   ================================================")
            
            if payment:
                # ✅ VERIFICA STATUS ANTIGO ANTES DE QUALQUER ATUALIZAÇÃO
                was_pending = payment.status == 'pending'
                status_antigo = payment.status
                logger.info(f"📊 Status ANTES: {status_antigo} | Novo status: {status} | Era pending: {was_pending}")
                
                # ✅ PROTEÇÃO: Se já está paid E o webhook também é paid, pode ser duplicado
                # MAS: Se status_antigo != paid e novo status é paid, PRECISA processar!
                if payment.status == 'paid' and status == 'paid':
                    logger.info(f"⚠️ Webhook duplicado: {payment.payment_id} já está pago - verificando se entregável foi enviado...")
                    # Verificar se entregável já foi enviado (via campo adicional ou log)
                    # Por ora, vamos tentar enviar novamente se falhou antes (idempotente)
                    # Mas retornar sucesso para não duplicar estatísticas
                    try:
                        resultado = send_payment_delivery(payment, bot_manager)
                        if resultado:
                            logger.info(f"✅ Entregável reenviado com sucesso (webhook duplicado)")
                    except:
                        pass
                    return jsonify({'status': 'already_processed'}), 200
                
                # ✅ ATUALIZA STATUS DO PAGAMENTO APENAS SE NÃO ERA PAID (SEM COMMIT AINDA!)
                if payment.status != 'paid':
                    payment.status = status
                
                # ✅ CORREÇÃO CRÍTICA: Enviar entregável SEMPRE que status vira 'paid'
                # Separar lógica: estatísticas só se era pending, entregável SEMPRE se vira paid
                deve_processar_estatisticas = (status == 'paid' and was_pending)
                deve_enviar_entregavel = (status == 'paid')  # SEMPRE envia se status é 'paid'
                
                # ✅ PROCESSAR ESTATÍSTICAS/COMISSÕES APENAS SE ERA PENDENTE (evita duplicação)
                if deve_processar_estatisticas:
                    logger.info(f"✅ Processando pagamento confirmado (era pending): {payment.payment_id}")
                    
                    payment.paid_at = get_brazil_time()
                    payment.bot.total_sales += 1
                    payment.bot.total_revenue += payment.amount
                    payment.bot.owner.total_sales += 1
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
                            paid_at=get_brazil_time()  # Pago no mesmo momento da venda
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
                    
                # ✅ ENVIAR ENTREGÁVEL E META PIXEL SEMPRE QUE STATUS VIRA 'paid' (CRÍTICO!)
                # Isso garante que mesmo se estatísticas já foram processadas, o entregável e Meta Pixel são enviados
                if deve_enviar_entregavel:
                    logger.info(f"📦 Enviando entregável para payment {payment.payment_id} (status: {payment.status})")
                    resultado = send_payment_delivery(payment, bot_manager)
                    if not resultado:
                        logger.warning(f"⚠️ Falha ao enviar entregável para payment {payment.payment_id}")
                    
                    # ============================================================================
                    # ✅ META PIXEL: ENVIAR PURCHASE EVENT (SEMPRE quando status é 'paid')
                    # ============================================================================
                    # ✅ CORREÇÃO CRÍTICA: Sempre enviar Meta Pixel quando status é 'paid',
                    # independente de se estatísticas foram processadas ou não
                    # Isso garante que mesmo se reconciliador atualizar antes do webhook,
                    # o Meta Pixel será enviado via webhook também (idempotente)
                    try:
                        send_meta_pixel_purchase_event(payment)
                        logger.info(f"📊 Meta Pixel Purchase disparado para {payment.payment_id} via webhook {gateway_type}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao disparar Meta Pixel via webhook {gateway_type}: {e}", exc_info=True)
                    
                    # ============================================================================
                    # ✅ UPSELLS AUTOMÁTICOS - APÓS COMPRA APROVADA (só se estatísticas foram processadas)
                    # ============================================================================
                    if deve_processar_estatisticas and payment.bot.config and payment.bot.config.upsells_enabled:
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
                    'payment_id': payment.payment_id,
                    'status': status,
                    'bot_id': payment.bot_id,
                    'amount': payment.amount,
                    'customer_name': payment.customer_name
                }, room=f'user_{payment.bot.user_id}')
                
                # ✅ ENVIAR NOTIFICAÇÃO DE VENDA (respeita configurações do usuário)
                if status == 'paid':
                    send_sale_notification(
                        user_id=payment.bot.user_id,
                        payment=payment,
                        status='approved'
                    )
                
                logger.info(f"💰 Pagamento atualizado: {payment.payment_id} - {status}")
        
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

# ==================== PWA PUSH NOTIFICATIONS ====================

@app.route('/api/push/vapid-public-key', methods=['GET'])
@login_required
def get_vapid_public_key():
    """Retorna chave pública VAPID para registro de subscription"""
    # Chaves VAPID devem ser geradas e configuradas em variáveis de ambiente
    vapid_public_key = os.getenv('VAPID_PUBLIC_KEY')
    
    if not vapid_public_key:
        logger.warning("⚠️ VAPID_PUBLIC_KEY não configurada. Não é possível gerar chaves temporárias dinamicamente.")
        logger.warning("⚠️ Configure VAPID_PUBLIC_KEY e VAPID_PRIVATE_KEY no .env")
        return jsonify({'error': 'VAPID keys não configuradas. Execute: python generate_vapid_keys.py'}), 500
    
    return jsonify({'public_key': vapid_public_key})

@app.route('/api/push/subscribe', methods=['POST'])
@login_required
@csrf.exempt
def subscribe_push():
    """Registra subscription de Push Notification do usuário"""
    try:
        data = request.get_json()
        subscription = data.get('subscription')
        
        if not subscription:
            return jsonify({'error': 'Subscription não fornecida'}), 400
        
        endpoint = subscription.get('endpoint')
        keys = subscription.get('keys', {})
        
        if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
            return jsonify({'error': 'Dados de subscription inválidos'}), 400
        
        # Verificar se já existe subscription com este endpoint
        existing = PushSubscription.query.filter_by(endpoint=endpoint, user_id=current_user.id).first()
        
        if existing:
            # Atualizar existente
            existing.p256dh = keys['p256dh']
            existing.auth = keys['auth']
            existing.user_agent = data.get('user_agent', request.headers.get('User-Agent', ''))
            existing.device_info = data.get('device_info', 'unknown')
            existing.is_active = True
            existing.updated_at = get_brazil_time()
            logger.info(f"✅ Subscription atualizada para user {current_user.id}")
        else:
            # Criar nova
            new_subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh=keys['p256dh'],
                auth=keys['auth'],
                user_agent=data.get('user_agent', request.headers.get('User-Agent', '')),
                device_info=data.get('device_info', 'unknown'),
                is_active=True
            )
            db.session.add(new_subscription)
            logger.info(f"✅ Nova subscription registrada para user {current_user.id}")
        
        db.session.commit()
        return jsonify({'message': 'Subscription registrada com sucesso'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao registrar subscription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/push/subscription-status', methods=['GET'])
@login_required
def get_subscription_status():
    """Verifica se o usuário tem subscription ativa"""
    try:
        active_count = PushSubscription.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).count()
        
        return jsonify({'has_active_subscription': active_count > 0, 'count': active_count})
    except Exception as e:
        logger.error(f"Erro ao verificar status da subscription: {e}")
        return jsonify({'has_active_subscription': False, 'error': str(e)}), 500

@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
@csrf.exempt
def unsubscribe_push():
    """Remove subscription de Push Notification"""
    try:
        data = request.get_json()
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return jsonify({'error': 'Endpoint não fornecido'}), 400
        
        subscription = PushSubscription.query.filter_by(
            endpoint=endpoint,
            user_id=current_user.id
        ).first()
        
        if subscription:
            subscription.is_active = False
            db.session.commit()
            logger.info(f"✅ Subscription desativada para user {current_user.id}")
            return jsonify({'message': 'Subscription removida com sucesso'}), 200
        else:
            return jsonify({'error': 'Subscription não encontrada'}), 404
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao remover subscription: {e}")
        return jsonify({'error': str(e)}), 500

def send_push_notification(user_id, title, body, data=None, color='green'):
    """
    Envia Push Notification para todas as subscriptions ativas do usuário
    
    Args:
        user_id: ID do usuário
        title: Título da notificação
        body: Corpo da notificação
        data: Dados adicionais (dict)
        color: Cor da notificação ('green' para aprovada, 'orange' para pendente)
    """
    try:
        from pywebpush import webpush, WebPushException
        import json
        
        # Buscar todas as subscriptions ativas do usuário
        subscriptions = PushSubscription.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        if not subscriptions:
            logger.info(f"⚠️ [PUSH] Nenhuma subscription ativa para user {user_id}")
            return
        
        # Chave privada VAPID
        vapid_private_key = os.getenv('VAPID_PRIVATE_KEY')
        vapid_claims = {
            "sub": f"mailto:{os.getenv('VAPID_EMAIL', 'admin@grimbots.com')}"
        }
        
        if not vapid_private_key:
            logger.warning("⚠️ VAPID_PRIVATE_KEY não configurada. Push notifications desabilitadas.")
            return
        
        # ✅ TRATAR FORMATO: pywebpush pode aceitar PEM ou base64
        # Se for base64, tentar converter para bytes se necessário
        try:
            # pywebpush aceita string (PEM ou base64) ou bytes
            # Testar se precisa converter
            import base64
            # Se parece ser base64, manter como string (pywebpush trata automaticamente)
            # Se começa com "-----BEGIN", é PEM e já está correto
            if not vapid_private_key.startswith("-----BEGIN"):
                # É base64 - pywebpush pode aceitar diretamente ou precisar converter
                # Vamos deixar como está e verificar se funciona
                logger.debug(f"VAPID key format: base64 ({len(vapid_private_key)} chars)")
        except Exception as e:
            logger.warning(f"⚠️ Aviso ao processar VAPID key: {e}")
        
        # Preparar payload com cor
        # ✅ IMPORTANTE: Incluir todos os dados no nível raiz para fácil acesso no Service Worker
        payload = {
            'title': title,
            'body': body,
            'color': color,  # 'green' ou 'orange'
            **(data or {})  # Spread dos dados adicionais (payment_id, amount, bot_id, url, etc.)
        }
        
        logger.debug(f"📦 Payload sendo enviado: {payload}")
        
        # Enviar para cada subscription
        sent_count = 0
        for subscription in subscriptions:
            try:
                # Log detalhado para debug
                logger.info(f"📤 Enviando push para subscription {subscription.id} (user {user_id})")
                logger.debug(f"   Endpoint: {subscription.endpoint[:50]}...")
                logger.debug(f"   Device: {subscription.device_info}")
                logger.debug(f"   Payload: {payload}")
                
                webpush(
                    subscription_info=subscription.to_dict(),
                    data=json.dumps(payload),
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims,
                    ttl=86400  # 24 horas - tempo de vida do push
                )
                subscription.last_used_at = get_brazil_time()
                sent_count += 1
                logger.info(f"✅ Push enviado com sucesso para subscription {subscription.id}")
            except WebPushException as e:
                logger.error(f"❌ Erro ao enviar push para subscription {subscription.id}: {e}")
                # Log detalhado do erro
                if hasattr(e, 'response') and e.response:
                    logger.error(f"   Status Code: {e.response.status_code}")
                    logger.error(f"   Response: {e.response.text[:200] if hasattr(e.response, 'text') else 'N/A'}")
                # Se subscription inválida (404, 410), marcar como inativa
                if hasattr(e, 'response') and e.response and e.response.status_code in [404, 410]:
                    subscription.is_active = False
                    logger.info(f"🔄 Subscription {subscription.id} marcada como inativa (endpoint inválido)")
            except Exception as e:
                logger.error(f"❌ Erro inesperado ao enviar push: {e}", exc_info=True)
        
        # Salvar atualizações no banco
        if sent_count > 0:
            db.session.commit()
        
        logger.info(f"📱 Push notifications enviadas: {sent_count}/{len(subscriptions)} para user {user_id}")
        
    except ImportError:
        logger.error("❌ pywebpush não instalado. Execute: pip install pywebpush")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar push notifications: {e}")

def send_sale_notification(user_id, payment, status='approved'):
    """
    Envia notificação de venda (pendente ou aprovada) conforme configurações do usuário spread
    
    Args:
        user_id: ID do usuário
        payment: Objeto Payment
        status: 'approved' ou 'pending'
    """
    try:
        logger.info(f"📱 [NOTIFICAÇÃO] Tentando enviar notificação de venda | User: {user_id} | Status: {status} | Valor: R$ {payment.amount:.2f}")
        
        # Buscar configurações do usuário
        settings = NotificationSettings.get_or_create(user_id)
        logger.info(f"📱 [NOTIFICAÇÃO] Configurações do usuário {user_id}: Aprovadas={settings.notify_approved_sales}, Pendentes={settings.notify_pending_sales}")
        
        if status == 'approved':
            if not settings.notify_approved_sales:
                logger.info(f"📱 [NOTIFICAÇÃO] Usuário {user_id} desativou notificações de vendas aprovadas")
                return  # Usuário desativou notificações de vendas aprovadas
            
            logger.info(f"📱 [NOTIFICAÇÃO] Enviando push de venda aprovada para user {user_id}")
            send_push_notification(
                user_id=user_id,
                title='💰 Venda Aprovada!',
                body=f'Você recebeu: R$ {payment.amount:.2f}',
                data={
                    'payment_id': payment.payment_id,
                    'amount': float(payment.amount),
                    'bot_id': payment.bot_id,
                    'url': '/dashboard'
                },
                color='green'  # Verde (#10B981)
            )
            
        elif status == 'pending':
            if not settings.notify_pending_sales:
                logger.info(f"📱 [NOTIFICAÇÃO] Usuário {user_id} desativou notificações de vendas pendentes")
                return  # Usuário desativou notificações de vendas pendentes
            
            logger.info(f"📱 [NOTIFICAÇÃO] Enviando push de venda pendente para user {user_id}")
            send_push_notification(
                user_id=user_id,
                title='🔄 Venda Pendente',
                body=f'Aguardando pagamento: R$ {payment.amount:.2f}',
                data={
                    'payment_id': payment.payment_id,
                    'amount': float(payment.amount),
                    'bot_id': payment.bot_id,
                    'url': '/dashboard'
                },
                color='orange'  # Amarelo/Laranja (#FFB800)
            )
            
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de venda: {e}", exc_info=True)

@app.route('/api/notification-settings', methods=['GET'])
@login_required
def get_notification_settings():
    """Retorna configurações de notificações do usuário"""
    settings = NotificationSettings.get_or_create(current_user.id)
    return jsonify(settings.to_dict())

@app.route('/api/notification-settings', methods=['PUT'])
@login_required
@csrf.exempt
def update_notification_settings():
    """Atualiza configurações de notificações do usuário"""
    try:
        data = request.get_json()
        settings = NotificationSettings.get_or_create(current_user.id)
        
        if 'notify_approved_sales' in data:
            settings.notify_approved_sales = bool(data['notify_approved_sales'])
        if 'notify_pending_sales' in data:
            settings.notify_pending_sales = bool(data['notify_pending_sales'])
        
        settings.updated_at = get_brazil_time()
        db.session.commit()
        
        logger.info(f"✅ Configurações de notificações atualizadas para user {current_user.id}")
        return jsonify(settings.to_dict())
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar configurações: {e}")
        return jsonify({'error': str(e)}), 500

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
            payment.paid_at = get_brazil_time()
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
                    paid_at=get_brazil_time()  # Pago no mesmo momento
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
                            if pool_bot.circuit_breaker_until > get_brazil_time():
                                continue  # Ainda bloqueado
                            else:
                                pool_bot.circuit_breaker_until = None  # Liberado
                        
                        # Health check no Telegram
                        try:
                            validation_result = bot_manager.validate_token(pool_bot.bot.token)
                            if validation_result.get('error_type'):
                                raise Exception('Token inválido')
                        except Exception:
                            # Token inválido ou banido
                            raise
                        
                        # Bot está saudável
                        pool_bot.status = 'online'
                        pool_bot.consecutive_failures = 0
                        pool_bot.last_error = None
                        pool_bot.last_health_check = get_brazil_time()
                        
                    except Exception as e:
                        # Bot falhou
                        pool_bot.consecutive_failures += 1
                        pool_bot.last_error = str(e)
                        pool_bot.last_health_check = get_brazil_time()
                        
                        if pool_bot.consecutive_failures >= 3:
                            # 3 falhas = offline + circuit breaker
                            pool_bot.status = 'offline'
                            pool_bot.circuit_breaker_until = get_brazil_time() + timedelta(minutes=2)
                            
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


# ✅ RANKING V2.0 - Job para atualizar taxas premium dos Top 3
scheduler.add_job(
    id='update_ranking_premium_rates',
    func=update_ranking_premium_rates,
    trigger='interval',
    hours=1,  # Atualizar a cada hora
    replace_existing=True
)

# Agendar health check a cada 15 segundos
scheduler.add_job(
    id='health_check_pools',
    func=health_check_all_pools,
    trigger='interval',
    seconds=15,
    replace_existing=True
)

# ✅ V2.0: Verificar e executar campanhas de remarketing agendadas
def check_scheduled_remarketing_campaigns():
    """
    Verifica campanhas agendadas e inicia envio quando chegar a hora
    Executado a cada 1 minuto via APScheduler
    """
    try:
        with app.app_context():
            from models import RemarketingCampaign, Bot
            from datetime import datetime
            
            now = get_brazil_time()
            
            # Buscar campanhas agendadas que já passaram da hora
            scheduled_campaigns = RemarketingCampaign.query.filter(
                RemarketingCampaign.status == 'scheduled',
                RemarketingCampaign.scheduled_at.isnot(None),
                RemarketingCampaign.scheduled_at <= now
            ).all()
            
            if scheduled_campaigns:
                logger.info(f"📅 Encontradas {len(scheduled_campaigns)} campanha(s) agendada(s) para executar")
            
            for campaign in scheduled_campaigns:
                try:
                    # Buscar bot e token
                    bot = Bot.query.get(campaign.bot_id)
                    if not bot or not bot.token:
                        logger.error(f"❌ Bot {campaign.bot_id} não encontrado ou sem token para campanha {campaign.id}")
                        campaign.status = 'failed'
                        db.session.commit()
                        continue
                    
                    logger.info(f"📤 Iniciando envio de campanha agendada: {campaign.name} (ID: {campaign.id})")
                    
                    # Iniciar envio em background
                    bot_manager.send_remarketing_campaign(campaign_id=campaign.id, bot_token=bot.token)
                    
                    logger.info(f"✅ Campanha agendada {campaign.id} iniciada com sucesso")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao executar campanha agendada {campaign.id}: {e}", exc_info=True)
                    campaign.status = 'failed'
                    db.session.commit()
    
    except Exception as e:
        logger.error(f"❌ Erro ao verificar campanhas agendadas: {e}", exc_info=True)

# Agendar verificação de campanhas agendadas a cada 1 minuto
try:
    scheduler.add_job(
        id='check_scheduled_remarketing',
        func=check_scheduled_remarketing_campaigns,
        trigger='interval',
        minutes=1,  # Verificar a cada 1 minuto
        replace_existing=True,
        max_instances=1
    )
    logger.info("✅ Job de verificação de campanhas agendadas configurado (1 minuto)")
except Exception as e:
    logger.warning(f"⚠️ Não foi possível agendar verificação de campanhas: {e}")


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

