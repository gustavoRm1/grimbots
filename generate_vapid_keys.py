"""
Gerar VAPID Keys para Push Notifications
Execute: python generate_vapid_keys.py
"""

try:
    from py_vapid import Vapid01
    import base64
    import tempfile
    import os
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    print("🔑 Gerando chaves VAPID...")
    vapid = Vapid01()
    vapid.generate_keys()
    
    # Salvar chave privada em arquivo temporário
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as f:
        temp_private = f.name
    
    try:
        # Salvar chave privada (formato PEM)
        vapid.save_key(temp_private)
        
        # Ler chave privada do arquivo (formato PEM completo)
        with open(temp_private, 'r') as f:
            private_key_pem = f.read().strip()
        
        # Carregar para extrair chave pública
        private_key_obj = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # Obter chave pública
        public_key_obj = private_key_obj.public_key()
        
        # ✅ CORRIGIDO: Web Push API precisa de 65 bytes (com prefixo 0x04)
        # Formato: uncompressed point = 1 byte (0x04) + 32 bytes (X) + 32 bytes (Y)
        public_key_uncompressed = public_key_obj.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # ✅ IMPORTANTE: A Web Push API espera os 65 bytes COMPLETOS (com prefixo 0x04)
        # Não remover o primeiro byte!
        public_key_raw = public_key_uncompressed  # 65 bytes: 0x04 + 32 bytes X + 32 bytes Y
        
        # Converter para base64 URL-safe (formato usado pela Web Push API)
        public_key = base64.urlsafe_b64encode(public_key_raw).decode('utf-8').rstrip('=')
        
        # Validar tamanho
        if len(public_key_raw) != 65:
            raise ValueError(f"Chave pública deve ter 65 bytes, mas tem {len(public_key_raw)} bytes")
        
        # ✅ MÉTODO ALTERNATIVO: Usar formato PEM diretamente para privada
        # pywebpush aceita PEM ou pode extrair automaticamente
        # Mas vamos usar base64 do PEM para facilitar armazenamento no .env
        # Converter PEM para uma linha (remover quebras)
        private_key_pem_one_line = private_key_pem.replace('\n', '\\n')
        
        # Ou converter DER para base64 (mais compacto)
        private_key_der = private_key_obj.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        private_key_base64 = base64.urlsafe_b64encode(private_key_der).decode('utf-8').rstrip('=')
        
        # Usar o formato base64 (mais fácil de armazenar no .env)
        private_key = private_key_base64
        
    finally:
        # Limpar arquivo temporário
        if os.path.exists(temp_private):
            os.unlink(temp_private)
    
    print("\n" + "="*70)
    print("✅ CHAVES GERADAS COM SUCESSO!")
    print("="*70)
    print(f"\n📊 Informações:")
    print(f"   Chave Pública: {len(public_key)} caracteres")
    print(f"   Chave Privada: {len(private_key)} caracteres")
    print("\n📋 Adicione estas linhas ao seu arquivo .env:\n")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print(f"VAPID_EMAIL=admin@grimbots.com")
    print("\n" + "="*70)
    print("⚠️ IMPORTANTE:")
    print("1. Copie TODAS as 3 linhas acima (sem quebrar as linhas!)")
    print("2. No nano, cole tudo de uma vez (Ctrl+Shift+V)")
    print("3. Certifique-se de que VAPID_PRIVATE_KEY está em UMA linha só")
    print("4. Adicione ao arquivo .env:")
    print("   nano .env")
    print("5. Reinicie o servidor:")
    print("   systemctl restart grimbots")
    print("6. Verifique:")
    print("   python diagnose_push_notifications.py")
    print("="*70)
    
except ImportError:
    print("❌ ERRO: py-vapid não instalado!")
    print("\n📦 Instale com:")
    print("   pip install py-vapid")
except Exception as e:
    print(f"❌ Erro ao gerar chaves: {e}")
    import traceback
    traceback.print_exc()
