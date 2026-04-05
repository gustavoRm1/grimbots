"""
Verificar se as chaves VAPID estão configuradas corretamente
Execute: python verify_vapid_keys.py
"""

from utils.secrets_loader import get_vapid_private_key, get_vapid_public_key
import os

print("="*70)
print("🔍 VERIFICAÇÃO DAS CHAVES VAPID")
print("="*70)
print()

# Carregar chaves usando secrets_loader (hierarquia: PATH > BASE64 > STRING)
vapid_public = get_vapid_public_key()
vapid_private = get_vapid_private_key()
vapid_email = os.getenv('VAPID_EMAIL', '')

print("1️⃣ Chave Pública:")
if vapid_public:
    print(f"   ✅ Configurada (via secrets_loader)")
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
    print(f"   ✅ Configurada (via secrets_loader)")
    print(f"   📏 Tamanho: {len(vapid_private)} caracteres")
    print(f"   🔤 Primeiros 30 chars: {vapid_private[:30]}...")
    print(f"   🔤 Últimos 30 chars: ...{vapid_private[-30:]}")
    
    # Verificar se termina com caractere estranho (pode ter sido cortada)
    if vapid_private.endswith('>') or vapid_private.endswith('...'):
        print("   ❌ ERRO: Chave privada parece estar cortada!")
        print("   ⚠️ Use: python setup_vapid_keys.py (configura automaticamente)")
    elif len(vapid_private) < 160:
        print("   ❌ ERRO: Chave privada muito curta (< 160 chars)!")
        print("   ⚠️ Esperado: 160-200 caracteres (base64 DER)")
        print("   ⚠️ Use: python setup_vapid_keys.py (configura automaticamente)")
    elif len(vapid_private) > 300:
        print("   ⚠️ ATENÇÃO: Chave privada muito longa (> 300 chars)")
        print("   ℹ️ Pode estar em formato PEM ao invés de base64")
        print("   ✅ Mas se funciona, está OK")
    else:
        print("   ✅ Tamanho parece correto (160-300 chars é normal)")
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

if vapid_public and vapid_private and len(vapid_private) >= 160 and not vapid_private.endswith('>') and not vapid_private.endswith('...'):
    print("✅ Todas as chaves parecem estar corretas!")
    print("   Reinicie o servidor: systemctl restart grimbots")
else:
    print("❌ Há problemas com as chaves!")
    print("   Use: python setup_vapid_keys.py")
    print("   (Configura automaticamente no .env, sem risco de cópia truncada)")

print("="*70)

