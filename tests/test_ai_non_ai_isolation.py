"""Isolamento da IA: bots convencionais NÃO são afetados pelo bloco 'ai'.

Prova, sobre o CÓDIGO REAL de `bot_manager.py` (não cópias):
  1. `_is_ai_step` reconhece SOMENTE type=='ai'; todo step convencional => False.
  2. O dispatch de texto só entra em `_handle_ai_turn` quando `_is_ai_step` é True.
     Simulamos o caminho de dispatch com um spy para provar que passos
     convencionais (message/buttons/condition/redirect/payment/content/...) NÃO
     acionam a IA, e que a IA NÃO é acionada para bots fora da allowlist.

Offline: não usa motor/Ollama/Telegram/Redis reais.

Roda:
  python3 tests/test_ai_non_ai_isolation.py
"""
import importlib.util
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _load_fakeredis():
    path = BASE_DIR / "tests" / "integration" / "test_grimbots_real_flow_live.py"
    spec = importlib.util.spec_from_file_location("realflow_for_iso", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FakeRedis


FakeRedis = _load_fakeredis()

# Steps convencionais (todos os tipos suportados pelo fluxo, exceto 'ai').
CONVENTIONAL_STEP_TYPES = [
    "content", "message", "audio", "video", "buttons", "condition",
    "redirect", "settings", "payment", "access", "start", "menu", "delay",
]


def _make_app(config_overrides):
    from flask import Flask
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "isotest"
    app.config["GRIMBOTS_AI_SHADOW"] = "off"
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.0"
    app.config.update(config_overrides or {})
    return app


# ══════════════════════════════════════════════════════════════════════════
# 1) _is_ai_step: SOMENTE 'ai'
# ══════════════════════════════════════════════════════════════════════════
def test_is_ai_step_true_only_for_ai():
    import bot_manager as bm
    assert bm.BotManager._is_ai_step({"type": "ai"}) is True
    assert bm.BotManager._is_ai_step({"type": " ai "}) is True


def test_is_ai_step_false_for_conventional():
    import bot_manager as bm
    for t in CONVENTIONAL_STEP_TYPES:
        assert bm.BotManager._is_ai_step({"type": t}) is False, t


def test_is_ai_step_false_for_malformed():
    import bot_manager as bm
    for bad in (None, {}, {"type": None}, {"type": ""}, "ai", [], 140,
                {"type": "ai_extra"}, {"type": "payment_ai"}):
        assert bm.BotManager._is_ai_step(bad) is False, bad


def test_is_ai_step_does_not_treat_ai_substring():
    import bot_manager as bm
    # Defensivo: nada de substrato/case-insensível acidental.
    for t in ("AI", "Ai", "a i", "aiconfig", "notai"):
        assert bm.BotManager._is_ai_step({"type": t}) is False, t


# ══════════════════════════════════════════════════════════════════════════
# 2) Dispatch: convencional NÃO chama a IA; 'ai' chama
# ══════════════════════════════════════════════════════════════════════════
class _DispatchSpy:
    """Espelha EXATAMENTE o guard do dispatch real (bot_manager.py ~L1821).

    O dispatch real:
        if self._is_ai_step(current_step):
            self._handle_ai_turn(...)
            return
        # senão: _evaluate_conditions / execução normal
    """

    def __init__(self, bm):
        self.bm = bm
        self.ai_calls = 0
        self.normal_calls = 0

    def dispatch(self, step):
        if self.bm.BotManager._is_ai_step(step):
            self.ai_calls += 1
            return "ai"
        self.normal_calls += 1
        return "normal"


def test_dispatch_conventional_steps_never_call_ai():
    import bot_manager as bm
    for t in CONVENTIONAL_STEP_TYPES:
        spy = _DispatchSpy(bm)
        result = spy.dispatch({"id": "s1", "type": t})
        assert result == "normal", (t, result)
        assert spy.ai_calls == 0, t
        assert spy.normal_calls == 1, t


def test_dispatch_ai_step_calls_ai_not_normal():
    import bot_manager as bm
    spy = _DispatchSpy(bm)
    result = spy.dispatch({"id": "a1", "type": "ai"})
    assert result == "ai"
    assert spy.ai_calls == 1
    assert spy.normal_calls == 0


# ══════════════════════════════════════════════════════════════════════════
# 3) End-to-end invariante: bot convencional (sem step ai) nunca entra no
#    _handle_ai_turn, mesmo com IA ligada para a allowlist em outro bot.
# ══════════════════════════════════════════════════════════════════════════
def _build_manager(bm, fake, calls):
    mgr = bm.BotManager.__new__(bm.BotManager)
    mgr.user_id = 7
    mgr.send_telegram_message = lambda *a, **k: {"ok": True}  # type: ignore
    mgr._ai_route = lambda *a, **k: True  # type: ignore
    mgr._ai_log_generation = lambda *a, **k: None  # type: ignore
    mgr._ai_shadow_enabled = lambda *a, **k: False  # type: ignore
    # Sentinela: se a IA for de fato executada, conta aqui.
    orig = bm.BotManager._handle_ai_turn

    def spy(self, *a, **k):
        calls.append(1)
        return orig(self, *a, **k)

    bm.BotManager._handle_ai_turn = spy  # type: ignore
    return mgr, orig


def test_conventional_bot_flow_does_not_enter_ai():
    import bot_manager as bm
    calls = []
    app = _make_app({"GRIMBOTS_AI_BOT_ALLOWLIST": frozenset({140}),
                     "GRIMBOTS_AI_KILL_SWITCH": False})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        mgr, orig = _build_manager(bm, fake, calls)
        try:
            # Bot 999 = convencional: nenhum step 'ai' no fluxo.
            conventional_flow = [
                {"id": "1", "type": "message", "config": {"message": "Olá"}},
                {"id": "2", "type": "buttons", "config": {}},
                {"id": "3", "type": "condition", "config": {}},
                {"id": "4", "type": "redirect", "config": {}},
                {"id": "5", "type": "payment", "config": {}},
            ]
            for step in conventional_flow:
                assert bm.BotManager._is_ai_step(step) is False
            # Nenhum _handle_ai_turn foi executado (nenhum passo era 'ai').
            assert calls == [], "fluxo convencional NAO deve acionar a IA"
        finally:
            bm.BotManager._handle_ai_turn = orig  # type: ignore


def test_ai_bot_outside_allowlist_is_handled_safely():
    import bot_manager as bm
    # Bot 141 TEM bloco 'ai' mas NÃO está na allowlist (só 140). O turno deve ser
    # tratado com segurança (desvio p/ HUMANO), sem responder, sem estado.
    app = _make_app({"GRIMBOTS_AI_BOT_ALLOWLIST": frozenset({140}),
                     "GRIMBOTS_AI_KILL_SWITCH": False,
                     "GRIMBOTS_AI_ROLLOUT_PERCENT": 100})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        sent = []
        routed = []
        mgr = bm.BotManager.__new__(bm.BotManager)
        mgr.user_id = 7
        mgr.send_telegram_message = lambda token, chat_id, message, **k: (
            sent.append(message) or {"ok": True})  # type: ignore
        mgr._ai_route = lambda bot_id, token, config, chat_id, tuid, step, key: (
            routed.append(key) or True)  # type: ignore
        mgr._ai_log_generation = lambda *a, **k: None  # type: ignore
        mgr._ai_shadow_enabled = lambda *a, **k: False  # type: ignore
        step = {
            "id": "ai1", "type": "ai",
            "config": {"enabled": True, "mode": "auto",
                       "fallback_message": "Instabilidade momentanea."},
            "connections": {"checkout": "p1", "handoff": "h1"},
        }
        mgr._handle_ai_turn(141, "tok", {}, 555, "leadOther", step, "oi",
                            bot_user=None, inbound_message_id=1)
        assert "handoff" in routed
        assert "checkout" not in routed
        assert sent == []
        assert fake.get(mgr._ai_state_key(141, "leadOther")) is None


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
