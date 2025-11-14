#!/usr/bin/env python3
"""
Script de Limpeza - Remover fbc Sintético do Redis

✅ OBJETIVO:
- Identificar e remover/zerar todos os fbc sintéticos do Redis
- fbc sintético = fbc gerado pelo servidor (timestamp recente)
- fbc real = fbc do cookie do navegador (timestamp antigo, do clique original)

✅ CRITÉRIO DE IDENTIFICAÇÃO:
- fbc sintético: timestamp dentro de 1 hora do momento atual
- fbc real: timestamp de dias/semanas atrás (geralmente < timestamp atual - 86400)
"""

import sys
import os
import json
import time
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}")

from redis_manager import get_redis_connection

def extract_timestamp_from_fbc(fbc_value):
    """
    Extrai timestamp do fbc no formato: fb.1.<timestamp>.<payload>
    Retorna None se não conseguir extrair
    """
    if not fbc_value or not isinstance(fbc_value, str):
        return None
    
    # Formato: fb.1.<timestamp>.<payload>
    match = re.match(r'^fb\.1\.(\d+)\.', fbc_value)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, AttributeError):
            return None
    return None

def is_synthetic_fbc(fbc_value, current_timestamp=None):
    """
    Determina se fbc é sintético baseado no timestamp
    
    fbc sintético: timestamp dentro de 1 hora do momento atual
    fbc real: timestamp de dias/semanas atrás
    """
    if not fbc_value:
        return False
    
    timestamp = extract_timestamp_from_fbc(fbc_value)
    if not timestamp:
        return False  # Não conseguiu extrair timestamp, assumir que não é sintético
    
    current_timestamp = current_timestamp or int(time.time())
    
    # ✅ fbc sintético: timestamp dentro de 1 hora (3600 segundos)
    # fbc real geralmente tem timestamp de dias/semanas atrás
    time_diff = current_timestamp - timestamp
    
    # Se timestamp está no futuro ou muito recente (< 1 hora), é sintético
    if time_diff < 3600:
        return True
    
    return False

def cleanup_redis_synthetic_fbc():
    """Limpa todos os fbc sintéticos do Redis"""
    
    print("=" * 80)
    print("🧹 LIMPEZA DE FBC SINTÉTICO DO REDIS")
    print("=" * 80)
    print()
    
    try:
        redis_conn = get_redis_connection()
        current_timestamp = int(time.time())
        
        # ✅ Buscar todas as chaves de tracking
        tracking_keys = []
        
        # Padrões de chaves de tracking
        patterns = [
            'tracking:*',  # tracking:{token}
            'tracking:fbclid:*',  # tracking:fbclid:{fbclid}
            'tracking:chat:*',  # tracking:chat:{user_id}
            'tracking:payment:*',  # tracking:payment:{payment_id}
            'tracking:last_token:user:*',  # tracking:last_token:user:{user_id}
        ]
        
        print("1️⃣ Buscando chaves de tracking no Redis...")
        for pattern in patterns:
            keys = list(redis_conn.scan_iter(match=pattern, count=1000))
            tracking_keys.extend(keys)
            print(f"   Padrão '{pattern}': {len(keys)} chaves encontradas")
        
        print(f"   Total de chaves encontradas: {len(tracking_keys)}")
        print()
        
        # ✅ Analisar cada chave
        synthetic_count = 0
        real_count = 0
        cleaned_count = 0
        
        print("2️⃣ Analisando fbc em cada chave...")
        
        for key in tracking_keys:
            try:
                value = redis_conn.get(key)
                if not value:
                    continue
                
                try:
                    data = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Não é JSON, pular
                    continue
                
                if not isinstance(data, dict):
                    continue
                
                fbc_value = data.get('fbc')
                if not fbc_value:
                    continue
                
                # ✅ Verificar se é sintético
                if is_synthetic_fbc(fbc_value, current_timestamp):
                    synthetic_count += 1
                    fbc_origin = data.get('fbc_origin', 'unknown')
                    
                    # ✅ Remover fbc sintético
                    data['fbc'] = None
                    data['fbc_origin'] = None
                    
                    # ✅ Salvar de volta no Redis
                    ttl = redis_conn.ttl(key)
                    if ttl > 0:
                        redis_conn.setex(key, ttl, json.dumps(data, ensure_ascii=False))
                    else:
                        redis_conn.set(key, json.dumps(data, ensure_ascii=False))
                    
                    cleaned_count += 1
                    print(f"   ✅ Limpo: {key[:50]}... (fbc_origin: {fbc_origin})")
                else:
                    real_count += 1
                    # ✅ Marcar como 'cookie' se não tiver fbc_origin
                    if not data.get('fbc_origin'):
                        data['fbc_origin'] = 'cookie'  # Assumir que fbc real veio de cookie
                        ttl = redis_conn.ttl(key)
                        if ttl > 0:
                            redis_conn.setex(key, ttl, json.dumps(data, ensure_ascii=False))
                        else:
                            redis_conn.set(key, json.dumps(data, ensure_ascii=False))
            
            except Exception as e:
                print(f"   ⚠️  Erro ao processar chave {key[:50]}...: {e}")
                continue
        
        print()
        print("=" * 80)
        print("📊 RESUMO DA LIMPEZA")
        print("=" * 80)
        print(f"   Total de chaves analisadas: {len(tracking_keys)}")
        print(f"   fbc REAL encontrados: {real_count}")
        print(f"   fbc SINTÉTICO encontrados: {synthetic_count}")
        print(f"   fbc sintético LIMPOS: {cleaned_count}")
        print()
        
        if cleaned_count > 0:
            print("✅ Limpeza concluída com sucesso!")
            print("   Todos os fbc sintéticos foram removidos do Redis")
        else:
            print("ℹ️  Nenhum fbc sintético encontrado (sistema já está limpo)")
        
        print()
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(cleanup_redis_synthetic_fbc())

