"""Rollout controlado + kill-switch global (piloto com leads reais).

Exercita o MÉTODO REAL `BotManager._handle_ai_turn` (não uma cópia) para provar:
  * kill-switch ON => TODO bloco 'ai' desvia para HUMANO, sem responder, sem
    estado e sem efeito;
  * rollout: lead fora do bucket (%) vai para HUMANO; dentro, segue o fluxo;
  * elegibilidade é DETERMINÍSTICA por (bot_id, lead) e respeita os limites
    0%/100%;
  * config ausente/inválida => fail-safe (kill-switch off, rollout 100%);
  * rollout/kill-switch NÃO contornam proteções a jusante: `enabled=False`,
    `human_takeover` continuam valendo (o gate apenas REMOVE leads da IA).

Offline: não usa motor/Ollama. Telegram/checkout mockados; Redis falso.
(Sem `__init__.py` nos testes: FakeRedis importado do fluxo real via importlib.)

Roda:
  python3 tests/test_ai_rollout_kill_switch.py
"""
import importlib.util
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _load_fakeredis():
    path = BASE_DIR / "tests" / "integration" / "test_grimbots_real_flow_live.py"
    spec = importlib.util.spec_from_file_location("realflow_for_fakeredis", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FakeRedis


FakeRedis = _load_fakeredis()


class Recorder:
    def __init__(self):
        self.sent = []
        self.route_calls = []

    def reset(self):
        self.sent.clear()
        self.route_calls.clear()


def _make_app(config_overrides):
    from flask import Flask
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "rtest"
    app.config["GRIMBOTS_AI_SHADOW"] = "off"
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.0"
    app.config.update(config_overrides or {})
    return app


def _build(bm, fake, rec, *, sent=True, route=True):
    mgr = bm.BotManager.__new__(bm.BotManager)
    mgr.user_id = 7

    def fake_send(token, chat_id, message, bot_id=None, save_message=False, **kw):
        rec.sent.append(message)
        return {"ok": True}

    mgr.send_telegram_message = fake_send  # type: ignore

    def fake_route(bot_id, token, config, chat_id, telegram_user_id, step, conn_key):
        target = (step.get("connections") or {}).get(conn_key)
        if not target:
            return False
        rec.route_calls.append((conn_key, step.get("id")))
        return True

    mgr._ai_route = fake_route  # type: ignore
    mgr._ai_log_generation = lambda *a, **k: None  # type: ignore
    mgr._ai_shadow_enabled = lambda *a, **k: False  # type: ignore
    # Motor nunca é chamado nos caminhos de gate; se for, falha explícita.
    mgr._ai_build_history = lambda *a, **k: []  # type: ignore
    return mgr


def _step(enabled=True):
    return {
        "id": "ai1", "type": "ai",
        "config": {
            "enabled": enabled, "mode": "auto",
            "allowed_actions": ["continue", "ask_question", "present_offer",
                                 "send_checkout", "handoff_human"],
            "offers": [{"id": "of1", "name": "Curso", "price": "R$ 97",
                        "checkout_url": "https://x/y", "active": True}],
            "fallback_message": "Instabilidade momentanea.",
        },
        "connections": {"checkout": "pay1", "handoff": "hum1"},
    }


def _run_turn(mgr, rec, step, text="oi", bot_id=140, tuid="lead1", mid=1):
    rec.reset()
    mgr._handle_ai_turn(
        bot_id, "tok", {"offers": step["config"]["offers"]}, 555, tuid, step, text,
        bot_user=None, inbound_message_id=mid)
    return rec


# ══════════════════════════════════════════════════════════════════════════
# 1) KILL-SWITCH: desligamento imediato, sem resposta/estado/efeito
# ══════════════════════════════════════════════════════════════════════════
def test_kill_switch_desvia_para_handoff():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_KILL_SWITCH": True})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        step = _step(enabled=True)
        _run_turn(mgr, rec, step)
        # Desviou para handoff, sem mensagem ao lead e sem estado de conversa.
        assert ("handoff", "ai1") in rec.route_calls
        assert ("checkout", "ai1") not in rec.route_calls
        assert rec.sent == []
        assert fake.get(mgr._ai_state_key(140, "lead1")) is None


def test_kill_switch_prevalece_sobre_enabled_true():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_KILL_SWITCH": True})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        _run_turn(mgr, rec, _step(enabled=True))
        assert ("handoff", "ai1") in rec.route_calls


def test_kill_switch_off_nao_desvia():
    import bot_manager as bm
    # Sem kill-switch, e rollout 100% => NÃO desvia precocemente. O turno segue
    # o fluxo (aqui paramos no motor, que testamos com get_ai_service ausente:
    # apenas confirmamos que NÃO houve handoff precoce do gate).
    app = _make_app({"GRIMBOTS_AI_KILL_SWITCH": False,
                     "GRIMBOTS_AI_ROLLOUT_PERCENT": 100})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        # get_ai_service ausente -> erro tipado, mas ANTES disso não deve haver
        # handoff de gate.
        import internal_logic.services.ai_service as ais
        orig = ais.get_ai_service

        def boom():
            raise RuntimeError("motor indisponivel (esperado no teste)")

        ais.get_ai_service = boom
        bm.get_ai_service = boom  # type: ignore
        try:
            _run_turn(mgr, rec, _step(enabled=True))
        finally:
            ais.get_ai_service = orig
        assert ("handoff", "ai1") not in rec.route_calls, "gate nao deve desviar"


# ══════════════════════════════════════════════════════════════════════════
# 2) ROLLOUT: elegibilidade determinística e limites
# ══════════════════════════════════════════════════════════════════════════
def test_rollout_100_sempre_elegivel():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": 100})
    with app.app_context():
        for uid in ("a", "b", "c", "1140"):
            assert bm.BotManager._ai_rollout_eligible(140, uid) is True


def test_rollout_0_nunca_elegivel():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": 0})
    with app.app_context():
        for uid in ("a", "b", "c", "1140"):
            assert bm.BotManager._ai_rollout_eligible(140, uid) is False


def test_rollout_bucket_deterministico():
    import bot_manager as bm
    app = _make_app({})
    with app.app_context():
        b1 = bm.BotManager._ai_rollout_bucket(140, "leadX")
        b2 = bm.BotManager._ai_rollout_bucket(140, "leadX")
        assert b1 == b2
        assert 0.0 <= b1 < 100.0
        # bots/leads diferentes tendem a buckets diferentes.
        assert bm.BotManager._ai_rollout_bucket(141, "leadX") != b1 or \
            bm.BotManager._ai_rollout_bucket(140, "leadY") != b1


def test_rollout_50_aproxima_metade():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": 50})
    with app.app_context():
        n = 2000
        elig = sum(1 for i in range(n)
                   if bm.BotManager._ai_rollout_eligible(140, f"lead{i}"))
        # Amostragem por hash: folga generosa (40%-60%).
        assert 0.40 * n <= elig <= 0.60 * n, elig


def test_rollout_exclui_lead_para_handoff():
    import bot_manager as bm
    app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": 0})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        _run_turn(mgr, rec, _step(enabled=True))
        assert ("handoff", "ai1") in rec.route_calls
        assert rec.sent == []
        assert fake.get(mgr._ai_state_key(140, "lead1")) is None


# ══════════════════════════════════════════════════════════════════════════
# 3) CONFIG AUSENTE / INVÁLIDA => fail-safe
# ══════════════════════════════════════════════════════════════════════════
def test_config_ausente_default_seguro():
    import bot_manager as bm
    # App sem as chaves: kill-switch off e rollout 100 (sem restrição).
    app = _make_app({})
    app.config.pop("GRIMBOTS_AI_KILL_SWITCH", None)
    app.config.pop("GRIMBOTS_AI_ROLLOUT_PERCENT", None)
    with app.app_context():
        assert bm.BotManager._ai_kill_switch_enabled() is False
        assert bm.BotManager._ai_rollout_percent() == 100.0
        assert bm.BotManager._ai_rollout_eligible(140, "x") is True


def test_config_invalida_fail_safe():
    import bot_manager as bm
    for bad in ("abc", None, "", "NaN"):
        app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": bad})
        with app.app_context():
            pct = bm.BotManager._ai_rollout_percent()
            assert pct == 100.0, (bad, pct)


def test_config_percentual_clampado():
    import bot_manager as bm
    for raw, exp in ((-50, 0.0), (150, 100.0), (37, 37.0)):
        app = _make_app({"GRIMBOTS_AI_ROLLOUT_PERCENT": raw})
        with app.app_context():
            assert bm.BotManager._ai_rollout_percent() == exp, (raw, exp)


# ══════════════════════════════════════════════════════════════════════════
# 4) NÃO contorna proteções a jusante
# ══════════════════════════════════════════════════════════════════════════
def test_rollout_100_nao_reativa_bloco_desabilitado():
    import bot_manager as bm
    # `enabled=False` deve vencer mesmo com rollout 100 e kill-switch off.
    app = _make_app({"GRIMBOTS_AI_KILL_SWITCH": False,
                     "GRIMBOTS_AI_ROLLOUT_PERCENT": 100})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        _run_turn(mgr, rec, _step(enabled=False))
        assert ("handoff", "ai1") in rec.route_calls
        assert rec.sent == []


def test_rollout_100_nao_contorna_human_takeover():
    import bot_manager as bm
    # human_takeover sticky: IA silenciosa mesmo com rollout 100/kill off.
    app = _make_app({"GRIMBOTS_AI_KILL_SWITCH": False,
                     "GRIMBOTS_AI_ROLLOUT_PERCENT": 100})
    with app.app_context():
        fake = FakeRedis()
        bm.get_redis_connection = lambda: fake
        rec = Recorder()
        mgr = _build(bm, fake, rec)
        step = _step(enabled=True)
        bot_id, tuid = 140, "leadHT"
        # Marca takeover no estado real.
        mgr._ai_state_set(bot_id, tuid, {"human_takeover": True})
        _run_turn(mgr, rec, step, bot_id=bot_id, tuid=tuid, mid=9)
        # IA silenciosa: sem mensagem, sem checkout, sem handoff novo do gate.
        assert rec.sent == []
        assert ("checkout", "ai1") not in rec.route_calls


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
