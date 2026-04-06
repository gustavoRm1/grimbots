"""
Migration: Adicionar coluna click_context_url ao modelo Payment
Idempotente e seguro para rodar várias vezes.

Execute: python migrations/migrations_add_click_context_url.py
Rollback (apenas se suportado pelo banco): python migrations/migrations_add_click_context_url.py rollback
"""

import os
import sys
from pathlib import Path

from flask import Flask
from sqlalchemy import text, inspect

# Ajustar path para importar app e models
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from internal_logic.core.models import db  # noqa: E402


def _init_app():
    app = Flask(__name__)
    DB_PATH = BASE_DIR / "instance" / "saas_bot_manager.db"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DB_PATH}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    return app


def add_click_context_url():
    app = _init_app()
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        table_name = None
        if "payments" in tables:
            table_name = "payments"
        elif "payment" in tables:
            table_name = "payment"
        else:
            print(f"❌ Tabela de pagamentos não encontrada. Tabelas: {tables}")
            return False

        print(f"🔍 Tabela detectada: {table_name}")

        # Já existe?
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        if "click_context_url" in columns:
            print("✅ Coluna click_context_url já existe - nada a fazer")
            return True

        # Criar coluna (compatível com SQLite/PostgreSQL/MySQL)
        try:
            db.session.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN click_context_url TEXT;
                    """
                )
            )
            db.session.commit()
            print("✅ Coluna click_context_url adicionada com sucesso")
        except Exception as e:
            db.session.rollback()
            msg = str(e).lower()
            if "duplicate" in msg or "exists" in msg:
                print("✅ Coluna click_context_url já existe (detectada pelo erro) - ignorando")
            else:
                print(f"❌ Erro ao adicionar coluna: {e}")
                return False

        return True


def rollback_click_context_url():
    """Remove a coluna click_context_url (se o banco suportar)."""
    app = _init_app()
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        table_name = None
        if "payments" in tables:
            table_name = "payments"
        elif "payment" in tables:
            table_name = "payment"
        else:
            print(f"❌ Tabela de pagamentos não encontrada. Tabelas: {tables}")
            return False

        columns = [col["name"] for col in inspector.get_columns(table_name)]
        if "click_context_url" not in columns:
            print("✅ Coluna click_context_url não existe - nada a remover")
            return True

        try:
            db.session.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    DROP COLUMN click_context_url;
                    """
                )
            )
            db.session.commit()
            print("✅ Coluna click_context_url removida")
        except Exception as e:
            db.session.rollback()
            print(
                "⚠️ Rollback falhou. Para SQLite, é necessário recriar a tabela manualmente.\n"
                f"Detalhe: {e}"
            )
            return False

        return True


if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) > 1 and _sys.argv[1] == "rollback":
        ok = rollback_click_context_url()
    else:
        ok = add_click_context_url()

    _sys.exit(0 if ok else 1)
