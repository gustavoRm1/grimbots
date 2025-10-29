"""
Verificar se as chaves VAPID no .env estão completas
Execute: python verify_vapid_keys.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("="*70)
print("🔍 VERIFICAÇÃO DAS CHAVES VAPID")
print("="*70)
print()

vapid_public = os.getenv('VAPID_PUBLIC_KEY', '')
vapid_private = os.getenv('VAPID_PRIVATE_KEY', '')
vapid_email = os.getenv('VAPID_EMAIL', '')

print("1️⃣ Chave Pública:")
if vapid_public:
    print(f"   ✅ Configurada")
    print(f"   📏 Tamanho: {len(vapid_public)} caracteres")
    print(f"   🔤 Primeiros 30 chars: {vapid_public[:30]}...")
    print(f"   🔤 Últimos 30 chars: ...{vapid_public[-30:]}")
    
    # Chave pública deve ter ~88 caracteres (base64 de 64 bytes)
    if len(vapid_public) < 80:
        print("   ⚠️ ATENÇÃO: Chave pública parece muito curta!")
else:
    print("   ❌ NÃO CONFIGURADA")

print()
print("2️⃣ Chave Privada:")
if vapid_private:
    print(f"   ✅ Configurada")
    print(f"   📏 Tamanho: {len(vapid_private)} caracteres")
    print(f"   🔤 Primeiros 30 chars: {vapid_private[:30]}...")
    print(f"   🔤 Últimos 30 chars: ...{vapid_private[-30:]}")
    
    # Verificar se termina com caractere estranho (pode ter sido cortada)
    if vapid_private.endswith('>') or vapid_private.endswith('...'):
        print("   ❌ ERRO: Chave privada parece estar cortada!")
        print("   ⚠️ Regere as chaves com: python generate_vapid_keys.py")
    elif len(vapid_private) < 200:
        print("   ⚠️ ATENÇÃO: Chave privada parece muito curta!")
        print("   ⚠️ Esperado: ~300+ caracteres")
        print("   ⚠️ Regere as chaves com: python generate_vapid_keys.py")
    else:
        print("   ✅ Tamanho parece correto")
else:
    print("   ❌ NÃO CONFIGURADA")

print()
print("3️⃣ Email VAPID:")
if vapid_email:
    print(f"   ✅ Configurado: {vapid_email}")
else:
    print("   ⚠️ NÃO CONFIGURADO (usando padrão: admin@grimbots.com)")

print()
print("="*70)

if vapid_public and vapid_private and len(vapid_private) > 200 and not vapid_private.endswith('>'):
    print("✅ Todas as chaves parecem estar corretas!")
    print("   Reinicie o servidor: systemctl restart grimbots")
else:
    print("❌ Há problemas com as chaves!")
    print("   Execute: python generate_vapid_keys.py")
    print("   E copie COMPLETAMENTE todas as linhas geradas")

print("="*70)

