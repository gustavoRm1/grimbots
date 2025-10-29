"""
Gerar VAPID Keys para Push Notifications
Execute: python generate_vapid_keys.py
"""

try:
    from py_vapid import Vapid01
    
    print("🔑 Gerando chaves VAPID...")
    vapid = Vapid01()
    vapid.generate_keys()
    
    public_key = vapid.public_key.public_bytes_raw().hex()
    private_key = vapid.private_key.private_bytes_raw().hex()
    
    print("\n" + "="*70)
    print("✅ CHAVES GERADAS COM SUCESSO!")
    print("="*70)
    print("\n📋 Adicione estas linhas ao seu arquivo .env:\n")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print(f"VAPID_EMAIL=admin@grimbots.com")
    print("\n" + "="*70)
    print("⚠️ IMPORTANTE:")
    print("1. Copie as linhas acima")
    print("2. Adicione ao arquivo .env na raiz do projeto")
    print("3. Reinicie o servidor (systemctl restart grimbots)")
    print("="*70)
    
except ImportError:
    print("❌ ERRO: py-vapid não instalado!")
    print("\n📦 Instale com:")
    print("   pip install py-vapid")
except Exception as e:
    print(f"❌ Erro ao gerar chaves: {e}")

