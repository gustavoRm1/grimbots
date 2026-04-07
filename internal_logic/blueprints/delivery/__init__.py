"""
Delivery Blueprint
==================
Blueprint para entrega de produtos e rastreamento Meta Pixel Client-Side.

ARQUITETURA: Client-Side (HTML-Only) com Callback de Deduplicação
- Purchase é disparado via JavaScript no template delivery.html
- Server-side apenas injeta variáveis no template
- Deduplicação via API callback /api/tracking/mark-purchase-sent

LÓGICA RESGATADA DO app.py LEGADO - Operação Resgate de Dados
"""

from flask import Blueprint
from .routes import delivery_bp

__all__ = ['delivery_bp']
