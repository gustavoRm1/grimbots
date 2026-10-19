"""
Grimbots AI API — cliente HTTP do Gateway (bloco 'ai' do Flow Editor).

ADITIVA: este módulo só é acionado quando um step tipo 'ai' roda no fluxo.
Motor tradicional/condições/pagamento não são afetados.

Contrato: POST /v1/agent/respond  (Grimbots AI API v1.0.0)
- Auth: header "X-API-Key: gp_..." (+ ngrok-skip-browser-warning)
- stateless, JSON estrito ("extra=forbid": NUNCA enviar model/system_prompt)
- shadow | suggestion | auto
"""

import json
import logging
import re
import time
import uuid

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# ── Enumeracoes do contrato ────────────────────────────────────────────────
ACTIONS = (
    "continue",
    "ask_question",
    "present_offer",
    "send_checkout",
    "handoff_human",
    "pause",
    "do_not_respond",
)
INTENTS = (
    "saudacao", "duvida", "interesse", "objecao",
    "compra", "suporte", "risco", "outro",
)
LEAD_TEMPERATURES = ("cold", "warm", "hot")
FUNNEL_STAGES = ("new", "connection", "qualification", "offer", "checkout", "customer", "human")
RISKS = ("low", "medium", "high")
MODES = ("shadow", "suggestion", "auto")
ROLES = ("user", "assistant", "system")

# Limites do servidor (doc v1.0.0)
MAX_PAYLOAD_BYTES = 65536
MAX_HISTORY_MESSAGES = 20
MAX_MESSAGE_CHARS = 4000  # D6: schema do motor (Message.content max_length=4000)
MAX_NEXT_QUESTION_CHARS = 300
MAX_CONVERSATION_SUMMARY_CHARS = 4000
MAX_OFFERS = 20
MAX_REQUEST_ID_LEN = 80

# ── D6 — limites do REQUEST = schema vigente do motor (autoritativos) ───────
# Fonte: api/schemas.py do Grimbots AI Gateway. Grimbots clampa EXATAMENTE no
# limite do motor (nunca acima); valores no limite passam inalterados. Itens
# marcados "<=" são propositalmente mais restritos (defensivos) e documentados.
MOTOR_REQUEST_LIMITS = {
    "request_id": 80, "seller_id": 80, "bot_id": 80,
    "conversation_id": 80, "bot_user_id": 80,
    "bot_config.name": 60,
    "bot_config.personality_items": 12,
    "bot_config.tone": 60,
    "bot_config.boldness": (1, 5),
    "bot_config.message_length": 20,
    "bot_config.emoji_level": 20,
    "bot_config.commercial_goal": 80,
    "lead.name": 60, "lead.interest": 120, "lead.objection": 120,
    "message.content": 4000,
    "conversation_summary": 4000,
    "available_offers": 20,
    "offer.id": 64, "offer.name": 120, "offer.price": 40, "offer.checkout_url": 400,
    "last_assistant_message": 2000,
    "questions_already_asked_items": 20, "questions_already_asked_item": 300,
    "offers_already_presented_items": 20, "offers_already_presented_item": 120,
    "collected_information_keys": 30,
    "collected_information_key": 60, "collected_information_value": 300,
    "turn_count": (0, 100),
    "contract_version": 10,
}

# Bot config — limites próprios (personality por item é "<=" o motor, que não
# impõe max_length por item; 40 é defesa de payload, não requisito do schema).
MAX_PERSONALITY_ITEMS = 12          # == motor max_length
MAX_PERSONALITY_ITEM_CHARS = 40     # <= motor (sem limite por item)

# ── E-P0 (D4/D14) — limites alinhados ao schema do motor --------------------
# Clamps defensivos: nunca enviamos valor acima do que o motor aceita (evita
# 422). Só APERTAM limites; para entradas válidas o payload v1.0 não muda.
MAX_LEAD_NAME_CHARS = 60
MAX_LEAD_INTEREST_CHARS = 120
MAX_LEAD_OBJECTION_CHARS = 120
MAX_OFFER_ID_CHARS = 64
MAX_OFFER_CHECKOUT_URL_CHARS = 400

# ── E-P1b (D6) — limites de memória = schema do motor (autoritativos) ───────
MAX_LAST_ASSISTANT_MESSAGE_CHARS = 2000
MAX_MEMORY_LIST_ITEMS = 20
MAX_QUESTION_ITEM_CHARS = 300
MAX_OFFER_ITEM_CHARS = 120
MAX_COLLECTED_KEYS = 30
MAX_COLLECTED_KEY_CHARS = 60
MAX_COLLECTED_VALUE_CHARS = 300
MAX_TURN_COUNT = 100

# Campos de memória operacional (contrato v1.1, request). Todos opcionais.
MEMORY_FIELDS = (
    "last_assistant_message", "collected_information", "questions_already_asked",
    "offers_already_presented", "turn_count", "last_action",
)

# ── E-P2 (D12) — mapa explícito de intent (valor original -> oficial) ───────
# O motor só devolve os 8 valores oficiais (qualquer outro é fatal lá). Este
# mapa é uma defesa do cliente caso um alias apareça, sempre auditável.
INTENT_ALIASES = {
    "oferta": "interesse",
    "informacao": "duvida",
}

# ── Fase 6A (contrato v1.1) — limites próprios, todos OFFLINE por padrão ────
MAX_PROFILE_LISTS = 8
MAX_PROFILE_ITEM_CHARS = 120
MAX_PROFILE_DESCRIPTION_CHARS = 600
MAX_RESOURCES = 20
MAX_TAGS = 8
MAX_TAG_CHARS = 24

# Marcadores de tentativa de alterar regras do sistema via persona (Fase 6A §3).
# O perfil é contexto de persona, NÃO um canal para mudar o comportamento do agente.
_PROFILE_INJECTION_MARKERS = (
    "ignore todas as regras", "ignorar todas as regras", "ignore as regras",
    "desconsidere as regras", "esqueca as regras", "ignore suas regras",
    "ignore previous", "ignore all previous", "system prompt", "prompt do sistema",
    "confirme pagamentos", "confirme o pagamento", "confirma pagamento",
    "invente midias", "invente midia", "crie midias", "crie arquivos",
    "voce agora e", "a partir de agora voce",
)
_PROFILE_INJECTION_RE = re.compile(
    "|".join(re.escape(m) for m in _PROFILE_INJECTION_MARKERS), re.IGNORECASE
)

# Codes 5xx que vale a pena repetir
_RETRYABLE_CODES = {
    "RATE_LIMITED",       # 429
    "AI_BUSY",            # 503
    "AI_TIMEOUT",         # 504
    "AI_INVALID_RESPONSE",  # 502
    "REQUEST_IN_PROGRESS",  # 409 (D11: entrega concorrente do mesmo request_id)
}
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (2, 4, 8)
_MAX_RETRY_AFTER = 30.0


class AIGatewayError(Exception):
    """Erro do Gateway (ou da configuracao local). Sempre segura de tratar."""

    def __init__(self, code, message="", status=None, retryable=False):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message or code
        self.status = status
        self.retryable = retryable


class AIResult:
    """Resposta 200 do /v1/agent/respond, ja normalizada."""

    __slots__ = (
        "request_id", "model", "message", "intent", "intent_original", "intent_kind",
        "lead_temperature", "funnel_stage", "action", "next_question",
        "handoff_human", "risk", "validation", "usage", "reason", "offer_id",
        "state_update",
    )

    def __init__(self, request_id="", model="", message="", intent="",
                 lead_temperature="warm", funnel_stage="qualification",
                 action="continue", next_question=None, handoff_human=False,
                 risk="low", validation=None, usage=None, reason=None,
                 offer_id=None, state_update=None):
        self.request_id = request_id
        self.model = model
        self.message = message or ""
        # D12 — normaliza o intent (aliases) e mantém o valor original auditável
        self.intent, self.intent_original, self.intent_kind = normalize_intent(intent)
        self.lead_temperature = lead_temperature
        self.funnel_stage = funnel_stage
        self.action = action if action in ACTIONS else "continue"
        self.next_question = next_question
        self.handoff_human = bool(handoff_human)
        self.risk = risk if risk in RISKS else "low"
        self.validation = validation if isinstance(validation, dict) else {"valid": True, "errors": []}
        self.usage = usage if isinstance(usage, dict) else {}
        self.reason = reason if isinstance(reason, str) else None
        self.offer_id = offer_id if offer_id else None
        self.state_update = state_update if isinstance(state_update, dict) else None

    @property
    def valid(self):
        return bool(self.validation.get("valid", True))

    @property
    def errors(self):
        return list(self.validation.get("errors") or [])

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise AIGatewayError("AI_INVALID_RESPONSE", "resposta nao e um objeto JSON")
        try:
            return cls(
                request_id=str(data.get("request_id") or ""),
                model=str(data.get("model") or ""),
                message=str(data.get("message") or ""),
                intent=str(data.get("intent") or "outro"),
                lead_temperature=str(data.get("lead_temperature") or "warm"),
                funnel_stage=str(data.get("funnel_stage") or "qualification"),
                action=str(data.get("action") or "continue"),
                next_question=data.get("next_question"),
                handoff_human=bool(data.get("handoff_human", False)),
                risk=str(data.get("risk") or "low"),
                validation=data.get("validation") or {"valid": True, "errors": []},
                usage=data.get("usage") or {},
                reason=data.get("reason"),
                offer_id=data.get("offer_id"),
                state_update=data.get("state_update"),
            )
        except (TypeError, ValueError) as exc:
            raise AIGatewayError("AI_INVALID_RESPONSE", f"campos invalidos: {exc}")

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


# ── Construcao de payload (estrito, extra=forbid) ──────────────────────────
def _clamp_str(value, limit, default=""):
    if value is None:
        return default
    text = str(value).strip()
    return text[:limit] if text else default


def _id(value, fallback):
    return _clamp_str(value, MAX_REQUEST_ID_LEN, fallback)


def build_payload(
    request_id,
    seller_id,
    bot_id,
    conversation_id,
    bot_user_id,
    bot_config=None,
    conversation_state=None,
    lead=None,
    recent_messages=None,
    conversation_summary=None,
    available_offers=None,
    allowed_actions=None,
    mode="shadow",
    contract_version=None,
    agent_profile=None,
    flow_resources=None,
    context_policy=None,
    last_assistant_message=None,
    collected_information=None,
    questions_already_asked=None,
    offers_already_presented=None,
    turn_count=None,
    last_action=None,
):
    """Monta o body exato do /v1/agent/respond (cada campo ja normalizado).

    E-P1b (aditivo/opt-in): os campos de memória (`last_assistant_message`,
    `collected_information`, `questions_already_asked`, `offers_already_presented`,
    `turn_count`, `last_action`) entram no payload SOMENTE quando não-None.
    Com todos None (default) o body é idêntico ao v1.0 byte-a-byte.

    Contexto v1.1 (aditivo/opt-in): `contract_version`/`agent_profile`/
    `flow_resources`/`context_policy` também só entram quando fornecidos.
    """
    if mode not in MODES:
        mode = "shadow"

    cfg = dict(bot_config or {})
    name = _clamp_str(cfg.get("name"), 60, "Assistente")
    payload = {
        "request_id": _id(request_id, f"req-{uuid.uuid4().hex[:24]}"),
        "seller_id": _id(seller_id, "seller"),
        "bot_id": _id(bot_id, "bot"),
        "conversation_id": _id(conversation_id, "conv"),
        "bot_user_id": _id(bot_user_id, "lead"),
        "mode": mode,
        "bot_config": {
            "name": name,
            "personality": _clamp_personality(cfg.get("personality")),
            "tone": _clamp_str(cfg.get("tone"), 60, "direto"),
            "boldness": _clamp_int(cfg.get("boldness"), 1, 5, 3),
            "message_length": _clamp_str(cfg.get("message_length"), 20, "short"),
            "emoji_level": _clamp_str(cfg.get("emoji_level"), 20, "moderate"),
            "commercial_goal": _clamp_str(cfg.get("commercial_goal"), 80, "qualificar"),
        },
        "conversation_state": {
            "funnel_stage": _clamp_enum(conversation_state, "funnel_stage", FUNNEL_STAGES, "new"),
            "lead_temperature": _clamp_enum(conversation_state, "lead_temperature", LEAD_TEMPERATURES, "warm"),
            "human_takeover": bool((conversation_state or {}).get("human_takeover", False)),
            "ai_enabled": bool((conversation_state or {}).get("ai_enabled", True)),
        },
        "lead": {
            "name": _clamp_str((lead or {}).get("name"), MAX_LEAD_NAME_CHARS),
            "interest": _clamp_str((lead or {}).get("interest"), MAX_LEAD_INTEREST_CHARS),
            "objection": _clamp_str((lead or {}).get("objection"), MAX_LEAD_OBJECTION_CHARS),
        },
        "recent_messages": _build_history(recent_messages),
        "conversation_summary": _clamp_str(conversation_summary, MAX_CONVERSATION_SUMMARY_CHARS),
        "available_offers": _build_offers(available_offers),
        "allowed_actions": _build_allowed_actions(allowed_actions),
    }

    # ── Fase 6A (v1.1) — chaves SÓ presentes quando fornecidas (default = v1.0) ──
    if contract_version:
        payload["contract_version"] = _clamp_str(contract_version, 10, "1.0")
    profile = _clamp_profile(agent_profile)
    if profile:
        payload["agent_profile"] = profile
    if flow_resources is not None:
        payload["flow_resources"] = _build_flow_resources(flow_resources)
    policy = _clamp_context_policy(context_policy)
    if policy:
        payload["context_policy"] = policy

    # ── E-P1b — memória operacional (só presente quando fornecida) ──────────
    if last_assistant_message is not None:
        payload["last_assistant_message"] = _clamp_str(
            last_assistant_message, MAX_LAST_ASSISTANT_MESSAGE_CHARS
        )
    if collected_information is not None:
        payload["collected_information"] = _clamp_collected_information(collected_information)
    if questions_already_asked is not None:
        payload["questions_already_asked"] = _clamp_memory_list(
            questions_already_asked, MAX_QUESTION_ITEM_CHARS
        )
    if offers_already_presented is not None:
        payload["offers_already_presented"] = _clamp_memory_list(
            offers_already_presented, MAX_OFFER_ITEM_CHARS
        )
    if turn_count is not None:
        payload["turn_count"] = _clamp_int(turn_count, 0, MAX_TURN_COUNT, 0)
    if last_action is not None:
        payload["last_action"] = last_action if last_action in ACTIONS else None
    return payload


def _clamp_int(value, low, high, default):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_enum(source, key, options, default):
    if isinstance(source, dict):
        value = str(source.get(key) or "").strip().lower()
        if value in options:
            return value
    return default


def _clamp_personality(value):
    if isinstance(value, (list, tuple)):
        items = [str(v).strip()[:MAX_PERSONALITY_ITEM_CHARS] for v in value if str(v).strip()]
        return items[:MAX_PERSONALITY_ITEMS]
    if isinstance(value, str) and value.strip():
        return [p.strip()[:MAX_PERSONALITY_ITEM_CHARS]
                for p in value.split(",") if p.strip()][:MAX_PERSONALITY_ITEMS]
    if value:
        return [_clamp_str(value, MAX_PERSONALITY_ITEM_CHARS)]
    return []


def _build_history(recent_messages):
    history = []
    for item in (recent_messages or [])[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        content = _clamp_str(item.get("content"), MAX_MESSAGE_CHARS)
        if role not in ROLES or not content:
            continue
        history.append({"role": role, "content": content})
    if not history:
        raise AIGatewayError("VALIDATION_ERROR", "recent_messages precisa de ao menos 1 item")
    return history


def _build_offers(available_offers):
    offers = []
    for item in (available_offers or [])[:MAX_OFFERS]:
        if not isinstance(item, dict):
            continue
        offer_id = _clamp_str(item.get("id"), MAX_OFFER_ID_CHARS)
        name = _clamp_str(item.get("name"), 120)
        price = _clamp_str(item.get("price"), 40)
        if not offer_id or not name or not price:
            continue
        offers.append({
            "id": offer_id,
            "name": name,
            "price": price,
            "checkout_url": _clamp_str(item.get("checkout_url"), MAX_OFFER_CHECKOUT_URL_CHARS),
            "active": bool(item.get("active", True)),
        })
    return offers


def _build_allowed_actions(allowed_actions):
    if not allowed_actions:
        return list(ACTIONS)
    picked = [a for a in allowed_actions if a in ACTIONS]
    return picked or list(ACTIONS)


# ── Fase 6A (v1.1) — helpers de normalizacao (offline; nao afetam v1.0) ─────
def _sanitize_profile_text(value, limit):
    """Texto de persona: trunca, remove tentativas de alterar regras, colapsa espacos."""
    text = _clamp_str(value, limit)
    if not text:
        return ""
    text = _PROFILE_INJECTION_RE.sub(" ", text)
    return " ".join(text.split())


def _clamp_str_list(value, max_items, item_chars):
    """Normaliza lista de strings (aceita lista/tuple ou string separada por virgula)."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        text = _sanitize_profile_text(item, item_chars)
        if text:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _clamp_profile(profile):
    """Valida agent_profile (§3). Retorna None (omite o perfil inteiro) se invalido.

    Regras: age obrigatorio 18..99; adult_only deve ser True. Sem isso, o perfil
    NAO e enviado — nunca em versao parcial/ambigua.
    """
    if not isinstance(profile, dict):
        return None
    try:
        age = int(profile.get("age"))
    except (TypeError, ValueError):
        return None
    if not (18 <= age <= 99):
        return None
    if profile.get("adult_only", True) is not True:
        return None
    return {
        "age": age,
        "adult_only": True,
        "origin": _sanitize_profile_text(profile.get("origin"), 60),
        "current_location": _sanitize_profile_text(profile.get("current_location"), 60),
        "niche": _sanitize_profile_text(profile.get("niche"), 40),
        "subniche": _sanitize_profile_text(profile.get("subniche"), 40),
        "speaking_style": _sanitize_profile_text(profile.get("speaking_style"), 120),
        "persona_description": _sanitize_profile_text(
            profile.get("persona_description"), MAX_PROFILE_DESCRIPTION_CHARS
        ),
        "likes": _clamp_str_list(profile.get("likes"), MAX_PROFILE_LISTS, 40),
        "dislikes": _clamp_str_list(profile.get("dislikes"), MAX_PROFILE_LISTS, 40),
        "boundaries": _clamp_str_list(
            profile.get("boundaries"), MAX_PROFILE_LISTS, MAX_PROFILE_ITEM_CHARS
        ),
    }


def _build_flow_resources(resources):
    """Projecao read-only dos recursos do fluxo (§4/§8). NUNCA inclui urls/file_ids."""
    out = []
    for item in (resources or [])[:MAX_RESOURCES]:
        if not isinstance(item, dict):
            continue
        resource_id = _clamp_str(item.get("resource_id"), 80)
        resource_type = _clamp_str(item.get("resource_type"), 30)
        if not resource_id or not resource_type:
            continue
        price = item.get("price_cents")
        try:
            price = int(price) if price is not None else None
        except (TypeError, ValueError):
            price = None
        out.append({
            "resource_id": resource_id,
            "resource_type": resource_type,
            "media_type": _clamp_str(item.get("media_type"), 20) or None,
            "label": _clamp_str(item.get("label"), 120),
            "description": _clamp_str(item.get("description"), 200),
            "tags": _clamp_str_list(item.get("tags"), MAX_TAGS, MAX_TAG_CHARS),
            "active": bool(item.get("active", True)),
            "has_media": bool(item.get("has_media", False)),
            "available": bool(item.get("available", False)),
            "requires_payment": bool(item.get("requires_payment", False)),
            "price_cents": price,
        })
    return out


def _clamp_context_policy(policy):
    if not isinstance(policy, dict):
        return None
    return {
        "include_current_node": bool(policy.get("include_current_node", True)),
        "include_reachable": bool(policy.get("include_reachable", True)),
        "include_global": bool(policy.get("include_global", False)),
        "max_resources": _clamp_int(policy.get("max_resources"), 1, MAX_RESOURCES, MAX_RESOURCES),
    }


def _clamp_collected_information(info):
    """Dict de escalares (≤30 chaves / key ≤60 / value ≤300). Descartar aninhado.

    Valores aninhados são descartados no cliente para nunca gerar 422 no motor.
    """
    if not isinstance(info, dict):
        return {}
    clean = {}
    for key, value in info.items():
        k = _clamp_str(key, MAX_COLLECTED_KEY_CHARS)
        if not k:
            continue
        if isinstance(value, str):
            v = value[:MAX_COLLECTED_VALUE_CHARS]
        elif value is None or isinstance(value, (bool, int, float)):
            v = value
        else:
            continue  # aninhado/lista -> descartado
        clean[k] = v
        if len(clean) >= MAX_COLLECTED_KEYS:
            break
    return clean


def _clamp_memory_list(items, item_limit):
    """Lista de strings com limite de itens e de caracteres por item."""
    out = []
    for item in (items or [])[:MAX_MEMORY_LIST_ITEMS]:
        if isinstance(item, str):
            text = item[:item_limit]
            if text:
                out.append(text)
    return out


def normalize_intent(raw):
    """D12 — (normalizado, original, kind). kind: None | 'alias' | 'invalid'."""
    value = str(raw or "").strip().lower()
    if value in INTENTS:
        return value, None, None
    if value in INTENT_ALIASES:
        return INTENT_ALIASES[value], value, "alias"
    return "outro", value, "invalid"


# D5 — whitelist APLICÁVEL pela plataforma em `state_update`.
# `last_action` foi RETIRADO (é interno da plataforma) e `conversation_summary`
# fica FORA (D10: resumo é responsabilidade da plataforma).
STATE_UPDATE_WHITELIST = (
    "collected_information",
    "questions_already_asked",
    "offers_already_presented",
    "funnel_stage",
    "lead_temperature",
    "objection",
    "interest",
)


def apply_state_update(state, state_update, errors=None):
    """Aplica o delta sugerido pelo motor (D5/D10/D12). Nunca é fatal.

    Retorna a lista de chaves aplicadas. Chaves fora da whitelist ou com valor
    inválido são IGNORADAS e registradas em `errors`. Nunca altera
    `conversation_summary` nem `last_action`.
    """
    applied = []
    if state_update is None:
        return applied
    if not isinstance(state_update, dict):
        if errors is not None:
            errors.append("state_update ignorado: tipo invalido.")
        return applied

    for key, value in state_update.items():
        if key not in STATE_UPDATE_WHITELIST:
            if errors is not None:
                errors.append(f"state_update.{key} ignorado: chave fora da whitelist.")
            continue

        if key == "collected_information":
            if not isinstance(value, dict):
                if errors is not None:
                    errors.append("state_update.collected_information ignorado: tipo invalido.")
                continue
            merged = dict(state.get("collected_information") or {})
            merged.update(_clamp_collected_information(value))
            state["collected_information"] = _clamp_collected_information(merged)
            applied.append(key)
        elif key in ("questions_already_asked", "offers_already_presented"):
            if not isinstance(value, list):
                if errors is not None:
                    errors.append(f"state_update.{key} ignorado: tipo invalido.")
                continue
            limit = MAX_QUESTION_ITEM_CHARS if key == "questions_already_asked" else MAX_OFFER_ITEM_CHARS
            merged = list(state.get(key) or []) + [str(v) for v in value if isinstance(v, str)]
            state[key] = _clamp_memory_list(merged, limit)
            applied.append(key)
        elif key == "funnel_stage":
            if value in FUNNEL_STAGES:
                state["funnel_stage"] = value
                applied.append(key)
            elif errors is not None:
                errors.append("state_update.funnel_stage ignorado: valor invalido.")
        elif key == "lead_temperature":
            if value in LEAD_TEMPERATURES:
                state["lead_temperature"] = value
                applied.append(key)
            elif errors is not None:
                errors.append("state_update.lead_temperature ignorado: valor invalido.")
        elif key in ("objection", "interest"):
            if isinstance(value, str):
                state[key] = value[:MAX_LEAD_OBJECTION_CHARS]
                applied.append(key)
            elif errors is not None:
                errors.append(f"state_update.{key} ignorado: tipo invalido.")
    return applied


def payload_size(payload):
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


# ── Transporte ─────────────────────────────────────────────────────────────
class GrimbotsAIService:
    """Cliente real do Gateway. Retentativas conforme a tabela do contrato."""

    def __init__(self, api_url, api_key, timeout=90.0):
        self.api_url = (api_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = float(timeout or 90)
        self.endpoint = f"{self.api_url}/v1/agent/respond"

    @property
    def configured(self):
        return bool(self.api_url and self.api_key)

    def respond(self, payload):
        if not self.configured:
            raise AIGatewayError(
                "API_KEY_NOT_CONFIGURED",
                "GRIMBOTS_AI_API_URL/GRIMBOTS_AI_API_KEY ausentes no .env",
                status=503,
            )

        size = payload_size(payload)
        if size > MAX_PAYLOAD_BYTES:
            raise AIGatewayError(
                "PAYLOAD_TOO_LARGE",
                f"payload {size}B > {MAX_PAYLOAD_BYTES}B",
                status=413,
            )

        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
            "Accept": "application/json",
        }

        attempt = 0
        last_code, last_message, last_status = "AI_BACKEND_ERROR", "sem resposta", 502
        while attempt < _MAX_ATTEMPTS:
            attempt += 1
            try:
                response = requests.post(
                    self.endpoint, json=payload, headers=headers, timeout=self.timeout
                )
            except requests.Timeout as exc:
                last_code, last_message, last_status = "AI_TIMEOUT", str(exc), 504
                if attempt < _MAX_ATTEMPTS:
                    self._sleep(attempt, None)
                    continue
                raise AIGatewayError(last_code, last_message, status=last_status, retryable=True)
            except requests.RequestException as exc:
                raise AIGatewayError(
                    "AI_BACKEND_UNAVAILABLE", str(exc), status=502, retryable=False
                )

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    last_code, last_message, last_status = "AI_INVALID_RESPONSE", "JSON invalido", 502
                    if attempt < _MAX_ATTEMPTS:
                        self._sleep(attempt, None)
                        continue
                    raise AIGatewayError(last_code, last_message, status=last_status, retryable=True)
                return AIResult.from_dict(data)

            code, message = self._parse_error(response)
            last_code, last_message, last_status = code, message, response.status_code
            if code not in _RETRYABLE_CODES or attempt >= _MAX_ATTEMPTS:
                raise AIGatewayError(code, message, status=response.status_code, retryable=code in _RETRYABLE_CODES)
            self._sleep(attempt, response.headers.get("Retry-After"))

        raise AIGatewayError(last_code, last_message, status=last_status, retryable=True)

    @staticmethod
    def _parse_error(response):
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            err = body.get("error") if isinstance(body.get("error"), dict) else body
            code = str(err.get("code") or "") if isinstance(err, dict) else ""
            message = str(err.get("message") or "") if isinstance(err, dict) else json.dumps(err)
            if code:
                return code, message
        return f"HTTP_{response.status_code}", (response.text or "")[:300]

    @staticmethod
    def _sleep(attempt, retry_after):
        if retry_after:
            try:
                seconds = min(float(retry_after), _MAX_RETRY_AFTER)
                if seconds > 0:
                    time.sleep(seconds)
                    return
            except (TypeError, ValueError):
                pass
        seconds = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
        time.sleep(seconds)


class MockAIService:
    """Simulacao local (GRIMBOTS_AI_MOCK=true). Nenhuma chamada externa."""

    def __init__(self):
        self.api_url = "mock://grimbots-ai"
        self.api_key = "mock"
        self.timeout = 0
        self.endpoint = "mock://grimbots-ai/v1/agent/respond"

    @property
    def configured(self):
        return True

    def respond(self, payload):
        history = payload.get("recent_messages") or []
        last = history[-1].get("content", "").lower() if history else ""
        allowed = payload.get("allowed_actions") or list(ACTIONS)

        if any(k in last for k in ("obrigad", "tchau", "valeu")):
            action, question, risk = "continue", None, "low"
            message = "Por nada! Qualquer coisa estou por aqui."
        elif any(k in last for k in ("cara", "bosta", "roub", "reclam")):
            action, question, risk = "handoff_human", None, "high"
            message = "Vou chamar uma pessoa da equipe para te ajudar."
        elif any(k in last for k in ("preco", "preço", "valor", "quanto", "caro", "barato")):
            action, question, risk = "present_offer", None, "low"
            message = "Temos o plano perfeito pra voce. Posso te mandar o checkout?"
        elif any(k in last for k in ("comprar", "quero", "pagar", "checkout", "link")):
            action, question, risk = "send_checkout", None, "low"
            message = "Fechado! Segue o checkout seguro:"
        elif "?" in last or any(k in last for k in ("como", "o que", "quem", "onde", "quando")):
            action, question, risk = "ask_question", "Me conta um pouco mais sobre o que voce precisa?", "low"
            message = "Boa pergunta! Antes de responder, me diz:"
        else:
            action, question, risk = "continue", None, "low"
            message = "Entendi! Me conta mais sobre o que voce procura?"

        if action not in allowed:
            action = "continue" if "continue" in allowed else allowed[0]
        return AIResult(
            request_id=payload.get("request_id", ""),
            model="grimbots-sales:latest-mock",
            message=message,
            intent="interesse",
            lead_temperature="warm",
            funnel_stage=payload.get("conversation_state", {}).get("funnel_stage", "qualification"),
            action=action,
            next_question=question,
            handoff_human=(action == "handoff_human"),
            risk=risk,
            validation={"valid": True, "errors": []},
            usage={"latency_ms": 0, "input_tokens": 0, "output_tokens": 0},
        )


def get_ai_service():
    """Factory: mock se GRIMBOTS_AI_MOCK, senao cliente real."""
    api_url = current_app.config.get("GRIMBOTS_AI_API_URL", "")
    api_key = current_app.config.get("GRIMBOTS_AI_API_KEY", "")
    timeout = current_app.config.get("GRIMBOTS_AI_TIMEOUT", 90)
    if current_app.config.get("GRIMBOTS_AI_MOCK"):
        return MockAIService()
    return GrimbotsAIService(api_url, api_key, timeout)
