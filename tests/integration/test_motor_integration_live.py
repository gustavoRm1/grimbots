"""Integração FUNCIONAL do motor comercial publicado (Grimbots <-> motor).

Dependência externa: o motor Grimbots AI Gateway (commit publicado
`a54b9dd`, branch `e4-subtle-buy-intent`) servido por `uvicorn`, com o Ollama
SUBSTITUÍDO por um mock HTTP local. NÃO é offline: o cliente REAL
`GrimbotsAIService` fala HTTP com o motor, que aplica a camada comercial
(`api/commercial_decision.py`: `decide`/`apply_decision`/`guard_final_message`).

Regra de escopo: este teste NÃO reimplementa a inteligência comercial. Ele
apenas reproduz o CONSUMO e o ROTEAMENTO do Grimbots, espelhando branch a branch
o despacho real de `BotManager._handle_ai_turn` (~L4700-4772) e a persistência
de estado (~L4663-4698), usando os helpers REAIS do runtime
(`build_payload`, `apply_state_update`, `resolve_funnel_stage`,
`BotManager._ai_memory_updates`, `BotManager._ai_memory_payload`).

Cobre os 11 fluxos exigidos:
 1. continuação natural; 2. pergunta de necessidade; 3. apresentação de oferta;
 4. intenção explícita + pagamento; 5. intenção sutil sem checkout indevido;
 6. objeção de preço e resolução em turnos posteriores; 7. recusa explícita
    (mesmo com sinal conflitante); 8. oferta ausente/inativa; 9. checkout fora
    das permissões efetivas; 10. IA desativada / transferência p/ humano;
 11. timeout, resposta inválida e indisponibilidade do motor.

Requer (via env, defaults para o worktree/venv de trabalho):
  GRIMBOTS_AI_MOTOR_DIR  (default: clone em /var/folders/.../opencode/grimbots-ai)
  GRIMBOTS_AI_VENV_PY    (default: .../opencode/t15venv/bin/python)

Se ausentes/inexistentes -> SKIP (exit 0), nunca quebra o CI.

Roda:
  GRIMBOTS_AI_MOTOR_DIR=.../motor-a54b9dd \
  GRIMBOTS_AI_VENV_PY=.../t15venv/bin/python \
  python3 tests/integration/test_motor_integration_live.py
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
API_KEY = "itest-motor-key"

# Modo do mock: "json" (saída sintética roteirizada) | "garbage" | "hang".
MOCK = {"prompts": [], "outputs": [], "mode": "json"}

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
        if not self.path.startswith("/api/generate"):
            self._send(404, {"error": "not found"})
            return
        try:
            req = json.loads(body)
        except ValueError:
            req = {}
        MOCK["prompts"].append(req.get("prompt", ""))

        if MOCK["mode"] == "hang":
            time.sleep(30)
            self._send(200, {"response": "{}", "done": True})
            return
        if MOCK["mode"] == "garbage":
            self._send(200, {"response": "isto nao e json valido {{{",
                             "prompt_eval_count": 5, "eval_count": 7, "done": True})
            return

        out = dict(_DEFAULT_OUTPUT)
        if MOCK["outputs"]:
            out.update(MOCK["outputs"].pop(0))
        self._send(200, {
            "response": json.dumps(out),
            "prompt_eval_count": 11,
            "eval_count": 22,
            "done": True,
        })


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


def _svc(port, timeout=20.0):
    from internal_logic.services.ai_service import GrimbotsAIService
    return GrimbotsAIService(f"http://127.0.0.1:{port}", API_KEY, timeout=timeout)


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
        conversation_id="c140-int", bot_user_id="8142273932",
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


def _persist(state, result, payload_objection=""):
    """Espelha `_persist` real (bot_manager.py ~L4663-4698) usando os helpers reais.

    Inclui a gravação da objeção do turno (runtime L4684-4685:
    `if _payload_objection: state_live['objection'] = _payload_objection`), e a
    persistência da memória (`_ai_memory_updates`, que grava `collected_information`).
    """
    from internal_logic.services.ai_service import apply_state_update, resolve_funnel_stage
    from bot_manager import BotManager
    su = getattr(result, "state_update", None)
    prev = state.get("funnel_stage")
    su_stage = su.get("funnel_stage") if isinstance(su, dict) else None
    if su:
        apply_state_update(state, su)
    state["lead_temperature"] = result.lead_temperature
    state["funnel_stage"] = (
        resolve_funnel_stage(prev, result.funnel_stage, su_stage) or result.funnel_stage
    )
    state["intent"] = result.intent
    state["last_intent"] = result.intent
    if payload_objection:
        state["objection"] = payload_objection
    state.update(BotManager._ai_memory_updates(
        state, result, result.action, result.message or "", result.next_question or "",
    ))
    # E3 multi-turno: a objeção do turno também é registrada em collected_information
    # (chave `objection`), que é o que o motor lê na leitura persistida (D5).
    if payload_objection:
        ci = dict(state.get("collected_information") or {})
        ci.setdefault("objection", payload_objection)
        state["collected_information"] = ci


class RoutingSpy:
    """Despacho que ESPELHA `BotManager._handle_ai_turn` (L4700-4772).

    Registra o EFEITO real (message/question/checkout/handoff/silence) e o alvo
    da saída do bloco, sem Telegram/DB/Redis. `checkout_connected`/`handoff_connected`
    representam as saídas ligadas do bloco 'ai' no Flow Builder.
    """

    def __init__(self, *, checkout_connected=True, handoff_connected=True):
        self.checkout_connected = checkout_connected
        self.handoff_connected = handoff_connected
        self.effects = []          # lista ordenada de efeitos
        self.messages = []         # textos enviados ao lead
        self.target = None         # bloco de destino (checkout/handoff)

    def dispatch(self, result, *, personalize=lambda t: t, is_redundant=lambda m, q: False):
        action = result.action
        message_text = personalize((result.message or "").strip())
        question = (result.next_question or "").strip() if action == "ask_question" else ""

        if action == "do_not_respond":
            self.effects.append("silence")
            return

        if action in ("continue", "ask_question", "present_offer", "pause"):
            if message_text:
                self.effects.append("message")
                self.messages.append(message_text)
            if question and not is_redundant(message_text, question):
                self.effects.append("question")
                self.messages.append(question)
            return

        if action == "send_checkout":
            if self.checkout_connected:
                if message_text:
                    self.effects.append("message")
                    self.messages.append(message_text)
                self.effects.append("checkout")
                self.target = "checkout"
                return
            self.effects.append("message")
            self.messages.append(message_text or "<fallback>")
            return

        if action == "handoff_human" or result.handoff_human:
            if message_text:
                self.effects.append("message")
                self.messages.append(message_text)
            if self.handoff_connected:
                self.effects.append("handoff")
                self.target = "handoff"
                return
            self.effects.append("message")
            self.messages.append(message_text or "<fallback>")
            return

        # ação desconhecida (defensivo)
        self.effects.append("fallback")
        self.messages.append(message_text or "<fallback>")


OFFERS = [{"id": "of1", "name": "Curso", "price": "R$ 97",
           "checkout_url": "https://x/y", "active": True}]
OFFERS_INACTIVE = [{"id": "of1", "name": "Curso", "price": "R$ 97",
                    "checkout_url": "https://x/y", "active": False}]
OPEN = ["continue", "ask_question", "present_offer", "send_checkout", "handoff_human"]


def run_scenarios(port):
    from internal_logic.services.ai_service import AIGatewayError
    svc = _svc(port)
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(("✅ " if cond else "❌ ") + name + (f"  [{detail}]" if detail else ""))

    def turn(rid, state, text, *, spy=None, **kw):
        r = svc.respond(_payload(rid, state, text, **kw))
        if spy is not None:
            spy.dispatch(r)
        return r

    # ── 1) Continuação natural da conversa (sem efeito indevido) ────────────
    MOCK["outputs"] = [{"action": "continue", "message": "Perfeito, seguimos!",
                        "funnel_stage": "connection"}]
    st = {"funnel_stage": "connection"}
    spy = RoutingSpy()
    r = turn("int-1", st, "oi, tudo bem?", spy=spy, allowed_actions=OPEN)
    check("1 continuacao natural: mensagem enviada, sem checkout/handoff",
          r.action == "continue" and spy.effects == ["message"]
          and spy.target is None,
          f"action={r.action} efeitos={spy.effects}")

    # ── 2) Pergunta para descobrir a necessidade do lead ────────────────────
    MOCK["outputs"] = [{"action": "ask_question", "message": "O que te trouxe aqui?",
                        "next_question": "O que te trouxe aqui?",
                        "funnel_stage": "qualification"}]
    st = {"funnel_stage": "new", "lead_temperature": "warm"}
    spy = RoutingSpy()
    r = turn("int-2", st, "queria saber mais",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             spy=spy, allowed_actions=OPEN)
    check("2 pergunta de necessidade: acao ask_question + pergunta coerente",
          r.action == "ask_question" and (r.next_question or "").strip()
          and "question" in spy.effects and spy.target is None,
          f"action={r.action} nq={r.next_question!r} efeitos={spy.effects}")

    # ── 3) Apresentação de oferta (lead quente, oferta disponível) ──────────
    MOCK["outputs"] = [{"action": "present_offer", "message": "Temos o Curso por R$ 97",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "qualification", "lead_temperature": "hot",
          "collected_information": {"need_confirmado": True}}
    spy = RoutingSpy()
    r = turn("int-3", st, "me mostra o que tem",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    check("3 apresentacao de oferta: present_offer (mensagem no canal)",
          r.action == "present_offer" and spy.effects == ["message"]
          and spy.target is None,
          f"action={r.action} efeitos={spy.effects}")

    # ── 4) Intenção explícita de compra + pagamento -> checkout ─────────────
    MOCK["outputs"] = [{"action": "present_offer", "message": "Vou te ajudar",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
          "lead_temperature": "hot"}
    spy = RoutingSpy()
    r = turn("int-4", st, "quero assinar agora, manda o link",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    check("4 intencao explicita + pagamento -> send_checkout ROTEIA checkout",
          r.action == "send_checkout" and "checkout" in spy.effects
          and spy.target == "checkout",
          f"action={r.action} efeitos={spy.effects} alvo={spy.target}")

    # ── 5) Intenção sutil: sinal sutil reconhecido; NÃO fecha sem contexto ──
    # 5a) sutil + oferta já apresentada -> encaminha checkout (comportamento do
    #     motor publicado após wiring de _SUBTLE_BUY_SIGNALS).
    MOCK["outputs"] = [{"action": "present_offer", "message": "Boa!",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
          "lead_temperature": "warm"}
    spy = RoutingSpy()
    r = turn("int-5a", st, "gostei muito, vou fechar",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    check("5a intencao sutil com oferta apresentada -> send_checkout (roteia)",
          r.action == "send_checkout" and spy.target == "checkout",
          f"action={r.action} alvo={spy.target}")
    # 5b) sutil SEM oferta apresentada -> NÃO dispara checkout indevido.
    MOCK["outputs"] = [{"action": "continue", "message": "Legal!",
                        "funnel_stage": "qualification"}]
    st = {"funnel_stage": "qualification", "offers_already_presented": []}
    spy = RoutingSpy()
    r = turn("int-5b", st, "gostei muito, vou fechar",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    check("5b intencao sutil SEM oferta apresentada -> NAO dispara checkout",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeitos={spy.effects}")

    # ── 6) Objeção de preço e resolução em turnos posteriores ───────────────
    # 6a) 1º turno: objeção de preço -> não fecha; esclarece/reapresenta.
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar ja",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    spy = RoutingSpy()
    r1 = turn("int-6a", st, "achei muito caro",
              lead={"name": "Ana", "interest": "curso", "objection": "caro"},
              offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    _persist(st, r1, payload_objection="caro")
    check("6a objecao de preco: NAO fecha checkout no turno da objecao",
          r1.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r1.action} efeitos={spy.effects}")
    # 6b) objeção persistida (memória round-trip) ainda bloqueia no 2º turno.
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar ja",
                        "funnel_stage": "offer"}]
    spy2 = RoutingSpy()
    r2 = turn("int-6b", st, "quero fechar",
              lead={"name": "Ana", "interest": "curso", "objection": ""},
              offers=OFFERS, spy=spy2, allowed_actions=OPEN, with_context=True)
    _persist(st, r2)
    check("6b objecao persistida (multi-turno) segue bloqueando checkout",
          r2.action != "send_checkout" and "checkout" not in spy2.effects,
          f"action={r2.action} efeitos={spy2.effects} ci={st.get('collected_information')}")
    # 6c) objeção RESOLVIDA permite retomar o fechamento.
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar ja",
                        "funnel_stage": "offer"}]
    st["collected_information"]["objection_resolved"] = True
    spy3 = RoutingSpy()
    r3 = turn("int-6c", st, "quero fechar agora",
              lead={"name": "Ana", "interest": "curso", "objection": ""},
              offers=OFFERS, spy=spy3, allowed_actions=OPEN, with_context=True)
    check("6c objecao resolvida -> retoma send_checkout (roteia checkout)",
          r3.action == "send_checkout" and spy3.target == "checkout",
          f"action={r3.action} alvo={spy3.target}")

    # ── 7) Recusa explícita, mesmo com sinal conflitante ────────────────────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    spy = RoutingSpy()
    r = turn("int-7", st, "nao quero mais, me tira da lista e para de mandar link",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=OPEN, with_context=True)
    check("7 recusa explicita vence sinal conflitante (sem checkout/oferta)",
          r.action in ("do_not_respond", "continue")
          and "checkout" not in spy.effects
          and r.action != "send_checkout",
          f"action={r.action} efeitos={spy.effects}")

    # ── 8) Oferta ausente ou inativa -> checkout bloqueado ──────────────────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    spy = RoutingSpy()
    r = turn("int-8a", st, "quero assinar agora, manda o link",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS_INACTIVE, spy=spy, allowed_actions=OPEN, with_context=True)
    check("8a oferta INATIVA -> checkout bloqueado (sem efeito checkout)",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeitos={spy.effects}")
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar",
                        "funnel_stage": "offer"}]
    spy = RoutingSpy()
    r = turn("int-8b", st, "quero assinar agora, manda o link",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=[], spy=spy, allowed_actions=OPEN, with_context=True)
    check("8b oferta AUSENTE -> checkout bloqueado (sem efeito checkout)",
          r.action != "send_checkout" and "checkout" not in spy.effects,
          f"action={r.action} efeitos={spy.effects}")

    # ── 9) Checkout fora das permissões efetivas ────────────────────────────
    MOCK["outputs"] = [{"action": "send_checkout", "message": "Fechar",
                        "funnel_stage": "offer"}]
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    no_checkout = ["continue", "ask_question", "present_offer", "handoff_human"]
    spy = RoutingSpy()
    r = turn("int-9", st, "quero assinar agora, manda o link",
             lead={"name": "Ana", "interest": "curso", "objection": ""},
             offers=OFFERS, spy=spy, allowed_actions=no_checkout, with_context=True)
    check("9 send_checkout fora de allowed_actions -> nao executa checkout",
          r.action != "send_checkout" and "checkout" not in spy.effects
          and r.action in no_checkout,
          f"action={r.action} efeitos={spy.effects}")

    # ── 10) IA desativada e transferência para humano (contrato 409) ────────
    try:
        turn("int-10a", {"funnel_stage": "new"}, "oi", allowed_actions=OPEN,
             conversation_state={"funnel_stage": "new", "lead_temperature": "warm",
                                 "human_takeover": False, "ai_enabled": False})
        check("10a ai_enabled=false -> 409 AI_DISABLED_FOR_BOT", False, "sem erro")
    except AIGatewayError as err:
        check("10a ai_enabled=false -> 409 AI_DISABLED_FOR_BOT",
              err.code == "AI_DISABLED_FOR_BOT" and err.status == 409,
              f"code={err.code} status={err.status}")
    try:
        turn("int-10b", {"funnel_stage": "new"}, "oi", allowed_actions=OPEN,
             conversation_state={"funnel_stage": "new", "lead_temperature": "warm",
                                 "human_takeover": True, "ai_enabled": True})
        check("10b human_takeover=true -> 409 HUMAN_TAKEOVER_ACTIVE", False, "sem erro")
    except AIGatewayError as err:
        check("10b human_takeover=true -> 409 HUMAN_TAKEOVER_ACTIVE",
              err.code == "HUMAN_TAKEOVER_ACTIVE" and err.status == 409,
              f"code={err.code} status={err.status}")

    # ── 11) Timeout, resposta inválida e indisponibilidade do motor ─────────
    # 11a) resposta inválida (saída não-JSON do modelo) -> tolerada pela camada
    #      comercial, sem efeito externo nem exceção.
    MOCK["outputs"] = []
    MOCK["mode"] = "garbage"
    try:
        st = {"funnel_stage": "connection"}
        spy = RoutingSpy()
        r = turn("int-11a", st, "oi", spy=spy, allowed_actions=OPEN)
        check("11a resposta invalida do modelo -> tratada, sem efeito externo",
              r is not None and "checkout" not in spy.effects
              and "handoff" not in spy.effects,
              f"action={r.action if r else None} efeitos={spy.effects}")
    except AIGatewayError as err:
        check("11a resposta invalida -> erro tipado (sem efeito externo)",
              True, f"code={err.code}")
    finally:
        MOCK["mode"] = "json"
    # 11b) timeout do motor -> erro tipado (Grimbots cai no fallback).
    slow = _svc(port, timeout=1.0)
    MOCK["mode"] = "hang"
    try:
        slow.respond(_payload("int-11b", {"funnel_stage": "connection"}, "oi",
                              allowed_actions=OPEN))
        check("11b timeout -> erro tipado", False, "sem erro")
    except AIGatewayError as err:
        check("11b timeout -> erro tipado (fallback controlado pelo Grimbots)",
              err is not None, f"code={err.code}")
    except Exception as exc:  # noqa: BLE001
        check("11b timeout -> erro tipado", False, f"excecao crua: {exc}")
    finally:
        MOCK["mode"] = "json"
    # 11c) motor indisponível (porta fechada) -> erro tipado, nao excecao crua.
    dead = _svc(free_port(), timeout=2.0)
    try:
        dead.respond(_payload("int-11c", {"funnel_stage": "connection"}, "oi",
                              allowed_actions=OPEN))
        check("11c motor indisponivel -> erro tipado", False, "sem erro")
    except AIGatewayError as err:
        check("11c motor indisponivel -> erro tipado (fail-open no runtime)",
              err is not None, f"code={err.code}")
    except Exception as exc:  # noqa: BLE001
        check("11c motor indisponivel -> erro tipado", False, f"excecao crua: {exc}")

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
    log = tempfile.NamedTemporaryFile("w+", suffix="-motor-int.log", delete=False)

    proc = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(MOTOR_DIR / "api"), env=env,
        stdout=log, stderr=subprocess.STDOUT,
    )

    ok = False
    try:
        wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})")
        print(f"  MOTOR_DIR={MOTOR_DIR}\n")
        results = run_scenarios(motor_port)
        ok = all(r[1] for r in results)
        print(f"\n{sum(1 for r in results if r[1])}/{len(results)} fluxos de integracao OK")
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
