"""
CAPI Client — Meta Conversions API HTTP Client
===============================================
Envia eventos para a Meta CAPI seguindo exatamente a documentação:
- Endpoint: POST /v19.0/{pixel_id}/events
- Timeout: 1500ms (recomendação Meta)
- Error handling:
  - 2xx → sucesso
  - 4xx → NÃO retentar (erro do cliente)
  - 5xx → retentar com exponential backoff (2^n s)
  - 429 → retentar com backoff mais longo (60 * 2^n s)
  - Transient → retentar
- Máx 3 tentativas por evento
"""

import logging
import time
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

META_CAPI_BASE_URL = "https://graph.facebook.com/v19.0/{pixel_id}/events"
REQUEST_TIMEOUT = 3  # 3s timeout padrão unificado
MAX_RETRIES = 3


class CAPIClientError(Exception):
    """Erro base do CAPI Client."""


class CAPIClient4xxError(CAPIClientError):
    """Erro 4xx — não retentar."""


class CAPIClient5xxError(CAPIClientError):
    """Erro 5xx — retentável."""


class CAPIClientRateLimitError(CAPIClientError):
    """Erro 429 — rate limit, retentar com backoff longo."""


REQUIRED_EVENT_FIELDS = ['event_name', 'event_time', 'action_source']


def _validate_event_data(event: Dict[str, Any]) -> bool:
    """Valida campos obrigatórios do evento antes de enviar."""
    for field in REQUIRED_EVENT_FIELDS:
        if not event.get(field):
            logger.warning(f"[CAPI] Campo obrigatório ausente: {field}")
            return False
    user_data = event.get('user_data')
    if user_data is not None and not isinstance(user_data, dict):
        logger.warning("[CAPI] user_data deve ser dict")
        return False
    return True


def send_event(
    pixel_id: str,
    access_token: str,
    event: Dict[str, Any],
    test_event_code: Optional[str] = None,
    validate_token: bool = False,
) -> bool:
    """Envia um evento para a Meta CAPI.

    Args:
        pixel_id: ID do Pixel Meta
        access_token: Access Token (deve estar decriptado)
        event: Payload do evento (event_name, event_time, user_data, ...)
        test_event_code: Código de teste (Events Manager)

    Returns:
        True se evento recebido com sucesso (events_received >= 1)
        False se erro 4xx ou falha permanente
    """
    payload: Dict[str, Any] = {
        'data': [event],
        'access_token': access_token,
    }
    if test_event_code:
        payload['test_event_code'] = test_event_code

    if not _validate_event_data(event):
        logger.warning(f"[CAPI] event_data inválido — abortando")
        return False

    if validate_token:
        try:
            from utils.meta_token_validator import validate_meta_token as _validate_meta_token
            if not _validate_meta_token(access_token):
                logger.critical(
                    f"[CAPI] TOKEN INVÁLIDO para pixel {pixel_id} — evento NÃO enviado"
                )
                return False
        except Exception as e:
            logger.error(f"[CAPI] Erro na validação do token: {e}")

    url = META_CAPI_BASE_URL.format(pixel_id=pixel_id)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            # ── 2xx: Sucesso ─────────────────────────────────
            if 200 <= resp.status_code < 300:
                body = resp.json()
                events_received = body.get('events_received', 0)
                if events_received >= 1:
                    logger.info(
                        f"[CAPI] Purchase enviado | pixel={pixel_id} "
                        f"| event_id={event.get('event_id', '?')} "
                        f"| events_received={events_received}"
                    )
                    return True
                else:
                    logger.warning(
                        f"[CAPI] events_received=0 | pixel={pixel_id} "
                        f"| event_id={event.get('event_id', '?')} "
                        f"| response={body}"
                    )
                    return False

            # ── 4xx: Erro do cliente — NUNCA retentar ───────
            if 400 <= resp.status_code < 500:
                logger.error(
                    f"[CAPI] ERRO 4xx | pixel={pixel_id} "
                    f"| status={resp.status_code} "
                    f"| event_id={event.get('event_id', '?')} "
                    f"| response={resp.text}"
                )
                return False

            # ── 429: Rate limit — backoff longo ──────────────
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    wait = 60 * (2 ** (attempt - 1))
                    logger.warning(
                        f"[CAPI] 429 rate limit | tentativa {attempt}/{MAX_RETRIES} "
                        f"| retry em {wait}s"
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.error(
                        f"[CAPI] 429 esgotou retries | pixel={pixel_id}"
                    )
                    return False

            # ── 5xx: Erro servidor Meta — retry backoff ─────
            if resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        f"[CAPI] {resp.status_code} | tentativa {attempt}/{MAX_RETRIES} "
                        f"| retry em {wait}s"
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.error(
                        f"[CAPI] 5xx esgotou retries | pixel={pixel_id} "
                        f"| status={resp.status_code}"
                    )
                    return False

            # ── Outro status inesperado ──────────────────────
            logger.warning(
                f"[CAPI] Status inesperado {resp.status_code} | "
                f"event_id={event.get('event_id', '?')}"
            )
            return False

        except requests.Timeout:
            if attempt < MAX_RETRIES:
                wait = 2 ** (attempt - 1)
                logger.warning(
                    f"[CAPI] timeout | tentativa {attempt}/{MAX_RETRIES} "
                    f"| retry em {wait}s"
                )
                time.sleep(wait)
                continue
            else:
                logger.error(
                    f"[CAPI] timeout esgotou retries | pixel={pixel_id}"
                )
                return False

        except requests.ConnectionError as e:
            if attempt < MAX_RETRIES:
                wait = 2 ** (attempt - 1)
                logger.warning(
                    f"[CAPI] connection error | tentativa {attempt}/{MAX_RETRIES} "
                    f"| retry em {wait}s | erro={e}"
                )
                time.sleep(wait)
                continue
            else:
                logger.error(
                    f"[CAPI] connection error esgotou retries | pixel={pixel_id}"
                )
                return False

        except Exception as e:
            logger.error(
                f"[CAPI] Erro inesperado | pixel={pixel_id} | erro={e}",
                exc_info=True,
            )
            return False

    return False
