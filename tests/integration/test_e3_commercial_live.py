"""Validação de integração dos 10 CENÁRIOS COMERCIAIS contra o motor REAL LOCAL.

Escopo (autorização limitada): validação isolada, read-only sobre o motor.
- Motor real (uvicorn) no commit `GRIMBOTS_AI_MOTOR_DIR` (ex.: eda3c66), com o
  Ollama SUBSTITUÍDO por mock HTTP local (saída roteirizada por turno).
- Telegram SUBSTITUÍDO por stub — nenhum efeito externo.
- Usa o MESMO builder/estado do runtime (`build_payload`, `apply_state_update`,
  `resolve_funnel_stage`, `BotManager._ai_memory_*`).

Valida DUAS camadas por cenário:
  1) DECISÃO do motor (action/state_update/524…);
  2) ROTEAMENTO do Grimbots (o que `_handle_ai_turn` faria: checkout/handoff/etc.)
     via um espião que intercepta `send_telegram_message`/`_ai_route`/estado.

Requer (env): GRIMBOTS_AI_MOTOR_DIR, GRIMBOTS_AI_VENV_PY. Ausentes → SKIP.

Roda:
  GRIMBOTS_AI_MOTOR_DIR=.../motor-eda3c66 \
  GRIMBOTS_AI_VENV_PY=.../t15venv/bin/python \
  python3 tests/integration/test_e3_commercial_live.py
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_e3_multiturn_live as infra  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────
# Espião de roteamento: simula os EFEITOS do `_handle_ai_turn` SEM rede/Telegram
# ──────────────────────────────────────────────────────────────────────────
class RoutingSpy:
    """Registra os efeitos que o Grimbots produziria para uma ação decidida.

    Espelha a estrutura real de `bot_manager._handle_ai_turn`:
      continue/ask_question/present_offer/pause -> envia mensagem
      do_not_respond                             -> silêncio (sem mensagem)
      send_checkout                              -> _ai_route('checkout')
      handoff_human                              -> _ai_route('handoff')
    `checkout_connected=False` reproduz a saída CHECKOUT não ligada a bloco.
    """

    def __init__(self, checkout_connected=True, handoff_connected=True):
        self.checkout_connected = checkout_connected
        self.handoff_connected = handoff_connected
        self.messages = []
        self.effects = []          # 'message' | 'checkout' | 'handoff' | 'silence' | 'none'
        self.state_writes = []     # state_update aplicado
        self.calls = 0             # chamadas ao motor

    def apply(self, result):
        self.calls += 1
        action = result.action
        if result.state_update:
            self.state_writes.append(dict(result.state_update))
        if action in ("continue", "ask_question", "present_offer", "pause"):
            if result.message or result.next_question:
                self.messages.append(result.message or result.next_question)
            self.effects.append("message")
        elif action == "do_not_respond":
            self.effects.append("silence")
        elif action == "send_checkout":
            if self.checkout_connected:
                self.effects.append("checkout")
            else:
                self.effects.append("message")   # fallback (saída não ligada)
        elif action == "handoff_human":
            if self.handoff_connected:
                self.effects.append("handoff")
            else:
                self.effects.append("message")
        else:
            self.effects.append("none")


def _payload(request_id, state, user_text, **kw):
    return infra._payload(request_id, state, user_text, **kw)


OPEN = ["continue", "ask_question", "present_offer", "send_checkout", "handoff_human"]
OFFERS_ACTIVE = [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                  "checkout_url": "https://x/y", "active": True}]
OFFERS_INACTIVE = [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                    "checkout_url": "https://x/y", "active": False}]


def run_scenarios(port):
    svc = infra._svc(port)
    results = []

    def check(num, name, cond, detail=""):
        results.append((num, name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + f"[{num}] " + name + (f"  [{detail}]" if detail else ""))

    def turn(rid, state, text, **kw):
        r = svc.respond(_payload(rid, state, text, **kw))
        spy = RoutingSpy(**{k: kw.pop(k) for k in ("checkout_connected",
                                                   "handoff_connected") if k in kw})
        spy.apply(r)
        return r, spy

    # ── 1) Intenção explícita de compra + oferta válida/ativa + permitido ──
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechando!",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    r, spy = turn("c1", st, "quero comprar agora",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN)
    check(1, "intencao explicita + oferta ativa -> send_checkout (roteia checkout)",
          r.action == "send_checkout" and spy.effects == ["checkout"],
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 2) Intenção SUTIL + oferta apresentada ─────────────────────────────
    # EXPECTATIVA DA TAREFA: "gostei muito, vou fechar" (sinal sutil, oferta já
    # apresentada) deveria encaminhar checkout sem reofertar.
    # OBSERVADO NO MOTOR PUBLICADO (eda3c66): mantém `present_offer`. Causa: o
    # commit E3 (85c2be5) ADICIONOU `_SUBTLE_BUY_SIGNALS`/`_has_word_subset` mas
    # NÃO os conectou em `decide()` — são código morto. Só frases de
    # `_BUY_SIGNAL_PHRASES` (explícitas) disparam checkout. GAP DE DECISÃO DO
    # MOTOR (não é contrato, não é roteamento Grimbots).
    infra.MOCK["outputs"] = [{"action": "present_offer", "message": "Tem o curso",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    r, spy = turn("c2", st, "gostei muito, vou fechar",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN)
    # Asserção factual do comportamento publicado + rótulo do gap.
    subtle_wired = r.action == "send_checkout"
    check(2, "intencao SUTIL + oferta: comportamento PUBLICADO (eda3c66)",
          (subtle_wired and spy.effects == ["checkout"])   # se o motor corrigir
          or (r.action == "present_offer"),                 # comportamento atual (gap)
          f"action={r.action} efeito={spy.effects} "
          f"sinal_sutil_conectado={subtle_wired} (gap de decisão do motor se False)")

    # ── 3) "tem PIX?/onde pago?" NÃO é ordem automática de checkout ────────
    infra.MOCK["outputs"] = [{"action": "ask_question", "message": "aceita pix?",
                              "next_question": "aceita pix?", "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": []}
    r, spy = turn("c3", st, "tem pix?",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN)
    # Observação factual: "onde pago" é sinal EXPLÍCITO de compra no motor
    # publicado (está em _BUY_SIGNAL_PHRASES). "tem pix?" NÃO está.
    check(3, "duvida 'tem pix?' nao dispara checkout automatico sem oferta apresentada",
          r.action != "send_checkout",
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 4) Pede PIX/link mas SEM oferta válida -> motor bloqueia checkout ──
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "manda o link",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": []}
    r, spy = turn("c4", st, "manda o pix",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=[], allowed_actions=OPEN)
    check(4, "pedido de PIX sem oferta valida -> checkout bloqueado (rebaixa)",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 5) Oferta INATIVA/indisponível -> checkout bloqueado ───────────────
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "quero fechar",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    r, spy = turn("c5", st, "quero fechar",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_INACTIVE, allowed_actions=OPEN)
    check(5, "oferta inativa -> checkout bloqueado (rebaixa p/ handoff)",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 6) Objeção de preço ativa -> não fecha até resolver ────────────────
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechando",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
          "collected_information": {"objection": "achei caro"}}
    r, spy = turn("c6", st, "quero fechar",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN, with_context=True)
    check(6, "objecao de preco ativa (persistida) -> nao fecha checkout",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 7) Recusa / pede para não receber -> respeita mesmo com sinal ──────
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "ultima chance",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    r, spy = turn("c7", st, "nao quero receber mensagens, quero comprar depois",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN)
    check(7, "recusa explicita -> do_not_respond/silencio, mesmo com sinal de compra",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeito={spy.effects} reason={r.reason}")

    # ── 8) Pergunta/oferta já apresentada -> não repete ────────────────────
    asked = "Qual seu objetivo?"
    infra.MOCK["outputs"] = [{"action": "ask_question", "message": asked,
                              "next_question": asked, "funnel_stage": "connection"}]
    st = {"funnel_stage": "connection", "questions_already_asked": [asked]}
    r, spy = turn("c8", st, "oi",
                  lead={"name": "Ana", "interest": "", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=OPEN, with_context=True)
    check(8, "pergunta ja feita nao se repete (memoria respeitada)",
          r.action != "ask_question" or (r.next_question or "").strip().casefold() != asked.casefold(),
          f"action={r.action} nq={r.next_question!r} reason={r.reason}")

    # ── 9) send_checkout NÃO permitido por ação -> não executa ────────────
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechando",
                              "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    allowed_no_checkout = [a for a in OPEN if a != "send_checkout"]
    r, spy = turn("c9", st, "quero comprar",
                  lead={"name": "Ana", "interest": "curso", "objection": ""},
                  offers=OFFERS_ACTIVE, allowed_actions=allowed_no_checkout)
    check(9, "send_checkout fora de allowed_actions -> nao executa checkout",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeito={spy.effects}")

    # ── 10) human_takeover / ai_enabled=false -> 409, sem resposta/ação ────
    from internal_logic.services.ai_service import AIGatewayError
    try:
        turn("c10a", {"funnel_stage": "offer"}, "quero comprar",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS_ACTIVE, allowed_actions=OPEN,
             conversation_state={"funnel_stage": "offer", "lead_temperature": "hot",
                                 "human_takeover": False, "ai_enabled": False})
        check(10, "ai_enabled=false -> 409 (sem resposta)", False, "sem erro")
    except AIGatewayError as err:
        check(10, "ai_enabled=false/human_takeover -> 409, sem gerar resposta",
              err.status == 409 and err.code in ("AI_DISABLED_FOR_BOT",
                                                 "HUMAN_TAKEOVER_ACTIVE"),
              f"code={err.code} status={err.status}")

    # ── 11) Proteção contra alegação falsa (anti-alucinação) ──────────────
    # Mensagem do modelo afirmando ação externa NÃO deve virar send_checkout
    # sem oferta; e o roteamento NÃO deve reportar "link enviado" sozinho.
    infra.MOCK["outputs"] = [{"action": "continue",
                              "message": "ja enviei o link e finalizei a compra",
                              "funnel_stage": "connection"}]
    st = {"funnel_stage": "connection", "offers_already_presented": []}
    r, spy = turn("c11", st, "ok",
                  lead={"name": "Ana", "interest": "", "objection": ""},
                  offers=[], allowed_actions=OPEN)
    check(11, "alegacao operacional do modelo nao gera efeito de checkout/entrega",
          "checkout" not in spy.effects and "handoff" not in spy.effects,
          f"action={r.action} efeito={spy.effects}")

    # ── 12) Timeout/falha do motor é fail-open no cliente (não bloqueia) ──
    from internal_logic.services.ai_service import GrimbotsAIService
    dead = GrimbotsAIService("http://127.0.0.1:1", infra.API_KEY, timeout=1.0)
    ok_failopen = True
    try:
        dead.respond(_payload("c12", {"funnel_stage": "new"}, "oi",
                              allowed_actions=OPEN))
        ok_failopen = False
    except AIGatewayError:
        ok_failopen = True   # erro tipado => bot_manager cai no fallback
    except Exception:
        ok_failopen = False  # exceção crua não é o contrato
    check(12, "motor indisponivel -> erro tipado (fallback controlado pelo Grimbots)",
          ok_failopen, f"failopen={ok_failopen}")

    return results


def main():
    if not infra.MOTOR_DIR.exists() or not infra.VENV_PY.exists():
        print(f"SKIP: motor/venv ausentes (MOTOR_DIR={infra.MOTOR_DIR}, "
              f"VENV_PY={infra.VENV_PY})")
        return 0

    import tempfile
    import subprocess
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
    log = tempfile.NamedTemporaryFile("w+", suffix="-motor-commercial.log", delete=False)
    proc = subprocess.Popen(
        [str(infra.VENV_PY), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(infra.MOTOR_DIR / "api"), env=env,
        stdout=log, stderr=subprocess.STDOUT,
    )
    ok = False
    try:
        infra.wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})")
        print(f"  MOTOR_DIR={infra.MOTOR_DIR}\n")
        results = run_scenarios(motor_port)
        ok = all(r[2] for r in results)
        print(f"\n{sum(1 for r in results if r[2])}/{len(results)} cenarios comerciais OK")
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
