"""Q2 — detecção contextual de objeção de preço (falso positivo "carro novo").

Causa raiz (relatório `docs/dev/e3/RESULTADO_CENARIOS_COMERCIAIS.md`, obs. Q2):
a plataforma casava gatilhos por SUBSTRING (`any(t in folded ...)`) e mantinha a
entrada "carro" (veículo) espelhando o motor. Resultado: "vou comprar um carro
novo" era persistido como objeção de preço — travando o checkout e gravando
objeção falsa. Também casava "caro" dentro de "caroteno".

Correção (lado PLATAFORMA, dono da persistência): casamento por PALAVRA/FRASE
com limite de token (`_ai_phrase_boundary_match`) e remoção da entrada "carro".
O motor NÃO é editado (Q1–Q3 encaminhadas ao dono do motor).

Offline: só helpers puros — sem rede/Redis/DB.

Roda:
  python3 tests/test_q2_objection_contextual.py
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot_manager import BotManager  # noqa: E402


# ── Detecção: objeção REAL ────────────────────────────────────────────────
def test_objecao_real_detectada():
    for text in ("achei muito caro", "ta caro demais", "esta caro",
                 "sem dinheiro agora", "nao tenho dinheiro",
                 "nao posso pagar isso", "esse valor ta salgado",
                 "ta puxado", "me da um desconto",
                 "preco alto demais"):
        assert BotManager._ai_objection_detected(text) is True, text


# ── Detecção: FALSO POSITIVO (núcleo do Q2) ────────────────────────────────
def test_carro_veiculo_nao_e_objecao():
    for text in ("vou comprar um carro novo, preciso juntar dinheiro",
                 "meu carro quebrou semana passada",
                 "trabalho dirigindo carro de app",
                 "carro"):
        assert BotManager._ai_objection_detected(text) is False, text


def test_substring_de_caro_nao_e_objecao():
    # "caro" não deve casar dentro de outra palavra.
    for text in ("esse curso tem caroteno na dieta",
                 "a carótida é uma artéria importante",
                 "que valorizacao boa"):
        assert BotManager._ai_objection_detected(text) is False, text


def test_texto_neutro_nao_e_objecao():
    for text in ("oi tudo bem?", "quero assinar", "pode mandar o link",
                 "qual o conteudo do curso?"):
        assert BotManager._ai_objection_detected(text) is False, text


# ── Detecção: RESOLUÇÃO (contextual, mesma regra) ─────────────────────────
def test_resolucao_real_detectada():
    for text in ("entendi o valor, vale a pena", "faz sentido pra mim",
                 "achei justo agora", "realmente compensa"):
        assert BotManager._ai_objection_resolved_signal(text) is True, text


def test_resolucao_nao_casa_substring():
    # "investimento" não deve casar como "e um bom investimento" (frase).
    for text in ("isso nao vale nada isso", "quero fazer um investimento pesado"):
        assert BotManager._ai_objection_resolved_signal(text) is False, text


# ── PERSISTÊNCIA: objeção falsa NÃO é gravada (Q2) ────────────────────────
def test_carro_novo_nao_persiste_objecao():
    state = {}
    changed = BotManager._ai_apply_objection_state(
        state, "vou comprar um carro novo, preciso juntar dinheiro")
    assert changed is False
    assert "objection" not in state
    assert (state.get("collected_information") or {}).get("objection") is None


def test_caroteno_nao_persiste_objecao():
    state = {}
    changed = BotManager._ai_apply_objection_state(
        state, "esse curso tem caroteno na dieta")
    assert changed is False
    assert "objection" not in state


# ── PERSISTÊNCIA: objeção real continua gravando ──────────────────────────
def test_objecao_real_persiste():
    state = {}
    changed = BotManager._ai_apply_objection_state(state, "achei muito caro")
    assert changed is True
    assert state["objection"] == "achei muito caro"
    assert state["collected_information"]["objection"] == "achei muito caro"


# ── RESOLUÇÃO: limpa objeção ativa (fluxo completo) ───────────────────────
def test_resolucao_limpa_objecao_apos_objecao_real():
    state = {}
    BotManager._ai_apply_objection_state(state, "achei muito caro")
    assert state.get("objection") == "achei muito caro"
    changed = BotManager._ai_apply_objection_state(
        state, "entendi o valor, vale a pena")
    assert changed is True
    assert "objection" not in state
    assert state["collected_information"]["objection_resolved"] is True


def test_resolucao_so_apos_objecao_real():
    # Sem objeção ativa, um sinal de resolução não cria ruído no estado.
    state = {}
    changed = BotManager._ai_apply_objection_state(state, "vale a pena")
    assert changed is False
    assert (state.get("collected_information") or {}).get("objection_resolved") is None


# ── Robustez ──────────────────────────────────────────────────────────────
def test_texto_vazio_e_estado_invalido():
    assert BotManager._ai_apply_objection_state({}, "") is False
    assert BotManager._ai_apply_objection_state(None, "achei caro") is False
    assert BotManager._ai_objection_detected("") is False
    assert BotManager._ai_objection_detected(None) is False


def test_match_por_frase_com_limite():
    # Gatilho multi-palavra casa como sequência; não casa fragmento isolado.
    assert BotManager._ai_objection_detected("isso ta muito caro mesmo") is True
    assert BotManager._ai_objection_detected("nao tenho como pagar agora") is True
    assert BotManager._ai_objection_detected("muito obrigado pela atencao") is False


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
