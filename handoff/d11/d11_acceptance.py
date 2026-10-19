#!/usr/bin/env python3
"""D11 — hand-off executavel para o desenvolvedor da IA (Grimbots AI Gateway).

OBJETIVO
--------
Provar/definir a idempotencia do motor por `request_id`: uma MESMA tentativa
(`request_id` identico) NAO pode disparar duas vezes o efeito que ela dirige
(mensagem / avanco de fluxo / checkout / handoff). O motor e a fonte do efeito
porque devolve a `action` que a plataforma executa.

Este script NAO altera o repositorio do motor. Ele:
  1. sobe um mock do Ollama (stdlib) que CONTABILIZA chamadas ao modelo;
  2. sobe o motor via uvicorn (do checkout do dev, por env) OU usa MOTOR_BASE_URL;
  3. roda 6 cenarios de contrato e imprime ESPERADO x OBSERVADO;
  4. grava results/observed.json + results/OBSERVED.md.

Rode (a partir da raiz deste pacote):
  MOTOR_DIR=/caminho/grimbots-ai \
  MOTOR_VENV_PY=/caminho/venv/bin/python \
  python3 d11_acceptance.py

  # ou, contra um motor ja em execucao:
  MOTOR_BASE_URL=http://127.0.0.1:8000 GRIMBOTS_API_KEY=... python3 d11_acceptance.py

Sem dependencias externas (apenas stdlib). Nao toca Redis/Telegram/DB.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

DEFAULT_MOTOR_DIR = os.environ.get(
    "MOTOR_DIR",
    "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/grimbots-ai",
)
DEFAULT_VENV_PY = os.environ.get(
    "MOTOR_VENV_PY",
    "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/t15venv/bin/python",
)
MOTOR_BASE_URL = os.environ.get("MOTOR_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("GRIMBOTS_API_KEY", "handoff-key")
REQUEST_TIMEOUT = 5          # timeout do motor para o Ollama (nesta execucao)
SLOW_SLEEP = REQUEST_TIMEOUT + 3

STATE = {"mode": "ok", "calls": 0}
CANONICAL = {
    "message": "Ola! Tudo bem? Como posso ajudar?",
    "intent": "saudacao",
    "lead_temperature": "warm",
    "funnel_stage": "connection",
    "action": "continue",
    "next_question": None,
    "handoff_human": False,
    "risk": "low",
}


# ── Mock Ollama (conta chamadas; modos de falha deterministicos) ───────────
class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MockOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/version"):
            self._json(200, {"version": "mock-0.0"})
        elif self.path.startswith("/api/ps"):
            self._json(200, {"models": []})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/api/generate"):
            self._json(404, {"error": "not found"})
            return
        STATE["calls"] += 1
        mode = STATE["mode"]
        if mode == "backend_error":
            self._json(500, {"error": "boom"})
            return
        if mode == "slow":
            time.sleep(SLOW_SLEEP)
        elif mode == "delay_ok":
            time.sleep(1.2)
        if mode == "invalid_model":
            self._json(200, {"response": "", "done": True})
            return
        self._json(200, {
            "response": json.dumps(CANONICAL),
            "prompt_eval_count": 11, "eval_count": 22, "done": True,
        })


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _reset():
    STATE["calls"] = 0


def _set_mode(mode):
    STATE["mode"] = mode


def _calls():
    return STATE["calls"]


# ── HTTP (stdlib) ──────────────────────────────────────────────────────────
def _post(base, body, timeout=30):
    req = urllib.request.Request(
        f"{base}/v1/agent/respond",
        data=json.dumps(body).encode(),
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": {"code": "TRANSPORT", "message": str(e)}}


def _code(body):
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return err.get("code", "")
    return ""


def _payload(request_id, text="oi"):
    return {
        "request_id": request_id,
        "seller_id": "1", "bot_id": "140",
        "conversation_id": "c140-handoff", "bot_user_id": "8142273932",
        "mode": "auto",
        "bot_config": {"name": "Maya", "personality": ["confiante"], "tone": "intimo"},
        "conversation_state": {"funnel_stage": "qualification", "lead_temperature": "warm",
                               "human_takeover": False, "ai_enabled": True},
        "lead": {"name": "Ana", "interest": "curso", "objection": ""},
        "recent_messages": [{"role": "user", "content": text}],
        "conversation_summary": "",
        "available_offers": [],
        "allowed_actions": ["continue", "ask_question", "present_offer",
                            "send_checkout", "handoff_human", "pause", "do_not_respond"],
    }


def _wait_http(url, timeout=40.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(0.25)
    raise RuntimeError(f"motor nao respondeu em {url}: {last}")


# ── Cenarios (expected x observed) ─────────────────────────────────────────
def scenario_1_duplicate(base):
    _reset(); _set_mode("ok")
    s1, b1 = _post(base, _payload("hf-s1"))
    c1 = _calls()
    s2, b2 = _post(base, _payload("hf-s1"))
    c2 = _calls()
    return {
        "id": "S1", "name": "mensagem duplicada (mesmo request_id, 2 envios)",
        "expected": "1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente)",
        "observed": f"1o={s1} chamadas={c1}; 2o={s2} chamadas={c2}",
        "pass": s1 == 200 and s2 == 200 and c2 == c1 == 1,
    }


def scenario_2_fail_after_reserve(base):
    _reset(); _set_mode("backend_error")
    s1, b1 = _post(base, _payload("hf-s2"))
    _set_mode("ok")
    s2, b2 = _post(base, _payload("hf-s2"))
    return {
        "id": "S2", "name": "falha apos reservar (backend 5xx -> retry MESMO request_id)",
        "expected": "1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 in (502, 503) and s2 == 200,
    }


def scenario_3_timeout(base):
    _reset(); _set_mode("slow")
    s1, b1 = _post(base, _payload("hf-s3"), timeout=30)
    _set_mode("ok")
    s2, b2 = _post(base, _payload("hf-s3"))
    return {
        "id": "S3", "name": "timeout do motor (Ollama lento -> 504 AI_TIMEOUT)",
        "expected": "1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 == 504 and _code(b1) == "AI_TIMEOUT" and s2 == 200,
    }


def scenario_4_retry_same_request_id(base):
    _reset(); _set_mode("ok")
    s1, b1 = _post(base, _payload("hf-s4"))
    _reset()  # zera o contador: o retry NAO pode chamar o modelo de novo
    s2, b2 = _post(base, _payload("hf-s4"))
    same = (b1.get("message") == b2.get("message")
            and b1.get("action") == b2.get("action"))
    return {
        "id": "S4", "name": "retry com o mesmo request_id apos SUCESSO",
        "expected": "2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo",
        "observed": f"2o={s2} novas_chamadas_apos_sucesso={_calls()} resposta_identica={same}",
        "pass": s1 == 200 and s2 == 200 and _calls() == 0 and same,
    }


def scenario_5_fail_before_complete(base):
    _reset(); _set_mode("invalid_model")
    s1, b1 = _post(base, _payload("hf-s5"))
    _set_mode("ok")
    s2, b2 = _post(base, _payload("hf-s5"))
    return {
        "id": "S5", "name": "falha antes de concluir (modelo invalido -> 502)",
        "expected": "1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 == 502 and _code(b1) == "AI_INVALID_RESPONSE" and s2 == 200,
    }


def scenario_6_concurrency(base):
    _reset(); _set_mode("delay_ok")
    out = {}

    def fire(tag):
        out[tag] = _post(base, _payload("hf-s6"), timeout=30)

    threads = [threading.Thread(target=fire, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    statuses = sorted(out[t][0] for t in out)
    calls = _calls()
    one_ok = sum(1 for t in out if out[t][0] == 200)
    return {
        "id": "S6", "name": "concorrencia: 2 entregas da MESMA mensagem/request_id",
        "expected": "modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS",
        "observed": f"status={statuses} chamadas_ao_modelo={calls} respostas_200={one_ok}",
        "pass": calls == 1 and one_ok >= 1,
    }


SCENARIOS = [
    scenario_1_duplicate,
    scenario_2_fail_after_reserve,
    scenario_3_timeout,
    scenario_4_retry_same_request_id,
    scenario_5_fail_before_complete,
    scenario_6_concurrency,
]


# ── Runner ─────────────────────────────────────────────────────────────────
def _spawn_motor():
    motor_dir = Path(DEFAULT_MOTOR_DIR)
    venv_py = Path(DEFAULT_VENV_PY)
    if not motor_dir.exists() or not venv_py.exists():
        return None, None, f"motor/venv ausentes (MOTOR_DIR={motor_dir}, MOTOR_VENV_PY={venv_py})"
    mock_port, motor_port = _free_port(), _free_port()
    httpd = _Server(("127.0.0.1", mock_port), MockOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    env = dict(os.environ)
    env.update({
        "GRIMBOTS_API_KEY": API_KEY,
        "OLLAMA_BASE_URL": f"http://127.0.0.1:{mock_port}",
        "HOST": "127.0.0.1", "PORT": str(motor_port),
        "GLOBAL_AI_ENABLED": "true", "HEALTH_REQUIRES_AUTH": "false",
        "ALLOWED_HOSTS": "*", "RATE_LIMIT_PER_MINUTE": "1000",
        "REQUEST_TIMEOUT": str(REQUEST_TIMEOUT), "LOG_LEVEL": "warning",
    })
    proc = subprocess.Popen(
        [str(venv_py), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(motor_dir / "api"), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{motor_port}"
    try:
        _wait_for(f"{base}/health")
    except Exception as e:  # noqa: BLE001
        proc.terminate()
        return None, httpd, f"motor nao subiu: {e}"
    return (base, proc), httpd, None


def _wait_for(url):
    deadline = time.time() + 30
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"X-API-Key": API_KEY}), timeout=2
            ) as r:
                if r.status == 200:
                    return
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(0.25)
    raise RuntimeError(last)


def main():
    base = MOTOR_BASE_URL
    httpd = proc = None
    if not base:
        spawned, httpd, err = _spawn_motor()
        if err:
            print(f"SKIP: {err}")
            return 0
        base, proc = spawned
    print(f"→ motor: {base}\n")

    try:
        results = [fn(base) for fn in SCENARIOS]
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if httpd:
            httpd.shutdown()

    print(f"{'ID':<4}{'ESPERADO':<1}")
    for r in results:
        print(f"[{r['id']}] {'PASS' if r['pass'] else 'FAIL'} — {r['name']}")
        print(f"     esperado: {r['expected']}")
        print(f"     observado: {r['observed']}")
    passed = sum(1 for r in results if r["pass"])
    print(f"\n{passed}/{len(results)} cenarios PASS\n")

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "observed.json").write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "motor_base_url": base,
        "passed": passed, "total": len(results), "results": results,
    }, ensure_ascii=False, indent=2))
    lines = ["# D11 — resultados OBSERVADOS", "",
             f"> {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} · motor `{base}`",
             f"> **{passed}/{len(results)} PASS**", ""]
    for r in results:
        lines += [f"## {r['id']} — {r['name']} — {'PASS' if r['pass'] else 'FAIL'}",
                  f"- **esperado:** {r['expected']}",
                  f"- **observado:** {r['observed']}", ""]
    (RESULTS / "OBSERVED.md").write_text("\n".join(lines) + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
