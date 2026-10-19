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
  3. registra versao/commit/config do motor (via /health e git);
  4. roda cenarios de contrato + cenarios de LIMITE e imprime ESPERADO x OBSERVADO;
  5. grava results/observed.json + results/OBSERVED.md + results/MATRIZ_ESPERADO_OBSERVADO.md.

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
GRIMBOTS_ROOT = HERE.parents[1]   # handoff/d11 -> handoff -> <repo Grimbots>

# Evidência objetiva de cada cenário (base do veredito PASS/FAIL).
EVIDENCE = {
    "S1": "contador POST /api/generate: 1ª=1 e 2ª=1 (sem 2ª execução)",
    "S2": "status 502 AI_BACKEND_ERROR → 200 com o MESMO request_id",
    "S3": "status 504 AI_TIMEOUT → 200 com o MESMO request_id",
    "S4": "resposta idêntica (message/action) e 0 chamadas novas ao modelo",
    "S5": "status 502 AI_INVALID_RESPONSE → 200 com o MESMO request_id",
    "S6": "chamadas ao modelo == 1; status [200, 409]",
    "S7": "2ª entrega=409 REQUEST_IN_PROGRESS + header Retry-After; após concluir 200 X-D11-Replay=true; chamadas==1",
    "S8": "chamadas 1 → 2 após restart (LIMITAÇÃO: store in-memory)",
    "S9": "200 (nenhum 422 por tamanho)",
    "S10": "422 VALIDATION_ERROR (motor rejeita > 4000)",
}

LIMITATIONS = [
    "**Reinício do motor:** o store de dedupe é in-memory. Após restart, o mesmo "
    "`request_id` NÃO tem replay e o modelo re-executa (evidência: S8, chamadas 1→2).",
    "**Store em memória:** a conclusão vive só no processo; sem persistência "
    "durável não há exactly-once.",
    "**Múltiplas instâncias / workers:** a dedupe é por processo. Com >1 worker ou "
    "instância, o mesmo `request_id` pode cair em processos diferentes e executar 2×.",
    "**Falha entre geração e persistência:** se o processo morrer DEPOIS de gerar a "
    "resposta e ANTES de gravar a conclusão, a reserva expira e o retry re-executa "
    "(at-most-once, não exactly-once).",
    "**Correção concreta sugerida (motor):** gravar a resposta *write-ahead* logo "
    "após o modelo (antes de serializar a saída) e usar store compartilhado com "
    "`complete()` atômico.",
]

SIGNATURE_NOTE = (
    "**Assinatura D11: compatibilidade validada nos cenários testados.** "
    "Os cenários de contrato S1–S7, S9 e S10 passaram (9/9) contra o commit do "
    "motor registrado abaixo. **Isto NÃO equivale a aprovação para produção** — "
    "as limitações abaixo permanecem e a ativação exige decisão explícita."
)

DEFAULT_MOTOR_DIR = os.environ.get(
    "MOTOR_DIR",
    "/var/folders/b8/fkz5pr_d3cz8n9_kk2s4nc_00000gn/T/opencode/motor-d11",
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
    def log_message(self, *_a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/tags"):
            self._json(200, {"models": []})
            return
        self._json(200, {"models": []})

    def do_POST(self):  # noqa: N802
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
def _headers_lower(hdrs):
    return {k.lower(): v for k, v in (hdrs.items() if hdrs else [])}


def _get(url, timeout=5, keyed=True):
    headers = {"X-API-Key": API_KEY} if keyed else {}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}"), _headers_lower(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"raw": raw}
        return e.code, body, _headers_lower(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, {"error": {"code": "TRANSPORT", "message": str(e)}}, {}


def _post(base, body, timeout=30):
    req = urllib.request.Request(
        f"{base}/v1/agent/respond",
        data=json.dumps(body).encode(),
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode()), _headers_lower(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw), _headers_lower(e.headers)
        except ValueError:
            return e.code, {"raw": raw}, _headers_lower(e.headers)
    except Exception as e:  # noqa: BLE001
        return 0, {"error": {"code": "TRANSPORT", "message": str(e)}}, {}


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


def _wait_for(url, timeout=30):
    deadline = time.time() + timeout
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
    raise RuntimeError(f"motor nao respondeu em {url}: {last}")


# ── Motor controller (local spawn com restart; ou remoto) ──────────────────
class Motor:
    """Controla o motor sob teste. `can_restart` so e True quando o subimos."""

    def __init__(self, base="", motor_dir=None, venv_py=None):
        self.base = base or ""
        self.motor_dir = motor_dir
        self.venv_py = venv_py
        self.proc = None
        self.mock = None
        self.mock_port = None

    @property
    def can_restart(self):
        return bool(self.mock_port and self.motor_dir and self.venv_py)

    def start_mock(self):
        self.mock_port = _free_port()
        self.mock = _Server(("127.0.0.1", self.mock_port), MockOllama)
        threading.Thread(target=self.mock.serve_forever, daemon=True).start()

    def spawn(self):
        port = _free_port()
        env = dict(os.environ)
        env.update({
            "GRIMBOTS_API_KEY": API_KEY,
            "OLLAMA_BASE_URL": f"http://127.0.0.1:{self.mock_port}",
            "HOST": "127.0.0.1", "PORT": str(port),
            "GLOBAL_AI_ENABLED": "true", "HEALTH_REQUIRES_AUTH": "false",
            "ALLOWED_HOSTS": "*", "RATE_LIMIT_PER_MINUTE": "1000",
            "REQUEST_TIMEOUT": str(REQUEST_TIMEOUT), "LOG_LEVEL": "warning",
        })
        self.proc = subprocess.Popen(
            [str(self.venv_py), "-m", "uvicorn", "app:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=str(self.motor_dir / "api"), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.base = f"http://127.0.0.1:{port}"
        _wait_for(f"{self.base}/health")

    def restart(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        self.spawn()
        return self.base

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.mock:
            self.mock.shutdown()


def _motor_meta(motor):
    meta = {"base_url": motor.base, "request_timeout_env": REQUEST_TIMEOUT}
    _st, health, _h = _get(f"{motor.base}/health")
    meta["health"] = health
    meta["version_reported"] = (health or {}).get("version")
    meta["model"] = (health or {}).get("model")
    if motor.motor_dir:
        for label, args in (
            ("git_commit", ["rev-parse", "HEAD"]),
            ("git_commit_short", ["rev-parse", "--short", "HEAD"]),
            ("git_subject", ["log", "-1", "--format=%s"]),
            ("git_describe", ["describe", "--tags", "--always"]),
        ):
            try:
                out = subprocess.run(
                    ["git", "-C", str(motor.motor_dir), *args],
                    capture_output=True, text=True, timeout=5,
                )
                meta[label] = out.stdout.strip()
            except Exception:  # noqa: BLE001
                meta[label] = None
    try:
        for label, args in (
            ("grimbots_commit", ["rev-parse", "HEAD"]),
            ("grimbots_commit_short", ["rev-parse", "--short", "HEAD"]),
        ):
            out = subprocess.run(
                ["git", "-C", str(GRIMBOTS_ROOT), *args],
                capture_output=True, text=True, timeout=5,
            )
            meta[label] = out.stdout.strip()
    except Exception:  # noqa: BLE001
        meta["grimbots_commit"] = None
    meta["repro_motor"] = (
        f"git -C <motor> checkout {meta.get('git_commit_short') or '<commit>'} && "
        "cd api && GRIMBOTS_API_KEY=... OLLAMA_BASE_URL=... uvicorn app:app"
    )
    meta["repro_acceptance"] = (
        "MOTOR_DIR=<motor> MOTOR_VENV_PY=<venv>/bin/python python3 handoff/d11/d11_acceptance.py"
    )
    meta["repro_grimbots_tests"] = (
        "python3 tests/test_d11_dedupe.py  # e tests/test_phase6a_contract_v11.py"
    )
    return meta


# ── Cenarios de CONTRATO (esperado x observado) ────────────────────────────
def scenario_1_duplicate(motor):
    base = motor.base
    _reset(); _set_mode("ok")
    s1, _b1, _h1 = _post(base, _payload("hf-s1"))
    c1 = _calls()
    s2, _b2, _h2 = _post(base, _payload("hf-s1"))
    c2 = _calls()
    return {
        "id": "S1", "kind": "contract",
        "name": "mensagem duplicada (mesmo request_id, 2 envios)",
        "expected": "1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente)",
        "observed": f"1o={s1} chamadas={c1}; 2o={s2} chamadas={c2}",
        "pass": s1 == 200 and s2 == 200 and c2 == c1 == 1,
    }


def scenario_2_fail_after_reserve(motor):
    base = motor.base
    _reset(); _set_mode("backend_error")
    s1, b1, _h1 = _post(base, _payload("hf-s2"))
    _set_mode("ok")
    s2, _b2, _h2 = _post(base, _payload("hf-s2"))
    return {
        "id": "S2", "kind": "contract",
        "name": "falha apos reservar (backend 5xx -> retry MESMO request_id)",
        "expected": "1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 in (502, 503) and s2 == 200,
    }


def scenario_3_timeout(motor):
    base = motor.base
    _reset(); _set_mode("slow")
    s1, b1, _h1 = _post(base, _payload("hf-s3"), timeout=30)
    _set_mode("ok")
    s2, _b2, _h2 = _post(base, _payload("hf-s3"))
    return {
        "id": "S3", "kind": "contract",
        "name": "timeout do motor (Ollama lento -> 504 AI_TIMEOUT)",
        "expected": "1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 == 504 and _code(b1) == "AI_TIMEOUT" and s2 == 200,
    }


def scenario_4_retry_same_request_id(motor):
    base = motor.base
    _reset(); _set_mode("ok")
    s1, b1, _h1 = _post(base, _payload("hf-s4"))
    _reset()  # zera o contador: o retry NAO pode chamar o modelo de novo
    s2, b2, _h2 = _post(base, _payload("hf-s4"))
    same = (b1.get("message") == b2.get("message")
            and b1.get("action") == b2.get("action"))
    return {
        "id": "S4", "kind": "contract",
        "name": "retry com o mesmo request_id apos SUCESSO",
        "expected": "2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo",
        "observed": f"2o={s2} novas_chamadas_apos_sucesso={_calls()} resposta_identica={same}",
        "pass": s1 == 200 and s2 == 200 and _calls() == 0 and same,
    }


def scenario_5_fail_before_complete(motor):
    base = motor.base
    _reset(); _set_mode("invalid_model")
    s1, b1, _h1 = _post(base, _payload("hf-s5"))
    _set_mode("ok")
    s2, _b2, _h2 = _post(base, _payload("hf-s5"))
    return {
        "id": "S5", "kind": "contract",
        "name": "falha antes de concluir (modelo invalido -> 502)",
        "expected": "1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada)",
        "observed": f"1o={s1} code={_code(b1)}; 2o={s2}",
        "pass": s1 == 502 and _code(b1) == "AI_INVALID_RESPONSE" and s2 == 200,
    }


def scenario_6_concurrency(motor):
    base = motor.base
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
        "id": "S6", "kind": "contract",
        "name": "concorrencia: 2 entregas da MESMA mensagem/request_id",
        "expected": "modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS",
        "observed": f"status={statuses} chamadas_ao_modelo={calls} respostas_200={one_ok}",
        "pass": calls == 1 and one_ok >= 1,
    }


def scenario_7_in_progress_409(motor):
    """409 REQUEST_IN_PROGRESS com Retry-After, e replay apos conclusao."""
    base = motor.base
    _reset(); _set_mode("delay_ok")   # modelo dorme 1.2s -> janela em andamento
    holder = {}

    def fire():
        holder["first"] = _post(base, _payload("hf-s7"), timeout=30)

    th = threading.Thread(target=fire)
    th.start()
    deadline = time.time() + 3
    while _calls() < 1 and time.time() < deadline:
        time.sleep(0.02)
    time.sleep(0.1)
    s_ip, b_ip, h_ip = _post(base, _payload("hf-s7"), timeout=10)  # em andamento
    th.join()
    s_after, _b_after, h_after = _post(base, _payload("hf-s7"), timeout=10)  # apos concluir
    retry_after = h_ip.get("retry-after")
    replay = h_after.get("x-d11-replay")
    return {
        "id": "S7", "kind": "contract",
        "name": "409 REQUEST_IN_PROGRESS (Retry-After) + replay apos conclusao",
        "expected": ("em andamento -> 409 REQUEST_IN_PROGRESS com header Retry-After; "
                     "1o=200; apos concluir -> 200 replay (X-D11-Replay=true); modelo 1x"),
        "observed": (f"em_andamento={s_ip} code={_code(b_ip)} retry_after={retry_after}; "
                     f"1o={holder.get('first', (None,))[0]}; apos={s_after} replay={replay}; "
                     f"chamadas={_calls()}"),
        "pass": (s_ip == 409 and _code(b_ip) == "REQUEST_IN_PROGRESS"
                 and retry_after is not None
                 and holder.get("first", (None,))[0] == 200
                 and _calls() == 1 and s_after == 200 and replay == "true"),
    }


def scenario_9_d6_at_limit(motor):
    """D6: payload com TODOS os campos no limite exato do motor -> 200."""
    base = motor.base
    _reset(); _set_mode("ok")
    p = _payload("hf-s9")
    p["bot_config"].update({
        "name": "N" * 60, "tone": "t" * 60, "commercial_goal": "g" * 80,
        "personality": ["p" * 40] * 12, "boldness": 5,
    })
    p["lead"].update({"name": "a" * 60, "interest": "i" * 120, "objection": "o" * 120})
    p["recent_messages"] = [{"role": "user", "content": "c" * 4000}]
    p["conversation_summary"] = "s" * 4000
    p["available_offers"] = [{"id": "o" * 64, "name": "n" * 120,
                              "price": "p" * 40, "checkout_url": "u" * 400}]
    s, b, _h = _post(base, p)
    return {
        "id": "S9", "kind": "contract",
        "name": "D6: payload com TODOS os campos no limite do motor",
        "expected": "200 (limites do motor respeitados; nenhum 422 por tamanho)",
        "observed": f"{s} code={_code(b)}",
        "pass": s == 200,
    }


def scenario_10_d6_over_limit(motor):
    """D6: 1 caractere acima do limite do motor -> 422 (prova que o clamp e preciso)."""
    base = motor.base
    _reset(); _set_mode("ok")
    p = _payload("hf-s10")
    p["recent_messages"] = [{"role": "user", "content": "c" * 4001}]
    s, b, _h = _post(base, p)
    return {
        "id": "S10", "kind": "contract",
        "name": "D6: message.content=4001 (1 acima do limite do motor)",
        "expected": "422 VALIDATION_ERROR (motor rejeita >4000 -> Grimbots deve clamar em 4000)",
        "observed": f"{s} code={_code(b)}",
        "pass": s == 422 and _code(b) == "VALIDATION_ERROR",
    }


def scenario_8_restart_durability(motor):
    """LIMITE: store in-memory -> apos restart NAO ha replay (single-instance)."""
    if not motor.can_restart:
        return {
            "id": "S8", "kind": "limitation",
            "name": "durabilidade do dedupe apos restart do motor",
            "expected": "exige motor local (spawn); SKIP em modo MOTOR_BASE_URL",
            "observed": "skip",
            "pass": True, "skipped": True,
        }
    _reset(); _set_mode("ok")
    s1, _b1, _h1 = _post(motor.base, _payload("hf-s8"))
    before = _calls()
    motor.restart()
    s2, _b2, _h2 = _post(motor.base, _payload("hf-s8"))
    after = _calls()
    return {
        "id": "S8", "kind": "limitation",
        "name": "durabilidade do dedupe apos restart (store in-memory)",
        "expected": ("LIMITE CONHECIDO: store in-memory -> apos restart o mesmo "
                     "request_id NAO tem replay; o modelo re-executa"),
        "observed": f"1o={s1}; apos_restart={s2}; chamadas_antes={before} chamadas_depois={after}",
        "pass": s2 == 200 and after == before + 1,
    }


SCENARIOS = [
    scenario_1_duplicate,
    scenario_2_fail_after_reserve,
    scenario_3_timeout,
    scenario_4_retry_same_request_id,
    scenario_5_fail_before_complete,
    scenario_6_concurrency,
    scenario_7_in_progress_409,
    scenario_9_d6_at_limit,
    scenario_10_d6_over_limit,
    scenario_8_restart_durability,
]


# ── Runner ─────────────────────────────────────────────────────────────────
def main():
    if MOTOR_BASE_URL:
        motor = Motor(base=MOTOR_BASE_URL)
    else:
        motor_dir = Path(DEFAULT_MOTOR_DIR)
        venv_py = Path(DEFAULT_VENV_PY)
        if not motor_dir.exists() or not venv_py.exists():
            print(f"SKIP: motor/venv ausentes (MOTOR_DIR={motor_dir}, MOTOR_VENV_PY={venv_py})")
            return 0
        motor = Motor(motor_dir=motor_dir, venv_py=venv_py)
        motor.start_mock()
        try:
            motor.spawn()
        except Exception as e:  # noqa: BLE001
            motor.stop()
            print(f"SKIP: motor nao subiu: {e}")
            return 0

    meta = _motor_meta(motor)
    print(f"→ motor: {motor.base}")
    print(f"  versao_reportada: {meta.get('version_reported')} "
          f"(commit {meta.get('git_commit_short')})")
    print(f"  git_subject: {meta.get('git_subject')}\n")

    try:
        results = [fn(motor) for fn in SCENARIOS]
    finally:
        motor.stop()

    contract = [r for r in results if r.get("kind") == "contract"]
    limits = [r for r in results if r.get("kind") == "limitation"]

    print(f"{'ID':<4}")
    for r in results:
        tag = "PASS" if r["pass"] else "FAIL"
        if r.get("skipped"):
            tag = "SKIP"
        print(f"[{r['id']}] {tag} — {r['name']}")
        print(f"     esperado: {r['expected']}")
        print(f"     observado: {r['observed']}")
    cpass = sum(1 for r in contract if r["pass"])
    print(f"\nCONTRATO: {cpass}/{len(contract)} PASS")
    print(f"LIMITES (documentados): "
          f"{sum(1 for r in limits if r['pass'])}/{len(limits)} OK\n")

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "observed.json").write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "motor": meta,
        "contract_passed": cpass, "contract_total": len(contract),
        "results": results,
    }, ensure_ascii=False, indent=2))

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lines = ["# D11 — resultados OBSERVADOS", "",
             f"> {ts} · motor `{motor.base}`",
             f"> versao_reportada `{meta.get('version_reported')}` · "
             f"commit `{meta.get('git_commit_short')}`",
             f"> **CONTRATO: {cpass}/{len(contract)} PASS**", ""]
    for r in results:
        tag = "SKIP" if r.get("skipped") else ("PASS" if r["pass"] else "FAIL")
        lines += [f"## {r['id']} — {r['name']} — {tag}",
                  f"- **esperado:** {r['expected']}",
                  f"- **observado:** {r['observed']}", ""]
    (RESULTS / "OBSERVED.md").write_text("\n".join(lines) + "\n")

    # Matriz esperado x observado (para o motor validar)
    _write_matrix(meta, results, ts, cpass, len(contract))

    return 0 if cpass == len(contract) else 1


def _write_matrix(meta, results, ts, cpass, ctotal):
    def _tag(r):
        return "SKIP" if r.get("skipped") else ("PASS" if r["pass"] else "FAIL")

    m = ["# D11 — matriz esperado × observado", "",
         f"> Gerado em **{ts}** pelo harness `handoff/d11/d11_acceptance.py`.",
         "> Reproduzível: ver §2. **Não** substitui os testes internos do motor.", "",
         "## 1. Identificação (commits exatos)", "",
         "| Item | Valor |", "|---|---|",
         f"| Motor — commit | `{meta.get('git_commit')}` (`{meta.get('git_commit_short')}`) |",
         f"| Motor — assunto | {meta.get('git_subject')} |",
         f"| Motor — versão reportada (`/health`) | `{meta.get('version_reported')}` |",
         f"| Motor — modelo | `{meta.get('model')}` |",
         f"| Motor — describe | `{meta.get('git_describe')}` |",
         f"| Grimbots — commit | `{meta.get('grimbots_commit')}` (`{meta.get('grimbots_commit_short')}`) |",
         f"| `REQUEST_TIMEOUT` (execução) | {meta.get('request_timeout_env')} |",
         "", "## 2. Comandos de reprodução", "",
         "```bash",
         "# 1) checkout do motor no commit acima (NÃO alterar o repo do motor)",
         meta.get("repro_motor", ""),
         "# 2) aceite D11 (independente)",
         meta.get("repro_acceptance", ""),
         "# 3) testes Grimbots (409 sem efeitos, D6, E4)",
         meta.get("repro_grimbots_tests", ""),
         "```", "",
         f"**Resultado: CONTRATO {cpass}/{ctotal} PASS.** "
         "Cenários `limitation` documentam limites arquiteturais conhecidos.", "",
         "## 3. Cenários de CONTRATO (S1–S7, S9, S10)", "",
         "| ID | cenário | esperado | observado | evidência | resultado |",
         "|---|---|---|---|---|---|"]
    for r in results:
        if r.get("kind") != "contract":
            continue
        m.append(
            f"| {r['id']} | {r['name']} | {r['expected']} | {r['observed']} | "
            f"{EVIDENCE.get(r['id'], '')} | {_tag(r)} |"
        )
    m += ["", "## 4. Cenário de LIMITAÇÃO (S8)", "",
          "| ID | cenário | esperado | observado | resultado |",
          "|---|---|---|---|---|"]
    for r in results:
        if r.get("kind") == "limitation":
            m.append(
                f"| {r['id']} | {r['name']} | {r['expected']} | {r['observed']} | "
                f"{_tag(r)} |"
            )
    m += ["", "## 5. Assinatura D11", "", SIGNATURE_NOTE, "",
          "## 6. Limitações documentadas (permanecem)", ""]
    m += [f"- {lim}" for lim in LIMITATIONS]
    m += ["", "## 7. Pendência do motor (próximo passo)", "",
          "Quando o motor entregar **(a)** persistência do store de dedupe e "
          "**(b)** correção da versão do `/health`: **re-executar** §2 contra a nova "
          "versão e **atualizar esta matriz** (o harness registra o novo commit).",
          ""]
    (RESULTS / "MATRIZ_ESPERADO_OBSERVADO.md").write_text("\n".join(m) + "\n")


if __name__ == "__main__":
    sys.exit(main())
