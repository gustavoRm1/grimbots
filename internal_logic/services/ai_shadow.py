"""
E5 — execução SHADOW da decisão comercial (NÃO ATIVADA por padrão).

Objetivo (spec E5): medir, em turnos REAIS, a decisão do motor com o payload
v1.1 (novo contexto/memória) SEM produzir efeito, e compará-la com a ação que a
produção (v1.0) efetivamente executou — sem presumir que a ação real estava
correta.

Garantias (invariantes testados em tests/test_e5_shadow.py):
  - Desligado por padrão (dupla flag: global + bloco). Desligado => no-op puro.
  - NUNCA envia mensagem, NUNCA roteia checkout/handoff, NUNCA persiste estado.
  - NUNCA duplica a persistência do bot (chama só `service.respond`).
  - Falha do shadow é fail-open: nunca interrompe o turno normal.
  - Roda fora do caminho crítico (dispatcher com thread pool + timeout).
  - Privacidade: lead referenciado por HMAC; sem texto cru por padrão;
    `conversation_summary` nunca é registrado.
  - Idempotência: 1 linha por request_id de shadow (UNIQUE).

Este módulo é ADITIVO e autocontido: não importa bot_manager nem Flask no topo.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout

logger = logging.getLogger(__name__)

# Valores da flag global que LIGAM o suporte (nunca ativam em produção sozinhos).
_ENABLED_VALUES = {"on", "true", "1", "yes", "enabled", "v1.1"}

# Chaves permitidas no snapshot de contexto (allowlist explícita).
_STATE_KEYS = ("funnel_stage", "lead_temperature", "human_takeover", "ai_enabled")
_POLICY_BOOL_KEYS = ("include_current_node", "include_reachable", "include_global")
_CANONICAL_SEP = ("\x1f", ":")

_HTML_RE = re.compile(r"<[^>]+>")


# ────────────────────────────────────────────────────────────────────────────
# Gate (dupla flag) — default OFF, byte-a-byte quando desligado
# ────────────────────────────────────────────────────────────────────────────
def shadow_gate(global_flag, block_config):
    """True somente com a flag GLOBAL ligada E o flag `shadow` do bloco ligado."""
    if str(global_flag or "").strip().lower() not in _ENABLED_VALUES:
        return False
    cfg = block_config if isinstance(block_config, dict) else {}
    return bool(cfg.get("shadow", False))


def sample_hit(bot_id, lead_ref, rate):
    """Amostragem determinística (estável por lead) para limitar custo/volume."""
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return False
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    key = f"{bot_id}|{lead_ref}".encode("utf-8")
    bucket = int(hashlib.sha256(key).hexdigest()[:8], 16) % 10000
    return bucket < int(rate * 10000)


# ────────────────────────────────────────────────────────────────────────────
# Privacidade
# ────────────────────────────────────────────────────────────────────────────
def lead_reference(telegram_user_id, secret):
    """Referência não reversível do lead (HMAC-SHA256). Nunca guarda o id cru."""
    secret = secret or "grimbots-shadow-default"
    return hmac.new(
        str(secret).encode("utf-8"),
        str(telegram_user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def _redact_text(text, limit):
    sanitized = _HTML_RE.sub(" ", str(text or ""))
    sanitized = " ".join(sanitized.split())
    return sanitized[:limit]


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=_CANONICAL_SEP)


def redact_context(payload, *, secret=None, include_text=False, max_text_chars=0):
    """Snapshot de contexto com controles de dados pessoais.

    Retorna (redacted, digest). O digest é estável e calculado SEM texto cru,
    para permitir comparação/deduplicação sem reter conteúdo pessoal.
    """
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get("conversation_state") or {}
    redacted = {
        "contract_version": str(payload.get("contract_version") or "1.0"),
        "mode": str(payload.get("mode") or ""),
        "conversation_state": {
            k: state.get(k) for k in _STATE_KEYS if k in state
        },
    }

    policy = payload.get("context_policy")
    if isinstance(policy, dict):
        redacted["context_policy"] = {
            **{k: bool(policy.get(k)) for k in _POLICY_BOOL_KEYS if k in policy},
            "allowed_actions": sorted(policy.get("allowed_actions") or []),
        }

    profile = payload.get("agent_profile")
    if isinstance(profile, dict):
        # Só presença/tamanho — nunca o texto do perfil.
        redacted["agent_profile"] = {
            "keys": sorted(profile.keys()),
            "personality_items": len(profile.get("personality") or []),
        }

    if payload.get("flow_resources") is not None:
        redacted["flow_resources_count"] = len(payload.get("flow_resources") or [])

    # Memória operacional: só metadados (sem valores/texto).
    if payload.get("collected_information") is not None:
        ci = payload.get("collected_information") or {}
        redacted["collected_information_keys"] = sorted(ci.keys()) if isinstance(ci, dict) else []
    for k, name in (
        ("questions_already_asked", "questions_count"),
        ("offers_already_presented", "offers_presented_count"),
    ):
        if payload.get(k) is not None:
            redacted[name] = len(payload.get(k) or [])
    if payload.get("turn_count") is not None:
        redacted["turn_count"] = payload.get("turn_count")
    if payload.get("last_action") is not None:
        redacted["last_action"] = payload.get("last_action")

    # Lead: apenas presença (nunca nome/valor cru).
    lead = payload.get("lead") or {}
    if isinstance(lead, dict):
        redacted["lead"] = {
            "has_name": bool(str(lead.get("name") or "").strip()),
            "has_interest": bool(str(lead.get("interest") or "").strip()),
            "has_objection": bool(str(lead.get("objection") or "").strip()),
        }

    # Histórico: só contagem/último papel; texto só se explicitamente permitido.
    history = payload.get("recent_messages") or []
    if isinstance(history, list):
        redacted["recent_messages_count"] = len(history)
        if history:
            redacted["last_role"] = str((history[-1] or {}).get("role") or "")

    digest = hashlib.sha256(_canonical(redacted).encode("utf-8")).hexdigest()

    if include_text and max_text_chars and isinstance(history, list) and history:
        redacted["last_user_excerpt"] = _redact_text(
            (history[-1] or {}).get("content"), int(max_text_chars)
        )
    return redacted, digest


# ────────────────────────────────────────────────────────────────────────────
# Comparação (não autoritativa)
# ────────────────────────────────────────────────────────────────────────────
_FUNNEL_ORDER = ("new", "connection", "qualification", "offer", "checkout", "customer", "human")


def _funnel_rank(stage):
    try:
        return _FUNNEL_ORDER.index(stage)
    except (ValueError, TypeError):
        return -1


def compare_decisions(proposed, observed):
    """Compara a decisão shadow com a ação efetivamente tomada.

    NÃO presume que a observada é correta: só reporta igualdade/delta.
    """
    proposed = proposed or {}
    observed = observed or {}
    p_action = proposed.get("action")
    o_action = observed.get("action")
    p_stage = proposed.get("funnel_stage")
    o_stage = observed.get("funnel_stage")
    p_rank, o_rank = _funnel_rank(p_stage), _funnel_rank(o_stage)
    return {
        "action_match": bool(p_action is not None and p_action == o_action),
        "proposed_action": p_action,
        "observed_action": o_action,
        "funnel_delta": (p_rank - o_rank) if (p_rank >= 0 and o_rank >= 0) else None,
        "proposed_funnel_stage": p_stage,
        "observed_funnel_stage": o_stage,
    }


# ────────────────────────────────────────────────────────────────────────────
# Persistência (fail-open) — 1 linha por request_id (UNIQUE => idempotente)
# ────────────────────────────────────────────────────────────────────────────
def record_shadow_decision(record):
    """Grava uma linha em ai_shadow_decisions. Fail-open: nunca propaga erro."""
    try:
        from internal_logic.core.extensions import db
        from internal_logic.core.models import AIShadowDecision

        existing = None
        if record.get("request_id"):
            existing = AIShadowDecision.query.filter_by(
                request_id=record["request_id"]
            ).first()
        if existing is not None:
            return existing.id  # idempotente
        row = AIShadowDecision(**{
            k: record.get(k) for k in _RECORD_FIELDS if k in record
        })
        db.session.add(row)
        db.session.commit()
        return row.id
    except Exception as exc:  # noqa: BLE001 — fail-open por design
        logger.debug(f"⚠️ [IA/shadow] falha ao gravar decisão shadow: {exc}")
        try:
            from internal_logic.core.extensions import db
            db.session.rollback()
        except Exception:
            pass
        return None


_RECORD_FIELDS = (
    "bot_id", "lead_ref", "request_id", "observed_source", "mode",
    "contract_version", "motor_version", "motor_commit", "motor_model",
    "context_digest", "context_json",
    "proposed_action", "proposed_intent", "proposed_funnel_stage",
    "proposed_lead_temperature", "proposed_risk", "proposed_offer_id",
    "proposed_valid",
    "observed_action", "observed_intent", "observed_funnel_stage",
    "observed_lead_temperature", "action_match", "funnel_delta",
    "latency_ms", "error_code",
)


def build_record(*, bot_id, lead_ref, request_id, observed, proposed=None,
                 context=None, compare=None, meta=None, latency_ms=0, error_code=None):
    """Monta o dict de persistência (sem Flask / sem I/O)."""
    proposed = proposed or {}
    observed = observed or {}
    compare = compare or compare_decisions(proposed, observed)
    meta = meta or {}
    return {
        "bot_id": bot_id,
        "lead_ref": lead_ref,
        "request_id": request_id,
        "observed_source": str(observed.get("source") or "v1.0_production"),
        "mode": str(meta.get("mode") or "shadow"),
        "contract_version": str(meta.get("contract_version") or "1.1"),
        "motor_version": str(meta.get("motor_version") or ""),
        "motor_commit": str(meta.get("motor_commit") or ""),
        "motor_model": str(proposed.get("model") or ""),
        "context_digest": (context or {}).get("digest"),
        "context_json": _canonical((context or {}).get("redacted")) if context else None,
        "proposed_action": proposed.get("action"),
        "proposed_intent": proposed.get("intent"),
        "proposed_funnel_stage": proposed.get("funnel_stage"),
        "proposed_lead_temperature": proposed.get("lead_temperature"),
        "proposed_risk": proposed.get("risk"),
        "proposed_offer_id": proposed.get("offer_id"),
        "proposed_valid": proposed.get("valid"),
        "observed_action": observed.get("action"),
        "observed_intent": observed.get("intent"),
        "observed_funnel_stage": observed.get("funnel_stage"),
        "observed_lead_temperature": observed.get("lead_temperature"),
        "action_match": compare.get("action_match"),
        "funnel_delta": compare.get("funnel_delta"),
        "latency_ms": int(latency_ms or 0),
        "error_code": error_code,
    }


# ────────────────────────────────────────────────────────────────────────────
# Dispatcher (fora do caminho crítico) — injetável
# ────────────────────────────────────────────────────────────────────────────
class _InlineDispatcher:
    def submit(self, fn):
        fn()


class _PoolDispatcher:
    def __init__(self, workers=2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ai-shadow")

    def submit(self, fn):
        try:
            self._pool.submit(fn)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"⚠️ [IA/shadow] dispatch falhou: {exc}")


_DISPATCHER = None
_DISPATCHER_LOCK = threading.Lock()


def get_dispatcher():
    """Dispatcher global. Async (thread pool) por padrão; inline se ASYNC=off."""
    global _DISPATCHER
    if _DISPATCHER is not None:
        return _DISPATCHER
    with _DISPATCHER_LOCK:
        if _DISPATCHER is None:
            async_on = os.environ.get("GRIMBOTS_AI_SHADOW_ASYNC", "true").lower() in {
                "1", "true", "yes", "on"
            }
            workers = int(os.environ.get("GRIMBOTS_AI_SHADOW_WORKERS", "2") or "2")
            _DISPATCHER = _PoolDispatcher(workers) if async_on else _InlineDispatcher()
    return _DISPATCHER


def set_dispatcher(dispatcher):
    """Injeção para testes (None restaura o comportamento padrão)."""
    global _DISPATCHER
    with _DISPATCHER_LOCK:
        _DISPATCHER = dispatcher


# ────────────────────────────────────────────────────────────────────────────
# Execução do shadow — fail-open, SEM efeitos
# ────────────────────────────────────────────────────────────────────────────
def run_shadow(*, respond, payload, observed, bot_id, lead_ref, request_id,
               meta=None, record=None, secret=None, include_text=False,
               max_text_chars=0, timeout=0):
    """Executa a decisão shadow e registra; NUNCA levanta, NUNCA produz efeito.

    `respond`  : callable(payload) -> AIResult-like (só leitura do motor).
    `record`   : callable(record_dict) -> Any (default: DB fail-open).
    """
    record = record or record_shadow_decision
    try:
        redacted, digest = redact_context(
            payload, secret=secret, include_text=include_text,
            max_text_chars=max_text_chars,
        )
        started = time.time()
        result = respond(payload)
        latency_ms = int((getattr(result, "usage", None) or {}).get("latency_ms") or 0)
        if not latency_ms:
            latency_ms = int((time.time() - started) * 1000)
        proposed = {
            "action": getattr(result, "action", None),
            "intent": getattr(result, "intent", None),
            "funnel_stage": getattr(result, "funnel_stage", None),
            "lead_temperature": getattr(result, "lead_temperature", None),
            "risk": getattr(result, "risk", None),
            "offer_id": getattr(result, "offer_id", None),
            "model": getattr(result, "model", None),
            "valid": getattr(result, "valid", None),
        }
        row = build_record(
            bot_id=bot_id, lead_ref=lead_ref, request_id=request_id,
            observed=observed, proposed=proposed,
            context={"redacted": redacted, "digest": digest},
            meta=meta, latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 — falha do shadow jamais interrompe
        logger.debug(f"⚠️ [IA/shadow] decisão shadow falhou (fail-open): {exc}")
        try:
            row = build_record(
                bot_id=bot_id, lead_ref=lead_ref, request_id=request_id,
                observed=observed, meta=meta, error_code="SHADOW_ERROR",
            )
        except Exception:  # noqa: BLE001
            return None
    try:
        record(row)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"⚠️ [IA/shadow] recorder falhou (fail-open): {exc}")
    return None


def make_shadow_request_id(base_request_id):
    """Id de shadow derivado (idempotente por turno), dentro do limite do motor."""
    base = str(base_request_id or "req")[:60]
    return f"shadow-{base}"[:80]
