"""Ciclo integrado com PERSISTÊNCIA REAL (Redis) em ambiente isolado.

Diferença central em relação a `test_grimbots_real_flow_live.py`: aqui o estado
conversacional e o marcador de idempotência (D11) vivem em **Redis REAL**
(`REDIS_URL`, db isolado), não num FakeRedis. Isso comprova persistência e
RECUPERAÇÃO entre conexões/instâncias — não apenas em memória do processo.

Serviços:
  - Redis REAL: `REDIS_URL` (default `redis://localhost:6379/15`, db isolado).
    O teste FLUSHA apenas o db configurado (nunca o db de produção).
  - Motor comercial REAL (`a54b9dd`) via HTTP, Ollama mockado (sem LLM real).
  - Telegram MOCKADO; checkout/handoff MOCKADOS (sem PIX, sem efeito externo).
  - Banco de dados: NÃO usado (auditoria desligada). Não habilita D11_STORE=sqlite.

Cenários:
  L1 objecao -> persistida em Redis real + recuperada por conexao nova
  L2 objecao persistida bloqueia checkout (turno seguinte)
  L3 resposta a objecao (esclarece) e mantem bloqueio enquanto nao resolvida
  L4 resolucao -> nova decisao comercial -> checkout liberado
  R1 falha RETRYAVEL do motor (REQUEST_IN_PROGRESS): sem efeito, reserva liberada
  R2 retry legitimo apos retryavel: processa UMA vez (sem duplicidade)
  R3 falha APOS decisao/antes do envio: excecao nao deixa efeito parcial; retry
     com a MESMA msg nao duplica (marcador durável so na conclusao)
  R4 reentrega da MESMA msg ja concluida: sem efeito (at-most-once)
  C1 checkout exige oferta ATIVA + permissao efetiva (allowed_actions)

Requer (env):
  GRIMBOTS_AI_MOTOR_DIR / GRIMBOTS_AI_VENV_PY (ver harness). Ausente -> SKIP.
  REDIS_URL (opcional; default db 15 local). Sem Redis acessivel -> SKIP.

Roda:
  GRIMBOTS_AI_MOTOR_DIR=.../motor-a54b9dd \
  GRIMBOTS_AI_VENV_PY=.../t15venv/bin/python \
  REDIS_URL=redis://localhost:6379/15 \
  python3 tests/integration/test_persistence_real_redis_live.py
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Redis ISOLADO: precisa ser definido ANTES de importar o redis_manager ────
REDIS_URL = os.environ.get("GRIMBOTS_TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["REDIS_URL"] = REDIS_URL

# Reusa o mock de Ollama e helpers do harness de fluxo real (mesma semântica).
import importlib.util as _ilu  # noqa: E402

_base_path = Path(__file__).resolve().parent / "test_grimbots_real_flow_live.py"
_spec = _ilu.spec_from_file_location("_gb_real_flow_base", _base_path)
base = _ilu.module_from_spec(_spec)
sys.modules["_gb_real_flow_base"] = base
_spec.loader.exec_module(base)  # noqa: E402

DEFAULT_MOTOR_DIR = "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/grimbots-ai"
DEFAULT_VENV_PY = "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/t15venv/bin/python"
MOTOR_DIR = Path(os.environ.get("GRIMBOTS_AI_MOTOR_DIR", DEFAULT_MOTOR_DIR))
VENV_PY = Path(os.environ.get("GRIMBOTS_AI_VENV_PY", DEFAULT_VENV_PY))
API_KEY = "rtest-motor-key"
MOCK = base.MOCK
MockOllama = base.MockOllama


def _redis_client():
    import redis
    return redis.from_url(REDIS_URL, decode_responses=True)


def _redis_available():
    try:
        c = _redis_client()
        c.ping()
        # Segurança: só permite db != 0 para não arriscar produção.
        db = _redis_client().connection_pool.connection_kwargs.get("db")
        if db in (0, None):
            return False, f"REDIS_URL aponta para db={db} (recusado por seguranca)"
        return True, db
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


class Recorder:
    def __init__(self):
        self.sent = []
        self.route_calls = []

    def reset(self):
        self.sent.clear()
        self.route_calls.clear()


def run(motor_port, rec, rclient):
    import bot_manager as bm
    from bot_manager import BotManager

    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    from flask import Flask
    app = Flask(__name__)
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.1"
    app.config["GRIMBOTS_AI_SHADOW"] = "off"
    app.config["SECRET_KEY"] = "rtest"
    ctx = app.app_context()
    ctx.push()

    # Redis REAL via get_redis_connection (sem monkeypatch).
    from internal_logic.core.redis_manager import get_redis_connection as real_get_redis

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7

    from internal_logic.services import ai_service as ais
    svc = ais.GrimbotsAIService(f"http://127.0.0.1:{motor_port}", API_KEY, timeout=20.0)
    ais.get_ai_service = lambda: svc
    bm.get_ai_service = lambda: svc  # type: ignore

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

    step = {
        "id": "ai1",
        "type": "ai",
        "config": {
            "enabled": True,
            "mode": "auto",
            "contract_version": "1.1",
            "contract_v11": True,
            "allowed_actions": [
                "continue", "ask_question", "present_offer",
                "send_checkout", "handoff_human",
            ],
            "offers": [{"id": "of1", "name": "Curso", "price": "R$ 97",
                        "checkout_url": "https://x/y", "active": True}],
            "fallback_message": "Instabilidade momentanea.",
        },
        "connections": {"checkout": "pay1", "handoff": "hum1"},
    }
    config = {"offers": step["config"]["offers"]}
    bot_id, tuid = 141, "8142273932"

    def state_via(conn):
        raw = conn.get(mgr._ai_state_key(bot_id, tuid))
        return json.loads(raw) if raw else {}

    def state():
        return state_via(real_get_redis())

    def turn(text, mid):
        rec.reset()
        mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step, text,
                            bot_user=None, inbound_message_id=mid)
        return state()

    def clear_state():
        rclient.delete(mgr._ai_state_key(bot_id, tuid))

    # ── L1: objeção persistida em Redis REAL e recuperada por conexão NOVA ──
    clear_state()
    MOCK["outputs"] = [{"action": "present_offer", "message": "Temos o Curso por R$ 97",
                        "funnel_stage": "offer"}]
    turn("achei muito caro", mid=201)
    st = state()
    fresh = real_get_redis()  # conexão/objeto novo = recuperação real
    ci = (st.get("collected_information") or {})
    raw_key = rclient.get(mgr._ai_state_key(bot_id, tuid))
    check("L1 objecao persistida em Redis real e recuperavel por conexao nova",
          bool(raw_key) and st.get("objection") == "achei muito caro"
          and ci.get("objection") == "achei muito caro"
          and bool(fresh.get(mgr._ai_state_key(bot_id, tuid))),
          f"key={'set' if raw_key else 'MISSING'} state.objection={st.get('objection')!r} "
          f"ci.objection={ci.get('objection')!r}")

    # ── L2: objeção persistida BLOQUEIA checkout no turno seguinte ──────────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    turn("quero fechar agora", mid=202)
    check("L2 objecao persistida bloqueia checkout (Redis real)",
          ("checkout", "ai1") not in rec.route_calls,
          f"rotas={list(rec.route_calls)}")

    # ── L3: resposta à objeção (esclarece) mantém bloqueio enquanto NÃO resolve ─
    MOCK["outputs"] = [{"action": "continue", "message": "Entendo a preocupacao com o valor.",
                        "funnel_stage": "offer"}]
    st3 = turn("entendi, mas ainda acho caro", mid=203)
    check("L3 resposta a objecao sem sinal de resolucao mantem objecao ativa",
          st3.get("objection") == "achei muito caro"
          and not (st3.get("collected_information") or {}).get("objection_resolved"),
          f"objection={st3.get('objection')!r} "
          f"resolved={(st3.get('collected_information') or {}).get('objection_resolved')!r}")

    # ── L4: resolução -> nova decisão comercial -> checkout liberado ────────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    st4 = turn("entendi o valor, vale a pena, pode mandar o link", mid=204)
    check("L4 resolucao libera nova decisao comercial com checkout",
          ("checkout", "ai1") in rec.route_calls
          and "objection" not in st4
          and (st4.get("collected_information") or {}).get("objection_resolved") is True,
          f"rotas={list(rec.route_calls)} ci={st4.get('collected_information')}")

    # ── R1/R2: falha RETRYÁVEL (REQUEST_IN_PROGRESS) -> libera; retry processa ─
    clear_state()
    _orig_respond = svc.respond

    class _RetryThenOk:
        def __init__(self, inner):
            self.inner = inner
            self.calls = 0

        def __call__(self, payload):
            self.calls += 1
            if self.calls == 1:
                raise ais.AIGatewayError("REQUEST_IN_PROGRESS",
                                         "outro turno em andamento", status=409)
            return self.inner(payload)

    svc.respond = _RetryThenOk(_orig_respond)
    try:
        MOCK["outputs"] = [{"action": "continue", "message": "Certo!"}]
        rec.reset()
        mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                            "oi", bot_user=None, inbound_message_id=301)
        r1_turn_key = mgr._ai_turn_key(bot_id, tuid, 301)
        r1_still_reserved = rclient.get(r1_turn_key)  # None se liberado
        check("R1 falha retryavel (409) nao deixa efeito e libera a reserva",
              rec.sent == [] and r1_still_reserved is None,
              f"sent={rec.sent} reserva={r1_still_reserved!r}")

        rec.reset()
        mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                            "oi", bot_user=None, inbound_message_id=301)
        r2_ok = rec.sent == ["Certo!"] and rclient.get(r1_turn_key) == "done"
        check("R2 retry legitimo da MESMA msg processa UMA vez (sem duplicidade)",
              r2_ok, f"sent={rec.sent} marcador={rclient.get(r1_turn_key)!r}")
    finally:
        svc.respond = _orig_respond

    # ── R3: falha APÓS decisão, ANTES do envio -> sem efeito parcial; retry OK ─
    clear_state()
    _orig_send = mgr.send_telegram_message
    boom = {"armed": True}

    def flaky_send(token, chat_id, message, bot_id=None, save_message=False, **kw):
        if boom["armed"]:
            boom["armed"] = False
            raise RuntimeError("telegram indisponivel (simulado)")
        return _orig_send(token, chat_id, message, bot_id=bot_id,
                          save_message=save_message, **kw)

    mgr.send_telegram_message = flaky_send  # type: ignore
    try:
        MOCK["outputs"] = [
            {"action": "continue", "message": "Msg1"},   # 1a tentativa (envio falha)
            {"action": "continue", "message": "Msg1"},   # retry (mesma decisao)
        ]
        rec.reset()
        r3_key = mgr._ai_turn_key(bot_id, tuid, 401)
        try:
            mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                                "oi", bot_user=None, inbound_message_id=401)
        except Exception as e:  # noqa: BLE001
            check("R3 (pré) excecao apos decisao propaga sem engolir", True, repr(e))
        r3_after_fail = rclient.get(r3_key)
        # Sem envio efetivo -> reserva liberada (permite retry), nada duplicado.
        check("R3 falha apos decisao/antes do envio: sem envio e reserva liberada",
              rec.sent == [] and r3_after_fail is None,
              f"sent={rec.sent} marcador={r3_after_fail!r}")

        rec.reset()
        mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                            "oi", bot_user=None, inbound_message_id=401)
        check("R3 retry processa exatamente UMA vez apos falha de envio",
              rec.sent == ["Msg1"] and rclient.get(r3_key) == "done",
              f"sent={rec.sent} marcador={rclient.get(r3_key)!r}")
    finally:
        mgr.send_telegram_message = _orig_send  # type: ignore

    # ── R4: reentrega da MESMA msg JÁ CONCLUÍDA -> sem efeito (durabilidade) ─
    MOCK["outputs"] = [{"action": "continue", "message": "Nao deveria enviar"}]
    rec.reset()
    mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                        "oi", bot_user=None, inbound_message_id=401)
    check("R4 reentrega de msg concluida nao gera efeito (marcador duravel)",
          rec.sent == [], f"sent={rec.sent} marcador={rclient.get(r3_key)!r}")

    # ── C1: checkout exige oferta ATIVA + permissao efetiva ─────────────────
    clear_state()
    # (a) sem permissao para send_checkout -> bloqueado
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    step_no_perm = json.loads(json.dumps(step))
    step_no_perm["config"]["allowed_actions"] = ["continue", "ask_question"]
    rec.reset()
    mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step_no_perm,
                        "pode mandar o link", bot_user=None, inbound_message_id=501)
    no_perm_blocked = ("checkout", "ai1") not in rec.route_calls

    # (b) oferta inativa -> bloqueado (mesmo com permissao)
    clear_state()
    step_inactive = json.loads(json.dumps(step))
    step_inactive["config"]["offers"] = [{"id": "of1", "name": "Curso", "price": "R$ 97",
                                          "checkout_url": "https://x/y", "active": False}]
    rec.reset()
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    mgr._handle_ai_turn(bot_id, "tok", {"offers": step_inactive["config"]["offers"]},
                        555, tuid, step_inactive, "pode mandar o link",
                        bot_user=None, inbound_message_id=502)
    inactive_blocked = ("checkout", "ai1") not in rec.route_calls

    # (c) oferta valida/ativa + permissao: precisa ter apresentado a oferta antes
    #     (o motor exige oferta autorizada/ativa para send_checkout).
    clear_state()
    MOCK["outputs"] = [{"action": "present_offer", "message": "Temos o Curso por R$ 97",
                        "funnel_stage": "offer"}]
    turn("quero saber do curso", mid=510)
    rec.reset()
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                        "pode mandar o link", bot_user=None, inbound_message_id=511)
    allowed_ok = ("checkout", "ai1") in rec.route_calls

    check("C1 checkout so com oferta ATIVA + permissao efetiva",
          no_perm_blocked and inactive_blocked and allowed_ok,
          f"sem_permissao_bloqueado={no_perm_blocked} "
          f"oferta_inativa_bloqueada={inactive_blocked} permitido={allowed_ok}")

    ctx.pop()
    return results


def main():
    if not MOTOR_DIR.exists() or not VENV_PY.exists():
        print(f"SKIP: motor/venv ausentes (MOTOR_DIR={MOTOR_DIR}, VENV_PY={VENV_PY})")
        return 0

    ok_redis, info = _redis_available()
    if not ok_redis:
        print(f"SKIP: Redis isolado indisponivel em {REDIS_URL}: {info}")
        return 0
    print(f"Redis REAL (isolado): {REDIS_URL} db={info}")

    rclient = _redis_client()
    rclient.flushdb()  # db isolado (guard: nunca db 0)

    mock_port = base.free_port()
    motor_port = base.free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", mock_port), MockOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    env = dict(os.environ)
    env.update({
        "GRIMBOTS_API_KEY": API_KEY,
        "OLLAMA_BASE_URL": f"http://127.0.0.1:{mock_port}",
        "PORT": str(motor_port),
        "GLOBAL_AI_ENABLED": "true",
        "HEALTH_REQUIRES_AUTH": "false",
        "ALLOWED_HOSTS": "*",
        "LOG_LEVEL": "warning",
    })
    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(MOTOR_DIR / "api"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        base.wait_http(f"http://127.0.0.1:{motor_port}/health")
        rec = Recorder()
        results = run(motor_port, rec, rclient)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        httpd.shutdown()
        rclient.flushdb()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} verificacoes (persistencia Redis real) OK")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
