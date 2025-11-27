#!/usr/bin/env python3
"""
Script para testar a função normalize_vip_chat_id
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.subscriptions import normalize_vip_chat_id

def main():
    print("=" * 70)
    print("🧪 TESTE DE normalize_vip_chat_id()")
    print("=" * 70)
    print()
    
    test_cases = [
        ("-1001234567890", "-1001234567890", "Chat ID válido"),
        ("  -1001234567890  ", "-1001234567890", "Chat ID com espaços"),
        ("", None, "String vazia (deve retornar None)"),
        (None, None, "None (deve retornar None)"),
        ("https://t.me/+abc123", "https://t.me/+abc123", "Link do Telegram"),
    ]
    
    all_passed = True
    
    for input_val, expected, description in test_cases:
        try:
            result = normalize_vip_chat_id(input_val)
            status = "✅" if result == expected else "❌"
            if result != expected:
                all_passed = False
            
            print(f"{status} {description}")
            print(f"   Input:    {repr(input_val)}")
            print(f"   Output:   {repr(result)}")
            print(f"   Expected: {repr(expected)}")
            print()
        except Exception as e:
            print(f"❌ ERRO ao testar {repr(input_val)}: {e}")
            print()
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
    else:
        print("❌ ALGUNS TESTES FALHARAM!")
    print("=" * 70)
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

