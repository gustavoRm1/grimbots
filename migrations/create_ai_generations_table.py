"""Cria a tabela NOVA `ai_generations` (auditoria do bloco 'ai' da Grimbots AI API).

Idempotente (checkfirst=True) - pode ser executado quantas vezes for preciso.
Nao altera nenhuma tabela existente.

Execute: python migrations/create_ai_generations_table.py
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import inspect as sa_inspect  # noqa: E402

from app import app  # noqa: E402
from internal_logic.core.extensions import db  # noqa: E402
from internal_logic.core.models import AIGeneration  # noqa: E402


def run():
    with app.app_context():
        existing = sa_inspect(db.engine).get_table_names()
        if "ai_generations" in existing:
            print("✅ Tabela ai_generations já existe — nada a fazer")
            return

        print("➕ Criando tabela ai_generations...")
        try:
            AIGeneration.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as exc:
            if "permission denied for schema" in str(exc):
                print(
                    "❌ Sem permissão CREATE no schema public.\n"
                    "   O código continua funcionando SEM essa tabela (o log de auditoria\n"
                    "   do bloco 'ai' falha em silêncio). Para habilitar, rode como superusuário:\n"
                    "   GRANT ALL ON SCHEMA public TO <usuario_do_app>;"
                )
                raise SystemExit(1)
            raise
        print("✅ Tabela ai_generations criada com sucesso")


if __name__ == "__main__":
    run()
