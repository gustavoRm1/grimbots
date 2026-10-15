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
MAX_MESSAGE_CHARS = 1200
MAX_NEXT_QUESTION_CHARS = 300
MAX_CONVERSATION_SUMMARY_CHARS = 4000
MAX_OFFERS = 20
MAX_REQUEST_ID_LEN = 80

# Codes 5xx que vale a pena repetir
_RETRYABLE_CODES = {
    "RATE_LIMITED",       # 429
    "AI_BUSY",            # 503
    "AI_TIMEOUT",         # 504
    "AI_INVALID_RESPONSE",  # 502
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
        "request_id", "model", "message", "intent", "lead_temperature",
        "funnel_stage", "action", "next_question", "handoff_human", "risk",
        "validation", "usage",
    )

    def __init__(self, request_id="", model="", message="", intent="",
                 lead_temperature="warm", funnel_stage="qualification",
                 action="continue", next_question=None, handoff_human=False,
                 risk="low", validation=None, usage=None):
        self.request_id = request_id
        self.model = model
        self.message = message or ""
        self.intent = intent
        self.lead_temperature = lead_temperature
        self.funnel_stage = funnel_stage
        self.action = action if action in ACTIONS else "continue"
        self.next_question = next_question
        self.handoff_human = bool(handoff_human)
        self.risk = risk if risk in RISKS else "low"
        self.validation = validation if isinstance(validation, dict) else {"valid": True, "errors": []}
        self.usage = usage if isinstance(usage, dict) else {}

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
):
    """Monta o body exato do /v1/agent/respond (cada campo ja normalizado)."""
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
            "tone": _clamp_str(cfg.get("tone"), 40, "direto"),
            "boldness": _clamp_int(cfg.get("boldness"), 1, 5, 3),
            "message_length": _clamp_str(cfg.get("message_length"), 20, "short"),
            "emoji_level": _clamp_str(cfg.get("emoji_level"), 20, "moderate"),
            "commercial_goal": _clamp_str(cfg.get("commercial_goal"), 60, "qualificar"),
        },
        "conversation_state": {
            "funnel_stage": _clamp_enum(conversation_state, "funnel_stage", FUNNEL_STAGES, "new"),
            "lead_temperature": _clamp_enum(conversation_state, "lead_temperature", LEAD_TEMPERATURES, "warm"),
            "human_takeover": bool((conversation_state or {}).get("human_takeover", False)),
            "ai_enabled": bool((conversation_state or {}).get("ai_enabled", True)),
        },
        "lead": {
            "name": _clamp_str((lead or {}).get("name"), 80),
            "interest": _clamp_str((lead or {}).get("interest"), 200),
            "objection": _clamp_str((lead or {}).get("objection"), 200),
        },
        "recent_messages": _build_history(recent_messages),
        "conversation_summary": _clamp_str(conversation_summary, MAX_CONVERSATION_SUMMARY_CHARS),
        "available_offers": _build_offers(available_offers),
        "allowed_actions": _build_allowed_actions(allowed_actions),
    }
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
        items = [str(v).strip()[:40] for v in value if str(v).strip()]
        return items[:6]
    if isinstance(value, str) and value.strip():
        return [p.strip()[:40] for p in value.split(",") if p.strip()][:6]
    if value:
        return [_clamp_str(value, 40)]
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
        offer_id = _clamp_str(item.get("id"), 80)
        name = _clamp_str(item.get("name"), 120)
        price = _clamp_str(item.get("price"), 40)
        if not offer_id or not name or not price:
            continue
        offers.append({
            "id": offer_id,
            "name": name,
            "price": price,
            "checkout_url": _clamp_str(item.get("checkout_url"), 500),
            "active": bool(item.get("active", True)),
        })
    return offers


def _build_allowed_actions(allowed_actions):
    if not allowed_actions:
        return list(ACTIONS)
    picked = [a for a in allowed_actions if a in ACTIONS]
    return picked or list(ACTIONS)


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
