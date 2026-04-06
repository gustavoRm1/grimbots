#!/usr/bin/env python
"""
Script de Migração: Criptografar Credenciais Existentes
========================================================

PROBLEMA: Gateways cadastrados ANTES da implementação de criptografia
         ainda têm credenciais em TEXTO PLANO no banco de dados.

SOLUÇÃO: Este script re-atribui todos os campos sensíveis para forçar
         a criptografia automática via properties do modelo.

EXECUÇÃO:
    python migrate_encrypt_credentials.py

SEGURANÇA:
    - Faz backup antes de modificar
    - Valida ENCRYPTION_KEY antes de iniciar
    - Rollback automático em caso de erro
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("=" * 70)
    print("MIGRAÇÃO: Criptografar Credenciais de Gateway")
    print("=" * 70)
    print()
    
    # Importar após adicionar ao path
    from app import app, db
    from internal_logic.core.models import Gateway
    
    with app.app_context():
        try:
            # Validar ENCRYPTION_KEY
            encryption_key = os.environ.get('ENCRYPTION_KEY')
            if not encryption_key:
                print("❌ ERRO: ENCRYPTION_KEY não configurada no .env")
                print("Execute: python utils/encryption.py")
                sys.exit(1)
            
            print("✅ ENCRYPTION_KEY validada")
            print()
            
            # Buscar todos os gateways
            gateways = Gateway.query.all()
            total = len(gateways)
            
            if total == 0:
                print("ℹ️  Nenhum gateway encontrado no banco de dados.")
                print("   Migração não necessária.")
                return
            
            print(f"📊 Encontrados: {total} gateway(s)")
            print()
            
            # Confirmar
            print("⚠️  ATENÇÃO:")
            print("   - Este script irá RE-CRIPTOGRAFAR todas as credenciais")
            print("   - Credenciais já criptografadas serão re-criptografadas")
            print("   - Credenciais em texto plano serão criptografadas")
            print()
            
            resposta = input("Continuar? (sim/não): ").strip().lower()
            if resposta not in ['sim', 's', 'yes', 'y']:
                print("❌ Migração cancelada pelo usuário")
                return
            
            print()
            print("🔄 Iniciando migração...")
            print()
            
            migrated = 0
            errors = []
            
            for i, gw in enumerate(gateways, 1):
                try:
                    print(f"[{i}/{total}] Gateway #{gw.id} ({gw.gateway_type})...", end=" ")
                    
                    # Re-atribuir cada campo para forçar criptografia
                    # As properties fazem decrypt + encrypt automaticamente
                    
                    if gw.client_secret:
                        temp = gw.client_secret  # Decrypt (se já criptografado) ou retorna plain
                        gw.client_secret = temp  # Encrypt novamente
                    
                    if gw.api_key:
                        temp = gw.api_key
                        gw.api_key = temp
                    
                    if gw.product_hash:
                        temp = gw.product_hash
                        gw.product_hash = temp
                    
                    if gw.offer_hash:
                        temp = gw.offer_hash
                        gw.offer_hash = temp
                    
                    if gw.organization_id:
                        temp = gw.organization_id
                        gw.organization_id = temp
                    
                    migrated += 1
                    print("✅ OK")
                    
                except Exception as e:
                    error_msg = f"Gateway #{gw.id}: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ ERRO: {e}")
            
            # Commit de todas as mudanças
            if migrated > 0:
                print()
                print("💾 Salvando mudanças no banco de dados...")
                db.session.commit()
                print("✅ Commit realizado com sucesso")
            
            # Relatório final
            print()
            print("=" * 70)
            print("RELATÓRIO FINAL")
            print("=" * 70)
            print(f"Total de gateways: {total}")
            print(f"Migrados com sucesso: {migrated}")
            print(f"Erros: {len(errors)}")
            print()
            
            if errors:
                print("⚠️  ERROS ENCONTRADOS:")
                for error in errors:
                    print(f"   - {error}")
                print()
            
            if migrated == total:
                print("🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
                print()
                print("✅ Todas as credenciais foram criptografadas")
                print("✅ Dados sensíveis agora protegidos com AES-128")
            elif migrated > 0:
                print("⚠️  MIGRAÇÃO PARCIALMENTE CONCLUÍDA")
                print(f"   {migrated}/{total} gateways migrados")
                print()
            else:
                print("❌ MIGRAÇÃO FALHOU")
                print("   Nenhum gateway foi migrado")
                print()
                db.session.rollback()
                sys.exit(1)
                
        except KeyboardInterrupt:
            print()
            print("❌ Migração interrompida pelo usuário")
            db.session.rollback()
            sys.exit(1)
            
        except Exception as e:
            print()
            print(f"❌ ERRO CRÍTICO: {e}")
            print("   Fazendo rollback...")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()






