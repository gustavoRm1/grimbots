#!/usr/bin/env python3
"""
Script para atualizar VAPID keys no .env a partir dos arquivos .pem gerados
Execute: python3 update_vapid_from_files.py
"""

import os
import re
from pathlib import Path

def read_pem_file(filepath):
    """Lê conteúdo de arquivo PEM"""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
        return content
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {filepath}")
        return None
    except Exception as e:
        print(f"❌ Erro ao ler arquivo {filepath}: {e}")
        return None

def update_env_file(public_key_value, private_key_pem):
    """Atualiza arquivo .env com novas chaves VAPID"""
    env_path = Path('.env')
    
    # Ler .env atual
    env_lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
    
    # Remover linhas antigas de VAPID
    new_lines = []
    skip_until_newline = False
    for line in env_lines:
        if line.strip().startswith('VAPID_'):
            skip_until_newline = True
            continue
        if skip_until_newline and line.strip() == '':
            skip_until_newline = False
        if not skip_until_newline:
            new_lines.append(line)
    
    # Adicionar novas chaves VAPID
    # Remover quebras de linha do PEM para armazenar em uma linha
    private_key_one_line = private_key_pem.replace('\n', '\\n')
    
    new_lines.append("\n# VAPID Keys para Push Notifications\n")
    new_lines.append(f"VAPID_PUBLIC_KEY={public_key_value}\n")
    new_lines.append(f"VAPID_PRIVATE_KEY={private_key_one_line}\n")
    new_lines.append(f"VAPID_EMAIL=admin@grimbots.com\n")
    
    # Escrever de volta
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ Arquivo .env atualizado: {env_path.absolute()}")

def main():
    print("="*70)
    print("🔑 ATUALIZANDO CHAVES VAPID NO .env")
    print("="*70)
    print()
    
    # Ler arquivos PEM
    private_key_pem = read_pem_file('private_key.pem')
    if not private_key_pem:
        print("❌ Não foi possível ler private_key.pem")
        return
    
    # Para a chave pública, usar a Application Server Key gerada
    # OU ler do arquivo public_key.pem se preferir
    public_key_value = input("📋 Cole a Application Server Key gerada (ou Enter para ler do public_key.pem): ").strip()
    
    if not public_key_value:
        # Tentar ler do arquivo
        public_key_pem_content = read_pem_file('public_key.pem')
        if public_key_pem_content:
            # Extrair chave pública do formato PEM (se necessário)
            # py_vapid pode gerar em formato diferente, então vamos usar a Application Server Key
            print("⚠️ É recomendado usar a Application Server Key gerada pelo py_vapid")
            public_key_value = input("📋 Cole a Application Server Key: ").strip()
    
    if not public_key_value:
        print("❌ Application Server Key é obrigatória")
        return
    
    # Validar que chave privada parece ser PEM válida
    if not private_key_pem.startswith('-----BEGIN'):
        print("⚠️ Aviso: private_key.pem não parece estar em formato PEM")
        print("   Continuando mesmo assim...")
    
    # Atualizar .env
    update_env_file(public_key_value, private_key_pem)
    
    print("\n" + "="*70)
    print("✅ CONFIGURAÇÃO CONCLUÍDA!")
    print("="*70)
    print("\n📝 Próximos passos:")
    print("1. Verificar se as chaves foram salvas corretamente:")
    print("   cat .env | grep VAPID")
    print("\n2. Reiniciar o servidor:")
    print("   systemctl restart grimbots")
    print("   # OU se estiver rodando manualmente:")
    print("   # Ctrl+C e depois iniciar novamente")
    print("\n3. Verificar logs para confirmar que não há mais erros:")
    print("   tail -f logs/app.log | grep -i vapid")
    print("\n" + "="*70)

if __name__ == '__main__':
    main()
