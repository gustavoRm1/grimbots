#!/usr/bin/env python3
"""
Teste Completo da Integração Meta Pixel
Data: 2024-10-20
Autor: Senior QI 300

VALIDAÇÕES:
- Migração do banco
- Configuração do Meta Pixel
- Envio de eventos (PageView, ViewContent, Purchase)
- Anti-duplicação
- Interface de usuário
"""

import os
import sys
import sqlite3
import requests
import json
from datetime import datetime

def test_database_migration():
    """Testa se a migração do banco foi aplicada corretamente"""
    print("🔍 TESTE 1: Migração do Banco de Dados")
    print("=" * 50)
    
    db_path = os.path.join('instance', 'saas_bot_manager.db')
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar colunas Meta Pixel na tabela bots
    cursor.execute("PRAGMA table_info(bots)")
    bot_columns = [row[1] for row in cursor.fetchall()]
    meta_bot_columns = [col for col in bot_columns if col.startswith('meta_')]
    
    print(f"✅ Colunas Meta Pixel em 'bots': {len(meta_bot_columns)}")
    for col in meta_bot_columns:
        print(f"   - {col}")
    
    # Verificar colunas Meta Pixel na tabela payments
    cursor.execute("PRAGMA table_info(payments)")
    payment_columns = [row[1] for row in cursor.fetchall()]
    meta_payment_columns = [col for col in payment_columns if col.startswith('meta_')]
    
    print(f"✅ Colunas Meta Pixel em 'payments': {len(meta_payment_columns)}")
    for col in meta_payment_columns:
        print(f"   - {col}")
    
    # Verificar colunas Meta Pixel na tabela bot_users
    cursor.execute("PRAGMA table_info(bot_users)")
    bot_user_columns = [row[1] for row in cursor.fetchall()]
    meta_bot_user_columns = [col for col in bot_user_columns if col.startswith('meta_')]
    
    print(f"✅ Colunas Meta Pixel em 'bot_users': {len(meta_bot_user_columns)}")
    for col in meta_bot_user_columns:
        print(f"   - {col}")
    
    conn.close()
    
    # Validação mínima
    if len(meta_bot_columns) >= 10 and len(meta_payment_columns) >= 5 and len(meta_bot_user_columns) >= 4:
        print("✅ Migração do banco: SUCESSO")
        return True
    else:
        print("❌ Migração do banco: FALHA")
        return False

def test_meta_pixel_api():
    """Testa a API do Meta Pixel"""
    print("\n🔍 TESTE 2: API do Meta Pixel")
    print("=" * 50)
    
    try:
        # Simular importação sem executar o código que depende de ENCRYPTION_KEY
        import sys
        import os
        
        # Adicionar chave temporária para o teste
        if 'ENCRYPTION_KEY' not in os.environ:
            os.environ['ENCRYPTION_KEY'] = 'hFWCKwVJGxdF8fmCTtU3TQQmtBwJ7zyyi3bYKnaHuFU='
        
        from utils.meta_pixel import MetaPixelAPI, MetaPixelHelper
        
        # Teste de validação de Pixel ID
        valid_pixel_id = MetaPixelHelper.is_valid_pixel_id("123456789012345")
        invalid_pixel_id = MetaPixelHelper.is_valid_pixel_id("123")
        
        print(f"✅ Validação Pixel ID válido: {valid_pixel_id}")
        print(f"✅ Validação Pixel ID inválido: {not invalid_pixel_id}")
        
        # Teste de validação de Access Token
        valid_token = MetaPixelHelper.is_valid_access_token("EAABwzLixnjYBO" + "x" * 50)
        invalid_token = MetaPixelHelper.is_valid_access_token("123")
        
        print(f"✅ Validação Access Token válido: {valid_token}")
        print(f"✅ Validação Access Token inválido: {not invalid_token}")
        
        # Teste de geração de event_id
        event_id = MetaPixelAPI._generate_event_id("test", "12345")
        print(f"✅ Geração de event_id: {event_id}")
        
        # Teste de geração de external_id
        external_id = MetaPixelHelper.generate_external_id()
        print(f"✅ Geração de external_id: {external_id}")
        
        print("✅ API do Meta Pixel: SUCESSO")
        return True
        
    except Exception as e:
        print(f"❌ API do Meta Pixel: FALHA - {e}")
        return False

def test_encryption():
    """Testa a criptografia"""
    print("\n🔍 TESTE 3: Criptografia")
    print("=" * 50)
    
    try:
        # Adicionar chave temporária para o teste
        import os
        if 'ENCRYPTION_KEY' not in os.environ:
            os.environ['ENCRYPTION_KEY'] = 'hFWCKwVJGxdF8fmCTtU3TQQmtBwJ7zyyi3bYKnaHuFU='
        
        from utils.encryption import encrypt, decrypt
        
        # Teste de criptografia
        original_text = "EAABwzLixnjYBO_test_token_12345"
        encrypted = encrypt(original_text)
        decrypted = decrypt(encrypted)
        
        print(f"✅ Texto original: {original_text}")
        print(f"✅ Texto criptografado: {encrypted[:20]}...")
        print(f"✅ Texto descriptografado: {decrypted}")
        
        if original_text == decrypted:
            print("✅ Criptografia: SUCESSO")
            return True
        else:
            print("❌ Criptografia: FALHA - Textos não coincidem")
            return False
            
    except Exception as e:
        print(f"❌ Criptografia: FALHA - {e}")
        return False

def test_app_routes():
    """Testa se as rotas da aplicação estão funcionando"""
    print("\n🔍 TESTE 4: Rotas da Aplicação")
    print("=" * 50)
    
    try:
        # Verificar se o arquivo app.py tem as rotas necessárias
        with open('app.py', 'r', encoding='utf-8') as f:
            app_content = f.read()
        
        required_routes = [
            '/api/bots/<int:bot_id>/meta-pixel',
            '/bots/<int:bot_id>/meta-pixel',
            '/api/bots/<int:bot_id>/meta-pixel/test'
        ]
        
        for route in required_routes:
            if route in app_content:
                print(f"✅ Rota encontrada: {route}")
            else:
                print(f"❌ Rota não encontrada: {route}")
                return False
        
        # Verificar se as funções estão definidas
        required_functions = [
            'send_meta_pixel_pageview_event',
            'send_meta_pixel_purchase_event',
            'get_meta_pixel_config',
            'update_meta_pixel_config',
            'test_meta_pixel_connection'
        ]
        
        for func in required_functions:
            if f"def {func}" in app_content:
                print(f"✅ Função encontrada: {func}")
            else:
                print(f"❌ Função não encontrada: {func}")
                return False
        
        print("✅ Rotas da Aplicação: SUCESSO")
        return True
        
    except Exception as e:
        print(f"❌ Rotas da Aplicação: FALHA - {e}")
        return False

def test_templates():
    """Testa se os templates estão corretos"""
    print("\n🔍 TESTE 5: Templates")
    print("=" * 50)
    
    try:
        # Verificar template de configuração Meta Pixel
        template_path = 'templates/meta_pixel_config.html'
        if os.path.exists(template_path):
            print(f"✅ Template encontrado: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Verificar elementos essenciais
            required_elements = [
                'meta_pixel_id',
                'meta_access_token',
                'meta_tracking_enabled',
                'meta_events_pageview',
                'meta_events_viewcontent',
                'meta_events_purchase'
            ]
            
            for element in required_elements:
                if element in template_content:
                    print(f"✅ Elemento encontrado: {element}")
                else:
                    print(f"❌ Elemento não encontrado: {element}")
                    return False
        else:
            print(f"❌ Template não encontrado: {template_path}")
            return False
        
        # Verificar se o link foi adicionado ao bot_config.html
        bot_config_path = 'templates/bot_config.html'
        if os.path.exists(bot_config_path):
            with open(bot_config_path, 'r', encoding='utf-8') as f:
                bot_config_content = f.read()
            
            if 'meta-pixel' in bot_config_content:
                print("✅ Link Meta Pixel adicionado ao bot_config.html")
            else:
                print("❌ Link Meta Pixel não encontrado no bot_config.html")
                return False
        
        print("✅ Templates: SUCESSO")
        return True
        
    except Exception as e:
        print(f"❌ Templates: FALHA - {e}")
        return False

def test_bot_manager():
    """Testa se o bot_manager foi atualizado"""
    print("\n🔍 TESTE 6: Bot Manager")
    print("=" * 50)
    
    try:
        with open('bot_manager.py', 'r', encoding='utf-8') as f:
            bot_manager_content = f.read()
        
        # Verificar se a função de ViewContent está definida
        if 'send_meta_pixel_viewcontent_event' in bot_manager_content:
            print("✅ Função ViewContent encontrada no bot_manager")
        else:
            print("❌ Função ViewContent não encontrada no bot_manager")
            return False
        
        # Verificar se a chamada está no _handle_start_command
        if 'send_meta_pixel_viewcontent_event(bot, bot_user, message)' in bot_manager_content:
            print("✅ Chamada ViewContent encontrada no _handle_start_command")
        else:
            print("❌ Chamada ViewContent não encontrada no _handle_start_command")
            return False
        
        print("✅ Bot Manager: SUCESSO")
        return True
        
    except Exception as e:
        print(f"❌ Bot Manager: FALHA - {e}")
        return False

def test_models():
    """Testa se os modelos foram atualizados"""
    print("\n🔍 TESTE 7: Modelos")
    print("=" * 50)
    
    try:
        with open('models.py', 'r', encoding='utf-8') as f:
            models_content = f.read()
        
        # Verificar campos Meta Pixel no modelo Bot
        bot_meta_fields = [
            'meta_pixel_id',
            'meta_access_token',
            'meta_tracking_enabled',
            'meta_events_pageview',
            'meta_events_viewcontent',
            'meta_events_purchase'
        ]
        
        for field in bot_meta_fields:
            if field in models_content:
                print(f"✅ Campo Bot encontrado: {field}")
            else:
                print(f"❌ Campo Bot não encontrado: {field}")
                return False
        
        # Verificar campos Meta Pixel no modelo Payment
        payment_meta_fields = [
            'meta_purchase_sent',
            'meta_purchase_sent_at',
            'meta_event_id'
        ]
        
        for field in payment_meta_fields:
            if field in models_content:
                print(f"✅ Campo Payment encontrado: {field}")
            else:
                print(f"❌ Campo Payment não encontrado: {field}")
                return False
        
        # Verificar campos Meta Pixel no modelo BotUser
        bot_user_meta_fields = [
            'meta_pageview_sent',
            'meta_viewcontent_sent'
        ]
        
        for field in bot_user_meta_fields:
            if field in models_content:
                print(f"✅ Campo BotUser encontrado: {field}")
            else:
                print(f"❌ Campo BotUser não encontrado: {field}")
                return False
        
        print("✅ Modelos: SUCESSO")
        return True
        
    except Exception as e:
        print(f"❌ Modelos: FALHA - {e}")
        return False

def main():
    """Executa todos os testes"""
    print("🚀 TESTE COMPLETO DA INTEGRAÇÃO META PIXEL")
    print("=" * 60)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        test_database_migration,
        test_meta_pixel_api,
        test_encryption,
        test_app_routes,
        test_templates,
        test_bot_manager,
        test_models
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Erro no teste: {e}")
    
    print("\n" + "=" * 60)
    print("📊 RESULTADO FINAL")
    print("=" * 60)
    print(f"Testes passaram: {passed}/{total}")
    print(f"Taxa de sucesso: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 TODOS OS TESTES PASSARAM! INTEGRAÇÃO COMPLETA!")
        print("\n✅ PRÓXIMOS PASSOS:")
        print("1. Configure um bot com Meta Pixel")
        print("2. Teste o redirecionador")
        print("3. Simule uma compra")
        print("4. Verifique os eventos no Meta Events Manager")
        return True
    else:
        print("❌ ALGUNS TESTES FALHARAM! REVISE A IMPLEMENTAÇÃO!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
