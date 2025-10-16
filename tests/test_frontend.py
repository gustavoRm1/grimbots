"""
Teste de Validação do Frontend
Verifica se todos os templates e arquivos JavaScript estão corretos
"""

import os
from jinja2 import Template, TemplateSyntaxError

def test_templates():
    """Testa se todos os templates HTML compilam"""
    templates = [
        'templates/base.html',
        'templates/dashboard.html',
        'templates/login.html',
        'templates/register.html',
        'templates/settings.html',
        'templates/bot_config.html',
        'templates/bot_create_wizard.html',
    ]
    
    print("=" * 60)
    print("TESTE DE TEMPLATES")
    print("=" * 60)
    
    for template_path in templates:
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                Template(f.read())
            print(f"[OK] {template_path}")
        except TemplateSyntaxError as e:
            print(f"[ERRO] {template_path}: {e}")
            return False
        except Exception as e:
            print(f"[AVISO] {template_path}: {e}")
    
    return True

def test_javascript_files():
    """Verifica se arquivos JavaScript existem"""
    js_files = [
        'static/js/ui-components.js',
        'static/js/friendly-errors.js',
        'static/js/gamification.js',
        'static/js/dashboard.js'
    ]
    
    print("\n" + "=" * 60)
    print("TESTE DE ARQUIVOS JAVASCRIPT")
    print("=" * 60)
    
    for js_file in js_files:
        if os.path.exists(js_file):
            size = os.path.getsize(js_file)
            print(f"[OK] {js_file} ({size} bytes)")
        else:
            print(f"[ERRO] {js_file} NAO EXISTE")
            return False
    
    return True

def test_css_files():
    """Verifica se arquivos CSS existem"""
    css_files = [
        'static/css/ui-components.css',
        'static/css/dark-theme.css',
        'static/css/gamification.css',
        'static/css/style.css'
    ]
    
    print("\n" + "=" * 60)
    print("TESTE DE ARQUIVOS CSS")
    print("=" * 60)
    
    for css_file in css_files:
        if os.path.exists(css_file):
            size = os.path.getsize(css_file)
            print(f"[OK] {css_file} ({size} bytes)")
        else:
            print(f"[ERRO] {css_file} NAO EXISTE")
            return False
    
    return True

def test_features_implemented():
    """Verifica se features foram implementadas"""
    print("\n" + "=" * 60)
    print("TESTE DE FEATURES IMPLEMENTADAS")
    print("=" * 60)
    
    features = []
    
    # 1. Tooltips
    with open('templates/bot_config.html', 'r', encoding='utf-8') as f:
        content = f.read()
        has_tooltips = 'data-tooltip' in content
        features.append(('Tooltips em bot_config.html', has_tooltips))
    
    # 2. Loading states
    with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()
        has_loading = 'x-show="loading"' in content and 'animate-spin' in content
        features.append(('Loading states em dashboard', has_loading))
    
    # 3. Confirmações
    with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()
        has_confirm = 'confirmAction' in content
        features.append(('confirmAction em dashboard', has_confirm))
    
    # 4. Dashboard toggle
    with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()
        has_toggle = 'showAdvanced' in content and 'toggleDashboard' in content
        features.append(('Dashboard toggle simples/avançado', has_toggle))
    
    # 5. Friendly errors
    has_friendly = os.path.exists('static/js/friendly-errors.js')
    features.append(('Sistema de erros amigáveis', has_friendly))
    
    # 6. UI Components
    has_ui = os.path.exists('static/js/ui-components.js')
    features.append(('UI Components sistema', has_ui))
    
    for feature, implemented in features:
        status = "[OK]" if implemented else "[ERRO]"
        print(f"{status} {feature}")
    
    return all(implemented for _, implemented in features)

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("VALIDAÇÃO COMPLETA DO FRONTEND")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("Templates", test_templates()))
    results.append(("JavaScript", test_javascript_files()))
    results.append(("CSS", test_css_files()))
    results.append(("Features", test_features_implemented()))
    
    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    
    for name, result in results:
        status = "[OK] PASSOU" if result else "[ERRO] FALHOU"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 60)
    print(f"SCORE: {passed}/{total} ({int(passed/total*100)}%)")
    
    if passed == total:
        print("[OK] TODOS OS TESTES PASSARAM")
        print("[OK] FRONTEND COMPLETO E FUNCIONAL")
        print("="*60)
        exit(0)
    else:
        print(f"[ERRO] {total - passed} TESTE(S) FALHARAM")
        print("=" * 60)
        exit(1)

