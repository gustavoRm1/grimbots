"""
Script de Migração: Adicionar Índices Faltantes
============================================================================
CORREÇÃO #8: Adiciona índices em campos frequentemente consultados

Índices adicionados:
- User.is_banned (queries de listagem de usuários)
- Bot.is_running (queries de bots ativos)
- Payment.status (queries de pagamentos por status)

Executar: python migrate_add_indexes.py
"""

from app import app, db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Adiciona índices faltantes"""
    with app.app_context():
        try:
            logger.info("🔧 Iniciando migração de índices...")
            
            # Conectar ao banco
            connection = db.engine.connect()
            
            # Lista de índices a criar
            indexes = [
                ("users", "is_banned", "idx_users_is_banned"),
                ("bots", "is_running", "idx_bots_is_running"),
                ("payments", "status", "idx_payments_status"),
            ]
            
            for table, column, index_name in indexes:
                try:
                    # Verificar se índice já existe
                    check_query = f"""
                        SELECT name FROM sqlite_master 
                        WHERE type='index' AND name='{index_name}'
                    """
                    result = connection.execute(db.text(check_query))
                    exists = result.fetchone() is not None
                    
                    if exists:
                        logger.info(f"⏭️  Índice {index_name} já existe")
                        continue
                    
                    # Criar índice
                    create_query = f"CREATE INDEX {index_name} ON {table}({column})"
                    connection.execute(db.text(create_query))
                    connection.commit()
                    
                    logger.info(f"✅ Índice {index_name} criado em {table}.{column}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao criar índice {index_name}: {e}")
                    connection.rollback()
            
            connection.close()
            
            logger.info("✅ Migração de índices concluída com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}")
            raise

if __name__ == '__main__':
    print("=" * 70)
    print("MIGRAÇÃO: ADICIONAR ÍNDICES FALTANTES")
    print("=" * 70)
    migrate()
    print("=" * 70)

