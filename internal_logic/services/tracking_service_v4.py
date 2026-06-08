"""
Tracking Service V4.1 — Alias para utils.tracking_service
=========================================================
Este arquivo agora é um alias. Toda implementação real está em
utils/tracking_service.py (a versão QI 300 com merge lógico,
indexação multi-chave e validação de token).
"""

import logging
logger = logging.getLogger(__name__)

from utils.tracking_service import TrackingServiceV4, TrackingService

logger.info("ℹ️ internal_logic/services/tracking_service_v4.py carregado — usando utils.tracking_service")

