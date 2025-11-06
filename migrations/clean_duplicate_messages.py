#!/usr/bin/env python
"""
Script: Limpar Mensagens Duplicadas
QI 10000 - Remove mensagens duplicadas do banco antes de adicionar constraint única

Uso:
    python migrations/clean_duplicate_messages.py
"""

import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clean_duplicates():
    """Remove mensagens duplicadas, mantendo apenas a mais antiga"""
    try:
        from app import app, db
        from models import BotMessage
        
        with app.app_context():
            print("🔍 Buscando mensagens duplicadas...")
            
            # Buscar duplicatas
            duplicates = db.session.execute(
                db.text("""
                    SELECT bot_id, telegram_user_id, message_id, direction, COUNT(*) as count
                    FROM bot_messages
                    GROUP BY bot_id, telegram_user_id, message_id, direction
                    HAVING COUNT(*) > 1
                """)
            ).fetchall()
            
            if not duplicates:
                print("✅ Nenhuma duplicata encontrada")
                return
            
            print(f"📊 Encontradas {len(duplicates)} duplicatas")
            
            total_deleted = 0
            for dup in duplicates:
                bot_id, telegram_user_id, message_id, direction, count = dup
                
                # Buscar todas as mensagens duplicadas
                messages = BotMessage.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    message_id=message_id,
                    direction=direction
                ).order_by(BotMessage.created_at.asc()).all()
                
                # Manter a primeira (mais antiga), deletar as outras
                if len(messages) > 1:
                    to_delete = messages[1:]  # Todas exceto a primeira
                    for msg in to_delete:
                        db.session.delete(msg)
                        total_deleted += 1
                    
                    print(f"   ✅ Limpado: bot_id={bot_id}, user_id={telegram_user_id}, msg_id={message_id} ({len(to_delete)} removidas)")
            
            if total_deleted > 0:
                print(f"\n💾 Commitando {total_deleted} mensagens deletadas...")
                db.session.commit()
                print(f"✅ {total_deleted} mensagens duplicadas removidas")
            else:
                print("✅ Nenhuma mensagem removida (já limpo)")
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        sys.exit(1)

if __name__ == '__main__':
    clean_duplicates()

