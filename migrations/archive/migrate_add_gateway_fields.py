"""
Migration: Adicionar campos Paradise e HooPay ao modelo Gateway
Executar: python migrate_add_gateway_fields.py
"""

from app import app, db
from models import Gateway

def migrate():
    """Adiciona novos campos à tabela gateways"""
    with app.app_context():
        try:
            print("🔧 Iniciando migration: Adicionar campos Paradise/HooPay...")
            
            # Adicionar colunas usando ALTER TABLE (SQLite/MySQL/PostgreSQL compatível)
            with db.engine.connect() as conn:
                # Verifica se colunas já existem
                inspector = db.inspect(db.engine)
                existing_columns = [col['name'] for col in inspector.get_columns('gateways')]
                
                # Paradise fields
                if 'product_hash' not in existing_columns:
                    print("  ➕ Adicionando coluna: product_hash")
                    conn.execute(db.text("ALTER TABLE gateways ADD COLUMN product_hash VARCHAR(255)"))
                    conn.commit()
                else:
                    print("  ✅ Coluna product_hash já existe")
                
                if 'offer_hash' not in existing_columns:
                    print("  ➕ Adicionando coluna: offer_hash")
                    conn.execute(db.text("ALTER TABLE gateways ADD COLUMN offer_hash VARCHAR(255)"))
                    conn.commit()
                else:
                    print("  ✅ Coluna offer_hash já existe")
                
                if 'store_id' not in existing_columns:
                    print("  ➕ Adicionando coluna: store_id")
                    conn.execute(db.text("ALTER TABLE gateways ADD COLUMN store_id VARCHAR(50)"))
                    conn.commit()
                else:
                    print("  ✅ Coluna store_id já existe")
                
                # HooPay fields
                if 'organization_id' not in existing_columns:
                    print("  ➕ Adicionando coluna: organization_id")
                    conn.execute(db.text("ALTER TABLE gateways ADD COLUMN organization_id VARCHAR(255)"))
                    conn.commit()
                else:
                    print("  ✅ Coluna organization_id já existe")
                
                # Split percentage (comum a todos)
                if 'split_percentage' not in existing_columns:
                    print("  ➕ Adicionando coluna: split_percentage")
                    conn.execute(db.text("ALTER TABLE gateways ADD COLUMN split_percentage FLOAT DEFAULT 4.0"))
                    conn.commit()
                    
                    # Atualizar registros existentes
                    conn.execute(db.text("UPDATE gateways SET split_percentage = 4.0 WHERE split_percentage IS NULL"))
                    conn.commit()
                    print("    ✅ Registros existentes atualizados com split_percentage = 4.0")
                else:
                    print("  ✅ Coluna split_percentage já existe")
            
            print("\n✅ Migration concluída com sucesso!")
            print("   Novos campos disponíveis:")
            print("   - product_hash (Paradise)")
            print("   - offer_hash (Paradise)")
            print("   - store_id (Paradise)")
            print("   - organization_id (HooPay)")
            print("   - split_percentage (Todos)")
            
        except Exception as e:
            print(f"\n❌ Erro durante migration: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    migrate()











