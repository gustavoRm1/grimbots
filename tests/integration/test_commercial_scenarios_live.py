"""Bateria de VALIDAÇÃO COMERCIAL CONTROLADA multi-turno (motor REAL a54b9dd).

Objetivo: avaliar a QUALIDADE das decisões comerciais (não repetir auditorias já
feitas) preparando a IA para um piloto com leads reais em produção controlada.

Dependência externa: o motor Grimbots AI Gateway (commit `a54b9dd`) via
`uvicorn`, com o Ollama SUBSTITUÍDO por mock HTTP (saída roteirizada por turno).
O cliente REAL `GrimbotsAIService` fala HTTP com o motor, que aplica a camada
comercial (`api/commercial_decision.py`). O Grimbots é responsável pela
integração: persistência de estado (`_persist`, mesmos helpers do runtime) e
roteamento (`RoutingSpy`, espelho de `_handle_ai_turn`).

Regra de escopo: NÃO reimplementa a inteligência comercial e NÃO altera o motor.

Decisão sobre expectativas (conforme alinhado): asserção FACTUAL do comportamento
publicado; quando divergir do ideal comercial, marca FALHA/observação de QUALIDADE
e anexa o payload mínimo de reprodução para o dono do motor.

Oito cenários obrigatórios:
  1. Lead curioso          -> avanca sem pressionar compra
  2. Intencao de compra    -> conduz ao proximo passo adequado (sutil = qualidade)
  3. Objecao de preco      -> compreende, responde e mantem checkout bloqueado
  4. Objecao resolvida     -> libera checkout so com oferta ativa + permissao
  5. Recusa explicita      -> respeita, nao insiste
  6. Conversa longa        -> preserva contexto, sem repetir pergunta, sem perder info
  7. Alegacoes falsas      -> nao inventa desconto/urgencia/garantia/acao concluida
  8. Falha e recuperacao   -> retomada sem descarte nem duplicidade (limites testados)

Serviços:
  REAL   : motor comercial (a54b9dd).
  MOCK   : Ollama (roteiriza a saida do modelo), Telegram, checkout/handoff.
  SEM Redis/DB real (persistencia real ja validada em etapa anterior).
  Nao habilita E5/shadow nem D11_STORE=sqlite.

Requer (env): GRIMBOTS_AI_MOTOR_DIR, GRIMBOTS_AI_VENV_PY. Ausentes -> SKIP.

Roda:
  GRIMBOTS_AI_MOTOR_DIR=.../motor-a54b9dd \
  GRIMBOTS_AI_VENV_PY=.../t15venv/bin/python \
  python3 tests/integration/test_commercial_scenarios_live.py [--json out.json]
"""
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_e3_multiturn_live as infra  # noqa: E402


OPEN = ["continue", "ask_question", "present_offer", "send_checkout", "handoff_human"]
# Recusa exige que a acao `do_not_respond` esteja PERMITIDA (senao o motor
# rebaixa via _clamp para `continue` — ver commercial_decision._SAFE_FALLBACK_ORDER).
OPEN_WITH_SILENCE = OPEN + ["do_not_respond"]
OFFERS_ACTIVE = [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                  "checkout_url": "https://x/y", "active": True}]
OFFERS_INACTIVE = [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                    "checkout_url": "https://x/y", "active": False}]
AI_MEM_CTX = {"ai_enabled": True, "human_takeover": False}


class ScenarioRecorder:
    """Coleta payload(s), transcricao, acao, resposta, state_update e estado por turno."""

    def __init__(self, name):
        self.name = name
        self.turns = []  # dicts por turno

    def add(self, *, lead_text, payload, action, message, reason, next_question,
            state_update, state_after, effect):
        self.turns.append({
            "lead": lead_text,
            "payload": payload,
            "action": action,
            "message": message,
            "reason": reason,
            "next_question": next_question,
            "state_update": state_update,
            "state_after": state_after,
            "effect": effect,
        })

    def transcript(self):
        lines = []
        for i, t in enumerate(self.turns, 1):
            lines.append(f"  turno {i}: LEAD: {t['lead']!r}")
            lines.append(f"           -> acao={t['action']} efeito={t['effect']}")
            if t["message"]:
                lines.append(f"              bot: {t['message']!r}")
            if t["reason"]:
                lines.append(f"              reason: {t['reason']}")
            if t["state_update"]:
                lines.append(f"              state_update: {t['state_update']}")
        return "\n".join(lines)


class RoutingSpy:
    """Espelha os EFEITOS de `_handle_ai_turn` (mesmo do harness comercial)."""

    def __init__(self, checkout_connected=True, handoff_connected=True):
        self.checkout_connected = checkout_connected
        self.handoff_connected = handoff_connected
        self.messages = []
        self.effects = []
        self.checkout_id = None

    def apply(self, result):
        action = result.action
        if result.state_update:
            pass
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
                self.effects.append("message")
        elif action == "handoff_human":
            if self.handoff_connected:
                self.effects.append("handoff")
            else:
                self.effects.append("message")
        else:
            self.effects.append("none")
        return self.effects[-1]


def run_scenarios(port, emit=print):
    from internal_logic.services.ai_service import apply_state_update, resolve_funnel_stage
    from bot_manager import BotManager

    svc = infra._svc(port)
    results = []
    recs = []

    def check(cid, name, cond, detail="", quality=False):
        tag = "QUALIDADE " if quality else ""
        results.append((cid, name, bool(cond), detail, quality))
        emit(("✅ " if cond else "❌ ") + f"[{cid}] {tag}" + name
             + (f"  [{detail}]" if detail else ""))

    def do_turn(rec, rid, state, text, *, offers=None, lead=None,
                allowed=None, conversation_state=None, checkout_connected=True):
        # Espelha a ORDEM do runtime: `_ai_apply_objection_state` roda no estado
        # ANTES de montar o payload (bot_manager ~L4617-4620). Assim o motor ja
        # ve objecao/resolucao neste turno — e, em resolucao, `lead.objection`
        # sai VAZIO (o motor da precedencia ao turno atual).
        BotManager._ai_apply_objection_state(state, text)
        if lead is None:
            lead = {"name": "Ana", "interest": "", "objection": state.get("objection") or ""}
        elif not isinstance(lead, dict):
            lead = {"name": "Ana", "interest": "", "objection": ""}
        payload = infra._payload(rid, state, text, lead=lead, offers=offers,
                                 allowed_actions=allowed,
                                 conversation_state=conversation_state,
                                 with_context=True)
        r = svc.respond(payload)
        spy = RoutingSpy(checkout_connected=checkout_connected)
        effect = spy.apply(r)
        # Persiste o turno no estado vivo (mesma semantica do runtime).
        su = getattr(r, "state_update", None)
        if su:
            apply_state_update(state, su)
        state["lead_temperature"] = r.lead_temperature
        state["funnel_stage"] = (
            resolve_funnel_stage(state.get("funnel_stage"), r.funnel_stage,
                                 (su or {}).get("funnel_stage")) or r.funnel_stage
        )
        state.update(BotManager._ai_memory_updates(
            state, r, r.action, r.message or "", r.next_question or ""))
        rec.add(lead_text=text, payload=payload, action=r.action, message=r.message,
                reason=r.reason, next_question=r.next_question, state_update=su,
                state_after=json.loads(json.dumps(state, default=str)), effect=effect)
        return r, spy, payload

    # ══════════════════════════════════════════════════════════════════════
    # 1) LEAD CURIOSO — avancar sem pressionar compra
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("1-lead-curioso")
    recs.append(rec)
    st = {"funnel_stage": "new"}
    infra.MOCK["outputs"] = [
        {"action": "ask_question", "message": "Oi! Tudo bem? O que te trouxe aqui hoje?",
         "next_question": "O que voce busca resolver primeiro?", "funnel_stage": "new"},
        {"action": "continue", "message": "Legal! Entendi seu interesse.",
         "funnel_stage": "qualification"},
    ]
    r1, spy1, _ = do_turn(rec, "s1a", st, "oi",
                          lead={"name": "Ana", "interest": "", "objection": ""},
                          offers=OFFERS_ACTIVE, allowed=OPEN,
                          conversation_state={"funnel_stage": "new", "lead_temperature": "warm", **AI_MEM_CTX})
    r2, spy2, _ = do_turn(rec, "s1b", st, "queria entender melhor o que voce oferece",
                          lead={"name": "Ana", "interest": "curso", "objection": ""},
                          offers=OFFERS_ACTIVE, allowed=OPEN,
                          conversation_state={"funnel_stage": st.get("funnel_stage"), "lead_temperature": "warm", **AI_MEM_CTX})
    no_checkout = "checkout" not in spy1.effects and "checkout" not in spy2.effects
    advanced = r1.action in ("ask_question", "continue") and r2.action in ("ask_question", "continue", "present_offer")
    check(1, "lead curioso avanca a conversa sem pressionar compra",
          no_checkout and advanced,
          f"t1={r1.action}/{spy1.effects} t2={r2.action}/{spy2.effects}")

    # ══════════════════════════════════════════════════════════════════════
    # 2) INTENCAO DE COMPRA — explicito vs sutil
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("2-intencao-compra")
    recs.append(rec)
    # 2a explicito
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Perfeito! Vamos finalizar.",
                              "funnel_stage": "offer"}]
    re, spe, _ = do_turn(rec, "s2a", st, "quero comprar agora",
                         lead={"name": "Ana", "interest": "curso", "objection": ""},
                         offers=OFFERS_ACTIVE, allowed=OPEN,
                         conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    check(2, "intencao EXPLICITA + oferta ativa -> conduz ao checkout",
          re.action == "send_checkout" and "checkout" in spe.effects,
          f"action={re.action} efeito={spe.effects} reason={re.reason}")
    # 2b sutil
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "present_offer", "message": "Tem o Curso Pro por R$ 97.",
                              "funnel_stage": "offer"}]
    rs, sps, _ = do_turn(rec, "s2b", st, "gostei muito, vou fechar",
                         lead={"name": "Ana", "interest": "curso", "objection": ""},
                         offers=OFFERS_ACTIVE, allowed=OPEN,
                         conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    subtle_ok = rs.action == "send_checkout"
    check(2, "intencao SUTIL + oferta apresentada -> conduz ao checkout",
          subtle_ok,
          f"action={rs.action} efeito={sps.effects} reason={rs.reason} "
          f"(gap de decisao do motor se != send_checkout)", quality=True)

    # ══════════════════════════════════════════════════════════════════════
    # 3) OBJECAO DE PRECO — mantem checkout bloqueado ate resolver
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("3-objecao-preco")
    recs.append(rec)
    # 3a lead objeta -> plataforma persiste
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "continue", "message": "Entendo! Me conta o que pesou no valor.",
                              "funnel_stage": "offer"}]
    r3a, sp3a, _ = do_turn(rec, "s3a", st, "achei muito caro",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    obj_persisted = st.get("objection") and (st.get("collected_information") or {}).get("objection")
    check(3, "objecao de preco detectada e persistida pela plataforma",
          bool(obj_persisted),
          f"objection={st.get('objection')!r} ci={st.get('collected_information')}")
    # 3b sinal de compra com objecao ativa -> checkout bloqueado
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar!",
                              "funnel_stage": "offer"}]
    r3b, sp3b, pl3b = do_turn(rec, "s3b", st, "quero fechar agora",
                              lead={"name": "Ana", "interest": "curso", "objection": st.get("objection") or ""},
                              offers=OFFERS_ACTIVE, allowed=OPEN,
                              conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    check(3, "objecao ativa + sinal de compra -> checkout permanece BLOQUEADO",
          r3b.action != "send_checkout" and "checkout" not in sp3b.effects,
          f"action={r3b.action} efeito={sp3b.effects} reason={r3b.reason}")
    # 3c resposta pertinente (esclarece) sem reapresentar oferta
    infra.MOCK["outputs"] = [{"action": "continue", "message": "O valor inclui acesso vitalicio e suporte.",
                              "funnel_stage": "offer"}]
    r3c, sp3c, _ = do_turn(rec, "s3c", st, "entendi, mas ainda acho caro",
                           lead={"name": "Ana", "interest": "curso", "objection": st.get("objection") or ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    check(3, "resposta a objecao e pertinente e nao reapresenta oferta/checkout",
          r3c.action in ("continue", "ask_question") and "checkout" not in sp3c.effects,
          f"action={r3c.action} efeito={sp3c.effects} reason={r3c.reason}")

    # ══════════════════════════════════════════════════════════════════════
    # 4) OBJECAO RESOLVIDA — libera checkout so com oferta ativa + permissao
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("4-objecao-resolvida")
    recs.append(rec)
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
          "objection": "achei muito caro",
          "collected_information": {"objection": "achei muito caro"}}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Otimo! Vamos finalizar.",
                              "funnel_stage": "offer"}]
    # Sinal de resolucao + sinal de compra RECONHECIDO pelo motor ("me passa o
    # link" esta em _DIRECT_PAYMENT_REQUEST_PHRASES). A frase natural "pode
    # mandar o link" NAO consta nas listas — observacao de qualidade (4c).
    r4a, sp4a, _ = do_turn(rec, "s4a", st, "entendi o valor, vale a pena, me passa o link",
                           lead={"name": "Ana", "interest": "curso"},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    resolved = (st.get("collected_information") or {}).get("objection_resolved") is True
    check(4, "objecao resolvida + oferta ativa/permitida -> libera checkout",
          resolved and r4a.action == "send_checkout" and "checkout" in sp4a.effects,
          f"resolved={resolved} action={r4a.action} efeito={sp4a.effects}")
    # 4b resolvida mas sem oferta ativa -> nao fecha
    st2 = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
           "collected_information": {"objection": "achei caro", "objection_resolved": True}}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar!",
                              "funnel_stage": "offer"}]
    r4b, sp4b, _ = do_turn(rec, "s4b", st2, "pode mandar o link",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_INACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    check(4, "resolvida mas oferta inativa -> checkout BLOQUEADO",
          r4b.action != "send_checkout" and "checkout" not in sp4b.effects,
          f"action={r4b.action} efeito={sp4b.effects} reason={r4b.reason}")
    # 4c QUALIDADE: frase natural equivalente nao e reconhecida como pedido de link
    st3 = {"funnel_stage": "offer", "offers_already_presented": ["of1"],
           "collected_information": {"objection": "achei caro", "objection_resolved": True}}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos finalizar.",
                              "funnel_stage": "offer"}]
    r4c, sp4c, _ = do_turn(rec, "s4c", st3, "pode mandar o link",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    check(4, "frase natural 'pode mandar o link' reconhecida como sinal de compra",
          r4c.action == "send_checkout",
          f"action={r4c.action} reason={r4c.reason} "
          f"(variante natural ausente das listas do motor)", quality=True)

    # ══════════════════════════════════════════════════════════════════════
    # 5) RECUSA EXPLICITA — respeitar e nao insistir
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("5-recusa")
    recs.append(rec)
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "ultima chance!",
                              "funnel_stage": "offer"}]
    r5, sp5, _ = do_turn(rec, "s5", st, "nao tenho interesse, me tira da lista",
                         lead={"name": "Ana", "interest": "curso", "objection": ""},
                         offers=OFFERS_ACTIVE, allowed=OPEN_WITH_SILENCE,
                         conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    check(5, "recusa explicita -> silencio, sem oferta/pergunta/checkout",
          r5.action == "do_not_respond" and sp5.effects == ["silence"],
          f"action={r5.action} efeito={sp5.effects} reason={r5.reason}")

    # ══════════════════════════════════════════════════════════════════════
    # 6) CONVERSA LONGA — contexto preservado, sem repetir, sem perder info
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("6-conversa-longa")
    recs.append(rec)
    st = {"funnel_stage": "qualification"}
    infra.MOCK["outputs"] = [
        {"action": "ask_question", "message": "Qual seu principal objetivo?",
         "next_question": "Qual seu principal objetivo?", "funnel_stage": "qualification"},
        {"action": "ask_question", "message": "Qual seu principal objetivo?",
         "next_question": "Qual seu principal objetivo?", "funnel_stage": "qualification"},
        {"action": "ask_question", "message": "Ha quanto tempo busca isso?",
         "next_question": "Ha quanto tempo busca isso?", "funnel_stage": "qualification"},
        {"action": "continue", "message": "Certo, anotei tudo que voce me contou.",
         "funnel_stage": "offer"},
    ]
    CS = lambda: {"funnel_stage": st.get("funnel_stage"), "lead_temperature": "warm", **AI_MEM_CTX}
    r6a, _, _ = do_turn(rec, "s6a", st, "quero melhorar minhas vendas",
                        lead={"name": "Ana", "interest": "vendas", "objection": ""},
                        offers=OFFERS_ACTIVE, allowed=OPEN, conversation_state=CS())
    asked_first = st.get("questions_already_asked") or []
    r6b, _, _ = do_turn(rec, "s6b", st, "ja falei, quero melhorar as vendas",
                        lead={"name": "Ana", "interest": "vendas", "objection": ""},
                        offers=OFFERS_ACTIVE, allowed=OPEN, conversation_state=CS())
    r6c, _, _ = do_turn(rec, "s6c", st, "comecei ano passado",
                        lead={"name": "Ana", "interest": "vendas", "objection": ""},
                        offers=OFFERS_ACTIVE, allowed=OPEN, conversation_state=CS())
    r6d, _, _ = do_turn(rec, "s6d", st, "pode seguir",
                        lead={"name": "Ana", "interest": "vendas", "objection": ""},
                        offers=OFFERS_ACTIVE, allowed=OPEN, conversation_state=CS())
    # repeticao: 2o turno pediu a MESMA pergunta ja feita -> motor deve suprimir
    repeated_allowed = r6b.next_question == "Qual seu principal objetivo?"
    ctx_preserved = bool((st.get("collected_information") or {})) or bool(st.get("questions_already_asked"))
    check(6, "pergunta repetida e suprimida (memoria respeitada)",
          not repeated_allowed,
          f"nq_t2={r6b.next_question!r} asked={len(asked_first)} reason={r6b.reason}")
    check(6, "contexto/informacao coletada preservados na conversa longa",
          ctx_preserved,
          f"ci={st.get('collected_information')} asked={st.get('questions_already_asked')}")

    # ══════════════════════════════════════════════════════════════════════
    # 7) ALEGACOES FALSAS — nao inventar desconto/urgencia/garantia/acao
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("7-alegacoes-falsas")
    recs.append(rec)
    # 7a acao externa concluida
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "continue",
                              "message": "ja enviei o link e seu pagamento foi aprovado",
                              "funnel_stage": "offer"}]
    r7a, sp7a, _ = do_turn(rec, "s7a", st, "ok",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    claim_gone = "ja enviei" not in (r7a.message or "").lower() and \
        "aprovado" not in (r7a.message or "").lower()
    check(7, "alegacao de acao externa concluida e bloqueada/substituida",
          claim_gone,
          f"msg={r7a.message!r} reason={r7a.reason}")
    # 7b garantia
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "present_offer",
                              "message": "Esse metodo tem resultado garantido, funciona 100%!",
                              "funnel_stage": "offer"}]
    r7b, sp7b, _ = do_turn(rec, "s7b", st, "me convence",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    guar_gone = "garantido" not in (r7b.message or "").lower() and "100%" not in (r7b.message or "")
    check(7, "alegacao de garantia de resultado e bloqueada/substituida",
          guar_gone,
          f"msg={r7b.message!r} reason={r7b.reason}")
    # 7c urgencia falsa
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "present_offer",
                              "message": "Corre que sao as ultimas vagas, acaba hoje!",
                              "funnel_stage": "offer"}]
    r7c, sp7c, _ = do_turn(rec, "s7c", st, "e se eu demorar?",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    urg_gone = "ultimas vagas" not in (r7c.message or "").lower() and "acaba hoje" not in (r7c.message or "").lower()
    check(7, "urgencia falsa (escassez) e bloqueada/substituida",
          urg_gone,
          f"msg={r7c.message!r} reason={r7c.reason}")
    # 7d desconto inventado (sem guard dedicado no mapa) -> rotulo de qualidade
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "present_offer",
                              "message": "Posso te dar um desconto especial de 50% so pra voce!",
                              "funnel_stage": "offer"}]
    r7d, sp7d, _ = do_turn(rec, "s7d", st, "ta caro, tem desconto?",
                           lead={"name": "Ana", "interest": "curso", "objection": ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    disc_gone = "desconto" not in (r7d.message or "").lower() and "50%" not in (r7d.message or "")
    check(7, "desconto inventado NAO e oferecido sem base (guard dedicado ausente)",
          disc_gone,
          f"msg={r7d.message!r} reason={r7d.reason}", quality=True)

    # ══════════════════════════════════════════════════════════════════════
    # 8) FALHA E RECUPERACAO — sem descarte nem duplicidade (limites testados)
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("8-falha-recuperacao")
    recs.append(rec)
    from internal_logic.services.ai_service import AIGatewayError

    # 8a motor indisponivel -> erro tipado (fallback controlado do Grimbots)
    dead = infra._svc(1)  # porta 1: inacessivel
    try:
        dead.respond(infra._payload("s8a", {"funnel_stage": "new"}, "oi", offers=OFFERS_ACTIVE, allowed_actions=OPEN))
        typed_err = False
    except AIGatewayError:
        typed_err = True
    except Exception:
        typed_err = False
    check(8, "motor indisponivel -> erro tipado (fallback controlado, sem crash)",
          typed_err, f"typed={typed_err}")
    # 8b 409 ai_enabled=false -> sem efeito (retomavel)
    try:
        svc.respond(infra._payload("s8b", {"funnel_stage": "offer"}, "oi",
                                   offers=OFFERS_ACTIVE, allowed_actions=OPEN,
                                   conversation_state={"funnel_stage": "offer", "lead_temperature": "warm",
                                                       "human_takeover": False, "ai_enabled": False}))
        got_409 = False
    except AIGatewayError as err:
        got_409 = err.status == 409
    check(8, "ia desabilitada -> 409 sem resposta (retomavel sem duplicar)",
          got_409, f"got_409={got_409}")
    # 8c retomada: objecao persistida entre turnos nao e descartada nem duplicada
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [
        {"action": "continue", "message": "Certo, sigo contigo.", "funnel_stage": "offer"},
        {"action": "send_checkout", "message": "Vamos fechar!", "funnel_stage": "offer"},
    ]
    do_turn(rec, "s8c1", st, "achei caro",
            lead={"name": "Ana", "interest": "curso", "objection": ""},
            offers=OFFERS_ACTIVE, allowed=OPEN,
            conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    obj1 = st.get("objection")
    r8c, sp8c, _ = do_turn(rec, "s8c2", st, "quero fechar",
                           lead={"name": "Ana", "interest": "curso", "objection": obj1 or ""},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "hot", **AI_MEM_CTX})
    # objecao preservada e checkout ainda bloqueado no retomar
    check(8, "retomada preserva objecao (sem descarte) e mantem checkout bloqueado",
          bool(obj1) and r8c.action != "send_checkout" and "checkout" not in sp8c.effects,
          f"obj={obj1!r} action={r8c.action} efeito={sp8c.effects}")

    # ══════════════════════════════════════════════════════════════════════
    # 9) SONDAS DE QUALIDADE COMERCIAL (para leads reais) — apenas observacao
    # ══════════════════════════════════════════════════════════════════════
    rec = ScenarioRecorder("9-sondas-qualidade")
    recs.append(rec)
    # 9a "carro" esta em _PRICE_WORDS: "vou comprar um carro" e lido como objecao
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "send_checkout", "message": "Vamos fechar!",
                              "funnel_stage": "offer"}]
    r9a, sp9a, _ = do_turn(rec, "s9a", st, "vou comprar um carro novo, preciso juntar dinheiro",
                           lead={"name": "Ana", "interest": "curso"},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    false_obj = st.get("objection")
    check(9, "sonda: texto com 'carro' NAO e tratado como objecao de preco",
          not false_obj,
          f"objection_falsamente_detectada={false_obj!r} action={r9a.action} "
          f"(falso positivo de _PRICE_WORDS)", quality=True)
    # 9b substring: "interessado" dentro de "desinteressado" casaria sinal de compra
    st = {"funnel_stage": "offer", "offers_already_presented": ["of1"]}
    infra.MOCK["outputs"] = [{"action": "continue", "message": "Sem problemas!",
                              "funnel_stage": "offer"}]
    r9b, sp9b, _ = do_turn(rec, "s9b", st, "estou desinteressado nesse tipo de coisa",
                           lead={"name": "Ana", "interest": "curso"},
                           offers=OFFERS_ACTIVE, allowed=OPEN,
                           conversation_state={"funnel_stage": "offer", "lead_temperature": "warm", **AI_MEM_CTX})
    substring_fp = r9b.action == "send_checkout"
    check(9, "sonda: 'desinteressado' NAO dispara sinal de compra (match por substring)",
          not substring_fp,
          f"action={r9b.action} reason={r9b.reason} "
          f"('interessado' esta em _SUBTLE_BUY_SIGNALS)", quality=True)

    # ── Impressao das transcricoes ──
    emit("\n" + "=" * 72)
    emit("TRANSCRICOES (motor REAL a54b9dd; Ollama/Telegram/checkout mockados)")
    emit("=" * 72)
    for rc in recs:
        emit(f"\n# Cenário {rc.name}")
        emit(rc.transcript())

    passed = sum(1 for _, _, ok, _, _ in results if ok)
    quality_fails = [r for r in results if not r[2] and r[4]]
    tech_fails = [r for r in results if not r[2] and not r[4]]
    emit(f"\n{passed}/{len(results)} verificacoes OK "
         f"(falhas tecnicas={len(tech_fails)}, falhas/observacoes de qualidade={len(quality_fails)})")
    return results, recs


def main():
    if not infra.MOTOR_DIR.exists() or not infra.VENV_PY.exists():
        print(f"SKIP: motor/venv ausentes (MOTOR_DIR={infra.MOTOR_DIR}, VENV_PY={infra.VENV_PY})")
        return 0

    import tempfile
    import subprocess
    import threading
    from http.server import ThreadingHTTPServer

    out_path = None
    if "--json" in sys.argv:
        out_path = sys.argv[sys.argv.index("--json") + 1]

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
    log = tempfile.NamedTemporaryFile("w+", suffix="-motor-scenarios.log", delete=False)
    proc = subprocess.Popen(
        [str(infra.VENV_PY), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(motor_port), "--log-level", "warning"],
        cwd=str(infra.MOTOR_DIR / "api"), env=env,
        stdout=log, stderr=subprocess.STDOUT,
    )
    ok = False
    results = []
    recs = []
    try:
        infra.wait_http(f"http://127.0.0.1:{motor_port}/health")
        print(f"→ motor no ar (mock ollama :{mock_port}, motor :{motor_port})")
        print(f"  MOTOR_DIR={infra.MOTOR_DIR}\n")
        results, recs = run_scenarios(motor_port)
        ok = all(r[2] for r in results)
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

    if out_path:
        data = {
            "results": [
                {"id": r[0], "name": r[1], "ok": r[2], "detail": r[3], "quality": r[4]}
                for r in results
            ],
            "transcripts": [
                {"name": rc.name, "turns": rc.turns} for rc in recs
            ],
        }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"\n→ resultados em JSON: {out_path}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
