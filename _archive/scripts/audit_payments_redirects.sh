#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 - << 'EOF'
from app import app, db
from models import Payment

try:
    from models import Redirect
except ImportError:
    Redirect = None

with app.app_context():
    payments = (
        Payment.query
        .filter_by(status='paid')
        .order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )

    if not payments:
        print("Nenhum pagamento 'paid' encontrado.")

    for p in payments:
        redirect = None
        if Redirect and getattr(p, 'redirect_id', None):
            redirect = Redirect.query.get(p.redirect_id)
        print("=" * 60)
        print("PAYMENT:", p.id)
        print("REDIRECT_ID:", getattr(p, 'redirect_id', None))
        print("REDIRECT_PIXEL:", getattr(redirect, 'meta_pixel_id', None) if redirect else None)
        print("PAYMENT_PIXEL:", getattr(p, 'meta_pixel_id', None))
EOF
