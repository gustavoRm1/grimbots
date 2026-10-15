"""
Contrato da Grimbots AI API — POST /v1/agent/respond (v1.0.0).

Offline (sempre roda):
  - payload montado pelo construtor bate com o golden tests/payloads/*.json
  - nenhum campo proibido (model/system_prompt) e enviado  -> extra=forbid
  - limites do contrato (historico <=20, ofertas <=20, ids <=80)
  - resposta capturada do Gateway real parseia em AIResult

Ao vivo (opt-in):
  python tests/test_agent_respond_contract.py --live
  (usa GRIMBOTS_AI_API_URL / GRIMBOTS_AI_API_KEY do .env ou do ambiente)
"""

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from internal_logic.services.ai_service import (  # noqa: E402
    ACTIONS,
    AIResult,
    AIGatewayError,
    GrimbotsAIService,
    MAX_HISTORY_MESSAGES,
    MAX_OFFERS,
    MAX_PAYLOAD_BYTES,
    MockAIService,
    build_payload,
)

PAYLOADS = Path(__file__).resolve().parent / "payloads"

# ── Fixture: uma config de bloco 'ai' como o Flow Editor persiste ──────────
AI_STEP_CONFIG = {
    "enabled": True,
    "bot_name": "Maya",
    "personality": "confiante, carinhosa",
    "tone": "intimo",
    "boldness": 3,
    "message_length": "short",
    "emoji_level": "moderate",
    "commercial_goal": "qualificar_e_converter",
    "mode": "auto",
    "funnel_stage": "qualification",
    "intro_message": "Oi! Me conte o que voce precisa.",
    "fallback_message": "Nao consegui processar. Pode reenviar?",
    "allowed_actions": ["continue", "ask_question", "present_offer", "send_checkout"],
    "offers": [
        {"id": "premium", "name": "Plano Premium", "price": 49.9, "active": True},
        {"id": "basico", "name": "Plano Basico", "price": 19.97, "checkout_url": "", "active": False},
    ],
}

FIXTURE_KWARGS = {
    "request_id": "gb-140-8142273932-abc1234567",
    "seller_id": "1",
    "bot_id": "140",
    "conversation_id": "c140-8142273932",
    "bot_user_id": "8142273932",
    "bot_config": {
        "name": AI_STEP_CONFIG["bot_name"],
        "personality": AI_STEP_CONFIG["personality"],
        "tone": AI_STEP_CONFIG["tone"],
        "boldness": AI_STEP_CONFIG["boldness"],
        "message_length": AI_STEP_CONFIG["message_length"],
        "emoji_level": AI_STEP_CONFIG["emoji_level"],
        "commercial_goal": AI_STEP_CONFIG["commercial_goal"],
    },
    "conversation_state": {
        "funnel_stage": AI_STEP_CONFIG["funnel_stage"],
        "lead_temperature": "warm",
        "human_takeover": False,
        "ai_enabled": True,
    },
    "lead": {"name": "Ana", "interest": "", "objection": "preco"},
    "recent_messages": [
        {"role": "assistant", "content": "Oi! Me conte o que voce precisa."},
        {"role": "user", "content": "Gostei, mas achei caro."},
    ],
    "conversation_summary": "",
    "available_offers": [
        {"id": "premium", "name": "Plano Premium", "price": "49.9", "checkout_url": "", "active": True},
        {"id": "basico", "name": "Plano Basico", "price": "19.97", "checkout_url": "", "active": False},
    ],
    "allowed_actions": AI_STEP_CONFIG["allowed_actions"],
    "mode": "auto",
}

# Resposta 200 capturada do Gateway real (2026-01-..) - nao editar.
CAPTURED_RESPONSE = {
    "request_id": "req-test-1",
    "model": "grimbots-sales:latest",
    "message": "Entendo que pode parecer caro, mas com esse plano voce ganha muito mais.",
    "intent": "objecao",
    "lead_temperature": "warm",
    "funnel_stage": "qualification",
    "action": "present_offer",
    "next_question": None,
    "handoff_human": False,
    "risk": "low",
    "validation": {"valid": True, "errors": []},
    "usage": {"latency_ms": 6131, "input_tokens": 692, "output_tokens": 83},
}


# ══════════════════════════════════════════════════════════════════════════
# OFFLINE
# ══════════════════════════════════════════════════════════════════════════
def test_build_payload_matches_golden():
    payload = build_payload(**FIXTURE_KWARGS)
    golden_path = PAYLOADS / "agent_respond_request.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert payload == golden, (
        "Payload difere do golden.\n"
        f"esperado: {json.dumps(golden, ensure_ascii=False, sort_keys=True)}\n"
        f"obtido:   {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def test_payload_never_sends_forbidden_fields():
    """extra=forbid no Gateway: model/system_prompt derrubam a requisicao."""
    payload = build_payload(**FIXTURE_KWARGS)
    for forbidden in ("model", "system_prompt", "temperature", "top_p"):
        assert forbidden not in payload, f"campo proibido '{forbidden}' presente"
    for forbidden in ("model", "system_prompt"):
        assert forbidden not in payload["bot_config"], f"bot_config contem '{forbidden}'"


def test_payload_shapes_are_strings_and_within_limits():
    payload = build_payload(**FIXTURE_KWARGS)
    for key in ("request_id", "seller_id", "bot_id", "conversation_id", "bot_user_id"):
        assert isinstance(payload[key], str), f"{key} deve ser str"
        assert 1 <= len(payload[key]) <= 80, f"{key} fora de 1..80"
    assert payload["mode"] in ("shadow", "suggestion", "auto")
    assert set(payload["allowed_actions"]).issubset(set(ACTIONS))
    assert isinstance(payload["conversation_state"]["funnel_stage"], str)
    assert isinstance(payload["conversation_state"]["lead_temperature"], str)


def test_history_and_offers_limits():
    big = [dict(role="user", content="m" * 5000) for _ in range(50)]
    payload = build_payload(recent_messages=big, **{k: v for k, v in FIXTURE_KWARGS.items()
                                                   if k != "recent_messages"})
    assert len(payload["recent_messages"]) <= MAX_HISTORY_MESSAGES
    for m in payload["recent_messages"]:
        assert len(m["content"]) <= 1200, "conteudo de mensagem deve ser truncado em 1200"

    offers = [{"id": str(i), "name": f"Oferta {i}", "price": "9.90", "active": True}
              for i in range(40)]
    payload = build_payload(available_offers=offers, **{k: v for k, v in FIXTURE_KWARGS.items()
                                                        if k != "available_offers"})
    assert len(payload["available_offers"]) <= MAX_OFFERS


def test_empty_history_raises():
    try:
        build_payload(recent_messages=[], **{k: v for k, v in FIXTURE_KWARGS.items()
                                             if k != "recent_messages"})
    except AIGatewayError as err:
        assert err.code == "VALIDATION_ERROR"
    else:
        raise AssertionError("historico vazio deveria dar VALIDATION_ERROR")


def test_captured_response_parses():
    result = AIResult.from_dict(CAPTURED_RESPONSE)
    assert result.action == "present_offer"
    assert result.intent == "objecao"
    assert result.valid is True
    assert result.risk == "low"
    assert result.handoff_human is False
    assert result.usage["latency_ms"] == 6131

    golden_path = PAYLOADS / "agent_respond_response.json"
    assert json.loads(golden_path.read_text(encoding="utf-8")) == CAPTURED_RESPONSE


def test_unknown_action_falls_back_to_continue():
    result = AIResult.from_dict(dict(CAPTURED_RESPONSE, action="send_link"))
    assert result.action == "continue"


def test_unconfigured_service_fails_closed():
    svc = GrimbotsAIService("", "")
    assert svc.configured is False
    try:
        svc.respond(build_payload(**FIXTURE_KWARGS))
    except AIGatewayError as err:
        assert err.code == "API_KEY_NOT_CONFIGURED"
    else:
        raise AssertionError("servico sem chave deveria falhar fechado")


def test_oversized_payload_rejected_locally():
    payload = build_payload(**FIXTURE_KWARGS)
    svc = GrimbotsAIService("http://127.0.0.1:9", "gp_x", 1)
    # infla o payload alem do limite do servidor
    payload["conversation_summary"] = "x" * MAX_PAYLOAD_BYTES
    try:
        svc.respond(payload)
    except AIGatewayError as err:
        assert err.code == "PAYLOAD_TOO_LARGE"
        assert err.status == 413
    else:
        raise AssertionError("payload gigante deveria ser rejeitado antes da rede")


def test_mock_service_covers_main_actions():
    mock = MockAIService()
    seen = set()
    for text in ("quanto custa?", "quero comprar", "voce e um bosta", "oi", "obrigado", "?"):
        result = mock.respond(build_payload(
            recent_messages=[{"role": "user", "content": text}], **{
                k: v for k, v in FIXTURE_KWARGS.items() if k != "recent_messages"}))
        assert isinstance(result, AIResult)
        assert result.action in ACTIONS
        assert result.message
        seen.add(result.action)
    assert len(seen) >= 4, f"mock cobriu poucas acoes: {seen}"


# ══════════════════════════════════════════════════════════════════════════
# AO VIVO (opt-in: --live)
# ══════════════════════════════════════════════════════════════════════════
def test_live_gateway():
    import uuid

    api_url = os.environ.get("GRIMBOTS_AI_API_URL", "").rstrip("/")
    api_key = os.environ.get("GRIMBOTS_AI_API_KEY", "")
    if not api_url or not api_key:
        print("⏭️  LIVE pulado: GRIMBOTS_AI_API_URL/GRIMBOTS_AI_API_KEY ausentes")
        return

    payload = build_payload(**dict(FIXTURE_KWARGS, request_id=f"gb-live-{uuid.uuid4().hex[:16]}"))
    svc = GrimbotsAIService(api_url, api_key, float(os.environ.get("GRIMBOTS_AI_TIMEOUT", 90)))
    result = svc.respond(payload)

    assert result.action in ACTIONS, f"action invalida: {result.action}"
    assert result.intent, "intent vazio"
    assert result.lead_temperature in ("cold", "warm", "hot")
    assert result.funnel_stage in ("new", "connection", "qualification", "offer",
                                   "checkout", "customer", "human")
    assert result.risk in ("low", "medium", "high")
    assert isinstance(result.valid, bool)
    assert isinstance(result.message, str)
    if result.action == "send_checkout":
        assert result.handoff_human is False, "send_checkout com handoff simultaneo"
    print(f"✅ LIVE ok: action={result.action} intent={result.intent} "
          f"risk={result.risk} latency={(result.usage or {}).get('latency_ms')}ms")


if __name__ == "__main__":
    import traceback

    offline = [fn for name, fn in sorted(globals().items())
               if name.startswith("test_") and name != "test_live_gateway"]
    failures = 0
    for fn in offline:
        try:
            fn()
            print(f"✅ {fn.__name__}")
        except Exception:
            failures += 1
            print(f"❌ {fn.__name__}")
            traceback.print_exc()

    if "--live" in sys.argv:
        try:
            test_live_gateway()
        except Exception:
            failures += 1
            print("❌ test_live_gateway")
            traceback.print_exc()

    print(f"\n{len(offline) - failures}/{len(offline)} offline OK")
    sys.exit(1 if failures else 0)
