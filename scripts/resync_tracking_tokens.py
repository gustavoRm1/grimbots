from datetime import datetime, timedelta

from app import app
from models import Payment
from utils.tracking_service import TrackingServiceV4

service = TrackingServiceV4()
CUTOFF_HOURS = 48


def _compact(payload):
    return {k: v for k, v in payload.items() if v is not None}


def main():
    cutoff = datetime.utcnow() - timedelta(hours=CUTOFF_HOURS)

    with app.app_context():
        payments = (
            Payment.query
            .filter(Payment.tracking_token.isnot(None))
            .filter(Payment.created_at >= cutoff)
            .order_by(Payment.created_at.desc())
            .limit(1000)
            .all()
        )

        print(f"Found {len(payments)} payments with tracking_token to resync")
        for payment in payments:
            token = payment.tracking_token
            payload = {
                "tracking_token": token,
                "payment_id": payment.payment_id,
                "bot_id": payment.bot_id,
                "customer_user_id": payment.customer_user_id,
                "fbp": getattr(payment, "fbp", None),
                "fbc": getattr(payment, "fbc", None),
                "fbclid": getattr(payment, "fbclid", None),
                "pageview_event_id": getattr(payment, "pageview_event_id", None),
                "client_ip": getattr(payment, "client_ip", None),
                "client_user_agent": getattr(payment, "client_user_agent", None),
            }
            ok = service.save_tracking_token(token, _compact(payload))
            print(f"{payment.payment_id} -> {token} -> {'OK' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
