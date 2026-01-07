import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app, db  # noqa: E402
from models import Payment  # noqa: E402

with app.app_context():
    payments = Payment.query.order_by(Payment.created_at.desc()).limit(20).all()

    for p in payments:
        print({
            "payment_id": p.id,
            "pageview_event_id": p.pageview_event_id,
            "purchase_event_id": p.meta_event_id,
            "purchase_sent_at": p.meta_purchase_sent_at.isoformat() if p.meta_purchase_sent_at else None,
        })
