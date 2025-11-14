#!/usr/bin/env python3
"""
Script de diagnóstico para ENCRYPTION_KEY
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Adicionar diretório raiz ao sys.path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

load_dotenv()

print("=" * 80)
print("  DIAGNÓSTICO - ENCRYPTION_KEY")
print("=" * 80)
print()

# Verificar se está no ambiente
env_key = os.environ.get('ENCRYPTION_KEY')
print(f"1. ENCRYPTION_KEY no ambiente: {'✅ SIM' if env_key else '❌ NÃO'}")
if env_key:
    print(f"   Tamanho: {len(env_key)} chars")
    print(f"   Primeiros 20 chars: {env_key[:20]}...")
    print(f"   Últimos 5 chars: ...{env_key[-5:]}")
    print(f"   Representação repr: {repr(env_key)}")
print()

# Verificar no .env
env_path = project_root / '.env'
print(f"2. Arquivo .env existe: {'✅ SIM' if env_path.exists() else '❌ NÃO'}")
if env_path.exists():
    print(f"   Caminho: {env_path}")
    print()
    
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        encryption_line = None
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('ENCRYPTION_KEY='):
                encryption_line = (i, line)
                break
        
        if encryption_line:
            line_num, line_content = encryption_line
            print(f"   ✅ Linha encontrada na linha {line_num}")
            print(f"   Conteúdo bruto: {repr(line_content)}")
            print()
            
            # Extrair chave
            key = line_content.split('=', 1)[1].strip()
            print(f"   Chave extraída (após split): {repr(key)}")
            print(f"   Tamanho: {len(key)} chars")
            
            # Remover aspas
            key_clean = key.strip('"').strip("'")
            print(f"   Chave limpa (sem aspas): {repr(key_clean)}")
            print(f"   Tamanho limpo: {len(key_clean)} chars")
            print()
            
            # Validar formato
            try:
                from cryptography.fernet import Fernet
                print("3. Validando formato da chave...")
                print(f"   Tentando criar objeto Fernet...")
                
                # Tentar com a chave limpa
                fernet_obj = Fernet(key_clean.encode('utf-8'))
                print(f"   ✅ Chave VÁLIDA!")
                print(f"   Objeto Fernet criado com sucesso")
                
                # Testar encriptar/desencriptar
                test_data = b"test"
                encrypted = fernet_obj.encrypt(test_data)
                decrypted = fernet_obj.decrypt(encrypted)
                if decrypted == test_data:
                    print(f"   ✅ Teste de encriptação/desencriptação: SUCESSO")
                else:
                    print(f"   ⚠️  Teste de encriptação/desencriptação: FALHOU")
                
            except Exception as e:
                print(f"   ❌ Chave INVÁLIDA!")
                print(f"   Erro: {e}")
                print(f"   Tipo do erro: {type(e).__name__}")
                
                # Tentar diagnosticar o problema
                print()
                print("   🔍 Diagnóstico detalhado:")
                print(f"   - Tamanho da chave: {len(key_clean)} chars")
                print(f"   - Esperado: 44 chars (32 bytes em base64)")
                
                if len(key_clean) != 44:
                    print(f"   - ⚠️  Tamanho incorreto!")
                
                # Verificar caracteres válidos
                valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=')
                invalid_chars = set(key_clean) - valid_chars
                if invalid_chars:
                    print(f"   - ⚠️  Caracteres inválidos encontrados: {invalid_chars}")
                
                # Verificar se termina com =
                if not key_clean.endswith('='):
                    print(f"   - ⚠️  Chave não termina com '='")
                
        else:
            print(f"   ❌ Linha ENCRYPTION_KEY não encontrada no .env")
else:
    print(f"   ❌ Arquivo .env não encontrado em: {env_path}")

print()
print("=" * 80)
print("  RECOMENDAÇÕES")
print("=" * 80)
print()

if not env_key:
    print("1. A ENCRYPTION_KEY não está no ambiente")
    print("   Solução: O script deve carregar automaticamente do .env")
    print()

if env_path.exists():
    print("2. Verificar manualmente o .env:")
    print(f"   cat {env_path} | grep ENCRYPTION_KEY")
    print()
    print("3. Se a chave estiver corrompida, gerar nova:")
    print('   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    print()
    print("4. Depois, atualizar o .env:")
    print("   nano .env")
    print("   # Editar a linha ENCRYPTION_KEY=...")
    print()

print("=" * 80)

