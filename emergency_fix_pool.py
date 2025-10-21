#!/usr/bin/env python3
"""
FIX EMERGENCIAL DE POOL
=======================
Quando um pool está bloqueando tudo e você precisa RESOLVER JÁ

USO:
----
python emergency_fix_pool.py ads01

AÇÕES:
------
1. Mostra config atual
2. Pergunta se quer desabilitar cloaker
3. Ou reconfigurar parâmetros
4. Restart automático
5. Teste do link
"""

import sys
import subprocess
from app import app, db
from models import RedirectPool
import requests

def fix_pool(slug):
    with app.app_context():
        pool = RedirectPool.query.filter_by(slug=slug).first()
        
        if not pool:
            print(f"❌ Pool '{slug}' não encontrado")
            sys.exit(1)
        
        print("=" * 80)
        print(f"🔧 POOL: {pool.name}")
        print("=" * 80)
        print()
        print(f"Slug: {pool.slug}")
        print(f"Cloaker: {'✅ Ativo' if pool.meta_cloaker_enabled else '❌ Inativo'}")
        print(f"Parâmetro: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        print()
        
        print("=" * 80)
        print("AÇÕES:")
        print("=" * 80)
        print("1. Desabilitar cloaker (EMERGÊNCIA)")
        print("2. Reconfigurar parâmetros")
        print("3. Apenas restart")
        print("4. Cancelar")
        print()
        
        choice = input("Escolha (1-4): ").strip()
        
        if choice == '1':
            # Desabilitar
            pool.meta_cloaker_enabled = False
            db.session.commit()
            print("\n✅ Cloaker DESABILITADO")
            print("⚠️  TODOS os links vão funcionar agora (sem proteção)")
            
        elif choice == '2':
            # Reconfigurar
            print("\nReconfigurar parâmetros:")
            param_name = input(f"Nome [{pool.meta_cloaker_param_name}]: ").strip() or pool.meta_cloaker_param_name
            param_value = input(f"Valor [{pool.meta_cloaker_param_value}]: ").strip() or pool.meta_cloaker_param_value
            
            pool.meta_cloaker_param_name = param_name
            pool.meta_cloaker_param_value = param_value
            db.session.commit()
            
            print(f"\n✅ Reconfigurado: {param_name}={param_value}")
            
        elif choice == '3':
            print("\n⏭️  Apenas restart (sem mudanças)")
            
        else:
            print("\n❌ Cancelado")
            sys.exit(0)
        
        # Restart
        print("\n🔄 Reiniciando servidor...")
        subprocess.run(['pkill', '-9', 'gunicorn'])
        subprocess.run(['pkill', '-9', 'python'])
        
        import time
        time.sleep(2)
        
        subprocess.Popen(
            ['nohup', 'gunicorn', '-c', 'gunicorn_config.py', 'wsgi:app'],
            stdout=open('/var/log/gunicorn.log', 'a'),
            stderr=subprocess.STDOUT,
            cwd='/root/grimbots'
        )
        
        print("✅ Servidor reiniciado")
        
        # Teste
        print("\n🧪 Testando link...")
        time.sleep(3)
        
        test_url = f"https://app.grimbots.online/go/{pool.slug}"
        if pool.meta_cloaker_enabled:
            test_url += f"?{pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}"
        
        print(f"   URL: {test_url}")
        
        try:
            response = requests.get(test_url, allow_redirects=False, timeout=5)
            
            if response.status_code == 302:
                print(f"   ✅ FUNCIONANDO (redirect para bot)")
                print(f"   Location: {response.headers.get('Location')}")
            elif response.status_code == 403:
                print(f"   ❌ BLOQUEADO (cloaker ativo)")
            else:
                print(f"   ⚠️  Status: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro no teste: {e}")
        
        print("\n" + "=" * 80)
        print("✅ PROCESSO CONCLUÍDO")
        print("=" * 80)
        print()
        print("📊 Monitorar:")
        print("   tail -f /var/log/gunicorn.log | grep -E 'ads01|BLOCK|Redirect'")
        print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("USO: python emergency_fix_pool.py <slug>")
        print("Exemplo: python emergency_fix_pool.py ads01")
        sys.exit(1)
    
    fix_pool(sys.argv[1])

