"""
Script de Diagnóstico: Push Notifications Android
Verifica por que notificações não estão chegando
"""

from app import app, db
from models import PushSubscription, NotificationSettings, User, Payment
from datetime import datetime, timedelta

def diagnose():
    with app.app_context():
        print("="*70)
        print("🔍 DIAGNÓSTICO: Push Notifications Android")
        print("="*70)
        print()
        
        # 1. Verificar VAPID keys
        import os
        vapid_public = os.getenv('VAPID_PUBLIC_KEY')
        vapid_private = os.getenv('VAPID_PRIVATE_KEY')
        vapid_email = os.getenv('VAPID_EMAIL', 'admin@grimbots.com')
        
        print("1️⃣ CONFIGURAÇÃO VAPID:")
        if vapid_public:
            print(f"   ✅ VAPID_PUBLIC_KEY: {vapid_public[:20]}...")
        else:
            print("   ❌ VAPID_PUBLIC_KEY: NÃO CONFIGURADA")
        
        if vapid_private:
            print(f"   ✅ VAPID_PRIVATE_KEY: {vapid_private[:20]}...")
        else:
            print("   ❌ VAPID_PRIVATE_KEY: NÃO CONFIGURADA")
        
        print(f"   📧 VAPID_EMAIL: {vapid_email}")
        print()
        
        # 2. Verificar subscriptions ativas
        active_subs = PushSubscription.query.filter_by(is_active=True).all()
        print(f"2️⃣ SUBSCRIPTIONS ATIVAS: {len(active_subs)}")
        for sub in active_subs:
            user = User.query.get(sub.user_id)
            device = sub.device_info or 'unknown'
            endpoint_short = sub.endpoint[:50] + '...' if len(sub.endpoint) > 50 else sub.endpoint
            print(f"   👤 User: {user.email if user else 'N/A'}")
            print(f"   📱 Device: {device}")
            print(f"   🔗 Endpoint: {endpoint_short}")
            print(f"   📅 Último uso: {sub.last_used_at or 'Nunca'}")
            print(f"   📅 Criado em: {sub.created_at}")
            print()
        
        # 3. Verificar configurações de notificações dos usuários
        print("3️⃣ CONFIGURAÇÕES DE NOTIFICAÇÕES:")
        users_with_subs = User.query.join(PushSubscription).filter(
            PushSubscription.is_active == True
        ).distinct().all()
        
        for user in users_with_subs:
            settings = NotificationSettings.query.filter_by(user_id=user.id).first()
            if settings:
                print(f"   👤 {user.email}:")
                print(f"      ✅ Vendas Aprovadas: {settings.notify_approved_sales}")
                print(f"      ✅ Vendas Pendentes: {settings.notify_pending_sales}")
            else:
                print(f"   👤 {user.email}: ⚠️ Sem configurações (usando padrão)")
        print()
        
        # 4. Verificar vendas recentes (últimas 24h)
        print("4️⃣ VENDAS RECENTES (últimas 24h):")
        yesterday = datetime.now() - timedelta(days=1)
        recent_payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= yesterday
        ).all()
        
        print(f"   📊 Total: {len(recent_payments)} vendas")
        for payment in recent_payments[:5]:  # Mostrar apenas 5 primeiras
            user = payment.bot.owner
            print(f"   💰 R$ {payment.amount:.2f} - Bot: {payment.bot.name} - User: {user.email}")
        print()
        
        # 5. Ver dashboard do usuário (verificar se tem subscription)
        print("5️⃣ RECOMENDAÇÕES:")
        if not vapid_public or not vapid_private:
            print("   ⚠️ Configure VAPID keys no .env")
            print("   Gerar keys: python -c \"from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); print('PUBLIC:', v.public_key.public_bytes_raw().hex()); print('PRIVATE:', v.private_key.private_bytes_raw().hex())\"")
        else:
            print("   ✅ VAPID keys configuradas")
        
        if len(active_subs) == 0:
            print("   ⚠️ Nenhuma subscription ativa encontrada")
            print("   ℹ️ O usuário precisa acessar o dashboard e permitir notificações")
        else:
            print(f"   ✅ {len(active_subs)} subscription(s) ativa(s)")
            print("   ℹ️ Verificar logs do servidor quando uma venda é aprovada")
            print("   ℹ️ Verificar console do navegador no Android (DevTools remoto)")
        
        print()
        print("="*70)
        print("✅ Diagnóstico concluído!")
        print("="*70)

if __name__ == '__main__':
    diagnose()

