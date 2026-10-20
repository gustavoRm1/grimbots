"""E3 multi-turno — persistência da objeção de preço (dono: PLATAFORMA).

Causa raiz corrigida: `_handle_ai_turn` só enviava `lead.objection` a partir de
`state['objection']`, e nada semeava esse campo a partir da conversa. Resultado:
a objeção de preço do lead NUNCA era persistida e o motor não bloqueava checkout
no turno seguinte (fere o critério "objeção e resolução em turnos posteriores").

A plataforma agora detecta os gatilhos de objeção/resolução no texto do lead e
persiste em `lead.objection` (v1.0) + `collected_information.objection` (v1.1).
O motor (a54b9dd) é quem bloqueia checkout quando recebe a objeção.

Offline: só exercita os helpers puros `BotManager._ai_apply_objection_state` /
`_ai_objection_detected` / `_ai_objection_resolved_signal` — sem rede/Redis/DB.

Roda:
  python3 tests/test_e3_objection_persistence.py
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot_manager import BotManager  # noqa: E402


def test_detecta_objecao_de_preco():
    for text in ("achei muito caro", "ta caro demais", "sem dinheiro agora",
                 "esse valor ta salgado", "me da um desconto"):
        assert BotManager._ai_objection_detected(text) is True, text


def test_nao_detecta_falso_positivo():
    for text in ("oi tudo bem?", "quero assinar", "pode mandar o link",
                 "qual o conteudo do curso?"):
        assert BotManager._ai_objection_detected(text) is False, text


def test_detecta_resolucao():
    for text in ("entendi o valor, vale a pena", "faz sentido pra mim",
                 "achei justo agora", "realmente compensa"):
        assert BotManager._ai_objection_resolved_signal(text) is True, text


def test_persiste_objecao_no_estado():
    state = {}
    changed = BotManager._ai_apply_objection_state(state, "achei muito caro")
    assert changed is True
    assert state["objection"] == "achei muito caro"
    assert state["collected_information"]["objection"] == "achei muito caro"


def test_objecao_idempotente_nao_sobrescreve():
    state = {}
    BotManager._ai_apply_objection_state(state, "achei muito caro")
    changed = BotManager._ai_apply_objection_state(state, "ta caro tambem")
    # Já havia objeção ativa: não sobrescreve (changed False na 2a vez pelo texto
    # de deteccao), mantendo a objeção original.
    assert state["objection"] == "achei muito caro"
    assert changed is False


def test_resolucao_limpa_objecao_e_marca_resolvido():
    state = {}
    BotManager._ai_apply_objection_state(state, "achei muito caro")
    assert state.get("objection") == "achei muito caro"
    changed = BotManager._ai_apply_objection_state(state, "entendi o valor, vale a pena")
    assert changed is True
    # `lead.objection` limpo (precedência do motor) + resolução persistida.
    assert "objection" not in state
    assert state["collected_information"]["objection_resolved"] is True


def test_resolucao_idempotente():
    state = {}
    BotManager._ai_apply_objection_state(state, "achei muito caro")
    BotManager._ai_apply_objection_state(state, "vale a pena")
    changed = BotManager._ai_apply_objection_state(state, "vale a pena de novo")
    assert changed is False
    assert state["collected_information"]["objection_resolved"] is True


def test_texto_vazio_e_estado_invalido_nao_quebram():
    assert BotManager._ai_apply_objection_state({}, "") is False
    assert BotManager._ai_apply_objection_state(None, "achei caro") is False


def test_espelha_objecao_ja_presente_em_collected_information():
    # Caminho real: `_payload_objection` pode já ter setado state['objection'];
    # o helper deve garantir o espelho em collected_information.objection.
    state = {"objection": "achei muito caro"}
    BotManager._ai_apply_objection_state(state, "tudo bem")
    assert state["collected_information"]["objection"] == "achei muito caro"


if __name__ == "__main__":
    import traceback

    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"✅ {fn.__name__}")
        except Exception:
            failures += 1
            print(f"❌ {fn.__name__}")
            traceback.print_exc()

    print(f"\n{len(tests) - failures}/{len(tests)} OK")
    sys.exit(1 if failures else 0)
