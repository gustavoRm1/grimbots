import json
import argparse
from datetime import datetime

from app import app, db  # type: ignore
from models import Payment  # type: ignore
from utils.tracking_service import TrackingServiceV4  # type: ignore


def fmt_dt(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def audit_payment(payment_id: int):
    with app.app_context():
        payment = Payment.query.filter_by(id=payment_id).first()
        if not payment:
            print(json.dumps({"error": f"payment {payment_id} not found"}, ensure_ascii=False, indent=2))
            return

        tracking_token = getattr(payment, "tracking_token", None)
        info = {
            "payment": {
                "id": payment.id,
                "payment_id": payment.payment_id,
                "bot_id": payment.bot_id,
                "amount": payment.amount,
                "status": payment.status,
                "created_at": fmt_dt(payment.created_at),
                "paid_at": fmt_dt(payment.paid_at),
                "tracking_token": tracking_token,
            }
        }

        ts = TrackingServiceV4()
        redis_payload = None
        if tracking_token:
            try:
                redis_payload = ts.recover_tracking_data(tracking_token)
            except Exception as e:
                redis_payload = {"error": str(e)}

        info["redis_payload"] = {
            "pixel_id": redis_payload.get("pixel_id") if redis_payload else None,
            "meta_pixel_id": redis_payload.get("meta_pixel_id") if redis_payload else None,
            "redirect_id": redis_payload.get("redirect_id") if redis_payload else None,
            "fbp": redis_payload.get("fbp") if redis_payload else None,
            "fbc": redis_payload.get("fbc") if redis_payload else None,
            "utm_source": redis_payload.get("utm_source") if redis_payload else None,
            "utm_campaign": redis_payload.get("utm_campaign") if redis_payload else None,
            "event_source_url": redis_payload.get("event_source_url") if redis_payload else None,
            "raw": redis_payload,
        } if redis_payload is not None else None

        print(json.dumps(info, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Audit sale tracking in DB + Redis")
    parser.add_argument("payment_id", nargs="?", type=int, default=4015990, help="Payment ID to audit (default: 4015990)")
    args = parser.parse_args()
    audit_payment(args.payment_id)


if __name__ == "__main__":
    main()
