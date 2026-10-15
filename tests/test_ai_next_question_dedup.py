"""
P1 — Dedup do `next_question` no bloco 'ai'.

Causa raiz corrigida: `_handle_ai_turn` enviava `message_text` E `next_question`
como DUAS mensagens; quando a pergunta já estava embutida na mensagem (ex.:
"Que bom! 😊 O que você quer conversar hoje?" + "O que você quer conversar hoje?")
o guard antigo (`question != message_text`) não detectava e o lead recebia a
pergunta duas vezes.

Este teste cobre `BotManager._is_redundant_question` e o GATE de envio do
turno de IA (message + question condicional), sem tocar no Telegram.

Roda offline:
  python tests/test_ai_next_question_dedup.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot_manager import BotManager  # noqa: E402


# ── Espelha o gate em _handle_ai_turn (action in continue/ask_question/...) ──
def _should_send_question(message, question) -> bool:
    return bool(question) and not BotManager._is_redundant_question(message, question)


_AI_ACTIONS = ("continue", "ask_question", "present_offer", "pause")


# ── Caso real reproduzido (bot 140, lead 8142273932) ───────────────────────
def test_repro_1_inbound_1_outbound():
    message = "Que bom! 😊 O que você quer conversar hoje?"
    question = "O que você quer conversar hoje?"
    assert BotManager._is_redundant_question(message, question) is True
    assert _should_send_question(message, question) is False, "não deve enviar a pergunta 2x"


def test_repro_second_turn():
    message = "Sim, estou aqui para te ajudar. 😊 O que você quer conversar hoje?"
    question = "O que você quer conversar hoje?"
    assert _should_send_question(message, question) is False


# ── Igualdade / sufixo / diferenças superficiais → redundante ───────────────
def test_exact_equal_is_redundant():
    assert BotManager._is_redundant_question("Qual o seu nome?", "Qual o seu nome?") is True


def test_question_as_suffix_is_redundant():
    msg = "Perfeito, anotei tudo. Quer ver os planos?"
    assert BotManager._is_redundant_question(msg, "Quer ver os planos?") is True


def test_only_punctuation_space_emoji_diff_is_redundant():
    msg = "Boa!  🔥  Você prefere o plano A?"
    q = "voce prefere o plano a"
    assert BotManager._is_redundant_question(msg, q) is True


def test_accent_diff_is_redundant():
    msg = "Otimo! Voce pode me contar mais?"
    q = "Você pode me contar mais?"
    assert BotManager._is_redundant_question(msg, q) is True


# ── Pergunta legítima preservada (não suprimir) ─────────────────────────────
def test_message_without_question_sends_question():
    assert _should_send_question("Tudo bem por aqui!", "Qual o seu nome?") is True


def test_message_with_different_question_sends_question():
    msg = "Você prefere o plano A ou o plano B?"
    q = "Qual o seu nome?"
    assert BotManager._is_redundant_question(msg, q) is False
    assert _should_send_question(msg, q) is True


def test_empty_question_never_sent():
    assert _should_send_question("Qualquer coisa", "") is False
    assert _should_send_question("Qualquer coisa", None) is False


def test_empty_message_with_question_sends():
    assert BotManager._is_redundant_question("", "Qual o seu nome?") is False
    assert _should_send_question("", "Qual o seu nome?") is True


# ── Sem regressão: gate só depende de ask_question produzir `question` ──────
def test_gate_matches_handler_wiring():
    # Em _handle_ai_turn: question = result.next_question if action == 'ask_question' else ''
    for action in _AI_ACTIONS:
        question = "Qual o seu nome?" if action == "ask_question" else ""
        sends = _should_send_question("Oi! Como posso ajudar?", question)
        assert sends is (action == "ask_question")


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
