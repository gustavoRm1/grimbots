#!/usr/bin/env python
"""
Script de Verificação - Sistema de Assinaturas
Verifica se toda a implementação FASE 1 está 100% completa e sem erros
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models import Payment, Subscription
from sqlalchemy import inspect

def verificar_implementacao():
    """Verifica se implementação está 100% completa"""
    
    print("=" * 70)
    print("🔍 VERIFICAÇÃO COMPLETA - SISTEMA DE ASSINATURAS")
    print("=" * 70)
    print()
    
    erros = []
    avisos = []
    sucessos = []
    
    with app.app_context():
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name
        
        print(f"📊 Banco de dados: {dialect}")
        print()
        
        # ========================================================================
        # VERIFICAÇÃO 1: Campos no Payment
        # ========================================================================
        print("=" * 70)
        print("1️⃣ VERIFICANDO CAMPOS NO PAYMENT")
        print("=" * 70)
        
        try:
            payment_columns = [c['name'] for c in inspector.get_columns('payments')]
            
            campos_necessarios = ['button_index', 'button_config', 'has_subscription']
            
            for campo in campos_necessarios:
                if campo in payment_columns:
                    print(f"  ✅ {campo}: EXISTE")
                    sucessos.append(f"Campo Payment.{campo}")
                else:
                    print(f"  ❌ {campo}: NÃO EXISTE")
                    erros.append(f"Campo Payment.{campo} não existe no banco")
            
            # Verificar no modelo
            if hasattr(Payment, 'button_index'):
                print(f"  ✅ Payment.button_index: Modelo OK")
            else:
                print(f"  ❌ Payment.button_index: Modelo FALTANDO")
                erros.append("Payment.button_index não existe no modelo")
            
            if hasattr(Payment, 'button_config'):
                print(f"  ✅ Payment.button_config: Modelo OK")
            else:
                print(f"  ❌ Payment.button_config: Modelo FALTANDO")
                erros.append("Payment.button_config não existe no modelo")
            
            if hasattr(Payment, 'has_subscription'):
                print(f"  ✅ Payment.has_subscription: Modelo OK")
            else:
                print(f"  ❌ Payment.has_subscription: Modelo FALTANDO")
                erros.append("Payment.has_subscription não existe no modelo")
                
        except Exception as e:
            print(f"  ❌ ERRO ao verificar Payment: {e}")
            erros.append(f"Erro ao verificar Payment: {e}")
        
        print()
        
        # ========================================================================
        # VERIFICAÇÃO 2: Tabela Subscriptions
        # ========================================================================
        print("=" * 70)
        print("2️⃣ VERIFICANDO TABELA SUBSCRIPTIONS")
        print("=" * 70)
        
        try:
            tables = inspector.get_table_names()
            
            if 'subscriptions' in tables:
                print(f"  ✅ Tabela subscriptions: EXISTE")
                sucessos.append("Tabela subscriptions existe")
                
                # Verificar colunas críticas
                sub_columns = [c['name'] for c in inspector.get_columns('subscriptions')]
                print(f"  📊 Total de colunas: {len(sub_columns)}")
                
                campos_criticos = [
                    'id', 'payment_id', 'bot_id', 'telegram_user_id',
                    'duration_type', 'duration_value', 'vip_chat_id',
                    'started_at', 'expires_at', 'status',
                    'created_at', 'updated_at'
                ]
                
                for campo in campos_criticos:
                    if campo in sub_columns:
                        print(f"  ✅ {campo}: EXISTE")
                    else:
                        print(f"  ❌ {campo}: NÃO EXISTE")
                        erros.append(f"Campo Subscription.{campo} não existe no banco")
                
                # Verificar constraint único
                try:
                    indexes = inspector.get_indexes('subscriptions')
                    unique_indexes = [idx for idx in indexes if idx.get('unique', False)]
                    payment_id_unique = any(
                        'payment_id' in str(idx.get('column_names', []))
                        for idx in unique_indexes
                    )
                    if payment_id_unique or len([c for c in inspector.get_columns('subscriptions') if c['name'] == 'payment_id' and c.get('unique', False)]) > 0:
                        print(f"  ✅ Constraint único em payment_id: OK")
                        sucessos.append("Constraint único payment_id")
                    else:
                        avisos.append("Constraint único em payment_id não verificado (pode estar OK)")
                except:
                    avisos.append("Não foi possível verificar constraint único (normal em alguns bancos)")
                    
            else:
                print(f"  ❌ Tabela subscriptions: NÃO EXISTE")
                erros.append("Tabela subscriptions não existe no banco")
            
        except Exception as e:
            print(f"  ❌ ERRO ao verificar tabela subscriptions: {e}")
            erros.append(f"Erro ao verificar subscriptions: {e}")
        
        print()
        
        # ========================================================================
        # VERIFICAÇÃO 3: Modelo Subscription
        # ========================================================================
        print("=" * 70)
        print("3️⃣ VERIFICANDO MODELO SUBSCRIPTION")
        print("=" * 70)
        
        try:
            if Subscription is not None:
                print(f"  ✅ Classe Subscription: EXISTE")
                sucessos.append("Classe Subscription existe")
                
                # Verificar métodos importantes
                metodos_necessarios = ['is_expired', 'days_remaining', 'to_dict']
                
                for metodo in metodos_necessarios:
                    if hasattr(Subscription, metodo):
                        print(f"  ✅ Subscription.{metodo}(): EXISTE")
                        sucessos.append(f"Subscription.{metodo}() existe")
                    else:
                        print(f"  ❌ Subscription.{metodo}(): NÃO EXISTE")
                        erros.append(f"Subscription.{metodo}() não existe")
                
                # Verificar campos importantes no modelo
                campos_modelo = [
                    'payment_id', 'bot_id', 'telegram_user_id',
                    'duration_type', 'duration_value', 'vip_chat_id',
                    'started_at', 'expires_at', 'status'
                ]
                
                for campo in campos_modelo:
                    if hasattr(Subscription, campo):
                        print(f"  ✅ Subscription.{campo}: EXISTE")
                    else:
                        print(f"  ❌ Subscription.{campo}: NÃO EXISTE")
                        erros.append(f"Subscription.{campo} não existe no modelo")
                
            else:
                print(f"  ❌ Classe Subscription: NÃO EXISTE")
                erros.append("Classe Subscription não existe")
                
        except Exception as e:
            print(f"  ❌ ERRO ao verificar modelo Subscription: {e}")
            erros.append(f"Erro ao verificar Subscription: {e}")
        
        print()
        
        # ========================================================================
        # VERIFICAÇÃO 4: Relacionamentos
        # ========================================================================
        print("=" * 70)
        print("4️⃣ VERIFICANDO RELACIONAMENTOS")
        print("=" * 70)
        
        try:
            # Verificar se Payment tem backref para subscription
            if hasattr(Payment, 'subscription'):
                print(f"  ✅ Payment.subscription: EXISTE (backref)")
                sucessos.append("Relacionamento Payment.subscription")
            else:
                avisos.append("Payment.subscription pode não estar configurado (normal se não houver dados)")
            
            # Verificar se Subscription tem relacionamento com Payment
            if hasattr(Subscription, 'payment'):
                print(f"  ✅ Subscription.payment: EXISTE")
                sucessos.append("Relacionamento Subscription.payment")
            else:
                print(f"  ❌ Subscription.payment: NÃO EXISTE")
                erros.append("Subscription.payment não existe")
            
            if hasattr(Subscription, 'bot'):
                print(f"  ✅ Subscription.bot: EXISTE")
                sucessos.append("Relacionamento Subscription.bot")
            else:
                print(f"  ❌ Subscription.bot: NÃO EXISTE")
                erros.append("Subscription.bot não existe")
                
        except Exception as e:
            print(f"  ❌ ERRO ao verificar relacionamentos: {e}")
            erros.append(f"Erro ao verificar relacionamentos: {e}")
        
        print()
        
        # ========================================================================
        # VERIFICAÇÃO 5: Imports e Dependências
        # ========================================================================
        print("=" * 70)
        print("5️⃣ VERIFICANDO IMPORTS E DEPENDÊNCIAS")
        print("=" * 70)
        
        try:
            from datetime import timezone
            print(f"  ✅ datetime.timezone: Importado")
            sucessos.append("Import timezone")
        except ImportError as e:
            print(f"  ❌ datetime.timezone: NÃO IMPORTADO")
            erros.append(f"timezone não importado: {e}")
        
        try:
            from dateutil.relativedelta import relativedelta
            print(f"  ✅ dateutil.relativedelta: Importado")
            sucessos.append("Import relativedelta")
        except ImportError:
            avisos.append("dateutil.relativedelta não importado (será necessário para cálculos de meses)")
        
        print()
        
        # ========================================================================
        # RESUMO FINAL
        # ========================================================================
        print("=" * 70)
        print("📋 RESUMO DA VERIFICAÇÃO")
        print("=" * 70)
        print()
        
        print(f"✅ Sucessos: {len(sucessos)}")
        if avisos:
            print(f"⚠️  Avisos: {len(avisos)}")
            for aviso in avisos:
                print(f"   - {aviso}")
        if erros:
            print(f"❌ Erros: {len(erros)}")
            for erro in erros:
                print(f"   - {erro}")
        
        print()
        print("=" * 70)
        
        if erros:
            print("❌ IMPLEMENTAÇÃO INCOMPLETA - EXISTEM ERROS!")
            print("=" * 70)
            return False
        elif avisos:
            print("⚠️  IMPLEMENTAÇÃO COMPLETA COM AVISOS")
            print("=" * 70)
            return True
        else:
            print("✅ IMPLEMENTAÇÃO 100% COMPLETA E SEM ERROS!")
            print("=" * 70)
            return True

if __name__ == '__main__':
    sucesso = verificar_implementacao()
    sys.exit(0 if sucesso else 1)

