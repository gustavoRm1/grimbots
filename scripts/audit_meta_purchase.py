from datetime import datetime, timedelta

from app import db
from models import Payment

START = datetime.now() - timedelta(hours=24)

payments = (
    Payment.query
    .filter(Payment.created_at >= START)
    .order_by(Payment.created_at.desc())
    .all()
)

print(f"\n🔍 Auditando {len(payments)} pagamentos\n")

for p in payments:
    print({
        "payment_id": p.id,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "meta_purchase_sent": p.meta_purchase_sent,
        "meta_purchase_sent_at": p.meta_purchase_sent_at.isoformat() if p.meta_purchase_sent_at else None,
        "meta_event_id": p.meta_event_id,
        "pageview_event_id": p.pageview_event_id,
        "fbclid": bool(p.fbclid),
        "fbc": bool(p.fbc),
        "fbp": bool(p.fbp),
    })
