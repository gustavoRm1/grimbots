#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 TESTE DIRETO: Meta Pixel Purchase Event
Testa envio direto à Meta API para verificar se funciona
"""

import os
import sys
import time
import requests

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    from models import Payment, PoolBot, RedirectPool
    from utils.encryption import decrypt
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    sys.exit(1)

print("=" * 80)
print("🧪 TESTE DIRETO: Meta Pixel Purchase Event")
print("=" * 80)

with app.app_context():
    # Buscar pool ativo com Meta Pixel configurado
    pool = RedirectPool.query.filter_by(
        is_active=True,
        meta_tracking_enabled=True,
        meta_events_purchase=True
    ).first()
    
    if not pool:
        print("\n❌ Nenhum pool ativo com Meta Pixel configurado encontrado!")
        sys.exit(1)
    
    print(f"\n✅ Pool encontrado: {pool.name} (ID: {pool.id})")
    print(f"   Pixel ID: {pool.meta_pixel_id}")
    print(f"   Purchase Event: Habilitado")
    
    # Descriptografar access token
    try:
        access_token = decrypt(pool.meta_access_token)
        print(f"   Access Token: ✅ Configurado (descriptografado)")
    except Exception as e:
        print(f"   ❌ Erro ao descriptografar Access Token: {e}")
        sys.exit(1)
    
    # Validar token
    print("\n🔍 Validando Access Token...")
    try:
        url = f"https://graph.facebook.com/v18.0/debug_token"
        params = {
            'input_token': access_token,
            'access_token': access_token
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token_data = data.get('data', {})
            is_valid = token_data.get('is_valid', False)
            
            if is_valid:
                print("   ✅ Access Token: VÁLIDO")
                print(f"      App ID: {token_data.get('app_id', 'N/A')}")
                print(f"      Type: {token_data.get('type', 'N/A')}")
            else:
                print(f"   ❌ Access Token: INVÁLIDO!")
                print(f"      Erro: {token_data.get('error', 'Unknown')}")
                sys.exit(1)
        else:
            print(f"   ❌ Erro ao validar token: HTTP {response.status_code}")
            print(f"      Response: {response.text[:200]}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Erro ao validar token: {e}")
        sys.exit(1)
    
    # Testar envio direto de evento Purchase
    print("\n📤 Testando envio direto de evento Purchase para Meta API...")
    
    event_data = {
        'event_name': 'Purchase',
        'event_time': int(time.time()),
        'event_id': f'test_direct_{int(time.time())}',
        'action_source': 'website',
        'user_data': {
            'external_id': f'test_user_{int(time.time())}'
        },
        'custom_data': {
            'currency': 'BRL',
            'value': 10.00
        }
    }
    
    url = f'https://graph.facebook.com/v18.0/{pool.meta_pixel_id}/events'
    payload = {
        'data': [event_data],
        'access_token': access_token
    }
    
    if pool.meta_test_event_code:
        payload['test_event_code'] = pool.meta_test_event_code
        print(f"   ⚠️ Usando Test Event Code: {pool.meta_test_event_code}")
    
    try:
        print(f"   URL: {url}")
        print(f"   Event ID: {event_data['event_id']}")
        print(f"   Enviando...")
        
        response = requests.post(url, json=payload, timeout=10)
        
        print(f"\n📊 RESPOSTA DA META API:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            events_received = result.get('events_received', 0)
            fbtrace_id = result.get('fbtrace_id', 'N/A')
            
            print(f"   ✅ SUCESSO!")
            print(f"      Events Received: {events_received}")
            print(f"      FBTrace ID: {fbtrace_id}")
            
            if events_received > 0:
                print("\n✅ TESTE PASSOU: Meta API aceitou o evento!")
                print("💡 Se os eventos não estão aparecendo no Gerenciador, verifique:")
                print("   1. Se está usando Test Event Code (eventos de teste não aparecem)")
                print("   2. Se há delay na Meta (pode levar alguns minutos)")
                print("   3. Se o pixel está configurado corretamente no Gerenciador")
            else:
                print("\n⚠️ ATENÇÃO: Meta API retornou sucesso mas events_received = 0")
                print("   Isso pode indicar problema com os dados do evento")
        else:
            print(f"   ❌ ERRO!")
            print(f"      Response: {response.text[:500]}")
            
            # Tentar parsear JSON se possível
            try:
                error_data = response.json()
                print(f"      Erro JSON: {error_data}")
            except:
                pass
                
    except Exception as e:
        print(f"   ❌ ERRO ao enviar: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

