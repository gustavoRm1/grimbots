"""Fluxo REAL do Grimbots: persistência de estado + D11 + objeção multi-turno.

Diferente do harness (`test_motor_integration_live.py`), este teste dirige o
MÉTODO REAL `BotManager._handle_ai_turn` — não uma cópia — usando:
  - Redis FALSO com semântica WATCH/MULTI (mesma do `_ai_state_atomic` real);
  - Telegram MOCKADO (captura as mensagens enviadas, sem efeito externo);
  - Checkout MOCKADO (a saída 'checkout' do bloco é registrada, sem gerar PIX);
  - Motor REAL (uvicorn + `a54b9dd`) via HTTP, com Ollama mockado.

Objetivo: comprovar que o estado da conversa (incl. objeção de preço) PERSISTE
entre turnos no mecanismo real de estado, e que o D11 não gera envio duplicado
em retry/timeout.

Contexto: contra o motor `a54b9dd` SEM o fix de plataforma, este teste
reproduzia um defeito — a objeção de preço do lead nunca era persistida
(T1 FAIL) e o checkout não era bloqueado no turno seguinte (T2 FAIL). O fix
(objeção dona da PLATAFORMA, em `bot_manager._ai_apply_objection_state`) torna
T1-T4 OK; o teste fica como regressão do fluxo real.

Requer (env):
  GRIMBOTS_AI_MOTOR_DIR / GRIMBOTS_AI_VENV_PY (ver harness). Ausente -> SKIP.

Roda:
  GRIMBOTS_AI_MOTOR_DIR=.../motor-a54b9dd \
  GRIMBOTS_AI_VENV_PY=.../t15venv/bin/python \
  python3 tests/integration/test_grimbots_real_flow_live.py
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DEFAULT_MOTOR_DIR = "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/grimbots-ai"
DEFAULT_VENV_PY = "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/t15venv/bin/python"
MOTOR_DIR = Path(os.environ.get("GRIMBOTS_AI_MOTOR_DIR", DEFAULT_MOTOR_DIR))
VENV_PY = Path(os.environ.get("GRIMBOTS_AI_VENV_PY", DEFAULT_VENV_PY))
API_KEY = "rtest-motor-key"

MOCK = {"outputs": [], "mode": "json"}

_DEFAULT_OUTPUT = {
    "message": "Certo! Me conta um pouco mais.",
    "intent": "saudacao",
    "lead_temperature": "warm",
    "funnel_stage": "qualification",
    "action": "continue",
    "next_question": None,
    "handoff_human": False,
    "risk": "low",
}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class MockOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/version"):
            self._send(200, {"version": "mock-0.0"})
        elif self.path.startswith("/api/ps"):
            self._send(200, {"models": []})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        if not self.path.startswith("/api/generate"):
            self._send(404, {"error": "not found"})
            return
        try:
            json.loads(body)
        except ValueError:
            pass
        if MOCK["mode"] == "hang":
            time.sleep(30)
            self._send(200, {"response": "{}", "done": True})
            return
        if MOCK["mode"] == "garbage":
            self._send(200, {"response": "nao json {{{", "done": True})
            return
        out = dict(_DEFAULT_OUTPUT)
        if MOCK["outputs"]:
            out.update(MOCK["outputs"].pop(0))
        self._send(200, {"response": json.dumps(out),
                         "prompt_eval_count": 11, "eval_count": 22, "done": True})


def wait_http(url, timeout=30.0):
    import urllib.request
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return r.read().decode()
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.25)
    raise RuntimeError(f"motor nao respondeu em {url}: {last}")


# ── Redis falso com WATCH/MULTI (idêntico em semântica ao dos testes 6A) ─────


class FakeRedis:
    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._data = {}
        self._ver = {}
        self._exp = {}
        self._lock = threading.RLock()

    def _alive(self, key):
        exp = self._exp.get(key)
        if exp is not None and exp <= self._clock():
            self._data.pop(key, None)
            self._exp.pop(key, None)
            self._ver[key] = self._ver.get(key, 0) + 1
        return key in self._data

    def get(self, key):
        with self._lock:
            return self._data.get(key) if self._alive(key) else None

    def setex(self, key, ttl, value):
        with self._lock:
            self._data[key] = value
            self._exp[key] = self._clock() + ttl
            self._ver[key] = self._ver.get(key, 0) + 1

    def set(self, key, value, ex=None, nx=False):
        with self._lock:
            if nx and self._alive(key):
                return False
            self._data[key] = value
            self._exp[key] = (self._clock() + ex) if ex else None
            self._ver[key] = self._ver.get(key, 0) + 1
            return True

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)
            self._exp.pop(key, None)
            self._ver[key] = self._ver.get(key, 0) + 1

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, r):
        self.r = r
        self._watched = {}
        self._pending = []
        self._multi = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.reset()

    def watch(self, key):
        with self.r._lock:
            self._watched[key] = self.r._ver.get(key, 0)

    def get(self, key):
        with self.r._lock:
            return self.r._data.get(key) if self.r._alive(key) else None

    def multi(self):
        self._multi = True

    def setex(self, key, ttl, value):
        self._pending.append((key, value, ttl))

    def execute(self):
        from bot_manager import _RedisWatchError
        with self.r._lock:
            for k, v in self._watched.items():
                if self.r._ver.get(k, 0) != v:
                    raise _RedisWatchError()
            for key, value, ttl in self._pending:
                self.r._data[key] = value
                self.r._exp[key] = self.r._clock() + ttl if ttl else None
                self.r._ver[key] = self.r._ver.get(key, 0) + 1
            self._pending = []

    def reset(self):
        self._watched = {}
        self._pending = []
        self._multi = False


class Recorder:
    """Captura efeitos do turno real (Telegram/checkout) sem tocar serviços."""

    def __init__(self):
        self.sent = []          # mensagens enviadas ao lead
        self.route_calls = []   # ('checkout'|'handoff', step_id)

    def reset(self):
        self.sent.clear()
        self.route_calls.clear()


def _build_manager(monkeypatch_redis):
    import bot_manager as bm
    mgr = bm.BotManager.__new__(bm.BotManager)
    mgr.user_id = 7
    return mgr


def run_real_flow(motor_port, rec):
    import bot_manager as bm
    from bot_manager import BotManager

    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    # Contexto de app REAL com a flag de contrato v1.1 ligada (caminho de ativação).
    from flask import Flask
    app = Flask(__name__)
    app.config["GRIMBOTS_AI_CONTRACT"] = "v1.1"
    app.config["GRIMBOTS_AI_SHADOW"] = "off"
    app.config["SECRET_KEY"] = "rtest"
    app.config["GRIMBOTS_AI_SHADOW_SECRET"] = "rtest"
    ctx = app.app_context()
    ctx.push()

    fake = FakeRedis()
    rec_orig = bm.get_redis_connection
    bm.get_redis_connection = lambda: fake

    # Motor real via http (cliente real)
    from internal_logic.services import ai_service as ais
    orig_get = ais.get_ai_service
    svc = ais.GrimbotsAIService(f"http://127.0.0.1:{motor_port}", API_KEY, timeout=20.0)
    ais.get_ai_service = lambda: svc
    bm.get_ai_service = lambda: svc  # type: ignore

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7

    # Telegram mockado: registra e devolve sucesso
    def fake_send(token, chat_id, message, bot_id=None, save_message=False, **kw):
        rec.sent.append(message)
        return {"ok": True}

    mgr.send_telegram_message = fake_send  # type: ignore

    # Checkout/handoff mockados: registra a saída do bloco, NÃO executa fluxo.
    def fake_route(bot_id, token, config, chat_id, telegram_user_id, step, conn_key):
        target = (step.get("connections") or {}).get(conn_key)
        if not target:
            return False
        rec.route_calls.append((conn_key, step.get("id")))
        return True

    mgr._ai_route = fake_route  # type: ignore

    # Auditoria (DB) e shadow: no-ops (fail-open já cobre, mas evitamos ruído).
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

    bot_id, tuid = 140, "8142273932"

    def state():
        raw = fake.get(mgr._ai_state_key(bot_id, tuid))
        return json.loads(raw) if raw else {}

    def turn(text, mid=None):
        rec.reset()
        mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step, text,
                            bot_user=None, inbound_message_id=mid)
        return state()

    # ── TURNO 1: lead levanta a objeção de preço ────────────────────────────
    MOCK["outputs"] = [{"action": "present_offer", "message": "Temos o Curso por R$ 97",
                        "funnel_stage": "offer"}]
    st1 = turn("achei muito caro", mid=101)
    obj_after_t1 = (st1.get("collected_information") or {}).get("objection")
    obj_state_t1 = st1.get("objection")
    check("T1 objecao do lead persistida no estado real (collected_information)",
          bool(obj_after_t1) or bool(obj_state_t1),
          f"ci.objection={obj_after_t1!r} state.objection={obj_state_t1!r}")

    # ── TURNO 2: sinal de compra; objeção PERSISTIDA deve bloquear checkout ──
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    st2 = turn("quero fechar agora", mid=102)
    t2_actions = list(rec.route_calls)
    t2_has_checkout = ("checkout", "ai1") in t2_actions
    check("T2 objecao persistida bloqueia checkout no turno seguinte (estado real)",
          not t2_has_checkout,
          f"rotas={t2_actions} mensagens={rec.sent}")

    # ── TURNO 3: lead sinaliza que a objeção foi resolvida ──────────────────
    # A plataforma deve detectar o sinal de resolução no texto e persistir
    # `collected_information.objection_resolved` (sem hook manual).
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    st3 = turn("entendi o valor, vale a pena, pode mandar o link", mid=103)
    t3_has_checkout = ("checkout", "ai1") in rec.route_calls
    check("T3 objecao resolvida permite retomar checkout (roteia checkout real)",
          t3_has_checkout,
          f"rotas={rec.route_calls} mensagens={rec.sent} "
          f"ci={st3.get('collected_information')}")

    # ── TURNO 4 (D11): a MESMA mensagem não deve gerar efeito duplicado ─────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    rec.reset()
    mgr._handle_ai_turn(bot_id, "tok", config, 555, tuid, step,
                        "entendi o valor, vale a pena, pode mandar o link",
                        bot_user=None, inbound_message_id=103)  # mesmo id do T3
    check("T4 D11: reentrega da MESMA mensagem nao gera efeito duplicado",
          rec.route_calls == [] and rec.sent == [],
          f"rotas={rec.route_calls} mensagens={rec.sent}")

    bm.get_redis_connection = rec_orig
    ais.get_ai_service = orig_get
    ctx.pop()
    return results


def main():
    if not MOTOR_DIR.exists() or not VENV_PY.exists():
        print(f"SKIP: motor/venv ausentes (MOTOR_DIR={MOTOR_DIR}, VENV_PY={VENV_PY})")
        return 0

    mock_port = free_port()
    motor_port = free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", mock_port), MockOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    env = dict(os.environ)
    env.update({
        "GRIMBOTS_API_KEY": API_KEY,
        "OLLAMA_BASE_URL": f"http://127.0.0.1:{mock_port}",
        "HOST": "127.0.0.1", "PORT": str(motor_port),
        "GLOBAL_AI_ENABLED": "true", "HEALTH_REQUIRES_AUTH": "false",
        "ALLOWED_HOSTS": "*", "RATE_LIMIT_PER_MINUTE": "1000",
        "EXPOSE_DOCS": "false", "LOG_LEVEL": "warning",
    })

    import tempfile
    log = tempfile.NamedTemporaryFile("w+", suffix="-real-flow.log", delete=False)
    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(MOTOR_DIR / "api"), env=env, stdout=log, stderr=subprocess.STDOUT,
    )

    ok = False
    try:
        wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})")
        print(f"  MOTOR_DIR={MOTOR_DIR}\n")
        rec = Recorder()
        results = run_real_flow(motor_port, rec)
        ok = all(r[1] for r in results)
        print(f"\n{sum(1 for r in results if r[1])}/{len(results)} verificacoes de fluxo real OK")
    except Exception as exc:  # noqa: BLE001
        import traceback
        print(f"💥 erro no harness: {exc}")
        traceback.print_exc()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        httpd.shutdown()
        try:
            log.close()
        except Exception:
            pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
