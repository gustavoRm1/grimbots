#!/usr/bin/env python3
"""
Fix Stats Calculation
=====================

Corrige as estatísticas do bot e user que estavam sendo calculadas errado.
O bug estava em usar total_sales += payment.amount ao invés de += 1.
"""

import os
import sys
from datetime import datetime

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Bot, User, Payment
from sqlalchemy import func
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def recalculate_bot_stats(bot_id):
    """Recalcula estatísticas de um bot específico"""
    with app.app_context():
        try:
            bot = Bot.query.get(bot_id)
            if not bot:
                logger.error(f"❌ Bot {bot_id} não encontrado")
                return
            
            logger.info(f"🔍 Recalculando estatísticas do bot {bot.name} (ID: {bot_id})...")
            
            # Recalcular vendas e receita
            payments_stats = db.session.query(
                func.count(Payment.id).label('total_sales'),
                func.sum(Payment.amount).label('total_revenue')
            ).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid'
            ).first()
            
            old_sales = bot.total_sales
            old_revenue = bot.total_revenue
            
            bot.total_sales = payments_stats.total_sales or 0
            bot.total_revenue = float(payments_stats.total_revenue or 0)
            
            db.session.commit()
            
            logger.info(f"✅ Bot {bot.name}:")
            logger.info(f"   Total Sales: {old_sales} → {bot.total_sales}")
            logger.info(f"   Total Revenue: R$ {old_revenue:.2f} → R$ {bot.total_revenue:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao recalcular bot {bot_id}: {e}")
            db.session.rollback()


def recalculate_user_stats(user_id):
    """Recalcula estatísticas de um user específico"""
    with app.app_context():
        try:
            user = User.query.get(user_id)
            if not user:
                logger.error(f"❌ User {user_id} não encontrado")
                return
            
            logger.info(f"🔍 Recalculando estatísticas do user {user.username} (ID: {user_id})...")
            
            # Buscar todos os bots do user
            bot_ids = [bot.id for bot in user.bots]
            
            if not bot_ids:
                logger.warning(f"⚠️ User {user.username} não tem bots")
                return
            
            # Recalcular vendas e receita baseado nos pagamentos dos bots do user
            payments_stats = db.session.query(
                func.count(Payment.id).label('total_sales'),
                func.sum(Payment.amount).label('total_revenue')
            ).filter(
                Payment.bot_id.in_(bot_ids),
                Payment.status == 'paid'
            ).first()
            
            old_sales = user.total_sales
            old_revenue = user.total_revenue
            
            user.total_sales = payments_stats.total_sales or 0
            user.total_revenue = float(payments_stats.total_revenue or 0)
            
            db.session.commit()
            
            logger.info(f"✅ User {user.username}:")
            logger.info(f"   Total Sales: {old_sales} → {user.total_sales}")
            logger.info(f"   Total Revenue: R$ {old_revenue:.2f} → R$ {user.total_revenue:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao recalcular user {user_id}: {e}")
            db.session.rollback()


def recalculate_all_stats():
    """Recalcula todas as estatísticas"""
    with app.app_context():
        logger.info("🚀 Recalculando TODAS as estatísticas...")
        
        try:
            # Recalcular todos os bots
            bots = Bot.query.all()
            logger.info(f"📊 Recalculando {len(bots)} bot(s)...")
            
            for bot in bots:
                recalculate_bot_stats(bot.id)
            
            # Recalcular todos os users
            users = User.query.filter_by(is_admin=False).all()
            logger.info(f"👥 Recalculando {len(users)} user(s)...")
            
            for user in users:
                recalculate_user_stats(user.id)
            
            logger.info("✅ Todas as estatísticas foram recalculadas!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao recalcular: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    logger.info("🚀 Iniciando correção de estatísticas...")
    recalculate_all_stats()
    logger.info("✅ Correção concluída!")

