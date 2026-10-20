"""D11 — liberação da reserva quando falha ANTES de qualquer efeito (offline).

Regressão do defeito reproduzido no ciclo real (test_persistence_real_redis_live
R3): decisão do motor consumida + estado persistido, então um erro no envio
(Telegram) escapava, e o `finally` marcava o turno como `done` — descartando a
mensagem do lead sem chance de reentrega/retry.

Correção (bot_manager): `effect_done` rastreia se algum envio/roteamento foi
entregue; no `finally`, exceção que escapa SEM efeito -> LIBERA a reserva.

Offline: usa FakeRedis (WATCH/MULTI) e um `respond` stubado (sem motor/rede/DB).
Roda:
  python3 tests/test_d11_turn_release.py
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import bot_manager as bm  # noqa: E402
from bot_manager import BotManager  # noqa: E402


def _import_fakeredis():
    import importlib.util as ilu
    p = Path(BASE_DIR) / "tests" / "integration" / "test_grimbots_real_flow_live.py"
    spec = ilu.spec_from_file_location("_gb_rf", p)
    mod = ilu.module_from_spec(spec)
    sys.modules["_gb_rf"] = mod
    spec.loader.exec_module(mod)
    return mod.FakeRedis


FakeRedis = _import_fakeredis()


class _Rec:
    def __init__(self):
        self.sent = []


def _make_mgr(fake, rec, respond):
    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    mgr.send_telegram_message = (  # type: ignore
        lambda token, chat_id, message, bot_id=None, save_message=False, **kw:
        (rec.sent.append(message), {"ok": True})[1]
    )
    mgr._ai_route = lambda *a, **k: False  # type: ignore
    mgr._ai_log_generation = lambda *a, **k: None  # type: ignore
    mgr._ai_shadow_enabled = lambda *a, **k: False  # type: ignore

    import internal_logic.services.ai_service as ais
    from internal_logic.services.ai_service import AIResult

    class _Svc:
        def respond(self, payload):
            return respond(payload)

    svc = _Svc()
    _orig_get = ais.get_ai_service
    ais.get_ai_service = lambda: svc
    bm.get_ai_service = lambda: svc  # type: ignore
    return mgr, _orig_get, ais, AIResult


STEP = {
    "id": "ai1", "type": "ai",
    "config": {"enabled": True, "mode": "auto", "contract_version": "1.1",
               "contract_v11": True,
               "allowed_actions": ["continue", "ask_question", "present_offer",
                                   "send_checkout", "handoff_human"],
               "offers": [{"id": "of1", "name": "Curso", "price": "R$ 97",
                           "checkout_url": "https://x/y", "active": True}],
               "fallback_message": "Instabilidade momentanea."},
    "connections": {"checkout": "pay1", "handoff": "hum1"},
}
CONFIG = {"offers": STEP["config"]["offers"]}


def _run(respond, *, send_raises=False, mid=900):
    from flask import Flask
    app = Flask(__name__)
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.1"
    app.config["GRIMBOTS_AI_SHADOW"] = "off"
    ctx = app.app_context()
    ctx.push()
    try:
        fake = FakeRedis()
        orig_get_redis = bm.get_redis_connection
        bm.get_redis_connection = lambda: fake
        rec = _Rec()
        mgr, _orig_get, ais, AIResult = _make_mgr(fake, rec, respond)
        if send_raises:
            def boom(*a, **k):
                raise RuntimeError("telegram indisponivel")
            mgr.send_telegram_message = boom  # type: ignore
        raised = None
        try:
            mgr._handle_ai_turn(141, "tok", CONFIG, 555, "8142273932",
                                STEP, "oi", bot_user=None, inbound_message_id=mid)
        except Exception as e:  # noqa: BLE001
            raised = e
        key = mgr._ai_turn_key(141, "8142273932", mid)
        marker = fake.get(key)
        return {"sent": list(rec.sent), "marker": marker, "raised": raised}
    finally:
        bm.get_redis_connection = orig_get_redis
        ais.get_ai_service = _orig_get
        ctx.pop()


def test_efeito_entregue_conclui_turno():
    from internal_logic.services.ai_service import AIResult
    r = _run(lambda p: AIResult(message="Msg", action="continue"), mid=901)
    assert r["sent"] == ["Msg"]
    assert r["marker"] == "done"


def test_falha_de_envio_sem_efeito_libera_reserva():
    from internal_logic.services.ai_service import AIResult
    r = _run(lambda p: AIResult(message="Msg", action="continue"),
             send_raises=True, mid=902)
    assert r["sent"] == []
    assert r["marker"] is None, "reserva deveria ser liberada, nao 'done'"
    assert r["raised"] is not None  # exceção propagou (não foi engolida)


def test_retryavel_409_libera_reserva_sem_efeito():
    from internal_logic.services.ai_service import AIGatewayError

    def respond(payload):
        raise AIGatewayError("REQUEST_IN_PROGRESS", "em andamento", status=409)

    r = _run(respond, mid=903)
    assert r["sent"] == []
    assert r["marker"] is None
    assert r["raised"] is None


def test_reentrega_de_turno_concluido_nao_reenvia():
    from internal_logic.services.ai_service import AIResult
    # 1o turno conclui; 2o com o MESMO id não deve reenviar.
    from flask import Flask
    app = Flask(__name__)
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.1"
    ctx = app.app_context()
    ctx.push()
    try:
        fake = FakeRedis()
        orig_get_redis = bm.get_redis_connection
        bm.get_redis_connection = lambda: fake
        rec = _Rec()
        mgr, _o, ais, _ = _make_mgr(fake, rec, lambda p: AIResult(message="Msg", action="continue"))
        mgr._handle_ai_turn(141, "tok", CONFIG, 555, "8142273932", STEP, "oi",
                            bot_user=None, inbound_message_id=904)
        first = list(rec.sent)
        mgr._handle_ai_turn(141, "tok", CONFIG, 555, "8142273932", STEP, "oi",
                            bot_user=None, inbound_message_id=904)
        assert first == ["Msg"]
        assert rec.sent == ["Msg"], f"nao deveria duplicar: {rec.sent}"
    finally:
        bm.get_redis_connection = orig_get_redis
        ais.get_ai_service = _o
        ctx.pop()


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
