#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 - << 'EOF'
from app import app, db
from models import Payment

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
        print("=" * 60)
        print("PAYMENT ID:", p.id)
        print("AMOUNT:", p.amount)
        print("CREATED:", p.created_at)
        print("BOT_USER_ID:", getattr(p, 'bot_user_id', None))
        print("PIXEL_ID:", getattr(p, 'meta_pixel_id', None))
        print("FBCLID:", getattr(p, 'fbclid', None))
        print("FBC:", getattr(p, 'fbc', None))
        print("FBP:", getattr(p, 'fbp', None))
        print("REDIRECT_ID:", getattr(p, 'redirect_id', None))
EOF
