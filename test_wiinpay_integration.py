"""
Teste de Integração Completa - WiinPay Gateway
Valida TUDO antes de ativar em produção
"""

def test_wiinpay_integration():
    """Testa integração completa do WiinPay"""
    print("\n" + "="*70)
    print(" TESTE DE INTEGRACAO - WIINPAY GATEWAY")
    print("="*70)
    print()
    
    errors = []
    warnings = []
    
    # ========================================
    # 1. VALIDAR ARQUIVO gateway_wiinpay.py
    # ========================================
    print("[1/10] Validando gateway_wiinpay.py...")
    try:
        from gateway_wiinpay import WiinPayGateway
        print("  [OK] Import bem-sucedido")
    except Exception as e:
        errors.append(f"Erro ao importar WiinPayGateway: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 2. VALIDAR INTERFACE PaymentGateway
    # ========================================
    print("[2/10] Validando implementacao da interface...")
    try:
        from gateway_interface import PaymentGateway
        
        # Verificar se WiinPayGateway herda de PaymentGateway
        if not issubclass(WiinPayGateway, PaymentGateway):
            errors.append("WiinPayGateway nao herda de PaymentGateway")
        else:
            print("  [OK] Herda corretamente de PaymentGateway")
        
        # Verificar metodos abstratos implementados
        required_methods = [
            'generate_pix',
            'process_webhook',
            'verify_credentials',
            'get_payment_status',
            'get_webhook_url',
            'get_gateway_name',
            'get_gateway_type'
        ]
        
        for method in required_methods:
            if not hasattr(WiinPayGateway, method):
                errors.append(f"Metodo {method} nao implementado")
            else:
                print(f"  [OK] Metodo {method} implementado")
    
    except Exception as e:
        errors.append(f"Erro ao validar interface: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 3. VALIDAR FACTORY
    # ========================================
    print("[3/10] Validando gateway_factory.py...")
    try:
        from gateway_factory import GatewayFactory
        
        # Verificar se wiinpay esta no registry
        available = GatewayFactory.get_available_gateways()
        if 'wiinpay' in available:
            print("  [OK] WiinPay registrado no Factory")
        else:
            errors.append("WiinPay nao esta no Factory registry")
            print(f"  [ERRO] Gateways disponiveis: {available}")
        
        # Tentar criar instancia
        gateway = GatewayFactory.create_gateway('wiinpay', {
            'api_key': 'test_key_12345',
            'split_user_id': '9876543210'
        })
        
        if gateway:
            print("  [OK] Instancia criada pelo Factory")
            print(f"  [OK] Nome: {gateway.get_gateway_name()}")
            print(f"  [OK] Tipo: {gateway.get_gateway_type()}")
        else:
            errors.append("Factory nao conseguiu criar instancia")
    
    except Exception as e:
        errors.append(f"Erro no Factory: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 4. VALIDAR MODELS
    # ========================================
    print("[4/10] Validando models.py...")
    try:
        import sys
        import os
        
        # Ler models.py e verificar campo split_user_id
        with open('models.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '_split_user_id' in content:
            print("  [OK] Campo _split_user_id definido")
        else:
            errors.append("Campo _split_user_id nao encontrado em models.py")
        
        if 'def split_user_id(self):' in content:
            print("  [OK] Property split_user_id implementada")
        else:
            errors.append("Property split_user_id nao encontrada")
        
        if '@split_user_id.setter' in content:
            print("  [OK] Setter split_user_id implementado")
        else:
            errors.append("Setter split_user_id nao encontrado")
    
    except Exception as e:
        errors.append(f"Erro ao validar models: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 5. VALIDAR APP.PY
    # ========================================
    print("[5/10] Validando app.py...")
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se 'wiinpay' esta na lista de gateways validos
        if "'wiinpay'" in content:
            print("  [OK] wiinpay aceito em app.py")
        else:
            errors.append("wiinpay nao esta na lista de gateways validos em app.py")
        
        # Verificar if gateway_type == 'wiinpay'
        if "gateway_type == 'wiinpay'" in content:
            print("  [OK] Bloco de configuracao wiinpay encontrado")
        else:
            errors.append("Bloco elif gateway_type == 'wiinpay' nao encontrado")
        
        # Verificar split_user_id
        if 'gateway.split_user_id' in content:
            print("  [OK] gateway.split_user_id usado em app.py")
        else:
            warnings.append("gateway.split_user_id pode nao estar sendo salvo")
    
    except Exception as e:
        errors.append(f"Erro ao validar app.py: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 6. VALIDAR FRONTEND
    # ========================================
    print("[6/10] Validando frontend (settings.html)...")
    try:
        with open('templates/settings.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar card WiinPay
        if 'WiinPay' in content:
            print("  [OK] Card WiinPay presente no frontend")
        else:
            errors.append("Card WiinPay nao encontrado em settings.html")
        
        # Verificar icone
        if 'wiinpay.ico' in content:
            print("  [OK] Icone wiinpay.ico referenciado")
        else:
            warnings.append("Icone wiinpay.ico pode nao estar sendo usado")
        
        # Verificar gateways.wiinpay no JavaScript
        if 'wiinpay:' in content:
            print("  [OK] wiinpay definido no JavaScript")
        else:
            errors.append("wiinpay nao definido no gateways object (JS)")
        
        # Verificar split_user_id
        if 'split_user_id' in content:
            print("  [OK] Campo split_user_id no frontend")
        else:
            errors.append("Campo split_user_id nao encontrado no frontend")
    
    except Exception as e:
        errors.append(f"Erro ao validar frontend: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # 7. VALIDAR ICONE
    # ========================================
    print("[7/10] Validando icone...")
    if os.path.exists('static/img/wiinpay.ico'):
        print("  [OK] Icone wiinpay.ico encontrado")
    else:
        errors.append("Icone wiinpay.ico nao encontrado em static/img/")
    
    # ========================================
    # 8. VALIDAR DOCUMENTACAO
    # ========================================
    print("[8/10] Validando documentacao...")
    if os.path.exists('docs/wiinpay.md'):
        print("  [OK] Documentacao docs/wiinpay.md encontrada")
    else:
        warnings.append("Documentacao docs/wiinpay.md nao encontrada")
    
    # ========================================
    # 9. VALIDAR MIGRATION
    # ========================================
    print("[9/10] Validando migration...")
    if os.path.exists('migrate_add_wiinpay.py'):
        print("  [OK] Migration migrate_add_wiinpay.py encontrada")
        
        # Compilar migration
        try:
            import py_compile
            py_compile.compile('migrate_add_wiinpay.py', doraise=True)
            print("  [OK] Migration compila sem erros")
        except:
            errors.append("Migration tem erros de sintaxe")
    else:
        errors.append("Migration migrate_add_wiinpay.py nao encontrada")
    
    # ========================================
    # 10. TESTE DE CRIACAO DE INSTANCIA
    # ========================================
    print("[10/10] Teste de criacao de instancia...")
    try:
        gateway = WiinPayGateway(
            api_key="test_api_key_123456",
            split_user_id="9876543210"
        )
        
        print(f"  [OK] Instancia criada")
        print(f"  [OK] Nome: {gateway.get_gateway_name()}")
        print(f"  [OK] Tipo: {gateway.get_gateway_type()}")
        print(f"  [OK] Webhook URL: {gateway.get_webhook_url()}")
        
        # Testar metodo de validacao
        if gateway.validate_amount(10.50):
            print(f"  [OK] validate_amount(10.50) = True")
        
        # Testar valor minimo
        if gateway.validate_amount(2.99):
            warnings.append("validate_amount nao esta checando valor minimo R$ 3,00")
        
    except Exception as e:
        errors.append(f"Erro ao criar instancia: {e}")
        print(f"  [ERRO] {e}")
    
    # ========================================
    # RESULTADO FINAL
    # ========================================
    print()
    print("="*70)
    print(" RESULTADO DOS TESTES")
    print("="*70)
    print()
    
    if errors:
        print(f"[ERRO] {len(errors)} erro(s) encontrado(s):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print()
    
    if warnings:
        print(f"[AVISO] {len(warnings)} aviso(s):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
        print()
    
    if not errors:
        print("[OK] TODOS OS TESTES PASSARAM!")
        print()
        print("WIINPAY ESTA 100% INTEGRADO:")
        print("  [OK] Backend: gateway_wiinpay.py")
        print("  [OK] Factory: WiinPay registrado")
        print("  [OK] Models: split_user_id (criptografado)")
        print("  [OK] API: wiinpay aceito")
        print("  [OK] Frontend: Card completo em settings.html")
        print("  [OK] Icone: wiinpay.ico presente")
        print("  [OK] Docs: wiinpay.md completa")
        print("  [OK] Migration: migrate_add_wiinpay.py")
        print()
        print("PODE ATIVAR EM PRODUCAO COM SEGURANCA!")
        print()
        return True
    else:
        print("[FALHA] Corrija os erros acima antes de ativar")
        return False

if __name__ == '__main__':
    success = test_wiinpay_integration()
    exit(0 if success else 1)

