"""Integração CONTROLADA contra o motor real (Grimbots AI Gateway) local.

Sobe:
  1. um mock do Ollama (HTTP stdlib) → devolve uma resposta JSON canônica;
  2. o motor via `uvicorn` (venv isolado do motor);
  3. o cliente real `GrimbotsAIService` (este processo) falando com o motor.

Cobre: v1.0 (baseline), v1.1 (memória + contexto), 409 takeover, extra=forbid
(422) e D11 (mesmo request_id 2x — evidencia que o motor NÃO deduplica).

Não depende de rede externa, não toca Redis/Telegram/DB.

Requer (via env, com defaults para o clone/venv de trabalho):
  GRIMBOTS_AI_MOTOR_DIR  (default: clone em /var/folders/.../opencode/grimbots-ai)
  GRIMBOTS_AI_VENV_PY    (default: .../opencode/t15venv/bin/python)

Se ausentes/inexistentes → SKIP (exit 0), nunca quebra o CI.

Roda:
  python3 tests/integration/test_motor_live.py
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
API_KEY = "itest-key"

MOCK_STATE = {"seen_prompts": [], "override": None}

MODEL_OUTPUT = {
    "message": "Olá! Tudo bem? Como posso ajudar?",
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
            MOCK_STATE["seen_prompts"].append(req.get("prompt", ""))
            resp = dict(MODEL_OUTPUT)
            if MOCK_STATE.get("override"):
                resp.update(MOCK_STATE["override"])
            self._send(200, {
                "response": json.dumps(resp),
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


def _mk_service(base_port):
    from internal_logic.services.ai_service import GrimbotsAIService
    return GrimbotsAIService(f"http://127.0.0.1:{base_port}", API_KEY, timeout=20.0)


def _base_kwargs(request_id="itest-req-1"):
    return {
        "request_id": request_id,
        "seller_id": "1",
        "bot_id": "140",
        "conversation_id": "c140-itest",
        "bot_user_id": "8142273932",
        "bot_config": {"name": "Maya", "personality": ["confiante"], "tone": "intimo"},
        "conversation_state": {"funnel_stage": "qualification",
                               "lead_temperature": "warm",
                               "human_takeover": False, "ai_enabled": True},
        "lead": {"name": "Ana", "interest": "curso", "objection": ""},
        "recent_messages": [{"role": "user", "content": "oi"}],
        "conversation_summary": "",
        "available_offers": [],
        "allowed_actions": ["continue", "ask_question", "present_offer"],
        "mode": "auto",
    }


def run_scenarios(port):
    from internal_logic.services.ai_service import build_payload, AIGatewayError
    svc = _mk_service(port)
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    # A) v1.0 baseline
    r = svc.respond(build_payload(**_base_kwargs("itest-req-v10")))
    check("A v1.0 baseline 200 + parse", r.message and r.intent == "saudacao",
          f"intent={r.intent}")

    # B) v1.1 (memória + contexto) — aceito pelo schema do motor
    kw = _base_kwargs("itest-req-v11")
    kw.update({
        "contract_version": "1.1",
        "agent_profile": {"name": "Maya", "goal": "qualificar"},
        "flow_resources": [{"type": "link", "label": "Aula", "url": "https://x/y"}],
        "context_policy": {"max_resources": 3},
        "last_assistant_message": "Ola!",
        "collected_information": {"cidade": "SP"},
        "questions_already_asked": ["Qual seu nome?"],
        "offers_already_presented": ["of1"],
        "turn_count": 3,
        "last_action": "ask_question",
    })
    r = svc.respond(build_payload(**kw))
    check("B v1.1 memoria+contexto 200", r.message and r.intent == "saudacao",
          f"msgs_enviadas={len(MOCK_STATE['seen_prompts'])}")

    # C) 409 takeover
    kw = _base_kwargs("itest-req-409")
    kw["conversation_state"] = {"funnel_stage": "human", "lead_temperature": "hot",
                                "human_takeover": True, "ai_enabled": True}
    try:
        svc.respond(build_payload(**kw))
        check("C 409 HUMAN_TAKEOVER_ACTIVE", False, "nao levantou erro")
    except AIGatewayError as err:
        check("C 409 HUMAN_TAKEOVER_ACTIVE", err.code == "HUMAN_TAKEOVER_ACTIVE",
              f"code={err.code} status={err.status}")

    # D) extra=forbid (campo desconhecido na raiz → 422 VALIDATION_ERROR)
    kw = _base_kwargs("itest-req-extra")
    payload = build_payload(**kw)
    payload["campo_desconhecido"] = 1
    try:
        svc.respond(payload)
        check("D extra=forbid 422", False, "nao levantou erro")
    except AIGatewayError as err:
        check("D extra=forbid 422", err.code == "VALIDATION_ERROR" and err.status == 422,
              f"code={err.code} status={err.status}")

    # E) D11 — mesmo request_id 2x: o motor DEDUPLICA (2º envio = replay, sem re-execucao)
    p = build_payload(**_base_kwargs("itest-req-dup"))
    calls_before = len(MOCK_STATE["seen_prompts"])
    r1 = svc.respond(p)
    calls_after_first = len(MOCK_STATE["seen_prompts"])
    r2 = svc.respond(dict(p))
    calls_after = len(MOCK_STATE["seen_prompts"])
    check("E D11 replay: 2o envio nao re-executa o modelo",
          bool(r1.message) and r1.message == r2.message
          and calls_after_first == calls_before + 1 and calls_after == calls_after_first,
          f"chamadas modelo: 1o=+{calls_after_first - calls_before} "
          f"2o=+{calls_after - calls_after_first}")

    # F) versao do servico exposta pelo /health (integracao)
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as h:
            health = json.loads(h.read().decode())
        check("F /health reporta versao do servico",
              bool(health.get("version")), f"version={health.get('version')}")
    except Exception as err:  # noqa: BLE001
        check("F /health reporta versao do servico", False, f"erro={err}")

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

    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(MOTOR_DIR / "api"), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    ok = False
    try:
        wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})\n")
        results = run_scenarios(motor_port)
        ok = all(r[1] for r in results)
        print(f"\n{sum(1 for r in results if r[1])}/{len(results)} cenarios OK")
    except Exception as exc:  # noqa: BLE001
        print(f"💥 erro no harness: {exc}")
        try:
            out = proc.stdout.read().decode() if proc.stdout else ""
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

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
