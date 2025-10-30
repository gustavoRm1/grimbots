"""
Script para verificar e corrigir chaves VAPID existentes
Execute: python fix_vapid_keys.py
"""

import os
import base64
from dotenv import load_dotenv

load_dotenv()

def check_vapid_key_format():
    """Verifica se a chave VAPID pública está no formato correto (65 bytes)"""
    print("="*70)
    print("🔍 VERIFICAÇÃO E CORREÇÃO DE CHAVES VAPID")
    print("="*70)
    print()
    
    vapid_public = os.getenv('VAPID_PUBLIC_KEY', '')
    
    if not vapid_public:
        print("❌ VAPID_PUBLIC_KEY não configurada no .env")
        print("   Execute: python generate_vapid_keys.py")
        return False
    
    print(f"📏 Tamanho atual da chave pública: {len(vapid_public)} caracteres")
    
    # Tentar decodificar
    try:
        # Adicionar padding
        padding = '=' * ((4 - len(vapid_public) % 4) % 4)
        base64_standard = (vapid_public + padding).replace('-', '+').replace('_', '/')
        decoded = base64.b64decode(base64_standard)
        
        print(f"📊 Bytes decodificados: {len(decoded)} bytes")
        
        if len(decoded) == 64:
            print()
            print("⚠️ PROBLEMA DETECTADO:")
            print("   A chave VAPID tem apenas 64 bytes!")
            print("   Web Push API requer 65 bytes (1 byte prefixo 0x04 + 64 bytes de coordenadas)")
            print()
            print("🔧 SOLUÇÃO:")
            print("   1. Execute: python generate_vapid_keys.py")
            print("   2. Copie as novas chaves geradas para o .env")
            print("   3. Reinicie o servidor: systemctl restart grimbots")
            return False
        elif len(decoded) == 65:
            print("✅ Tamanho correto: 65 bytes")
            if decoded[0] == 0x04:
                print("✅ Prefixo correto: 0x04")
                print()
                print("✅ Chave VAPID está no formato correto!")
                print("   Se ainda há erro no frontend, pode ser problema de conversão JavaScript")
                return True
            else:
                print(f"⚠️ Prefixo incorreto: 0x{decoded[0]:02x} (esperado: 0x04)")
                return False
        else:
            print(f"❌ Tamanho inválido: {len(decoded)} bytes (esperado: 65 bytes)")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao decodificar chave: {e}")
        return False

if __name__ == '__main__':
    check_vapid_key_format()

