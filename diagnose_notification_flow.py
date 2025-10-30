"""
Script de Diagnóstico: Fluxo de Notificações Push
Verifica cada etapa do processo de envio de notificações
"""

import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from app import app, db
from models import User, PushSubscription, NotificationSettings, Payment, Bot

def diagnose_notification_flow():
    with app.app_context():
        print("="*70)
        print("🔍 DIAGNÓSTICO: Fluxo de Notificações Push")
        print("="*70)
        
        # 1. Verificar pywebpush
        print("\n1️⃣ pywebpush instalado?")
        try:
            from pywebpush import webpush, WebPushException
            print("   ✅ pywebpush está instalado")
        except ImportError:
            print("   ❌ pywebpush NÃO está instalado!")
            print("   Execute: pip install pywebpush")
            return
        
        # 2. Verificar VAPID keys
        print("\n2️⃣ Chaves VAPID configuradas?")
        vapid_public = os.getenv('VAPID_PUBLIC_KEY')
        vapid_private = os.getenv('VAPID_PRIVATE_KEY')
        if vapid_public and vapid_private:
            print(f"   ✅ VAPID_PUBLIC_KEY: {len(vapid_public)} chars")
            print(f"   ✅ VAPID_PRIVATE_KEY: {len(vapid_private)} chars")
        else:
            print("   ❌ VAPID keys não configuradas!")
            print("   Execute: python setup_vapid_keys.py")
            return
        
        # 3. Verificar usuários e suas subscriptions
        print("\n3️⃣ Subscriptions ativas:")
        all_users = User.query.all()
        users_with_subs = []
        for user in all_users:
            subs = PushSubscription.query.filter_by(user_id=user.id, is_active=True).all()
            if subs:
                users_with_subs.append((user, subs))
                print(f"   👤 User {user.id} ({user.email}): {len(subs)} subscription(s) ativa(s)")
                for sub in subs:
                    print(f"      - ID: {sub.id}, Device: {sub.device_info}, Endpoint: {sub.endpoint[:50]}...")
        
        if not users_with_subs:
            print("   ❌ Nenhuma subscription ativa encontrada!")
            print("   ⚠️ O usuário precisa:")
            print("      1. Acessar o dashboard no Android")
            print("      2. Permitir notificações quando solicitado")
            print("      3. Verificar se aparece: '✅ Subscription registrada no servidor' no console")
            return
        
        # 4. Verificar configurações de notificação
        print("\n4️⃣ Configurações de notificações:")
        for user, subs in users_with_subs:
            settings = NotificationSettings.query.filter_by(user_id=user.id).first()
            if settings:
                print(f"   👤 User {user.id}:")
                print(f"      ✅ Notificar vendas aprovadas: {settings.notify_approved_sales}")
                print(f"      ✅ Notificar vendas pendentes: {settings.notify_pending_sales}")
            else:
                print(f"   👤 User {user.id}: ⚠️ Sem configurações (será criada automaticamente)")
        
        # 5. Verificar última venda e se tentou notificar
        print("\n5️⃣ Última venda (última hora):")
        from datetime import timedelta
        last_hour = datetime.now() - timedelta(hours=1)
        recent_payments = Payment.query.filter(Payment.created_at >= last_hour).order_by(Payment.created_at.desc()).limit(5).all()
        
        if not recent_payments:
            print("   ℹ️ Nenhuma venda na última hora")
        else:
            for payment in recent_payments:
                bot = Bot.query.get(payment.bot_id)
                user_id = bot.user_id if bot else None
                print(f"   💰 R$ {payment.amount:.2f} | Status: {payment.status} | Bot: {bot.name if bot else 'N/A'} | User: {user_id}")
                
                if user_id:
                    # Verificar se user tem subscription
                    subs = PushSubscription.query.filter_by(user_id=user_id, is_active=True).all()
                    settings = NotificationSettings.query.filter_by(user_id=user_id).first()
                    print(f"      Subscriptions: {len(subs)} | Notificar pendentes: {settings.notify_pending_sales if settings else 'padrão=False'}")
        
        # 6. Resumo e recomendações
        print("\n" + "="*70)
        print("📋 RESUMO:")
        
        if not vapid_public or not vapid_private:
            print("   ❌ VAPID keys não configuradas - Execute: python setup_vapid_keys.py")
        elif not users_with_subs:
            print("   ❌ Nenhuma subscription ativa - Usuário precisa permitir notificações no navegador")
        else:
            print("   ✅ Tudo parece estar configurado!")
            print("   ℹ️ Próximos passos:")
            print("      1. Faça uma venda de teste")
            print("      2. Verifique os logs para ver se aparece:")
            print("         - '📱 [NOTIFICAÇÃO] Tentando enviar notificação...'")
            print("         - '📤 Enviando push para subscription...'")
            print("      3. Se não aparecer, verifique se 'notify_pending_sales' está ativado nas configurações")
        
        print("="*70)

if __name__ == '__main__':
    diagnose_notification_flow()

