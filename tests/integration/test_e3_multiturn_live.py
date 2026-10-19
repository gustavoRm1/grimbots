"""Integração CONTROLADA multi-turno (E3) contra o motor real LOCAL.

Dependência externa: o motor Grimbots AI Gateway (`origin/main`) servido por
`uvicorn`, com o Ollama SUBSTITUÍDO por um mock HTTP local (saída roteirizada
por turno). NÃO é um teste offline: o cliente real `GrimbotsAIService` fala
HTTP com o motor, que aplica a camada E3 (decisão comercial).

O loop de plataforma (persistir estado + memória e reenviar no turno seguinte)
usa os helpers REAIS do Grimbots (`apply_state_update`, `resolve_funnel_stage`,
`BotManager._ai_memory_updates`, `BotManager._ai_memory_payload`) — os mesmos do
runtime. Sem Telegram/Redis/DB/DB real.

Requer (via env, defaults para o clone/venv de trabalho):
  GRIMBOTS_AI_MOTOR_DIR  (default: clone em /var/folders/.../opencode/grimbots-ai)
  GRIMBOTS_AI_VENV_PY    (default: .../opencode/t15venv/bin/python)

Se ausentes/inexistentes → SKIP (exit 0), nunca quebra o CI.

Roda:
  python3 tests/integration/test_e3_multiturn_live.py
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
API_KEY = "itest-e3-key"

MOCK = {"prompts": [], "outputs": []}

_DEFAULT_OUTPUT = {
    "message": "Certo! Me conta um pouco mais.",
    "intent": "saudacao",
    "lead_temperature": "warm",
    "funnel_stage": "connection",
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
        try:
            req = json.loads(body)
        except ValueError:
            req = {}
        if self.path.startswith("/api/generate"):
            MOCK["prompts"].append(req.get("prompt", ""))
            out = dict(_DEFAULT_OUTPUT)
            if MOCK["outputs"]:
                out.update(MOCK["outputs"].pop(0))
            self._send(200, {
                "response": json.dumps(out),
                "prompt_eval_count": 11,
                "eval_count": 22,
                "done": True,
            })
        else:
            self._send(404, {"error": "not found"})


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


def _svc(port):
    from internal_logic.services.ai_service import GrimbotsAIService
    return GrimbotsAIService(f"http://127.0.0.1:{port}", API_KEY, timeout=20.0)


def _payload(request_id, state, user_text, *, lead=None, offers=None,
             allowed_actions=None, conversation_state=None, context_policy=None,
             with_context=False):
    """Monta o REQUEST usando o MESMO builder do runtime (build_payload)."""
    from internal_logic.services.ai_service import build_payload
    from bot_manager import BotManager
    cs = conversation_state or {
        "funnel_stage": state.get("funnel_stage") or "new",
        "lead_temperature": state.get("lead_temperature") or "warm",
        "human_takeover": bool(state.get("human_takeover", False)),
        "ai_enabled": bool(state.get("ai_enabled", True)),
    }
    kwargs = dict(
        request_id=request_id, seller_id="1", bot_id="140",
        conversation_id="c140-e3", bot_user_id="8142273932",
        bot_config={"name": "Maya", "personality": ["confiante"], "tone": "intimo"},
        conversation_state=cs,
        lead=lead or {"name": "Ana", "interest": "", "objection": ""},
        recent_messages=[{"role": "user", "content": user_text}],
        conversation_summary="",
        available_offers=offers or [],
        allowed_actions=allowed_actions,
        mode="auto",
        contract_version="1.1",
    )
    if with_context:
        kwargs["context_policy"] = context_policy
        kwargs.update(BotManager._ai_memory_payload(state))
    return build_payload(**kwargs)


def _persist(state, result, user_text):
    """Aplica o turno ao estado vivo (mesma semântica do `_persist` do runtime)."""
    from internal_logic.services.ai_service import apply_state_update, resolve_funnel_stage
    from bot_manager import BotManager
    su = getattr(result, "state_update", None)
    if su:
        apply_state_update(state, su)
    state["lead_temperature"] = result.lead_temperature
    state["funnel_stage"] = (
        resolve_funnel_stage(state.get("funnel_stage"), result.funnel_stage,
                             (su or {}).get("funnel_stage"))
        or result.funnel_stage
    )
    state.update(BotManager._ai_memory_updates(
        state, result, result.action, result.message or "",
        result.next_question or "",
    ))


def run_scenarios(port):
    from internal_logic.services.ai_service import AIGatewayError
    svc = _svc(port)
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    def turn(rid, state, text, **kw):
        r = svc.respond(_payload(rid, state, text, **kw))
        return r

    OFFERS = [{"id": "of1", "name": "Curso", "price": "R$ 97",
               "checkout_url": "https://x/y", "active": True}]
    OPEN = ["continue", "ask_question", "present_offer", "send_checkout", "handoff_human"]

    # 1) Objeção de preço PERSISTIDA (multi-turno) impede send_checkout.
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar agora",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "collected_information": {"objection": "achei caro"},
          "offers_already_presented": []}
    r = turn("e3-obj-block", st, "quero fechar",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, allowed_actions=OPEN, with_context=True)
    check("1 objecao ativa (persistida) nao fecha checkout",
          r.action != "send_checkout" and r.action == "present_offer",
          f"action={r.action} reason={r.reason}")

    # 2) Objeção RESOLVIDA permite retomar o fechamento com contexto suficiente.
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar agora",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer",
          "collected_information": {"objection": "achei caro",
                                    "objection_resolved": True,
                                    "need_confirmado": True},
          "offers_already_presented": []}
    r = turn("e3-obj-resolved", st, "quero fechar",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, allowed_actions=OPEN, with_context=True)
    check("2 objecao resolvida permite send_checkout (contexto suficiente)",
          r.action == "send_checkout", f"action={r.action} reason={r.reason}")

    # 3) Pergunta já feita NÃO é repetida entre turnos (estado round-trip).
    asked = "Qual seu nome?"
    MOCK["outputs"] = [{"action": "ask_question", "message": asked,
                        "next_question": asked, "funnel_stage": "connection"},
                       {"action": "ask_question", "message": asked,
                        "next_question": asked, "funnel_stage": "connection"}]
    st = {"funnel_stage": "connection"}
    r1 = turn("e3-rep-1", st, "oi", allowed_actions=OPEN, with_context=True)
    _persist(st, r1, "oi")
    payload2 = _payload("e3-rep-2", st, "oi", allowed_actions=OPEN, with_context=True)
    r2 = svc.respond(payload2)
    _persist(st, r2, "oi")
    repeated = (r2.next_question or "").strip().casefold() == asked.casefold()
    check("3 pergunta ja feita nao se repete (memoria persistida no turno 2)",
          r1.action == "ask_question" and r2.action != "ask_question" and not repeated
          and asked in (payload2.get("questions_already_asked") or []),
          f"t1={r1.action} t2={r2.action} nq2={r2.next_question!r}")

    # 4) Estado retornado é persistido e ENVIADO no turno seguinte (funil avança).
    MOCK["outputs"] = [{"action": "continue", "message": "ok", "funnel_stage": "new"}]
    st = {"funnel_stage": "new"}
    r = turn("e3-state-1", st, "quero marketing",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             allowed_actions=OPEN, with_context=True)
    _persist(st, r, "quero marketing")
    payload2 = _payload("e3-state-2", st, "e depois?",
                        lead={"name": "Ana", "interest": "curso", "objection": ""},
                        allowed_actions=OPEN, with_context=True)
    check("4 estado (funnel_stage) persistido e reenviado no turno seguinte",
          (r.state_update or {}).get("funnel_stage") == "qualification"
          and st["funnel_stage"] == "qualification"
          and payload2["conversation_state"]["funnel_stage"] == "qualification",
          f"su={r.state_update} state={st['funnel_stage']} "
          f"next={payload2['conversation_state']['funnel_stage']}")

    # 5) `allowed_actions` ∩ `context_policy.allowed_actions` (intersecção E2).
    MOCK["outputs"] = [{"action": "continue", "message": "ok", "funnel_stage": "new"}]
    st = {"funnel_stage": "new"}
    r_open = turn("e3-policy-open", st, "quero marketing",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  allowed_actions=OPEN, with_context=True)
    st = {"funnel_stage": "new"}
    r_tight = turn("e3-policy-tight", st, "quero marketing",
                   lead={"name": "Ana", "interest": "curso", "objection": ""},
                   allowed_actions=OPEN, with_context=True,
                   context_policy={"allowed_actions": ["continue"]})
    check("5 context_policy.allowed_actions restringe (intersecção E2)",
          r_open.action == "ask_question" and r_tight.action == "continue",
          f"aberto={r_open.action} policy-tight={r_tight.action}")

    # 6) ai_enabled=false e human_takeover=true bloqueiam a geração (contrato).
    try:
        turn("e3-off", {"funnel_stage": "new"}, "oi", allowed_actions=OPEN,
             conversation_state={"funnel_stage": "new", "lead_temperature": "warm",
                                 "human_takeover": False, "ai_enabled": False})
        check("6a ai_enabled=false -> 409 AI_DISABLED_FOR_BOT", False, "sem erro")
    except AIGatewayError as err:
        check("6a ai_enabled=false -> 409 AI_DISABLED_FOR_BOT",
              err.code == "AI_DISABLED_FOR_BOT" and err.status == 409,
              f"code={err.code} status={err.status}")
    try:
        turn("e3-human", {"funnel_stage": "new"}, "oi", allowed_actions=OPEN,
             conversation_state={"funnel_stage": "new", "lead_temperature": "warm",
                                 "human_takeover": True, "ai_enabled": True})
        check("6b human_takeover=true -> 409 HUMAN_TAKEOVER_ACTIVE", False, "sem erro")
    except AIGatewayError as err:
        check("6b human_takeover=true -> 409 HUMAN_TAKEOVER_ACTIVE",
              err.code == "HUMAN_TAKEOVER_ACTIVE" and err.status == 409,
              f"code={err.code} status={err.status}")

    # 7) `funnel_stage` NÃO executa efeitos externos por si só: a mudança de
    #    estágio (state_update) acompanha uma ação decidida por contexto; não
    #    força checkout/handoff. (O motor não produz efeito externo.)
    MOCK["outputs"] = [{"action": "continue", "message": "ok", "funnel_stage": "new"}]
    st = {"funnel_stage": "new"}
    r = turn("e3-noeffect", st, "quero marketing",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             allowed_actions=OPEN, with_context=True)
    check("7 mudanca de funil nao dispara checkout/handoff sozinha",
          r.action in ("ask_question", "continue") and r.action not in (
              "send_checkout", "handoff_human")
          and (r.state_update or {}).get("funnel_stage") == "qualification",
          f"action={r.action} su={r.state_update}")

    # 8) E-P0/D6 — collected_information fim-a-fim: dentro do limite é
    #    preservado; acima do limite o cliente CLAMPA (sem 422 evitável no motor).
    MOCK["outputs"] = [{"action": "continue", "message": "ok",
                        "funnel_stage": "connection"},
                       {"action": "continue", "message": "ok",
                        "funnel_stage": "connection"}]
    info_ok = {f"k{i}": "v" * 200 for i in range(20)}
    p_ok = _payload("e3-ep0-ok", {"funnel_stage": "connection",
                                  "collected_information": info_ok},
                    "oi", allowed_actions=OPEN, with_context=True)
    r_ok = svc.respond(p_ok)
    info_big = {f"k{i}": "v" * 400 for i in range(40)}
    p_big = _payload("e3-ep0-big", {"funnel_stage": "connection",
                                    "collected_information": info_big},
                     "oi", allowed_actions=OPEN, with_context=True)
    r_big = svc.respond(p_big)
    ci_big = p_big.get("collected_information") or {}
    check("8 collected_information: limite preservado / excedente clampado (sem 422)",
          bool(r_ok.message) and bool(r_big.message)
          and p_ok["collected_information"] == info_ok
          and len(ci_big) == 20
          and all(len(v) <= 200 for v in ci_big.values()),
          f"ok_claves={len(p_ok['collected_information'])} "
          f"big_claves={len(ci_big)} big_maxlen="
          f"{max((len(v) for v in ci_big.values()), default=0)}")

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
        "HOST": "127.0.0.1",
        "PORT": str(motor_port),
        "GLOBAL_AI_ENABLED": "true",
        "HEALTH_REQUIRES_AUTH": "false",
        "ALLOWED_HOSTS": "*",
        "RATE_LIMIT_PER_MINUTE": "1000",
        "EXPOSE_DOCS": "false",
        "LOG_LEVEL": "warning",
    })

    import tempfile
    log = tempfile.NamedTemporaryFile("w+", suffix="-motor-e3.log", delete=False)

    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(MOTOR_DIR / "api"), env=env,
        stdout=log, stderr=subprocess.STDOUT,
    )

    ok = False
    try:
        wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})\n")
        results = run_scenarios(motor_port)
        ok = all(r[1] for r in results)
        print(f"\n{sum(1 for r in results if r[1])}/{len(results)} cenarios E3 OK")
    except Exception as exc:  # noqa: BLE001
        print(f"💥 erro no harness: {exc}")
        try:
            log.flush()
            with open(log.name, encoding="utf-8", errors="replace") as fh:
                out = fh.read()
            if out:
                print("--- motor output ---\n" + out[-3000:])
        except Exception:
            pass
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
