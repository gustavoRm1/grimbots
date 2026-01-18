#!/usr/bin/env python3
"""
TESTE DE VALIDAÇÃO DA CORREÇÃO META PIXEL

Verifica se:
1. PageView NÃO tem eventID
2. Purchase TEM eventID único
3. eventID é diferente entre PageView e Purchase
"""

import re

def test_pageview_no_eventid():
    """Verifica se PageView não tem eventID"""
    with open('templates/telegram_redirect.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Procurar por fbq('track', 'PageView') com eventID
    pageview_with_eventid = re.search(r"fbq\('track',\s*'PageView'[^)]*eventID", content, re.IGNORECASE)
    pageview_simple = re.search(r"fbq\('track',\s*'PageView'\s*\);", content)
    
    print("🔍 TESTE 1: PageView SEM eventID")
    print(f"   ❌ PageView com eventID encontrado: {bool(pageview_with_eventid)}")
    print(f"   ✅ PageView simples encontrado: {bool(pageview_simple)}")
    
    if pageview_with_eventid:
        print("   🚨 ERRO: PageView ainda tem eventID!")
        return False
    elif pageview_simple:
        print("   ✅ SUCESSO: PageView sem eventID")
        return True
    else:
        print("   ⚠️ AVISO: PageView não encontrado")
        return False

def test_purchase_with_eventid():
    """Verifica se Purchase TEM eventID"""
    with open('templates/delivery.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Procurar por fbq('track', 'Purchase') com eventID
    purchase_with_eventid = re.search(r"fbq\('track',\s*'Purchase'[^}]*eventID\s*:\s*EVENT_ID", content, re.IGNORECASE)
    purchase_simple = re.search(r"fbq\('track',\s*'Purchase'\s*\);", content)
    
    print("\n🔍 TESTE 2: Purchase COM eventID")
    print(f"   ✅ Purchase com eventID encontrado: {bool(purchase_with_eventid)}")
    print(f"   ❌ Purchase simples encontrado: {bool(purchase_simple)}")
    
    if purchase_with_eventid and not purchase_simple:
        print("   ✅ SUCESSO: Purchase com eventID correto")
        return True
    elif purchase_simple:
        print("   🚨 ERRO: Purchase sem eventID!")
        return False
    else:
        print("   ⚠️ AVISO: Purchase não encontrado")
        return False

def test_eventid_unique():
    """Verifica se eventID é único por pagamento"""
    with open('templates/delivery.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Procurar por EVENT_ID dinâmico
    dynamic_eventid = re.search(r"const EVENT_ID = \"\{\{\s*pixel_config\.event_id\s*\}\}\"", content)
    fixed_eventid = re.search(r"eventID\s*:\s*['\"]purchase_[\d]+['\"]", content)
    
    print("\n🔍 TESTE 3: eventID ÚNICO por pagamento")
    print(f"   ✅ EVENT_ID dinâmico encontrado: {bool(dynamic_eventid)}")
    print(f"   ❌ EVENT_ID fixo encontrado: {bool(fixed_eventid)}")
    
    if dynamic_eventid and not fixed_eventid:
        print("   ✅ SUCESSO: eventID é dinâmico (único por pagamento)")
        return True
    elif fixed_eventid:
        print("   🚨 ERRO: eventID está fixo!")
        return False
    else:
        print("   ⚠️ AVISO: eventID não encontrado")
        return False

def test_no_pageview_eventid_in_backend():
    """Verifica se backend não passa pageview_event_id para template"""
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Procurar por pageview_event_id no render_template
    pageview_in_template = re.search(r"pageview_event_id\s*=", content)
    
    print("\n🔍 TESTE 4: Backend não passa pageview_event_id")
    print(f"   ❌ pageview_event_id no render_template: {bool(pageview_in_template)}")
    
    if not pageview_in_template:
        print("   ✅ SUCESSO: Backend não passa pageview_event_id")
        return True
    else:
        print("   🚨 ERRO: Backend ainda passa pageview_event_id!")
        return False

def main():
    print("🧪 TESTE DE VALIDAÇÃO - CORREÇÃO META PIXEL")
    print("=" * 50)
    
    tests = [
        test_pageview_no_eventid(),
        test_purchase_with_eventid(),
        test_eventid_unique(),
        test_no_pageview_eventid_in_backend()
    ]
    
    print("\n📊 RESUMO")
    print(f"   ✅ Testes passados: {sum(tests)}/{len(tests)}")
    
    if all(tests):
        print("   🎉 TODOS OS TESTES PASSARAM!")
        print("   📋 PRÓXIMOS PASSOS:")
        print("      1. Fazer um teste real")
        print("      2. Verificar Network: tr?ev=Purchase")
        print("      3. Confirmar Events Manager: 'Received'")
    else:
        print("   🚨 ALGUNS TESTES FALHARAM!")
        print("   📋 REVISAR OS ERROS ACIMA")
    
    return all(tests)

if __name__ == "__main__":
    main()
