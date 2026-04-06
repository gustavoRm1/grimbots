from app import app, db
from internal_logic.core.models import Payment, BotUser
from sqlalchemy import desc


def audit():
    with app.app_context():
        print("=" * 60)
        print("🔍 AUDITORIA DE VENDAS RECENTES (Últimas 10)")
        print("=" * 60)

        payments = (
            Payment.query.filter(Payment.status.in_(["approved", "paid"]))
            .order_by(desc(Payment.created_at))
            .limit(10)
            .all()
        )

        if not payments:
            print("❌ Nenhuma venda encontrada no banco.")
            return

        print(f"{'ID':<8} | {'VALOR':<10} | {'DATA':<20} | {'FBCLID (DB)':<20} | {'BOT_USER ID'}")
        print("-" * 80)

        for p in payments:
            fbclid_status = "✅ PRESENTE" if p.fbclid else "❌ NULO (MISSING)"
            user_fbclid = "N/A"
            bot_user = getattr(p, "bot_user", None)
            bot_user_id = getattr(bot_user, "id", None)
            if bot_user:
                user_fbclid = "✅ NO USER" if bot_user.fbclid else "❌ NULO NO USER"

            created_at_str = (
                p.created_at.strftime("%d/%m %H:%M") if getattr(p, "created_at", None) else "N/A"
            )

            print(
                f"{p.id:<8} | {p.amount:<10} | {created_at_str:<20} | "
                f"{fbclid_status:<20} | {bot_user_id} ({user_fbclid})"
            )

            if p.fbclid:
                print(f"   ↳ FBC: {p.fbc} | FBP: {p.fbp}")

        print("=" * 60)


if __name__ == "__main__":
    audit()
