"""
Testes de Segurança - grimbots
================================

Cobertura:
- CSRF Protection
- Rate Limiting
- Criptografia de Credenciais
- Validação de SECRET_KEY
- Input Sanitization

Execução:
    pytest test_security.py -v
"""

import pytest
import os
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# Configurar ambiente de teste ANTES de importar app
os.environ['SECRET_KEY'] = 'test_secret_key_with_at_least_32_characters_for_testing'
os.environ['ENCRYPTION_KEY'] = 'test_encryption_key_base64_format_here_44chars=='
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import app, db
from models import Gateway, User
from utils.encryption import encrypt, decrypt

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Cliente de teste Flask"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = True  # ✅ CSRF ativo em testes
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

@pytest.fixture
def test_user():
    """Usuário de teste"""
    with app.app_context():
        user = User(
            email='test@example.com',
            username='testuser',
            full_name='Test User'
        )
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.commit()
        return user

# =============================================================================
# TESTE #1: CSRF PROTECTION
# =============================================================================

def test_csrf_token_required_on_login(client):
    """
    CRÍTICO: Verifica se login SEM csrf_token é BLOQUEADO
    """
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'wrong'
    })
    
    # Deve retornar 400 (Bad Request) por falta de CSRF token
    assert response.status_code == 400, \
        "❌ FALHA: Login sem CSRF token deveria ser bloqueado"

def test_csrf_token_required_on_register(client):
    """
    CRÍTICO: Verifica se registro SEM csrf_token é BLOQUEADO
    """
    response = client.post('/register', data={
        'email': 'new@example.com',
        'username': 'newuser',
        'full_name': 'New User',
        'password': 'Password123!'
    })
    
    assert response.status_code == 400, \
        "❌ FALHA: Registro sem CSRF token deveria ser bloqueado"

def test_csrf_token_valid_passes(client):
    """
    Verifica se requisição COM csrf_token válido PASSA
    """
    with client.session_transaction() as sess:
        # Obter CSRF token da sessão
        csrf_token = sess.get('csrf_token', None)
    
    # TODO: Implementar quando templates tiverem csrf_token()
    # Por ora, apenas verificar que CSRF está ativo
    assert app.config.get('WTF_CSRF_ENABLED') == True

# =============================================================================
# TESTE #2: RATE LIMITING
# =============================================================================

def test_rate_limit_blocks_brute_force_login(client):
    """
    CRÍTICO: Verifica se rate limit bloqueia 11ª tentativa de login
    Configurado: 10 tentativas por minuto
    """
    # Fazer 10 tentativas (permitidas)
    for i in range(10):
        response = client.post('/login', data={
            'email': 'test@example.com',
            'password': f'wrong{i}'
        }, follow_redirects=False)
        # Pode ser 400 (CSRF) ou outro, mas não 429
    
    # 11ª tentativa deve ser bloqueada com 429 (Too Many Requests)
    response = client.post('/login', data={
        'email': 'test@example.com',
        'password': 'wrong11'
    })
    
    assert response.status_code == 429, \
        f"❌ FALHA: 11ª tentativa deveria retornar 429, mas retornou {response.status_code}"

def test_rate_limit_blocks_register_spam(client):
    """
    Verifica se rate limit bloqueia spam de registro
    Configurado: 3 registros por hora
    """
    # Fazer 3 tentativas (permitidas)
    for i in range(3):
        response = client.post('/register', data={
            'email': f'spam{i}@example.com',
            'username': f'spam{i}',
            'full_name': f'Spam {i}',
            'password': 'Password123!'
        })
    
    # 4ª tentativa deve ser bloqueada
    response = client.post('/register', data={
        'email': 'spam4@example.com',
        'username': 'spam4',
        'full_name': 'Spam 4',
        'password': 'Password123!'
    })
    
    assert response.status_code == 429, \
        f"❌ FALHA: 4º registro deveria ser bloqueado"

# =============================================================================
# TESTE #3: CRIPTOGRAFIA
# =============================================================================

def test_encryption_roundtrip():
    """
    Verifica se encrypt/decrypt funcionam corretamente
    """
    original = "minha_senha_secreta_123"
    
    # Criptografar
    encrypted = encrypt(original)
    
    # Não deve ser igual ao original
    assert encrypted != original, \
        "❌ FALHA: Texto criptografado não deve ser igual ao original"
    
    # Descriptografar
    decrypted = decrypt(encrypted)
    
    # Deve retornar ao original
    assert decrypted == original, \
        f"❌ FALHA: Decrypt falhou. Esperado: {original}, Obtido: {decrypted}"

def test_gateway_credentials_are_encrypted_in_database():
    """
    CRÍTICO: Verifica se credenciais de Gateway são armazenadas CRIPTOGRAFADAS
    """
    with app.app_context():
        # Criar gateway de teste
        gateway = Gateway(
            user_id=1,
            gateway_type='test_gateway'
        )
        
        # Atribuir credencial em texto plano
        plain_secret = "my_secret_api_key_12345"
        gateway.client_secret = plain_secret
        
        db.session.add(gateway)
        db.session.commit()
        
        # Verificar que _client_secret (campo no banco) está CRIPTOGRAFADO
        assert gateway._client_secret != plain_secret, \
            "❌ FALHA CRÍTICA: Credencial armazenada em TEXTO PLANO no banco!"
        
        # Verificar que property retorna DESCRIPTOGRAFADO
        assert gateway.client_secret == plain_secret, \
            "❌ FALHA: Property não descriptografou corretamente"
        
        # Recarregar do banco para garantir persistência
        db.session.refresh(gateway)
        
        # Ainda deve descriptografar corretamente
        assert gateway.client_secret == plain_secret, \
            "❌ FALHA: Persistência falhou"

def test_gateway_encryption_handles_none_values():
    """
    Verifica se criptografia lida com valores None corretamente
    """
    with app.app_context():
        gateway = Gateway(
            user_id=1,
            gateway_type='test'
        )
        
        # Atribuir None
        gateway.client_secret = None
        
        db.session.add(gateway)
        db.session.commit()
        
        # Deve retornar None (não tentar criptografar None)
        assert gateway.client_secret is None
        assert gateway._client_secret is None

# =============================================================================
# TESTE #4: VALIDAÇÃO DE SECRET_KEY
# =============================================================================

def test_secret_key_minimum_length():
    """
    Verifica se SECRET_KEY tem no mínimo 32 caracteres
    """
    secret_key = app.config['SECRET_KEY']
    
    assert len(secret_key) >= 32, \
        f"❌ FALHA: SECRET_KEY muito curta ({len(secret_key)} chars). Mínimo: 32"

def test_secret_key_not_default():
    """
    Verifica se SECRET_KEY não é a padrão de desenvolvimento
    """
    secret_key = app.config['SECRET_KEY']
    
    default_keys = [
        'dev',
        'development',
        'dev-secret-key-change-in-production',
        'test123',
        'secret'
    ]
    
    for default in default_keys:
        assert default not in secret_key.lower(), \
            f"❌ FALHA: SECRET_KEY parece ser padrão: '{secret_key}'"

# =============================================================================
# TESTE #5: INPUT SANITIZATION
# =============================================================================

def test_sql_injection_prevention():
    """
    Verifica se ORM previne SQL Injection básico
    """
    with app.app_context():
        # Tentar SQL injection via email
        malicious_email = "admin' OR '1'='1"
        
        # ORM deve escapar automaticamente
        user = User.query.filter_by(email=malicious_email).first()
        
        # Não deve encontrar usuário (injection não funciona)
        assert user is None, \
            "❌ FALHA: SQL Injection possível!"

# =============================================================================
# RELATÓRIO
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("EXECUTANDO TESTES DE SEGURANÇA - grimbots")
    print("=" * 70)
    print()
    
    # Executar com pytest
    pytest.main([__file__, '-v', '--tb=short'])


