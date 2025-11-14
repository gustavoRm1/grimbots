#!/usr/bin/env python3
"""
Script para buscar logs do Meta Pixel
Funciona com arquivos de log ou journalctl
"""

import os
import subprocess
import sys
from pathlib import Path

def buscar_logs_meta():
    """Busca logs do Meta Pixel"""
    
    print("=" * 80)
    print("🔍 BUSCANDO LOGS DO META PIXEL")
    print("=" * 80)
    print()
    
    # Tentar arquivos de log primeiro
    log_files = []
    if Path('logs').exists():
        log_files.extend(Path('logs').glob('*.log'))
    if Path('.').exists():
        log_files.extend(Path('.').glob('*.log'))
    
    encontrados = False
    
    if log_files:
        print(f"✅ Encontrados {len(log_files)} arquivo(s) de log")
        print()
        
        for log_file in log_files[:3]:  # Limitar a 3 arquivos
            print(f"📄 Analisando: {log_file}")
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                    # Buscar linhas META
                    redirect_lines = [l.strip() for l in lines if 'META REDIRECT' in l or '[META REDIRECT]' in l]
                    purchase_lines = [l.strip() for l in lines if 'META PURCHASE' in l or '[META PURCHASE]' in l]
                    fbc_synthetic = [l.strip() for l in lines if 'fbc.*gerado' in l.lower() or 'fbc sintético' in l.lower() or 'fbc gerado do fbclid' in l.lower()]
                    
                    if redirect_lines:
                        print(f"   ✅ {len(redirect_lines)} redirects encontrados")
                        print(f"   Últimos 3:")
                        for line in redirect_lines[-3:]:
                            print(f"      {line[:150]}")
                        encontrados = True
                    
                    if purchase_lines:
                        print(f"   ✅ {len(purchase_lines)} purchases encontrados")
                        print(f"   Últimos 3:")
                        for line in purchase_lines[-3:]:
                            print(f"      {line[:150]}")
                        encontrados = True
                    
                    if fbc_synthetic:
                        print(f"   ❌ {len(fbc_synthetic)} fbc sintéticos encontrados (ERRO!)")
                        for line in fbc_synthetic[-3:]:
                            print(f"      {line[:150]}")
                    else:
                        print(f"   ✅ Nenhum fbc sintético encontrado (CORRETO!)")
                    
                    if not redirect_lines and not purchase_lines:
                        print(f"   ⚠️  Nenhuma linha META encontrada")
                    
                    print()
            except Exception as e:
                print(f"   ❌ Erro ao ler: {e}")
                print()
    
    # Se não encontrou em arquivos, tentar journalctl
    if not encontrados:
        print("📋 Tentando journalctl (systemd)...")
        print()
        
        try:
            result = subprocess.run(
                ['journalctl', '-u', 'grimbots', '-n', '500', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                
                redirect_lines = [l for l in lines if 'META REDIRECT' in l or '[META REDIRECT]' in l]
                purchase_lines = [l for l in lines if 'META PURCHASE' in l or '[META PURCHASE]' in l]
                fbc_synthetic = [l for l in lines if 'fbc.*gerado' in l.lower() or 'fbc sintético' in l.lower() or 'fbc gerado do fbclid' in l.lower()]
                
                if redirect_lines:
                    print(f"✅ {len(redirect_lines)} redirects encontrados no journalctl")
                    print(f"Últimos 3:")
                    for line in redirect_lines[-3:]:
                        print(f"   {line[:200]}")
                    encontrados = True
                    print()
                
                if purchase_lines:
                    print(f"✅ {len(purchase_lines)} purchases encontrados no journalctl")
                    print(f"Últimos 3:")
                    for line in purchase_lines[-3:]:
                        print(f"   {line[:200]}")
                    encontrados = True
                    print()
                
                if fbc_synthetic:
                    print(f"❌ {len(fbc_synthetic)} fbc sintéticos encontrados (ERRO!)")
                    for line in fbc_synthetic[-3:]:
                        print(f"   {line[:200]}")
                else:
                    print(f"✅ Nenhum fbc sintético encontrado (CORRETO!)")
                
                if not redirect_lines and not purchase_lines:
                    print("⚠️  Nenhuma linha META encontrada no journalctl")
            else:
                print(f"❌ Erro ao executar journalctl: {result.stderr}")
        except FileNotFoundError:
            print("⚠️  journalctl não encontrado (não é systemd?)")
        except subprocess.TimeoutExpired:
            print("⚠️  journalctl demorou muito (timeout)")
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    print()
    print("=" * 80)
    
    if not encontrados:
        print("⚠️  Nenhum log META encontrado")
        print()
        print("Possíveis causas:")
        print("   1. Nenhuma venda foi feita ainda")
        print("   2. Logs estão em outro local")
        print("   3. Aplicação não está gerando logs")
        print()
        print("Tente:")
        print("   - Fazer uma nova venda")
        print("   - Verificar se Gunicorn está rodando: ps aux | grep gunicorn")
        print("   - Verificar logs do systemd: sudo journalctl -u grimbots -n 50")
    
    return 0

if __name__ == '__main__':
    exit(buscar_logs_meta())

