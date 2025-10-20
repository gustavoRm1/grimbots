"""
Migration: Archive Old Bot Users on Token Change
================================================
Adiciona campo 'archived' para marcar usuários de tokens antigos.

Quando o token é trocado:
- Usuários antigos são arquivados
- Contador total_users é resetado
- Analytics mostra separado (ativos vs histórico)

Execução: python migrate_archive_old_users.py
"""

import sys
from app import app, db
from sqlalchemy import text

def migrate_add_archived_field():
    """Adiciona campo archived na tabela bot_users"""
    
    with app.app_context():
        print("=" * 80)
        print("MIGRACAO: Adicionar Campo 'archived' em BotUser")
        print("=" * 80)
        print()
        
        try:
            # Adicionar coluna archived (default False)
            db.session.execute(text("ALTER TABLE bot_users ADD COLUMN archived BOOLEAN DEFAULT 0"))
            db.session.commit()
            print("[OK] Coluna 'archived' adicionada com sucesso")
        except Exception as e:
            db.session.rollback()
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("[INFO] Coluna 'archived' ja existe, pulando...")
            else:
                print(f"[ERRO] Erro ao adicionar coluna: {e}")
                return False
        
        try:
            # Adicionar coluna archived_reason (motivo do arquivamento)
            db.session.execute(text("ALTER TABLE bot_users ADD COLUMN archived_reason VARCHAR(100)"))
            db.session.commit()
            print("[OK] Coluna 'archived_reason' adicionada com sucesso")
        except Exception as e:
            db.session.rollback()
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("[INFO] Coluna 'archived_reason' ja existe, pulando...")
            else:
                print(f"[AVISO] Erro ao adicionar coluna archived_reason: {e}")
        
        try:
            # Adicionar coluna archived_at (data do arquivamento)
            db.session.execute(text("ALTER TABLE bot_users ADD COLUMN archived_at DATETIME"))
            db.session.commit()
            print("[OK] Coluna 'archived_at' adicionada com sucesso")
        except Exception as e:
            db.session.rollback()
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("[INFO] Coluna 'archived_at' ja existe, pulando...")
            else:
                print(f"[AVISO] Erro ao adicionar coluna archived_at: {e}")
        
        print()
        print("[SUCESSO] Schema atualizado!")
        print()
        return True

if __name__ == '__main__':
    print()
    print("=" * 80)
    print(" " * 20 + "MIGRACAO: ARQUIVO DE USUARIOS")
    print("=" * 80)
    print()
    
    try:
        if migrate_add_archived_field():
            print()
            print("=" * 80)
            print("[SUCESSO] Migracao concluida!")
            print("=" * 80)
            print()
            print("[INFO] Agora quando voce trocar o token de um bot:")
            print("   1. Usuarios antigos serao arquivados automaticamente")
            print("   2. Contador total_users sera resetado para 0")
            print("   3. Analytics mostrara historico separado")
            print()
    except Exception as e:
        print()
        print(f"[ERRO CRITICO] {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

