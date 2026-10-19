#!/usr/bin/env python3
"""
Migration E5: cria a tabela aditiva `ai_shadow_decisions`.

Não altera nenhuma tabela existente. Idempotente (checkfirst=True): pode rodar
múltiplas vezes sem erro. Não ativa a feature — a tabela só recebe linhas quando
o flag global GRIMBOTS_AI_SHADOW e o flag `shadow` do bloco estiverem ligados.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # noqa: E402


def migrate():
    with app.app_context():
        try:
            from internal_logic.core.models import AIShadowDecision
            AIShadowDecision.__table__.create(bind=db.engine, checkfirst=True)
            print("✅ Tabela ai_shadow_decisions pronta (criada ou já existente)")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Erro ao criar ai_shadow_decisions: {exc}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    sys.exit(0 if migrate() else 1)
