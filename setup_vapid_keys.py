"""
Script para configurar VAPID keys automaticamente no .env
Execute: python setup_vapid_keys.py
"""

import os
import base64
import tempfile
from pathlib import Path
from py_vapid import Vapid01
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def setup_vapid_keys():
    """Gera e configura VAPID keys no .env"""
    try:
        print("🔑 Gerando chaves VAPID...")
        vapid = Vapid01()
        vapid.generate_keys()
        
        # Salvar chave privada em arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as f:
            temp_private = f.name
        
        try:
            # Salvar chave privada (formato PEM)
            vapid.save_key(temp_private)
            
            # Ler chave privada do arquivo
            with open(temp_private, 'rb') as f:
                private_key_pem = f.read()
            
            # Carregar chave privada
            private_key_obj = serialization.load_pem_private_key(
                private_key_pem,
                password=None,
                backend=default_backend()
            )
            
            # Obter chave pública
            public_key_obj = private_key_obj.public_key()
            
            # Converter chave pública para formato uncompressed point
            public_key_uncompressed = public_key_obj.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            
            # Web Push API usa apenas os 64 bytes (sem o prefixo 0x04)
            public_key_raw = public_key_uncompressed[1:]
            
            # Converter para base64 URL-safe
            public_key = base64.urlsafe_b64encode(public_key_raw).decode('utf-8').rstrip('=')
            
            # Converter chave privada para DER e depois base64
            private_key_der = private_key_obj.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            private_key = base64.urlsafe_b64encode(private_key_der).decode('utf-8').rstrip('=')
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(temp_private):
                os.unlink(temp_private)
        
        # Caminho do .env
        env_path = Path('.env')
        
        # Ler .env atual
        env_lines = []
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Remover linhas antigas de VAPID se existirem
        env_lines = [line for line in env_lines if not line.strip().startswith('VAPID_')]
        
        # Adicionar novas linhas VAPID
        env_lines.append(f"\n# VAPID Keys para Push Notifications\n")
        env_lines.append(f"VAPID_PUBLIC_KEY={public_key}\n")
        env_lines.append(f"VAPID_PRIVATE_KEY={private_key}\n")
        env_lines.append(f"VAPID_EMAIL=admin@grimbots.com\n")
        
        # Escrever de volta
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        print("\n" + "="*70)
        print("✅ CHAVES VAPID CONFIGURADAS AUTOMATICAMENTE NO .env!")
        print("="*70)
        print(f"\n📊 Informações:")
        print(f"   Chave Pública: {len(public_key)} caracteres")
        print(f"   Chave Privada: {len(private_key)} caracteres")
        print(f"\n📝 Arquivo .env atualizado:")
        print(f"   {env_path.absolute()}")
        print("\n⚠️ PRÓXIMOS PASSOS:")
        print("1. Reinicie o servidor:")
        print("   systemctl restart grimbots")
        print("2. Verifique se está funcionando:")
        print("   python diagnose_push_notifications.py")
        print("="*70)
        
    except ImportError:
        print("❌ ERRO: py-vapid não instalado!")
        print("\n📦 Instale com:")
        print("   pip install py-vapid")
    except Exception as e:
        print(f"❌ Erro ao configurar chaves: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    setup_vapid_keys()

