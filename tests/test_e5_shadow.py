"""
E5 — execução SHADOW da decisão comercial (offline, flag DESLIGADA por padrão).

Garante os invariantes do plano E5:
  - desligado por padrão (dupla flag) => no-op puro;
  - SEM efeitos externos (nunca send/route/state);
  - SEM duplicar persistência de estado;
  - privacidade (HMAC do lead; sem texto cru; summary excluído);
  - falha do shadow é fail-open;
  - comparação não presume que a ação real estava correta;
  - idempotência por request_id.

Não faz rede, não toca Redis/Telegram/DB.
  python tests/test_e5_shadow.py
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from internal_logic.services import ai_shadow as shadow  # noqa: E402
from internal_logic.services.ai_service import AIResult  # noqa: E402
from bot_manager import BotManager  # noqa: E402


def _payload():
    return {
        "request_id": "gb-1-2-abc",
        "mode": "shadow",
        "contract_version": "1.1",
        "conversation_state": {"funnel_stage": "qualification", "lead_temperature": "warm",
                               "human_takeover": False, "ai_enabled": True},
        "lead": {"name": "Joao da Silva", "interest": "plano premium",
                 "objection": "esta caro"},
        "recent_messages": [
            {"role": "user", "content": "oi, quanto custa?"},
            {"role": "assistant", "content": "oi!"},
        ],
        "conversation_summary": "lead tem cpf 123.456.789-00 e cartao 4111",
        "context_policy": {"include_current_node": True, "allowed_actions": ["present_offer"]},
        "collected_information": {"nome": "Joao", "email": "j@x.com"},
        "questions_already_asked": ["qual seu nome?", "qual seu email?"],
        "turn_count": 3,
    }


# ── Gate ───────────────────────────────────────────────────────────────────
def test_gate_default_off():
    assert shadow.shadow_gate("off", {"shadow": True}) is False
    assert shadow.shadow_gate("", {"shadow": True}) is False
    assert shadow.shadow_gate("on", {}) is False
    assert shadow.shadow_gate("on", {"shadow": False}) is False
    assert shadow.shadow_gate("on", {"shadow": True}) is True


def test_sample_hit_bounds():
    assert shadow.sample_hit(1, "abc", 0) is False
    assert shadow.sample_hit(1, "abc", 1) is True
    assert shadow.sample_hit(1, "abc", 2) is True
    a = shadow.sample_hit(1, "abc", 0.5)
    b = shadow.sample_hit(1, "abc", 0.5)
    assert a == b  # determinístico


# ── Privacidade / redaction ─────────────────────────────────────────────────
def test_redact_has_no_raw_pii():
    redacted, digest = shadow.redact_context(_payload(), secret="segredo")
    blob = json.dumps(redacted, ensure_ascii=False)
    assert "Joao da Silva" not in blob
    assert "j@x.com" not in blob
    assert "caro" not in blob
    assert "quanto custa" not in blob
    assert "123.456.789-00" not in blob          # conversation_summary nunca entra
    assert "4111" not in blob
    assert redacted["lead"] == {"has_name": True, "has_interest": True, "has_objection": True}
    assert redacted["collected_information_keys"] == ["email", "nome"]
    assert redacted["recent_messages_count"] == 2
    assert len(digest) == 64
    # digest é estável e independente de texto bruto
    _, digest2 = shadow.redact_context(_payload(), secret="segredo")
    assert digest == digest2


def test_redact_include_text_is_truncated_and_sanitized():
    redacted, _ = shadow.redact_context(
        _payload(), secret="s", include_text=True, max_text_chars=5
    )
    assert redacted["last_user_excerpt"] == "oi, q"[:5] or len(redacted["last_user_excerpt"]) <= 5
    html, _ = shadow.redact_context(
        {"recent_messages": [{"role": "user", "content": "<b>oi</b> mundo"}]},
        secret="s", include_text=True, max_text_chars=20,
    )
    assert "<b>" not in html["last_user_excerpt"]


def test_lead_reference_is_not_reversible():
    ref = shadow.lead_reference("8142273932", "segredo")
    assert ref != "8142273932"
    assert "8142273932" not in ref
    assert ref == shadow.lead_reference("8142273932", "segredo")  # estável
    assert ref != shadow.lead_reference("8142273932", "outro")    # muda com segredo


# ── Comparação ──────────────────────────────────────────────────────────────
def test_compare_does_not_presume_real_is_correct():
    cmp = shadow.compare_decisions(
        {"action": "handoff_human", "funnel_stage": "human"},
        {"action": "present_offer", "funnel_stage": "offer"},
    )
    assert cmp["action_match"] is False
    assert cmp["proposed_action"] == "handoff_human"
    assert cmp["observed_action"] == "present_offer"
    assert cmp["funnel_delta"] == 3  # human(6) - offer(3)
    match = shadow.compare_decisions({"action": "continue"}, {"action": "continue"})
    assert match["action_match"] is True
    assert match["funnel_delta"] is None  # estágio ausente não inventa delta


def test_shadow_request_id_within_motor_limit():
    rid = shadow.make_shadow_request_id("gb-1-2-" + "x" * 90)
    assert rid.startswith("shadow-")
    assert len(rid) <= 80


# ── run_shadow: happy path + isolamento de falha ────────────────────────────
class _Result:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_run_shadow_happy_path_records_comparison():
    collected = []
    result = _Result(action="present_offer", intent="interesse", funnel_stage="offer",
                     lead_temperature="warm", risk="low", offer_id="OF1",
                     model="grimbots-sales:latest", valid=True, usage={"latency_ms": 7})
    shadow.run_shadow(
        respond=lambda p: result, payload=_payload(),
        observed={"action": "continue", "intent": "duvida", "funnel_stage": "qualification",
                  "lead_temperature": "warm", "source": "v1.0_production"},
        bot_id=1, lead_ref="ref", request_id="shadow-r1", meta={"contract_version": "1.1"},
        record=lambda r: collected.append(r), secret="s", include_text=False,
    )
    assert len(collected) == 1
    row = collected[0]
    assert row["request_id"] == "shadow-r1"
    assert row["proposed_action"] == "present_offer"
    assert row["observed_action"] == "continue"
    assert row["action_match"] is False
    assert row["funnel_delta"] == 1
    assert row["latency_ms"] == 7
    assert row["context_digest"] and len(row["context_digest"]) == 64
    assert "Joao da Silva" not in (row["context_json"] or "")
    assert row["error_code"] is None


def test_run_shadow_failure_is_isolated_and_recorded():
    collected = []

    def _boom(_payload):
        raise RuntimeError("motor caiu")

    assert shadow.run_shadow(
        respond=_boom, payload=_payload(),
        observed={"action": "continue"}, bot_id=1, lead_ref="ref",
        request_id="shadow-r2", record=lambda r: collected.append(r), secret="s",
    ) is None
    assert len(collected) == 1
    assert collected[0]["error_code"] == "SHADOW_ERROR"
    assert collected[0]["observed_action"] == "continue"


def test_run_shadow_recorder_failure_is_isolated():
    def _bad_record(_row):
        raise RuntimeError("db fora")

    # não deve propagar
    assert shadow.run_shadow(
        respond=lambda p: _Result(action="continue", usage={}),
        payload=_payload(), observed={"action": "continue"}, bot_id=1,
        lead_ref="ref", request_id="shadow-r3", record=_bad_record, secret="s",
    ) is None


# ── Integração isolada: _ai_dispatch_shadow NÃO produz efeito ───────────────
def test_dispatch_shadow_has_no_side_effects_and_persists_only_shadow():
    import internal_logic.services.ai_service as a_svc
    from flask import Flask

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="k" * 32, GRIMBOTS_AI_SHADOW_SECRET="hmac",
        GRIMBOTS_AI_SHADOW_SAMPLE=1.0, GRIMBOTS_AI_SHADOW_INCLUDE_TEXT=False,
        GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS=0,
        GRIMBOTS_AI_MOTOR_VERSION="1.6.0", GRIMBOTS_AI_MOTOR_COMMIT="a3ccecf",
    )

    collected = []
    original_get = a_svc.get_ai_service
    original_record = shadow.record_shadow_decision
    original_dispatcher = shadow._DISPATCHER
    a_svc.get_ai_service = lambda: type("S", (), {"respond": staticmethod(
        lambda p: _Result(action="send_checkout", intent="compra", funnel_stage="checkout",
                          lead_temperature="hot", risk="low", offer_id=None,
                          model="m", valid=True, usage={"latency_ms": 3}))})()
    shadow.record_shadow_decision = lambda row: collected.append(row)
    shadow.set_dispatcher(shadow._InlineDispatcher())

    mgr = BotManager.__new__(BotManager)
    mgr.user_id = 7

    def _must_not_call(*_a, **_k):
        raise AssertionError("shadow não pode produzir efeito externo")

    for name in ("send_telegram_message", "_ai_route", "_ai_state_atomic",
                 "_ai_state_set", "_ai_turn_claim"):
        setattr(mgr, name, _must_not_call)
    mgr._ai_v11_payload_kwargs = lambda *a, **k: {"agent_profile": {"name": "x"}}
    mgr._ai_memory_payload = lambda state: {"turn_count": 1}

    try:
        with app.app_context():
            mgr._ai_dispatch_shadow(
                bot_id=1, telegram_user_id="8142273932", config={}, step={"id": "s1"},
                step_config={"shadow": True}, history=[{"role": "user", "content": "quero"}],
                state={"funnel_stage": "offer"}, request_id="gb-1-2-abc",
                observed={"action": "present_offer", "intent": "interesse",
                          "funnel_stage": "offer", "lead_temperature": "warm",
                          "source": "v1.0_production"},
                build_payload_fn=lambda extra: {**_payload(), **extra},
                secret="hmac", sample_rate=1.0, include_text=False, max_text_chars=0,
                motor_version="1.6.0", motor_commit="a3ccecf",
            )
    finally:
        a_svc.get_ai_service = original_get
        shadow.record_shadow_decision = original_record
        shadow.set_dispatcher(original_dispatcher)

    assert len(collected) == 1
    row = collected[0]
    assert row["observed_action"] == "present_offer"
    assert row["proposed_action"] == "send_checkout"
    assert row["action_match"] is False
    assert row["motor_version"] == "1.6.0"
    assert row["motor_commit"] == "a3ccecf"
    assert "8142273932" not in json.dumps(row)


def test_ai_shadow_enabled_respects_global_and_block():
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        app.config["GRIMBOTS_AI_SHADOW"] = "off"
        assert BotManager._ai_shadow_enabled({"shadow": True}) is False
        app.config["GRIMBOTS_AI_SHADOW"] = "on"
        assert BotManager._ai_shadow_enabled({"shadow": True}) is True
        assert BotManager._ai_shadow_enabled({"shadow": False}) is False
        assert BotManager._ai_shadow_enabled({}) is False


# ── Runner ──────────────────────────────────────────────────────────────────
def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"✅ {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"💥 {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} offline OK")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
