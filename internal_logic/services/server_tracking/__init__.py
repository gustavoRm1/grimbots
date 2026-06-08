"""
Server-Side Meta CAPI Tracking (Dual-Mode)
==========================================

DUAL-MODE ARCHITECTURE:
├── HTML-ONLY: pool has pixel_id but NO access_token
│   → Purchase fires from browser (delivery.html)
│   → Server does NOT send Purchase
│
└── SERVER: pool has pixel_id AND access_token
    → Purchase sent via RQ job (purchase_reconciler)
    → delivery.html Pixel disabled (pixel_id = None)
    → Tracking independente do cliente abrir o delivery

A pool NEVER runs both modes simultaneously.
"""


def is_server_mode(pool) -> bool:
    """True se pool está em SERVER MODE (access_token presente).

    SERVER MODE ativa quando o seller configura TANTO o Pixel ID
    quanto o Access Token. Nesse modo:
    - Purchase é enviado via servidor (RQ job)
    - delivery.html NÃO renderiza o Pixel
    - Tracking funciona mesmo sem o cliente abrir o link de entrega
    """
    if not pool:
        return False
    return bool(
        pool.meta_tracking_enabled
        and pool.meta_pixel_id
        and pool.meta_access_token
    )


def is_html_only(pool) -> bool:
    """True se pool está em HTML-ONLY mode (sem access_token).

    HTML-ONLY mode quando o seller configura APENAS o Pixel ID.
    Nesse modo:
    - Purchase dispara via browser Pixel no delivery.html
    - Servidor não envia nada
    - Tracking depende do cliente abrir o link de entrega
    """
    if not pool:
        return False
    return bool(
        pool.meta_tracking_enabled
        and pool.meta_pixel_id
        and not pool.meta_access_token
    )
