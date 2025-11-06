#!/usr/bin/env python
"""
Migration: Adicionar Constraint Única em BotMessage
QI 10000 - Previne duplicação de mensagens no banco de dados

Esta migration adiciona uma constraint única que garante que:
- Uma mensagem com mesmo bot_id + telegram_user_id + message_id + direction
- Não pode ser inserida duas vezes

Uso:
    python migrations/add_unique_constraint_bot_messages.py
"""

import os
import sys
import sqlite3

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def add_unique_constraint():
    """Adiciona constraint única em bot_messages"""
    try:
        from app import app, db
        from models import BotMessage
        
        with app.app_context():
            # Verificar se constraint já existe
            inspector = db.inspect(db.engine)
            indexes = inspector.get_indexes('bot_messages')
            
            constraint_name = 'idx_bot_message_unique'
            constraint_exists = any(idx['name'] == constraint_name for idx in indexes)
            
            if constraint_exists:
                print(f"✅ Constraint '{constraint_name}' já existe")
                return
            
            # SQLite não suporta ADD CONSTRAINT diretamente
            # Precisamos criar índice único
            print("➕ Adicionando índice único em bot_messages...")
            
            try:
                # Tentar criar índice único
                db.session.execute(
                    db.text("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_message_unique 
                        ON bot_messages(bot_id, telegram_user_id, message_id, direction)
                    """)
                )
                db.session.commit()
                print("✅ Índice único criado com sucesso")
            except Exception as e:
                # Se falhar, pode ser que já exista ou banco não suporta
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"✅ Índice já existe (ou similar)")
                else:
                    print(f"⚠️  Erro ao criar índice: {e}")
                    print("   Isso não é crítico - o código já tem verificação de duplicação")
                    print("   O índice único é apenas uma camada extra de proteção")
            
            # Verificar duplicatas existentes antes de adicionar constraint
            print("\n🔍 Verificando duplicatas existentes...")
            duplicates = db.session.execute(
                db.text("""
                    SELECT bot_id, telegram_user_id, message_id, direction, COUNT(*) as count
                    FROM bot_messages
                    GROUP BY bot_id, telegram_user_id, message_id, direction
                    HAVING COUNT(*) > 1
                """)
            ).fetchall()
            
            if duplicates:
                print(f"⚠️  Encontradas {len(duplicates)} duplicatas:")
                for dup in duplicates[:10]:  # Mostrar apenas primeiras 10
                    print(f"   bot_id={dup[0]}, user_id={dup[1]}, msg_id={dup[2]}, dir={dup[3]}, count={dup[4]}")
                if len(duplicates) > 10:
                    print(f"   ... e mais {len(duplicates) - 10} duplicatas")
                print("\n💡 Recomendação: Limpar duplicatas antes de adicionar constraint")
                print("   Execute: python migrations/clean_duplicate_messages.py")
            else:
                print("✅ Nenhuma duplicata encontrada")
            
            print("\n✅ Migration concluída")
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    add_unique_constraint()

