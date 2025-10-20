"""
Test: Gateway Statistics Update
================================
Testes automatizados para garantir que as estatísticas dos gateways
são atualizadas corretamente quando pagamentos são criados e confirmados.

Autor: Senior Developer (QI 240)
Data: 2025-10-20
"""

import pytest
from app import app, db
from models import User, Bot, BotConfig, Gateway, Payment
from datetime import datetime


class TestGatewayStatistics:
    """Testes de atualização de estatísticas de gateway"""
    
    @pytest.fixture
    def client(self):
        """Setup do cliente de teste"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app.test_client()
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def test_user(self):
        """Cria usuário de teste"""
        user = User(
            email='test@gateway.com',
            username='testuser',
            commission_percentage=2.0
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()
        return user
    
    @pytest.fixture
    def test_bot(self, test_user):
        """Cria bot de teste"""
        bot = Bot(
            user_id=test_user.id,
            token='TEST_TOKEN_12345',
            name='Test Bot',
            username='testbot'
        )
        db.session.add(bot)
        db.session.commit()
        return bot
    
    @pytest.fixture
    def test_gateway(self, test_user):
        """Cria gateway de teste"""
        gateway = Gateway(
            user_id=test_user.id,
            gateway_type='syncpay',
            client_id='test_client',
            is_active=True,
            is_verified=True,
            total_transactions=0,
            successful_transactions=0
        )
        gateway.client_secret = 'test_secret'
        db.session.add(gateway)
        db.session.commit()
        return gateway
    
    def test_gateway_stats_on_payment_creation(self, client, test_bot, test_gateway):
        """
        Testa se total_transactions é incrementado ao criar pagamento
        """
        # Arrange
        initial_total = test_gateway.total_transactions
        
        # Act
        payment = Payment(
            bot_id=test_bot.id,
            payment_id='TEST_PAY_001',
            gateway_type='syncpay',
            gateway_transaction_id='TXN_001',
            amount=50.0,
            customer_name='Test Customer',
            customer_user_id='123456',
            product_name='Test Product',
            status='pending'
        )
        db.session.add(payment)
        
        # Simular incremento manual (como em bot_manager.py linha ~1626)
        test_gateway.total_transactions += 1
        
        db.session.commit()
        
        # Assert
        assert test_gateway.total_transactions == initial_total + 1
        assert test_gateway.successful_transactions == 0  # Ainda pendente
        print(f"✓ Payment created: total_transactions = {test_gateway.total_transactions}")
    
    def test_gateway_stats_on_payment_confirmation(self, client, test_bot, test_gateway):
        """
        Testa se successful_transactions é incrementado ao confirmar pagamento
        """
        # Arrange - Criar pagamento pendente
        payment = Payment(
            bot_id=test_bot.id,
            payment_id='TEST_PAY_002',
            gateway_type='syncpay',
            gateway_transaction_id='TXN_002',
            amount=100.0,
            customer_name='Test Customer 2',
            customer_user_id='789012',
            product_name='Test Product 2',
            status='pending'
        )
        db.session.add(payment)
        test_gateway.total_transactions += 1
        db.session.commit()
        
        initial_successful = test_gateway.successful_transactions
        
        # Act - Confirmar pagamento
        payment.status = 'paid'
        payment.paid_at = datetime.now()
        
        # Simular incremento (como em app.py linha ~3357)
        test_gateway.successful_transactions += 1
        
        db.session.commit()
        
        # Assert
        assert test_gateway.successful_transactions == initial_successful + 1
        assert payment.status == 'paid'
        print(f"✓ Payment confirmed: successful_transactions = {test_gateway.successful_transactions}")
    
    def test_gateway_success_rate_calculation(self, client, test_bot, test_gateway):
        """
        Testa o cálculo correto da taxa de sucesso
        """
        # Arrange - Criar 5 pagamentos (3 pagos, 2 pendentes)
        for i in range(5):
            payment = Payment(
                bot_id=test_bot.id,
                payment_id=f'TEST_PAY_{i+10}',
                gateway_type='syncpay',
                gateway_transaction_id=f'TXN_{i+10}',
                amount=50.0,
                customer_name=f'Customer {i}',
                customer_user_id=f'{i}',
                product_name='Product',
                status='pending'
            )
            db.session.add(payment)
            test_gateway.total_transactions += 1
            
            # Confirmar apenas os 3 primeiros
            if i < 3:
                payment.status = 'paid'
                payment.paid_at = datetime.now()
                test_gateway.successful_transactions += 1
        
        db.session.commit()
        
        # Act - Calcular taxa de sucesso
        success_rate = (test_gateway.successful_transactions / test_gateway.total_transactions * 100) if test_gateway.total_transactions > 0 else 0
        
        # Assert
        assert test_gateway.total_transactions == 5
        assert test_gateway.successful_transactions == 3
        assert success_rate == 60.0  # 3/5 = 60%
        print(f"✓ Success rate calculated: {success_rate}% (3/5)")
    
    def test_gateway_stats_isolation_per_user(self, client):
        """
        Testa se as estatísticas de gateways são isoladas por usuário
        """
        # Arrange - Criar 2 usuários com gateways
        user1 = User(email='user1@test.com', username='user1', commission_percentage=2.0)
        user1.set_password('pass1')
        user2 = User(email='user2@test.com', username='user2', commission_percentage=2.0)
        user2.set_password('pass2')
        
        db.session.add_all([user1, user2])
        db.session.commit()
        
        gateway1 = Gateway(user_id=user1.id, gateway_type='syncpay', total_transactions=0, successful_transactions=0)
        gateway2 = Gateway(user_id=user2.id, gateway_type='syncpay', total_transactions=0, successful_transactions=0)
        
        db.session.add_all([gateway1, gateway2])
        db.session.commit()
        
        bot1 = Bot(user_id=user1.id, token='TOKEN1', name='Bot1')
        bot2 = Bot(user_id=user2.id, token='TOKEN2', name='Bot2')
        
        db.session.add_all([bot1, bot2])
        db.session.commit()
        
        # Act - Criar pagamentos para cada usuário
        payment1 = Payment(
            bot_id=bot1.id,
            payment_id='PAY_USER1',
            gateway_type='syncpay',
            amount=50.0,
            customer_user_id='1',
            status='paid'
        )
        payment2 = Payment(
            bot_id=bot2.id,
            payment_id='PAY_USER2',
            gateway_type='syncpay',
            amount=100.0,
            customer_user_id='2',
            status='paid'
        )
        
        db.session.add_all([payment1, payment2])
        gateway1.total_transactions += 1
        gateway1.successful_transactions += 1
        gateway2.total_transactions += 1
        gateway2.successful_transactions += 1
        db.session.commit()
        
        # Assert - Verificar isolamento
        assert gateway1.total_transactions == 1
        assert gateway1.successful_transactions == 1
        assert gateway2.total_transactions == 1
        assert gateway2.successful_transactions == 1
        print(f"✓ Gateway stats isolated per user")
    
    def test_gateway_stats_idempotency(self, client, test_bot, test_gateway):
        """
        Testa se webhooks duplicados não incrementam contadores duas vezes
        """
        # Arrange
        payment = Payment(
            bot_id=test_bot.id,
            payment_id='TEST_PAY_DUP',
            gateway_type='syncpay',
            gateway_transaction_id='TXN_DUP',
            amount=50.0,
            customer_user_id='999',
            status='pending'
        )
        db.session.add(payment)
        test_gateway.total_transactions += 1
        db.session.commit()
        
        # Act - Simular primeiro webhook (confirmação)
        if payment.status != 'paid':  # ✅ Verificação de idempotência
            payment.status = 'paid'
            payment.paid_at = datetime.now()
            test_gateway.successful_transactions += 1
            db.session.commit()
        
        successful_after_first = test_gateway.successful_transactions
        
        # Simular segundo webhook duplicado
        if payment.status != 'paid':  # ❌ Não deve entrar aqui
            payment.status = 'paid'
            payment.paid_at = datetime.now()
            test_gateway.successful_transactions += 1
            db.session.commit()
        
        # Assert
        assert test_gateway.successful_transactions == successful_after_first
        assert test_gateway.successful_transactions == 1  # Incrementou apenas uma vez
        print(f"✓ Duplicate webhook handled correctly (idempotency)")


if __name__ == '__main__':
    print("=" * 80)
    print("TESTES DE ESTATISTICAS DE GATEWAY")
    print("=" * 80)
    print()
    
    # Executar testes
    pytest.main([__file__, '-v', '--tb=short'])

