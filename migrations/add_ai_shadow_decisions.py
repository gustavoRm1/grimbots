#!/usr/bin/env python3
"""
Migration E5: cria a tabela aditiva `ai_shadow_decisions` e mantém colunas novas.

Aditiva e idempotente (pode rodar múltiplas vezes):
  - cria a tabela se não existir (checkfirst);
  - adiciona colunas novas (ex.: `motor_version_source`) se a tabela já existir.

Não altera nenhuma tabela existente. Não ativa a feature — só recebe linhas com
GRIMBOTS_AI_SHADOW=on E flag `shadow` do bloco.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

# (nome, DDL) — colunas adicionadas após a criação inicial da tabela.
_EXTRA_COLUMNS = [
    ("motor_version_source", "VARCHAR(20)"),
]


def migrate():
    with app.app_context():
        try:
            from internal_logic.core.models import AIShadowDecision
            AIShadowDecision.__table__.create(bind=db.engine, checkfirst=True)
            print("✅ Tabela ai_shadow_decisions pronta (criada ou já existente)")

            inspector = inspect(db.engine)
            cols = [c["name"] for c in inspector.get_columns("ai_shadow_decisions")]
            for name, ddl in _EXTRA_COLUMNS:
                if name not in cols:
                    db.session.execute(text(
                        f"ALTER TABLE ai_shadow_decisions ADD COLUMN {name} {ddl}"
                    ))
                    db.session.commit()
                    print(f"✅ Coluna {name} adicionada")
            return True
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            print(f"❌ Erro na migration ai_shadow_decisions: {exc}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    sys.exit(0 if migrate() else 1)
