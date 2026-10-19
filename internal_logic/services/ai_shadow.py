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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Política de retenção default (dias). <= 0 desliga o expurgo.
DEFAULT_RETENTION_DAYS = 90
# Limites operacionais default (podem ser reconfigurados por env/limiter).
DEFAULT_MAX_INFLIGHT = 8
DEFAULT_MAX_PER_MINUTE = 120
DEFAULT_MAX_PER_DAY = 5000
# TTL do cache de versão do motor (s).
DEFAULT_VERSION_TTL = 300.0

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
    "contract_version", "motor_version", "motor_version_source",
    "motor_commit", "motor_model",
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
        "motor_version_source": str(meta.get("motor_version_source") or "unknown"),
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
# 2A — Retenção e expurgo seguro
# ────────────────────────────────────────────────────────────────────────────
def retention_cutoff(retention_days, now=None):
    """Data-limite (UTC) para expurgo; None quando a retenção está desligada."""
    if retention_days is None:
        retention_days = DEFAULT_RETENTION_DAYS
    try:
        days = int(retention_days)
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    if days <= 0:
        return None
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base - timedelta(days=days)


def filter_expired(rows, cutoff):
    """Ids de `rows` (id, created_at) anteriores ao cutoff (UTC). Puro/testável."""
    if cutoff is None:
        return []
    expired = []
    for row in rows or []:
        rid, created = (row if isinstance(row, (tuple, list)) else (row.get("id"), row.get("created_at")))
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            expired.append(rid)
    return expired


def _db_fetch_expired(cutoff, limit):
    from internal_logic.core.models import AIShadowDecision
    q = AIShadowDecision.query.filter(AIShadowDecision.created_at < cutoff)
    q = q.order_by(AIShadowDecision.created_at.asc())
    if limit:
        q = q.limit(limit)
    return [(r.id, r.created_at) for r in q.all()]


def _db_delete_ids(ids):
    from internal_logic.core.extensions import db
    from internal_logic.core.models import AIShadowDecision
    AIShadowDecision.query.filter(AIShadowDecision.id.in_(list(ids))).delete(
        synchronize_session=False
    )
    db.session.commit()


def purge_expired(*, retention_days=None, now=None, batch_size=None,
                  fetch=None, delete=None):
    """Expurgo idempotente por lote. Fail-open: nunca propaga; retorna contagem.

    `fetch(cutoff, limit)` -> [(id, created_at), ...]  (injável em testes)
    `delete(ids)`         -> None                      (injável em testes)
    """
    cutoff = retention_cutoff(retention_days, now)
    if cutoff is None:
        return {"enabled": False, "deleted": 0, "cutoff": None}
    fetch = fetch or _db_fetch_expired
    delete = delete or _db_delete_ids
    total = 0
    try:
        while True:
            rows = fetch(cutoff, batch_size)
            if not rows:
                break
            ids = [rid for rid, _ in rows]
            delete(ids)
            total += len(ids)
            if not batch_size or len(rows) < batch_size:
                break
    except Exception as exc:  # noqa: BLE001 — fail-open
        logger.debug(f"⚠️ [IA/shadow] expurgo interrompido (fail-open): {exc}")
    return {"enabled": True, "deleted": total, "cutoff": cutoff.isoformat()}


# ────────────────────────────────────────────────────────────────────────────
# 2B — Limites operacionais (in-flight + taxa + orçamento diário)
# ────────────────────────────────────────────────────────────────────────────
class ShadowLimiter:
    """Admissão concorrente-segura. Ao atingir limite, a admissão é NEGADA
    (shadow ignorado) — nunca bloqueia o turno real."""

    def __init__(self, max_inflight=DEFAULT_MAX_INFLIGHT, max_per_minute=DEFAULT_MAX_PER_MINUTE,
                 max_per_day=DEFAULT_MAX_PER_DAY, now_fn=None):
        self.max_inflight = max(1, int(max_inflight))
        self.max_per_minute = int(max_per_minute)
        self.max_per_day = int(max_per_day)
        self._now = now_fn or (lambda: time.monotonic())
        self._wall = now_fn or (lambda: time.time())
        self._lock = threading.Lock()
        self._inflight = 0
        self._minute_events = []
        self._day_key = None
        self._day_count = 0

    def admit(self):
        """True se admitido (reserva in-flight). Chamar `release()` ao terminar."""
        with self._lock:
            # Orçamento diário
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if day != self._day_key:
                self._day_key, self._day_count = day, 0
            if self.max_per_day and self._day_count >= self.max_per_day:
                return False
            # Taxa por minuto (janela deslizante)
            if self.max_per_minute:
                now = self._now()
                self._minute_events = [t for t in self._minute_events if now - t < 60.0]
                if len(self._minute_events) >= self.max_per_minute:
                    return False
            # In-flight
            if self._inflight >= self.max_inflight:
                return False
            self._inflight += 1
            self._day_count += 1
            if self.max_per_minute:
                self._minute_events.append(self._now())
            return True

    def release(self):
        with self._lock:
            if self._inflight > 0:
                self._inflight -= 1

    def snapshot(self):
        with self._lock:
            return {
                "inflight": self._inflight,
                "day_count": self._day_count,
                "day_key": self._day_key,
                "minute_events": len(self._minute_events),
                "max_inflight": self.max_inflight,
                "max_per_minute": self.max_per_minute,
                "max_per_day": self.max_per_day,
            }


_LIMITER = None
_LIMITER_LOCK = threading.Lock()


def configure_limiter(max_inflight=None, max_per_minute=None, max_per_day=None,
                      now_fn=None):
    """(Re)configura o limiter global. Usado no boot e em testes."""
    global _LIMITER
    mi = max_inflight if max_inflight is not None else \
        os.environ.get("GRIMBOTS_AI_SHADOW_MAX_INFLIGHT", DEFAULT_MAX_INFLIGHT)
    mp = max_per_minute if max_per_minute is not None else \
        os.environ.get("GRIMBOTS_AI_SHADOW_MAX_PER_MINUTE", DEFAULT_MAX_PER_MINUTE)
    md = max_per_day if max_per_day is not None else \
        os.environ.get("GRIMBOTS_AI_SHADOW_MAX_PER_DAY", DEFAULT_MAX_PER_DAY)
    lim = ShadowLimiter(mi, mp, md, now_fn=now_fn)
    with _LIMITER_LOCK:
        _LIMITER = lim
    return lim


def get_limiter():
    if _LIMITER is not None:
        return _LIMITER
    return configure_limiter()


# ────────────────────────────────────────────────────────────────────────────
# 2D — Rastreabilidade da versão do motor (/health, com fallback explícito)
# ────────────────────────────────────────────────────────────────────────────
_VERSION_CACHE = {"value": None, "source": "unknown", "at": 0.0}
_VERSION_LOCK = threading.Lock()


def reset_version_cache():
    with _VERSION_LOCK:
        _VERSION_CACHE.update({"value": None, "source": "unknown", "at": 0.0})


def resolve_motor_version(health_fetcher=None, fallback="", ttl=DEFAULT_VERSION_TTL,
                          now_fn=None):
    """Retorna (version, source). `source` ∈ health|env|unknown.

    Consulta `/health` (fonte verificável) com cache; se indisponível usa o
    fallback informado (env) — **nunca inventa** uma versão. Dentro do TTL não
    faz nova chamada (inclusive para cache negativo).
    """
    now = (now_fn or time.time)()
    with _VERSION_LOCK:
        cached = dict(_VERSION_CACHE)
    if cached["at"] and (now - cached["at"]) < ttl:
        return _from_cache(cached, fallback)

    version, source = None, "unknown"
    if health_fetcher is not None:
        try:
            body = health_fetcher() or {}
            v = str(body.get("version") or "").strip()
            if v:
                version, source = v, "health"
        except Exception as exc:  # noqa: BLE001 — cacheia a indisponibilidade
            logger.debug(f"ℹ️ [IA/shadow] /health indisponível: {exc}")
    if version is None and fallback:
        version, source = str(fallback).strip(), "env"
    with _VERSION_LOCK:
        _VERSION_CACHE.update({"value": version, "source": source, "at": now})
    return _from_cache({"value": version, "source": source}, fallback)


def _from_cache(cached, fallback):
    if cached.get("value"):
        return cached["value"], (cached.get("source") or "unknown")
    return (str(fallback).strip() if fallback else ""), ("env" if fallback else "unknown")


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
