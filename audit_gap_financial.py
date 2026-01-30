from app import app, db
from models import Payment, User, Bot

TARGET_EMAIL = "grcontato001@gmail.com"


def main():
    with app.app_context():
        user = User.query.filter_by(email=TARGET_EMAIL).first()
        if not user:
            print(f"Usuário não encontrado: {TARGET_EMAIL}")
            return

        bot_ids = [b.id for b in user.bots]
        if not bot_ids:
            print(f"Usuário {TARGET_EMAIL} não possui bots.")
            return

        payments_q = Payment.query.filter(Payment.bot_id.in_(bot_ids))

        # Resumo de status
        status_counts = (
            db.session.query(Payment.status, db.func.count(Payment.id))
            .filter(Payment.bot_id.in_(bot_ids))
            .group_by(Payment.status)
            .all()
        )
        counts_map = {status or 'NULL': count for status, count in status_counts}
        total = sum(counts_map.values())

        print("=== AUDITORIA FINANCEIRA: grcontato001@gmail.com ===")
        print(f"1. Bots do Usuário: {bot_ids}")
        print("2. Resumo de Pagamentos (DB Local):")
        print(f"   - Total Registrados: {total}")
        print(f"   - Status PENDING: {counts_map.get('pending', 0)}")
        print(f"   - Status APPROVED/paid: {counts_map.get('paid', 0)}")
        print(f"   - Status EXPIRED/cancelled/failed: {counts_map.get('expired', 0) + counts_map.get('cancelled', 0) + counts_map.get('failed', 0)}")

        print("3. Análise de GAP: Últimos 10 Pagamentos")
        last_10 = payments_q.order_by(Payment.created_at.desc()).limit(10).all()
        for p in last_10:
            print(f"   ID={p.id} | gateway_id={p.gateway_transaction_id or '-'} | created_at={p.created_at} | status={p.status}")

        # IDs úteis para grep
        print("\nIDs de Bot para grep em logs:")
        print(" ".join(f"BotID_{bid}" for bid in bot_ids))


if __name__ == "__main__":
    main()
