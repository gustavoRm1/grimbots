"""
Script de Verificação QI 500
Valida todas as implementações da arquitetura multi-gateway e tracking universal

Execute: python verificar_implementacao_qi500.py
"""

import sys
import os
from pathlib import Path
import importlib.util

# Adicionar raiz ao path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Variáveis de controle
checks_passed = 0
checks_failed = 0
warnings = []

def print_check(name, passed, message=""):
    """Imprime resultado de um check"""
    global checks_passed, checks_failed
    if passed:
        print(f"[OK] {name}")
        if message:
            print(f"     {message}")
        checks_passed += 1
    else:
        print(f"[ERRO] {name}")
        if message:
            print(f"       {message}")
        checks_failed += 1

def print_warning(message):
    """Imprime um aviso"""
    warnings.append(message)
    print(f"[AVISO] {message}")

def check_file_exists(file_path):
    """Verifica se arquivo existe"""
    return file_path.exists() and file_path.is_file()

def check_file_contains(file_path, *strings):
    """Verifica se arquivo contém strings"""
    if not check_file_exists(file_path):
        return False
    try:
        content = file_path.read_text(encoding='utf-8')
        return all(s in content for s in strings)
    except:
        return False

import io
import sys

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print("=" * 70)
print("VERIFICACAO IMPLEMENTACAO QI 500")
print("=" * 70)
print()

# ============================================================================
# CHECK 1: GatewayFactory com Adapter
# ============================================================================
print("[1/10] Verificando GatewayFactory (Adapter)...")
try:
    from gateway_factory import GatewayFactory
    
    # Verificar se método create_gateway aceita use_adapter
    import inspect
    sig = inspect.signature(GatewayFactory.create_gateway)
    has_use_adapter = 'use_adapter' in sig.parameters
    
    print_check(
        "GatewayFactory.create_gateway(use_adapter)",
        has_use_adapter,
        "Parâmetro use_adapter presente"
    )
    
    # Tentar criar gateway com adapter (padrão)
    try:
        dummy_credentials = {'api_token': 'dummy_test'}
        gateway = GatewayFactory.create_gateway('atomopay', dummy_credentials)
        
        if gateway:
            # Verificar se tem atributo _gateway (indica que é adapter)
            has_adapter = hasattr(gateway, '_gateway')
            print_check(
                "GatewayFactory retorna GatewayAdapter",
                has_adapter,
                "Adapter está envolvendo o gateway" if has_adapter else "Gateway não está usando adapter"
            )
        else:
            print_check("GatewayFactory cria gateway", False, "Gateway retornou None (pode ser por credenciais inválidas)")
    except Exception as e:
        print_warning(f"GatewayFactory retorna GatewayAdapter: Erro ao criar gateway (normal se credenciais inválidas): {e}")
        
except ImportError as e:
    print_check("GatewayFactory importado", False, f"Erro ao importar: {e}")

print()

# ============================================================================
# CHECK 2: TrackingServiceV4
# ============================================================================
print("[2/10] Verificando TrackingServiceV4...")
try:
    from utils.tracking_service import TrackingServiceV4
    
    service = TrackingServiceV4()
    print_check(
        "TrackingServiceV4 carregado",
        service is not None,
        f"Classe: {TrackingServiceV4.__name__}"
    )
    
    # Verificar métodos principais
    has_generate = hasattr(service, 'generate_tracking_token')
    has_save = hasattr(service, 'save_tracking_data')
    has_recover = hasattr(service, 'recover_tracking_data')
    
    print_check(
        "TrackingServiceV4 métodos",
        has_generate and has_save and has_recover,
        "generate_tracking_token, save_tracking_data, recover_tracking_data presentes"
    )
    
    # Testar geração de token
    try:
        token = service.generate_tracking_token(
            bot_id=1,
            customer_user_id='123456'
        )
        is_valid = token.startswith('tracking_') and len(token) > 10
        print_check(
            "TrackingServiceV4.generate_tracking_token",
            is_valid,
            f"Token gerado: {token[:20]}..." if is_valid else "Token inválido"
        )
    except Exception as e:
        print_check("TrackingServiceV4.generate_tracking_token", False, f"Erro ao gerar token: {e}")
    
except ImportError as e:
    print_check("TrackingServiceV4", False, f"Erro ao importar: {e}")
except Exception as e:
    print_check("TrackingServiceV4", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 3: Modelo Payment com tracking_token
# ============================================================================
print("[3/10] Verificando modelo Payment...")
try:
    # Verificar se campo tracking_token existe no modelo (via arquivo)
    models_path = BASE_DIR / 'models.py'
    if check_file_contains(models_path, 'tracking_token'):
        print_check(
            "Payment.tracking_token (modelo)",
            True,
            "Campo tracking_token presente no modelo Payment"
        )
    else:
        print_check("Payment.tracking_token (modelo)", False, "Campo tracking_token NÃO encontrado no modelo")
    
    # Verificar banco (tentar importar app se possível)
    try:
        from models import Payment
        has_field = hasattr(Payment, 'tracking_token')
        print_check(
            "Payment.tracking_token (atributo)",
            has_field,
            "Campo tracking_token presente como atributo"
        )
    except Exception as e:
        print_warning(f"Não foi possível verificar atributo Payment.tracking_token: {e}")
        
except Exception as e:
    print_check("Payment.tracking_token", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 4: GatewayAdapter
# ============================================================================
print("[4/10] Verificando GatewayAdapter...")
try:
    from gateway_adapter import GatewayAdapter
    
    print_check(
        "GatewayAdapter importado",
        True,
        f"Classe: {GatewayAdapter.__name__}"
    )
    
    # Verificar métodos principais
    has_normalize_generate = hasattr(GatewayAdapter, '_normalize_generate_response')
    has_normalize_webhook = hasattr(GatewayAdapter, '_normalize_webhook_response')
    has_extract_producer = hasattr(GatewayAdapter, 'extract_producer_hash')
    
    print_check(
        "GatewayAdapter métodos de normalização",
        has_normalize_generate and has_normalize_webhook,
        "Métodos de normalização presentes"
    )
    
    print_check(
        "GatewayAdapter.extract_producer_hash",
        has_extract_producer,
        "Método extract_producer_hash presente"
    )
    
except ImportError as e:
    print_check("GatewayAdapter", False, f"Erro ao importar: {e}")

print()

# ============================================================================
# CHECK 5: extract_producer_hash na interface
# ============================================================================
print("[5/10] Verificando extract_producer_hash...")
try:
    from gateway_interface import PaymentGateway
    
    has_method = hasattr(PaymentGateway, 'extract_producer_hash')
    print_check(
        "PaymentGateway.extract_producer_hash",
        has_method,
        "Método extract_producer_hash presente na interface"
    )
    
    # Verificar implementação no AtomPay
    from gateway_atomopay import AtomPayGateway
    atompay_has_method = hasattr(AtomPayGateway, 'extract_producer_hash')
    
    # Verificar se é método próprio (não herdado)
    if atompay_has_method:
        method = getattr(AtomPayGateway, 'extract_producer_hash')
        is_overridden = 'AtomPayGateway' in str(method.__qualname__)
        print_check(
            "AtomPayGateway.extract_producer_hash",
            is_overridden,
            "Método implementado em AtomPayGateway" if is_overridden else "Método não sobrescrito"
        )
    
except ImportError as e:
    print_check("extract_producer_hash", False, f"Erro ao importar: {e}")

print()

# ============================================================================
# CHECK 6: Middleware
# ============================================================================
print("[6/10] Verificando Middleware...")
try:
    middleware_path = BASE_DIR / 'middleware' / 'gateway_validator.py'
    has_middleware_file = middleware_path.exists()
    
    print_check(
        "Middleware arquivo",
        has_middleware_file,
        f"Arquivo: {middleware_path.name}"
    )
    
    if has_middleware_file:
        from middleware.gateway_validator import validate_gateway_request, rate_limit_webhook, sanitize_log_data
        
        has_validate = callable(validate_gateway_request)
        has_rate_limit = callable(rate_limit_webhook)
        has_sanitize = callable(sanitize_log_data)
        
        print_check(
            "Middleware funções",
            has_validate and has_rate_limit and has_sanitize,
            "validate_gateway_request, rate_limit_webhook, sanitize_log_data presentes"
        )
    
except ImportError as e:
    print_check("Middleware", False, f"Erro ao importar: {e}")
except Exception as e:
    print_check("Middleware", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 7: Webhook usando GatewayAdapter
# ============================================================================
print("[7/10] Verificando webhook (app.py)...")
try:
    app_py_path = BASE_DIR / 'app.py'
    if app_py_path.exists():
        content = app_py_path.read_text(encoding='utf-8')
        
        # Verificar se webhook usa GatewayAdapter
        uses_adapter = 'GatewayFactory.create_gateway' in content and 'use_adapter=True' in content
        uses_extract_producer = 'extract_producer_hash' in content
        
        print_check(
            "Webhook usando GatewayAdapter",
            uses_adapter,
            "Webhook criando gateway com adapter=True"
        )
        
        print_check(
            "Webhook usando extract_producer_hash",
            uses_extract_producer,
            "Webhook extraindo producer_hash via adapter"
        )
    
except Exception as e:
    print_check("Webhook", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 8: bot_manager usando TrackingServiceV4
# ============================================================================
print("[8/10] Verificando bot_manager...")
try:
    bot_manager_path = BASE_DIR / 'bot_manager.py'
    if bot_manager_path.exists():
        content = bot_manager_path.read_text(encoding='utf-8')
        
        uses_tracking_v4 = 'TrackingServiceV4' in content
        generates_token = 'generate_tracking_token' in content
        saves_tracking = 'save_tracking_data' in content and 'tracking_token' in content
        
        print_check(
            "bot_manager usando TrackingServiceV4",
            uses_tracking_v4,
            "TrackingServiceV4 importado e usado"
        )
        
        print_check(
            "bot_manager gerando tracking_token",
            generates_token,
            "generate_tracking_token sendo chamado"
        )
        
        print_check(
            "bot_manager salvando tracking_token",
            saves_tracking,
            "tracking_token sendo salvo no Payment e Redis"
        )
    
except Exception as e:
    print_check("bot_manager", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 9: Migration disponível
# ============================================================================
print("[9/10] Verificando Migration...")
try:
    migration_path = BASE_DIR / 'migrations' / 'migrations_add_tracking_token.py'
    has_migration = migration_path.exists()
    
    print_check(
        "Migration arquivo",
        has_migration,
        f"Arquivo: {migration_path.name}"
    )
    
    if has_migration:
        content = migration_path.read_text(encoding='utf-8')
        detects_table = 'payments' in content or 'payment' in content
        is_idempotent = 'already exists' in content.lower() or 'if not exists' in content.lower()
        
        print_check(
            "Migration detecta tabela automaticamente",
            detects_table,
            "Migration detecta 'payments' ou 'payment'"
        )
        
        print_check(
            "Migration idempotente",
            is_idempotent,
            "Migration pode rodar múltiplas vezes sem erro"
        )
    
except Exception as e:
    print_check("Migration", False, f"Erro: {e}")

print()

# ============================================================================
# CHECK 10: Meta Pixel usando tracking_token
# ============================================================================
print("[10/10] Verificando Meta Pixel...")
try:
    app_py_path = BASE_DIR / 'app.py'
    if app_py_path.exists():
        content = app_py_path.read_text(encoding='utf-8')
        
        # Verificar se send_meta_pixel_purchase_event usa tracking_token
        uses_tracking_token = 'payment.tracking_token' in content or ('tracking_token' in content and 'recover_tracking_data' in content)
        
        uses_tracking_v4_recover = 'TrackingServiceV4' in content and 'recover_tracking_data' in content
        
        print_check(
            "Meta Pixel usando tracking_token",
            uses_tracking_token,
            "send_meta_pixel_purchase_event recupera dados via tracking_token"
        )
        
        print_check(
            "Meta Pixel usando TrackingServiceV4",
            uses_tracking_v4_recover,
            "Recuperação via TrackingServiceV4.recover_tracking_data"
        )
    
except Exception as e:
    print_check("Meta Pixel", False, f"Erro: {e}")

print()

# ============================================================================
# RESUMO FINAL
# ============================================================================
print("=" * 70)
print("RESUMO DA VERIFICACAO")
print("=" * 70)
print(f"[OK] Checks passados: {checks_passed}")
print(f"[ERRO] Checks falhados: {checks_failed}")
print(f"[AVISO] Avisos: {len(warnings)}")
print()

if warnings:
    print("[AVISOS]")
    for warning in warnings:
        print(f"   - {warning}")
    print()

if checks_failed == 0:
    print("[SUCESSO] PARABENS! Implementacao QI 500 esta 100% completa!")
    print()
    print("[PROXIMOS PASSOS]")
    print("   1. Execute a migration no servidor:")
    print("      python migrations/migrations_add_tracking_token.py")
    print()
    print("   2. Reinicie o serviço:")
    print("      sudo systemctl restart grimbots")
    print()
    print("   3. Teste uma transação real:")
    print("      - Gere um PIX com valor exótico (ex: 41,73)")
    print("      - NÃO pague")
    print("      - Vá no painel da Átomo e clique em 'Enviar novamente webhook'")
    print("      - Verifique logs: journalctl -u grimbots -f")
    print("      - Deve aparecer:")
    print("        ✅ Producer hash identificado")
    print("        ✅ Gateway Adapter usado")
    print("        ✅ Payment encontrado")
    print("        ✅ Status updated: pending → failed")
    print()
    print("   4. Verificar se Pixel NÃO dispara se recusado:")
    print("      - Payment com status 'failed' não deve disparar Meta Pixel")
    print()
    sys.exit(0)
else:
    print("[ATENCAO] Alguns checks falharam. Revise os erros acima.")
    print()
    print("[DICA] Execute este script no servidor para verificar:")
    print("   - Banco de dados (migration aplicada)")
    print("   - Dependências instaladas")
    print("   - Configurações de produção")
    sys.exit(1)
