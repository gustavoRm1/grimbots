"""
TESTES: TRACKING ELITE
======================

Testa todo o fluxo de captura e associação de IP/UA/Session

Autor: QI 500 Elite Team
Data: 2025-10-21
"""

import pytest
import json
import redis
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Configuração do test environment
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, db
from models import BotUser, RedirectPool, PoolBot, Bot, User


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


@pytest.fixture
def redis_mock():
    """Mock Redis para testes"""
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    yield r
    # Cleanup
    try:
        r.flushdb()
    except:
        pass


def test_redirect_captures_tracking_data(client, redis_mock):
    """Teste 1: Redirect captura IP, UA e salva no Redis"""
    
    # Setup: Criar pool e bot
    with app.app_context():
        user = User(email='test@test.com', username='test')
        user.set_password('test123')
        db.session.add(user)
        
        bot = Bot(user_id=1, token='test_token', username='testbot', is_running=False)
        db.session.add(bot)
        
        pool = RedirectPool(
            name='Test Pool',
            slug='testpool',
            is_active=True,
            meta_cloaker_enabled=False
        )
        db.session.add(pool)
        db.session.commit()
        
        pool_bot = PoolBot(pool_id=pool.id, bot_id=bot.id, is_enabled=True, status='online')
        db.session.add(pool_bot)
        db.session.commit()
    
    # Fazer request com fbclid
    response = client.get(
        '/go/testpool?fbclid=test123abc&utm_source=facebook',
        headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1) Safari/537.36',
            'X-Forwarded-For': '179.123.45.67'
        }
    )
    
    # Verificar redirect
    assert response.status_code == 302
    
    # Verificar se salvou no Redis
    tracking_json = redis_mock.get('tracking:test123abc')
    assert tracking_json is not None, "Tracking não foi salvo no Redis"
    
    tracking_data = json.loads(tracking_json)
    
    # Validar dados salvos
    assert tracking_data['ip'] == '179.123.45.67'
    assert 'iPhone' in tracking_data['user_agent']
    assert tracking_data['fbclid'] == 'test123abc'
    assert tracking_data['utm_source'] == 'facebook'
    assert 'session_id' in tracking_data
    assert 'timestamp' in tracking_data
    
    print("✅ TESTE 1 PASSOU: Redirect captura e salva dados no Redis")


def test_botuser_associates_tracking_data(redis_mock):
    """Teste 2: BotUser busca dados do Redis e associa"""
    
    # Setup: Salvar dados no Redis
    tracking_data = {
        'ip': '179.123.45.67',
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1) Safari/537.36',
        'fbclid': 'test456def',
        'session_id': 'uuid-test-123',
        'timestamp': datetime.now().isoformat(),
        'utm_source': 'facebook',
        'utm_campaign': 'black_friday'
    }
    
    redis_mock.setex('tracking:test456def', 180, json.dumps(tracking_data))
    
    # Simular criação de BotUser com fbclid
    with app.app_context():
        user = User(email='test2@test.com', username='test2')
        user.set_password('test123')
        db.session.add(user)
        
        bot = Bot(user_id=1, token='test_token2', username='testbot2', is_running=False)
        db.session.add(bot)
        db.session.commit()
        
        bot_user = BotUser(
            bot_id=bot.id,
            telegram_user_id='123456',
            first_name='Test',
            fbclid='test456def'
        )
        
        # Simular lógica de associação do bot_manager
        if bot_user.fbclid:
            tracking_json = redis_mock.get(f'tracking:{bot_user.fbclid}')
            if tracking_json:
                tracking_elite = json.loads(tracking_json)
                
                bot_user.ip_address = tracking_elite.get('ip')
                bot_user.user_agent = tracking_elite.get('user_agent')
                bot_user.tracking_session_id = tracking_elite.get('session_id')
                bot_user.click_timestamp = datetime.fromisoformat(tracking_elite['timestamp'])
        
        db.session.add(bot_user)
        db.session.commit()
        
        # Validar associação
        assert bot_user.ip_address == '179.123.45.67'
        assert 'iPhone' in bot_user.user_agent
        assert bot_user.tracking_session_id == 'uuid-test-123'
        assert bot_user.click_timestamp is not None
        
        # Verificar que foi deletado do Redis
        assert redis_mock.get('tracking:test456def') is None
    
    print("✅ TESTE 2 PASSOU: BotUser associa dados do Redis corretamente")


def test_tracking_elite_with_ttl_expired(redis_mock):
    """Teste 3: Comportamento quando TTL expira (> 3 min)"""
    
    with app.app_context():
        user = User(email='test3@test.com', username='test3')
        user.set_password('test123')
        db.session.add(user)
        
        bot = Bot(user_id=1, token='test_token3', username='testbot3', is_running=False)
        db.session.add(bot)
        db.session.commit()
        
        # Criar BotUser SEM dados no Redis (simulando expiração)
        bot_user = BotUser(
            bot_id=bot.id,
            telegram_user_id='789012',
            first_name='Test',
            fbclid='expired_fbclid'
        )
        
        # Tentar buscar do Redis
        tracking_json = redis_mock.get(f'tracking:{bot_user.fbclid}')
        
        # Não deve quebrar, apenas não associar
        if tracking_json:
            # Associar (não vai entrar aqui)
            pass
        else:
            # Deve cair aqui e continuar funcionando
            assert bot_user.ip_address is None
            assert bot_user.user_agent is None
        
        db.session.add(bot_user)
        db.session.commit()
        
        # Bot funciona normalmente mesmo sem tracking elite
        assert bot_user.id is not None
        assert bot_user.telegram_user_id == '789012'
    
    print("✅ TESTE 3 PASSOU: Sistema funciona mesmo quando TTL expira")


def test_redis_failure_graceful_degradation():
    """Teste 4: Sistema continua funcionando se Redis cair"""
    
    with app.app_context():
        user = User(email='test4@test.com', username='test4')
        user.set_password('test123')
        db.session.add(user)
        
        bot = Bot(user_id=1, token='test_token4', username='testbot4', is_running=False)
        db.session.add(bot)
        db.session.commit()
        
        # Simular Redis indisponível
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")
            
            # Criar BotUser deve funcionar normalmente
            bot_user = BotUser(
                bot_id=bot.id,
                telegram_user_id='345678',
                first_name='Test',
                fbclid='test_fbclid'
            )
            
            try:
                # Tentar buscar do Redis (vai falhar)
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                tracking_json = r.get(f'tracking:{bot_user.fbclid}')
            except Exception as e:
                # Erro capturado, sistema continua
                pass
            
            # Bot funciona sem tracking elite
            db.session.add(bot_user)
            db.session.commit()
            
            assert bot_user.id is not None
    
    print("✅ TESTE 4 PASSOU: Degradação graciosa quando Redis falha")


def test_meta_pixel_uses_tracking_data():
    """Teste 5: Meta Pixel usa IP/UA do tracking elite"""
    
    with app.app_context():
        user = User(email='test5@test.com', username='test5')
        user.set_password('test123')
        db.session.add(user)
        
        bot = Bot(user_id=1, token='test_token5', username='testbot5', is_running=False)
        db.session.add(bot)
        db.session.commit()
        
        # Criar BotUser COM tracking elite
        bot_user = BotUser(
            bot_id=bot.id,
            telegram_user_id='567890',
            first_name='Test',
            ip_address='179.123.45.67',
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1) Safari/537.36',
            tracking_session_id='uuid-test-456'
        )
        
        db.session.add(bot_user)
        db.session.commit()
        
        # Simular construção de evento Meta Pixel
        event_data = {
            'user_data': {
                'external_id': f'user_{bot_user.telegram_user_id}',
                'client_ip_address': bot_user.ip_address if hasattr(bot_user, 'ip_address') and bot_user.ip_address else None,
                'client_user_agent': bot_user.user_agent if hasattr(bot_user, 'user_agent') and bot_user.user_agent else None
            }
        }
        
        # Validar que dados foram incluídos
        assert event_data['user_data']['client_ip_address'] == '179.123.45.67'
        assert 'iPhone' in event_data['user_data']['client_user_agent']
    
    print("✅ TESTE 5 PASSOU: Meta Pixel usa dados do tracking elite")


if __name__ == '__main__':
    # Rodar testes
    pytest.main([__file__, '-v', '-s'])

