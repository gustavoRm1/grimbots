"""
Migração DB Agnostic - Versão Isolada (Sem Eventlet)
Adiciona coluna group_id à tabela remarketing_campaigns
"""
import os
import sys

# Carregar variáveis de ambiente primeiro
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError


def run_migration():
    # Criar app mínimo para contexto (sem SocketIO/Eventlet)
    app = Flask(__name__)
    
    # Configuração do banco a partir das variáveis de ambiente
    database_url = os.getenv('DATABASE_URL', 'sqlite:///grimbots.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db = SQLAlchemy(app)
    
    with app.app_context():
        try:
            print("⏳ Iniciando migração do banco de dados...")
            print(f"📡 Conectado a: {database_url[:30]}...")
            
            # 1. Adicionar a coluna group_id (VARCHAR(50) NULL)
            try:
                db.session.execute(text(
                    "ALTER TABLE remarketing_campaigns ADD COLUMN group_id VARCHAR(50) NULL;"
                ))
                db.session.commit()
                print("✅ Coluna 'group_id' adicionada com sucesso.")
            except (OperationalError, ProgrammingError) as e:
                db.session.rollback()
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg or 'exists' in error_msg:
                    print("ℹ️ Coluna 'group_id' já existe. Pulando...")
                else:
                    raise
            
            # 2. Criar o índice idx_group_id
            try:
                db.session.execute(text(
                    "CREATE INDEX idx_group_id ON remarketing_campaigns (group_id);"
                ))
                db.session.commit()
                print("✅ Índice 'idx_group_id' criado com sucesso.")
            except (OperationalError, ProgrammingError) as e:
                db.session.rollback()
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg or 'exists' in error_msg:
                    print("ℹ️ Índice 'idx_group_id' já existe. Pulando...")
                else:
                    raise
            
            print("🚀 Migração concluída! O banco de dados está pronto para o Remarketing Global.")
            print("\n📋 Resumo:")
            print("   - Coluna 'group_id' (VARCHAR(50), NULL): OK")
            print("   - Índice 'idx_group_id': OK")
            print("\n💡 Próximo passo: As novas campanhas de remarketing geral serão automaticamente vinculadas via group_id.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Erro na migração: {str(e)}")
            sys.exit(1)


if __name__ == '__main__':
    run_migration()
