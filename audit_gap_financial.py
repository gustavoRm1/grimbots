from datetime import datetime, timedelta

from app import app, db
from models import Payment

# Ajuste aqui se o timezone do DB estiver em UTC; assumindo timestamps já coerentes
PENDING_AGE_MINUTES = 20


def main():
    with app.app_context():
        # Contagem por status
        status_counts = (
            db.session.query(Payment.status, db.func.count(Payment.id))
            .group_by(Payment.status)
            .all()
        )
        counts_map = {status or 'NULL': count for status, count in status_counts}

        # Pendentes há mais de 20 minutos
        cutoff = datetime.utcnow() - timedelta(minutes=PENDING_AGE_MINUTES)
        stuck_pending = (
            Payment.query
            .filter(Payment.status == 'pending')
            .filter(Payment.created_at <= cutoff)
            .order_by(Payment.created_at.asc())
            .all()
        )

        # Integridade de campos críticos
        missing_tracking = Payment.query.filter(
            db.or_(Payment.tracking_token.is_(None), Payment.tracking_token == '')
        ).all()
        missing_gateway = Payment.query.filter(
            db.or_(Payment.gateway_transaction_id.is_(None), Payment.gateway_transaction_id == '')
        ).all()

        print("=== RESUMO POR STATUS ===")
        print(f"APPROVED/paid: {counts_map.get('paid', 0)}")
        print(f"PENDING: {counts_map.get('pending', 0)}")
        print(f"EXPIRED/cancelled/failed: {counts_map.get('expired', 0) + counts_map.get('cancelled', 0) + counts_map.get('failed', 0)}")
        print(f"OUTROS: {counts_map}")
        print()

        print(f"=== PENDENTES > {PENDING_AGE_MINUTES} MIN ===")
        if not stuck_pending:
            print("Nenhum pendente antigo encontrado.")
        else:
            for p in stuck_pending:
                print(f"ID={p.id} | gateway_id={p.gateway_transaction_id or '-'} | created_at={p.created_at} | value={p.amount}")
        print()

        print("=== INTEGRIDADE ===")
        print(f"Pagamentos sem tracking_token: {len(missing_tracking)}")
        if missing_tracking:
            print("IDs:", [p.id for p in missing_tracking])
        print(f"Pagamentos sem gateway_transaction_id: {len(missing_gateway)}")
        if missing_gateway:
            print("IDs:", [p.id for p in missing_gateway])


if __name__ == "__main__":
    main()
