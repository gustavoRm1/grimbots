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
import hashlib
import base64
from pathlib import Path

# ============================================================================
# CARREGAR ENCRYPTION_KEY VIA SECRETS LOADER (hierarquia: PATH > BASE64 > STRING)
# ============================================================================

# SECRETS LOADER: Usar hierarquia PATH > BASE64 > STRING
from utils.secrets_loader import get_encryption_key

RAW_ENCRYPTION_KEY = get_encryption_key()


def _derive_fernet_key(raw_key: str) -> bytes:
    """
    Deriva uma chave Fernet válida a partir de qualquer string.
    
    Suporta:
    - Chaves Fernet completas (base64 url-safe, 32 bytes)
    - Strings curtas (16-32 chars) → Derivação via SHA256 (COMPATIBILIDADE LEGADO)
    - Hexadecimal → Decodificação + padding
    - Qualquer formato legado
    
    Args:
        raw_key: String da ENCRYPTION_KEY
        
    Returns:
        bytes: Chave Fernet válida (base64 url-safe, 32 bytes)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not raw_key:
        raise ValueError("ENCRYPTION_KEY vazia")
    
    key_str = raw_key.strip()
    
    # Tentativa 1: Já é uma chave Fernet válida?
    try:
        # Fernet.generate_key() retorna base64 url-safe de 32 bytes
        # Exemplo: b'gAAAAAB...' (44 caracteres)
        if len(key_str) >= 32:
            test_key = key_str.encode('utf-8')
            Fernet(test_key)  # Validação
            logger.info(f" Chave Fernet válida detectada (formato nativo)")
            return test_key
    except Exception:
        pass  # Não é formato Fernet, continuar derivação
    
    # Tentativa 2: String curta (16-31 chars) → SHA256 + Base64 (COMPATIBILIDADE LEGADO)
    try:
        if 16 <= len(key_str) <= 32:
            # Derivar 32 bytes via SHA256
            key_bytes = hashlib.sha256(key_str.encode('utf-8')).digest()
            # Codificar em base64 url-safe (formato Fernet)
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            # Validar
            Fernet(fernet_key)
            logger.info(f" Chave derivada via SHA256 (compatibilidade legado)")
            return fernet_key
    except Exception:
        pass
    
    # Tentativa 3: Hexadecimal → Decode + Base64
    try:
        if len(key_str) == 64:  # Possível hex de 32 bytes
            hex_bytes = bytes.fromhex(key_str)
            if len(hex_bytes) == 32:
                fernet_key = base64.urlsafe_b64encode(hex_bytes)
                Fernet(fernet_key)
                logger.info(f" Chave derivada de hexadecimal")
                return fernet_key
    except Exception:
        pass
    
    # Tentativa 4: Qualquer outra string → SHA256 (fallback final)
    try:
        key_bytes = hashlib.sha256(key_str.encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        Fernet(fernet_key)
        logger.info(f" Chave derivada via SHA256 (fallback)")
        return fernet_key
    except Exception:
        pass
    
    # Erro: Formato não reconhecido
    raise RuntimeError(
        f"\n ERRO CRÍTICO: Não foi possível derivar chave Fernet!\n"
        f"Tamanho da chave fornecida: {len(key_str)}\n"
        f"Primeiros 20 chars: {key_str[:20]}...\n\n"
        f"A chave deve ser:\n"
        f"  - Uma chave Fernet completa (base64 url-safe, ~44 chars)\n"
        f"  - Uma string de 16-32 caracteres (será derivada via SHA256)\n"
        f"  - Hexadecimal de 64 caracteres (32 bytes)\n\n"
        f"Gere uma nova chave:\n"
        f"  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )


# Derivar chave compatível
ENCRYPTION_KEY = _derive_fernet_key(RAW_ENCRYPTION_KEY)

try:
    # Tentar criar Fernet para validar formato
    fernet = Fernet(ENCRYPTION_KEY)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f" Fernet inicializado com sucesso (chave derivada)")
except Exception as e:
    raise RuntimeError(
        f"\n ERRO CRÍTICO: Falha ao inicializar Fernet com chave derivada!\n"
        f"Erro: {e}\n\n"
        f"Verifique a ENCRYPTION_KEY no .env"
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
        String descriptografada ou None em caso de erro (resiliência)
        
    Raises:
        RuntimeError: Apenas em casos críticos (não para InvalidToken)
    """
    if not value:
        return None
    
    try:
        decrypted_bytes = fernet.decrypt(value.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        # ✅ CRÍTICO: Tratamento resiliente para InvalidToken
        import logging
        logger = logging.getLogger(__name__)
        
        # ✅ VERIFICAR TIPO ESPECÍFICO DE ERRO
        error_type = type(e).__name__
        
        if 'InvalidToken' in error_type or 'cryptography.fernet.InvalidToken' in str(type(e)):
            # ✅ RESILIÊNCIA: InvalidToken significa ENCRYPTION_KEY mudou
            # NÃO deve crashar o sistema, apenas retornar None
            logger.warning(f"⚠️ ERRO DE DESCRIPTOGRAFIA (InvalidToken): ENCRYPTION_KEY foi alterada")
            logger.warning(f"   Valor (primeiros 50 chars): {value[:50] if value else 'None'}...")
            logger.warning(f"   SOLUÇÃO: Reconfigure as credenciais do gateway")
            return None  # ✅ RESILIÊNCIA: Retorna None em vez de crashar
        
        # ✅ OUTROS ERROS: Log detalhado para diagnóstico
        logger.error(f"❌ ERRO AO DESCRIPTOGRAFAR: {error_type}: {e}")
        logger.error(f"   Valor (primeiros 50 chars): {value[:50] if value else 'None'}...")
        logger.error(f"   ENCRYPTION_KEY está configurada: {bool(ENCRYPTION_KEY)}")
        logger.error(f"   ENCRYPTION_KEY (primeiros 20 chars): {ENCRYPTION_KEY[:20] if ENCRYPTION_KEY else 'None'}...")
        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após armazenar dados")
        logger.error(f"   SOLUÇÃO: Restaure a ENCRYPTION_KEY original ou reconfigure os gateways")
        
        # ✅ RESILIÊNCIA: Retornar None em vez de crashar
        return None


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






