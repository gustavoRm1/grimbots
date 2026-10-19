"""E5 — integração da execução SHADOW contra o motor real (LOCAL).

Prova, contra o motor real (uvicorn + Ollama roteirizado), que:
  - o payload v1.1 do shadow é ACEITO (sem 422) e produz decisão;
  - `run_shadow` registra a comparação (proposta v1.1 × ação real v1.0);
  - o shadow NÃO executa efeito algum (só chama `respond`);
  - falha do motor é fail-open (linha SHADOW_ERROR, sem exceção).

Reusa a infra do harness E3 (`test_e3_multiturn_live`) — nenhuma duplicação de
launch. Reusa `BotManager._ai_memory_payload` e `ai_service.build_payload`.

Se motor/venv ausentes → SKIP (exit 0).

Roda:
  python3 tests/integration/test_e5_shadow_live.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_e3_multiturn_live as infra  # noqa: E402


def _payload_v10(rid, state, user_text):
    from internal_logic.services.ai_service import build_payload
    return build_payload(
        request_id=rid, seller_id="1", bot_id="140", conversation_id="c140-e5",
        bot_user_id="8142273932",
        bot_config={"name": "Maya", "personality": ["confiante"], "tone": "intimo"},
        conversation_state={"funnel_stage": state.get("funnel_stage") or "new",
                            "lead_temperature": "warm", "human_takeover": False,
                            "ai_enabled": True},
        lead={"name": "Ana", "interest": "", "objection": ""},
        recent_messages=[{"role": "user", "content": user_text}],
        conversation_summary="",
        available_offers=[],
        mode="auto", contract_version="1.0",
    )


def _payload_v11(rid, state, user_text):
    from internal_logic.services.ai_service import build_payload
    from bot_manager import BotManager
    return build_payload(
        request_id=rid, seller_id="1", bot_id="140", conversation_id="c140-e5",
        bot_user_id="8142273932",
        bot_config={"name": "Maya", "personality": ["confiante"], "tone": "intimo"},
        conversation_state={"funnel_stage": state.get("funnel_stage") or "new",
                            "lead_temperature": "warm", "human_takeover": False,
                            "ai_enabled": True},
        lead={"name": "Ana", "interest": "curso", "objection": ""},
        recent_messages=[{"role": "user", "content": user_text}],
        conversation_summary="",
        available_offers=[],
        mode="shadow", contract_version="1.1",
        **BotManager._ai_memory_payload(state),
    )


def run_scenarios(port):
    from internal_logic.services import ai_shadow as shadow
    svc = infra._svc(port)
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    # ── 1) shadow v1.1 aceito pelo motor e comparado com a ação v1.0 ────────
    infra.MOCK["outputs"] = [{"action": "ask_question", "message": "me conta",
                              "next_question": "qual seu objetivo?",
                              "funnel_stage": "connection"}]
    st = {"funnel_stage": "new", "collected_information": {}, "questions_already_asked": []}
    real = svc.respond(_payload_v10("e5-real-1", st, "oi"))
    infra.MOCK["outputs"] = [{"action": "present_offer", "message": "tem o plano X",
                              "next_question": None, "funnel_stage": "offer"}]
    shadow_payload = _payload_v11("shadow-e5-1", st, "oi")

    rows = []
    shadow.run_shadow(
        respond=svc.respond, payload=shadow_payload,
        observed={"action": real.action, "intent": real.intent,
                  "funnel_stage": real.funnel_stage,
                  "lead_temperature": real.lead_temperature, "source": "v1.0_production"},
        bot_id=140, lead_ref=shadow.lead_reference("8142273932", "k"),
        request_id="shadow-e5-1",
        meta={"contract_version": "1.1", "motor_commit": "origin/main"},
        record=lambda r: rows.append(r), secret="k", include_text=False,
    )
    from internal_logic.services.ai_service import ACTIONS
    row = rows[0] if rows else {}
    check("1 shadow v1.1 aceito + comparação gravada (proposta×real)",
          len(rows) == 1 and row.get("proposed_action") in ACTIONS
          and row.get("observed_action") == real.action
          and row.get("action_match") is (row.get("proposed_action") == real.action)
          and row.get("error_code") is None,
          f"proposto={row.get('proposed_action')} real={real.action} "
          f"match={row.get('action_match')}")

    # ── 2) sem PII crua no contexto registrado ─────────────────────────────
    blob = row.get("context_json") or ""
    check("2 contexto registrado sem PII crua (sem nome/telegram)",
          "8142273932" not in blob and "Ana" not in blob and bool(row.get("context_digest")),
          f"digest_ok={bool(row.get('context_digest'))}")

    # ── 3) falha do motor é fail-open (nenhuma exceção; linha de erro) ─────
    from internal_logic.services.ai_service import GrimbotsAIService
    dead = GrimbotsAIService("http://127.0.0.1:1", "k", timeout=1.0)
    rows2 = []
    ok = True
    try:
        shadow.run_shadow(
            respond=dead.respond, payload=_payload_v11("shadow-e5-2", st, "oi"),
            observed={"action": "continue"}, bot_id=140, lead_ref="ref",
            request_id="shadow-e5-2", record=lambda r: rows2.append(r), secret="k",
        )
    except Exception:  # noqa: BLE001
        ok = False
    check("3 falha do motor fail-open (linha SHADOW_ERROR, sem exceção)",
          ok and len(rows2) == 1 and rows2[0].get("error_code") == "SHADOW_ERROR",
          f"linhas={len(rows2)} erro={rows2[0].get('error_code') if rows2 else None}")

    return results


def main():
    if not infra.MOTOR_DIR.exists() or not infra.VENV_PY.exists():
        print("SKIP: motor/venv ausentes")
        return 0

    import socket
    import subprocess
    import tempfile
    import threading
    from http.server import ThreadingHTTPServer

    mock_port = infra.free_port()
    motor_port = infra.free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", mock_port), infra.MockOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    env = dict(os.environ)
    env.update({
        "GRIMBOTS_API_KEY": infra.API_KEY,
        "OLLAMA_BASE_URL": f"http://127.0.0.1:{mock_port}",
        "HOST": "127.0.0.1", "PORT": str(motor_port),
        "GLOBAL_AI_ENABLED": "true", "HEALTH_REQUIRES_AUTH": "false",
        "ALLOWED_HOSTS": "*", "RATE_LIMIT_PER_MINUTE": "1000",
        "EXPOSE_DOCS": "false", "LOG_LEVEL": "warning",
    })
    log = tempfile.NamedTemporaryFile("w+", suffix="-motor-e5.log", delete=False)
    proc = subprocess.Popen(
        [str(infra.VENV_PY), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(infra.MOTOR_DIR / "api"), env=env,
        stdout=log, stderr=subprocess.STDOUT,
    )
    ok = False
    try:
        infra.wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock :{mock_port}, motor :{motor_port})\n")
        results = run_scenarios(motor_port)
        ok = all(r[1] for r in results)
        print(f"\n{sum(1 for r in results if r[1])}/{len(results)} cenarios E5 OK")
    except Exception as exc:  # noqa: BLE001
        print(f"💥 erro no harness: {exc}")
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
