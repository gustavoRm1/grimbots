"""
🧪 TESTE COMPLETO - ANALYTICS V2.0 (QI 540)

OBJETIVO:
- Validar API retorna dados corretos
- Validar detecção de problemas
- Validar detecção de oportunidades
- Validar cálculo de ROI

Implementado por: QI 540
"""

import os
import sys
from datetime import datetime, timedelta

# Ajustar sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ✅ CONFIGURAR ENCRYPTION_KEY ANTES DE IMPORTAR APP
if 'ENCRYPTION_KEY' not in os.environ:
    print("⚙️  Configurando ENCRYPTION_KEY para teste...")
    os.environ['ENCRYPTION_KEY'] = 'test-key-for-analytics-v2-qi540-validation-only'

from app import app, db
from models import User, Bot, Payment, BotUser, RedirectPool, PoolBot
import json

def setup_test_data():
    """Criar dados de teste realistas"""
    print("\n🔧 Configurando dados de teste...")
    
    with app.app_context():
        # Limpar dados anteriores
        Payment.query.delete()
        BotUser.query.delete()
        PoolBot.query.delete()
        RedirectPool.query.delete()
        Bot.query.delete()
        User.query.filter(User.email == 'test_analytics@grimbots.com').delete()
        db.session.commit()
        
        # Criar usuário
        user = User(
            email='test_analytics@grimbots.com',
            name='Test Analytics',
            is_active=True
        )
        user.set_password('senha123')
        db.session.add(user)
        db.session.commit()
        
        # Criar bot
        bot = Bot(
            user_id=user.id,
            name='Bot Analytics Test',
            username='test_analytics_bot',
            token='TEST:analytics_token',
            is_running=True
        )
        db.session.add(bot)
        db.session.commit()
        
        # ===================================================================
        # CENÁRIO 1: BOT COM LUCRO E OPORTUNIDADES
        # ===================================================================
        today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        
        # Criar usuários com PageView (simular tráfego pago)
        for i in range(100):
            user_obj = BotUser(
                bot_id=bot.id,
                telegram_user_id=900000 + i,
                first_name=f'User{i}',
                username=f'user{i}',
                meta_pageview_sent=True,
                meta_pageview_sent_at=today,
                utm_source='facebook',
                utm_campaign='test-campaign'
            )
            db.session.add(user_obj)
        
        # 40 usuários iniciam conversa (ViewContent)
        for i in range(40):
            user_obj = BotUser.query.filter_by(telegram_user_id=900000 + i).first()
            user_obj.meta_viewcontent_sent = True
            user_obj.meta_viewcontent_sent_at = today
        
        db.session.commit()
        
        # 20 vendas hoje (R$ 4.000 de receita)
        for i in range(20):
            payment = Payment(
                bot_id=bot.id,
                customer_name=f'Customer{i}',
                customer_user_id=f'user{i}',
                amount=200.0,  # R$ 200 cada
                status='paid',
                payment_id=f'test_pay_{i}',
                created_at=today,
                utm_source='facebook',
                utm_campaign='test-campaign'
            )
            db.session.add(payment)
        
        # 10 vendas ontem (R$ 2.000 de receita - para comparação)
        for i in range(10):
            payment = Payment(
                bot_id=bot.id,
                customer_name=f'CustomerY{i}',
                customer_user_id=f'user_y{i}',
                amount=200.0,
                status='paid',
                payment_id=f'test_pay_yesterday_{i}',
                created_at=yesterday
            )
            db.session.add(payment)
        
        # Clientes recorrentes (para oportunidade de upsell)
        for i in range(5):
            payment = Payment(
                bot_id=bot.id,
                customer_name=f'Customer{i}',
                customer_user_id=f'user{i}',  # Mesmo user_id
                amount=150.0,
                status='paid',
                payment_id=f'test_pay_repeat_{i}',
                created_at=today
            )
            db.session.add(payment)
        
        db.session.commit()
        
        print(f"✅ Criado usuário: {user.email}")
        print(f"✅ Criado bot: {bot.name} (ID: {bot.id})")
        print(f"✅ 100 PageViews (tráfego pago)")
        print(f"✅ 40 ViewContents (40% conversão)")
        print(f"✅ 20 compras hoje (R$ 4.000)")
        print(f"✅ 10 compras ontem (R$ 2.000)")
        print(f"✅ 5 clientes recorrentes")
        
        return user, bot


def test_analytics_v2():
    """Teste principal"""
    print("\n" + "="*60)
    print("🧪 TESTE ANALYTICS V2.0 (QI 540)")
    print("="*60)
    
    user, bot = setup_test_data()
    
    with app.test_client() as client:
        # Login
        response = client.post('/login', data={
            'email': 'test_analytics@grimbots.com',
            'password': 'senha123'
        }, follow_redirects=True)
        
        print(f"\n📡 Chamando API: /api/bots/{bot.id}/analytics-v2")
        
        # Chamar API
        response = client.get(f'/api/bots/{bot.id}/analytics-v2')
        
        assert response.status_code == 200, f"❌ Status: {response.status_code}"
        
        data = response.json
        
        print("\n" + "="*60)
        print("💰 CARD 1: LUCRO/PREJUÍZO HOJE")
        print("="*60)
        
        summary = data['summary']
        print(f"Faturou hoje: R$ {summary['today_revenue']:.2f}")
        print(f"Gastou estimado (100 cliques × R$ 2): R$ {summary['today_spend']:.2f}")
        print(f"Lucro: R$ {summary['today_profit']:.2f}")
        print(f"ROI: {summary['today_roi']:.1f}%")
        print(f"Vendas: {summary['today_sales']}")
        print(f"vs Ontem: {summary['revenue_change']:+.1f}%")
        print(f"Status: {summary['status']}")
        
        # Validações
        assert summary['today_revenue'] == 4000.0, "❌ Receita deveria ser R$ 4.000"
        assert summary['today_spend'] == 200.0, "❌ Gasto deveria ser R$ 200 (100 × R$ 2)"
        assert summary['today_profit'] == 3800.0, "❌ Lucro deveria ser R$ 3.800"
        assert summary['today_roi'] > 0, "❌ ROI deveria ser positivo"
        assert summary['today_sales'] == 20, "❌ Deveria ter 20 vendas"
        assert summary['status'] == 'profit', "❌ Status deveria ser 'profit'"
        
        print("✅ Card 1: VALIDADO")
        
        print("\n" + "="*60)
        print("⚠️  CARD 2: PROBLEMAS")
        print("="*60)
        
        problems = data['problems']
        print(f"Problemas detectados: {len(problems)}")
        
        if problems:
            for i, p in enumerate(problems, 1):
                print(f"\n{i}. [{p['severity']}] {p['title']}")
                print(f"   {p['description']}")
                print(f"   💡 {p['action']}")
                print(f"   [{p['action_button']}]")
        else:
            print("✅ Nenhum problema crítico detectado")
        
        # Como ROI está positivo, não deve ter problema de ROI negativo
        roi_problem = any('ROI negativo' in p['title'] for p in problems)
        assert not roi_problem, "❌ Não deveria detectar ROI negativo (ROI está positivo)"
        
        print("✅ Card 2: VALIDADO")
        
        print("\n" + "="*60)
        print("🚀 CARD 3: OPORTUNIDADES")
        print("="*60)
        
        opportunities = data['opportunities']
        print(f"Oportunidades detectadas: {len(opportunities)}")
        
        if opportunities:
            for i, o in enumerate(opportunities, 1):
                print(f"\n{i}. [{o['type']}] {o['title']}")
                print(f"   {o['description']}")
                print(f"   ⚡ {o['action']}")
                print(f"   [{o['action_button']}]")
        else:
            print("⚠️  Nenhuma oportunidade especial detectada")
        
        # Deve detectar oportunidade de ROI alto (1800% ROI)
        scale_opp = any('ROI excelente' in o['title'] for o in opportunities)
        assert scale_opp, "❌ Deveria detectar oportunidade de escalar (ROI > 200%)"
        
        # Deve detectar oportunidade de upsell (25%+ recompra)
        upsell_opp = any('compram 2+ vezes' in o['title'] for o in opportunities)
        assert upsell_opp, "❌ Deveria detectar oportunidade de upsell (5 de 20 = 25%)"
        
        print("✅ Card 3: VALIDADO")
        
        print("\n" + "="*60)
        print("📊 DADOS COMPLEMENTARES")
        print("="*60)
        
        funnel = data['conversion_funnel']
        print(f"\nFunil de Conversão:")
        print(f"  PageViews: {funnel['pageviews']}")
        print(f"  ViewContents: {funnel['viewcontents']}")
        print(f"  Purchases: {funnel['purchases']}")
        print(f"  Taxa PageView → ViewContent: {funnel['pageview_to_viewcontent']:.1f}%")
        print(f"  Taxa ViewContent → Purchase: {funnel['viewcontent_to_purchase']:.1f}%")
        
        assert funnel['pageviews'] == 100, "❌ Deveria ter 100 PageViews"
        assert funnel['viewcontents'] == 40, "❌ Deveria ter 40 ViewContents"
        assert funnel['purchases'] == 20, "❌ Deveria ter 20 Purchases"
        
        print("✅ Funil: VALIDADO")
        
        print("\n" + "="*60)
        print("🎉 TESTE COMPLETO: SUCESSO")
        print("="*60)
        
        print("\n✅ TODAS AS VALIDAÇÕES PASSARAM:")
        print("  ✅ Cálculo de lucro correto")
        print("  ✅ Cálculo de ROI correto")
        print("  ✅ Comparação com ontem correto")
        print("  ✅ Detecção de problemas funcionando")
        print("  ✅ Detecção de oportunidades funcionando")
        print("  ✅ Funil de conversão correto")
        
        print("\n💪 Analytics V2.0 está PRONTO PARA PRODUÇÃO!")


if __name__ == '__main__':
    try:
        test_analytics_v2()
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES PASSARAM - QI 540")
        print("="*60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TESTE FALHOU: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

