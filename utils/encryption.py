"""
============================================================================
CORREÇÃO #5: CRIPTOGRAFIA DE CREDENCIAIS DE GATEWAY
============================================================================

Sistema de criptografia segura usando Fernet (AES-128 CBC + HMAC)
Protege: API Keys, Client Secrets, Tokens de gateway de pagamento
"""

from cryptography.fernet import Fernet
import os
import sys

# ============================================================================
# VALIDAÇÃO: ENCRYPTION_KEY OBRIGATÓRIA
# ============================================================================

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

if not ENCRYPTION_KEY:
    raise RuntimeError(
        "\n❌ ERRO CRÍTICO: ENCRYPTION_KEY não configurada!\n\n"
        "Execute:\n"
        "  python -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\" >> .env\n"
    )

try:
    # Tentar criar Fernet para validar formato
    fernet = Fernet(ENCRYPTION_KEY.encode())
except Exception as e:
    raise RuntimeError(
        f"\n❌ ERRO CRÍTICO: ENCRYPTION_KEY inválida!\n"
        f"Erro: {e}\n\n"
        "Gere uma nova:\n"
        "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
    )


# ============================================================================
# FUNÇÕES DE CRIPTOGRAFIA/DESCRIPTOGRAFIA
# ============================================================================

def encrypt(value: str) -> str:
    """
    Criptografa um valor usando Fernet (AES-128)
    
    Args:
        value: String a ser criptografada
        
    Returns:
        String criptografada em base64
    """
    if not value:
        return None
    
    try:
        encrypted_bytes = fernet.encrypt(value.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"Erro ao criptografar: {e}")


def decrypt(value: str) -> str:
    """
    Descriptografa um valor usando Fernet (AES-128)
    
    Args:
        value: String criptografada em base64
        
    Returns:
        String descriptografada
    """
    if not value:
        return None
    
    try:
        decrypted_bytes = fernet.decrypt(value.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        raise RuntimeError(
            f"Erro ao descriptografar: {e}\n"
            "POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após armazenar dados.\n"
            "SOLUÇÃO: Restaure a ENCRYPTION_KEY original ou reconfigure os gateways."
        )


# ============================================================================
# UTILITÁRIO: GERAR NOVA ENCRYPTION_KEY
# ============================================================================

def generate_encryption_key() -> str:
    """
    Gera uma nova ENCRYPTION_KEY válida
    
    Returns:
        Nova chave em formato string
    """
    return Fernet.generate_key().decode('utf-8')


if __name__ == '__main__':
    print("=" * 70)
    print("GERADOR DE ENCRYPTION_KEY")
    print("=" * 70)
    print()
    print("Nova ENCRYPTION_KEY gerada:")
    print()
    key = generate_encryption_key()
    print(f"ENCRYPTION_KEY={key}")
    print()
    print("✅ Copie esta linha e adicione ao arquivo .env")
    print("⚠️  NUNCA compartilhe esta chave")
    print("⚠️  Se perdê-la, todos os dados criptografados serão irrecuperáveis")
    print("=" * 70)






