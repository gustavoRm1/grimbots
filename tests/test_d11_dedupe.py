"""D11 — idempotência de turno: casos de FALHA e limites da garantia.

Cenário-alvo (pedido do proprietário): **o processamento falha DEPOIS da reserva
da chave**. Aqui validamos o comportamento de 2 fases (reserva → conclusão) e
documentamos os limites do "at-most-once".

Fake Redis com TTL e relógio controlável — não toca Redis/Telegram/DB.

Roda:
  python3 tests/test_d11_dedupe.py
"""
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot_manager import BotManager  # noqa: E402
import bot_manager as bm  # noqa: E402


class FakeRedis:
    """Redis in-memory com `set(ex,nx)`, `get`, `delete` e relógio injetável."""

    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._data = {}          # key -> value
        self._exp = {}           # key -> expire_at
        self._lock = threading.RLock()

    def _alive(self, key):
        exp = self._exp.get(key)
        if exp is not None and exp <= self._clock():
            self._data.pop(key, None)
            self._exp.pop(key, None)
        return key in self._data

    def get(self, key):
        with self._lock:
            return self._data.get(key) if self._alive(key) else None

    def set(self, key, value, ex=None, nx=False):
        with self._lock:
            if nx and self._alive(key):
                return False
            self._data[key] = value
            self._exp[key] = (self._clock() + ex) if ex else None
            return True

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)
            self._exp.pop(key, None)

    # estado atômico (não exercitado aqui, mas mantém compatibilidade)
    def pipeline(self):
        raise NotImplementedError


def _mgr(fake, user_id=7):
    mgr = BotManager.__new__(BotManager)
    mgr.user_id = user_id
    return mgr


def _with_redis(fake):
    original = bm.get_redis_connection
    bm.get_redis_connection = lambda: fake
    return original


# ══════════════════════════════════════════════════════════════════════════
# 1) Ciclo feliz: reserva → duplicado bloqueado → conclusão durável
# ══════════════════════════════════════════════════════════════════════════
def test_reserve_blocks_duplicate_then_complete_is_durable():
    fake = FakeRedis()
    orig = _with_redis(fake)
    try:
        mgr = _mgr(fake)
        assert mgr._ai_turn_claim(1, "999", 10) is True      # reserva
        assert mgr._ai_turn_claim(1, "999", 10) is False     # duplicado (reserva ativa)
        mgr._ai_turn_complete(1, "999", 10)                  # efeito concluído
        assert mgr._ai_turn_claim(1, "999", 10) is False     # duplicado (durável)
        assert fake.get(mgr._ai_turn_key(1, "999", 10)) == "done"
    finally:
        bm.get_redis_connection = orig


# ══════════════════════════════════════════════════════════════════════════
# 2) FALHA DEPOIS da reserva (sem concluir/liberar): janela limitada pelo TTL
# ══════════════════════════════════════════════════════════════════════════
def test_fail_after_reserve_blocks_only_until_reserve_ttl():
    t = {"now": 1000.0}
    fake = FakeRedis(clock=lambda: t["now"])
    orig = _with_redis(fake)
    try:
        mgr = _mgr(fake)
        assert mgr._ai_turn_claim(1, "999", 11) is True      # reserva
        # ... processamento FALHA e não conclui nem libera ...
        assert mgr._ai_turn_claim(1, "999", 11) is False     # reentrega bloqueada
        # após o TTL da reserva (120s) a reentrega PODE reprocessar (sem perda)
        t["now"] += mgr._AI_TURN_RESERVE_TTL + 1
        assert mgr._ai_turn_claim(1, "999", 11) is True
    finally:
        bm.get_redis_connection = orig


# ══════════════════════════════════════════════════════════════════════════
# 3) Liberação explícita (sem efeito) permite reprocessar imediatamente
# ══════════════════════════════════════════════════════════════════════════
def test_release_allows_immediate_retry():
    fake = FakeRedis()
    orig = _with_redis(fake)
    try:
        mgr = _mgr(fake)
        assert mgr._ai_turn_claim(1, "999", 12) is True
        mgr._ai_turn_release(1, "999", 12)                   # sem efeito → libera
        assert mgr._ai_turn_claim(1, "999", 12) is True
    finally:
        bm.get_redis_connection = orig


# ══════════════════════════════════════════════════════════════════════════
# 4) Fail-open: sem Redis / sem message_id → nunca bloqueia
# ══════════════════════════════════════════════════════════════════════════
def test_fail_open_without_message_id():
    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    assert mgr._ai_turn_claim(1, "999", None) is True
    assert mgr._ai_turn_claim(1, "999", "") is True


def test_fail_open_when_redis_unavailable():
    orig = bm.get_redis_connection

    def _boom():
        raise RuntimeError("redis down")

    bm.get_redis_connection = _boom
    try:
        mgr = BotManager.__new__(BotManager)
        mgr.user_id = 7
        assert mgr._ai_turn_claim(1, "999", 13) is True      # não bloqueia
        mgr._ai_turn_complete(1, "999", 13)                  # no-op, sem exceção
        mgr._ai_turn_release(1, "999", 13)                   # no-op, sem exceção
    finally:
        bm.get_redis_connection = orig


def test_fail_open_when_redis_none():
    orig = bm.get_redis_connection
    bm.get_redis_connection = lambda: None
    try:
        mgr = BotManager.__new__(BotManager)
        mgr.user_id = 7
        assert mgr._ai_turn_claim(1, "999", 14) is True
    finally:
        bm.get_redis_connection = orig


# ══════════════════════════════════════════════════════════════════════════
# 5) Concorrência: mesma mensagem → exatamente UM vencedor
# ══════════════════════════════════════════════════════════════════════════
def test_concurrent_same_message_single_winner():
    fake = FakeRedis()
    orig = _with_redis(fake)
    try:
        mgr = _mgr(fake)
        wins = []
        barrier = threading.Barrier(20)

        def worker():
            barrier.wait()
            wins.append(mgr._ai_turn_claim(1, "999", 15))

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert wins.count(True) == 1, wins
    finally:
        bm.get_redis_connection = orig


# ══════════════════════════════════════════════════════════════════════════
# 6) `_handle_ai_turn` CONCLUI a reserva mesmo quando o gateway falha
#    (o fallback é um efeito; não deve duplicar em reentrega)
# ══════════════════════════════════════════════════════════════════════════
def test_handle_ai_turn_completes_on_gateway_failure():
    import internal_logic.services.ai_service as svc

    captured = {"completed": 0, "sent": 0, "claimed": 0}

    class _BoomService:
        def respond(self, payload):
            raise svc.AIGatewayError("AI_BUSY", "busy", status=503, retryable=True)

    orig_get = svc.get_ai_service
    svc.get_ai_service = lambda *a, **k: _BoomService()

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    mgr._ai_build_history = lambda *a, **k: [{"role": "user", "content": "oi"}]
    mgr._ai_state_get = lambda *a, **k: {}
    mgr._ai_contract_v11_enabled = lambda *a, **k: False
    mgr._personalize_text = lambda *a, **k: "fallback"
    mgr._ai_log_generation = lambda *a, **k: None
    mgr.send_telegram_message = lambda **k: captured.__setitem__("sent", captured["sent"] + 1)

    def _claim(*a, **k):
        captured["claimed"] += 1
        return True

    mgr._ai_turn_claim = _claim
    mgr._ai_turn_complete = lambda *a, **k: captured.__setitem__("completed", captured["completed"] + 1)
    try:
        mgr._handle_ai_turn(1, "tok", {}, 99, "999",
                            {"id": "s1", "config": {}}, "oi", inbound_message_id=99)
        assert captured["claimed"] == 1
        assert captured["sent"] == 1          # fallback enviado (efeito)
        assert captured["completed"] == 1     # reserva concluída (sem duplicar)
    finally:
        svc.get_ai_service = orig_get


# ══════════════════════════════════════════════════════════════════════════
# 6c) Contrato futuro do motor: 409 REQUEST_IN_PROGRESS (D11 no motor)
#     -> retryável e SEM fallback (entrega concorrente do mesmo request_id).
# ══════════════════════════════════════════════════════════════════════════
def test_request_in_progress_is_retryable_and_has_no_fallback():
    import internal_logic.services.ai_service as svc

    assert "REQUEST_IN_PROGRESS" in svc._RETRYABLE_CODES

    captured = {"completed": 0, "sent": 0}

    class _Svc:
        def respond(self, payload):
            raise svc.AIGatewayError("REQUEST_IN_PROGRESS", "in progress",
                                     status=409, retryable=True)

    orig_get = svc.get_ai_service
    svc.get_ai_service = lambda *a, **k: _Svc()

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    mgr._ai_build_history = lambda *a, **k: [{"role": "user", "content": "oi"}]
    mgr._ai_state_get = lambda *a, **k: {}
    mgr._ai_contract_v11_enabled = lambda *a, **k: False
    mgr._personalize_text = lambda *a, **k: "fallback"
    mgr._ai_log_generation = lambda *a, **k: None
    mgr.send_telegram_message = lambda **k: captured.__setitem__("sent", captured["sent"] + 1)
    mgr._ai_turn_claim = lambda *a, **k: True
    mgr._ai_turn_complete = lambda *a, **k: captured.__setitem__("completed", captured["completed"] + 1)
    try:
        mgr._handle_ai_turn(1, "tok", {}, 99, "999",
                            {"id": "s1", "config": {}}, "oi", inbound_message_id=99)
        assert captured["sent"] == 0, "409 in-progress nao deve enviar fallback"
        assert captured["completed"] == 1
    finally:
        svc.get_ai_service = orig_get


# ══════════════════════════════════════════════════════════════════════════
# 6b) EFEITO COMERCIAL não duplica em replay (msg, fluxo, checkout, handoff)
# ══════════════════════════════════════════════════════════════════════════
def _run_turn_twice(action, step=None, message_id=500):
    """Roda `_handle_ai_turn` 2x com o MESMO message_id e conta efeitos."""
    import internal_logic.services.ai_service as svc

    fake = FakeRedis()
    orig_redis = _with_redis(fake)
    counts = {"sent": 0, "route": 0, "state": 0, "unknown": 0}

    class _Svc:
        def respond(self, payload):
            return svc.AIResult(
                request_id=payload.get("request_id", ""),
                message="mensagem", intent="interesse",
                lead_temperature="warm", funnel_stage="qualification",
                action=action, next_question=None,
                handoff_human=(action == "handoff_human"), risk="low",
            )

    orig_get = svc.get_ai_service
    svc.get_ai_service = lambda *a, **k: _Svc()

    step = step or {"id": "s1", "config": {}, "connections": {"checkout": "pay1"}}

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7
    mgr._ai_build_history = lambda *a, **k: [{"role": "user", "content": "oi"}]
    mgr._ai_state_get = lambda *a, **k: {}
    mgr._ai_contract_v11_enabled = lambda *a, **k: False
    mgr._personalize_text = lambda text, *a, **k: text
    mgr._ai_log_generation = lambda *a, **k: None
    mgr._ai_bot_config = lambda *a, **k: {"name": "Maya"}
    mgr._ai_build_offers = lambda *a, **k: []
    mgr._is_redundant_question = lambda *a, **k: False

    def _send(**k):
        counts["sent"] += 1
    mgr.send_telegram_message = _send

    def _route(*a, **k):
        counts["route"] += 1
        return True
    mgr._ai_route = _route

    def _atomic(bot_id, uid, persist):
        counts["state"] += 1
        persist({})
    mgr._ai_state_atomic = _atomic

    try:
        mgr._handle_ai_turn(1, "tok", {}, 99, "999", step, "oi", inbound_message_id=message_id)
        first = dict(counts)
        mgr._handle_ai_turn(1, "tok", {}, 99, "999", step, "oi", inbound_message_id=message_id)
        second = dict(counts)
        blocked = mgr._ai_turn_claim(1, "999", message_id) is False
    finally:
        svc.get_ai_service = orig_get
        bm.get_redis_connection = orig_redis
    return first, second, blocked


def test_replay_no_duplicate_message_send():
    first, second, blocked = _run_turn_twice("continue", message_id=601)
    assert first["sent"] == 1 and first["state"] == 1
    assert second == first, "replay nao pode reenviar mensagem nem repersistir"
    assert blocked is True


def test_replay_no_duplicate_checkout_routing():
    first, second, blocked = _run_turn_twice("send_checkout", message_id=602)
    assert first["route"] == 1, "checkout roteado 1x"
    assert second["route"] == 1, "replay NAO pode rotear checkout 2x"
    assert second["sent"] == first["sent"] and second["state"] == first["state"]
    assert blocked is True


def test_replay_no_duplicate_handoff_routing():
    first, second, blocked = _run_turn_twice("handoff_human", message_id=603)
    assert first["route"] == 1, "handoff roteado 1x"
    assert second["route"] == 1, "replay NAO pode disparar handoff 2x"
    assert second["sent"] == first["sent"] and second["state"] == first["state"]
    assert blocked is True


# ══════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════
def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"✅ {fn.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"💥 {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} D11 OK")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
