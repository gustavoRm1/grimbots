import os
import sys
from collections import Counter

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app, db  # noqa: E402
from models import Payment  # noqa: E402

with app.app_context():
    ids = [
        p.meta_event_id
        for p in Payment.query
        .filter(Payment.meta_event_id.isnot(None))
        .all()
    ]

    counter = Counter(ids)
    duplicates = {k: v for k, v in counter.items() if v > 1}

    print("\n🚨 EVENT_ID DUPLICADOS:\n")
    for k, v in duplicates.items():
        print(k, "→", v, "pagamentos")

    if not duplicates:
        print("Nenhum event_id duplicado encontrado.")
