"""Idempotente: adiciona colunas de contexto de clique no BotUser.
Execute: python3 migrations/migrate_botuser_click_context.py
"""
import sys
from pathlib import Path
from sqlalchemy import inspect, text

# Garantir import do app/db mesmo fora do PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app, db  # noqa: E402


def run():
    with app.app_context():
        insp = inspect(db.engine)
        table = "bot_users" if "bot_users" in insp.get_table_names() else "bot_user"
        cols = [c["name"] for c in insp.get_columns(table)]

        alters = []
        if "last_click_context_url" not in cols:
            alters.append("ADD COLUMN last_click_context_url TEXT")
        if "last_fbclid" not in cols:
            alters.append("ADD COLUMN last_fbclid VARCHAR(255)")
        if "last_fbp" not in cols:
            alters.append("ADD COLUMN last_fbp VARCHAR(255)")
        if "last_fbc" not in cols:
            alters.append("ADD COLUMN last_fbc VARCHAR(255)")

        if not alters:
            print("✅ colunas já existem - nada a fazer")
            return

        db.session.execute(text(f"ALTER TABLE {table} " + ", ".join(alters)))
        db.session.commit()
        print("✅ Migração concluída")


if __name__ == "__main__":
    run()
